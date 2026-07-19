from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import socket
import time
from typing import Iterator

from .protocol import CsiFrameV1, HeartbeatV1, InvalidPacket, MAX_UDP_PAYLOAD, parse_udp_packet


@dataclass(slots=True)
class NodeHealth:
    node_id: int
    last_csi_rx_ns: int | None = None
    last_heartbeat_rx_ns: int | None = None
    last_seen_monotonic_ns: int | None = None
    packet_loss_count: int = 0
    out_of_order_count: int = 0
    invalid_count: int = 0
    last_seq_csi: int | None = None
    last_seq_heartbeat: int | None = None

    def ingest_csi(self, frame: CsiFrameV1) -> None:
        self.last_csi_rx_ns = frame.host_rx_ns
        self.last_seen_monotonic_ns = time.time_ns()
        if self.last_seq_csi is not None:
            delta = frame.seq - self.last_seq_csi
            if delta < 0:
                self.out_of_order_count += 1
            elif delta > 1:
                self.packet_loss_count += delta - 1
        self.last_seq_csi = frame.seq

    def ingest_heartbeat(self, packet: HeartbeatV1) -> None:
        self.last_heartbeat_rx_ns = packet.host_rx_ns
        self.last_seen_monotonic_ns = time.time_ns()
        if self.last_seq_heartbeat is not None:
            delta = packet.seq - self.last_seq_heartbeat
            if delta < 0:
                self.out_of_order_count += 1
            elif delta > 1:
                self.packet_loss_count += delta - 1
        self.last_seq_heartbeat = packet.seq


@dataclass(slots=True)
class NodeBuffer:
    node_id: int
    csi_frames: deque[CsiFrameV1] = field(default_factory=lambda: deque(maxlen=256))
    heartbeats: deque[HeartbeatV1] = field(default_factory=lambda: deque(maxlen=64))
    health: NodeHealth = field(init=False)

    def __post_init__(self) -> None:
        self.health = NodeHealth(node_id=self.node_id)

    def add_packet(self, packet: CsiFrameV1 | HeartbeatV1 | InvalidPacket) -> None:
        if isinstance(packet, CsiFrameV1):
            self.csi_frames.append(packet)
            self.health.ingest_csi(packet)
        elif isinstance(packet, HeartbeatV1):
            self.heartbeats.append(packet)
            self.health.ingest_heartbeat(packet)
        else:
            self.health.invalid_count += 1

    def is_stale(self, now_ns: int, timeout_ns: int) -> bool:
        latest = self.health.last_seen_monotonic_ns
        return latest is None or (now_ns - latest) > timeout_ns


@dataclass(slots=True)
class SourceBindingRejection:
    node_id: int
    expected_ip: str
    expected_port: int
    actual_ip: str
    actual_port: int
    packet_kind: str
    host_rx_ns: int

    def to_record(self) -> dict[str, object]:
        return {
            "record_type": "security_event",
            "event_type": "node_source_mismatch",
            "node_id": self.node_id,
            "expected_source": {
                "ip": self.expected_ip,
                "port": self.expected_port,
            },
            "actual_source": {
                "ip": self.actual_ip,
                "port": self.actual_port,
            },
            "packet_kind": self.packet_kind,
            "host_rx_ns": self.host_rx_ns,
        }


@dataclass(slots=True)
class SourceMissingRejection:
    node_id: int
    packet_kind: str
    host_rx_ns: int

    def to_record(self) -> dict[str, object]:
        return {
            "record_type": "security_event",
            "event_type": "node_source_missing",
            "node_id": self.node_id,
            "packet_kind": self.packet_kind,
            "host_rx_ns": self.host_rx_ns,
        }


class SourcePinningGuard:
    """Binds each node id to its first observed UDP source for a session."""

    def __init__(self) -> None:
        self.bindings: dict[int, tuple[str, int]] = {}
        self.rejections: list[SourceBindingRejection | SourceMissingRejection] = []

    def check(
        self, packet: CsiFrameV1 | HeartbeatV1
    ) -> SourceBindingRejection | SourceMissingRejection | None:
        source_ip = packet.source_ip
        source_port = packet.source_port
        if not source_ip or source_port <= 0:
            rejection = SourceMissingRejection(
                node_id=packet.node_id,
                packet_kind="csi_frame" if isinstance(packet, CsiFrameV1) else "heartbeat",
                host_rx_ns=packet.host_rx_ns,
            )
            self.rejections.append(rejection)
            return rejection

        existing = self.bindings.get(packet.node_id)
        if existing is None:
            self.bindings[packet.node_id] = (source_ip, source_port)
            return None

        if existing == (source_ip, source_port):
            return None

        rejection = SourceBindingRejection(
            node_id=packet.node_id,
            expected_ip=existing[0],
            expected_port=existing[1],
            actual_ip=source_ip,
            actual_port=source_port,
            packet_kind="csi_frame" if isinstance(packet, CsiFrameV1) else "heartbeat",
            host_rx_ns=packet.host_rx_ns,
        )
        self.rejections.append(rejection)
        return rejection


class UdpPacketSource:
    def __init__(self, bind_host: str = "0.0.0.0", bind_port: int = 5005) -> None:
        self.bind_host = bind_host
        self.bind_port = bind_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((bind_host, bind_port))
        self.sock.settimeout(0.25)

    def packets(self) -> Iterator[CsiFrameV1 | HeartbeatV1 | InvalidPacket]:
        for packet, _data in self.packets_with_raw():
            yield packet

    def packets_with_raw(self) -> Iterator[tuple[CsiFrameV1 | HeartbeatV1 | InvalidPacket, bytes]]:
        while True:
            try:
                data, addr = self.sock.recvfrom(MAX_UDP_PAYLOAD)
            except socket.timeout:
                break
            yield parse_udp_packet(data, addr, time.time_ns()), data

    def close(self) -> None:
        self.sock.close()
