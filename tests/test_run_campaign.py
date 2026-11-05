"""run_campaign: refusals, labelling, and a dry run on the EXISTING recordings against the numbers stored by the current repo tooling.

The real-data tests read data/datasets/room1 read-only and are skipped when it is absent. Everything else uses temp dirs."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from scripts.presence_eval import run_campaign as rc
from scripts.presence_eval.movement import fused_scores
from scripts.presence_eval.recordings import load_recording
from scripts.presence_eval.stats import auc
from scripts.presence_eval.tables import ROOM_DIR, load_tables, group_recordings

from test_campaign_validator import SHORT, write_campaign          # tests/ is on sys.path (pytest rootdir mode)

REPO = rc.REPO
STORED = REPO / "reports" / "fix-2026-11" / "results" / "movement_score.json"
AUC_TOL = 1e-9            # same functions on the same windows: the point estimates must agree to float precision


def committed() -> dict:
    return {"path": "PREREG.md", "sha256": "0" * 64, "tracked": True, "clean": True, "commit": "abc1234"}


@pytest.fixture(scope="module")
def synthetic(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("rc") / "campaign-test"
    write_campaign(root)
    return root


# ---- refusals ----------------------------------------------------------------------------------


def test_an_invalid_campaign_is_refused_and_nothing_is_written(synthetic: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    with pytest.raises(rc.Refused) as e:
        rc.run(synthetic, out, allow_uncommitted_prereg=True)       # the real minimums refuse the 70 s blocks
    assert e.value.code == 1 and "INVALID" in str(e.value)
    assert not out.exists()


def test_an_uncommitted_prereg_is_refused(synthetic: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(rc, "prereg_state", lambda *a, **k: {**committed(), "tracked": False, "clean": False, "commit": None})
    with pytest.raises(rc.Refused) as e:
        rc.run(synthetic, tmp_path / "out", min_minutes=SHORT)
    assert e.value.code == 3 and "commit it BEFORE analysing" in str(e.value)
    monkeypatch.setattr(rc, "prereg_state", lambda *a, **k: {**committed(), "clean": False})      # tracked but modified
    with pytest.raises(rc.Refused):
        rc.run(synthetic, tmp_path / "out", min_minutes=SHORT)


def test_the_report_is_refused_under_data(synthetic: Path, monkeypatch) -> None:
    monkeypatch.setattr(rc, "prereg_state", lambda *a, **k: committed())
    with pytest.raises(rc.Refused) as e:
        rc.run(synthetic, REPO / "data" / "sessions" / "campaign-out", min_minutes=SHORT)
    assert e.value.code == 2 and not (REPO / "data" / "sessions" / "campaign-out").exists()


def test_prereg_state_in_a_throwaway_git_repo(tmp_path: Path) -> None:
    def git(*a: str) -> None:
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=tmp_path, check=True, capture_output=True)
    f = tmp_path / "P.md"
    f.write_text("frozen", encoding="utf-8")
    git("init", "-q")
    assert rc.prereg_state(f, tmp_path)["tracked"] is False                         # untracked
    git("add", "P.md")
    git("commit", "-q", "-m", "prereg")
    s = rc.prereg_state(f, tmp_path)
    assert s["tracked"] and s["clean"] and s["commit"] and len(s["sha256"]) == 64
    f.write_text("frozen but edited", encoding="utf-8")
    s2 = rc.prereg_state(f, tmp_path)
    assert s2["tracked"] and not s2["clean"] and s2["sha256"] != s["sha256"]        # modified after the freeze


def test_the_real_prereg_file_has_every_owner_item_resolved_and_the_code_matches_it() -> None:
    text = rc.PREREG.read_text(encoding="utf-8")
    assert "[OWNER TO" not in text                                                   # all items resolved 2026-11-04 (PREREG section 7)
    for cid in ("C1b", "C2b", "C7"):
        assert cid in text
    assert "report-only" in text and "10** min" in text and "1.5 s" in text
    assert "K7" in text and "parity-aware decor" in text and "K8" in text and "anti-aliased" in text
    assert rc.C1_LOWER_MIN == rc.C1B_LOWER_MIN == rc.C2B_LOWER_MIN == 0.80          # C1, C1b, C2b: "≥ 0.80" in the table
    assert rc.cp.BLOCK_RULES["fan_with_person"][0] == 10.0


# ---- labelling and the end-to-end path on a tiny synthetic campaign -----------------------------


def test_end_to_end_labels_every_unmeasurable_number(synthetic: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(rc, "prereg_state", lambda *a, **k: committed())
    out = tmp_path / "out"
    rep = rc.run(synthetic, out, min_minutes=SHORT)
    assert rep["conclusion"].startswith("no candidate met the criteria") and rep["candidates_meeting_criteria"] == []
    md = (out / "campaign-report.md").read_text(encoding="utf-8")
    assert "[TO BE MEASURED]" in md and "[OWNER TO" not in md and "report-only" in md and rep["prereg"]["sha256"] in md
    assert "no accuracy, detection-rate or false-alarm figure is claimed" in md
    for cand, r in rep["candidates"].items():                                        # 46 windows per block < 60: nothing may be reported as measured
        assert r["walking_vs_empty_2"]["status"] == "[TO BE MEASURED]", cand
        assert r["criteria"]["verdict"] == "[TO BE MEASURED]"
        assert r["criteria"]["C1b_still"] is None and r["criteria"]["C2b_fan_with_person"] is None      # not computable from 46 windows, never guessed
        assert r["criteria"]["C7"].startswith("report-only")
    assert {"decor_parity/fused4", "perturb_agc/fused12", "move_decor_L45/fused4"} <= set(rep["candidates"])
    assert json.loads((out / "campaign_report.json").read_text(encoding="utf-8"))["link_state"] == "L1"


def test_a_dry_run_is_flagged_in_the_report(synthetic: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(rc, "prereg_state", lambda *a, **k: {**committed(), "tracked": False, "clean": False, "commit": None})
    rep = rc.run(synthetic, tmp_path / "o", allow_uncommitted_prereg=True, min_minutes=SHORT)
    assert rep["dry_run_uncommitted_prereg"] is True
    assert "DRY RUN" in (tmp_path / "o" / "campaign-report.md").read_text(encoding="utf-8")


def test_the_verdict_logic_on_hand_built_scores() -> None:
    rng = np.random.default_rng(3)
    quiet = lambda n: rng.normal(0, 1, n)                      # noqa: E731
    # C2 is an interval (PREREG section 4): it fails only if the fan is flagged significantly more than the empty
    good = {"empty_1": quiet(800), "empty_2": quiet(800), "walking": quiet(400) + 6.0, "fan_alone": quiet(300) - 1.0, "still": quiet(300) + 2.0}
    r = rc.evaluate({"good": good})["good"]["criteria"]
    assert r["C4"] is True and r["C1"] is True and r["C3"] is True and r["C2"] is True and r["verdict"] == "MEETS"
    drift = {**good, "empty_2": quiet(800) + 3.0}                  # the second empty drifted: C4 fails, so the candidate cannot meet the criteria
    rd = rc.evaluate({"drift": drift})["drift"]["criteria"]
    assert rd["C4"] is False and rd["verdict"] == "DOES NOT MEET"
    weak = {**good, "walking": quiet(400) + 0.1}                   # walking barely separates: C1 fails
    assert rc.evaluate({"weak": weak})["weak"]["criteria"]["C1"] is False
    fan = {**good, "fan_alone": quiet(300) + 5.0}                  # the fan is flagged more than the empty: C2 fails
    assert rc.evaluate({"fan": fan})["fan"]["criteria"]["C2"] is False


def _flagged_exactly(rng: np.random.Generator, n: int, k: int, thr: float) -> np.ndarray:
    """n scores of which exactly k (spread out, 20 windows apart) are above thr and the rest well below."""
    x = np.minimum(rng.normal(0, 1, n), thr - 0.3)
    x[np.arange(k) * 20 + 3] = thr + 1.0
    return x


def test_c2_is_an_interval_a_noisy_point_excess_is_not_a_failure() -> None:
    rng = np.random.default_rng(11)
    e1 = rng.normal(0, 1, 1000)
    thr = float(np.quantile(e1, 0.99))
    e2 = _flagged_exactly(rng, 800, 8, thr)                       # 1.0 % flagged at alpha 1 %
    fan = _flagged_exactly(rng, 300, 6, thr)                      # 2.0 %: above the empty's share as a point, but 6 windows cannot show it is more
    r = rc.evaluate({"c": {"empty_1": e1, "empty_2": e2, "fan_alone": fan}})["c"]
    a = r["rates"]["alpha_0.01"]
    assert a["fan_alone_flagged_share"] > a["empty_2_flagged_share"]                # the old strict point comparison would have failed here
    d = a["fan_minus_empty_2"]
    assert d["d"] == pytest.approx(0.02 - 0.01) and d["lo"] <= 0.0 < d["hi"]
    assert r["criteria"]["C2"] is True


def test_c2_fails_only_when_the_lower_bound_is_above_zero() -> None:
    rng = np.random.default_rng(12)
    e1, e2 = rng.normal(0, 1, 1000), rng.normal(0, 1, 800)
    loud_fan = rng.normal(0, 1, 300) + 5.0                        # flagged far more than the empty at both alphas
    r = rc.evaluate({"c": {"empty_1": e1, "empty_2": e2, "fan_alone": loud_fan}})["c"]
    assert r["rates"]["alpha_0.01"]["fan_minus_empty_2"]["lo"] > 0 and r["rates"]["alpha_0.05"]["fan_minus_empty_2"]["lo"] > 0
    assert r["criteria"]["C2"] is False
    same = rc.evaluate({"c": {"empty_1": e1, "empty_2": e2, "fan_alone": e2.copy()}})["c"]            # identical distribution: d = 0, lower bound below 0
    assert same["rates"]["alpha_0.01"]["fan_minus_empty_2"]["d"] == 0.0 and same["criteria"]["C2"] is True


def test_the_rate_difference_bootstrap_is_deterministic_and_has_the_right_sign() -> None:
    from scripts.presence_eval.stats import block_bootstrap_rate_diff
    a = np.zeros(300, dtype=bool); a[::3] = True                   # 33 %
    b = np.zeros(300, dtype=bool); b[::30] = True                  # 3.3 %
    r1, r2 = block_bootstrap_rate_diff(a, b), block_bootstrap_rate_diff(a, b)
    assert r1 == r2 and r1["d"] == pytest.approx(a.mean() - b.mean()) and r1["lo"] > 0.2
    assert block_bootstrap_rate_diff(b, a)["hi"] < -0.2
    assert np.isnan(block_bootstrap_rate_diff(np.zeros(0, bool), b)["d"])


def test_c1b_and_c2b_are_separate_claims_that_do_not_change_the_verdict() -> None:
    rng = np.random.default_rng(13)
    quiet = lambda n: rng.normal(0, 1, n)                      # noqa: E731
    base = {"empty_1": quiet(800), "empty_2": quiet(800), "walking": quiet(400) + 6.0, "fan_alone": quiet(300) - 1.0}
    strong = {**base, "still": quiet(300) + 3.0, "fan_with_person": quiet(300) + 6.0}
    c = rc.evaluate({"s": strong})["s"]["criteria"]
    assert c["C1b_still"] is True and c["C2b_fan_with_person"] is True and c["verdict"] == "MEETS"
    weak = {**base, "still": quiet(300) + 0.1, "fan_with_person": quiet(300) + 0.1}                   # both separate poorly
    c = rc.evaluate({"w": weak})["w"]["criteria"]
    assert c["C1b_still"] is False and c["C2b_fan_with_person"] is False
    assert c["verdict"] == "MEETS"                                                               # ... and neither can stop the candidate meeting C1-C3
    assert rc.evaluate({"n": base})["n"]["criteria"]["C1b_still"] is None                           # no still block: not computable, not guessed


def test_c7_is_report_only_both_directions_in_seconds_and_cannot_change_the_verdict() -> None:
    rng = np.random.default_rng(14)
    quiet = lambda n: rng.normal(0, 1, n)                      # noqa: E731
    blocks = {"empty_1": quiet(800), "empty_2": quiet(800), "walking": quiet(400) + 6.0, "fan_alone": quiet(300) - 1.0, "still": quiet(300) + 0.5}
    r = rc.evaluate({"c": blocks})["c"]
    a = r["rates"]["alpha_0.01"]
    for key in ("walking_unflagged_seconds", "still_unflagged_seconds", "empty_2_flagged_seconds", "fan_alone_flagged_seconds"):
        assert a[key] is not None and a[key] >= 0.0                                               # both failure directions, in seconds, measured
    assert a["still_unflagged_seconds"] > a["walking_unflagged_seconds"]                            # a barely-separated still block is mostly missed
    assert r["criteria"]["C7"].startswith("report-only") and "no limit" in r["criteria"]["C7"]
    assert r["criteria"]["verdict"] == "MEETS"                                                    # large still miss seconds, same verdict


def test_thresholds_are_fitted_on_the_first_empty_block_only() -> None:
    rng = np.random.default_rng(4)
    e1, e2 = rng.normal(0, 1, 900), rng.normal(0, 1, 900)
    r = rc.evaluate({"c": {"empty_1": e1, "empty_2": e2}})["c"]["rates"]["alpha_0.01"]
    assert r["threshold"] == pytest.approx(float(np.quantile(e1, 0.99)))
    e2b = e2 + 100.0                                                # nothing about empty_2 can move the threshold
    assert rc.evaluate({"c": {"empty_1": e1, "empty_2": e2b}})["c"]["rates"]["alpha_0.01"]["threshold"] == r["threshold"]


def test_cli_exit_codes(synthetic: Path, tmp_path: Path, capsys) -> None:
    assert rc.main([str(tmp_path / "missing")]) == 2
    assert rc.main([str(synthetic), "--out", str(tmp_path / "o")]) == 1          # validator refuses the 70 s blocks: exit 1
    assert "REFUSED" in capsys.readouterr().err


def test_the_module_never_writes_outside_the_report_dir() -> None:
    import inspect
    src = inspect.getsource(rc)
    assert src.count(".write_text(") == 1 and src.count("dump_json(") == 1
    assert "_under_data(out_dir)" in src


# ---- dry run on the existing recordings: same numbers as the current repo tooling ------------------


needs_data = pytest.mark.skipif(not ROOM_DIR.is_dir() or not STORED.is_file(), reason="recordings or stored movement results absent")


def _find(subject: str, label: str):
    groups = group_recordings(ROOM_DIR)
    names = [n for n in groups if f"__{subject}__{label}__" in n]
    assert len(names) == 1, (subject, label, names)
    return groups[names[0]]


@pytest.fixture(scope="module")
def legacy_segments():
    from scripts.presence_eval.tables import load_all
    return rc.legacy_epoch_segments(load_all(ROOM_DIR), (1, 2))


def _epoch_segments(segs: dict, epoch: str, label: str) -> list:
    return [s for s in segs.values() if rc.ee.epoch_of(s) == epoch and s.label == label]


@needs_data
def test_dry_run_walking_vs_empty_matches_the_stored_movement_result(legacy_segments) -> None:
    """E05 in results/movement_score.json (variant N1+N2/decor/L45): walking AUC 0.7777917..., 101 walking and 79 empty windows.
    The recordings contain link steps, so the EXISTING epoch segmentation supplies the segments; run_campaign's scoring and evaluation layer is what is compared."""
    stored = json.loads(STORED.read_text(encoding="utf-8"))["variants"]["N1+N2/decor/L45"]["within_epoch"]["E05"]["auc"]["walking"]
    (walking,), (empty,) = _epoch_segments(legacy_segments, "E05", "walking"), _epoch_segments(legacy_segments, "E05", "empty")
    cand = "move_decor_L45/fused12"
    sw, se = rc.candidate_scores(walking, None)[cand], rc.candidate_scores(empty, None)[cand]
    got = rc.evaluate({cand: {"empty_1": se, "walking": sw}})[cand]["walking_vs_empty_1"]
    assert got["status"] == "measured"
    assert (got["n_pos"], got["n_neg"]) == (stored["n_pos"], stored["n_neg"]) == (101, 79)
    assert got["auc"] == pytest.approx(stored["auc"], abs=AUC_TOL)
    pos, neg = fused_scores(walking, "decor", 45, (1, 2))[1], fused_scores(empty, "decor", 45, (1, 2))[1]      # the repo's own function, called directly
    assert got["auc"] == pytest.approx(auc(pos[np.isfinite(pos)], neg[np.isfinite(neg)]), abs=AUC_TOL)


