from pathlib import Path
import time

from phantom.protocol import CsiFrameV1, HeartbeatV1
from phantom.recording import read_jsonl_records
from phantom.runtime import PhantomRuntime, RuntimeConfig, RuntimeMode


def make_csi(
    node_id: int,
    seq: int,
    device_ts_us: int,
    host_rx_ns: int,
    source_ip: str = "10.0.0.11",
    source_port: int = 5005,
) -> CsiFrameV1:
    return CsiFrameV1(
        schema_version=1,
        node_id=node_id,
        seq=seq,
        device_ts_us=device_ts_us,
        device_ts_ms=device_ts_us // 1000,
        device_ts_valid=True,
        host_rx_ns=host_rx_ns,
        rssi_dbm=-50,
        noise_dbm=-90,
        channel=1,
        freq_mhz=2412,
        n_antennas=1,
        n_subcarriers=4,
        iq_bytes=bytes([1, 2, 3, 4, 5, 6, 7, 8]),
        source_ip=source_ip,
        source_port=source_port,
    )


def make_heartbeat(
    node_id: int,
    seq: int,
    host_rx_ns: int,
    source_ip: str = "10.0.0.11",
    source_port: int = 5005,
) -> HeartbeatV1:
    return HeartbeatV1(
        schema_version=1,
        node_id=node_id,
        seq=seq,
        device_ts_ms=seq * 1000,
        host_rx_ns=host_rx_ns,
        wifi_connected=True,
        callback_drops=0,
        queue_high_watermark=0,
        send_failures=0,
        reconnect_count=0,
        firmware_build_id=1,
        source_ip=source_ip,
        source_port=source_port,
    )


def test_runtime_stays_degraded_with_one_node(tmp_path: Path):
    runtime = PhantomRuntime(RuntimeConfig(output_dir=str(tmp_path), stale_timeout_ns=10_000_000_000))
    runtime.start_session()
    derived = runtime.ingest_packet(make_csi(1, 1, 1_000_000, 2_000_000))
    assert derived is not None
    assert derived["mode"] == "degraded"
    assert runtime.current_mode() == RuntimeMode.LIVE_DEGRADED_SINGLE_NODE
    runtime.stop_session()


def test_runtime_fuses_with_two_nodes(tmp_path: Path):
    runtime = PhantomRuntime(RuntimeConfig(output_dir=str(tmp_path), stale_timeout_ns=10_000_000_000))
    runtime.start_session()
    runtime.ingest_packet(make_csi(1, 1, 1_000_000, 2_000_000))
    derived = runtime.ingest_packet(make_csi(2, 1, 1_000_100, 2_000_100))
    assert derived is not None
    assert derived["mode"] == "fused"
    assert derived["fused"] is not None
    assert runtime.current_mode() == RuntimeMode.LIVE_FUSED_TWO_NODE
    runtime.stop_session()


def test_runtime_status_transitions_fused_degraded_recovered(tmp_path: Path):
    runtime = PhantomRuntime(RuntimeConfig(output_dir=str(tmp_path), stale_timeout_ns=10_000_000_000))
    runtime.start_session()
    runtime.ingest_packet(make_csi(1, 1, 1_000_000, 2_000_000))
    runtime.ingest_packet(make_csi(2, 1, 1_000_100, 2_000_100))
    assert runtime.current_mode() == RuntimeMode.LIVE_FUSED_TWO_NODE

    runtime.node_buffers[2].health.last_seen_monotonic_ns = 1
    assert runtime.current_mode() == RuntimeMode.LIVE_DEGRADED_SINGLE_NODE

    runtime.ingest_packet(make_csi(2, 2, 1_000_200, 2_000_200))
    assert runtime.current_mode() == RuntimeMode.LIVE_FUSED_TWO_NODE
    runtime.stop_session()


def test_source_pinning_rejects_spoofed_node_source(tmp_path: Path):
    runtime = PhantomRuntime(RuntimeConfig(output_dir=str(tmp_path), stale_timeout_ns=10_000_000_000))
    runtime.start_session()
    first = runtime.ingest_packet(make_csi(1, 1, 1_000_000, 2_000_000, "10.0.0.11", 5005))
    spoof = runtime.ingest_packet(make_csi(1, 2, 1_000_050, 2_000_050, "10.0.0.99", 5005))
    assert first is not None
    assert spoof is None
    assert runtime.status()["source_pinning_rejections"] == 1
    assert runtime.node_buffers[1].health.last_seq_csi == 1
    runtime.stop_session()


