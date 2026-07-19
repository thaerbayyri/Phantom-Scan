/**
 * @file edge_processing.c
 * @brief ADR-039 Edge Intelligence — dual-core CSI processing pipeline.
 *
 * Core 0 (WiFi task): Pushes raw CSI frames into lock-free SPSC ring buffer.
 * Core 1 (DSP task):  Pops frames, runs signal processing pipeline:
 *   1. Phase extraction from I/Q pairs
 *   2. Phase unwrapping (continuous phase)
 *   3. Welford variance tracking per subcarrier
 *   4. Top-K subcarrier selection by variance
 *   5. Biquad IIR bandpass → breathing (0.1-0.5 Hz), heart rate (0.8-2.0 Hz),
 *      re-tuned to the measured (EMA) CSI sample rate
 *   6. BPM estimation — breathing: zero-crossing; heart rate: autocorrelation
 *      with breathing-harmonic rejection + median smoothing
 *   7. Presence detection (adaptive or fixed threshold)
 *   8. Fall detection (phase acceleration)
 *   9. Multi-person vitals via subcarrier group clustering
 *  10. Delta compression (XOR + RLE) for bandwidth reduction
 *  11. Feature-state broadcast (magic 0xC5110006, with real confidences;
 *      the 0xC5110002 vitals struct remains internal for display/WASM)
 */

#include "edge_processing.h"
#include "wasm_runtime.h"
#include "stream_sender.h"
#include "rv_feature_state.h"

#include <math.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "sdkconfig.h"
#include "nvs_config.h"

static const char *TAG = "edge_proc";
extern nvs_config_t g_nvs_config;

/* ======================================================================
 * SPSC Ring Buffer (lock-free, single-producer single-consumer)
 * ====================================================================== */

static edge_ring_buf_t s_ring;
static edge_runtime_stats_t s_runtime_stats;

static inline bool ring_push(const uint8_t *iq, uint16_t len,
                             int8_t rssi, uint8_t channel)
{
    uint32_t next = (s_ring.head + 1) % EDGE_RING_SLOTS;
    if (next == s_ring.tail) {
        s_runtime_stats.enqueue_drops++;
        return false;  /* Full — drop frame. */
    }

    uint32_t occupancy = (s_ring.head >= s_ring.tail)
        ? (s_ring.head - s_ring.tail)
        : (EDGE_RING_SLOTS - s_ring.tail + s_ring.head);
    if (occupancy > s_runtime_stats.queue_high_watermark) {
        s_runtime_stats.queue_high_watermark = occupancy;
    }

    edge_ring_slot_t *slot = &s_ring.slots[s_ring.head];
    uint16_t copy_len = (len > EDGE_MAX_IQ_BYTES) ? EDGE_MAX_IQ_BYTES : len;
    memcpy(slot->iq_data, iq, copy_len);
    slot->iq_len = copy_len;
    slot->rssi = rssi;
    slot->channel = channel;
    slot->timestamp_us = (uint32_t)(esp_timer_get_time() & 0xFFFFFFFF);

    /* Memory barrier: ensure slot data is visible before advancing head. */
    __sync_synchronize();
    s_ring.head = next;
    return true;
}

static inline bool ring_pop(edge_ring_slot_t *out)
{
    if (s_ring.tail == s_ring.head) {
        return false;  /* Empty. */
    }

    memcpy(out, &s_ring.slots[s_ring.tail], sizeof(edge_ring_slot_t));

    __sync_synchronize();
    s_ring.tail = (s_ring.tail + 1) % EDGE_RING_SLOTS;
    return true;
}

/* Biquad IIR filter design/process, phase extraction/unwrap, and the BPM
 * estimators used below now live in edge_dsp_pure.c (ESP-IDF-free, so they
 * are host-testable — see main/test/test_edge_dsp_pure.c, PS-AUDIT-002).
 * edge_processing.h pulls in their declarations via edge_dsp_pure.h. */

/* ======================================================================
 * Welford Running Statistics
 * ====================================================================== */

static inline void welford_reset(edge_welford_t *w)
{
    w->mean = 0.0;
    w->m2   = 0.0;
    w->count = 0;
}

static inline void welford_update(edge_welford_t *w, double x)
{
    w->count++;
    double delta = x - w->mean;
    w->mean += delta / (double)w->count;
    double delta2 = x - w->mean;
    w->m2 += delta * delta2;
}

static inline double welford_variance(const edge_welford_t *w)
{
    return (w->count > 1) ? (w->m2 / (double)(w->count - 1)) : 0.0;
}

/*
 * Static scratch for building contiguous signal buffers from the filtered
 * rings. Lives in .bss instead of the DSP task stack: two 256-float buffers
 * are ~2 KB, which the 8 KB task stack cannot spare on top of the autocorr
 * call chain.
 */
static float s_scratch_br[EDGE_PHASE_HISTORY_LEN];
static float s_scratch_hr[EDGE_PHASE_HISTORY_LEN];

/* Median smoother for the emitted heart rate. The per-frame autocorr estimate
 * still has occasional single-frame outliers (startup transient before the
 * filters re-tune, momentary harmonic mis-locks); a median over the last few
 * VALID estimates stops the reported HR from jumping between frames without
 * lagging real changes much. Only valid (in-range) estimates are pushed, so
 * out-of-range/zero results never pollute the window. */
#define HR_SMOOTH_N 13
static float   s_hr_ring[HR_SMOOTH_N];
static uint8_t s_hr_ring_n;
static uint8_t s_hr_ring_idx;

