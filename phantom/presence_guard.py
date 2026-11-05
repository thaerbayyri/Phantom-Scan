"""Refuse a degenerate (saturated) logistic presence head.

A logistic head p = sigmoid(w.x + b) can only express "present" AND "absent" if its logit range straddles 0.
For an input of norm at most R the logit lies in [b - ||w||R, b + ||w||R], so the head is usable only when
||w||R > |b|. With R = 1 (L2-normalised input) this is the condition ||w|| > |bias|; the head published with
RuView (||w|| = 3.67, bias = 8.19) fails it: p(present) >= 0.989 for ANY unit-norm input (RuView issue #1521).

The check is pure (numpy only) so it can be unit-tested without loading any model. ADVISORY use only: a refused
head means the sidecar reports no presence evidence (``None``); it never touches the authoritative verdict (F1).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class PresenceHeadCheck:
    ok: bool
    reason: str
    weight_norm: float
    bias: float
    input_norm: float
    logit_min: float
    logit_max: float
    p_min: float
    p_max: float


def _sigmoid(x: float) -> float:
    x = max(-60.0, min(60.0, x))
    return 1.0 / (1.0 + math.exp(-x))


def presence_head_check(weights: Sequence[float], bias: float, input_norm: float = 1.0) -> PresenceHeadCheck:
    """ok iff the logit can reach both signs for inputs of norm <= ``input_norm`` (default 1: L2-normalised)."""
    w = np.asarray(weights, dtype=np.float64)
    nan = float("nan")
    if w.ndim != 1 or w.size == 0 or not np.isfinite(w).all() or not math.isfinite(bias) or not (math.isfinite(input_norm) and input_norm > 0):
        return PresenceHeadCheck(False, "invalid head: weights/bias/input_norm must be finite and non-empty", nan, float(bias), float(input_norm), nan, nan, nan, nan)
    norm = float(np.linalg.norm(w))
    lo, hi = bias - norm * input_norm, bias + norm * input_norm
    p_lo, p_hi = _sigmoid(lo), _sigmoid(hi)
    if norm * input_norm > abs(bias):
        return PresenceHeadCheck(True, "ok: logit range straddles 0", norm, float(bias), float(input_norm), lo, hi, p_lo, p_hi)
    side = "present" if bias > 0 else "absent"
    reason = (
        f"saturated: ||w||*R = {norm * input_norm:.2f} <= |bias| = {abs(bias):.2f}, so the head answers '{side}' "
        f"for every input of norm <= {input_norm:g} (p in [{p_lo:.3f}, {p_hi:.3f}])"
    )
    return PresenceHeadCheck(False, reason, norm, float(bias), float(input_norm), lo, hi, p_lo, p_hi)
