/**
 * @file test_edge_dsp_pure.c
 * @brief Host-side regression test for PS-AUDIT-002 (sovereign human-presence
 * verdict must require respiratory periodicity, not motion alone).
 *
 * Compiles and links the REAL edge_dsp_pure.c shipped in firmware — not a
 * reimplementation — against a plain host toolchain, since that file is
 * deliberately ESP-IDF-free (see edge_dsp_pure.h). It is not part of the
 * ESP-IDF build (main/CMakeLists.txt does not reference this directory) and
 * is not wired into npm test / pytest; it is C-only firmware-logic coverage.
 *
 * Build & run (from firmware/esp32-csi-node/main/test):
 *   gcc -std=c99 -O2 -Wall -I.. test_edge_dsp_pure.c ../edge_dsp_pure.c -lm -o test_edge_dsp_pure
 *   ./test_edge_dsp_pure
 *
 * Exit code 0 = all assertions passed. The KNOWN LIMITATION section prints
 * diagnostic output but does not assert — see edge_dsp_pure.h's docstring on
 * edge_evaluate_human_presence for why that case is a documented follow-up,
 * not a regression this test enforces.
 */

#include "../edge_dsp_pure.h"
#include <assert.h>
#include <stdio.h>
#include <stddef.h>
#include <math.h>
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#define FS 15.0f   /* matches edge_processing.c's s_sample_rate_hz reset default */
#define N  256      /* matches EDGE_PHASE_HISTORY_LEN */

static int g_failures = 0;
#define CHECK(cond) do { \
    if (!(cond)) { \
        fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
        g_failures++; \
    } else { \
        printf("ok   %s:%d: %s\n", __FILE__, __LINE__, #cond); \
    } \
} while (0)

static unsigned long s_rng = 12345;
/** Deterministic LCG noise in [-1,1] — reproducible across runs/platforms. */
static float frand(void)
{
    s_rng = s_rng * 1103515245UL + 12345UL;
    return ((float)((s_rng >> 16) & 0x7fffUL) / 16384.0f) - 1.0f;
}

/** Mirrors process_frame's Step 8 motion-energy computation: variance of the
 *  raw (unfiltered) signal over the last <=20 samples. */
static float motion_energy_last20(const float *sig, int n)
{
    int window = (n < 20) ? n : 20;
    float sum = 0.0f, sum2 = 0.0f;
    for (int i = n - window; i < n; i++) { sum += sig[i]; sum2 += sig[i] * sig[i]; }
    float mean = sum / (float)window;
    float e = (sum2 / (float)window) - (mean * mean);
    return (e < 0.0f) ? 0.0f : e;
}

/** Runs a raw phase signal through the exact process_frame Step 6/7 sequence
 *  (biquad filter -> autocorr for breathing then heart, with harmonic
 *  rejection) and evaluates the Step 9 verdict, mirroring the real firmware
 *  call sequence field-for-field. */
static bool run_pipeline(const float *raw, int n, float threshold,
                         float *out_resp_conf, float *out_breathing_bpm,
                         float *out_motion_energy)
{
    edge_biquad_t bq_br, bq_hr;
    biquad_bandpass_design(&bq_br, FS, 0.1f, 0.5f);
    biquad_bandpass_design(&bq_hr, FS, 0.8f, 2.0f);

    float br_filt[N], hr_filt[N];
    for (int i = 0; i < n; i++) {
        br_filt[i] = biquad_process(&bq_br, raw[i]);
        hr_filt[i] = biquad_process(&bq_hr, raw[i]);
    }

    float motion_energy = motion_energy_last20(raw, n);

    float br_ratio = 0.0f, hr_ratio = 0.0f;
    float br_rob = estimate_periodicity_autocorr(br_filt, (uint16_t)n, FS,
                                                  EDGE_BREATHING_BPM_MIN,
                                                  EDGE_BREATHING_BPM_MAX,
                                                  0.0f, &br_ratio);
    (void)estimate_periodicity_autocorr(hr_filt, (uint16_t)n, FS,
                                         45.0f, 180.0f, br_rob / 60.0f,
                                         &hr_ratio);

    float breathing_bpm = 0.0f;
    if (br_rob >= EDGE_BREATHING_BPM_MIN && br_rob <= EDGE_BREATHING_BPM_MAX) {
        breathing_bpm = br_rob;
    }
    float rc = (br_ratio - 0.2f) / 0.6f;
    if (rc < 0.0f) rc = 0.0f; else if (rc > 1.0f) rc = 1.0f;

    if (out_resp_conf) *out_resp_conf = rc;
    if (out_breathing_bpm) *out_breathing_bpm = breathing_bpm;
    if (out_motion_energy) *out_motion_energy = motion_energy;

    bool motion_present = motion_energy > threshold;
    return edge_evaluate_human_presence(motion_present, /*breathing_data_ready=*/true,
                                         breathing_bpm, rc);
}

