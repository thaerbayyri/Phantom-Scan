/**
 * @file rv_feature_state.h
 * @brief Compact on-wire feature state packet (ported from RuView ADR-081).
 *
 * Carries the board DSP results (motion/presence/vitals) WITH real confidence
 * fields, replacing the confidence-less 0xC5110002 vitals packet as this
 * firmware's wire format. The dashboard server already parses this layout
 * (server/lib/udp-server.ts parseFeatureStatePacket).
 *
 * Magic numbers in use across this firmware:
 *   0xC5110001 — raw CSI frame        (csi_collector.h)
 *   0xC5110002 — vitals packet        (edge_processing.h, internal/display only)
 *   0xC5110003 — compressed CSI       (edge_processing.h)
 *   0xC5110006 — feature state        (this file)
 *   0xC51100A1 — heartbeat            (csi_collector.c)
 */

#ifndef RV_FEATURE_STATE_H
#define RV_FEATURE_STATE_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/** Magic number for rv_feature_state_t. */
#define RV_FEATURE_STATE_MAGIC  0xC5110006u

/** Quality flag bits. */
#define RV_QFLAG_PRESENCE_VALID      (1u << 0)
#define RV_QFLAG_RESPIRATION_VALID   (1u << 1)
#define RV_QFLAG_HEARTBEAT_VALID     (1u << 2)
#define RV_QFLAG_ANOMALY_TRIGGERED   (1u << 3)
#define RV_QFLAG_ENV_SHIFT_DETECTED  (1u << 4)
#define RV_QFLAG_DEGRADED_MODE       (1u << 5)
#define RV_QFLAG_CALIBRATING         (1u << 6)
#define RV_QFLAG_RECOMMEND_RECAL     (1u << 7)

/**
 * Compact per-node sensing state, emitted at the vitals interval (~1 Hz).
 *
 * CRC32 is the IEEE polynomial computed over bytes [0 .. sizeof - 4].
 * The 60-byte layout is wire-compatible with RuView's ADR-081 packet and
 * with the dashboard server's parser — do not reorder fields.
 */
typedef struct __attribute__((packed)) {
    uint32_t magic;             /**< RV_FEATURE_STATE_MAGIC. */
    uint8_t  node_id;           /**< Source node id. */
    uint8_t  mode;              /**< Capture profile at emit time (0 = default). */
    uint16_t seq;               /**< Monotonic per-node sequence. */
    uint64_t ts_us;             /**< Node-local microseconds. */
    float    motion_score;      /**< Raw motion energy (phase variance). */
    float    presence_score;    /**< Raw presence score (== motion energy). */
    float    respiration_bpm;   /**< Breaths per minute. */
    float    respiration_conf;  /**< 0..1 autocorr peak ratio mapping. */
    float    heartbeat_bpm;     /**< Beats per minute. */
    float    heartbeat_conf;    /**< 0..1 autocorr peak ratio mapping. */
    float    anomaly_score;     /**< 1 when fall detected, else 0. */
    float    env_shift_score;   /**< 0..1, baseline drift (unused: 0). */
    float    node_coherence;    /**< 0..1, multi-link agreement (unused: 0). */
    uint16_t quality_flags;     /**< RV_QFLAG_* bitmap. */
    uint16_t reserved;
    uint32_t crc32;             /**< IEEE CRC32 over bytes [0..end-4]. */
} rv_feature_state_t;

_Static_assert(sizeof(rv_feature_state_t) == 60,
               "rv_feature_state_t must be 60 bytes on the wire");

/**
 * Compute IEEE CRC32 over a byte buffer (bit-by-bit; the ~60-byte packet at
 * 1 Hz has negligible CPU cost, so no lookup table).
 */
uint32_t rv_feature_state_crc32(const uint8_t *data, size_t len);

/**
 * Finalize an rv_feature_state_t by populating magic, node_id, mode, seq,
 * ts_us, and crc32. Caller fills the remaining fields in-place before
 * calling this; after finalize() the packet is ready to send on the wire.
 */
void rv_feature_state_finalize(rv_feature_state_t *pkt,
                               uint8_t node_id,
                               uint16_t seq,
                               uint64_t ts_us,
                               uint8_t mode);

#ifdef __cplusplus
}
#endif

#endif /* RV_FEATURE_STATE_H */
