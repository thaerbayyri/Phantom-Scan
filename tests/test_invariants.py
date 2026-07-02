from pathlib import Path

from phantom.dsp import deterministic_human_gate, dual_node_on_axis_position


ROOT = Path(__file__).resolve().parents[1]


def test_dual_node_equal_balance_midpoint():
    result = dual_node_on_axis_position(10.0, 10.0, baseline_m=5.0)
    assert result["dimensionality"] == "1D-on-axis"
    assert result["balance"] == 0.5
    assert abs(float(result["x_m"]) - 2.5) < 1e-9


def test_f1_ai_perturbations_do_not_change_deterministic_human_gate():
    baseline = deterministic_human_gate(
        motion_present=True,
        respiration_periodic=True,
        cardiac_energy_present=False,
    )
    ai_perturbations = [
        {"presence_prob": 0.0, "confidence": 0.0, "resp_bpm": 2.0},
        {"presence_prob": 1.0, "confidence": 1.0, "resp_bpm": 99.0},
        {"pose": [[999, -999]], "humanProb": 1.0},
    ]
    for _perturbation in ai_perturbations:
        assert deterministic_human_gate(True, True, False) is baseline


def test_f1_ai_path_does_not_emit_authoritative_identity_or_aoa():
    ai_source = (ROOT / "scripts" / "ai_inference.py").read_text(encoding="utf-8")
    assert '"label": label' in ai_source
    assert 'label = "unknown"' in ai_source
    assert "advisoryLabel" in ai_source
    assert "aoa" not in ai_source.lower()


def test_f2_dashboard_live_surface_has_no_upstream_hardware_controls():
    dashboard = (ROOT / "client" / "src" / "pages" / "dashboard.tsx").read_text(encoding="utf-8")
    top_bar = (ROOT / "client" / "src" / "components" / "dashboard" / "top-bar.tsx").read_text(encoding="utf-8")
    forbidden = ["HardwareConfig", "SystemControlPanel", "api/esp32/configure", "execute-task"]
    for token in forbidden:
        assert token not in dashboard
        assert token not in top_bar


def test_runtime_scope_guard_has_no_flight_control_imports():
    runtime_files = [
        ROOT / "phantom" / "runtime.py",
        ROOT / "phantom" / "api.py",
        ROOT / "phantom" / "ingest.py",
        ROOT / "server" / "index.ts",
        ROOT / "server" / "lib" / "authority-follower.ts",
    ]
    forbidden = ["mavlink", "uav", "drone", "gps", "imu", "psc"]
    for path in runtime_files:
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in text, f"{token} leaked into runtime file {path}"
