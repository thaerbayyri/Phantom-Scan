"""PS-FIX-36 step 0: dataset recordings may carry two extra per-frame fields (`seq`, `nsc`). Every reader and the campaign validator must
behave exactly as without them. Writes only to pytest temp folders; never touches data/.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import test_campaign_validator as tcv  # sibling test module: its synthetic-campaign builders (pytest puts tests/ on sys.path)
from phantom.dataset import load_recording as strict_load_recording
from scripts.presence_eval import campaign as cp
from scripts.presence_eval.recordings import parse_files

HEADER = {"type": "header", "schema": 2, "roomId": "lab", "subjectId": "s1", "label": "empty", "count": 0, "notes": "",
          "startedAtMs": 1_794_000_000_000, "partStartedAtMs": 1_794_000_000_000, "part": 1, "geometry": {}}


def write_recording(path: Path, *, extras: bool, nodes=(1, 2), seconds: int = 12, fps: int = 20) -> Path:
    rng = np.random.default_rng(7)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(HEADER) + "\n")
        seq = {n: 100 * n for n in nodes}
        for s in range(seconds):
            for k in range(fps):
                for n in nodes:
                    row = {"type": "frame", "t": HEADER["startedAtMs"] + s * 1000 + k * (1000 // fps), "n": n, "rssi": -40 - n,
                           "a": [round(float(x), 2) for x in 10 + rng.normal(0, 0.3, 51)]}
                    if extras:
                        row["seq"] = seq[n]
                        row["nsc"] = 128
                    seq[n] += 1
                    fh.write(json.dumps(row) + "\n")
    return path


def test_the_presence_eval_loader_returns_identical_series_with_and_without_the_extra_fields(tmp_path: Path) -> None:
    plain = parse_files([write_recording(tmp_path / "lab__s1__empty__20261110T080000Z.jsonl", extras=False)])
    extra = parse_files([write_recording(tmp_path / "lab__s1__empty__20261110T080100Z.jsonl", extras=True)])
    assert extra.stats == plain.stats
    assert extra.stats.malformed_lines == 0 and extra.stats.bad_length_frames == 0
    assert set(extra.nodes) == set(plain.nodes) == {1, 2}
    for n in plain.nodes:
        assert np.array_equal(extra.nodes[n].t, plain.nodes[n].t)
        assert np.array_equal(extra.nodes[n].rssi, plain.nodes[n].rssi)
        assert np.array_equal(extra.nodes[n].a, plain.nodes[n].a)


def test_even_the_strict_dataset_loader_accepts_the_extra_fields(tmp_path: Path) -> None:
    plain = strict_load_recording([write_recording(tmp_path / "lab__s1__empty__20261110T080000Z.jsonl", extras=False)], strict=True)
    extra = strict_load_recording([write_recording(tmp_path / "lab__s1__empty__20261110T080100Z.jsonl", extras=True)], strict=True)
    assert extra.report.frames == plain.report.frames > 0
    assert extra.report.malformed_lines == extra.report.bad_frames == 0
    for n in plain.nodes:
        assert np.array_equal(extra.nodes[n].t_ms, plain.nodes[n].t_ms)
        assert np.array_equal(extra.nodes[n].amps, plain.nodes[n].amps)


def _add_extras_to_every_recording(root: Path) -> int:
    """Rewrite every frame line of every recording under root with seq and nsc added (in place, temp copy only)."""
    changed = 0
    for path in root.rglob("*.jsonl"):
        out, seq = [], 0
        for line in path.read_text(encoding="utf-8").splitlines():
            obj = json.loads(line)
            if obj.get("type") == "frame":
                obj["seq"], obj["nsc"] = seq, 128
                seq += 1
                changed += 1
            out.append(json.dumps(obj))
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return changed


def test_the_campaign_validator_gives_the_same_verdict_and_numbers_when_every_frame_carries_seq_and_nsc(tmp_path: Path) -> None:
    root = tmp_path / "c"
    tcv.write_campaign(root)
    before = cp.validate(root, tcv.SHORT)
    assert before.ok, before.failures
    changed = _add_extras_to_every_recording(root)
    assert changed > 1000, "the synthetic campaign must actually have been rewritten"
    after = cp.validate(root, tcv.SHORT)
    assert after.ok, after.failures
    assert after.failures == before.failures == []
    assert after.warnings == before.warnings
    assert set(after.blocks) == set(before.blocks)
    for bid, facts in before.blocks.items():
        assert after.blocks[bid]["nodes"] == facts["nodes"], bid
        assert after.blocks[bid]["duration_s"] == facts["duration_s"], bid
