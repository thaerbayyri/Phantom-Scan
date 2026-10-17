/**
 * @file csi_filter_pure.c
 * @brief Pure source-MAC filter helpers — no ESP-IDF dependencies, so the
 *        logic is unit-tested on the host (see test/test_csi_filter_pure.c).
 */

#include "csi_filter_pure.h"

#include <stddef.h>
#include <string.h>

static bool mac_all_equal(const uint8_t *mac, uint8_t value)
{
    if (mac == NULL) {
        return false;
    }
    for (int i = 0; i < CSI_MAC_LEN; i++) {
        if (mac[i] != value) {
            return false;
        }
    }
    return true;
}

bool csi_mac_is_zero(const uint8_t *mac)
{
    return mac_all_equal(mac, 0x00);
}

bool csi_mac_is_broadcast(const uint8_t *mac)
{
    return mac_all_equal(mac, 0xFF);
}

bool csi_mac_filter_accept(const uint8_t *src, const uint8_t *filter)
{
    if (filter == NULL || csi_mac_is_zero(filter)) {
        return true; /* no filter configured */
    }
    if (src == NULL) {
        return false;
    }
    return memcmp(src, filter, CSI_MAC_LEN) == 0;
}

csi_filter_mode_t csi_filter_mode_from_nvs(const uint8_t *blob, uint32_t blob_len)
{
    if (blob == NULL || blob_len != CSI_MAC_LEN || csi_mac_is_zero(blob)) {
        return CSI_FILTER_AUTO_AP;
    }
    if (csi_mac_is_broadcast(blob)) {
        return CSI_FILTER_DISABLED;
    }
    return CSI_FILTER_FIXED_MAC;
}
