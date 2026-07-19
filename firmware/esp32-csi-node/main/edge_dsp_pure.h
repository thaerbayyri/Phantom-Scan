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
 * Empirically calibrated (main/test/test_edge_dsp_pure.c calibration run,
 * 500 Monte Carlo trials each, real edge_dsp_pure.c code): pure broadband
 * noise exceeds 0.5 in only 0.2% of trials (1/500, max observed 0.53),
 * while synthetic breathing across the 8-40 BPM physiological range with
 * realistic noise never produced a confidence below 0.59 (0/500 misses).
 * 0.5 sits with margin on both sides of that gap.
 */
#define EDGE_RESP_CONF_MIN 0.5f

/** Breathing sanity band (BPM), shared by the estimator's sanity clamp and
 *  the verdict's periodicity check (single source of truth, PS-AUDIT-002). */
#define EDGE_BREATHING_BPM_MIN 6.0f
#define EDGE_BREATHING_BPM_MAX 40.0f

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
 * vibration (e.g. a precisely-tuned mechanical resonance) into the 6-40 BPM
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
