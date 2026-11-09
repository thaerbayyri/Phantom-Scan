"""2026-11 recording campaign: the data spec in code, and the validator. READ-ONLY.

    python -m scripts.presence_eval.validate_campaign <campaign folder> [--json OUT.json] [--min-fan-person-min N] [--link-state-mode c1|c2]

Exit 0 = every gate passed; 1 = at least one gate failed (one clear line each); 2 = usage error. It never writes into ``data/`` (the optional
``--json`` report is refused when it would land under data/). Spec: reports/presence-eval-2026-11/RECORDING-DATA-SPEC.md. Pre-registration:
reports/presence-eval-2026-11/PREREG-2026-11-recording-campaign.md. Every threshold comes from existing tooling (sources in the pre-registration).
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from .epochs import HELD_FRACTION, MIN_BASELINE_FPS, STEP_DB, detect_events, second_series
from .recordings import load_recording

REPO = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = 1
MAX_FPS = 100.0                     # the firmware send gate is 10 ms (csi_ping_pure.h CSI_MIN_SEND_INTERVAL_MS)
REF_S = 60                          # seconds at the start of a block used as that block's reference RSSI
LOG_SLACK_S = 300                   # an entry-log line may precede/follow the block by this much without a warning
DURATION_SLACK_S = 120              # operator start/stop vs recorded frame times
LINK_STATE_MODES = ("c1", "c2")     # "c1" = the frozen first-60-s reference (default, unchanged); "c2" = the c2 amendment (whole-block medians)
# c2 amendment A1: the empty block each non-empty block is compared with; the two empty blocks are compared with each other.
ADJACENT_EMPTY = {"fan_alone": "empty_1", "walking": "empty_1", "still": "empty_1", "fan_with_person": "empty_2"}

# block type -> (minimum minutes (None = none registered), entry log required, allowed recorder labels). PREREG section 2.
BLOCK_RULES: dict[str, tuple[float | None, bool, tuple[str, ...]]] = {
    "empty_1": (60.0, True, ("empty",)),
    "fan_alone": (5.0, True, ("empty_fan",)),
    "walking": (5.0, False, ("walking",)),
    "still": (5.0, False, ("still",)),
    "empty_2": (60.0, True, ("empty",)),
    "fan_with_person": (10.0, False, ("still", "walking")),     # set by the owner 2026-11-04; no existing rule to inherit
}
CAMPAIGN_KEYS = ("schema_version", "campaign_id", "nodes_expected")
BLOCK_KEYS = ("schema_version", "block_id", "block_type", "recording", "start_utc", "stop_utc", "link_state_id", "person_count", "fan_on")


@dataclass
class Report:
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    blocks: dict[str, dict] = field(default_factory=dict)      # block_id -> facts, for run_campaign

    @property
    def ok(self) -> bool:
        return not self.failures


def _read_json(path: Path, rep: Report, what: str) -> dict | None:
    if not path.is_file():
        rep.failures.append(f"{what} missing: {path}")
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        rep.failures.append(f"{what} is not valid JSON ({path.name}): {e}")
        return None
    if not isinstance(data, dict):
        rep.failures.append(f"{what} must be a JSON object: {path}")
        return None
    return data


def parse_utc(s: object) -> datetime | None:
    if not isinstance(s, str):
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def recording_parts(block_dir: Path, recording: str) -> list[Path]:
    """The recorder's parts of one recording: ``<recording>.jsonl`` and ``<recording>.partN.jsonl``."""
    return sorted(p for p in block_dir.glob(f"{recording}*.jsonl") if p.name == f"{recording}.jsonl" or p.name.startswith(f"{recording}.part"))


def summary_sidecar(part: Path) -> Path:
    return part.with_name(part.name[: -len(".jsonl")] + ".summary.json")


