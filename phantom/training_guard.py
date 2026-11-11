"""Training-folder guard: refuse to train from a folder that is not a training room.

The loader (``phantom.dataset.load_room_dataset``) takes every ``*.jsonl`` under ``<root>/<room_id>/`` and selects
by folder name only. This guard runs BEFORE the loader and never changes what the loader returns. It refuses:

  * a room id that names campaign, soak, smoke or link-state reference data (``REFUSED_ROOM_PATTERNS``);
  * a folder holding a ``.jsonl`` whose header ``roomId`` differs from the folder name (a stray or copied file);
  * a folder whose headers carry different ``capture.channel`` values (recordings from both sides of a link-state
    boundary). A header without a channel (``null`` / ``not_recorded``) says nothing and is ignored.

``allow_unsafe=True`` turns each refusal into a returned warning; it is OFF by default.
"""
from __future__ import annotations

import fnmatch
import json
import sys
from pathlib import Path
from typing import TextIO

REFUSED_ROOM_PATTERNS: tuple[str, ...] = ("campaign-*", "soak-*", "smoke-*", "epoch*-ref-*", "smoke-test")


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


def room_refusals(root: Path | str, room_id: str) -> list[str]:
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
    if len(channels) > 1:
        listed = ", ".join(f"channel {ch} ({name})" for ch, name in sorted(channels.items()))
        reasons.append(f"recordings from different link states in one folder: {listed}")
    return reasons


def check_training_room(root: Path | str, room_id: str, *, allow_unsafe: bool = False) -> list[str]:
    """Raise UnsafeTrainingRoom when the room is unsafe; with allow_unsafe, return the reasons as warnings instead."""
    reasons = room_refusals(root, room_id)
    if reasons and not allow_unsafe:
        raise UnsafeTrainingRoom("; ".join(reasons) + " (pass --allow-unsafe to override)")
    return reasons


def enforce_training_room(root: Path | str, room_id: str, *, allow_unsafe: bool = False, stream: TextIO | None = None) -> bool:
    """CLI helper for the training scripts: False (after printing REFUSED) when training must not start."""
    out = stream if stream is not None else sys.stderr
    try:
        warnings = check_training_room(root, room_id, allow_unsafe=allow_unsafe)
    except UnsafeTrainingRoom as exc:
        print(f"REFUSED: {exc}", file=out)
        return False
    for warning in warnings:
        print(f"WARNING: --allow-unsafe is set, training anyway: {warning}", file=out)
    return True
