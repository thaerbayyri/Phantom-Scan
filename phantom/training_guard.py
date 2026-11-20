"""Training-folder guard: refuse to train from a folder that is not a training room.

The loader (``phantom.dataset.load_room_dataset``) takes every ``*.jsonl`` under ``<root>/<room_id>/`` and selects
by folder name only. This guard runs BEFORE the loader and never changes what the loader returns. It refuses:

  * a room id that names campaign, soak, smoke or link-state reference data (``REFUSED_ROOM_PATTERNS``);
  * a folder holding a ``.jsonl`` whose header ``roomId`` differs from the folder name (a stray or copied file);
  * a folder whose headers carry different ``capture.channel`` values (recordings from both sides of a link-state
    boundary). A header without a channel (``null`` / ``not_recorded``) says nothing and is ignored;
  * a recording part whose recorder summary (``.summary.json``) shows any node below ``MIN_TRAINING_FPS`` (the
    campaign's 0.7 x 67 fps collapse rule). Slow and normal clips must not be mixed: the rate changes the data, and
    when it differs between labels a model can learn the rate instead of the room. Parts shorter than
    ``MIN_RATE_PART_S`` and parts without a summary say nothing.

``allow_unsafe=True`` turns each refusal into a returned warning; it is OFF by default.
"""
from __future__ import annotations

import fnmatch
import json
import sys
from pathlib import Path
from typing import Iterable, TextIO

REFUSED_ROOM_PATTERNS: tuple[str, ...] = ("campaign-*", "soak-*", "smoke-*", "epoch*-ref-*", "smoke-test")
REFERENCE_FPS = 67.0
COLLAPSE_RATIO = 0.7
MIN_TRAINING_FPS = COLLAPSE_RATIO * REFERENCE_FPS
MIN_RATE_PART_S = 60.0


class UnsafeTrainingRoom(Exception):
    """The room folder must not be used for training (see the message for every reason)."""


def room_name_refusal(room_id: str) -> str | None:
    """Reason text if the room id itself names non-training data, else None."""
    for pattern in REFUSED_ROOM_PATTERNS:
        if fnmatch.fnmatchcase(room_id, pattern):
            return f"room id '{room_id}' matches '{pattern}' (campaign, soak, smoke or reference data, not training data)"
    return None


def _read_header(path: Path) -> dict | None:
    """First line of a recorder file as a header dict; None when it is not a readable header (the loader reports that)."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            obj = json.loads(fh.readline())
    except (OSError, ValueError):
        return None
    if not isinstance(obj, dict) or obj.get("type") != "header":
        return None
    return obj


def _header_channel(header: dict) -> int | None:
    capture = header.get("capture")
    channel = capture.get("channel") if isinstance(capture, dict) else None
    return channel if isinstance(channel, int) and not isinstance(channel, bool) else None


def _slow_nodes(jsonl_path: Path, exclude_nodes: Iterable[int] = ()) -> list[str]:
    """'N<id> <fps> fps' for every node below MIN_TRAINING_FPS in this part's recorder summary ([] if none/unknown)."""
    summary_path = jsonl_path.with_name(jsonl_path.name[: -len(".jsonl")] + ".summary.json")
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    per_node = summary.get("perNode") if isinstance(summary, dict) else None
    if not isinstance(per_node, dict):
        return []
    slow: list[str] = []
    skip = {str(int(n)) for n in exclude_nodes}
    for node, stats in sorted(per_node.items()):
        if str(node) in skip:
            continue
        try:
            frames = float(stats["frames"])
            span_s = (float(stats["lastFrameMs"]) - float(stats["firstFrameMs"])) / 1000.0
        except (KeyError, TypeError, ValueError):
            continue
        if span_s < MIN_RATE_PART_S:
            continue
        fps = (frames - 1.0) / span_s
        if fps < MIN_TRAINING_FPS:
            slow.append(f"N{node} {fps:.1f} fps")
    return slow


def room_refusals(root: Path | str, room_id: str, exclude_nodes: Iterable[int] = ()) -> list[str]:
    """Every reason this room must not be trained from (empty list = safe). Reads header lines only."""
    reasons: list[str] = []
    name_reason = room_name_refusal(room_id)
    if name_reason is not None:
        reasons.append(name_reason)
    room_dir = Path(root) / room_id
    if not room_dir.is_dir():
        return reasons
    channels: dict[int, str] = {}
    for path in sorted(room_dir.glob("*.jsonl")):
        header = _read_header(path)
        if header is None:
            continue
        header_room = header.get("roomId")
        if header_room != room_id:
            reasons.append(f"{path.name}: header roomId '{header_room}' differs from the folder name '{room_id}'")
        channel = _header_channel(header)
        if channel is not None:
            channels.setdefault(channel, path.name)
        slow = _slow_nodes(path, exclude_nodes)
        if slow:
            reasons.append(
                f"{path.name}: recorded below {MIN_TRAINING_FPS:.1f} fps ({', '.join(slow)}); "
                "move it out of the training folder"
            )
    if len(channels) > 1:
        listed = ", ".join(f"channel {ch} ({name})" for ch, name in sorted(channels.items()))
        reasons.append(f"recordings from different link states in one folder: {listed}")
    return reasons


def check_training_room(
    root: Path | str, room_id: str, *, allow_unsafe: bool = False, exclude_nodes: Iterable[int] = ()
) -> list[str]:
    """Raise UnsafeTrainingRoom when the room is unsafe; with allow_unsafe, return the reasons as warnings instead.

    ``exclude_nodes`` are node ids the caller will not train on; their frame rate is not judged.
    """
    reasons = room_refusals(root, room_id, exclude_nodes)
    if reasons and not allow_unsafe:
        raise UnsafeTrainingRoom("; ".join(reasons) + " (pass --allow-unsafe to override)")
    return reasons


def enforce_training_room(
    root: Path | str,
    room_id: str,
    *,
    allow_unsafe: bool = False,
    stream: TextIO | None = None,
    exclude_nodes: Iterable[int] = (),
) -> bool:
    """CLI helper for the training scripts: False (after printing REFUSED) when training must not start."""
    out = stream if stream is not None else sys.stderr
    try:
        warnings = check_training_room(root, room_id, allow_unsafe=allow_unsafe, exclude_nodes=exclude_nodes)
    except UnsafeTrainingRoom as exc:
        print(f"REFUSED: {exc}", file=out)
        return False
    for warning in warnings:
        print(f"WARNING: --allow-unsafe is set, training anyway: {warning}", file=out)
    return True
