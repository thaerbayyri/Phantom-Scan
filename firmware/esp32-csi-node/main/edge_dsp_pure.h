/**
 * @file edge_dsp_pure.h
 * @brief Pure (ESP-IDF-free) DSP math for edge_processing.c's respiratory/
 * cardiac pipeline, plus the sovereign human-presence verdict (PS-AUDIT-002).
 *
 * Kept dependency-free (stdint/stdbool/math only, no FreeRTOS/esp_* headers)
 * so the exact code compiled into firmware can also be compiled and
 * unit-tested on a host toolchain — see main/test/test_edge_dsp_pure.c.
 */

#ifndef EDGE_DSP_PURE_H
#define EDGE_DSP_PURE_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ---- Biquad IIR filter state ---- */
typedef struct {
    float b0, b1, b2;  /**< Numerator coefficients. */
    float a1, a2;       /**< Denominator coefficients (a0 = 1). */
    float x1, x2;       /**< Input delay line. */
    float y1, y2;       /**< Output delay line. */
} edge_biquad_t;

/**
 * Design a 2nd-order Butterworth bandpass biquad.
 * @param bq   Output biquad state.
 * @param fs   Sampling frequency (Hz).
 * @param f_lo Low cutoff frequency (Hz).
 * @param f_hi High cutoff frequency (Hz).
 */
void biquad_bandpass_design(edge_biquad_t *bq, float fs, float f_lo, float f_hi);

float biquad_process(edge_biquad_t *bq, float x);

/** Unwrap phase to maintain continuity (avoid 2*pi jumps). */
float unwrap_phase(float prev, float curr);

/** Extract phase (radians) from an I/Q pair at byte offset. */
float extract_phase(const uint8_t *iq, uint16_t idx);

/**
 * Estimate BPM from a filtered signal using positive zero-crossings.
 * @return Estimated BPM, or 0 if insufficient crossings.
 */
float estimate_bpm_zero_crossing(const float *history, uint16_t len, float sample_rate);

/**
 * Dominant periodicity in a band via autocorrelation.
 * @param out_peak_ratio Optional: receives best/r0 (autocorr peak ratio,
 *                       the confidence basis) when a peak is accepted,
 *                       0 otherwise. May be NULL.
 * @return Dominant rate in BPM within the band, or 0 if no confident peak.
 */
float estimate_periodicity_autocorr(const float *sig, uint16_t len, float fs,
                                     float bpm_lo, float bpm_hi,
                                     float reject_br_hz,
                                     float *out_peak_ratio);

/**
 * Minimum autocorrelation peak ratio (see estimate_periodicity_autocorr's
 * out_peak_ratio) required to call the breathing band "periodic" for the
 * sovereign human-presence verdict. estimate_periodicity_autocorr's own
 * acceptance floor is 0.2 (else it returns 0 BPM / 0 ratio), but that alone
 * is not a safe gate threshold: broadband noise can exceed it by chance
 * (the search scans many candidate lags — a multiple-comparisons effect).
 *
 * Empirically calibrated against the FULL canonical 6-30 BPM band (500 Monte
 * Carlo trials each, real edge_dsp_pure.c code, all SYNTHETIC — not real
 * captures, see PHANTOM_SCAN_REMEDIATION_REPORT.md):
 *   - Pure broadband noise: P(resp_conf >= 0.5) = 0.2% (1/500, max 0.53).
 *   - Synthetic breathing, 6-30 BPM, realistic noise: min resp_conf = 0.379
 *     (near the 6 BPM edge, ~1.7 cycles fit in the 256-sample/~17s window
 *     at the firmware's typical 15 Hz — a genuinely weaker signal, not a
 *     calibration error). At threshold 0.5 this gives an 8% missed-
 *     detection rate (40/500) concentrated at the low-BPM edge; at 0.2%
 *     noise false-positive rate.
 * 0.5 is kept deliberately conservative (favors NOT declaring presence over
 * a false claim, consistent with F1) even though it under-covers the
 * hardest low-BPM synthetic cases. Because Step 9 re-evaluates every frame,
 * a miss here delays registration by one analysis window rather than
 * losing a real, continuously breathing target — but this trade-off is
 * unverified against real slow-breather captures.
 */
#define EDGE_RESP_CONF_MIN 0.5f

/** Breathing sanity band (BPM), shared by the estimator's sanity clamp and
 *  the verdict's periodicity check (single source of truth, PS-AUDIT-002).
 *  Matches canon exactly: 0.1-0.5 Hz respiratory band == 6-30 BPM. The
 *  pre-WP-2 firmware's sanity clamp used 6-40 BPM (0.667 Hz upper edge),
 *  which exceeded canon with no documented clinical rationale (e.g.
 *  tachypnea coverage) anywhere in this codebase; clamped to canon here
 *  during WP-2 close-out rather than left as undocumented drift. */
#define EDGE_BREATHING_BPM_MIN 6.0f
#define EDGE_BREATHING_BPM_MAX 30.0f

/**
 * Sovereign human-presence verdict (F1 firewall, PS-AUDIT-002): motion
 * energy above threshold is necessary but not sufficient. A fan, curtain,
 * HVAC draft, or other non-human mover can raise motion energy without
 * producing genuine 0.1-0.5 Hz respiratory periodicity — this gate requires
 * both.
 *
 * Cardiac-band data (0.8-2.0 Hz rate/confidence) is deliberately NOT a
 * parameter of this function. Per canon, cardiac may only ever raise a
 * REPORTED confidence value alongside an already-positive verdict — it must
 * never gate or relax a negative respiratory verdict. Keeping it out of the
 * signature is a structural (compile-time-checkable) guarantee of that
 * constraint, not just a runtime convention: there is no cardiac data for
 * this function to consult even if a future edit tried to.
 *
 * KNOWN LIMITATION (documented, not fixed by this gate): the underlying
 * autocorrelation estimator can alias a clean, highly periodic non-human
 * vibration (e.g. a precisely-tuned mechanical resonance) into the 6-30 BPM
 * search band, because a band-limited pure tone's autocorrelation retains
 * strong peaks at integer sub-harmonics of its true period. Broadband/
 * non-tonal ambient motion (real fan blade flutter, curtains in air
 * currents, foliage, most HVAC noise) is NOT affected — see
 * main/test/test_edge_dsp_pure.c for the empirical evidence distinguishing
 * the two cases. Closing the tonal-aliasing gap requires a harmonic-purity
 * or peak-sharpness check in the estimator itself and is tracked as a
 * follow-up, not part of this fix.
 *
 * @param motion_present      True when motion_energy > the active threshold.
 * @param breathing_data_ready True once enough history has accumulated for
 *                             the BPM/confidence estimate to be meaningful
 *                             (mirrors process_frame's `s_history_len >= 64`
 *                             gate) — false during the startup transient.
 * @param breathing_bpm        Latest sanity-clamped breathing estimate.
 * @param resp_conf            Autocorr peak-ratio confidence for breathing_bpm.
 * @return true only when motion is present AND in-band, confident
 *         respiratory periodicity was found.
 */
bool edge_evaluate_human_presence(bool motion_present,
                                   bool breathing_data_ready,
                                   float breathing_bpm,
                                   float resp_conf);

#ifdef __cplusplus
}
#endif

#endif /* EDGE_DSP_PURE_H */
