"""Regression coverage for PS-AUDIT-016 (already fixed in code — see
PHANTOM_SCAN_REMEDIATION_REPORT.md WP-14): `_build_derived_frame()` must feed
`cross_node_correlation()` with real multi-frame motion HISTORIES (not a
single sample, which forces correlation to a structural 0.0 regardless of
input), and `dual_node_on_axis_position()` must be fed the normalized motion
metric, not raw mean amplitude. This test drives the real
`PhantomRuntime.ingest_packet()` pipeline (not the pure functions in
isolation) so the wiring itself is what's under test.
"""

import math
from pathlib import Path

from phantom.protocol import CsiFrameV1
from phantom.runtime import PhantomRuntime, RuntimeConfig


def _iq_bytes_for_amplitude(amplitude: float) -> bytes:
    """Single-subcarrier I/Q pair whose magnitude is ~`amplitude`."""
    i_val = max(-127, min(127, int(round(amplitude))))
    return bytes([i_val & 0xFF, 0])


def _make_csi(node_id: int, seq: int, amplitude: float, ts_us: int) -> CsiFrameV1:
    return CsiFrameV1(
        schema_version=1,
        node_id=node_id,
        seq=seq,
        device_ts_us=ts_us,
        device_ts_ms=ts_us // 1000,
        device_ts_valid=True,
        host_rx_ns=ts_us * 1000,
        rssi_dbm=-50,
        noise_dbm=-90,
        channel=1,
        freq_mhz=2412,
        n_antennas=1,
        n_subcarriers=1,
        iq_bytes=_iq_bytes_for_amplitude(amplitude),
        source_ip="10.0.0.11" if node_id == 1 else "10.0.0.12",
        source_port=5005,
    )


def _lcg(seed: int):
    """Deterministic tiny linear congruential generator -> floats in [-1, 1]."""
    state = seed
    while True:
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        yield (state / 0x7FFFFFFF) * 2.0 - 1.0


def _run_two_node_session(*, output_dir: Path, correlated: bool, n_frames: int = 120) -> dict:
    # output_dir must be a real pytest tmp_path, not "" — an empty string
    # resolves to the CWD (repo root when pytest runs from there), which
    # previously left stray <uuid>.jsonl session files in the repo root.
    runtime = PhantomRuntime(RuntimeConfig(output_dir=str(output_dir), stale_timeout_ns=60_000_000_000))
    left_noise = _lcg(1)
    right_noise = _lcg(2 if correlated else 999)
    derived = None
    for i in range(n_frames):
        ts_us = 1_000_000 + i * 100_000
        shared = 20.0 * math.sin(2 * math.pi * i / 25.0) if correlated else 0.0
        left_amp = 60.0 + shared + 3.0 * next(left_noise)
        if correlated:
            right_amp = 60.0 + shared + 3.0 * next(right_noise)
        else:
            # Fully independent motion on the right node: no shared component.
            right_amp = 60.0 + 20.0 * math.sin(2 * math.pi * i / 7.0 + 1.7) + 3.0 * next(right_noise)
        runtime.ingest_packet(_make_csi(1, i, left_amp, ts_us))
        derived = runtime.ingest_packet(_make_csi(2, i, right_amp, ts_us + 50))
    assert derived is not None
    assert derived["mode"] == "fused"
    return derived


def test_cross_node_correlation_is_not_structurally_zero(tmp_path: Path):
    derived = _run_two_node_session(output_dir=tmp_path, correlated=True)
    correlation = derived["fused"]["cross_node_correlation"]
    assert correlation != 0.0, (
        "cross_node_correlation must not be the structural 0.0 that results "
        "from feeding single-sample arrays (PS-AUDIT-016 regression)"
    )


def test_correlated_motion_scores_higher_than_independent_motion(tmp_path: Path):
    correlated = _run_two_node_session(output_dir=tmp_path / "a", correlated=True)["fused"]["cross_node_correlation"]
    independent = _run_two_node_session(output_dir=tmp_path / "b", correlated=False)["fused"]["cross_node_correlation"]
    assert correlated > independent, (
        f"shared-motion correlation ({correlated}) should exceed independent-motion "
        f"correlation ({independent}) — the metric must reflect real synchrony, "
        "not just be nonzero"
    )


def test_on_axis_position_uses_motion_energy_through_real_pipeline_wiring(tmp_path: Path):
    derived = _run_two_node_session(output_dir=tmp_path, correlated=True)
    on_axis = derived["fused"]["on_axis_position"]
    assert on_axis["dimensionality"] == "1D-on-axis"
    assert on_axis["baseline_m"] == 3.0
    # Centered geometry: midpoint balance (0.5) maps to x_m == 0.0, not the
    # stale 5 m-baseline "2.5" once locked in by test_invariants.py.
    assert -1.5 <= on_axis["x_m"] <= 1.5
