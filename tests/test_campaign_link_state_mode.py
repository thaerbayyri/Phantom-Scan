"""c2 amendment A1: the link-state mode of the campaign validator (scripts/presence_eval/campaign.py), default OFF.

Default mode ("c1") must behave exactly as before; the real-folder byte-identity proof (text and JSON output on the c1 campaign) is recorded in the
ledger. "c2" replaces the first-60-s between-block check with whole-block medians (unrounded, fail at 6 dB or more) against the adjacent empty block,
and keeps every in-block gate and the all-six-block-types check. Synthetic campaigns in pytest temp folders only; nothing under data/.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import test_campaign_validator as tcv  # sibling test module: its synthetic-campaign builders (pytest puts tests/ on sys.path)
from scripts.presence_eval import campaign as cp


def const(value: float):
    return lambda node, s: value


def halves(first: float, second: float):
    """RSSI `first` for the first half of the block's seconds and `second` for the rest: an even frame count, so the median is their mean."""
    return lambda node, s: first if s < tcv.SECONDS // 2 else second


def build(tmp_path: Path, rssi: dict[str, object] | None = None, fps: dict[str, object] | None = None) -> Path:
    root = tmp_path / "c"
    root.mkdir(parents=True, exist_ok=True)
    (root / "campaign.json").write_text(json.dumps({"schema_version": 1, "campaign_id": "t", "nodes_expected": list(tcv.NODES)}), encoding="utf-8")
    for i, btype in enumerate(cp.BLOCK_RULES):
        kw: dict = {"rssi_fn": (rssi or {}).get(btype, const(-40.0))}
        if fps and btype in fps:
            kw["fps_fn"] = fps[btype]
        tcv.write_block(root, btype, i, **kw)
    return root


def link_failures(rep: cp.Report) -> list[str]:
    return [f for f in rep.failures if "link-state check (c2)" in f]


def facts(btype: str, ref: float, median: float, ls: str = "L1") -> dict:
    return {"block_type": btype, "link_state_id": ls, "nodes": {1: {"ref_rssi": ref, "median_rssi": median}}}


def report_with(blocks: dict[str, dict]) -> cp.Report:
    rep = cp.Report()
    rep.blocks = blocks
    return rep


# ── default mode is unchanged ──────────────────────────────────────────────────────────────────────────────────────

def test_default_mode_is_the_frozen_behaviour_and_adds_nothing(tmp_path: Path) -> None:
    root = build(tmp_path)
    default = cp.validate(root, tcv.SHORT)
    explicit = cp.validate(root, tcv.SHORT, link_state_mode="c1")
    assert (default.failures, default.warnings, default.notes, default.blocks) == (explicit.failures, explicit.warnings, explicit.notes, explicit.blocks)
    assert default.ok, default.failures
    assert not any("median_rssi" in nf for f in default.blocks.values() for nf in f["nodes"].values())
    assert not any("c2" in n for n in default.notes)


def test_default_mode_still_applies_the_first_60_second_between_block_rule(tmp_path: Path) -> None:
    rep = report_with({"01": facts("empty_1", -40, -40), "04": facts("still", -47, -41)})
    cp._validate_link_states(rep)  # default argument
    assert any("undeclared link change between blocks 01 and 04" in f for f in rep.failures)


def test_an_unknown_mode_is_refused(tmp_path: Path) -> None:
    root = build(tmp_path)
    with pytest.raises(ValueError):
        cp.validate(root, tcv.SHORT, link_state_mode="c3")
    with pytest.raises(SystemExit) as exc:
        cp.main([str(root), "--link-state-mode", "c3"])
    assert exc.value.code == 2


# ── c2 mode ────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_c2_mode_records_the_whole_block_median_and_passes_a_complete_campaign(tmp_path: Path) -> None:
    rep = cp.validate(build(tmp_path), tcv.SHORT, link_state_mode="c2")
    assert rep.ok, rep.failures
    assert all(nf["median_rssi"] == -40.0 for f in rep.blocks.values() for nf in f["nodes"].values())
    assert any("link-state mode c2" in n for n in rep.notes)


@pytest.mark.parametrize("still_rssi, expected_diff, should_fail", [
    (halves(-45, -46), 5.5, False),   # median -45.5: 5.5 dB from -40, passes only if the median is compared unrounded (rounded to -46 it would fail)
    (const(-45), 5.0, False),
    (const(-46), 6.0, True),          # exactly 6.00 dB fails: the frozen convention, fails at 6 dB or more
    (halves(-46, -47), 6.5, True),
])
def test_boundary_passes_below_6_db_and_fails_at_6_db_unrounded(tmp_path: Path, still_rssi, expected_diff: float, should_fail: bool) -> None:
    rep = cp.validate(build(tmp_path, rssi={"still": still_rssi}), tcv.SHORT, link_state_mode="c2")
    failures = link_failures(rep)
    assert bool(failures) is should_fail, (expected_diff, failures)
    if should_fail:
        assert f"difference {expected_diff:.2f} dB" in failures[0]
        assert "invalid and is not analysed" in failures[0]


