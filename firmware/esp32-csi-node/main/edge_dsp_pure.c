/**
 * @file edge_dsp_pure.c
 * @brief Bodies for edge_dsp_pure.h — see that header for contracts.
 */

#include "edge_dsp_pure.h"
#include <math.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

void biquad_bandpass_design(edge_biquad_t *bq, float fs,
                            float f_lo, float f_hi)
{
    float w0 = 2.0f * M_PI * (f_lo + f_hi) / 2.0f / fs;
    float bw = 2.0f * M_PI * (f_hi - f_lo) / fs;
    float alpha = sinf(w0) * sinhf(logf(2.0f) / 2.0f * bw / sinf(w0));

    float a0_inv = 1.0f / (1.0f + alpha);
    bq->b0 =  alpha * a0_inv;
    bq->b1 =  0.0f;
    bq->b2 = -alpha * a0_inv;
    bq->a1 = -2.0f * cosf(w0) * a0_inv;
    bq->a2 =  (1.0f - alpha) * a0_inv;

    bq->x1 = bq->x2 = 0.0f;
    bq->y1 = bq->y2 = 0.0f;
}

float biquad_process(edge_biquad_t *bq, float x)
{
    float y = bq->b0 * x + bq->b1 * bq->x1 + bq->b2 * bq->x2
            - bq->a1 * bq->y1 - bq->a2 * bq->y2;
    bq->x2 = bq->x1;
    bq->x1 = x;
    bq->y2 = bq->y1;
    bq->y1 = y;
    return y;
}

float unwrap_phase(float prev, float curr)
{
    float diff = curr - prev;
    if (diff > M_PI)       diff -= 2.0f * M_PI;
    else if (diff < -M_PI) diff += 2.0f * M_PI;
    return prev + diff;
}

float extract_phase(const uint8_t *iq, uint16_t idx)
{
    int8_t i_val = (int8_t)iq[idx * 2];
    int8_t q_val = (int8_t)iq[idx * 2 + 1];
    return atan2f((float)q_val, (float)i_val);
}

float estimate_bpm_zero_crossing(const float *history, uint16_t len,
                                 float sample_rate)
{
    if (len < 4) return 0.0f;

    uint16_t crossings[128];
    uint16_t n_cross = 0;

    for (uint16_t i = 1; i < len && n_cross < 128; i++) {
        if (history[i - 1] <= 0.0f && history[i] > 0.0f) {
            crossings[n_cross++] = i;
        }
    }

    if (n_cross < 2) return 0.0f;

    float total_period = 0.0f;
    for (uint16_t i = 1; i < n_cross; i++) {
        total_period += (float)(crossings[i] - crossings[i - 1]);
    }
    float avg_period_samples = total_period / (float)(n_cross - 1);

    if (avg_period_samples < 1.0f) return 0.0f;

    float freq_hz = sample_rate / avg_period_samples;
    return freq_hz * 60.0f;
}

float estimate_period_regularity_cv(const float *sig, uint16_t len, float fs,
                                     float claimed_bpm)
{
    if (len < 4) return -1.0f;

    /* Sub-sample (linearly interpolated) crossing TIMES, not raw sample
     * indices: an integer-only crossing index quantizes to +/-0.5 samples,
     * which dominates the statistic for short-period signals (few
     * samples/cycle) regardless of how truly regular the source is.
     * Interpolating the crossing time removes that artifact so the CV
     * reflects real period jitter, not sampling-grid noise. */
    float crossings[128];
    uint16_t n_cross = 0;

    for (uint16_t i = 1; i < len && n_cross < 128; i++) {
        if (sig[i - 1] <= 0.0f && sig[i] > 0.0f) {
            float denom = sig[i] - sig[i - 1];
            float frac = (denom > 1e-9f) ? (-sig[i - 1] / denom) : 0.0f;
            crossings[n_cross++] = (float)(i - 1) + frac;
        }
    }

    if (n_cross < 3) return -1.0f; /* too few cycles to judge jitter */

    uint16_t n_intervals = n_cross - 1;

    /* Sub-harmonic-aliasing multiplicity check: if the raw signal oscillates
     * far more often than the claimed (accepted) BPM implies, the accepted
     * periodicity is a sub-harmonic of a much faster, non-biological source
     * — decisive on its own, and not reliably caught by the CV below when
     * the raw period is short (few samples/cycle). */
    if (claimed_bpm > 0.0f && fs > 0.0f) {
        float window_s = (float)len / fs;
        float expected_cycles = window_s * (claimed_bpm / 60.0f);
        if (expected_cycles > 0.5f) {
            float multiplicity = (float)n_intervals / expected_cycles;
            if (multiplicity > 1.6f) return 0.0f; /* force rejection */
        }
    }
    float intervals[127];
    float sum = 0.0f;
    for (uint16_t i = 0; i < n_intervals; i++) {
        intervals[i] = crossings[i + 1] - crossings[i];
        sum += intervals[i];
    }
    float mean = sum / (float)n_intervals;
    if (mean <= 1e-6f) return -1.0f;

    float var_acc = 0.0f;
    for (uint16_t i = 0; i < n_intervals; i++) {
        float d = intervals[i] - mean;
        var_acc += d * d;
    }
    float variance = var_acc / (float)n_intervals;
    return sqrtf(variance) / mean;
}

