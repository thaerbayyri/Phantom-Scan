/**
 * @file csi_collector.c
 * @brief CSI data collection and ADR-018 binary frame serialization.
 *
 * Registers the ESP-IDF WiFi CSI callback and serializes incoming CSI data
 * into the ADR-018 binary frame format for UDP transmission.
 *
 * ADR-029 extensions:
 *   - Channel-hop table for multi-band sensing (channels 1/6/11 by default)
 *   - Timer-driven channel hopping at configurable dwell intervals
 *   - NDP frame injection stub for sensing-first TX
 */

#include "csi_collector.h"
#include "stream_sender.h"
#include "edge_processing.h"
#include "nvs_config.h"

#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "esp_timer.h"
#include "ping/ping_sock.h"
#include "lwip/ip_addr.h"
#include "sdkconfig.h"

static const char *TAG = "csi_collector";
extern nvs_config_t g_nvs_config;
extern volatile uint32_t g_wifi_reconnect_count;
extern volatile bool g_wifi_connected;

static uint32_t s_sequence = 0;
static uint32_t s_cb_count = 0;
static uint32_t s_send_ok = 0;
static uint32_t s_send_fail = 0;
static uint32_t s_rate_skip = 0;
static uint32_t s_cb_drop = 0;
static esp_ping_handle_t s_self_ping = NULL;

/**
 * Minimum interval between UDP sends in microseconds.
 * CSI callbacks can fire hundreds of times per second in promiscuous mode.
 * We cap the send rate to avoid exhausting lwIP packet buffers (ENOMEM).
 * Default: 20 ms = 50 Hz max send rate.
 */
#define CSI_MIN_SEND_INTERVAL_US  (20 * 1000)
static int64_t s_last_send_us = 0;

static void csi_ping_cb_noop(esp_ping_handle_t hdl, void *args)
{
    (void)hdl;
    (void)args;
}

static void csi_start_self_ping(void)
{
    if (s_self_ping != NULL) {
        return;
    }

    esp_netif_t *sta_netif = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
    if (sta_netif == NULL) {
        ESP_LOGW(TAG, "self-ping skipped: station netif unavailable");
        return;
    }

    esp_netif_ip_info_t ip_info;
    esp_err_t err = esp_netif_get_ip_info(sta_netif, &ip_info);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "self-ping skipped: ip info unavailable (%s)", esp_err_to_name(err));
        return;
    }

    if (ip_info.gw.addr == 0) {
        ESP_LOGW(TAG, "self-ping skipped: gateway not assigned yet");
        return;
    }

    ip_addr_t target_addr;
    memset(&target_addr, 0, sizeof(target_addr));
    target_addr.type = IPADDR_TYPE_V4;
    target_addr.u_addr.ip4.addr = ip_info.gw.addr;

    esp_ping_config_t ping_config = ESP_PING_DEFAULT_CONFIG();
    ping_config.target_addr = target_addr;
    ping_config.count = ESP_PING_COUNT_INFINITE;
    ping_config.interval_ms = 20;
    ping_config.data_size = 1;

    esp_ping_callbacks_t callbacks = {
        .cb_args = NULL,
        .on_ping_success = csi_ping_cb_noop,
        .on_ping_timeout = csi_ping_cb_noop,
        .on_ping_end = csi_ping_cb_noop,
    };

    err = esp_ping_new_session(&ping_config, &callbacks, &s_self_ping);
    if (err != ESP_OK) {
        s_self_ping = NULL;
        ESP_LOGW(TAG, "self-ping session create failed: %s", esp_err_to_name(err));
        return;
    }

    err = esp_ping_start(s_self_ping);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "self-ping start failed: %s", esp_err_to_name(err));
        esp_ping_delete_session(s_self_ping);
        s_self_ping = NULL;
        return;
    }

    ESP_LOGI(TAG, "self-ping started -> " IPSTR " @50Hz (CSI OFDM source)", IP2STR(&ip_info.gw));
}

/* ---- ADR-029: Channel-hop state ---- */

/** Channel hop table (populated from NVS at boot or via set_hop_table). */
static uint8_t  s_hop_channels[CSI_HOP_CHANNELS_MAX] = {1, 6, 11, 36, 40, 44};

/** Number of active channels in the hop table. 1 = single-channel (no hop). */
static uint8_t  s_hop_count   = 1;

/** Dwell time per channel in milliseconds. */
static uint32_t s_dwell_ms    = 50;

/** Current index into s_hop_channels. */
static uint8_t  s_hop_index   = 0;

/** Handle for the periodic hop timer. NULL when timer is not running. */
static esp_timer_handle_t s_hop_timer = NULL;