static float hr_smooth_push(float hr)
{
    s_hr_ring[s_hr_ring_idx] = hr;
    s_hr_ring_idx = (uint8_t)((s_hr_ring_idx + 1) % HR_SMOOTH_N);
    if (s_hr_ring_n < HR_SMOOTH_N) s_hr_ring_n++;

    float tmp[HR_SMOOTH_N];
    for (uint8_t i = 0; i < s_hr_ring_n; i++) tmp[i] = s_hr_ring[i];
    for (uint8_t i = 1; i < s_hr_ring_n; i++) {       /* insertion sort, tiny N */
        float v = tmp[i];
        int j = (int)i - 1;
        while (j >= 0 && tmp[j] > v) { tmp[j + 1] = tmp[j]; j--; }
        tmp[j + 1] = v;
    }
    return tmp[s_hr_ring_n / 2];
}

/* ======================================================================
 * DSP Pipeline State
 * ====================================================================== */

/** Edge processing configuration. */
static edge_config_t s_cfg;

/** Per-subcarrier running variance (for top-K selection). */
static edge_welford_t s_subcarrier_var[EDGE_MAX_SUBCARRIERS];

/** Previous phase per subcarrier (for unwrapping). */
static float s_prev_phase[EDGE_MAX_SUBCARRIERS];
static bool  s_phase_initialized;

/** Top-K subcarrier indices (sorted by variance, descending). */
static uint8_t s_top_k[EDGE_TOP_K];
static uint8_t s_top_k_count;

/** Phase history for the primary (highest-variance) subcarrier. */
static float s_phase_history[EDGE_PHASE_HISTORY_LEN];
static uint16_t s_history_len;
static uint16_t s_history_idx;

/** Biquad filters for breathing and heart rate. */
static edge_biquad_t s_bq_breathing;
static edge_biquad_t s_bq_heartrate;

/** Filtered signal histories for BPM estimation. */
static float s_breathing_filtered[EDGE_PHASE_HISTORY_LEN];
static float s_heartrate_filtered[EDGE_PHASE_HISTORY_LEN];

/** Latest vitals state. */
static float    s_breathing_bpm;
static float    s_heartrate_bpm;
static float    s_motion_energy;
static float    s_presence_score;
static bool     s_presence_detected;
static bool     s_fall_detected;
static int8_t   s_latest_rssi;
static uint32_t s_frame_count;

/** Vitals confidences: autocorr peak ratio mapped to 0..1 (see step 7). */
static float s_resp_conf;
static float s_hr_conf;

/** Presence threshold in effect (configured / calibrated / default) — kept
 *  so the vitals motion flag uses the same machinery as presence. */
static float s_presence_threshold_active;

/** Feature-state (0xC5110006) sequence counter. */
static uint16_t s_feature_state_seq;

/** Measured CSI sample rate (EMA over inter-frame dt) and the fs the biquads
 *  were last designed at. The callback rate is variable (~13-19 Hz with
 *  self-ping); a fixed assumed fs mis-scales every BPM estimate. */
static float    s_sample_rate_hz;
static float    s_filter_design_fs;
static uint32_t s_last_frame_ts_us;

/** Previous phase velocity for fall detection (acceleration). */
static float s_prev_phase_velocity;

/** Adaptive calibration state. */
static bool     s_calibrated;
static float    s_calib_sum;
static float    s_calib_sum_sq;
static uint32_t s_calib_count;
static float    s_adaptive_threshold;

/** Last vitals send timestamp. */
static int64_t s_last_vitals_send_us;

/** Delta compression state. */
static uint8_t s_prev_iq[EDGE_MAX_IQ_BYTES];
static uint16_t s_prev_iq_len;
static bool s_has_prev_iq;

/** Multi-person vitals state. */
static edge_person_vitals_t s_persons[EDGE_MAX_PERSONS];
static edge_biquad_t s_person_bq_br[EDGE_MAX_PERSONS];
static edge_biquad_t s_person_bq_hr[EDGE_MAX_PERSONS];
static float s_person_br_filt[EDGE_MAX_PERSONS][EDGE_PHASE_HISTORY_LEN];
static float s_person_hr_filt[EDGE_MAX_PERSONS][EDGE_PHASE_HISTORY_LEN];

/** Latest vitals packet (thread-safe via volatile copy). */
static volatile edge_vitals_pkt_t s_latest_pkt;
static volatile bool s_pkt_valid;

/* ======================================================================
 * Top-K Subcarrier Selection
 * ====================================================================== */

/**
 * Select top-K subcarriers by variance (descending).
 * Uses partial insertion sort — O(n*K) which is fine for n <= 128.
 */
static void update_top_k(uint16_t n_subcarriers)
{
    uint8_t k = s_cfg.top_k_count;
    if (k > EDGE_TOP_K) k = EDGE_TOP_K;
    if (k > n_subcarriers) k = (uint8_t)n_subcarriers;

    /* Simple selection: find K largest variances. */
    bool used[EDGE_MAX_SUBCARRIERS];
    memset(used, 0, sizeof(used));

    for (uint8_t ki = 0; ki < k; ki++) {
        double best_var = -1.0;
        uint8_t best_idx = 0;

        for (uint16_t sc = 0; sc < n_subcarriers; sc++) {
            if (!used[sc]) {
                double v = welford_variance(&s_subcarrier_var[sc]);
                if (v > best_var) {
                    best_var = v;
                    best_idx = (uint8_t)sc;
                }
            }
        }

        s_top_k[ki] = best_idx;
        used[best_idx] = true;
    }

    s_top_k_count = k;
}

