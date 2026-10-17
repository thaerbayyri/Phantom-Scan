/**
 * @file test_csi_filter_pure.c
 * @brief Host unit tests for the CSI source-MAC filter (csi_filter_pure.c).
 *
 * Build & run (from this directory):
 *   gcc -std=c99 -O2 -Wall -I.. test_csi_filter_pure.c ../csi_filter_pure.c -o test_csi_filter_pure
 *   ./test_csi_filter_pure
 */

#include "../csi_filter_pure.h"

#include <stdio.h>
#include <stddef.h>

static int g_failures = 0;
#define CHECK(cond) do { \
    if (!(cond)) { \
        fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
        g_failures++; \
    } \
} while (0)

static const uint8_t AP[CSI_MAC_LEN]    = {0x24, 0x0A, 0xC4, 0x11, 0x22, 0x33};
static const uint8_t PHONE[CSI_MAC_LEN] = {0x9C, 0x2E, 0xA1, 0x44, 0x55, 0x66};
static const uint8_t ZERO[CSI_MAC_LEN]  = {0, 0, 0, 0, 0, 0};
static const uint8_t OFF[CSI_MAC_LEN]   = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

static void test_accept_only_matching_transmitter(void)
{
    CHECK(csi_mac_filter_accept(AP, AP));
    CHECK(!csi_mac_filter_accept(PHONE, AP));
}

static void test_no_filter_accepts_everything(void)
{
    CHECK(csi_mac_filter_accept(PHONE, NULL));
    CHECK(csi_mac_filter_accept(PHONE, ZERO));
    CHECK(csi_mac_filter_accept(NULL, NULL));
}

static void test_active_filter_rejects_unknown_source(void)
{
    CHECK(!csi_mac_filter_accept(NULL, AP));
}

static void test_nvs_mode_classification(void)
{
    CHECK(csi_filter_mode_from_nvs(NULL, 0) == CSI_FILTER_AUTO_AP);
    CHECK(csi_filter_mode_from_nvs(AP, 5) == CSI_FILTER_AUTO_AP); /* wrong length */
    CHECK(csi_filter_mode_from_nvs(ZERO, 6) == CSI_FILTER_AUTO_AP);
    CHECK(csi_filter_mode_from_nvs(OFF, 6) == CSI_FILTER_DISABLED);
    CHECK(csi_filter_mode_from_nvs(AP, 6) == CSI_FILTER_FIXED_MAC);
}

static void test_mac_predicates(void)
{
    CHECK(csi_mac_is_zero(ZERO));
    CHECK(!csi_mac_is_zero(AP));
    CHECK(csi_mac_is_broadcast(OFF));
    CHECK(!csi_mac_is_broadcast(AP));
    CHECK(!csi_mac_is_zero(NULL));
}

int main(void)
{
    test_accept_only_matching_transmitter();
    test_no_filter_accepts_everything();
    test_active_filter_rejects_unknown_source();
    test_nvs_mode_classification();
    test_mac_predicates();
    if (g_failures) {
        fprintf(stderr, "%d check(s) failed\n", g_failures);
        return 1;
    }
    printf("test_csi_filter_pure: all checks passed\n");
    return 0;
}