def test_c2_ignores_the_first_60_seconds_while_c1_does_not() -> None:
    blocks = {"01": facts("empty_1", ref=-40, median=-40), "04": facts("still", ref=-47, median=-41)}  # first 60 s 7 dB apart, whole-block medians 1 dB apart
    c1, c2 = report_with(blocks), report_with(blocks)
    cp._validate_link_states(c1, "c1")
    cp._validate_link_states(c2, "c2")
    assert any("undeclared link change" in f for f in c1.failures)
    assert link_failures(c2) == []


def test_each_block_is_compared_with_its_own_adjacent_empty_block() -> None:
    base = {"01": facts("empty_1", -40, -40.0), "05": facts("empty_2", -44, -44.0)}
    # fan_with_person uses empty_2: 5 dB from empty_2 passes, although it is 9 dB from empty_1 (which would fail if it were compared with that)
    ok = report_with({**base, "06": facts("fan_with_person", -49, -49.0)})
    cp._validate_link_states(ok, "c2")
    assert link_failures(ok) == []
    # fan_alone uses empty_1: 6 dB from empty_1 fails, although it is only 2 dB from empty_2
    bad = report_with({**base, "02": facts("fan_alone", -46, -46.0)})
    cp._validate_link_states(bad, "c2")
    assert len(link_failures(bad)) == 1 and "block 02" in link_failures(bad)[0] and "vs 01" in link_failures(bad)[0]


def test_empty_1_and_empty_2_are_compared_with_each_other() -> None:
    rep = report_with({"01": facts("empty_1", -40, -40.0), "05": facts("empty_2", -46, -46.0)})
    cp._validate_link_states(rep, "c2")
    assert len(link_failures(rep)) == 1 and "block 05" in link_failures(rep)[0] and "vs 01" in link_failures(rep)[0]
    near = report_with({"01": facts("empty_1", -40, -40.0), "05": facts("empty_2", -45, -45.0)})
    cp._validate_link_states(near, "c2")
    assert link_failures(near) == []


def test_a_person_induced_shift_of_6_db_fails_the_block_and_a_smaller_one_does_not() -> None:
    for btype in ("walking", "still", "fan_with_person"):
        ref_block = "empty_2" if btype == "fan_with_person" else "empty_1"
        bad = report_with({"E": facts(ref_block, -40, -40.0), "P": facts(btype, -46, -46.0)})
        cp._validate_link_states(bad, "c2")
        assert len(link_failures(bad)) == 1, btype
        good = report_with({"E": facts(ref_block, -40, -40.0), "P": facts(btype, -45, -45.0)})
        cp._validate_link_states(good, "c2")
        assert link_failures(good) == [], btype


def test_a_missing_adjacent_empty_block_is_not_compared_and_only_the_all_six_check_speaks() -> None:
    rep = report_with({"01": facts("empty_1", -40, -40.0), "06": facts("fan_with_person", -60, -60.0)})
    cp._validate_link_states(rep, "c2")
    assert link_failures(rep) == []
    assert any("no link state contains all six block types" in f for f in rep.failures)


def test_blocks_in_different_link_states_are_never_compared() -> None:
    rep = report_with({"01": facts("empty_1", -40, -40.0, ls="L1"), "02": facts("fan_alone", -70, -70.0, ls="L2")})
    cp._validate_link_states(rep, "c2")
    assert link_failures(rep) == []


def test_nodes_without_a_median_are_skipped() -> None:
    a = {"block_type": "empty_1", "link_state_id": "L1", "nodes": {1: {"median_rssi": None}, 2: {"median_rssi": -40.0}}}
    b = {"block_type": "still", "link_state_id": "L1", "nodes": {1: {"median_rssi": -90.0}, 2: {"median_rssi": -41.0}}}
    rep = report_with({"01": a, "04": b})
    cp._validate_link_states(rep, "c2")
    assert link_failures(rep) == []


def test_the_in_block_gates_and_the_all_six_check_still_apply_in_c2_mode(tmp_path: Path) -> None:
    collapse = lambda node, s: tcv.FPS if s < 30 else 5  # noqa: E731 - a held rate collapse inside one block
    rep = cp.validate(build(tmp_path, fps={"walking": collapse}), tcv.SHORT, link_state_mode="c2")
    assert any("undeclared link change inside the block" in f and "[03_walking]" in f for f in rep.failures)
    shutil.rmtree(tmp_path / "c" / "blocks" / "05_empty_2")
    rep2 = cp.validate(tmp_path / "c", tcv.SHORT, link_state_mode="c2")
    assert any("no link state contains all six block types" in f for f in rep2.failures)


def test_the_cli_accepts_the_c2_flag_and_prints_its_note(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = build(tmp_path)
    code = cp.main([str(root), "--link-state-mode", "c2"])
    out = capsys.readouterr().out
    assert "link-state mode c2" in out
    assert code in (0, 1)  # the synthetic 70 s blocks are below the real minimums; the point here is the flag and the note
    cp.main([str(root)])
    assert "link-state mode c2" not in capsys.readouterr().out