/* ======================================================================
 * Adaptive Presence Calibration
 * ====================================================================== */

/*
 * Learns the empty-room noise floor: accumulates motion energy over the
 * first EDGE_CALIB_FRAMES frames, then fixes the presence threshold at
 * mean + EDGE_CALIB_SIGMA_MULT * sigma (floored at 0.01) — the room must be
 * empty during boot calibration for presence detection to be meaningful.
 */
static void calibration_update(float motion)
{
    if (s_calibrated) return;

    s_calib_sum += motion;
    s_calib_sum_sq += motion * motion;
    s_calib_count++;

    if (s_calib_count >= EDGE_CALIB_FRAMES) {
        float mean = s_calib_sum / (float)s_calib_count;
        float var = (s_calib_sum_sq / (float)s_calib_count) - (mean * mean);
        float sigma = (var > 0.0f) ? sqrtf(var) : 0.001f;

        s_adaptive_threshold = mean + EDGE_CALIB_SIGMA_MULT * sigma;
        if (s_adaptive_threshold < 0.01f) {
            s_adaptive_threshold = 0.01f;
        }

        s_calibrated = true;
        ESP_LOGI(TAG, "Adaptive calibration complete: mean=%.4f sigma=%.4f "
                 "threshold=%.4f (from %lu frames)",
                 mean, sigma, s_adaptive_threshold,
                 (unsigned long)s_calib_count);
    }
}

/* ======================================================================
 * Delta Compression (XOR + RLE)
 * ====================================================================== */

/**
 * Delta-compress I/Q data relative to previous frame.
 * Format: [XOR'd bytes], then RLE-encoded.
 *
 * @param curr       Current I/Q data.
 * @param len        Length of I/Q data.
 * @param out        Output compressed buffer.
 * @param out_max    Max output buffer size.
 * @return Compressed size, or 0 if compression would expand the data.
 */
static uint16_t delta_compress(const uint8_t *curr, uint16_t len,
                               uint8_t *out, uint16_t out_max)
{
    if (!s_has_prev_iq || len != s_prev_iq_len || len == 0) {
        return 0;
    }

    /* XOR delta. */
    uint8_t xor_buf[EDGE_MAX_IQ_BYTES];
    for (uint16_t i = 0; i < len; i++) {
        xor_buf[i] = curr[i] ^ s_prev_iq[i];
    }

    /* RLE encode: [value, count] pairs.
     * If count > 255, emit multiple pairs. */
    uint16_t out_idx = 0;

    uint16_t i = 0;
    while (i < len) {
        uint8_t val = xor_buf[i];
        uint16_t run = 1;
        while (i + run < len && xor_buf[i + run] == val && run < 255) {
            run++;
        }

        if (out_idx + 2 > out_max) return 0;  /* Would overflow. */
        out[out_idx++] = val;
        out[out_idx++] = (uint8_t)run;
        i += run;
    }

    /* Only use compression if it actually saves space. */
    if (out_idx >= len) {
        return 0;
    }

    return out_idx;
}

/**
 * Send a compressed CSI frame (magic 0xC5110003).
 *
 * Header:
 *   [0..3]   Magic 0xC5110003 (LE)
 *   [4]      Node ID
 *   [5]      Channel
 *   [6..7]   Original I/Q length (LE u16)
 *   [8..9]   Compressed length (LE u16)
 *   [10..]   Compressed data
 */
static void send_compressed_frame(const uint8_t *iq_data, uint16_t iq_len,
                                  uint8_t channel)
{
    uint8_t comp_buf[EDGE_MAX_IQ_BYTES];
    uint16_t comp_len = delta_compress(iq_data, iq_len,
                                       comp_buf, sizeof(comp_buf));
    if (comp_len == 0) {
        /* Compression didn't help — skip sending compressed version. */
        goto store_prev;
    }

    /* Build compressed frame packet. */
    uint16_t pkt_size = 10 + comp_len;
    uint8_t pkt[10 + EDGE_MAX_IQ_BYTES];

    uint32_t magic = EDGE_COMPRESSED_MAGIC;
    memcpy(&pkt[0], &magic, 4);

    pkt[4] = g_nvs_config.node_id;
    pkt[5] = channel;
    memcpy(&pkt[6], &iq_len, 2);
    memcpy(&pkt[8], &comp_len, 2);
    memcpy(&pkt[10], comp_buf, comp_len);

    stream_sender_send(pkt, pkt_size);

    ESP_LOGD(TAG, "Compressed frame: %u → %u bytes (%.0f%% reduction)",
             iq_len, comp_len,
             (1.0f - (float)comp_len / (float)iq_len) * 100.0f);

store_prev:
    /* Store current frame as reference for next delta. */
    memcpy(s_prev_iq, iq_data, iq_len);
    s_prev_iq_len = iq_len;
    s_has_prev_iq = true;
}

/* ======================================================================
 * Multi-Person Vitals
 * ====================================================================== */

/**
 * Update multi-person vitals by assigning top-K subcarriers to person groups.
 *
 * Division strategy: top-K subcarriers are evenly divided among
 * up to EDGE_MAX_PERSONS groups. Each group tracks independent
 * phase history and BPM estimation.
 */
