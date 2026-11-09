"""c2 amendment A2: the read-only soak checker (scripts/presence_eval/soak_check.py).

Synthetic soaks in pytest temp folders use the checker's parameters (minimum hours, reference seconds, window seconds) scaled down so a test
recording is a few minutes long; the spec values are asserted separately. Nothing here writes under data/."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from scripts.presence_eval import soak_check as sc

ROOT = Path(__file__).resolve().parents[1]
BASE_MS = 1_794_300_000_000
HEADER = {"type": "header", "schema": 2, "roomId": "soak-test", "subjectId": "s1", "label": "empty", "count": 0, "notes": "", "startedAtMs": BASE_MS, "part": 1}
SMALL = dict(min_hours=0.05, ref_s=60, window_s=10)        # 180 s minimum, 60 s reference, 10 s rolling window (tests only)
CLI_SMALL = ["--min-hours", "0.05", "--reference-s", "60", "--window-s", "10"]


def write_soak(path: Path, *, nodes=(1, 2, 3), seconds: int = 200, fps=60, rssi=lambda n, s: -40, seq_step=None) -> Path:
    """fps / rssi / seq_step may be callables (node, second) -> value; frames are evenly spaced inside each second."""
    rows = []
    for node in nodes:
        counter = 5_000 * node
        for s in range(seconds):
            k = int(fps(node, s) if callable(fps) else fps)
            for i in range(k):
                step = seq_step(node, s) if seq_step else None
                if step is not None:
                    counter += int(step)
                rows.append((BASE_MS + s * 1000 + int(i * 1000 / max(k, 1)), node, int(rssi(node, s)), counter if step is not None else None))
    rows.sort()
    with path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(HEADER) + "\n")
        for t, node, r, seq in rows:
            obj = {"type": "frame", "t": t, "n": node, "rssi": r, "a": [1.0] * 51}
            if seq is not None:
                obj["seq"], obj["nsc"] = seq, 128
            fh.write(json.dumps(obj) + "\n")
    return path


def failing(res: sc.SoakResult) -> list[str]:
    return [c.name for c in res.checks if not c.ok]


def run(path: Path, **kw) -> sc.SoakResult:
    return sc.check_soak([path], **{**SMALL, **kw})


def soak_end() -> datetime:
    """The time of the last synthetic frame: second 199, frame 59 of 60, at +983 ms."""
    return datetime.fromtimestamp((BASE_MS + 199 * 1000 + 983) / 1000, timezone.utc)


def test_the_spec_values_are_the_defaults() -> None:
    assert (sc.MIN_SOAK_H, sc.REF_S, sc.WINDOW_S, sc.COLLAPSE_RATIO, sc.MIN_LEVEL_FPS, sc.STEP_DB, sc.TIMING_MAX_H) == (3.0, 600, 60, 0.7, 54.0, 6.0, 1.0)


def test_a_steady_soak_passes_and_the_timing_rule_is_not_evaluated_without_a_block_1_start(tmp_path: Path) -> None:
    res = run(write_soak(tmp_path / "s.jsonl"))
    assert res.passed and failing(res) == []
    assert res.timing == "not evaluated"
    assert any("NON-SPEC PARAMETERS" in w for w in res.warnings)          # the relaxed test parameters are never silent
    assert {c.name for c in res.checks} >= {"duration", "level, node 1", "rate, node 2", "RSSI, node 3", "per-recording gates, node 3"}


def test_the_rate_condition_fails_alone_for_a_held_drop_and_ignores_a_short_dip(tmp_path: Path) -> None:
    held = write_soak(tmp_path / "held.jsonl", fps=lambda n, s: 30 if (n == 1 and 100 <= s < 130) else 60)
    res = run(held)
    assert failing(res) == ["rate, node 1"]
    assert "first below 0.7 x at +" in next(c.detail for c in res.checks if c.name == "rate, node 1")
    dip = write_soak(tmp_path / "dip.jsonl", fps=lambda n, s: 30 if (n == 1 and 100 <= s < 105) else 60)  # 5 s of a 10 s window: median 45 fps, above 0.7 x 60 = 42
    assert failing(run(dip)) == []


def test_the_level_condition_fails_alone_when_the_first_minutes_run_below_54_fps(tmp_path: Path) -> None:
    res = run(write_soak(tmp_path / "s.jsonl", fps=50))               # flat 50 fps: no collapse, but below the 54 fps level
    assert sorted(failing(res)) == ["level, node 1", "level, node 2", "level, node 3"]
    assert run(write_soak(tmp_path / "ok.jsonl", fps=54)).passed      # exactly 54 passes


@pytest.mark.parametrize("shift, should_fail", [(5, False), (6, True), (7, True)])
def test_the_rssi_condition_fails_at_6_db_held_longer_than_the_window(tmp_path: Path, shift: int, should_fail: bool) -> None:
    res = run(write_soak(tmp_path / "s.jsonl", rssi=lambda n, s: -40 - shift if (n == 2 and s >= 100) else -40))
    assert failing(res) == (["RSSI, node 2"] if should_fail else [])


def test_a_short_rssi_blip_is_ignored_by_the_rolling_median(tmp_path: Path) -> None:
    res = run(write_soak(tmp_path / "s.jsonl", rssi=lambda n, s: -50 if (n == 2 and 100 <= s < 104) else -40))  # 10 dB for 4 s of a 10 s window
    assert failing(res) == []


def test_a_soak_shorter_than_the_minimum_fails_only_the_duration(tmp_path: Path) -> None:
    res = run(write_soak(tmp_path / "s.jsonl", seconds=100))          # 100 s against a 180 s test minimum
    assert failing(res) == ["duration"]


def test_the_per_recording_gates_coverage_and_median_rate(tmp_path: Path) -> None:
    gappy = run(write_soak(tmp_path / "gappy.jsonl", fps=lambda n, s: 0 if (n == 3 and s % 10 < 3) else 60))   # 70 % of the seconds have frames
    assert failing(gappy) == ["per-recording gates, node 3"]
    slow = run(write_soak(tmp_path / "slow.jsonl", fps=lambda n, s: 15 if n == 1 else 60))                      # median 15 fps, outside [20, 100]
    assert "per-recording gates, node 1" in failing(slow) and "level, node 1" in failing(slow)


def test_a_listed_node_without_frames_fails(tmp_path: Path) -> None:
    res = run(write_soak(tmp_path / "s.jsonl"), nodes=(1, 2, 5))
    assert failing(res) == ["node 5 present"]


@pytest.mark.parametrize("minutes_after, ok", [(0, True), (59, True), (60, True), (61, False), (-1, False)])
def test_the_timing_rule_block_1_must_start_within_one_hour_after_the_soak_ends(tmp_path: Path, minutes_after: int, ok: bool) -> None:
    res = run(write_soak(tmp_path / "s.jsonl"), block1_start=soak_end() + timedelta(minutes=minutes_after))
    assert res.timing == ("pass" if ok else "fail")
    assert res.passed is ok
    assert failing(res) == ([] if ok else ["timing rule: block 1 within 1 h of the soak end"])


def test_any_declared_change_needs_a_new_soak_even_when_block_1_starts_in_time(tmp_path: Path) -> None:
    soak = write_soak(tmp_path / "s.jsonl")
    res = run(soak, block1_start=soak_end() + timedelta(minutes=10), changes=["router channel 2 -> 6"])
    assert res.timing == "fail" and "timing rule: no change in between" in failing(res)
    only_change = run(soak, changes=["node 3 moved"])
    assert only_change.timing == "fail" and not only_change.passed


def test_the_seq_report_is_report_only_and_never_changes_the_verdict(tmp_path: Path) -> None:
    # produced rate (delta seq) collapses from step 4 to step 1 at +100 s while the delivered rate stays 60 fps
    path = write_soak(tmp_path / "s.jsonl", seq_step=lambda n, s: 4 if s < 100 else 1)
    res = run(path)
    assert res.passed and failing(res) == []
    assert res.report_only["frames_with_seq"] == res.report_only["frames"] > 0
    assert res.report_only["flagged_windows"] > 0 and res.report_only["cases"]      # the labels are reported ...
    assert any("REPORT-ONLY (does not decide the verdict)" in line for line in sc.render(res))   # ... and printed as report-only
    plain = run(write_soak(tmp_path / "plain.jsonl"))
    assert "no seq" in plain.report_only["note"] and plain.passed


def test_the_rssi_median_is_a_true_unrounded_median() -> None:
    def hist(values: list[int]) -> np.ndarray:
        h = np.zeros((1, sc.RSSI_BINS), dtype=np.int64)
        for v in values:
            h[0, -v] += 1
        return h
    assert sc.hist_median(hist([-40, -41]))[0] == -40.5                 # even count: the mean of the two middle values
    assert sc.hist_median(hist([-40, -41, -43]))[0] == -41.0
    assert sc.hist_median(hist([-45] * 3 + [-46] * 3))[0] == -45.5
    assert np.isnan(sc.hist_median(np.zeros((1, sc.RSSI_BINS), dtype=np.int64))[0])


def test_the_cli_exit_codes_the_input_is_never_modified_and_json_is_refused_under_data(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    good = write_soak(tmp_path / "good.jsonl")
    bad = write_soak(tmp_path / "bad.jsonl", fps=50)
    before = hashlib.sha256(good.read_bytes()).hexdigest()
    out_json = tmp_path / "result.json"
    assert sc.main([str(good), *CLI_SMALL, "--json", str(out_json)]) == 0
    printed = capsys.readouterr().out
    assert "VERDICT: PASS" in printed and "NON-SPEC PARAMETERS" in printed
    assert json.loads(out_json.read_text(encoding="utf-8"))["passed"] is True
    assert hashlib.sha256(good.read_bytes()).hexdigest() == before
    assert sc.main([str(bad), *CLI_SMALL]) == 1 and "VERDICT: FAIL" in capsys.readouterr().out
    under_data = ROOT / "data" / "soak_check_must_not_exist.json"
    assert sc.main([str(good), *CLI_SMALL, "--json", str(under_data)]) == 2 and not under_data.exists()
    assert sc.main([str(tmp_path / "missing.jsonl")]) == 2
    empty = tmp_path / "empty.jsonl"
    empty.write_text(json.dumps(HEADER) + "\n", encoding="utf-8")
    assert sc.main([str(empty), *CLI_SMALL]) == 2
    block1 = (soak_end() + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert sc.main([str(good), *CLI_SMALL, "--block1-start", block1]) == 0
    assert sc.main([str(good), *CLI_SMALL, "--block1-start", block1, "--change", "router rebooted and channel changed"]) == 1


SMOKE = sorted((ROOT / "data" / "datasets" / "smoke-test").glob("*.jsonl")) if (ROOT / "data" / "datasets" / "smoke-test").is_dir() else []


@pytest.mark.skipif(not SMOKE, reason="data/datasets/smoke-test is local, gitignored data and is not present")
def test_the_checker_on_the_real_smoke_test_recording_with_relaxed_parameters() -> None:
    """126 s of real frames: relaxed parameters (tests only) exercise every check on real data, read-only.

    The rates are steady on all four nodes, but node 1's RSSI has a real held step of about 9 dB near +20 s (its first-30-s median is -36 dBm,
    its per-minute median -27 dBm): the RSSI condition correctly fails for node 1 and only for node 1. The cause of that step is not known."""
    path = [p for p in SMOKE if ".part" not in p.name][0]
    res = sc.check_soak(sc.sr.expand_parts(path), min_hours=0.03, ref_s=30, window_s=10)
    assert {c.name for c in res.checks} >= {f"{kind}, node {n}" for kind in ("level", "rate", "RSSI", "per-recording gates") for n in (1, 2, 3, 4)}
    assert failing(res) == ["RSSI, node 1"], [c for c in res.checks if not c.ok]
    assert "first at +" in next(c.detail for c in res.checks if c.name == "RSSI, node 1") and not res.passed
    assert res.report_only["frames_with_seq"] == res.report_only["frames"] > 1000
    assert any("NON-SPEC PARAMETERS" in w for w in res.warnings)