float estimate_periodicity_autocorr(const float *sig, uint16_t len, float fs,
                                    float bpm_lo, float bpm_hi,
                                    float reject_br_hz,
                                    float *out_peak_ratio)
{
    if (out_peak_ratio) *out_peak_ratio = 0.0f;
    if (len < 32 || fs <= 0.0f || bpm_hi <= bpm_lo) return 0.0f;

    int lag_min = (int)(fs * 60.0f / bpm_hi);
    int lag_max = (int)(fs * 60.0f / bpm_lo);
    if (lag_min < 2) lag_min = 2;
    if (lag_max >= (int)len) lag_max = (int)len - 1;
    if (lag_max <= lag_min + 1) return 0.0f;

    const float br_hz = reject_br_hz;

    float r0 = 0.0f;
    for (uint16_t i = 0; i < len; i++) r0 += sig[i] * sig[i];
    if (r0 <= 1e-6f) return 0.0f;

    float best = -1.0f;
    int   best_lag = 0;

    for (int lag = lag_min; lag <= lag_max; lag++) {
        float f = fs / (float)lag;

        if (br_hz > 0.0f) {
            bool harmonic = false;
            for (int k = 1; k <= 6; k++) {
                float h = (float)k * br_hz;
                if (fabsf(f - h) < 0.08f * h) { harmonic = true; break; }
            }
            if (harmonic) continue;
        }

        float acc = 0.0f;
        for (int i = 0; i + lag < (int)len; i++) acc += sig[i] * sig[i + lag];
        if (acc > best) { best = acc; best_lag = lag; }
    }

    if (best_lag == 0) return 0.0f;
    if (best / r0 < 0.2f) return 0.0f;

    float lag_ref = (float)best_lag;
    {
        float a = 0.0f, c = 0.0f;
        for (int i = 0; i + (best_lag - 1) < (int)len; i++) a += sig[i] * sig[i + best_lag - 1];
        for (int i = 0; i + (best_lag + 1) < (int)len; i++) c += sig[i] * sig[i + best_lag + 1];
        float denom = a - 2.0f * best + c;
        if (fabsf(denom) > 1e-6f) {
            float delta = 0.5f * (a - c) / denom;
            if (delta > -1.0f && delta < 1.0f) lag_ref += delta;
        }
    }

    if (out_peak_ratio) *out_peak_ratio = best / r0;
    return fs / lag_ref * 60.0f;
}

bool edge_evaluate_human_presence(bool motion_present,
                                   bool breathing_data_ready,
                                   float breathing_bpm,
                                   float resp_conf,
                                   float period_cv)
{
    if (!motion_present || !breathing_data_ready) return false;

    bool in_band = (breathing_bpm >= EDGE_BREATHING_BPM_MIN) &&
                   (breathing_bpm <= EDGE_BREATHING_BPM_MAX);
    bool confident = (resp_conf >= EDGE_RESP_CONF_MIN);
    /* Indeterminate (-1.0f, too few cycles to judge) passes through rather
     * than rejecting, to avoid worsening the already-documented missed-
     * detection rate at the low-BPM edge (see EDGE_RESP_CONF_MIN). */
    bool natural_jitter = (period_cv < 0.0f) || (period_cv >= EDGE_RESP_PERIOD_CV_MIN);

    return in_band && confident && natural_jitter;
}

bool edge_evaluate_calibration_window(float mean, float sigma, float max_sample)
{
    float deviation = max_sample - mean;
    if (deviation <= 0.0f) return true; /* max never below mean; degenerate guard */
    return deviation <= EDGE_CALIB_REJECT_SIGMA_MULT * sigma;
}