def test_source_pinning_applies_to_heartbeats_and_csi(tmp_path: Path):
    runtime = PhantomRuntime(RuntimeConfig(output_dir=str(tmp_path), stale_timeout_ns=10_000_000_000))
    runtime.start_session()
    runtime.ingest_packet(make_heartbeat(2, 1, 100, "10.0.0.12", 5005))
    derived = runtime.ingest_packet(make_csi(2, 1, 1_000_000, 2_000_000, "10.0.0.12", 5005))
    spoof = runtime.ingest_packet(make_csi(2, 2, 1_000_050, 2_000_050, "10.0.0.88", 5005))
    assert derived is not None
    assert spoof is None
    assert runtime.source_guard.bindings[2] == ("10.0.0.12", 5005)
    runtime.stop_session()


def test_jsonl_roundtrip_replay(tmp_path: Path):
    runtime = PhantomRuntime(RuntimeConfig(output_dir=str(tmp_path), stale_timeout_ns=10_000_000_000))
    runtime.start_session()
    runtime.ingest_packet(make_heartbeat(1, 1, 100))
    runtime.ingest_packet(make_csi(1, 1, 1_000_000, 2_000_000))
    runtime.ingest_packet(make_csi(2, 1, 1_000_050, 2_000_050))
    session_path = runtime.writer.path  # type: ignore[union-attr]
    runtime.stop_session()

    replay_runtime = PhantomRuntime(RuntimeConfig(output_dir=str(tmp_path), stale_timeout_ns=10_000_000_000))
    replay_runtime.start_session()
    outputs = replay_runtime.replay_file(str(session_path))
    replay_runtime.stop_session()
    assert outputs
    assert outputs[-1]["mode"] in {"degraded", "fused"}


def test_live_runtime_rejects_missing_source_info(tmp_path: Path):
    runtime = PhantomRuntime(RuntimeConfig(output_dir=str(tmp_path), stale_timeout_ns=10_000_000_000))
    runtime.start_session()
    derived = runtime.ingest_packet(make_csi(1, 1, 1_000_000, 2_000_000, "", 0))
    assert derived is None
    assert runtime.status()["source_pinning_rejections"] == 1
    runtime.stop_session()


def test_device_timestamp_preferred_over_host_timestamp():
    frame = make_csi(1, 1, 1_234_567, 9_999_999)
    assert frame.authoritative_timestamp_ns == 1_234_567_000


def test_recording_contains_header_and_footer(tmp_path: Path):
    runtime = PhantomRuntime(RuntimeConfig(output_dir=str(tmp_path), stale_timeout_ns=10_000_000_000))
    runtime.start_session()
    runtime.ingest_packet(make_csi(1, 1, 1_000_000, 2_000_000))
    path = runtime.writer.path  # type: ignore[union-attr]
    runtime.stop_session()
    records = list(read_jsonl_records(path))
    assert records[0]["record_type"] == "session_header"
    assert records[-1]["record_type"] == "session_footer"


def test_control_stop_pauses_ingest_until_explicit_start(tmp_path: Path):
    runtime = PhantomRuntime(RuntimeConfig(output_dir=str(tmp_path), stale_timeout_ns=10_000_000_000))
    runtime.start_session()
    assert runtime.ingest_packet(make_csi(1, 1, 1_000_000, 2_000_000, "10.0.0.11", 5005))
    assert runtime.status()["source_pinning"]

    runtime.stop_session(pause_ingest=True, reset_state=True)
    stopped_status = runtime.status()
    assert stopped_status["started"] is False
    assert stopped_status["ingest_paused"] is True
    assert stopped_status["source_pinning"] == {}
    assert stopped_status["last_derived"] is None

    assert runtime.ingest_packet(make_csi(1, 2, 1_000_050, 2_000_050, "10.0.0.11", 5005)) is None
    assert runtime.status()["started"] is False
    assert runtime.status()["source_pinning"] == {}

    runtime.start_session()
    assert runtime.ingest_packet(make_csi(1, 3, 1_000_100, 2_000_100, "10.0.0.11", 5005))
    assert runtime.status()["started"] is True
    assert runtime.status()["ingest_paused"] is False
    assert runtime.status()["source_pinning"] == {"1": {"ip": "10.0.0.11", "port": 5005}}
    runtime.stop_session()
