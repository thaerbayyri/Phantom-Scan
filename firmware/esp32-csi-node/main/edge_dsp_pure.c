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
                                   float resp_conf)
{
    if (!motion_present || !breathing_data_ready) return false;

    bool in_band = (breathing_bpm >= EDGE_BREATHING_BPM_MIN) &&
                   (breathing_bpm <= EDGE_BREATHING_BPM_MAX);
    bool confident = (resp_conf >= EDGE_RESP_CONF_MIN);

    return in_band && confident;
}
