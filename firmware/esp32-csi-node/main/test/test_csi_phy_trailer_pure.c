/**
 * @file test_csi_phy_trailer_pure.c
 * @brief Host unit tests for the PS-FIX-36 extended PHY trailer (csi_phy_trailer_pure.c).
 *
 * Build & run (from this directory; MSYS2 gcc on this machine: C:\msys64\ucrt64\bin\gcc.exe):
 *   gcc -std=c99 -O2 -Wall -Wextra -I.. test_csi_phy_trailer_pure.c ../csi_phy_trailer_pure.c -o test_csi_phy_trailer_pure
 *   ./test_csi_phy_trailer_pure
 *
 * The golden hex strings below are the same ones in tests/fixtures/phy_trailer_golden.json; a server test
 * (server/lib/csi-phy-trailer.test.ts) reads this file and fails if they drift apart.
 */

#include "../csi_phy_trailer_pure.h"

#include <stdio.h>
#include <string.h>

static int g_failures = 0;
#define CHECK(cond) do { \
    if (!(cond)) { \
        fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
        g_failures++; \
    } \
} while (0)

/* GOLDEN_HEX_BEGIN */
#define GOLDEN_HT_AMPDU_QOS   "504858310987038088021b0ac4112261"
#define GOLDEN_HT40_STBC_SGI  "50485831d54c00a008420100aabbccaf"
#define GOLDEN_ZERO           "50485831000000000000000000000000"
/* GOLDEN_HEX_END */

static void to_hex(const uint8_t *b, size_t n, char *out)
{
    static const char H[] = "0123456789abcdef";
    for (size_t i = 0; i < n; i++) {
        out[2 * i] = H[b[i] >> 4];
        out[2 * i + 1] = H[b[i] & 0x0F];
    }
    out[2 * n] = '\0';
}

static csi_phy_fields_t ht_ampdu_qos(void)
{
    csi_phy_fields_t f;
    memset(&f, 0, sizeof(f));
    f.sig_mode = 1; f.aggregation = 1; f.mcs = 7; f.first_word_invalid = 1; f.ampdu_cnt = 3;
    f.hdr_valid = 1; f.fc0 = 0x88; f.fc1 = 0x02; f.rx_seq = 0x0A1B;
    f.mac_low3[0] = 0xC4; f.mac_low3[1] = 0x11; f.mac_low3[2] = 0x22;
    return f;
}

static csi_phy_fields_t ht40_stbc_sgi(void)
{
    csi_phy_fields_t f;
    memset(&f, 0, sizeof(f));
    f.sig_mode = 1; f.cwb = 1; f.stbc = 1; f.sgi = 1; f.fec_coding = 1; f.mcs = 0x4C;
    f.secondary_channel = 1; f.hdr_valid = 1; f.fc0 = 0x08; f.fc1 = 0x42; f.rx_seq = 1;
    f.mac_low3[0] = 0xAA; f.mac_low3[1] = 0xBB; f.mac_low3[2] = 0xCC;
    return f;
}

static void test_golden_frames(void)
{
    uint8_t out[CSI_PHY_TRAILER_SIZE];
    char hex[2 * CSI_PHY_TRAILER_SIZE + 1];
    csi_phy_fields_t a = ht_ampdu_qos();
    CHECK(csi_phy_trailer_pack(&a, out, sizeof(out)) == CSI_PHY_TRAILER_SIZE);
    to_hex(out, sizeof(out), hex);
    CHECK(strcmp(hex, GOLDEN_HT_AMPDU_QOS) == 0);

    csi_phy_fields_t b = ht40_stbc_sgi();
    CHECK(csi_phy_trailer_pack(&b, out, sizeof(out)) == CSI_PHY_TRAILER_SIZE);
    to_hex(out, sizeof(out), hex);
    CHECK(strcmp(hex, GOLDEN_HT40_STBC_SGI) == 0);

    csi_phy_fields_t z;
    memset(&z, 0, sizeof(z));
    CHECK(csi_phy_trailer_pack(&z, out, sizeof(out)) == CSI_PHY_TRAILER_SIZE);
    to_hex(out, sizeof(out), hex);
    CHECK(strcmp(hex, GOLDEN_ZERO) == 0);
}

static void test_round_trip(void)
{
    uint8_t out[CSI_PHY_TRAILER_SIZE];
    csi_phy_fields_t in = ht40_stbc_sgi();
    csi_phy_fields_t back;
    CHECK(csi_phy_trailer_pack(&in, out, sizeof(out)) == CSI_PHY_TRAILER_SIZE);
    CHECK(csi_phy_trailer_unpack(out, sizeof(out), &back) == 1);
    CHECK(memcmp(&in, &back, sizeof(in)) == 0);
}

