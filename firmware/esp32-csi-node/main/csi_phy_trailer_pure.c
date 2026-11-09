/**
 * @file csi_phy_trailer_pure.c
 * @brief PS-FIX-36 extended PHY trailer pack/unpack (pure C, host-testable). See csi_phy_trailer_pure.h.
 */

#include "csi_phy_trailer_pure.h"

#include <string.h>

uint8_t csi_phy_trailer_checksum(const uint8_t *trailer)
{
    uint8_t x = 0;
    for (size_t i = 4; i <= 14; i++) {
        x ^= trailer[i];
    }
    return x;
}

size_t csi_phy_trailer_pack(const csi_phy_fields_t *f, uint8_t *out, size_t out_len)
{
    if (f == NULL || out == NULL || out_len < CSI_PHY_TRAILER_SIZE) {
        return 0;
    }

    uint8_t t[CSI_PHY_TRAILER_SIZE];
    const uint32_t magic = CSI_PHY_TRAILER_MAGIC;
    t[0] = (uint8_t)(magic & 0xFFu);
    t[1] = (uint8_t)((magic >> 8) & 0xFFu);
    t[2] = (uint8_t)((magic >> 16) & 0xFFu);
    t[3] = (uint8_t)((magic >> 24) & 0xFFu);

    t[4] = (uint8_t)((f->sig_mode & 0x03u) | ((f->cwb & 0x01u) << 2) | ((f->aggregation & 0x01u) << 3) |
                     ((f->stbc & 0x03u) << 4) | ((f->sgi & 0x01u) << 6) | ((f->fec_coding & 0x01u) << 7));
    t[5] = (uint8_t)((f->mcs & 0x7Fu) | ((f->first_word_invalid & 0x01u) << 7));
    t[6] = f->ampdu_cnt;
    t[7] = (uint8_t)((f->rate & 0x1Fu) | ((f->secondary_channel & 0x03u) << 5) | ((f->hdr_valid & 0x01u) << 7));
    t[8] = (f->hdr_valid & 0x01u) ? f->fc0 : 0u;
    t[9] = (f->hdr_valid & 0x01u) ? f->fc1 : 0u;
    t[10] = (uint8_t)(f->rx_seq & 0xFFu);
    t[11] = (uint8_t)((f->rx_seq >> 8) & 0xFFu);
    t[12] = f->mac_low3[0];
    t[13] = f->mac_low3[1];
    t[14] = f->mac_low3[2];
    t[15] = csi_phy_trailer_checksum(t);

    memcpy(out, t, CSI_PHY_TRAILER_SIZE);
    return CSI_PHY_TRAILER_SIZE;
}

int csi_phy_trailer_unpack(const uint8_t *in, size_t len, csi_phy_fields_t *f)
{
    if (in == NULL || f == NULL || len < CSI_PHY_TRAILER_SIZE) {
        return 0;
    }
    const uint32_t magic = (uint32_t)in[0] | ((uint32_t)in[1] << 8) | ((uint32_t)in[2] << 16) | ((uint32_t)in[3] << 24);
    if (magic != CSI_PHY_TRAILER_MAGIC) {
        return 0;
    }
    if (csi_phy_trailer_checksum(in) != in[15]) {
        return 0;
    }

    csi_phy_fields_t r;
    memset(&r, 0, sizeof(r));
    r.sig_mode = (uint8_t)(in[4] & 0x03u);
    r.cwb = (uint8_t)((in[4] >> 2) & 0x01u);
    r.aggregation = (uint8_t)((in[4] >> 3) & 0x01u);
    r.stbc = (uint8_t)((in[4] >> 4) & 0x03u);
    r.sgi = (uint8_t)((in[4] >> 6) & 0x01u);
    r.fec_coding = (uint8_t)((in[4] >> 7) & 0x01u);
    r.mcs = (uint8_t)(in[5] & 0x7Fu);
    r.first_word_invalid = (uint8_t)((in[5] >> 7) & 0x01u);
    r.ampdu_cnt = in[6];
    r.rate = (uint8_t)(in[7] & 0x1Fu);
    r.secondary_channel = (uint8_t)((in[7] >> 5) & 0x03u);
    r.hdr_valid = (uint8_t)((in[7] >> 7) & 0x01u);
    r.fc0 = in[8];
    r.fc1 = in[9];
    r.rx_seq = (uint16_t)((uint16_t)in[10] | ((uint16_t)in[11] << 8));
    r.mac_low3[0] = in[12];
    r.mac_low3[1] = in[13];
    r.mac_low3[2] = in[14];
    *f = r;
    return 1;
}
