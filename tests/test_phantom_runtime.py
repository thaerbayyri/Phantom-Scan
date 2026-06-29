from pathlib import Path
import time

from phantom.protocol import CsiFrameV1, HeartbeatV1
from phantom.recording import read_jsonl_records
from phantom.runtime import PhantomRuntime, RuntimeConfig, RuntimeMode


def make_csi(node_id: int, seq: int, device_ts_us: int, host_rx_ns: int) -> CsiFrameV1:
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
    )


def make_heartbeat(node_id: int, seq: int, host_rx_ns: int) -> HeartbeatV1:
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