@needs_data
def test_dry_run_empty_vs_empty_control_matches_the_stored_pair_auc(legacy_segments) -> None:
    """E07 in results/movement_score.json: s8 vs s9, point AUC 0.5400752...; the control passes. Bootstrap settings differ (300 vs 1000), so only the point AUC is compared."""
    stored = json.loads(STORED.read_text(encoding="utf-8"))["variants"]["N1+N2/decor/L45"]["within_epoch"]["E07"]["empty_vs_empty_control"]
    pair = stored["pairs"][0]
    empties = sorted(_epoch_segments(legacy_segments, "E07", "empty"), key=lambda s: s.rid)
    assert [s.rid for s in empties] == [pair["a"], pair["b"]]
    cand = "move_decor_L45/fused12"
    sc = [rc.candidate_scores(s, None)[cand] for s in empties]
    got = rc.evaluate({cand: {"empty_1": sc[0], "empty_2": sc[1]}})[cand]["c4_empty_vs_empty"]
    assert got["passes"] is True and stored["passes"] is True
    assert got["pairs"][0]["auc"] == pytest.approx(pair["auc"], abs=AUC_TOL)
    assert got["worst_symmetric_upper_bound"] == pytest.approx(stored["worst_symmetric_upper_bound"], abs=0.05)   # bootstrap noise only