/**
 * Serialize CSI data into ADR-018 binary frame format.
 *
 * Layout:
 *   [0..3]   Magic: 0xC5110001 (LE)
 *   [4]      Schema version
 *   [5]      Node ID
 *   [6]      Number of antennas
 *   [7..8]   Number of subcarriers (LE u16)
 *   [9..12]  Frequency MHz (LE u32) — derived from channel
 *   [13..16] Sequence number (LE u32)
 *   [17]     RSSI (i8)
 *   [18]     Noise floor (i8)
 *   [19]     WiFi channel
 *   [20..27] Device timestamp us (LE u64)
 *   [28..31] Device timestamp ms (LE u32)
 *   [32..]   I/Q data (raw bytes from ESP-IDF callback)
 */
size_t csi_serialize_frame(const wifi_csi_info_t *info, uint8_t *buf, size_t buf_len)
{
    if (info == NULL || buf == NULL || info->buf == NULL) {
        return 0;
    }

    uint8_t n_antennas = 1;  /* ESP32-S3 typically reports 1 antenna for CSI */
    uint16_t iq_len = (uint16_t)info->len;
    uint16_t n_subcarriers = iq_len / (2 * n_antennas);

    size_t frame_size = CSI_HEADER_SIZE + iq_len;
    if (frame_size > buf_len) {
        ESP_LOGW(TAG, "Buffer too small: need %u, have %u", (unsigned)frame_size, (unsigned)buf_len);
        return 0;
    }

    /* Derive frequency from channel number */
    uint8_t channel = info->rx_ctrl.channel;
    uint32_t freq_mhz;
    if (channel >= 1 && channel <= 13) {
        freq_mhz = 2412 + (channel - 1) * 5;
    } else if (channel == 14) {
        freq_mhz = 2484;
    } else if (channel >= 36 && channel <= 177) {
        freq_mhz = 5000 + channel * 5;
    } else {
        freq_mhz = 0;
    }

    /* Magic (LE) */
    uint32_t magic = CSI_MAGIC;
    memcpy(&buf[0], &magic, 4);

    /* Schema version */
    buf[4] = (uint8_t)CSI_SCHEMA_VERSION;

    /* Node ID */
    buf[5] = (uint8_t)g_nvs_config.node_id;

    /* Number of antennas */
    buf[6] = n_antennas;

    /* Number of subcarriers (LE u16) */
    memcpy(&buf[7], &n_subcarriers, 2);

    /* Frequency MHz (LE u32) */
    memcpy(&buf[9], &freq_mhz, 4);

    /* Sequence number (LE u32) */
    uint32_t seq = s_sequence++;
    memcpy(&buf[13], &seq, 4);

    /* RSSI (i8) */
    buf[17] = (uint8_t)(int8_t)info->rx_ctrl.rssi;

    /* Noise floor (i8) */
    buf[18] = (uint8_t)(int8_t)info->rx_ctrl.noise_floor;

    /* Channel */
    buf[19] = channel;

    uint64_t device_ts_us = (uint64_t)esp_timer_get_time();
    uint32_t device_ts_ms = (uint32_t)(device_ts_us / 1000ULL);
    memcpy(&buf[20], &device_ts_us, sizeof(device_ts_us));
    memcpy(&buf[28], &device_ts_ms, sizeof(device_ts_ms));

    /* I/Q data */
    memcpy(&buf[CSI_HEADER_SIZE], info->buf, iq_len);

    return frame_size;
}

/**
 * WiFi CSI callback — invoked by ESP-IDF when CSI data is available.
 */
static void wifi_csi_callback(void *ctx, wifi_csi_info_t *info)
{
    (void)ctx;
    s_cb_count++;

    if (s_cb_count <= 3 || (s_cb_count % 250) == 0) {
        ESP_LOGI(TAG, "CSI cb #%lu: len=%d rssi=%d ch=%d",
                 (unsigned long)s_cb_count, info->len,
                 info->rx_ctrl.rssi, info->rx_ctrl.channel);
    }

    uint8_t frame_buf[CSI_MAX_FRAME_SIZE];
    size_t frame_len = csi_serialize_frame(info, frame_buf, sizeof(frame_buf));

    if (frame_len > 0) {
        /* Rate-limit UDP sends to avoid ENOMEM from lwIP pbuf exhaustion.
         * In promiscuous mode, CSI callbacks can fire 100-500+ times/sec.
         * We only need 20-50 Hz for the sensing pipeline. */
        int64_t now = esp_timer_get_time();
        if ((now - s_last_send_us) >= CSI_MIN_SEND_INTERVAL_US) {
            int ret = stream_sender_send(frame_buf, frame_len);
            if (ret > 0) {
                s_send_ok++;
                s_last_send_us = now;
            } else {
                s_send_fail++;
                if (s_send_fail <= 5) {
                    ESP_LOGW(TAG, "sendto failed (fail #%lu)", (unsigned long)s_send_fail);
                }
            }
        } else {
            s_rate_skip++;
        }
    }

    /* ADR-039: Enqueue raw I/Q into edge processing ring buffer. */
    if (info->buf && info->len > 0) {
        if (!edge_enqueue_csi((const uint8_t *)info->buf, (uint16_t)info->len,
                              (int8_t)info->rx_ctrl.rssi, info->rx_ctrl.channel)) {
            s_cb_drop++;
        }
    }
}

