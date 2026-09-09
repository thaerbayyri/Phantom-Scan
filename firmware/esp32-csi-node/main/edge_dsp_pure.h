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
 * Regularity metric for the breathing-band signal, combining two checks
 * (PS-AUDIT-002 follow-up, WP-16):
 *
 * 1. Coefficient of variation (stddev/mean) of consecutive positive
 *    zero-crossing intervals. Real biological breathing has natural
 *    cycle-to-cycle rate jitter, while a clean mechanical tone (fan, HVAC at
 *    a stable RPM) is MORE regular cycle-to-cycle than a human ever is. A
 *    high CV is therefore evidence FOR biological breathing; a near-zero CV
 *    is evidence the source is mechanical — the opposite polarity of a
 *    typical signal-quality metric.
 * 2. Crossing-count multiplicity vs. `claimed_bpm`: sub-harmonic aliasing
 *    (see estimate_periodicity_autocorr's docstring) reports a slow BPM from
 *    a much FASTER underlying raw oscillation, so the raw zero-crossing
 *    count in the window is far higher than one crossing per claimed cycle
 *    would predict. This under-sampled-relative-to-its-own-frequency
 *    condition also defeats check 1 alone (interpolated crossing timing
 *    still carries real quantization/interpolation noise when there are
 *    only a handful of raw samples per raw cycle), so a large multiplicity
 *    is treated as decisive evidence of a non-biological source regardless
 *    of the CV, and this function returns 0.0f (forces rejection) in that
 *    case without needing a separate return channel.
 *
 * @param claimed_bpm  The breathing_bpm the gate is about to evaluate (0 or
 *                     negative to skip the multiplicity check, e.g. when the
 *                     estimate was already out of band).
 * @return stddev/mean of the crossing-to-crossing intervals (0.0f if the
 *         multiplicity check alone indicates a non-biological source), or
 *         -1.0f (indeterminate sentinel) when fewer than 3 zero-crossings
 *         are found in the window (too few cycles to judge jitter
 *         meaningfully).
 */
float estimate_period_regularity_cv(const float *sig, uint16_t len, float fs,
                                     float claimed_bpm);

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

/**
 * Minimum cycle-to-cycle period coefficient of variation (see
 * estimate_period_regularity_cv) required to accept in-band periodicity as
 * biological rather than a clean mechanical tone (PS-AUDIT-002 follow-up,
 * WP-16). PLACEHOLDER, calibrated only against SYNTHETIC data the same way
 * EDGE_RESP_CONF_MIN was (see PHANTOM_SCAN_REMEDIATION_REPORT.md) — needs
 * real-hardware breathing captures and a real fan/HVAC negative control
 * before this threshold can be considered final. Values below this are
 * treated as "too regular to be human"; the -1.0f indeterminate sentinel
 * (too few cycles in the window) is treated as PASS, not reject — see
 * edge_evaluate_human_presence's docstring for why.
 *
 * Deliberately set very low: estimate_period_regularity_cv's sub-harmonic-
 * aliasing multiplicity check (not this raw-CV floor) is what actually
 * rejects the documented tonal-aliasing exploit (forces the return to
 * 0.0f — see test_tonal_aliasing_is_rejected, measured period_cv=0.000 for
 * the canonical 2.2 Hz aliasing case). A higher floor here was tried and
 * measurably hurt real jittered-breathing detection (raised the Monte Carlo
 * missed-detection rate from ~20% to 30%+ purely from raw CV chance-dipping
 * below the floor near the low-cycle-count band edges — see
 * test_monte_carlo_calibration_bounds) without improving tonal-aliasing
 * rejection, which the multiplicity check already handles. This constant's
 * remaining job is a weak secondary backstop, not the primary mitigation.
 */
#define EDGE_RESP_PERIOD_CV_MIN 0.002f

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
 * TONAL-ALIASING MITIGATION (PS-AUDIT-002 follow-up, WP-16): the underlying
 * autocorrelation estimator can alias a clean, highly periodic non-human
 * vibration (e.g. a precisely-tuned mechanical resonance) into the 6-30 BPM
 * search band, because a band-limited pure tone's autocorrelation retains
 * strong peaks at integer sub-harmonics of its true period. Broadband/
 * non-tonal ambient motion (real fan blade flutter, curtains in air
 * currents, foliage, most HVAC noise) is NOT affected. This gate now also
 * requires `period_cv` (see estimate_period_regularity_cv, which folds in
 * BOTH a raw cycle-to-cycle jitter CV and a sub-harmonic-aliasing crossing-
 * multiplicity check — the multiplicity check is what actually rejects the
 * documented exploit; see that function's docstring) to show evidence of a
 * biological source: a clean mechanical tone — whether via near-zero raw
 * jitter or, more decisively, via far more raw oscillation cycles than its
 * claimed BPM implies — is rejected even if it otherwise passes the
 * confidence/band checks. The indeterminate sentinel (-1.0f, too few cycles
 * in the window to judge) is treated as PASS, matching the existing
 * conservative-on-missed-detection stance at the low-BPM edge (see
 * EDGE_RESP_CONF_MIN's docstring)
 * rather than rejecting cases the estimator can't evaluate. The threshold
 * (EDGE_RESP_PERIOD_CV_MIN) is a placeholder calibrated only on synthetic
 * data — see main/test/test_edge_dsp_pure.c for the empirical evidence and
 * PHANTOM_SCAN_REMEDIATION_REPORT.md for the real-hardware validation this
 * still needs.
 *
 * @param motion_present      True when motion_energy > the active threshold.
 * @param breathing_data_ready True once enough history has accumulated for
 *                             the BPM/confidence estimate to be meaningful
 *                             (mirrors process_frame's `s_history_len >= 64`
 *                             gate) — false during the startup transient.
 * @param breathing_bpm        Latest sanity-clamped breathing estimate.
 * @param resp_conf            Autocorr peak-ratio confidence for breathing_bpm.
 * @param period_cv            Cycle-to-cycle period coefficient of variation
 *                              from estimate_period_regularity_cv, or -1.0f
 *                              when indeterminate (see above).
 * @return true only when motion is present AND in-band, confident,
 *         naturally-jittered respiratory periodicity was found.
 */
bool edge_evaluate_human_presence(bool motion_present,
                                   bool breathing_data_ready,
                                   float breathing_bpm,
                                   float resp_conf,
                                   float period_cv);

/**
 * Minimum outlier margin (in window sigmas) between the single largest
 * sample seen during an adaptive-calibration accumulation window and that
 * window's own mean, above which the window is rejected as contaminated
 * (see edge_evaluate_calibration_window). Deliberately much larger than
 * EDGE_CALIB_SIGMA_MULT (3.0, used for the resulting presence threshold
 * itself): for a window of EDGE_CALIB_FRAMES=1200 i.i.d. samples, extreme-
 * value theory puts the expected max deviation of genuinely empty-room
 * noise at roughly sqrt(2*ln(1200)) ~= 3.8 sigma, so an 8-sigma floor should
 * essentially never reject a truly empty, steady-state window while still
 * catching a transient contaminating spike (a person walking through, or a
 * mechanical mover switching on) whose motion-energy peak is realistically
 * many multiples of ambient noise. PLACEHOLDER pending real-hardware
 * empty-room + negative-control validation, same caveat as
 * EDGE_RESP_PERIOD_CV_MIN — see PHANTOM_SCAN_REMEDIATION_REPORT.md.
 */
#define EDGE_CALIB_REJECT_SIGMA_MULT 8.0f

/**
 * Validate a completed adaptive-calibration accumulation window before
 * calibration_update (edge_processing.c) locks its mean+k*sigma in as the
 * live presence threshold. The window is assumed to have been captured in
 * an empty room; this function looks for evidence it wasn't.
 *
 * A contaminating motion event during the supposed-empty boot window (an
 * occupant walking through, or a mechanical mover such as a fan/HVAC
 * cycling on) shows up as one or a few samples far above the window's own
 * mean+sigma envelope, even though the same event also inflates the
 * window's mean and sigma themselves (diluted by the other ~1200 samples,
 * so the inflation is real but partial) — a check based on mean/sigma alone
 * would partially hide the very contamination it's supposed to detect.
 * Comparing the window's single largest sample against its own mean/sigma
 * catches this: the max is dominated by the spike, not the dilution.
 *
 * This only detects the "contamination" failure direction (room not empty
 * during boot). It cannot detect the opposite direction (a genuinely quiet
 * but unrepresentative window setting too low a threshold) — that failure
 * mode has no spike signature to key off and is out of scope here.
 *
 * @param mean       Window mean motion energy.
 * @param sigma      Window standard deviation of motion energy (the
 *                   caller's divide-by-zero floor, e.g. 0.001f when
 *                   variance <= 0, applies before this is called).
 * @param max_sample Largest single motion-energy sample observed during the
 *                   window (running max, tracked alongside sum/sum_sq).
 * @return true when the window looks like steady-state ambient noise (safe
 *         to lock in as the calibrated threshold); false when a
 *         contaminating spike was detected and the caller should discard
 *         the window and re-accumulate.
 */
bool edge_evaluate_calibration_window(float mean, float sigma, float max_sample);

#ifdef __cplusplus
}
#endif

#endif /* EDGE_DSP_PURE_H */
