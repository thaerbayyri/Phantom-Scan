/**
 * @file csi_ping_pure.h
 * @brief Timing constants and the per-node start offset for the CSI self-ping.
 *
 * Header-only and free of ESP-IDF includes so it can be unit-tested on the
 * host (see test/test_csi_ping_pure.c).
 *
 * Why these values: the self-ping is the CSI source (the AP's echo replies).
 * esp_ping blocks on each reply for `timeout_ms`; with the 1000 ms default a
 * single lost reply froze a node's CSI stream for a second, which with four
 * nodes sharing one AP showed up as 10-20 fps. A short timeout bounds the stall
 * to one interval. Nodes also start their pings at different offsets so four
 * boards do not hit the AP in the same instant.
 */
#ifndef CSI_PING_PURE_H
#define CSI_PING_PURE_H

#include <stdint.h>

/**
 * Gap between echo requests. FreeRTOS ticks are 10 ms here (CONFIG_FREERTOS_HZ=100),
 * so keep this a multiple of 10: ~33 pps per node plus ~10 Hz of AP beacons gives
 * roughly 40 fps without overloading the AP with four nodes.
 */
#define CSI_PING_INTERVAL_MS      30U
/** Reply wait. Must stay below the interval so a lost reply costs at most one slot. */
#define CSI_PING_TIMEOUT_MS       20U
/** Minimum spacing of forwarded CSI frames (was 20 ms, which aliased with the ping). */
#define CSI_MIN_SEND_INTERVAL_MS  10U
/** Offsets are spread over this many distinct slots (node ids 1..4 plus headroom). */
#define CSI_PING_SLOTS            4U

/**
 * Delay before this node starts pinging, in ms. Spreads nodes evenly across one
 * ping interval: with 4 slots and a 30 ms interval the offsets are 0, 7, 14, 21.
 */
static inline uint32_t csi_ping_start_offset_ms(uint8_t node_id, uint32_t interval_ms)
{
    if (interval_ms == 0U) {
        return 0U;
    }
    return ((uint32_t)node_id % CSI_PING_SLOTS) * (interval_ms / CSI_PING_SLOTS);
}

#endif /* CSI_PING_PURE_H */