/**
 * Promiscuous mode callback — required for CSI to fire on all received frames.
 * We don't need the packet content, just the CSI triggered by reception.
 */
static void wifi_promiscuous_cb(void *buf, wifi_promiscuous_pkt_type_t type)
{
    /* No-op: CSI callback is registered separately and fires in parallel. */
    (void)buf;
    (void)type;
}

void csi_collector_init(void)
{
    /* Enable promiscuous mode — required for reliable CSI callbacks.
     * Without this, CSI only fires on frames destined to this station,
     * which may be very infrequent on a quiet network. */
    ESP_ERROR_CHECK(esp_wifi_set_promiscuous(true));
    ESP_ERROR_CHECK(esp_wifi_set_promiscuous_rx_cb(wifi_promiscuous_cb));

    wifi_promiscuous_filter_t filt = {
        .filter_mask = WIFI_PROMIS_FILTER_MASK_MGMT | WIFI_PROMIS_FILTER_MASK_DATA,
    };
    ESP_ERROR_CHECK(esp_wifi_set_promiscuous_filter(&filt));

    ESP_LOGI(TAG, "CSI filter upgraded to MGMT+DATA");

    wifi_csi_config_t csi_config = {
        .lltf_en = true,
        .htltf_en = true,
        .stbc_htltf2_en = true,
        .ltf_merge_en = true,
        .channel_filter_en = false,
        .manu_scale = false,
        .shift = false,
    };

    ESP_ERROR_CHECK(esp_wifi_set_csi_config(&csi_config));
    ESP_ERROR_CHECK(esp_wifi_set_csi_rx_cb(wifi_csi_callback, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_csi(true));
    csi_start_self_ping();

    ESP_LOGI(TAG, "CSI collection initialized (node_id=%d, channel=%d)",
             g_nvs_config.node_id, CONFIG_CSI_WIFI_CHANNEL);
}

/* ---- ADR-029: Channel hopping ---- */

void csi_collector_set_hop_table(const uint8_t *channels, uint8_t hop_count, uint32_t dwell_ms)
{
    if (channels == NULL) {
        ESP_LOGW(TAG, "csi_collector_set_hop_table: channels is NULL");
        return;
    }
    if (hop_count == 0 || hop_count > CSI_HOP_CHANNELS_MAX) {
        ESP_LOGW(TAG, "csi_collector_set_hop_table: invalid hop_count=%u (max=%u)",
                 (unsigned)hop_count, (unsigned)CSI_HOP_CHANNELS_MAX);
        return;
    }
    if (dwell_ms < 10) {
        ESP_LOGW(TAG, "csi_collector_set_hop_table: dwell_ms=%lu too small, clamping to 10",
                 (unsigned long)dwell_ms);
        dwell_ms = 10;
    }

    memcpy(s_hop_channels, channels, hop_count);
    s_hop_count = hop_count;
    s_dwell_ms  = dwell_ms;
    s_hop_index = 0;

    ESP_LOGI(TAG, "Hop table set: %u channels, dwell=%lu ms", (unsigned)hop_count,
             (unsigned long)dwell_ms);
    for (uint8_t i = 0; i < hop_count; i++) {
        ESP_LOGI(TAG, "  hop[%u] = channel %u", (unsigned)i, (unsigned)channels[i]);
    }
}

void csi_hop_next_channel(void)
{
    if (s_hop_count <= 1) {
        /* Single-channel mode: no-op for backward compatibility. */
        return;
    }

    s_hop_index = (s_hop_index + 1) % s_hop_count;
    uint8_t channel = s_hop_channels[s_hop_index];

    /*
     * esp_wifi_set_channel() changes the primary channel.
     * The second parameter is the secondary channel offset for HT40;
     * we use HT20 (no secondary) for sensing.
     */
    esp_err_t err = esp_wifi_set_channel(channel, WIFI_SECOND_CHAN_NONE);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "Channel hop to %u failed: %s", (unsigned)channel, esp_err_to_name(err));
    } else if ((s_cb_count % 200) == 0) {
        /* Periodic log to confirm hopping is working (not every hop). */
        ESP_LOGI(TAG, "Hopped to channel %u (index %u/%u)",
                 (unsigned)channel, (unsigned)s_hop_index, (unsigned)s_hop_count);
    }
}

/**
 * Timer callback for channel hopping.
 * Called every s_dwell_ms milliseconds from the esp_timer context.
 */
