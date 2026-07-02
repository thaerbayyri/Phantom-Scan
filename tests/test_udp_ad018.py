import struct
from pathlib import Path

from phantom.protocol import (
    CSI_HEADER_SIZE,
    CSI_MAGIC,
    HEARTBEAT_MAGIC,
    SCHEMA_VERSION,
    CsiFrameV1,
    HeartbeatV1,
    InvalidPacket,
    parse_udp_packet,
)


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> bytes:
    return bytes.fromhex((FIXTURES / name).read_text(encoding="utf-8").strip())


def build_csi_frame(
    *,
    node_id: int = 1,
    seq: int = 7,
    n_antennas: int = 1,
    n_subcarriers: int = 4,
    freq_mhz: int = 2412,
    rssi_dbm: int = -55,
    noise_dbm: int = -90,
    channel: int = 1,
    device_ts_us: int = 123456789,
    device_ts_ms: int = 123456,
) -> bytes:
    iq = bytes([1, 2, 3, 4, 5, 6, 7, 8])
    return struct.pack(
        "<IBBBHIIbbBQI",
        CSI_MAGIC,
        SCHEMA_VERSION,
        node_id,
        n_antennas,
        n_subcarriers,
        freq_mhz,
        seq,
        rssi_dbm,
        noise_dbm,
        channel,
        device_ts_us,
        device_ts_ms,
    ) + iq


def build_heartbeat(
    *,
    node_id: int = 1,
    seq: int = 11,
    device_ts_ms: int = 987654,
) -> bytes:
    return struct.pack(
        "<IBBBBIIIIIQI",
        HEARTBEAT_MAGIC,
        SCHEMA_VERSION,
        node_id,
        1,
        0,
        seq,
        device_ts_ms,
        2,
        8,
        3,
        1,
        42,
    )


def test_parse_valid_csi_frame():
    parsed = parse_udp_packet(build_csi_frame(), ("127.0.0.1", 5005), 999)
    assert isinstance(parsed, CsiFrameV1)
    assert parsed.node_id == 1
    assert parsed.seq == 7
    assert parsed.device_ts_valid is True
    assert parsed.host_rx_ns == 999
    assert len(parsed.iq_bytes) == 8


def test_parse_committed_adr018_fixture_field_parity():
    parsed = parse_udp_packet(load_fixture("adr018_frame.hex"), ("127.0.0.1", 5005), 999)
    assert isinstance(parsed, CsiFrameV1)
    assert parsed.schema_version == 1
    assert parsed.node_id == 2
    assert parsed.n_antennas == 1
    assert parsed.n_subcarriers == 4
    assert parsed.freq_mhz == 2412
    assert parsed.seq == 17
    assert parsed.rssi_dbm == -55
    assert parsed.noise_dbm == -90
    assert parsed.channel == 1
    assert parsed.device_ts_us == 123456789
    assert parsed.device_ts_ms == 123456
    assert parsed.iq_bytes == bytes([1, 2, 3, 4, 5, 6, 7, 8])


def test_parse_valid_heartbeat():
    parsed = parse_udp_packet(build_heartbeat(), ("127.0.0.1", 5005), 111)
    assert isinstance(parsed, HeartbeatV1)
    assert parsed.node_id == 1
    assert parsed.seq == 11
    assert parsed.callback_drops == 2


def test_parse_committed_heartbeat_fixture_is_not_csi():
    parsed = parse_udp_packet(load_fixture("heartbeat_frame.hex"), ("127.0.0.1", 5005), 111)
    assert isinstance(parsed, HeartbeatV1)
    assert not isinstance(parsed, CsiFrameV1)
    assert parsed.node_id == 2
    assert parsed.seq == 18


def test_reject_bad_magic():
    parsed = parse_udp_packet(b"\x00\x00\x00\x00", ("127.0.0.1", 5005), 222)
    assert isinstance(parsed, InvalidPacket)
    assert "unknown_magic" in parsed.reason


def test_reject_truncated_csi():
    parsed = parse_udp_packet(build_csi_frame()[: CSI_HEADER_SIZE - 1], ("127.0.0.1", 5005), 333)
    assert isinstance(parsed, InvalidPacket)
    assert parsed.reason == "truncated_csi_header"
