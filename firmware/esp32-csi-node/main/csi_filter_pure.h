/**
 * @file csi_filter_pure.h
 * @brief Pure (host-testable) source-MAC filter for CSI frames.
 *
 * In promiscuous MGMT+DATA mode the CSI callback fires for frames from ANY
 * transmitter (phones, beacons from neighbouring APs, the other nodes). Each
 * node's temporal amplitude statistics then mix unrelated radio links, which
 * reads as "motion" in an empty room. Filtering to one transmitter (by
 * default the connected AP, whose replies to the 50 Hz self-ping are the
 * intended sensing link) keeps a single, stable link per node.
 *
 * The filter MUST run before the 50 Hz send rate gate: otherwise frames from
 * other transmitters consume the send slots and the wanted link's yield
 * collapses (RuView ADR-345 measured ~42 -> 6-13 frames/s).
 */

#ifndef CSI_FILTER_PURE_H
#define CSI_FILTER_PURE_H

#include <stdbool.h>
#include <stdint.h>

#define CSI_MAC_LEN 6

/** Filter mode resolved from NVS. */
typedef enum {
    CSI_FILTER_AUTO_AP = 0,   /**< No NVS value: filter to the connected AP's BSSID. */
    CSI_FILTER_FIXED_MAC = 1, /**< NVS filter_mac holds a specific transmitter MAC. */
    CSI_FILTER_DISABLED = 2,  /**< NVS filter_mac = FF:FF:FF:FF:FF:FF ("off"). */
} csi_filter_mode_t;

/** True when all CSI_MAC_LEN bytes are zero. */
bool csi_mac_is_zero(const uint8_t *mac);

/** True when all CSI_MAC_LEN bytes are 0xFF (the provisioning "off" marker). */
bool csi_mac_is_broadcast(const uint8_t *mac);

/**
 * Decide whether a frame from `src` passes the filter.
 * A NULL or all-zero `filter` means "no filter" (accept everything).
 * With an active filter, a NULL `src` is rejected.
 */
bool csi_mac_filter_accept(const uint8_t *src, const uint8_t *filter);

/** Classify an NVS filter_mac blob (NULL / wrong length / all-zero = AUTO_AP). */
csi_filter_mode_t csi_filter_mode_from_nvs(const uint8_t *blob, uint32_t blob_len);

#endif /* CSI_FILTER_PURE_H */