static void update_multi_person_vitals(const uint8_t *iq_data, uint16_t n_sc,
                                       float sample_rate)
{
    if (s_top_k_count < 2) return;

    /* Determine number of active persons based on available subcarriers. */
    uint8_t n_persons = s_top_k_count / 2;
    if (n_persons > EDGE_MAX_PERSONS) n_persons = EDGE_MAX_PERSONS;
    if (n_persons < 1) n_persons = 1;

    uint8_t subs_per_person = s_top_k_count / n_persons;

    for (uint8_t p = 0; p < n_persons; p++) {
        edge_person_vitals_t *pv = &s_persons[p];
        pv->active = true;
        pv->subcarrier_idx = s_top_k[p * subs_per_person];

        /* Average phase across this person's subcarrier group. */
        float avg_phase = 0.0f;
        uint8_t count = 0;
        for (uint8_t s = 0; s < subs_per_person; s++) {
            uint8_t sc_idx = s_top_k[p * subs_per_person + s];
            if (sc_idx < n_sc) {
                avg_phase += extract_phase(iq_data, sc_idx);
                count++;
            }
        }
        if (count > 0) avg_phase /= (float)count;

        /* Unwrap and store in history. */
        if (pv->history_len > 0) {
            uint16_t prev_idx = (pv->history_idx + EDGE_PHASE_HISTORY_LEN - 1)
                                % EDGE_PHASE_HISTORY_LEN;
            avg_phase = unwrap_phase(pv->phase_history[prev_idx], avg_phase);
        }

        pv->phase_history[pv->history_idx] = avg_phase;
        pv->history_idx = (pv->history_idx + 1) % EDGE_PHASE_HISTORY_LEN;
        if (pv->history_len < EDGE_PHASE_HISTORY_LEN) pv->history_len++;

        /* Filter and estimate BPM. */
        float br_val = biquad_process(&s_person_bq_br[p], avg_phase);
        float hr_val = biquad_process(&s_person_bq_hr[p], avg_phase);

        uint16_t idx = (pv->history_idx + EDGE_PHASE_HISTORY_LEN - 1)
                       % EDGE_PHASE_HISTORY_LEN;
        s_person_br_filt[p][idx] = br_val;
        s_person_hr_filt[p][idx] = hr_val;

        /* Estimate BPM when we have enough history. */
        if (pv->history_len >= 64) {
            /* Build contiguous buffers (static scratch — persons are
             * processed sequentially on the single DSP task). */
            uint16_t buf_len = pv->history_len;

            for (uint16_t i = 0; i < buf_len; i++) {
                uint16_t ri = (pv->history_idx + EDGE_PHASE_HISTORY_LEN
                               - buf_len + i) % EDGE_PHASE_HISTORY_LEN;
                s_scratch_br[i] = s_person_br_filt[p][ri];
                s_scratch_hr[i] = s_person_hr_filt[p][ri];
            }

            float br = estimate_bpm_zero_crossing(s_scratch_br, buf_len, sample_rate);
            float br_rob = estimate_periodicity_autocorr(s_scratch_br, buf_len,
                                                         sample_rate, 6.0f, 40.0f,
                                                         0.0f, NULL);
            float hr = estimate_periodicity_autocorr(s_scratch_hr, buf_len,
                                                     sample_rate, 45.0f, 180.0f,
                                                     br_rob / 60.0f, NULL);

            /* Sanity clamp. */
            if (br >= 6.0f && br <= 40.0f) pv->breathing_bpm = br;
            if (hr >= 40.0f && hr <= 180.0f) pv->heartrate_bpm = hr;
        }
    }

    /* Mark remaining persons as inactive. */
    for (uint8_t p = n_persons; p < EDGE_MAX_PERSONS; p++) {
        s_persons[p].active = false;
    }
}

/* ======================================================================
 * Vitals Packet Sending
 * ====================================================================== */

/*
 * Refresh the internal 0xC5110002 vitals snapshot consumed by
 * edge_get_vitals() (display/WASM). NOT sent on the wire anymore — the
 * 0xC5110006 feature-state below is the wire format, carrying the same
 * metrics plus real confidence fields (the server would otherwise fabricate
 * 100% confidence for this packet's estimates).
 */
static void update_vitals_state(void)
{
    edge_vitals_pkt_t pkt;
    memset(&pkt, 0, sizeof(pkt));

    pkt.magic = EDGE_VITALS_MAGIC;
    pkt.node_id = g_nvs_config.node_id;

    pkt.flags = 0;
    if (s_presence_detected) pkt.flags |= 0x01;
    if (s_fall_detected)     pkt.flags |= 0x02;
    /* Motion bit uses the same threshold machinery as presence (configured /
     * calibrated / default) instead of an unrelated hardcoded constant. */
    if (s_motion_energy > s_presence_threshold_active) pkt.flags |= 0x04;

    pkt.breathing_rate = (uint16_t)(s_breathing_bpm * 100.0f);
    pkt.heartrate = (uint32_t)(s_heartrate_bpm * 10000.0f);
    pkt.rssi = s_latest_rssi;

    /* Count active persons. */
    uint8_t n_active = 0;
    for (uint8_t p = 0; p < EDGE_MAX_PERSONS; p++) {
        if (s_persons[p].active) n_active++;
    }
    pkt.n_persons = n_active;

    pkt.motion_energy = s_motion_energy;
    pkt.presence_score = s_presence_score;
    pkt.timestamp_ms = (uint32_t)(esp_timer_get_time() / 1000);

    /* Update thread-safe copy. */
    s_latest_pkt = pkt;
    s_pkt_valid = true;
}

/*
 * Send the 0xC5110006 rv_feature_state packet — the board's wire format for
 * DSP results. motion/presence carry the same raw values as the internal
 * vitals snapshot so dashboard readings stay continuous across firmware
 * versions; confidences are real autocorr peak ratios (see step 7).
 */