static void test_inputs_are_masked_to_field_widths(void)
{
    uint8_t out[CSI_PHY_TRAILER_SIZE];
    csi_phy_fields_t f;
    csi_phy_fields_t back;
    memset(&f, 0xFF, sizeof(f));   /* every field all-ones, including out-of-range bits */
    f.hdr_valid = 1;
    CHECK(csi_phy_trailer_pack(&f, out, sizeof(out)) == CSI_PHY_TRAILER_SIZE);
    CHECK(csi_phy_trailer_unpack(out, sizeof(out), &back) == 1);
    CHECK(back.sig_mode == 3 && back.cwb == 1 && back.aggregation == 1 && back.stbc == 3);
    CHECK(back.sgi == 1 && back.fec_coding == 1 && back.mcs == 0x7F && back.first_word_invalid == 1);
    CHECK(back.rate == 0x1F && back.secondary_channel == 3 && back.hdr_valid == 1);
}

static void test_hdr_not_valid_zeroes_frame_control(void)
{
    uint8_t out[CSI_PHY_TRAILER_SIZE];
    csi_phy_fields_t f = ht_ampdu_qos();
    f.hdr_valid = 0;               /* fc0/fc1 hold stale bytes that must not leak onto the wire */
    CHECK(csi_phy_trailer_pack(&f, out, sizeof(out)) == CSI_PHY_TRAILER_SIZE);
    CHECK(out[8] == 0 && out[9] == 0);
    CHECK((out[7] & 0x80u) == 0);
}

static void test_rejects_bad_input(void)
{
    uint8_t out[CSI_PHY_TRAILER_SIZE];
    uint8_t before[CSI_PHY_TRAILER_SIZE];
    csi_phy_fields_t f = ht_ampdu_qos();
    csi_phy_fields_t back;
    memset(out, 0xA5, sizeof(out));
    memcpy(before, out, sizeof(out));
    CHECK(csi_phy_trailer_pack(NULL, out, sizeof(out)) == 0);
    CHECK(csi_phy_trailer_pack(&f, NULL, sizeof(out)) == 0);
    CHECK(csi_phy_trailer_pack(&f, out, CSI_PHY_TRAILER_SIZE - 1u) == 0);
    CHECK(memcmp(out, before, sizeof(out)) == 0);   /* a refused pack leaves the buffer untouched */

    CHECK(csi_phy_trailer_pack(&f, out, sizeof(out)) == CSI_PHY_TRAILER_SIZE);
    CHECK(csi_phy_trailer_unpack(NULL, sizeof(out), &back) == 0);
    CHECK(csi_phy_trailer_unpack(out, sizeof(out), NULL) == 0);
    CHECK(csi_phy_trailer_unpack(out, CSI_PHY_TRAILER_SIZE - 1u, &back) == 0);

    uint8_t bad[CSI_PHY_TRAILER_SIZE];
    memcpy(bad, out, sizeof(bad));
    bad[0] ^= 0x01u;                                 /* wrong magic */
    CHECK(csi_phy_trailer_unpack(bad, sizeof(bad), &back) == 0);
    memcpy(bad, out, sizeof(bad));
    bad[6] ^= 0x10u;                                 /* corrupted field, stale checksum */
    CHECK(csi_phy_trailer_unpack(bad, sizeof(bad), &back) == 0);
}

static void test_trailer_is_appended_after_iq_without_touching_it(void)
{
    uint8_t frame[32 + 128 + CSI_PHY_TRAILER_SIZE];
    uint8_t copy[32 + 128];
    csi_phy_fields_t f = ht_ampdu_qos();
    csi_phy_fields_t back;
    for (size_t i = 0; i < 32 + 128; i++) {
        frame[i] = (uint8_t)(i * 5u + 1u);
    }
    memcpy(copy, frame, sizeof(copy));
    CHECK(csi_phy_trailer_pack(&f, frame + 32 + 128, CSI_PHY_TRAILER_SIZE) == CSI_PHY_TRAILER_SIZE);
    CHECK(memcmp(frame, copy, sizeof(copy)) == 0);   /* header and I/Q bytes are unchanged */
    CHECK(csi_phy_trailer_unpack(frame + 32 + 128, CSI_PHY_TRAILER_SIZE, &back) == 1);
    CHECK(back.rx_seq == 0x0A1B);
}

int main(void)
{
    test_golden_frames();
    test_round_trip();
    test_inputs_are_masked_to_field_widths();
    test_hdr_not_valid_zeroes_frame_control();
    test_rejects_bad_input();
    test_trailer_is_appended_after_iq_without_touching_it();
    if (g_failures != 0) {
        fprintf(stderr, "test_csi_phy_trailer_pure: %d failure(s)\n", g_failures);
        return 1;
    }
    printf("test_csi_phy_trailer_pure: all checks passed\n");
    return 0;
}
