"""Python Milestone-1 detection authority (UDP :5005 → derived frames).

SUPERSEDED — live detection now runs in server/lib (the TS dashboard owns
UDP :5005); kept for reference. Running this alongside the dashboard causes
an EADDRINUSE collision on :5005.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import enum
import os
import socket
import time
from typing import Any

from .ai_status import probe_ai_stack
from .dsp import NodeDspPipeline, cross_node_correlation, dual_node_on_axis_position
from .ingest import NodeBuffer, SourcePinningGuard, UdpPacketSource
from .protocol import CsiFrameV1, HeartbeatV1, InvalidPacket
from .recording import JsonlSessionWriter, read_jsonl_records


class RuntimeMode(str, enum.Enum):
    LIVE_DEGRADED_SINGLE_NODE = "live_degraded_single_node"
    LIVE_FUSED_TWO_NODE = "live_fused_two_node"
    REPLAY_DEGRADED_SINGLE_NODE = "replay_degraded_single_node"
    REPLAY_FUSED_TWO_NODE = "replay_fused_two_node"


@dataclass(slots=True)
class RuntimeConfig:
    expected_nodes: tuple[int, int] = (1, 2)
    stale_timeout_ns: int = 3_000_000_000
    output_dir: str = os.path.join("data", "sessions")
    udp_host: str = "0.0.0.0"
    udp_port: int = 5005
    ai_model_dir: str = os.path.join("ai model and densepose", "model")
    synthetic_enabled: bool = False
    forward_ai_host: str = "127.0.0.1"
    forward_ai_port: int = 5006
    forward_ai_enabled: bool = True


class PhantomRuntime:
    def __init__(self, config: RuntimeConfig | None = None) -> None:
        self.config = config or RuntimeConfig()
        self.node_buffers = {
            node_id: NodeBuffer(node_id=node_id) for node_id in self.config.expected_nodes
        }
        self.node_pipelines = {
            node_id: NodeDspPipeline() for node_id in self.config.expected_nodes
        }
        self.latest_node_metrics: dict[int, dict[str, Any]] = {}
        self.writer: JsonlSessionWriter | None = None
        self.started = False
        self.ingest_paused = False
        self.replay_mode = False
        self.source_guard = SourcePinningGuard()
        self.ml_status = probe_ai_stack(self.config.ai_model_dir).to_dict()
        self.last_derived: dict[str, Any] | None = None
        self.forward_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def start_session(self) -> None:
        self.ingest_paused = False
        if self.started:
            return
        self._reset_session_state()
        self.writer = JsonlSessionWriter.create(
            output_dir=self.config.output_dir,
            expected_nodes=list(self.config.expected_nodes),
            dsp_config={"sample_rate_hz": 20.0, "pipeline": "deterministic_m1"},
            ml_mode=self.ml_status["mode"],
            host_info={
                "udp_host": self.config.udp_host,
                "udp_port": self.config.udp_port,
                "node_source_pinning": True,
            },
            firmware_metadata={
                "ai_status": self.ml_status,
                "active_adapters": self.ml_status.get("adapters", {}),
            },
        )
        self.started = True

    def stop_session(self, *, pause_ingest: bool = False, reset_state: bool = False) -> None:
        if self.writer:
            self.writer.close(
                summary={
                    "last_mode": self.current_mode().value,
                    "ml_status": self.ml_status,
                    "synthetic_enabled": self.config.synthetic_enabled,
                    "source_pinning_rejections": len(self.source_guard.rejections),
                }
            )
        self.writer = None
        self.started = False
        if pause_ingest:
            self.ingest_paused = True
        if reset_state:
            self._reset_session_state()

    def _reset_session_state(self) -> None:
        self.node_buffers = {
            node_id: NodeBuffer(node_id=node_id) for node_id in self.config.expected_nodes
        }
        self.node_pipelines = {
            node_id: NodeDspPipeline() for node_id in self.config.expected_nodes
        }
        self.latest_node_metrics = {}
        self.last_derived = None
        self.source_guard = SourcePinningGuard()

    def current_mode(self) -> RuntimeMode:
        """fused_two_node when BOTH nodes are fresh, else degraded_single_node
        (same freshness rule the TS pipeline later adopted)."""
        now_ns = time.time_ns()
        active_nodes = [
            node_id
            for node_id, state in self.node_buffers.items()
            if not state.is_stale(now_ns, self.config.stale_timeout_ns)
        ]
        is_replay = self.replay_mode
        if len(active_nodes) == 2:
            return RuntimeMode.REPLAY_FUSED_TWO_NODE if is_replay else RuntimeMode.LIVE_FUSED_TWO_NODE
        return RuntimeMode.REPLAY_DEGRADED_SINGLE_NODE if is_replay else RuntimeMode.LIVE_DEGRADED_SINGLE_NODE

    def ingest_packet(
        self,
        packet: CsiFrameV1 | HeartbeatV1 | InvalidPacket,
        raw_data: bytes | None = None,
    ) -> dict[str, Any] | None:
        """Ingest one UDP packet: source-pin check → buffer → per-node DSP →
        derived (fused) frame. Returns the derived frame for CSI packets."""
        if self.ingest_paused:
            return None

        if not self.started:
            self.start_session()

        if isinstance(packet, InvalidPacket):
            return None

        if packet.node_id not in self.node_buffers:
            return None

        rejection = self.source_guard.check(packet)
        if rejection is not None:
            if self.writer:
                self.writer.write(rejection.to_record())
            return None

        if raw_data and self.config.forward_ai_enabled:
            self.forward_socket.sendto(
                raw_data,
                (self.config.forward_ai_host, self.config.forward_ai_port),
            )

        self.node_buffers[packet.node_id].add_packet(packet)
        if self.writer:
            self.writer.write(packet.to_record())

        if isinstance(packet, CsiFrameV1):
            per_node = self.node_pipelines[packet.node_id].process(packet)
            self.latest_node_metrics[packet.node_id] = per_node
            derived = self._build_derived_frame(packet.node_id, per_node)
            self.last_derived = derived
            if self.writer:
                self.writer.write(derived)
            return derived

        return None

    def _build_derived_frame(self, node_id: int, node_metrics: dict[str, Any]) -> dict[str, Any]:
        """Fusion step: when both nodes are healthy, combine their latest
        metrics into cross-node correlation + a 1-D on-axis position
        (mode="fused"); otherwise emit single-node metrics (mode="degraded")."""
        now_ns = time.time_ns()
        healthy_nodes = {
            nid: state
            for nid, state in self.node_buffers.items()
            if not state.is_stale(now_ns, self.config.stale_timeout_ns)
        }
        per_node = {str(node_id): node_metrics}
        mode = "degraded"
        fused: dict[str, Any] | None = None
        timing_alignment_ns: int | None = None

        if len(healthy_nodes) == 2 and all(state.csi_frames for state in healthy_nodes.values()):
            left = healthy_nodes[self.config.expected_nodes[0]].csi_frames[-1]
            right = healthy_nodes[self.config.expected_nodes[1]].csi_frames[-1]
            left_metrics = self.latest_node_metrics.get(left.node_id, node_metrics)
            right_metrics = self.latest_node_metrics.get(right.node_id, node_metrics)
            per_node = {str(left.node_id): left_metrics, str(right.node_id): right_metrics}
            timing_alignment_ns = abs(
                left.authoritative_timestamp_ns - right.authoritative_timestamp_ns
            )
            fused = {
                "cross_node_correlation": cross_node_correlation(
                    np_array([left_metrics["dynamic_mean"]]),
                    np_array([right_metrics["dynamic_mean"]]),
                ),
                "on_axis_position": dual_node_on_axis_position(
                    float(left_metrics["mean_amplitude"]),
                    float(right_metrics["mean_amplitude"]),
                    baseline_m=5.0,
                ),
                "timing_alignment_ns": timing_alignment_ns,
                "source_seqs": {
                    str(left.node_id): left.seq,
                    str(right.node_id): right.seq,
                },
            }
            mode = "fused"

        return {
            "record_type": "derived_frame",
            "schema_version": 1,
            "emitted_at_ns": time.time_ns(),
            "runtime_mode": self.current_mode().value,
            "mode": mode,
            "per_node": per_node,
            "fused": fused,
            "timing_alignment_ns": timing_alignment_ns,
            "source": "synthetic" if self.config.synthetic_enabled else "live",
            "synthetic_enabled": self.config.synthetic_enabled,
        }

    def live_step(self, packet_source: UdpPacketSource) -> list[dict[str, Any]]:
        outputs: list[dict[str, Any]] = []
        for packet, raw_data in packet_source.packets_with_raw():
            derived = self.ingest_packet(packet, raw_data=raw_data)
            if derived:
                outputs.append(derived)
        return outputs

    def replay_file(self, path: str, speed: float = 0.0) -> list[dict[str, Any]]:
        self.replay_mode = True
        outputs: list[dict[str, Any]] = []
        last_host_rx_ns: int | None = None
        for record in read_jsonl_records(path):
            record_type = record.get("record_type")
            if record_type == "csi_frame":
                packet = CsiFrameV1(
                    schema_version=record["schema_version"],
                    node_id=record["node_id"],
                    seq=record["seq"],
                    device_ts_us=record.get("device_ts_us"),
                    device_ts_ms=record.get("device_ts_ms"),
                    device_ts_valid=record.get("device_ts_valid", False),
                    host_rx_ns=record["host_rx_ns"],
                    rssi_dbm=record["rssi_dbm"],
                    noise_dbm=record["noise_dbm"],
                    channel=record["channel"],
                    freq_mhz=record["freq_mhz"],
                    n_antennas=record["n_antennas"],
                    n_subcarriers=record["n_subcarriers"],
                    iq_bytes=bytes.fromhex(record["iq_hex"]),
                    source_ip=record.get("source_ip", ""),
                    source_port=record.get("source_port", 0),
                )
                if speed and last_host_rx_ns is not None:
                    delay_ns = max(0, packet.host_rx_ns - last_host_rx_ns)
                    time.sleep(delay_ns / 1_000_000_000 / speed)
                last_host_rx_ns = packet.host_rx_ns
                derived = self.ingest_packet(packet)
                if derived:
                    outputs.append(derived)
            elif record_type == "heartbeat":
                packet = HeartbeatV1(
                    schema_version=record["schema_version"],
                    node_id=record["node_id"],
                    seq=record["seq"],
                    device_ts_ms=record["device_ts_ms"],
                    host_rx_ns=record["host_rx_ns"],
                    wifi_connected=record["wifi_connected"],
                    callback_drops=record["callback_drops"],
                    queue_high_watermark=record["queue_high_watermark"],
                    send_failures=record["send_failures"],
                    reconnect_count=record["reconnect_count"],
                    firmware_build_id=record["firmware_build_id"],
                    source_ip=record.get("source_ip", ""),
                    source_port=record.get("source_port", 0),
                )
                self.ingest_packet(packet)
        return outputs

    def status(self) -> dict[str, Any]:
        now_ns = time.time_ns()
        nodes = {}
        for node_id, state in self.node_buffers.items():
            nodes[str(node_id)] = {
                "stale": state.is_stale(now_ns, self.config.stale_timeout_ns),
                "last_csi_rx_ns": state.health.last_csi_rx_ns,
                "last_heartbeat_rx_ns": state.health.last_heartbeat_rx_ns,
                "packet_loss_count": state.health.packet_loss_count,
                "out_of_order_count": state.health.out_of_order_count,
                "invalid_count": state.health.invalid_count,
                "buffered_csi_frames": len(state.csi_frames),
                "buffered_heartbeats": len(state.heartbeats),
            }
        return {
            "status": "ok",
            "runtime_mode": self.current_mode().value,
            "started": self.started,
            "ingest_paused": self.ingest_paused,
            "ml_status": self.ml_status,
            "authority": True,
            "source": "synthetic" if self.config.synthetic_enabled else "live",
            "synthetic_enabled": self.config.synthetic_enabled,
            "source_pinning": {
                str(node_id): {"ip": source[0], "port": source[1]}
                for node_id, source in self.source_guard.bindings.items()
            },
            "source_pinning_rejections": len(self.source_guard.rejections),
            "nodes": nodes,
            "last_derived": self.last_derived,
        }

    def sensing_frame(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "runtime_mode": self.current_mode().value,
            "authority": True,
            "ingest_paused": self.ingest_paused,
            "source": "synthetic" if self.config.synthetic_enabled else "live",
            "synthetic_enabled": self.config.synthetic_enabled,
            "node_mode": "fused_two_node" if "FUSED_TWO_NODE" in self.current_mode().name else "single_node",
            "source_pinning": {
                str(node_id): {"ip": source[0], "port": source[1]}
                for node_id, source in self.source_guard.bindings.items()
            },
            "source_pinning_rejections": len(self.source_guard.rejections),
            "ml_status": self.ml_status,
            "derived": self.last_derived,
        }


def np_array(values: list[float]) -> Any:
    import numpy as np

    return np.asarray(values, dtype=float)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phantom Scan canonical Milestone 1 runtime")
    sub = parser.add_subparsers(dest="command", required=True)

    live = sub.add_parser("live", help="Run UDP live ingest")
    live.add_argument("--host", default="0.0.0.0")
    live.add_argument("--port", type=int, default=5005)
    live.add_argument("--output-dir", default=os.path.join("data", "sessions"))
    live.add_argument("--duration", type=float, default=0.0)
    live.add_argument("--api-host", default="127.0.0.1")
    live.add_argument("--api-port", type=int, default=8789)
    live.add_argument("--no-api", action="store_true")
    live.add_argument("--forward-ai-host", default="127.0.0.1")
    live.add_argument("--forward-ai-port", type=int, default=5006)
    live.add_argument("--no-forward-ai", action="store_true")
    live.add_argument("--synthetic", action="store_true", help="Explicitly allow synthetic/demo source tagging.")
    live.add_argument("--no-synthetic", action="store_true", default=True, help="Default canonical live mode; no synthetic output.")

    replay = sub.add_parser("replay", help="Replay JSONL session")
    replay.add_argument("--input", required=True)
    replay.add_argument("--speed", type=float, default=0.0)
    replay.add_argument("--output-dir", default=os.path.join("data", "sessions"))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    runtime = PhantomRuntime(
        RuntimeConfig(
            output_dir=args.output_dir,
            udp_host=getattr(args, "host", "0.0.0.0"),
            udp_port=getattr(args, "port", 5005),
            synthetic_enabled=bool(getattr(args, "synthetic", False)),
            forward_ai_host=getattr(args, "forward_ai_host", "127.0.0.1"),
            forward_ai_port=getattr(args, "forward_ai_port", 5006),
            forward_ai_enabled=not bool(getattr(args, "no_forward_ai", False)),
        )
    )

    if args.command == "live":
        api = None
        if not args.no_api:
            from .api import RuntimeApiServer

            api = RuntimeApiServer(runtime, host=args.api_host, port=args.api_port)
            api.start()
        source = UdpPacketSource(bind_host=args.host, bind_port=args.port)
        deadline = time.monotonic() + args.duration if args.duration > 0 else None
        try:
            while deadline is None or time.monotonic() < deadline:
                runtime.live_step(source)
        except KeyboardInterrupt:
            pass
        finally:
            source.close()
            if api:
                api.stop()
            runtime.stop_session()
        return 0

    if args.command == "replay":
        runtime.start_session()
        runtime.replay_file(args.input, speed=args.speed)
        runtime.stop_session()
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
