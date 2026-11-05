"""Link-state epochs: split recordings where a node's link changed, so empties from different link states are never pooled.

Why: node 1 stepped from about -36 to -47 dBm (and its frame rate collapsed) at +195 s inside the s7 walking recording
and stayed there for ~1.5 h (PS-EVAL-006). Scores calibrated on one link state are not valid in another.

Per node and recording, on a 1 s grid (median RSSI, frame count):
  * rssi_step     : |median(next HOLD s) - median(previous PRE s)| >= STEP_DB, and >= 90 % of the HOLD seconds are beyond STEP_DB
                    on the same side (the step is HELD, not a one-second dip);
  * rate_collapse : median frame rate over the next HOLD s <= COLLAPSE x the previous PRE s median (>= 80 % of seconds below
                    0.85 x baseline), baseline >= MIN_BASELINE_FPS.
Between consecutive recordings of the same day the last/first EDGE_S seconds are compared the same way (the change happened
in an unrecorded gap). A new calendar day always starts a new epoch (nodes may have been moved; nothing says otherwise).

Epoch boundaries for a node SET are the union of that set's events. The time from PRE_MARGIN_S before an in-recording event to
SETTLE_S after it is TRANSITIONAL and must be excluded from detection evaluations. The CAUSE of an event is never inferred here.

STATUS OF THE BOUNDARY RULE: the persistence / empty-recording / 60 s rule in is_boundary() was chosen POST HOC, after looking at
these recordings (it was not in the original specification and was not pre-registered). Its sensitivity to the step threshold
(4/6/8 dB) and the hold time (10/30/60 s) is reported by epoch_sensitivity.py; every ambiguous step is listed there.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

import numpy as np

from .recordings import NodeSeries

STEP_DB = 6.0
HOLD_S = 10
PRE_S = 30
COLLAPSE = 0.7
MIN_BASELINE_FPS = 20.0
EDGE_S = 30
PRE_MARGIN_S = 5
SETTLE_S = 30
HELD_FRACTION = 0.9
COLLAPSE_FRACTION = 0.8


@dataclass(frozen=True)
class Event:
    node: int
    t_ms: int            # absolute (recorder host clock) onset
    kind: str            # rssi_step | rate_collapse | gap_step | gap_collapse | day_boundary
    delta_db: float | None
    fps_before: float | None
    fps_after: float | None
    rssi_before: float | None
    rssi_after: float | None
    in_gap: bool = False
    persistent: bool | None = None   # new level also holds at the end of the recording AND at the start of the next one
    held_s: float | None = None      # seconds the new level held before returning toward the old one (or to the recording end)
    reversal: bool = False           # returns to the level before the previous step: the end of an excursion, not a new link state

    def label(self) -> str:
        bits = [f"N{self.node} {self.kind}"]
        if self.delta_db is not None:
            bits.append(f"{self.delta_db:+.0f} dB ({self.rssi_before:.0f} -> {self.rssi_after:.0f} dBm)")
        if self.fps_before is not None and self.fps_after is not None:
            bits.append(f"fps {self.fps_before:.0f} -> {self.fps_after:.0f}")
        return " ".join(bits)


def second_series(node: NodeSeries, t0_ms: int, n_sec: int) -> tuple[np.ndarray, np.ndarray]:
    """(median RSSI per second [NaN where no frames], frames per second) on a 1 s grid starting at t0_ms."""
    sec = ((node.t - t0_ms) // 1000).astype(np.int64)
    keep = (sec >= 0) & (sec < n_sec)
    sec, rssi = sec[keep], node.rssi[keep]
    fps = np.bincount(sec, minlength=n_sec).astype(np.float64)
    med = np.full(n_sec, np.nan)
    if sec.size:
        order = np.argsort(sec, kind="stable")
        sec, rssi = sec[order], rssi[order]
        bounds = np.flatnonzero(np.diff(sec)) + 1
        for s_idx, chunk in zip(sec[np.concatenate([[0], bounds])], np.split(rssi, bounds)):
            if np.isfinite(chunk).any():
                med[s_idx] = np.nanmedian(chunk)
    return med, fps


def _nanmed(x: np.ndarray) -> float:
    return float(np.nanmedian(x)) if np.isfinite(x).any() else float("nan")


def _held_seconds(rssi: np.ndarray, s: int, base: float, step_db: float, calm: int = 5) -> float:
    """Seconds from onset ``s`` until RSSI is back within step_db/2 of ``base`` for ``calm`` consecutive seconds (or the end)."""
    back = np.isfinite(rssi) & (np.abs(rssi - base) < step_db / 2)
    run = 0
    for k in range(s, len(rssi)):
        run = run + 1 if back[k] else 0
        if run >= calm:
            return float(k - calm + 1 - s)
    return float(len(rssi) - s)


def detect_events(rssi: np.ndarray, fps: np.ndarray, t0_ms: int, node: int, *, pre: int = PRE_S, hold: int = HOLD_S, step_db: float = STEP_DB) -> list[Event]:
    """Held RSSI steps and frame-rate collapses inside one recording (onset = first second of the earliest qualifying window)."""
    events: list[Event] = []
    n = len(rssi)
    quiet_until = {"rssi_up": 0, "rssi_down": 0, "rate_collapse": 0}  # per direction: a step and its REVERSAL are both real events
    for s in range(pre, n - hold + 1):
        before_r, after_r = rssi[s - pre:s], rssi[s:s + hold]
        before_f, after_f = fps[s - pre:s], fps[s:s + hold]
        base, new = _nanmed(before_r), _nanmed(after_r)
        direction = "rssi_up" if new > base else "rssi_down"
        if np.isfinite(base) and np.isfinite(new) and s >= quiet_until[direction]:
            if abs(new - base) >= step_db:
                beyond = np.sign(new - base) * (after_r - base) >= step_db
                if np.isfinite(after_r).sum() >= 0.5 * hold and beyond.sum() / max(1, np.isfinite(after_r).sum()) >= HELD_FRACTION:
                    events.append(Event(node, t0_ms + s * 1000, "rssi_step", new - base, float(np.median(before_f)), float(np.median(after_f)), base, new, held_s=_held_seconds(rssi, s, base, step_db)))
                    quiet_until[direction] = s + pre
        if s >= quiet_until["rate_collapse"]:
            base_f, new_f = float(np.median(before_f)), float(np.median(after_f))
            if base_f >= MIN_BASELINE_FPS and new_f <= COLLAPSE * base_f and (after_f <= 0.85 * base_f).mean() >= COLLAPSE_FRACTION:
                events.append(Event(node, t0_ms + s * 1000, "rate_collapse", None, base_f, new_f, _nanmed(before_r), _nanmed(after_r)))
                quiet_until["rate_collapse"] = s + pre
    return _mark_reversals(sorted(events, key=lambda e: e.t_ms))


def _mark_reversals(events: list[Event]) -> list[Event]:
    out: list[Event] = []
    for i, e in enumerate(events):
        prev = next((p for p in reversed(events[:i]) if p.kind == "rssi_step"), None)
        if (
            e.kind == "rssi_step"
            and prev is not None
            and np.sign(e.delta_db) != np.sign(prev.delta_db)
            and abs(e.rssi_after - prev.rssi_before) <= PERSIST_DB
            and e.t_ms - prev.t_ms <= (PRE_S + HOLD_S) * 1000
        ):
            e = replace(e, reversal=True)
        out.append(e)
    return out


def edge_stats(rssi: np.ndarray, fps: np.ndarray, *, last: bool, edge: int = EDGE_S) -> tuple[float, float]:
    sl = slice(max(0, len(rssi) - edge), len(rssi)) if last else slice(0, min(len(rssi), edge))
    return _nanmed(rssi[sl]), float(np.median(fps[sl]))


@dataclass
class RecordingLinks:
    """Everything the epoch logic needs about one recording."""
    rid: str
    day: str
    t_start_ms: int
    t_end_ms: int
    label: str = ""
    events: dict[int, list[Event]] = field(default_factory=dict)             # node -> in-recording events
    edges: dict[int, dict[str, tuple[float, float]]] = field(default_factory=dict)  # node -> {"first": (rssi, fps), "last": (...)}


EMPTY_LABELS = ("empty", "empty_fan")
PERSIST_DB = 3.0


def analyze_recording(rid: str, day: str, nodes: dict[int, NodeSeries], t_start_ms: int, t_end_ms: int, label: str = "", *, step_db: float = STEP_DB, hold: int = HOLD_S) -> RecordingLinks:
    n_sec = int((t_end_ms - t_start_ms) // 1000) + 1
    out = RecordingLinks(rid, day, t_start_ms, t_end_ms, label)
    for node, series in nodes.items():
        rssi, fps = second_series(series, t_start_ms, n_sec)
        out.events[node] = detect_events(rssi, fps, t_start_ms, node, hold=hold, step_db=step_db)
        out.edges[node] = {"first": edge_stats(rssi, fps, last=False), "last": edge_stats(rssi, fps, last=True)}
    return out


def gap_events(prev: RecordingLinks, nxt: RecordingLinks, *, step_db: float = STEP_DB) -> list[Event]:
    """Events between two consecutive recordings (same or different day). The change happened somewhere in the gap."""
    ev: list[Event] = []
    if prev.day != nxt.day:
        return [Event(0, nxt.t_start_ms, "day_boundary", None, None, None, None, None, in_gap=True)]
    for node in sorted(set(prev.edges) & set(nxt.edges)):
        (r0, f0), (r1, f1) = prev.edges[node]["last"], nxt.edges[node]["first"]
        if np.isfinite(r0) and np.isfinite(r1) and abs(r1 - r0) >= step_db:
            ev.append(Event(node, nxt.t_start_ms, "gap_step", r1 - r0, f0, f1, r0, r1, in_gap=True))
        elif f0 >= MIN_BASELINE_FPS and f1 <= COLLAPSE * f0:
            ev.append(Event(node, nxt.t_start_ms, "gap_collapse", None, f0, f1, r0, r1, in_gap=True))
    return ev


def classify_persistence(links: list[RecordingLinks]) -> list[RecordingLinks]:
    """Mark every in-recording event persistent or not (in place; returns the chronologically sorted list).

    rssi_step: persistent iff the median of the recording's last EDGE_S seconds is within PERSIST_DB of the new level AND the
    next recording of the same day (if any) starts within PERSIST_DB of it. rate_collapse: the same with frame rates (<= 0.85 x
    the pre-event rate). With no next recording the event is persistent=None (cannot be confirmed)."""
    links.sort(key=lambda r: r.t_start_ms)
    for i, rec in enumerate(links):
        nxt = links[i + 1] if i + 1 < len(links) and links[i + 1].day == rec.day else None
        for node, evs in rec.events.items():
            for k, e in enumerate(evs):
                last_r, last_f = rec.edges[node]["last"]
                nxt_r, nxt_f = nxt.edges[node]["first"] if nxt and node in nxt.edges else (float("nan"), float("nan"))
                if e.kind == "rssi_step":
                    here = bool(np.isfinite(last_r) and abs(last_r - e.rssi_after) <= PERSIST_DB)
                    ahead = None if nxt is None else bool(np.isfinite(nxt_r) and abs(nxt_r - e.rssi_after) <= PERSIST_DB)
                else:
                    here = bool(last_f <= 0.85 * e.fps_before)
                    ahead = None if nxt is None else bool(nxt_f <= 0.85 * e.fps_before)
                verdict = None if ahead is None else (here and ahead)
                evs[k] = replace(e, persistent=verdict)
    return links


MIN_EMPTY_BOUNDARY_HOLD_S = 60.0


def is_boundary(rec: RecordingLinks, e: Event) -> bool:
    """A persistent change always splits. In an EMPTY/fan recording a non-persistent change splits only if it HELD
    >= MIN_EMPTY_BOUNDARY_HOLD_S (nobody legitimately changes the link there, but a 10-20 s flicker is an excursion, not a new
    link state). In an occupied recording a non-persistent step may be the person's own body, so it only warns."""
    if e.reversal:
        return False
    if e.persistent:
        return True
    return rec.label in EMPTY_LABELS and e.held_s is not None and e.held_s >= MIN_EMPTY_BOUNDARY_HOLD_S


