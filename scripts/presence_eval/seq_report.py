"""Offline per-node, per-minute report from a recording that carries the PS-FIX-36 step 0 fields `seq` and `nsc`.

For every node and every minute of the recording it reports:
  * delivered rate   frames recorded per second (what every other tool calls the frame rate);
  * produced rate    frames the node serialized per second, from the forward step of `seq` between consecutive recorded
                     frames (`seq` counts frames PRODUCED, before the 10 ms send gate, not frames sent);
  * ratio            delivered / produced for the same frames (the share that got through gate, send and network);
  * nsc mix          share of each raw subcarrier count (64 = LLTF only, 128 = LLTF + HT-LTF, 192 = + STBC-HT-LTF).
A backward jump of `seq` is logged as a node reboot and contributes no step. A minute whose delivered rate is below
COLLAPSE_RATIO x the node's reference rate is flagged (full minutes only). Observation only: it says nothing about the cause.

Read-only. Never writes under data/. Recordings made before the step 0 change have no `seq`/`nsc`: only the delivered rate is reported.

    python -m scripts.presence_eval.seq_report data/datasets/smoke-test/<name>.jsonl [--reference-minutes 10] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Sequence

from .recordings import iter_lines, part_number

U32 = 1 << 32
BACKWARD_JUMP = 1 << 31         # a forward step of 2^31 or more is a backward jump of the u32 counter
BIN_MS = 60_000
COLLAPSE_RATIO = 0.7            # the frozen rule's collapse ratio; the reference is the node's own rate
DEFAULT_REFERENCE_MINUTES = 10
REPO_DATA = Path(__file__).resolve().parents[2] / "data"


@dataclass
class Minute:
    index: int
    frames: int = 0
    paired: int = 0             # frames that contributed a seq step (they had a predecessor with seq)
    produced: int = 0           # sum of those forward steps
    nsc: Counter = field(default_factory=Counter)
    seconds: float = 60.0
    partial: bool = False

    @property
    def delivered_rate(self) -> float:
        return self.frames / self.seconds if self.seconds > 0 else 0.0

    @property
    def produced_rate(self) -> float | None:
        return self.produced / self.seconds if self.paired and self.seconds > 0 else None

    @property
    def ratio(self) -> float | None:
        return self.paired / self.produced if self.produced > 0 else None


@dataclass
class NodeAcc:
    minutes: dict[int, Minute] = field(default_factory=dict)
    frames: int = 0
    with_seq: int = 0
    zero_steps: int = 0
    prev_seq: int | None = None
    reboots: list[dict] = field(default_factory=list)


def _iso(ms: float) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_u32(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and 0 <= v < U32


def expand_parts(path: Path) -> list[Path]:
    """The given file plus its .partN siblings, in part order (a part file is used as given)."""
    if ".part" in path.name:
        return [path]
    siblings = sorted(path.parent.glob(path.name.replace(".jsonl", ".part*.jsonl")), key=part_number)
    return [path, *siblings]


def _count_step(node: NodeAcc, minute: Minute, seq: int, t_ms: float) -> None:
    if node.prev_seq is not None:
        step = (seq - node.prev_seq) % U32
        if step >= BACKWARD_JUMP:
            node.reboots.append({"t_ms": int(t_ms), "utc": _iso(t_ms), "from_seq": node.prev_seq, "to_seq": seq})
        else:
            node.zero_steps += step == 0
            minute.paired += 1
            minute.produced += step
    node.prev_seq = seq


def accumulate(paths: Sequence[Path]) -> tuple[float | None, float | None, dict[int, NodeAcc]]:
    t0: float | None = None
    t_last: float | None = None
    nodes: dict[int, NodeAcc] = {}
    for path in paths:
        for kind, obj in iter_lines(path):
            if kind != "frame":
                continue
            n, t = obj.get("n"), obj.get("t")  # type: ignore[union-attr]
            if not isinstance(n, int) or isinstance(n, bool) or not isinstance(t, (int, float)):
                continue
            t0 = t if t0 is None else t0
            t_last = t if t_last is None else max(t_last, t)
            node = nodes.setdefault(n, NodeAcc())
            index = max(0, int((t - t0) // BIN_MS))
            minute = node.minutes.setdefault(index, Minute(index))
            minute.frames += 1
            node.frames += 1
            nsc = obj.get("nsc")  # type: ignore[union-attr]
            if isinstance(nsc, int) and not isinstance(nsc, bool):
                minute.nsc[nsc] += 1
            seq = obj.get("seq")  # type: ignore[union-attr]
            if _is_u32(seq):
                node.with_seq += 1
                _count_step(node, minute, seq, t)
            else:
                node.prev_seq = None
    return t0, t_last, nodes


def finish_minutes(nodes: dict[int, NodeAcc], t0: float, t_last: float) -> int:
    """Fill gaps with empty minutes up to the last minute; mark a short final minute as partial. Returns the last minute index."""
    last = max(0, int((t_last - t0) // BIN_MS))
    tail_s = (t_last - t0 - last * BIN_MS) / 1000
    for node in nodes.values():
        for i in range(last + 1):
            node.minutes.setdefault(i, Minute(i))
        if tail_s < 60:
            node.minutes[last].seconds, node.minutes[last].partial = max(tail_s, 0.001), True
    return last


def reference_rate(node: NodeAcc, reference_minutes: int, override: float | None) -> float | None:
    if override is not None:
        return override
    full = [m.delivered_rate for _, m in sorted(node.minutes.items()) if not m.partial][:reference_minutes]
    return median(full) if full else None


def flagged_minutes(node: NodeAcc, reference: float | None, collapse: float) -> list[int]:
    if reference is None:
        return []
    return [i for i, m in sorted(node.minutes.items()) if not m.partial and m.delivered_rate < collapse * reference]


def nsc_text(c: Counter) -> str:
    total = sum(c.values())
    return " ".join(f"{k}:{v / total:.1%}" for k, v in sorted(c.items(), key=lambda kv: -kv[1])) if total else "-"


def render(t0: float, nodes: dict[int, NodeAcc], refs: dict[int, float | None], flags: dict[int, list[int]], collapse: float) -> list[str]:
    out = [f"recording start {_iso(t0)}; collapse flag below {collapse:g} x the node's reference delivered rate"]
    for n in sorted(nodes):
        node = nodes[n]
        ref = refs[n]
        out.append(f"\nnode {n}: {node.frames} frames, {node.with_seq} with seq; reference delivered rate "
                   + (f"{ref:.1f} fps" if ref is not None else "n/a (no full minute)")
                   + f"; reboots {len(node.reboots)}; zero seq steps {node.zero_steps}")
        out.append("  min  start (UTC)  delivered/s  produced/s  ratio   nsc mix                 flag")
        for i, m in sorted(node.minutes.items()):
            prod = f"{m.produced_rate:10.1f}" if m.produced_rate is not None else f"{'-':>10}"
            ratio = f"{m.ratio:6.1%}" if m.ratio is not None else f"{'-':>6}"
            flag = "FLAG" if i in flags[n] else ("partial" if m.partial else "")
            out.append(f"  {i:3d}  {_iso(t0 + i * BIN_MS)[11:19]}    {m.delivered_rate:10.1f}  {prod}  {ratio}   {nsc_text(m.nsc):<22}  {flag}")
        for r in node.reboots:
            out.append(f"  REBOOT at {r['utc']}: seq {r['from_seq']} -> {r['to_seq']} (backward jump)")
    out.append(f"\nflagged windows: {sum(len(v) for v in flags.values())}")
    return out


def build(paths: Sequence[Path], reference_minutes: int, override: float | None, collapse: float) -> tuple[list[str], dict]:
    t0, t_last, nodes = accumulate(paths)
    if t0 is None or t_last is None or not nodes:
        raise ValueError("no usable frames in the recording")
    finish_minutes(nodes, t0, t_last)
    refs = {n: reference_rate(a, reference_minutes, override) for n, a in nodes.items()}
    flags = {n: flagged_minutes(a, refs[n], collapse) for n, a in nodes.items()}
    summary = {"start_utc": _iso(t0), "end_utc": _iso(t_last), "collapse_ratio": collapse, "flagged_windows": sum(len(v) for v in flags.values()), "nodes": {
        str(n): {"frames": a.frames, "with_seq": a.with_seq, "reference_delivered_rate": refs[n], "reboots": a.reboots, "zero_steps": a.zero_steps, "flagged_minutes": flags[n],
                 "minutes": [{"minute": i, "partial": m.partial, "delivered_rate": m.delivered_rate, "produced_rate": m.produced_rate, "ratio": m.ratio, "nsc": dict(m.nsc)}
                             for i, m in sorted(a.minutes.items())]} for n, a in sorted(nodes.items())}}
    return render(t0, nodes, refs, flags, collapse), summary


def _under_data(path: Path) -> bool:
    try:
        path.resolve().relative_to(REPO_DATA.resolve())
        return True
    except ValueError:
        return False


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Per-node per-minute delivered/produced rate and nsc mix from seq and nsc (read-only)")
    ap.add_argument("recording", type=Path, nargs="+", help="a .jsonl recording file (its .partN siblings are added automatically)")
    ap.add_argument("--reference-minutes", type=int, default=DEFAULT_REFERENCE_MINUTES, help="reference = median delivered rate of the first N full minutes")
    ap.add_argument("--reference-fps", type=float, default=None, help="use this delivered rate as the reference instead")
    ap.add_argument("--collapse", type=float, default=COLLAPSE_RATIO)
    ap.add_argument("--json", type=Path, default=None, help="also write the report here (never under data/)")
    ap.add_argument("--fail-on-flag", action="store_true", help="exit 3 when any window is flagged")
    args = ap.parse_args(argv)
    if args.json is not None and _under_data(args.json):
        print(f"error: refusing to write a report under data/: {args.json}", file=sys.stderr)
        return 2
    paths = [p for rec in args.recording for p in expand_parts(rec)]
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        print(f"error: not a file: {', '.join(missing)}", file=sys.stderr)
        return 2
    try:
        lines, summary = build(paths, args.reference_minutes, args.reference_fps, args.collapse)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    if args.json is not None:
        args.json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 3 if args.fail_on_flag and summary["flagged_windows"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
