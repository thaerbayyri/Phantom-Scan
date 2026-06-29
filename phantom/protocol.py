from __future__ import annotations

from dataclasses import asdict, dataclass
import enum
import math
import socket
import struct
import time
from typing import Any


CSI_MAGIC = 0xC5110001
HEARTBEAT_MAGIC = 0xC51100A1
SCHEMA_VERSION = 1
CSI_HEADER_SIZE = 32
HEARTBEAT_SIZE = 40
MAX_UDP_PAYLOAD = 4096


class PacketKind(str, enum.Enum):
    CSI = "csi_frame"
    HEARTBEAT = "heartbeat"


def _now_host_rx_ns() -> int:
    return time.time_ns()


@dataclass(slots=True)
class PacketEnvelope:
    host_rx_ns: int
    remote_addr: str
    remote_port: int
    payload_size: int


@dataclass(slots=True)
class CsiFrameV1:
    schema_version: int
    node_id: int
    seq: int
    device_ts_us: int | None
    device_ts_ms: int | None
    device_ts_valid: bool
    host_rx_ns: int
    rssi_dbm: int
    noise_dbm: int
    channel: int
    freq_mhz: int
    n_antennas: int
    n_subcarriers: int
    iq_bytes: bytes
    source_ip: str = ""
    source_port: int = 0

    @property
    def authoritative_timestamp_ns(self) -> int:
        if self.device_ts_valid:
            if self.device_ts_us is not None:
                return self.device_ts_us * 1000
            if self.device_ts_ms is not None:
                return self.device_ts_ms * 1_000_000
        return self.host_rx_ns

    def to_record(self) -> dict[str, Any]:
        return {
            "record_type": PacketKind.CSI.value,
            "schema_version": self.schema_version,
            "node_id": self.node_id,
            "seq": self.seq,
            "device_ts_us": self.device_ts_us,
            "device_ts_ms": self.device_ts_ms,
            "device_ts_valid": self.device_ts_valid,
            "host_rx_ns": self.host_rx_ns,
            "rssi_dbm": self.rssi_dbm,
            "noise_dbm": self.noise_dbm,
            "channel": self.channel,
            "freq_mhz": self.freq_mhz,
            "n_antennas": self.n_antennas,
            "n_subcarriers": self.n_subcarriers,
            "iq_hex": self.iq_bytes.hex(),
            "source_ip": self.source_ip,
            "source_port": self.source_port,
        }


@dataclass(slots=True)
class HeartbeatV1:
    schema_version: int
    node_id: int
    seq: int
    device_ts_ms: int
    host_rx_ns: int
    wifi_connected: bool
    callback_drops: int
    queue_high_watermark: int
    send_failures: int
    reconnect_count: int
    firmware_build_id: int
    source_ip: str = ""
    source_port: int = 0

    def to_record(self) -> dict[str, Any]:
        return {
            "record_type": PacketKind.HEARTBEAT.value,
            "schema_version": self.schema_version,
            "node_id": self.node_id,
            "seq": self.seq,
            "device_ts_ms": self.device_ts_ms,
            "host_rx_ns": self.host_rx_ns,
            "wifi_connected": self.wifi_connected,
            "callback_drops": self.callback_drops,
            "queue_high_watermark": self.queue_high_watermark,
            "send_failures": self.send_failures,
            "reconnect_count": self.reconnect_count,
            "firmware_build_id": self.firmware_build_id,
            "source_ip": self.source_ip,
            "source_port": self.source_port,
        }


@dataclass(slots=True)
class InvalidPacket:
    reason: str
    host_rx_ns: int
    source_ip: str
    source_port: int
    payload_size: int


def _freq_to_channel(freq_mhz: int) -> int:
    if freq_mhz == 2484:
        return 14
    if 2412 <= freq_mhz <= 2472:
        return (freq_mhz - 2412) // 5 + 1
    if 5000 <= freq_mhz <= 5885:
        return (freq_mhz - 5000) // 5
    return 0


def _device_ts_valid_us(value: int | None) -> bool:
    return value is not None and value > 0 and value < 10**16


def _device_ts_valid_ms(value: int | None) -> bool:
    return value is not None and value > 0 and value < 10**13


def parse_udp_packet(
    data: bytes,
    remote_addr: tuple[str, int] = ("", 0),
    host_rx_ns: int | None = None,
) -> CsiFrameV1 | HeartbeatV1 | InvalidPacket:
    host_rx_ns = host_rx_ns or _now_host_rx_ns()
    source_ip, source_port = remote_addr

    if len(data) < 4:
        return InvalidPacket("truncated_magic", host_rx_ns, source_ip, source_port, len(data))

    magic = struct.unpack_from("<I", data, 0)[0]

    if magic == CSI_MAGIC:
        return parse_csi_frame(data, source_ip, source_port, host_rx_ns)
    if magic == HEARTBEAT_MAGIC:
        return parse_heartbeat(data, source_ip, source_port, host_rx_ns)

    return InvalidPacket(
        f"unknown_magic_0x{magic:08x}", host_rx_ns, source_ip, source_port, len(data)
    )


