/**
 * @file csi_collector.h
 * @brief CSI data collection and ADR-018 binary frame serialization.
 */

#ifndef CSI_COLLECTOR_H
#define CSI_COLLECTOR_H

#include <stdint.h>
#include <stddef.h>
#include "esp_err.h"
#include "esp_wifi_types.h"

/** ADR-018 magic number. */
#define CSI_MAGIC 0xC5110001
#define CSI_HEARTBEAT_MAGIC 0xC51100A1
#define CSI_SCHEMA_VERSION 1

/** ADR-018 header size in bytes. */
#define CSI_HEADER_SIZE 32

/** Maximum frame buffer size: header + generous upper bound (4x oversized vs. the
 *  1 antenna * 256 subcarriers this hardware actually sends) to safely absorb any
 *  malformed/oversized packet. Not a reflection of expected antenna count. */
#define CSI_MAX_FRAME_SIZE (CSI_HEADER_SIZE + 4 * 256 * 2)

/** Maximum number of channels in the hop table (ADR-029). */
#define CSI_HOP_CHANNELS_MAX 6

/**
 * Initialize CSI collection.
 * Registers the WiFi CSI callback.
 */
void csi_collector_init(void);

/**
 * Cache the node ID before WiFi bring-up.
 *
 * Must be called right after nvs_config_load(), BEFORE wifi_init_sta():
 * WiFi init has historically clobbered the runtime config struct, and a
 * corrupted node_id makes two boards indistinguishable at the host
 * (which then rejects one of them as a source-mismatch spoof).
 */
void csi_collector_set_node_id(uint8_t node_id);

/**
 * Cache the NVS filter_mac blob (see csi_filter_pure.h) before WiFi init,
 * for the same clobbering reason as csi_collector_set_node_id(). `len` is 0
 * when the key is absent (auto: filter to the connected AP's BSSID).
 */
void csi_collector_set_filter_config(const uint8_t *nvs_filter_mac, uint8_t len);

/**
 * Re-resolve the active source-MAC filter: the NVS MAC, nothing ("off"), or
 * the currently connected AP's BSSID. Call after (re)connecting to the AP —
 * the BSSID can change across reconnects on multi-AP networks.
 */
void csi_collector_refresh_filter_mac(void);

/**
 * Serialize CSI data into ADR-018 binary frame format.
 *
 * @param info   WiFi CSI info from the ESP-IDF callback.
 * @param buf    Output buffer (must be at least CSI_MAX_FRAME_SIZE bytes).
 * @param buf_len Size of the output buffer.
 * @return Number of bytes written, or 0 on error.
 */
size_t csi_serialize_frame(const wifi_csi_info_t *info, uint8_t *buf, size_t buf_len);

typedef struct __attribute__((packed)) {
    uint32_t magic;
    uint8_t  schema_version;
    uint8_t  node_id;
    uint8_t  wifi_connected;
    uint8_t  reserved0;
    uint32_t seq;
    uint32_t device_ts_ms;
    uint32_t callback_drops;
    uint32_t queue_high_watermark;
    uint32_t send_failures;
    uint32_t reconnect_count;
    uint64_t firmware_build_id;
} csi_heartbeat_pkt_t;

_Static_assert(sizeof(csi_heartbeat_pkt_t) == 40, "heartbeat packet must be 40 bytes");

/**
 * Configure the channel-hop table for multi-band sensing (ADR-029).
 *
 * When hop_count == 1 the collector stays on the single configured channel
 * (backward-compatible with the original single-channel mode).
 *
 * @param channels  Array of WiFi channel numbers (1-14 for 2.4 GHz, 36-177 for 5 GHz).
 * @param hop_count Number of entries in the channels array (1..CSI_HOP_CHANNELS_MAX).
 * @param dwell_ms  Dwell time per channel in milliseconds (>= 10).
 */
void csi_collector_set_hop_table(const uint8_t *channels, uint8_t hop_count, uint32_t dwell_ms);

/**
 * Advance to the next channel in the hop table.
 *
 * Called by the hop timer callback. If hop_count <= 1 this is a no-op.
 * Calls esp_wifi_set_channel() internally.
 */
void csi_hop_next_channel(void);

/**
 * Start the channel-hop timer.
 *
 * Creates an esp_timer periodic callback that fires every dwell_ms
 * milliseconds, calling csi_hop_next_channel(). If hop_count <= 1
 * the timer is not started (single-channel backward-compatible mode).
 */
void csi_collector_start_hop_timer(void);

/**
 * Inject an NDP (Null Data Packet) frame for sensing.
 *
 * Uses esp_wifi_80211_tx() to send a preamble-only frame (~24 us airtime)
 * that triggers CSI measurement at all receivers. This is the "sensing-first"
 * TX mechanism described in ADR-029.
 *
 * @return ESP_OK on success, or an error code.
 *
 * @note TODO: Full NDP frame construction. Currently sends a minimal
 *       null-data frame as a placeholder.
 */
esp_err_t csi_inject_ndp_frame(void);
void csi_collector_start_heartbeat_task(void);

#endif /* CSI_COLLECTOR_H */