static void send_feature_state_packet(void)
{
    rv_feature_state_t pkt;
    memset(&pkt, 0, sizeof(pkt));

    pkt.motion_score     = s_motion_energy;
    pkt.presence_score   = s_presence_score;
    pkt.respiration_bpm  = s_breathing_bpm;
    pkt.respiration_conf = s_resp_conf;
    pkt.heartbeat_bpm    = s_heartrate_bpm;
    pkt.heartbeat_conf   = s_hr_conf;
    pkt.anomaly_score    = s_fall_detected ? 1.0f : 0.0f;
    pkt.env_shift_score  = 0.0f;
    pkt.node_coherence   = 0.0f;

    pkt.quality_flags = 0;
    if (s_presence_detected)     pkt.quality_flags |= RV_QFLAG_PRESENCE_VALID;
    if (s_breathing_bpm > 0.0f)  pkt.quality_flags |= RV_QFLAG_RESPIRATION_VALID;
    if (s_heartrate_bpm > 0.0f)  pkt.quality_flags |= RV_QFLAG_HEARTBEAT_VALID;
    if (s_fall_detected)         pkt.quality_flags |= RV_QFLAG_ANOMALY_TRIGGERED;
    if (!s_calibrated && s_cfg.presence_thresh == 0.0f) {
        pkt.quality_flags |= RV_QFLAG_CALIBRATING;
    }

    rv_feature_state_finalize(&pkt, g_nvs_config.node_id,
                              s_feature_state_seq++,
                              (uint64_t)esp_timer_get_time(), 0);

    stream_sender_send((const uint8_t *)&pkt, sizeof(pkt));
}

/* ======================================================================
 * Main DSP Pipeline (runs on Core 1)
 * ====================================================================== */

/*
 * Board-side presence/motion pipeline, one CSI frame per call. Independent of
 * the host DSP: results ride the 1 Hz rv_feature_state packet and are shown
 * side-by-side on the dashboard's Board DSP card, never fused with the host
 * target math. Steps: phase extract/unwrap -> per-subcarrier Welford variance
 * -> top-K subcarrier pick -> breathing/heart bandpass -> zero-crossing BPM ->
 * motion energy (phase variance) -> presence threshold -> fall detection.
 */
