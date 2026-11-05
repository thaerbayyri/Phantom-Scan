"""Recording-campaign validator: every refusal path, on small synthetic campaigns in the recorder's own JSONL format. Writes only to temp dirs."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from scripts.presence_eval import campaign as cp

SECONDS = 70
FPS = 25
MIN_MIN = SECONDS / 60.0 - 0.05            # short test blocks: the minimum is lowered for the test, the rules are otherwise the real ones
SHORT = {t: MIN_MIN for t in cp.BLOCK_RULES}                         # every minimum lowered for the 70 s test blocks; the real rules are asserted separately
NODES = (1, 2, 3, 4)
BASE_MS = 1_794_000_000_000
LABEL = {"empty_1": "empty", "fan_alone": "empty_fan", "walking": "walking", "still": "still", "empty_2": "empty", "fan_with_person": "still"}
FOLDERS = {"empty_1": "01_empty_1", "fan_alone": "02_fan_alone", "walking": "03_walking", "still": "04_still", "empty_2": "05_empty_2", "fan_with_person": "06_fan_with_person"}
STAMP = "20261110T08{:02d}00Z"


def write_recording(block_dir: Path, name: str, label: str, t0_ms: int, *, seconds=SECONDS, fps=FPS, nodes=NODES, rssi_fn=None, fps_fn=None, summary=True) -> None:
    rng = np.random.default_rng(t0_ms % 1000)
    path = block_dir / f"{name}.jsonl"
    rssi_fn = rssi_fn or (lambda node, s: -40 - node)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({"type": "header", "schema": 2, "roomId": "room1", "subjectId": "s11", "label": label, "count": 0, "notes": "", "startedAtMs": t0_ms, "part": 1, "geometry": {}}) + "\n")
        for node in nodes:
            for s in range(seconds):
                n = int(fps_fn(node, s)) if fps_fn else fps
                for k in range(n):
                    fh.write(json.dumps({"type": "frame", "t": t0_ms + s * 1000 + int(k * 1000 / max(n, 1)), "n": node, "rssi": int(rssi_fn(node, s)),
                                         "a": [round(float(x), 1) for x in 10 + rng.normal(0, 0.3, 51)]}) + "\n")
    if summary:
        (block_dir / f"{name}.summary.json").write_text(json.dumps({"frames": 1}), encoding="utf-8")


def block_json(btype: str, idx: int, name: str, **over) -> dict:
    meta = {"schema_version": 1, "block_id": FOLDERS[btype], "block_type": btype, "recording": name,
            "start_utc": "2026-11-10T08:00:00Z", "stop_utc": "2026-11-10T08:01:10Z", "link_state_id": "L1",
            "person_count": 0 if "empty" in btype or btype == "fan_alone" else 1, "person_present": btype in ("walking", "still", "fan_with_person"),
            "fan_on": "fan" in btype, "fan_position": None, "subject": None, "link_state_notes": "", "link_change_events": [], "entry_log": "entry-log.txt", "notes": ""}
    meta.update(over)
    return meta


def write_block(root: Path, btype: str, idx: int, **kw) -> Path:
    d = root / "blocks" / FOLDERS[btype]
    d.mkdir(parents=True, exist_ok=True)
    name = f"room1__s11__{LABEL[btype]}__{STAMP.format(idx)}"
    write_recording(d, name, LABEL[btype], BASE_MS + idx * 600_000, **kw)
    (d / "block.json").write_text(json.dumps(block_json(btype, idx, name)), encoding="utf-8")
    if btype in ("empty_1", "empty_2", "fan_alone"):
        (d / "entry-log.txt").write_text("2026-11-10T07:59:30Z operator room checked empty\n2026-11-10T08:01:20Z operator left the building\n", encoding="utf-8")
    return d


def write_campaign(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "campaign.json").write_text(json.dumps({"schema_version": 1, "campaign_id": "test", "nodes_expected": list(NODES)}), encoding="utf-8")
    for i, bt in enumerate(cp.BLOCK_RULES):
        write_block(root, bt, i)


@pytest.fixture(scope="module")
def valid_root(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("campaign") / "c1"
    write_campaign(root)
    return root


@pytest.fixture
def camp(valid_root: Path, tmp_path: Path) -> Path:
    dst = tmp_path / "c"
    shutil.copytree(valid_root, dst)
    return dst


def fails(rep: cp.Report, needle: str) -> bool:
    return any(needle in f for f in rep.failures)


def tree_hash(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}


def test_a_complete_campaign_is_valid(valid_root: Path) -> None:
    rep = cp.validate(valid_root, SHORT)
    assert rep.ok, rep.failures
    assert set(rep.blocks) == set(FOLDERS.values())
    assert not any("not enforced" in w for w in rep.warnings)        # every block type now has a registered minimum


def test_the_real_minimums_refuse_short_blocks(valid_root: Path) -> None:
    rep = cp.validate(valid_root)                                      # no override: 70 s blocks are far below 60 / 5 / 10 minutes
    assert fails(rep, "shorter than the required 60 min for empty_1") and fails(rep, "shorter than the required 5 min for walking")
    assert fails(rep, "shorter than the required 10 min for fan_with_person")


def test_the_fan_with_person_minimum_is_enforced_when_only_the_other_minimums_are_lowered(valid_root: Path) -> None:
    others = {t: MIN_MIN for t in cp.BLOCK_RULES if t != "fan_with_person"}
    rep = cp.validate(valid_root, others)
    assert fails(rep, "shorter than the required 10 min for fan_with_person")
    assert not [f for f in rep.failures if "shorter than the required" in f and "fan_with_person" not in f]


def test_missing_campaign_json_is_refused(camp: Path) -> None:
    (camp / "campaign.json").unlink()
    assert fails(cp.validate(camp, SHORT), "campaign.json missing")


def test_missing_block_json_is_refused(camp: Path) -> None:
    (camp / "blocks" / "03_walking" / "block.json").unlink()
    assert fails(cp.validate(camp, SHORT), "block.json of 03_walking missing")


def test_missing_recorder_summary_sidecar_is_refused(camp: Path) -> None:
    next((camp / "blocks" / "04_still").glob("*.summary.json")).unlink()
    assert fails(cp.validate(camp, SHORT), "recorder sidecar missing")


def test_empty_block_without_entry_log_is_refused(camp: Path) -> None:
    (camp / "blocks" / "05_empty_2" / "entry-log.txt").unlink()
    assert fails(cp.validate(camp, SHORT), "entry log missing or empty")


def test_entry_log_with_one_line_is_refused(camp: Path) -> None:
    (camp / "blocks" / "01_empty_1" / "entry-log.txt").write_text("2026-11-10T08:00:00Z operator room checked empty\n", encoding="utf-8")
    assert fails(cp.validate(camp, SHORT), "at least a start line and an end line")


def test_block_shorter_than_required_is_refused(camp: Path) -> None:
    rep = cp.validate(camp, {**SHORT, "walking": 5.0})
    assert fails(rep, "[03_walking] block is 1.2 min, shorter than the required 5 min for walking")


def test_frame_rate_below_the_band_is_refused(camp: Path) -> None:
    d = camp / "blocks" / "02_fan_alone"
    name = json.loads((d / "block.json").read_text())["recording"]
    write_recording(d, name, "empty_fan", BASE_MS + 600_000, fps=10)
    assert fails(cp.validate(camp, SHORT), "median rate 10.0 fps is outside [20, 100]")


def test_frame_rate_above_the_band_is_refused(camp: Path) -> None:
    d = camp / "blocks" / "02_fan_alone"
    name = json.loads((d / "block.json").read_text())["recording"]
    write_recording(d, name, "empty_fan", BASE_MS + 600_000, fps=120)
    assert fails(cp.validate(camp, SHORT), "outside [20, 100]")


def test_a_held_rssi_step_inside_a_block_is_refused(camp: Path) -> None:
    d = camp / "blocks" / "03_walking"
    name = json.loads((d / "block.json").read_text())["recording"]
    write_recording(d, name, "walking", BASE_MS + 1_200_000, rssi_fn=lambda node, s: -40 - node - (8 if (node == 2 and s >= 35) else 0))
    rep = cp.validate(camp, SHORT)
    assert fails(rep, "undeclared link change inside the block") and fails(rep, "[03_walking]")


def test_a_rate_collapse_inside_a_block_is_refused(camp: Path) -> None:
    d = camp / "blocks" / "04_still"
    name = json.loads((d / "block.json").read_text())["recording"]
    write_recording(d, name, "still", BASE_MS + 1_800_000, fps_fn=lambda node, s: FPS if (node != 3 or s < 35) else 8)
    assert fails(cp.validate(camp, SHORT), "rate_collapse")


def test_a_missing_node_is_refused(camp: Path) -> None:
    d = camp / "blocks" / "01_empty_1"
    name = json.loads((d / "block.json").read_text())["recording"]
    write_recording(d, name, "empty", BASE_MS, nodes=(1, 2, 3))
    assert fails(cp.validate(camp, SHORT), "[01_empty_1] node 4 is missing")


def test_a_node_with_gaps_is_refused(camp: Path) -> None:
    d = camp / "blocks" / "01_empty_1"
    name = json.loads((d / "block.json").read_text())["recording"]
    write_recording(d, name, "empty", BASE_MS, fps_fn=lambda node, s: 0 if (node == 4 and s % 2 == 0) else FPS)
    assert fails(cp.validate(camp, SHORT), "node 4 delivered frames in only")


def test_an_undeclared_rssi_shift_between_blocks_of_one_link_state_is_refused(camp: Path) -> None:
    d = camp / "blocks" / "05_empty_2"
    name = json.loads((d / "block.json").read_text())["recording"]
    write_recording(d, name, "empty", BASE_MS + 3_000_000, rssi_fn=lambda node, s: -40 - node - 9)
    rep = cp.validate(camp, SHORT)
    assert fails(rep, "undeclared link change between blocks") and fails(rep, "give the later block its own link_state_id")


def test_a_declared_new_link_state_without_all_six_blocks_is_refused(camp: Path) -> None:
    d = camp / "blocks" / "05_empty_2"
    name = json.loads((d / "block.json").read_text())["recording"]
    write_recording(d, name, "empty", BASE_MS + 3_000_000, rssi_fn=lambda node, s: -40 - node - 9)
    meta = json.loads((d / "block.json").read_text())
    meta["link_state_id"] = "L2"
    (d / "block.json").write_text(json.dumps(meta), encoding="utf-8")
    rep = cp.validate(camp, SHORT)
    assert not fails(rep, "undeclared link change between blocks")        # declared: not an undeclared shift
    assert fails(rep, "no link state contains all six block types")      # but L1 now lacks empty_2


def test_a_block_without_link_state_id_is_refused(camp: Path) -> None:
    f = camp / "blocks" / "01_empty_1" / "block.json"
    meta = json.loads(f.read_text())
    meta["link_state_id"] = ""
    f.write_text(json.dumps(meta), encoding="utf-8")
    assert fails(cp.validate(camp, SHORT), "no link_state_id: epochs are not segmented")


def test_unknown_block_type_and_duplicate_ids_are_refused(camp: Path) -> None:
    f = camp / "blocks" / "03_walking" / "block.json"
    meta = json.loads(f.read_text())
    meta["block_type"] = "dancing"
    f.write_text(json.dumps(meta), encoding="utf-8")
    assert fails(cp.validate(camp, SHORT), "unknown block_type 'dancing'")
    meta["block_type"] = "walking"
    meta["block_id"] = "01_empty_1"
    f.write_text(json.dumps(meta), encoding="utf-8")
    assert fails(cp.validate(camp, SHORT), "duplicate block_id")


def test_a_label_that_does_not_match_the_block_type_is_refused(camp: Path) -> None:
    d = camp / "blocks" / "03_walking"
    name = json.loads((d / "block.json").read_text())["recording"]
    write_recording(d, name, "empty", BASE_MS + 1_200_000)
    assert fails(cp.validate(camp, SHORT), "does not match block type walking")


def test_a_campaign_missing_a_block_type_is_refused(camp: Path) -> None:
    shutil.rmtree(camp / "blocks" / "06_fan_with_person")
    assert fails(cp.validate(camp, SHORT), "no link state contains all six block types")


def test_not_a_folder_and_bad_json_are_refused_not_crashes(tmp_path: Path, camp: Path) -> None:
    assert not cp.validate(tmp_path / "nope").ok
    (camp / "campaign.json").write_text("{not json", encoding="utf-8")
    assert fails(cp.validate(camp, SHORT), "not valid JSON")


def test_cli_exit_codes_and_it_never_writes_into_the_campaign(camp: Path, tmp_path: Path, capsys) -> None:
    before = tree_hash(camp)
    assert cp.main([str(camp)]) == 1                                    # real minimums refuse the 70 s blocks
    assert "INVALID" in capsys.readouterr().out
    out = tmp_path / "report.json"
    assert cp.main([str(camp), "--json", str(out)]) == 1 and json.loads(out.read_text())["valid"] is False
    assert tree_hash(camp) == before                                    # read-only
    assert cp.main([str(tmp_path / "missing")]) == 2


def test_the_json_report_is_refused_under_data(camp: Path) -> None:
    target = cp.REPO / "data" / "sessions" / "report-must-not-exist.json"
    assert cp.main([str(camp), "--json", str(target)]) == 2
    assert not target.exists()


def test_sidecar_and_part_helpers(tmp_path: Path) -> None:
    for n in ("rec.jsonl", "rec.part2.jsonl", "rec2.jsonl", "other.jsonl"):
        (tmp_path / n).write_text("{}")
    assert [p.name for p in cp.recording_parts(tmp_path, "rec")] == ["rec.jsonl", "rec.part2.jsonl"]
    assert cp.summary_sidecar(tmp_path / "rec.part2.jsonl").name == "rec.part2.summary.json"
    assert cp.parse_utc("2026-11-10T08:00:00Z").year == 2026 and cp.parse_utc("nonsense") is None


def test_the_spec_numbers_come_from_the_existing_tooling() -> None:
    from scripts.presence_eval import epochs
    assert cp.STEP_DB == epochs.STEP_DB == 6.0 and cp.MIN_BASELINE_FPS == epochs.MIN_BASELINE_FPS == 20.0
    assert cp.BLOCK_RULES["empty_1"][0] == 60.0 and cp.BLOCK_RULES["empty_2"][0] == 60.0 and cp.BLOCK_RULES["fan_alone"][0] == 5.0
    assert cp.BLOCK_RULES["fan_with_person"][0] == 10.0                 # set by the owner 2026-11-04 (PREREG section 2); no existing rule to inherit