def parse_csi_frame(data: bytes, source_ip: str = "", source_port: int = 0, host_rx_ns: int | None = None) -> CsiFrameV1 | InvalidPacket:
    host_rx_ns = host_rx_ns or _now_host_rx_ns()
    if len(data) < CSI_HEADER_SIZE:
        return InvalidPacket("truncated_csi_header", host_rx_ns, source_ip, source_port, len(data))

    (
        magic,
        schema_version,
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
    ) = struct.unpack_from("<IBBBHIIbbBQI", data, 0)

    if magic != CSI_MAGIC:
        return InvalidPacket("invalid_csi_magic", host_rx_ns, source_ip, source_port, len(data))
    if schema_version != SCHEMA_VERSION:
        return InvalidPacket(f"unsupported_csi_schema_v{schema_version}", host_rx_ns, source_ip, source_port, len(data))
    if n_antennas <= 0 or n_subcarriers <= 0:
        return InvalidPacket("invalid_csi_dimensions", host_rx_ns, source_ip, source_port, len(data))

    iq_bytes = data[CSI_HEADER_SIZE:]
    expected_iq_bytes = n_antennas * n_subcarriers * 2
    if len(iq_bytes) != expected_iq_bytes:
        return InvalidPacket("csi_payload_length_mismatch", host_rx_ns, source_ip, source_port, len(data))

    if channel == 0:
        channel = _freq_to_channel(freq_mhz)

    valid_us = _device_ts_valid_us(device_ts_us)
    valid_ms = _device_ts_valid_ms(device_ts_ms)

    return CsiFrameV1(
        schema_version=schema_version,
        node_id=node_id,
        seq=seq,
        device_ts_us=device_ts_us if valid_us else None,
        device_ts_ms=device_ts_ms if valid_ms else None,
        device_ts_valid=bool(valid_us or valid_ms),
        host_rx_ns=host_rx_ns,
        rssi_dbm=rssi_dbm,
        noise_dbm=noise_dbm,
        channel=channel,
        freq_mhz=freq_mhz,
        n_antennas=n_antennas,
        n_subcarriers=n_subcarriers,
        iq_bytes=iq_bytes,
        source_ip=source_ip,
        source_port=source_port,
    )


def parse_heartbeat(data: bytes, source_ip: str = "", source_port: int = 0, host_rx_ns: int | None = None) -> HeartbeatV1 | InvalidPacket:
    host_rx_ns = host_rx_ns or _now_host_rx_ns()
    if len(data) < HEARTBEAT_SIZE:
        return InvalidPacket("truncated_heartbeat", host_rx_ns, source_ip, source_port, len(data))

    (
        magic,
        schema_version,
        node_id,
        wifi_connected,
        _reserved0,
        seq,
        device_ts_ms,
        callback_drops,
        queue_high_watermark,
        send_failures,
        reconnect_count,
        firmware_build_id,
    ) = struct.unpack_from("<IBBBBIIIIIQI", data, 0)

    if magic != HEARTBEAT_MAGIC:
        return InvalidPacket("invalid_heartbeat_magic", host_rx_ns, source_ip, source_port, len(data))
    if schema_version != SCHEMA_VERSION:
        return InvalidPacket(f"unsupported_heartbeat_schema_v{schema_version}", host_rx_ns, source_ip, source_port, len(data))

    return HeartbeatV1(
        schema_version=schema_version,
        node_id=node_id,
        seq=seq,
        device_ts_ms=device_ts_ms,
        host_rx_ns=host_rx_ns,
        wifi_connected=bool(wifi_connected),
        callback_drops=callback_drops,
        queue_high_watermark=queue_high_watermark,
        send_failures=send_failures,
        reconnect_count=reconnect_count,
        firmware_build_id=firmware_build_id,
        source_ip=source_ip,
        source_port=source_port,
    )


def iq_pairs_from_bytes(iq_bytes: bytes) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    for i in range(0, len(iq_bytes), 2):
        i_val, q_val = struct.unpack_from("<bb", iq_bytes, i)
        pairs.append((i_val, q_val))
    return pairs


def build_record_metadata(host: str = "", port: int = 0) -> dict[str, Any]:
    return {
        "runtime_host": host or socket.gethostname(),
        "runtime_port": port,
        "schema_version": SCHEMA_VERSION,
    }