static void hop_timer_cb(void *arg)
{
    (void)arg;
    csi_hop_next_channel();
}

void csi_collector_start_hop_timer(void)
{
    if (s_hop_count <= 1) {
        ESP_LOGI(TAG, "Single-channel mode: hop timer not started");
        return;
    }

    if (s_hop_timer != NULL) {
        ESP_LOGW(TAG, "Hop timer already running");
        return;
    }

    esp_timer_create_args_t timer_args = {
        .callback = hop_timer_cb,
        .arg      = NULL,
        .name     = "csi_hop",
    };

    esp_err_t err = esp_timer_create(&timer_args, &s_hop_timer);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to create hop timer: %s", esp_err_to_name(err));
        return;
    }

    uint64_t period_us = (uint64_t)s_dwell_ms * 1000;
    err = esp_timer_start_periodic(s_hop_timer, period_us);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to start hop timer: %s", esp_err_to_name(err));
        esp_timer_delete(s_hop_timer);
        s_hop_timer = NULL;
        return;
    }

    ESP_LOGI(TAG, "Hop timer started: period=%lu ms, channels=%u",
             (unsigned long)s_dwell_ms, (unsigned)s_hop_count);
}

/* ---- ADR-029: NDP frame injection stub ---- */

esp_err_t csi_inject_ndp_frame(void)
{
    /*
     * TODO: Construct a proper 802.11 Null Data Packet frame.
     *
     * A real NDP is preamble-only (~24 us airtime, no payload) and is the
     * sensing-first TX mechanism described in ADR-029. For now we send a
     * minimal null-data frame as a placeholder so the API is wired up.
     *
     * Frame structure (IEEE 802.11 Null Data):
     *   FC (2) | Duration (2) | Addr1 (6) | Addr2 (6) | Addr3 (6) | SeqCtl (2)
     *   = 24 bytes total, no body, no FCS (hardware appends FCS).
     */
    uint8_t ndp_frame[24];
    memset(ndp_frame, 0, sizeof(ndp_frame));

    /* Frame Control: Type=Data (0x02), Subtype=Null (0x04) -> 0x0048 */
    ndp_frame[0] = 0x48;
    ndp_frame[1] = 0x00;

    /* Duration: 0 (let hardware fill) */

    /* Addr1 (destination): broadcast */
    memset(&ndp_frame[4], 0xFF, 6);

    /* Addr2 (source): will be overwritten by hardware with own MAC */

    /* Addr3 (BSSID): broadcast */
    memset(&ndp_frame[16], 0xFF, 6);

    esp_err_t err = esp_wifi_80211_tx(WIFI_IF_STA, ndp_frame, sizeof(ndp_frame), false);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "NDP inject failed: %s", esp_err_to_name(err));
    }

    return err;
}

static void csi_heartbeat_task(void *arg)
{
    (void)arg;
    uint32_t last_send_ok = 0;
    uint32_t last_cb_count = 0;
    while (1) {
        csi_heartbeat_pkt_t pkt;
        memset(&pkt, 0, sizeof(pkt));
        pkt.magic = CSI_HEARTBEAT_MAGIC;
        pkt.schema_version = CSI_SCHEMA_VERSION;
        pkt.node_id = g_nvs_config.node_id;
        pkt.wifi_connected = g_wifi_connected ? 1 : 0;
        pkt.seq = s_sequence;
        pkt.device_ts_ms = (uint32_t)(esp_timer_get_time() / 1000ULL);

        edge_runtime_stats_t edge_stats;
        memset(&edge_stats, 0, sizeof(edge_stats));
        edge_get_stats(&edge_stats);

        pkt.callback_drops = s_cb_drop + edge_stats.enqueue_drops;
        pkt.queue_high_watermark = edge_stats.queue_high_watermark;
        pkt.send_failures = s_send_fail;
        pkt.reconnect_count = g_wifi_reconnect_count;
        pkt.firmware_build_id = 1;

        stream_sender_send((const uint8_t *)&pkt, sizeof(pkt));
        ESP_LOGI(
            TAG,
            "medium tick: yield=%lupps csi_cb=%lu send_fail=%lu rate_skip=%lu cb_drop=%lu",
            (unsigned long)(s_send_ok - last_send_ok),
            (unsigned long)(s_cb_count - last_cb_count),
            (unsigned long)s_send_fail,
            (unsigned long)s_rate_skip,
            (unsigned long)(s_cb_drop + edge_stats.enqueue_drops)
        );
        last_send_ok = s_send_ok;
        last_cb_count = s_cb_count;
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

void csi_collector_start_heartbeat_task(void)
{
    xTaskCreatePinnedToCore(
        csi_heartbeat_task,
        "csi_heartbeat",
        4096,
        NULL,
        4,
        NULL,
        1
    );
}
