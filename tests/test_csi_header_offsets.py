"""PS-FIX-08: audit the ADR-018 header offsets (esp. RSSI) with frames built BY HAND from the firmware layout
(firmware/esp32-csi-node/main/csi_collector.c, csi_serialize_frame), independent of either parser. The same hex vector is pinned in
server/lib/phy-guard.test.ts, so the TS and Python parsers are checked against identical bytes."""
from __future__ import annotations

import pytest

from phantom.protocol import CsiFrameV1, parse_csi_frame

# magic@0 schema@4 node@5 ant@6 nsub@7(u16) freq@9(u32) seq@13(u32) rssi@17(i8) noise@18(i8) chan@19 ts_us@20(u64) ts_ms@28(u32) iq@32
VECTOR_HEX = "010011c501020104008509000004030201d1a4060200000001000000443322110102030405060708"


def build(node: int = 2, n_sub: int = 4, freq: int = 2437, seq: int = 0x01020304, rssi: int = -47, noise: int = -92, channel: int = 6) -> bytes:
    buf = bytearray(32 + 2 * n_sub)
    buf[0:4] = (0xC5110001).to_bytes(4, "little")
    buf[4], buf[5], buf[6] = 1, node, 1
    buf[7:9] = n_sub.to_bytes(2, "little")
    buf[9:13] = freq.to_bytes(4, "little")
    buf[13:17] = seq.to_bytes(4, "little")
    buf[17] = rssi & 0xFF
    buf[18] = noise & 0xFF
    buf[19] = channel
    buf[20:28] = (0x0000000100000002).to_bytes(8, "little")
    buf[28:32] = (0x11223344).to_bytes(4, "little")
    buf[32:] = bytes(range(1, 2 * n_sub + 1))
    return bytes(buf)


def test_the_hand_built_frame_is_the_pinned_vector() -> None:
    assert build().hex() == VECTOR_HEX


def test_every_header_field_is_read_from_the_firmware_offset() -> None:
    f = parse_csi_frame(bytes.fromhex(VECTOR_HEX), "10.0.0.2", 5005)
    assert isinstance(f, CsiFrameV1)
    assert (f.schema_version, f.node_id, f.n_antennas, f.n_subcarriers) == (1, 2, 1, 4)
    assert (f.freq_mhz, f.seq, f.rssi_dbm, f.noise_dbm, f.channel) == (2437, 0x01020304, -47, -92, 6)
    assert (f.device_ts_us, f.device_ts_ms) == (0x0000000100000002, 0x11223344)
    assert f.iq_bytes == bytes(range(1, 9))


@pytest.mark.parametrize("rssi", [-128, -100, -47, -1, 0, 1, 127])
def test_rssi_is_a_signed_byte_at_offset_17_including_the_extremes(rssi: int) -> None:
    assert parse_csi_frame(build(rssi=rssi), "10.0.0.2", 5005).rssi_dbm == rssi


def test_a_parser_reading_the_neighbouring_bytes_would_be_caught() -> None:
    raw = bytearray(build(rssi=-47, noise=-92))
    raw[16] = 0x55                                          # byte before RSSI (seq high byte): must not leak into RSSI
    raw[19] = 11                                            # channel changes; noise and RSSI must not
    f = parse_csi_frame(bytes(raw), "10.0.0.2", 5005)
    assert (f.rssi_dbm, f.noise_dbm, f.channel) == (-47, -92, 11)


def test_the_frequency_to_channel_pairing_matches_the_firmware_derivation() -> None:
    for channel, freq in ((1, 2412), (6, 2437), (11, 2462), (14, 2484)):
        assert parse_csi_frame(build(freq=freq, channel=channel), "10.0.0.2", 5005).freq_mhz == freq