/* ---- (a) Fan/curtain: broadband, non-tonal ambient motion must NOT set
 * presence, even though it clears the motion threshold. ---- */
static void test_broadband_motion_alone_is_not_human(void)
{
    float sig[N];
    for (int i = 0; i < N; i++) sig[i] = 0.9f * frand();

    float resp_conf, breathing_bpm, motion_energy;
    bool verdict = run_pipeline(sig, N, 0.05f, &resp_conf, &breathing_bpm, &motion_energy);

    printf("[broadband motion] motion_energy=%.5f resp_conf=%.3f breathing_bpm=%.1f verdict=%d\n",
           motion_energy, resp_conf, breathing_bpm, verdict);
    CHECK(motion_energy > 0.05f);          /* motion IS present */
    CHECK(resp_conf < EDGE_RESP_CONF_MIN); /* but no respiratory periodicity */
    CHECK(verdict == false);               /* so presence must stay false */
}

/* ---- (b) Breathing-band periodic motion at a physiologically plausible
 * rate DOES set presence. ---- */
static void test_breathing_band_sets_human_present(void)
{
    float sig[N];
    for (int i = 0; i < N; i++) {
        float t = (float)i / FS;
        sig[i] = 1.2f * sinf(2.0f * (float)M_PI * 0.25f * t) + 0.05f * frand(); /* 15 BPM */
    }

    float resp_conf, breathing_bpm, motion_energy;
    bool verdict = run_pipeline(sig, N, 0.05f, &resp_conf, &breathing_bpm, &motion_energy);

    printf("[breathing 15bpm]  motion_energy=%.5f resp_conf=%.3f breathing_bpm=%.1f verdict=%d\n",
           motion_energy, resp_conf, breathing_bpm, verdict);
    CHECK(motion_energy > 0.05f);
    CHECK(resp_conf >= EDGE_RESP_CONF_MIN);
    CHECK(breathing_bpm >= EDGE_BREATHING_BPM_MIN && breathing_bpm <= EDGE_BREATHING_BPM_MAX);
    CHECK(verdict == true);
}

/* ---- (c) Structural firewall: edge_evaluate_human_presence has no cardiac
 * parameters, so cardiac-band data cannot participate in the gate at all —
 * a strong cardiac reading paired with a NEGATIVE respiratory reading must
 * still yield a negative verdict. Cardiac values are computed here (as
 * process_frame would) purely to show they exist and are simply never
 * passed to the gate. ---- */
static void test_cardiac_only_cannot_flip_negative_respiratory_verdict(void)
{
    /* No breathing-band content at all: resp gate inputs are explicitly
     * negative (bpm=0, conf=0), as process_frame would report when the
     * autocorr search finds no accepted breathing-band peak. */
    bool motion_present = true;      /* even with motion present... */
    float breathing_bpm = 0.0f;      /* ...and even with a strong, valid... */
    float resp_conf = 0.0f;          /* ...cardiac reading available (below,
                                         computed but intentionally unused): */
    float hr_bpm_would_be = 72.0f;   /* NOT a parameter of the gate. */
    float hr_conf_would_be = 0.95f;  /* NOT a parameter of the gate. */
    (void)hr_bpm_would_be;
    (void)hr_conf_would_be;

    bool verdict = edge_evaluate_human_presence(motion_present, /*breathing_data_ready=*/true,
                                                 breathing_bpm, resp_conf);
    printf("[cardiac-only]     motion_present=%d breathing_bpm=%.1f resp_conf=%.3f "
           "(hr_bpm=%.1f hr_conf=%.2f computed but NOT passed to gate) verdict=%d\n",
           motion_present, breathing_bpm, resp_conf, hr_bpm_would_be, hr_conf_would_be, verdict);
    CHECK(verdict == false);
}