@dataclass
class Timeline:
    """Epoch boundaries for one node set."""
    nodes: tuple[int, ...]
    boundaries: list[tuple[int, str]]                     # (t_ms, reason), sorted
    transitional: list[tuple[int, int, str]]              # (t_start_ms, t_end_ms, reason)
    _times: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._times = [b[0] for b in self.boundaries]

    def epoch_index(self, t_ms: int) -> int:
        return bisect.bisect_right(self._times, t_ms)

    def is_transitional(self, t_ms: int) -> bool:
        return any(a <= t_ms < b for a, b, _ in self.transitional)

    def epoch_name(self, t_ms: int) -> str:
        return f"E{self.epoch_index(t_ms) + 1:02d}"


def build_timeline(links: list[RecordingLinks], nodes: tuple[int, ...], step_db: float = STEP_DB) -> Timeline:
    """links must cover every recording of the study (any order); boundaries use only events of ``nodes``."""
    links = sorted(links, key=lambda r: r.t_start_ms)
    boundaries: list[tuple[int, str]] = []
    transitional: list[tuple[int, int, str]] = []
    for i, rec in enumerate(links):
        for node in nodes:
            for e in rec.events.get(node, []):
                if not is_boundary(rec, e):
                    continue  # ambiguous (possibly the occupant); reported, not used to split
                boundaries.append((e.t_ms, e.label()))
                transitional.append((e.t_ms - PRE_MARGIN_S * 1000, e.t_ms + SETTLE_S * 1000, e.label()))
        if i > 0:
            for e in gap_events(links[i - 1], rec, step_db=step_db):
                if e.kind == "day_boundary" or e.node in nodes:
                    boundaries.append((e.t_ms, e.label() if e.kind != "day_boundary" else "new calendar day"))
    boundaries.sort()
    return Timeline(tuple(nodes), boundaries, sorted(transitional))


def iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
