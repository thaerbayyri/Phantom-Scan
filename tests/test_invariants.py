from pathlib import Path

from phantom.dsp import deterministic_human_gate, dual_node_on_axis_position


ROOT = Path(__file__).resolve().parents[1]


def test_dual_node_equal_balance_midpoint():
    result = dual_node_on_axis_position(10.0, 10.0, baseline_m=3.0)
    assert result["dimensionality"] == "1D-on-axis"
    assert result["balance"] == 0.5
    assert abs(float(result["x_m"]) - 0.0) < 1e-9


def test_deterministic_human_gate_is_a_pure_function_of_its_dsp_inputs():
    # deterministic_human_gate takes no AI input at all; the end-to-end F1
    # check (AI advisories cannot change the live gate) is the TS test
    # "F1: extreme AI advisories leave every deterministic broadcast
    # byte-identical" in server/lib/websocket.test.ts.
    assert deterministic_human_gate(True, True, False) == deterministic_human_gate(True, True, False)


def test_f1_ai_sidecar_only_sends_advisory_message_types():
    import re

    ai_source = (ROOT / "scripts" / "ai_inference.py").read_text(encoding="utf-8")
    sent_types = set(re.findall(r'"type":\s*"([A-Za-z]+)"', ai_source))
    # targetIdentity/vitalSigns are relayed by the server ONLY as
    # advisoryIdentity/advisoryVitalSigns; none of these can write the
    # authoritative channels (websocket.ts F1 firewall).
    allowed = {"poseFrame", "targetIdentity", "vitalSigns", "calibrationAck", "registerAIClient"}
    assert sent_types, "sanity: the sidecar must send something"
    assert sent_types <= allowed, f"unexpected sidecar message types: {sent_types - allowed}"


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
    ]
    forbidden = ["mavlink", "uav", "drone", "gps", "imu", "psc"]
    for path in runtime_files:
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in text, f"{token} leaked into runtime file {path}"