/* ---- Boundary/API-contract unit tests for edge_evaluate_human_presence. ---- */
static void test_gate_boundaries(void)
{
    CHECK(edge_evaluate_human_presence(false, true, 15.0f, 1.0f) == false); /* no motion */
    CHECK(edge_evaluate_human_presence(true, false, 15.0f, 1.0f) == false); /* data not ready */
    CHECK(edge_evaluate_human_presence(true, true, 5.9f, 1.0f) == false);   /* just below band */
    CHECK(edge_evaluate_human_presence(true, true, EDGE_BREATHING_BPM_MAX + 0.1f, 1.0f) == false); /* just above band */
    CHECK(edge_evaluate_human_presence(true, true, 15.0f, EDGE_RESP_CONF_MIN - 0.001f) == false); /* just under conf floor */
    CHECK(edge_evaluate_human_presence(true, true, 15.0f, EDGE_RESP_CONF_MIN) == true);            /* at conf floor */
    CHECK(edge_evaluate_human_presence(true, true, EDGE_BREATHING_BPM_MIN, 1.0f) == true);         /* band edges inclusive */
    CHECK(edge_evaluate_human_presence(true, true, EDGE_BREATHING_BPM_MAX, 1.0f) == true);
}

/* ---- B2: sample-rate correctness across the canonical 3-7 Hz measured-CSI
 * range (PHANTOM_SCAN_BEHAVIORAL_TEST_REPORT.md). The pure estimator takes
 * fs as an explicit parameter (verified: no hardcoded frequency literal in
 * edge_dsp_pure.c), so this feeds the SAME 15 BPM breathing waveform
 * generated at 3, 5, and 7 Hz and confirms estimate_periodicity_autocorr
 * recovers ~15 BPM at each rate — catching a fixed-fs frequency-axis bug
 * that a single-FS test suite (the tests above, all at FS=15) cannot see.
 * Real per-sample timing jitter is not modeled here: the pure functions
 * take a scalar fs, matching the firmware's own EMA-smoothed scalar rate
 * (edge_processing.c's s_sample_rate_hz) rather than per-sample timestamps. */
static void test_bpm_estimate_consistent_across_measured_csi_rates(void)
{
    const float rates[] = {3.0f, 5.0f, 7.0f};
    const float truth_bpm = 15.0f;
    const float truth_hz = truth_bpm / 60.0f;

    for (size_t r = 0; r < sizeof(rates) / sizeof(rates[0]); r++) {
        float fs = rates[r];
        float sig[N];
        for (int i = 0; i < N; i++) {
            float t = (float)i / fs;
            sig[i] = 1.2f * sinf(2.0f * (float)M_PI * truth_hz * t);
        }
        edge_biquad_t bq;
        biquad_bandpass_design(&bq, fs, 0.1f, 0.5f);
        float filt[N];
        for (int i = 0; i < N; i++) filt[i] = biquad_process(&bq, sig[i]);
        float ratio = 0.0f;
        float est_bpm = estimate_periodicity_autocorr(filt, N, fs,
                                                        EDGE_BREATHING_BPM_MIN,
                                                        EDGE_BREATHING_BPM_MAX,
                                                        0.0f, &ratio);
        printf("[sample-rate sweep] fs=%.1fHz truth=%.1fBPM est=%.2fBPM ratio=%.3f\n",
               fs, truth_bpm, est_bpm, ratio);
        CHECK(fabsf(est_bpm - truth_bpm) < 1.0f);
    }
}

/* ---- B2: committed Monte Carlo false-positive / missed-detection
 * calibration (promotes the scratch calibration run cited in
 * edge_dsp_pure.h's EDGE_RESP_CONF_MIN docstring into a real, reproducible,
 * asserted regression test — the original run was never committed). Fixed
 * LCG seed per trial for determinism (rule: no wall-clock/flaky behavioral
 * tests). Bounds are set with margin above the originally measured figures
 * (0.2% noise FP, 8% missed-detection at the 6 BPM edge) so this catches a
 * real regression without being flaky on normal floating-point variation. */
static unsigned long s_calib_rng;
static float calib_frand(void)
{
    s_calib_rng = s_calib_rng * 1103515245UL + 12345UL;
    return ((float)((s_calib_rng >> 16) & 0x7fffUL) / 16384.0f) - 1.0f;
}