static void process_frame(const edge_ring_slot_t *slot)
{
    uint16_t n_subcarriers = slot->iq_len / 2;
    if (n_subcarriers == 0 || n_subcarriers > EDGE_MAX_SUBCARRIERS) return;

    s_frame_count++;
    s_latest_rssi = slot->rssi;

    /* Measure the REAL CSI sample rate from inter-frame timestamps. The
     * callback rate is variable (self-ping + ambient traffic, ~13-19 Hz);
     * a fixed assumed fs both scales BPM wrong (true ~87 BPM can read ~45)
     * and detunes the bandpass filters. EMA-smooth and clamp to a plausible
     * band. */
    if (s_last_frame_ts_us != 0 && slot->timestamp_us > s_last_frame_ts_us) {
        float dt = (float)(slot->timestamp_us - s_last_frame_ts_us) * 1e-6f;
        if (dt > 0.02f && dt < 0.5f) {   /* 2-50 Hz plausible; reject gaps/hops */
            float inst = 1.0f / dt;
            s_sample_rate_hz += 0.05f * (inst - s_sample_rate_hz);
            if (s_sample_rate_hz < 8.0f)  s_sample_rate_hz = 8.0f;
            if (s_sample_rate_hz > 30.0f) s_sample_rate_hz = 30.0f;
        }
    }
    s_last_frame_ts_us = slot->timestamp_us;

    /* Re-tune the biquads if the measured rate has drifted from their design
     * fs, so the breathing (0.1-0.5 Hz) and HR (0.8-2.0 Hz) passbands stay in
     * real Hz. biquad_bandpass_design resets delay state, so only redesign on
     * real drift (>15%) — the estimation windows average over the one-time
     * transient. */
    if (fabsf(s_sample_rate_hz - s_filter_design_fs) > 0.15f * s_filter_design_fs) {
        biquad_bandpass_design(&s_bq_breathing, s_sample_rate_hz, 0.1f, 0.5f);
        biquad_bandpass_design(&s_bq_heartrate, s_sample_rate_hz, 0.8f, 2.0f);
        for (uint8_t pp = 0; pp < EDGE_MAX_PERSONS; pp++) {
            biquad_bandpass_design(&s_person_bq_br[pp], s_sample_rate_hz, 0.1f, 0.5f);
            biquad_bandpass_design(&s_person_bq_hr[pp], s_sample_rate_hz, 0.8f, 2.0f);
        }
        s_filter_design_fs = s_sample_rate_hz;
        ESP_LOGI(TAG, "Biquads re-tuned to measured fs=%.1f Hz", s_sample_rate_hz);
    }

    const float sample_rate = s_sample_rate_hz;

    /* --- Step 1-2: Phase extraction + unwrapping per subcarrier --- */
    float phases[EDGE_MAX_SUBCARRIERS];
    for (uint16_t sc = 0; sc < n_subcarriers; sc++) {
        float raw_phase = extract_phase(slot->iq_data, sc);

        if (s_phase_initialized) {
            phases[sc] = unwrap_phase(s_prev_phase[sc], raw_phase);
        } else {
            phases[sc] = raw_phase;
        }
        s_prev_phase[sc] = phases[sc];
    }
    s_phase_initialized = true;

    /* --- Step 3: Welford variance update per subcarrier --- */
    for (uint16_t sc = 0; sc < n_subcarriers; sc++) {
        welford_update(&s_subcarrier_var[sc], (double)phases[sc]);
    }

    /* --- Step 4: Top-K selection (every 100 frames to amortize cost) --- */
    if ((s_frame_count % 100) == 1 || s_top_k_count == 0) {
        update_top_k(n_subcarriers);
    }

    if (s_top_k_count == 0) return;

    /* --- Step 5: Phase of primary (highest-variance) subcarrier --- */
    float primary_phase = phases[s_top_k[0]];

    /* Store in phase history ring buffer. */
    s_phase_history[s_history_idx] = primary_phase;
    s_history_idx = (s_history_idx + 1) % EDGE_PHASE_HISTORY_LEN;
    if (s_history_len < EDGE_PHASE_HISTORY_LEN) s_history_len++;

    /* --- Step 6: Biquad bandpass filtering --- */
    float br_val = biquad_process(&s_bq_breathing, primary_phase);
    float hr_val = biquad_process(&s_bq_heartrate, primary_phase);

    uint16_t filt_idx = (s_history_idx + EDGE_PHASE_HISTORY_LEN - 1)
                        % EDGE_PHASE_HISTORY_LEN;
    s_breathing_filtered[filt_idx] = br_val;
    s_heartrate_filtered[filt_idx] = hr_val;

    /* --- Step 7: BPM estimation ---
     * Breathing: zero-crossing on the band-filtered signal, plus a robust
     * autocorrelation estimate whose fundamental drives HR harmonic
     * rejection (a breathing harmonic otherwise aliases into the HR band).
     * Heart rate: autocorrelation periodicity search with harmonic
     * rejection, median-smoothed over the last HR_SMOOTH_N valid estimates.
     * Confidences are the autocorr peak ratios mapped linearly from the
     * acceptance floor (0.2) to saturation (0.8). */
    if (s_history_len >= 64) {
        /* Build contiguous buffers from ring (static scratch, .bss). */
        uint16_t buf_len = s_history_len;

        for (uint16_t i = 0; i < buf_len; i++) {
            uint16_t ri = (s_history_idx + EDGE_PHASE_HISTORY_LEN
                           - buf_len + i) % EDGE_PHASE_HISTORY_LEN;
            s_scratch_br[i] = s_breathing_filtered[ri];
            s_scratch_hr[i] = s_heartrate_filtered[ri];
        }

        float br_ratio = 0.0f, hr_ratio = 0.0f;
        float br_bpm = estimate_bpm_zero_crossing(s_scratch_br, buf_len, sample_rate);
        /* Robust breathing period (autocorr) drives HR harmonic rejection. */
        float br_rob = estimate_periodicity_autocorr(s_scratch_br, buf_len, sample_rate,
                                                     EDGE_BREATHING_BPM_MIN,
                                                     EDGE_BREATHING_BPM_MAX,
                                                     0.0f, &br_ratio);
        float hr_bpm = estimate_periodicity_autocorr(s_scratch_hr, buf_len, sample_rate,
                                                     45.0f, 180.0f, br_rob / 60.0f,
                                                     &hr_ratio);

        /* Sanity clamp: breathing band shared with the presence verdict's
         * periodicity check (edge_dsp_pure.h, PS-AUDIT-002); heart rate 40-180 BPM. */
        if (br_bpm >= EDGE_BREATHING_BPM_MIN && br_bpm <= EDGE_BREATHING_BPM_MAX) {
            s_breathing_bpm = br_bpm;
        }
        if (hr_bpm >= 40.0f && hr_bpm <= 180.0f) s_heartrate_bpm = hr_smooth_push(hr_bpm);

        /* Confidence: clamp((ratio - 0.2) / 0.6, 0, 1); 0 when no peak. */
        float rc = (br_ratio - 0.2f) / 0.6f;
        float hc = (hr_ratio - 0.2f) / 0.6f;
        s_resp_conf = (rc < 0.0f) ? 0.0f : (rc > 1.0f) ? 1.0f : rc;
        s_hr_conf   = (hc < 0.0f) ? 0.0f : (hc > 1.0f) ? 1.0f : hc;
    }

    /* --- Step 8: Motion energy (variance of recent phases) ---
     * A moving person perturbs the multipath channel, so the primary
     * subcarrier's phase jitters; its variance over the last <=20 samples
     * (~1 s) is the board's motion metric. */
    if (s_history_len >= 10) {
        float sum = 0.0f, sum2 = 0.0f;
        uint16_t window = (s_history_len < 20) ? s_history_len : 20;
        for (uint16_t i = 0; i < window; i++) {
            uint16_t ri = (s_history_idx + EDGE_PHASE_HISTORY_LEN
                           - window + i) % EDGE_PHASE_HISTORY_LEN;
            float v = s_phase_history[ri];
            sum += v;
            sum2 += v * v;
        }
        float mean = sum / (float)window;
        s_motion_energy = (sum2 / (float)window) - (mean * mean);
        if (s_motion_energy < 0.0f) s_motion_energy = 0.0f;
    }

    /* --- Step 9: Presence detection (sovereign is_human verdict) ---
     * s_presence_score/s_motion_energy stay pure METRICS (motion energy
     * above a threshold that is either configured (presence_thresh), learned
     * from the empty room (mean + k*sigma via calibration_update), or a 0.05
     * default until calibration finishes) — they no longer alone decide the
     * verdict.
     *
     * PS-AUDIT-002 (F1 firewall): motion alone is NOT sufficient to declare
     * a human present — a fan, curtain, or other non-human mover can raise
     * motion energy without producing genuine 0.1-0.5 Hz respiratory
     * periodicity. s_presence_detected now requires motion AND confident,
     * in-band respiratory periodicity (edge_evaluate_human_presence).
     * Cardiac-band data is intentionally never passed to that gate — see
     * edge_dsp_pure.h for why that must stay a compile-time guarantee. */
    s_presence_score = s_motion_energy;

    /* Adaptive calibration: learn ambient noise level from first N frames. */
    if (!s_calibrated && s_cfg.presence_thresh == 0.0f) {
        calibration_update(s_motion_energy);
    }

    float threshold = s_cfg.presence_thresh;
    if (threshold == 0.0f && s_calibrated) {
        threshold = s_adaptive_threshold;
    } else if (threshold == 0.0f) {
        threshold = 0.05f;  /* Default until calibrated. */
    }
    s_presence_threshold_active = threshold;

    bool motion_present = (s_presence_score > threshold);
    bool breathing_data_ready = (s_history_len >= 64);  /* mirrors Step 7's gate */
    s_presence_detected = edge_evaluate_human_presence(
        motion_present, breathing_data_ready, s_breathing_bpm, s_resp_conf);

    /* --- Step 10: Fall detection (phase acceleration) --- */
    if (s_history_len >= 3) {
        uint16_t i0 = (s_history_idx + EDGE_PHASE_HISTORY_LEN - 1) % EDGE_PHASE_HISTORY_LEN;
        uint16_t i1 = (s_history_idx + EDGE_PHASE_HISTORY_LEN - 2) % EDGE_PHASE_HISTORY_LEN;
        float velocity = s_phase_history[i0] - s_phase_history[i1];
        float accel = fabsf(velocity - s_prev_phase_velocity);
        s_prev_phase_velocity = velocity;

        s_fall_detected = (accel > s_cfg.fall_thresh);
        if (s_fall_detected && ((s_frame_count % 100) == 0)) {
            ESP_LOGW(TAG, "Fall detected! accel=%.4f > thresh=%.4f",
                     accel, s_cfg.fall_thresh);
        }
    }

    /* --- Step 11: Multi-person vitals --- */
    update_multi_person_vitals(slot->iq_data, n_subcarriers, sample_rate);

    /* --- Step 12: Delta compression --- */
    if (s_cfg.tier >= 2) {
        send_compressed_frame(slot->iq_data, slot->iq_len, slot->channel);
    }

    /* --- Step 13: Refresh vitals snapshot + send feature-state packet --- */
    int64_t now_us = esp_timer_get_time();
    int64_t interval_us = (int64_t)s_cfg.vital_interval_ms * 1000;
    if ((now_us - s_last_vitals_send_us) >= interval_us) {
        update_vitals_state();
        send_feature_state_packet();
        s_last_vitals_send_us = now_us;

        if ((s_frame_count % 200) == 0) {
            ESP_LOGI(TAG, "Vitals: br=%.1f hr=%.1f motion=%.4f pres=%s "
                     "fall=%s persons=%u frames=%lu",
                     s_breathing_bpm, s_heartrate_bpm, s_motion_energy,
                     s_presence_detected ? "YES" : "no",
                     s_fall_detected ? "YES" : "no",
                     (unsigned)s_latest_pkt.n_persons,
                     (unsigned long)s_frame_count);
        }
    }

    /* --- Step 14 (ADR-040): Dispatch to WASM modules --- */
    if (s_cfg.tier >= 2 && s_pkt_valid) {
        /* Extract amplitudes from I/Q for WASM host API. */
        float amplitudes[EDGE_MAX_SUBCARRIERS];
        for (uint16_t sc = 0; sc < n_subcarriers; sc++) {
            int8_t i_val = (int8_t)slot->iq_data[sc * 2];
            int8_t q_val = (int8_t)slot->iq_data[sc * 2 + 1];
            amplitudes[sc] = sqrtf((float)(i_val * i_val + q_val * q_val));
        }

        /* Build variance array from Welford state. */
        float variances[EDGE_MAX_SUBCARRIERS];
        for (uint16_t sc = 0; sc < n_subcarriers; sc++) {
            variances[sc] = (float)welford_variance(&s_subcarrier_var[sc]);
        }

        wasm_runtime_on_frame(phases, amplitudes, variances,
                              n_subcarriers,
                              (const edge_vitals_pkt_t *)&s_latest_pkt);
    }
}