def _check_entry_log(block_dir: Path, meta: dict, start: datetime | None, stop: datetime | None, rep: Report, bid: str) -> None:
    log = block_dir / str(meta.get("entry_log") or "entry-log.txt")
    if not log.is_file() or not log.read_text(encoding="utf-8", errors="replace").strip():
        rep.failures.append(f"[{bid}] entry log missing or empty ({log.name}): the emptiness of this block cannot be verified")
        return
    lines = [ln for ln in log.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
    if len(lines) < 2:
        rep.failures.append(f"[{bid}] entry log needs at least a start line and an end line (found {len(lines)})")
    for ln in lines:
        ts = parse_utc(ln.split()[0])
        if ts is None:
            rep.warnings.append(f"[{bid}] entry-log line without a leading UTC timestamp: {ln[:60]!r}")
        elif start and stop and (ts < start - timedelta(seconds=LOG_SLACK_S) or ts > stop + timedelta(seconds=LOG_SLACK_S)):
            rep.warnings.append(f"[{bid}] entry-log line outside the block time range: {ln[:60]!r}")


def _validate_block(block_dir: Path, meta: dict, nodes_expected: list[int], min_minutes: dict, rep: Report, whole_median: bool = False) -> dict | None:
    bid = str(meta.get("block_id"))
    btype = meta.get("block_type")
    if btype not in BLOCK_RULES:
        rep.failures.append(f"[{bid}] unknown block_type {btype!r} (expected one of {sorted(BLOCK_RULES)})")
        return None
    min_min, log_required, labels = BLOCK_RULES[btype]
    min_min = min_minutes.get(btype, min_min)
    for key in BLOCK_KEYS:
        if key not in meta:
            rep.failures.append(f"[{bid}] block.json lacks required field {key!r}")
    if not str(meta.get("link_state_id") or "").strip():
        rep.failures.append(f"[{bid}] no link_state_id: epochs are not segmented")
    start, stop = parse_utc(meta.get("start_utc")), parse_utc(meta.get("stop_utc"))
    if start is None or stop is None or stop <= start:
        rep.failures.append(f"[{bid}] start_utc / stop_utc missing, unparsable or not in order")
    parts = recording_parts(block_dir, str(meta.get("recording")))
    if not parts:
        rep.failures.append(f"[{bid}] no recording parts named {meta.get('recording')!r} in {block_dir.name}/")
        return None
    for p in parts:
        if not summary_sidecar(p).is_file():
            rep.failures.append(f"[{bid}] recorder sidecar missing: {summary_sidecar(p).name}")
    if log_required:
        _check_entry_log(block_dir, meta, start, stop, rep, bid)
    try:
        rec = load_recording(parts, None)
    except Exception as e:  # a parse failure is a validation result, never a crash
        rep.failures.append(f"[{bid}] recording could not be read: {e}")
        return None
    if rec.label not in labels:
        rep.failures.append(f"[{bid}] recorder label {rec.label!r} does not match block type {btype} (allowed: {', '.join(labels)})")
    all_t = [int(s.t[0]) for s in rec.nodes.values() if len(s.t)] + [int(s.t[-1]) for s in rec.nodes.values() if len(s.t)]
    if not all_t:
        rep.failures.append(f"[{bid}] the recording holds no frames")
        return None
    t0, t1 = min(all_t), max(all_t)
    duration_s = (t1 - t0) / 1000.0
    if min_min is None:
        rep.warnings.append(f"[{bid}] minimum duration for {btype} has no registered minimum: not enforced (measured {duration_s / 60:.1f} min)")
    elif duration_s < min_min * 60.0:
        rep.failures.append(f"[{bid}] block is {duration_s / 60:.1f} min, shorter than the required {min_min:g} min for {btype}")
    if start and stop and abs((stop - start).total_seconds() - duration_s) > DURATION_SLACK_S:
        rep.warnings.append(f"[{bid}] operator start/stop span {(stop - start).total_seconds():.0f} s differs from the recorded {duration_s:.0f} s")
    n_sec = int(duration_s) + 1
    facts: dict = {"block_type": btype, "link_state_id": meta.get("link_state_id"), "duration_s": duration_s, "nodes": {}, "t0_ms": t0, "parts": [p.name for p in parts]}
    for node in nodes_expected:
        s = rec.nodes.get(node)
        if s is None or len(s.t) == 0:
            rep.failures.append(f"[{bid}] node {node} is missing (no frames)")
            continue
        rssi, fps = second_series(s, t0, n_sec)
        coverage = float(np.mean(fps > 0))
        med_fps = float(np.median(fps[fps > 0])) if (fps > 0).any() else 0.0
        if coverage < HELD_FRACTION:
            rep.failures.append(f"[{bid}] node {node} delivered frames in only {coverage:.0%} of the seconds (needs {HELD_FRACTION:.0%})")
        if not (MIN_BASELINE_FPS <= med_fps <= MAX_FPS):
            rep.failures.append(f"[{bid}] node {node} median rate {med_fps:.1f} fps is outside [{MIN_BASELINE_FPS:g}, {MAX_FPS:g}]")
        for ev in detect_events(rssi, fps, t0, node):
            if ev.kind in ("rssi_step", "rate_collapse"):
                rep.failures.append(f"[{bid}] undeclared link change inside the block: {ev.label()} at +{(ev.t_ms - t0) / 1000:.0f} s (stop, log, wait 2 min, start a new block)")
        ref = rssi[:REF_S][np.isfinite(rssi[:REF_S])]
        node_facts = {"median_fps": med_fps, "coverage": coverage, "ref_rssi": float(np.median(ref)) if ref.size else None}
        if whole_median:  # c2 link-state mode only: whole-block median RSSI over all frames of the untrimmed recording, unrounded
            r_all = s.rssi[np.isfinite(s.rssi)].astype(np.float64)
            node_facts["median_rssi"] = float(np.median(r_all)) if r_all.size else None
        facts["nodes"][node] = node_facts
    return facts


def validate(folder: Path, min_minutes: dict | None = None, link_state_mode: str = "c1") -> Report:
    """Validate a campaign folder against the spec. ``min_minutes`` overrides per block type (tests use short blocks; the CLI only sets fan_with_person).
    ``link_state_mode`` "c1" (default) is the frozen rule, byte-for-byte unchanged; "c2" applies the c2 amendment A1 instead of the first-60-s between-block check."""
    if link_state_mode not in LINK_STATE_MODES:
        raise ValueError(f"unknown link_state_mode {link_state_mode!r} (expected one of {LINK_STATE_MODES})")
    rep = Report()
    min_minutes = min_minutes or {}
    folder = Path(folder)
    if not folder.is_dir():
        rep.failures.append(f"not a folder: {folder}")
        return rep
    campaign = _read_json(folder / "campaign.json", rep, "campaign.json")
    if campaign is None:
        return rep
    for key in CAMPAIGN_KEYS:
        if key not in campaign:
            rep.failures.append(f"campaign.json lacks required field {key!r}")
    nodes_expected = [int(n) for n in campaign.get("nodes_expected", [])] if isinstance(campaign.get("nodes_expected"), list) else []
    if not nodes_expected:
        rep.failures.append("campaign.json: nodes_expected must be a non-empty list of node ids")
    block_dirs = sorted(p for p in (folder / "blocks").glob("*") if p.is_dir()) if (folder / "blocks").is_dir() else []
    if not block_dirs:
        rep.failures.append("no blocks found under blocks/")
    seen_ids: set[str] = set()
    for bd in block_dirs:
        meta = _read_json(bd / "block.json", rep, f"block.json of {bd.name}")
        if meta is None:
            continue
        bid = str(meta.get("block_id"))
        if bid in seen_ids:
            rep.failures.append(f"duplicate block_id {bid!r}")
        seen_ids.add(bid)
        facts = _validate_block(bd, meta, nodes_expected, min_minutes, rep, whole_median=link_state_mode == "c2")
        if facts is not None:
            rep.blocks[bid] = facts
    _validate_link_states(rep, link_state_mode)
    rep.notes.append(f"{len(block_dirs)} block folder(s), {len(rep.blocks)} readable; nodes expected {nodes_expected}")
    if link_state_mode == "c2":
        rep.notes.append("link-state mode c2: whole-block median RSSI against the adjacent empty block, fails at " f"{STEP_DB:g} dB or more (unrounded)")
    return rep


def _validate_link_states(rep: Report, mode: str = "c1") -> None:
    by_state: dict[str, list[str]] = {}
    for bid, f in rep.blocks.items():
        by_state.setdefault(str(f["link_state_id"]), []).append(bid)
    complete = [ls for ls, bids in by_state.items() if {rep.blocks[b]["block_type"] for b in bids} >= set(BLOCK_RULES)]
    if not complete:
        have = {ls: sorted({rep.blocks[b]["block_type"] for b in bids}) for ls, bids in by_state.items()}
        rep.failures.append(f"no link state contains all six block types {sorted(BLOCK_RULES)}; found {have}")
    if mode == "c2":
        _c2_link_state_check(rep, by_state)
        return
    for ls, bids in by_state.items():
        ordered = sorted(bids)
        first = rep.blocks[ordered[0]]
        for bid in ordered[1:]:
            for node, nf in rep.blocks[bid]["nodes"].items():
                ref, cur = first["nodes"].get(node, {}).get("ref_rssi"), nf.get("ref_rssi")
                if ref is not None and cur is not None and abs(cur - ref) >= STEP_DB:
                    rep.failures.append(f"undeclared link change between blocks {ordered[0]} and {bid} in link state {ls}: node {node} RSSI {ref:.0f} -> {cur:.0f} dBm "
                                        f"({cur - ref:+.0f} dB, >= {STEP_DB:g} dB): give the later block its own link_state_id")


def _pair_check(rep: Report, ls: str, bid: str, ref_bid: str) -> None:
    """c2 amendment A1: whole-block median RSSI of ``bid`` against ``ref_bid``, per node, unrounded; fails at STEP_DB (6 dB) or more."""
    for node, nf in sorted(rep.blocks[bid]["nodes"].items()):
        cur = nf.get("median_rssi")
        ref = rep.blocks[ref_bid]["nodes"].get(node, {}).get("median_rssi")
        if cur is None or ref is None:
            continue
        diff = abs(cur - ref)
        if diff >= STEP_DB:
            rep.failures.append(f"link-state check (c2) in link state {ls}: block {bid} node {node} whole-block median RSSI {cur:.1f} dBm vs {ref_bid} {ref:.1f} dBm: "
                                f"difference {diff:.2f} dB, >= {STEP_DB:g} dB; the block is invalid and is not analysed (a re-recording is a new block, at most one per block type)")


def _c2_link_state_check(rep: Report, by_state: dict[str, list[str]]) -> None:
    """c2 amendment A1, inside each link state: empty_1 against empty_2, and each non-empty block against its adjacent empty block.
    A missing adjacent empty block is not compared here (the all-six-block-types check reports the missing type)."""
    for ls, bids in sorted(by_state.items()):
        by_type: dict[str, list[str]] = {}
        for bid in sorted(bids):
            by_type.setdefault(str(rep.blocks[bid]["block_type"]), []).append(bid)
        for e1 in by_type.get("empty_1", []):
            for e2 in by_type.get("empty_2", []):
                _pair_check(rep, ls, e2, e1)
        for btype, adjacent in ADJACENT_EMPTY.items():
            for bid in by_type.get(btype, []):
                for ref_bid in by_type.get(adjacent, []):
                    _pair_check(rep, ls, bid, ref_bid)


def _under_data(path: Path) -> bool:
    try:
        path.resolve().relative_to((REPO / "data").resolve())
        return True
    except ValueError:
        return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate a 2026-11 recording campaign folder (read-only)")
    ap.add_argument("folder", type=Path)
    ap.add_argument("--json", type=Path, default=None, help="also write the report here (never under data/)")
    ap.add_argument("--min-fan-person-min", type=float, default=None, help="override the minimum minutes for the fan_with_person block (default: the registered 10)")
    ap.add_argument("--link-state-mode", choices=LINK_STATE_MODES, default="c1",
                    help="c1 = the frozen first-60-s reference (default); c2 = the c2 amendment: whole-block medians against the adjacent empty block")
    args = ap.parse_args(argv)
    if args.json is not None and _under_data(args.json):
        print(f"error: refusing to write a report under data/: {args.json}", file=sys.stderr)
        return 2
    if not args.folder.is_dir():
        print(f"error: {args.folder} is not a folder", file=sys.stderr)
        return 2
    mm = {"fan_with_person": args.min_fan_person_min} if args.min_fan_person_min is not None else {}
    rep = validate(args.folder, mm, args.link_state_mode)
    for n in rep.notes:
        print(f"note: {n}")
    for w in rep.warnings:
        print(f"WARN: {w}")
    for f in rep.failures:
        print(f"FAIL: {f}")
    print("INVALID" if rep.failures else "VALID", f"({len(rep.failures)} failure(s), {len(rep.warnings)} warning(s))")
    if args.json is not None:
        args.json.write_text(json.dumps({"valid": rep.ok, "failures": rep.failures, "warnings": rep.warnings, "notes": rep.notes, "blocks": rep.blocks}, indent=2, default=float), encoding="utf-8")
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())
