"""PS-FIX-37: the pasted-serial-log parser, on synthetic logs that follow the firmware's exact format strings
(csi_collector.c: "medium tick: yield=%lupps csi_cb=%lu send_fail=%lu rate_skip=%lu cb_drop=%lu" and
"CSI cb #%lu: len=%d rssi=%d ch=%d mac_skip=%lu"). It reads text only; a source test pins that no serial/socket code exists."""
from __future__ import annotations

import inspect
import json
import math

import pytest

from scripts.presence_eval import parse_serial_counters as psc

GREEN, RESET = "\x1b[0;32m", "\x1b[0m"


def tick(t_ms: int, y: int, cb: int, sf: int, rs: int, dr: int, colour: bool = False) -> str:
    body = f"I ({t_ms}) csi_collector: medium tick: yield={y}pps csi_cb={cb} send_fail={sf} rate_skip={rs} cb_drop={dr}"
    return f"{GREEN}{body}{RESET}" if colour else body


def cb_line(t_ms: int, n: int, rssi: int, ch: int, mac: int) -> str:
    return f"I ({t_ms}) csi_collector: CSI cb #{n}: len=128 rssi={rssi} ch={ch} mac_skip={mac}"


def make_log(seconds: int = 60, y: int = 65, cb: int = 90, rs_per_s: int = 20) -> str:
    lines = ["I (100) wifi: unrelated boot noise", "garbage line without numbers"]
    for i in range(seconds):
        lines.append(tick(1000 + i * 1000, y, cb, 0, rs_per_s * (i + 1), 0, colour=(i % 2 == 0)))
        if i % 5 == 0:
            n = 250 * (i // 5 + 1)
            lines.append(cb_line(1000 + i * 1000, n, -45, 6, mac=int(n * 0.30)))
    return "\n".join(lines)


def test_parses_ticks_callbacks_and_ignores_noise_and_ansi_colours() -> None:
    p = psc.parse_text(make_log(30))
    assert len(p["ticks"]) == 30 and len(p["callbacks"]) == 6
    assert p["ignored_lines"] == 2
    assert p["ticks"][0] == {"t_ms": 1000, "yield_pps": 65, "cb_delta": 90, "send_fail": 0, "rate_skip": 20, "cb_drop": 0}


def test_summary_numbers() -> None:
    s = psc.summarize(psc.parse_text(make_log(60)), node=2)
    assert s["mean_yield_pps"] == pytest.approx(65.0)
    assert s["frames_per_ping_interval"] == pytest.approx(65 * 0.030)           # 1.95 frames per 30 ms ping
    assert s["yield_over_callbacks"] == pytest.approx(65 / 90)
    assert s["rate_skip_per_s"] == pytest.approx(20.0)
    assert s["mac_skip_share_of_callbacks"] == pytest.approx(0.30, abs=0.005)
    assert s["share_ticks_at_gate_cap"] == 0.0
    assert s["channels_seen"] == [6] and s["rssi_min_max"] == [-45, -45]
    assert s["warnings"] == []


def test_a_node_running_at_the_gate_cap_is_reported() -> None:
    s = psc.summarize(psc.parse_text(make_log(30, y=100)))
    assert s["share_ticks_at_gate_cap"] == 1.0


def test_short_capture_is_flagged() -> None:
    s = psc.summarize(psc.parse_text(make_log(5)))
    assert any("too short" in w for w in s["warnings"])


def test_counter_reset_means_reboot_and_suppresses_the_cumulative_figures() -> None:
    lines = [tick(1000 + i * 1000, 65, 90, 0, 100 + i, 0) for i in range(12)]
    lines += [tick(13000 + i * 1000, 65, 90, 0, 3 + i, 0) for i in range(12)]   # rate_skip restarts: the node rebooted
    s = psc.summarize(psc.parse_text("\n".join(lines)))
    assert any("rebooted" in w for w in s["warnings"])
    assert s["rate_skip_per_s"] is None


def test_callback_counter_going_down_suppresses_the_mac_share() -> None:
    log = "\n".join([cb_line(1000, 5000, -40, 6, 1500), cb_line(2000, 250, -40, 6, 70)])
    s = psc.summarize(psc.parse_text(log))
    assert "mac_skip_share_of_callbacks" not in s and any("went down" in w for w in s["warnings"])


def test_empty_and_garbage_input_do_not_crash() -> None:
    s = psc.summarize(psc.parse_text(""))
    assert s["ticks"] == 0 and s["warnings"]
    s2 = psc.summarize(psc.parse_text("hello\nworld\n"))
    assert s2["ignored_lines"] == 2


def test_cli_exit_codes_and_json(tmp_path) -> None:
    log = tmp_path / "node2.txt"
    log.write_text(make_log(30), encoding="utf-8")
    out = tmp_path / "s.json"
    assert psc.main([str(log), "--node", "2", "--json", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["node"] == 2
    assert psc.main([str(tmp_path / "missing.txt")]) == 2
    empty = tmp_path / "empty.txt"
    empty.write_text("nothing useful\n", encoding="utf-8")
    assert psc.main([str(empty)]) == 1


def test_render_mentions_frame_types_cannot_be_seen_and_has_no_nan_text() -> None:
    text = psc.render(psc.summarize(psc.parse_text(make_log(30)), node=1))
    assert "cannot say which frame TYPES" in text and "nan" not in text.lower()
    assert not math.isnan(psc.summarize(psc.parse_text(make_log(30)))["mean_yield_pps"])


def test_module_never_touches_a_serial_port_or_a_socket() -> None:
    src = inspect.getsource(psc)
    code = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith(("#", '"""')))
    code = code.replace("args.json.write_text", "").replace("write_text", "")
    for banned in ("import serial", "pyserial", "import socket", "import usb", "COM", "/dev/tty", "esptool", "write("):
        assert banned not in code, banned