/* ======================================================================
 * Edge Processing Task (pinned to Core 1)
 * ====================================================================== */

static void edge_task(void *arg)
{
    (void)arg;
    ESP_LOGI(TAG, "Edge DSP task started on core %d (tier=%u)",
             xPortGetCoreID(), s_cfg.tier);

    edge_ring_slot_t slot;
    uint8_t frames_since_yield = 0;

    while (1) {
        if (ring_pop(&slot)) {
            process_frame(&slot);
            frames_since_yield++;
            if (frames_since_yield >= 4) {
                frames_since_yield = 0;
                vTaskDelay(pdMS_TO_TICKS(1));
            }
        } else {
            /* No frames available — yield briefly. */
            frames_since_yield = 0;
            vTaskDelay(pdMS_TO_TICKS(1));
        }
    }
}

/* ======================================================================
 * Public API
 * ====================================================================== */

bool edge_enqueue_csi(const uint8_t *iq_data, uint16_t iq_len,
                      int8_t rssi, uint8_t channel)
{
    return ring_push(iq_data, iq_len, rssi, channel);
}

bool edge_get_vitals(edge_vitals_pkt_t *pkt)
{
    if (!s_pkt_valid || pkt == NULL) return false;
    memcpy(pkt, (const void *)&s_latest_pkt, sizeof(edge_vitals_pkt_t));
    return true;
}

