/**
 * @file csi_phy_trailer_pure.h
 * @brief PS-FIX-36 extended: a 16-byte PHY trailer appended AFTER the I/Q payload of an ADR-018 v1 CSI datagram.
 *
 * Pure C and free of ESP-IDF includes so it is unit-tested on the host (test/test_csi_phy_trailer_pure.c).
 * NOT wired into csi_collector.c, NOT listed in CMakeLists.txt, never flashed: integration is a separate,
 * approved step (design: reports/fix-2026-11/15-PS-FIX-36-extended-design.md).
 *
 * Why a trailer and not new header bytes: all 32 bytes of the ADR-018 v1 header are in use. The TypeScript ingest
 * accepts a datagram longer than 32 + n_antennas * n_subcarriers * 2, so an appended trailer leaves it working
 * unchanged (proven by server/lib/csi-phy-trailer.test.ts). NOT every reader: the Python parser
 * phantom/protocol.py parse_csi_frame requires an EXACT length and rejects a trailer frame (measured 2026-11-09:
 * csi_payload_length_mismatch); its callers scripts/ai_inference.py and scripts/record_dataset.py must be changed
 * before any firmware sends the trailer. At integration also assert an even I/Q length: the trailer is only
 * recognised at 32 + 2 * n_subcarriers + 16, and the output-buffer size check must include the trailer.
 * secondary_channel is 4 bits in the IDF struct but 2 bits on the wire (values 0..2 fit).
 *
 * Wire layout (little-endian, 16 bytes):
 *   [0..3]   magic 0x31584850 ("PHX1": bytes 50 48 58 31)
 *   [4]      sig_mode[1:0] | cwb<<2 | aggregation<<3 | stbc[1:0]<<4 | sgi<<6 | fec_coding<<7
 *   [5]      mcs[6:0] | first_word_invalid<<7
 *   [6]      ampdu_cnt
 *   [7]      rate[4:0] | secondary_channel[1:0]<<5 | hdr_valid<<7
 *   [8]      802.11 frame-control byte 0 (type/subtype), 0 when hdr_valid is 0
 *   [9]      802.11 frame-control byte 1 (flags), 0 when hdr_valid is 0
 *   [10..11] rx_seq (u16, from wifi_csi_info_t.rx_seq)
 *   [12..14] transmitter: last three bytes of wifi_csi_info_t.mac
 *   [15]     XOR of bytes 4..14
 */
#ifndef CSI_PHY_TRAILER_PURE_H
#define CSI_PHY_TRAILER_PURE_H

#include <stddef.h>
#include <stdint.h>

#define CSI_PHY_TRAILER_MAGIC 0x31584850u
#define CSI_PHY_TRAILER_SIZE  16u

/** Plain fields, filled by the caller from wifi_csi_info_t (rx_ctrl, mac, hdr, rx_seq). */
typedef struct {
    uint8_t  sig_mode;            /* rx_ctrl.sig_mode: 0 non-HT, 1 HT, 3 VHT (2 bits) */
    uint8_t  cwb;                 /* rx_ctrl.cwb: 0 = 20 MHz, 1 = 40 MHz (1 bit) */
    uint8_t  aggregation;         /* rx_ctrl.aggregation: 1 = AMPDU (1 bit) */
    uint8_t  stbc;                /* rx_ctrl.stbc (2 bits) */
    uint8_t  sgi;                 /* rx_ctrl.sgi (1 bit) */
    uint8_t  fec_coding;          /* rx_ctrl.fec_coding (1 bit) */
    uint8_t  mcs;                 /* rx_ctrl.mcs (7 bits) */
    uint8_t  first_word_invalid;  /* wifi_csi_info_t.first_word_invalid (1 bit) */
    uint8_t  ampdu_cnt;           /* rx_ctrl.ampdu_cnt (8 bits) */
    uint8_t  rate;                /* rx_ctrl.rate (5 bits; valid for non-HT only) */
    uint8_t  secondary_channel;   /* rx_ctrl.secondary_channel (2 bits) */
    uint8_t  hdr_valid;           /* 1 when hdr was non-NULL and long enough to read two frame-control bytes */
    uint8_t  fc0;                 /* hdr[0] */
    uint8_t  fc1;                 /* hdr[1] */
    uint16_t rx_seq;              /* wifi_csi_info_t.rx_seq */
    uint8_t  mac_low3[3];         /* wifi_csi_info_t.mac[3..5] */
} csi_phy_fields_t;

/** XOR of trailer bytes 4..14 (the value stored in byte 15). */
uint8_t csi_phy_trailer_checksum(const uint8_t *trailer);

/**
 * Pack the fields into out[0..15]. Inputs are masked to their field widths. When hdr_valid is 0 the two
 * frame-control bytes are written as 0 so that the output is a function of the meaningful fields only.
 * @return CSI_PHY_TRAILER_SIZE, or 0 when f or out is NULL or out_len is too small (out is left untouched).
 */
size_t csi_phy_trailer_pack(const csi_phy_fields_t *f, uint8_t *out, size_t out_len);

/**
 * Unpack and validate (magic and checksum) the first 16 bytes of in.
 * @return 1 and fill *f on success; 0 when in or f is NULL, len < 16, the magic is wrong or the checksum fails.
 */
int csi_phy_trailer_unpack(const uint8_t *in, size_t len, csi_phy_fields_t *f);

#endif /* CSI_PHY_TRAILER_PURE_H */