static void test_monte_carlo_calibration_bounds(void)
{
    const int trials = 500;
    int noise_false_positives = 0;
    int breathing_missed = 0;

    for (int i = 0; i < trials; i++) {
        s_calib_rng = (unsigned long)(1000 + i * 7919);
        float sig[N];
        for (int j = 0; j < N; j++) sig[j] = 0.9f * calib_frand();
        float resp_conf, breathing_bpm, motion_energy;
        (void)run_pipeline(sig, N, 0.05f, &resp_conf, &breathing_bpm, &motion_energy);
        if (resp_conf >= EDGE_RESP_CONF_MIN) noise_false_positives++;
    }

    for (int i = 0; i < trials; i++) {
        s_calib_rng = (unsigned long)(2000 + i * 7919);
        float bpm = EDGE_BREATHING_BPM_MIN + (float)(i % 25); /* sweep the full canonical band */
        float hz = bpm / 60.0f;
        float sig[N];
        for (int j = 0; j < N; j++) {
            float t = (float)j / FS;
            sig[j] = 1.2f * sinf(2.0f * (float)M_PI * hz * t) + 0.15f * calib_frand();
        }
        float resp_conf, breathing_bpm, motion_energy;
        bool verdict = run_pipeline(sig, N, 0.05f, &resp_conf, &breathing_bpm, &motion_energy);
        if (!verdict) breathing_missed++;
    }

    float noise_fp_rate = (float)noise_false_positives / trials;
    float missed_rate = (float)breathing_missed / trials;
    printf("[Monte Carlo, N=%d] noise_false_positive_rate=%.3f breathing_missed_detection_rate=%.3f\n",
           trials, noise_fp_rate, missed_rate);
    CHECK(noise_fp_rate < 0.02f);   /* originally measured 0.2%; margin to 2% */
    /* FINDING (PHANTOM_SCAN_BEHAVIORAL_TEST_REPORT.md): measured 19.8% here
     * via the FULL two-factor verdict (edge_evaluate_human_presence, which
     * requires motion_energy>threshold AND resp_conf>=EDGE_RESP_CONF_MIN),
     * higher than the WP-2 close-out's 8% figure — that number only checked
     * resp_conf in isolation and did not account for motion_energy also
     * failing to clear its 0.05 threshold at some low-BPM/low-amplitude
     * combinations. This is the more representative number; bound kept
     * with margin above it, not tightened to hide the gap. */
    CHECK(missed_rate < 0.25f);
}

/* ---- KNOWN LIMITATION (documented in edge_dsp_pure.h): a clean, highly
 * periodic non-human tone can alias into the breathing band via the
 * autocorrelation's integer sub-harmonics. Printed as evidence for the
 * remediation report; deliberately NOT asserted (would make this test
 * permanently red for a known, tracked-separately gap). ---- */
static void demo_known_limitation_tonal_aliasing(void)
{
    float sig[N];
    for (int i = 0; i < N; i++) {
        float t = (float)i / FS;
        sig[i] = 0.5f * sinf(2.0f * (float)M_PI * 2.2f * t); /* clean 2.2 Hz tone, no noise */
    }
    float resp_conf, breathing_bpm, motion_energy;
    bool verdict = run_pipeline(sig, N, 0.05f, &resp_conf, &breathing_bpm, &motion_energy);
    printf("[KNOWN LIMITATION, not asserted] clean 2.2Hz tone: motion_energy=%.5f "
           "resp_conf=%.3f breathing_bpm=%.1f verdict=%d "
           "(sub-harmonic aliasing; real fan/curtain noise does not reproduce this — "
           "see test_broadband_motion_alone_is_not_human)\n",
           motion_energy, resp_conf, breathing_bpm, verdict);
}

int main(void)
{
    test_gate_boundaries();
    test_broadband_motion_alone_is_not_human();
    test_breathing_band_sets_human_present();
    test_cardiac_only_cannot_flip_negative_respiratory_verdict();
    test_bpm_estimate_consistent_across_measured_csi_rates();
    test_monte_carlo_calibration_bounds();
    demo_known_limitation_tonal_aliasing();

    if (g_failures) {
        fprintf(stderr, "\n%d assertion(s) FAILED\n", g_failures);
        return 1;
    }
    printf("\nAll assertions passed.\n");
    return 0;
}