void edge_get_multi_person(edge_person_vitals_t *persons, uint8_t *n_active)
{
    uint8_t active = 0;
    for (uint8_t p = 0; p < EDGE_MAX_PERSONS; p++) {
        if (persons) persons[p] = s_persons[p];
        if (s_persons[p].active) active++;
    }
    if (n_active) *n_active = active;
}

void edge_get_phase_history(const float **out_buf, uint16_t *out_len,
                            uint16_t *out_idx)
{
    if (out_buf) *out_buf = s_phase_history;
    if (out_len) *out_len = s_history_len;
    if (out_idx) *out_idx = s_history_idx;
}

void edge_get_variances(float *out_variances, uint16_t n_subcarriers)
{
    if (out_variances == NULL) return;
    uint16_t n = (n_subcarriers > EDGE_MAX_SUBCARRIERS) ? EDGE_MAX_SUBCARRIERS : n_subcarriers;
    for (uint16_t i = 0; i < n; i++) {
        out_variances[i] = (float)welford_variance(&s_subcarrier_var[i]);
    }
}

void edge_get_stats(edge_runtime_stats_t *out_stats)
{
    if (out_stats == NULL) return;
    *out_stats = s_runtime_stats;
}

esp_err_t edge_processing_init(const edge_config_t *cfg)
{
    if (cfg == NULL) {
        ESP_LOGE(TAG, "edge_processing_init: cfg is NULL");
        return ESP_ERR_INVALID_ARG;
    }

    /* Store config. */
    s_cfg = *cfg;

    ESP_LOGI(TAG, "Initializing edge processing (tier=%u, top_k=%u, "
             "vital_interval=%ums, presence_thresh=%.3f)",
             s_cfg.tier, s_cfg.top_k_count,
             s_cfg.vital_interval_ms, s_cfg.presence_thresh);

    /* Reset all state. */
    memset(&s_ring, 0, sizeof(s_ring));
    memset(s_subcarrier_var, 0, sizeof(s_subcarrier_var));
    memset(s_prev_phase, 0, sizeof(s_prev_phase));
    s_phase_initialized = false;
    s_top_k_count = 0;
    s_history_len = 0;
    s_history_idx = 0;
    s_breathing_bpm = 0.0f;
    s_heartrate_bpm = 0.0f;
    s_motion_energy = 0.0f;
    s_presence_score = 0.0f;
    s_presence_detected = false;
    s_fall_detected = false;
    s_latest_rssi = 0;
    s_frame_count = 0;
    s_prev_phase_velocity = 0.0f;
    s_last_vitals_send_us = 0;
    s_has_prev_iq = false;
    s_prev_iq_len = 0;
    s_pkt_valid = false;
    memset(&s_runtime_stats, 0, sizeof(s_runtime_stats));

    /* Reset vitals confidence / feature-state / HR smoother state. */
    s_resp_conf = 0.0f;
    s_hr_conf = 0.0f;
    s_presence_threshold_active = 0.05f;
    s_feature_state_seq = 0;
    s_hr_ring_n = 0;
    s_hr_ring_idx = 0;

    /* Reset measured sample-rate state (init estimate 15 Hz; biquads are
     * designed at 20 Hz below and re-tune once the measured rate drifts
     * >15% from that design fs). */
    s_sample_rate_hz = 15.0f;
    s_filter_design_fs = 20.0f;
    s_last_frame_ts_us = 0;

    /* Reset calibration state. */
    s_calibrated = false;
    s_calib_sum = 0.0f;
    s_calib_sum_sq = 0.0f;
    s_calib_count = 0;
    s_adaptive_threshold = 0.05f;

    /* Reset multi-person state. */
    memset(s_persons, 0, sizeof(s_persons));
    for (uint8_t p = 0; p < EDGE_MAX_PERSONS; p++) {
        s_persons[p].active = false;
    }

    /* Design biquad bandpass filters at the initial 20 Hz assumption; they
     * are re-designed in process_frame once the measured rate drifts >15%. */
    const float fs = 20.0f;
    biquad_bandpass_design(&s_bq_breathing, fs, 0.1f, 0.5f);
    biquad_bandpass_design(&s_bq_heartrate, fs, 0.8f, 2.0f);

    /* Design per-person filters. */
    for (uint8_t p = 0; p < EDGE_MAX_PERSONS; p++) {
        biquad_bandpass_design(&s_person_bq_br[p], fs, 0.1f, 0.5f);
        biquad_bandpass_design(&s_person_bq_hr[p], fs, 0.8f, 2.0f);
    }

    if (s_cfg.tier == 0) {
        ESP_LOGI(TAG, "Edge tier 0: raw passthrough (no DSP task)");
        return ESP_OK;
    }

    /* Start DSP task on Core 1. */
    BaseType_t ret = xTaskCreatePinnedToCore(
        edge_task,
        "edge_dsp",
        8192,       /* 8 KB stack — sufficient for DSP pipeline. */
        NULL,
        5,          /* Priority 5 — above idle, below WiFi. */
        NULL,
        1           /* Pin to Core 1. */
    );

    if (ret != pdPASS) {
        ESP_LOGE(TAG, "Failed to create edge DSP task");
        return ESP_ERR_NO_MEM;
    }

    ESP_LOGI(TAG, "Edge DSP task created on Core 1 (stack=8192, priority=5)");
    return ESP_OK;
}
