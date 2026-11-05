"""PS-FIX-06: a saturated logistic presence head must be refused (advisory presence unavailable)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from phantom.presence_guard import presence_head_check

ROOT = Path(__file__).resolve().parents[1]
SHIPPED = ROOT / "ai model and densepose" / "model" / "presence-head.json"


def head(norm: float, bias: float, n: int = 128) -> tuple[np.ndarray, float]:
    rng = np.random.default_rng(3)
    w = rng.standard_normal(n)
    return w / np.linalg.norm(w) * norm, bias


def test_the_known_saturated_shape_is_refused() -> None:
    w, b = head(3.67, 8.19)                          # RuView's published head: bias > ||w||
    res = presence_head_check(w, b)
    assert res.ok is False
    assert res.p_min >= 0.989 and res.logit_min > 4.5  # 'present' for ANY unit-norm input
    assert "saturated" in res.reason and "'present'" in res.reason


def test_saturation_toward_absent_is_refused_too() -> None:
    res = presence_head_check(*head(3.67, -8.19))
    assert res.ok is False and "'absent'" in res.reason and res.p_max <= 0.011


def test_a_head_whose_logit_range_straddles_zero_is_accepted() -> None:
    res = presence_head_check(*head(3.67, 0.5))
    assert res.ok is True and res.p_min < 0.5 < res.p_max


def test_boundary_requires_strictly_greater_norm() -> None:
    assert presence_head_check(*head(5.0, 5.0)).ok is False          # ||w|| == |bias|: refused
    assert presence_head_check(*head(5.0001, 5.0)).ok is True
    assert presence_head_check(*head(4.9999, -5.0)).ok is False


@pytest.mark.parametrize("w,b", [([], 0.0), ([1.0, float("nan")], 0.0), ([1.0, float("inf")], 0.0), ([1.0, 2.0], float("nan")), ([[1.0, 2.0]], 0.0)])
def test_invalid_heads_are_refused_not_crashed(w, b) -> None:
    res = presence_head_check(w, b)
    assert res.ok is False and "invalid" in res.reason


@pytest.mark.parametrize("r", [0.0, -1.0, float("nan"), float("inf")])
def test_invalid_input_norm_is_refused(r: float) -> None:
    assert presence_head_check([1.0, 2.0], 0.1, input_norm=r).ok is False


def test_input_norm_is_part_of_the_condition_and_documents_the_trade_off() -> None:
    w, b = head(3.67, 8.19)
    assert presence_head_check(w, b, input_norm=1.0).ok is False
    # For un-normalised activations of norm ~15 (the sidecar's own docstring; UNVERIFIED) the same numbers would pass.
    assert presence_head_check(w, b, input_norm=15.0).ok is True


@pytest.mark.skipif(not SHIPPED.is_file(), reason="model directory not present")
def test_the_head_shipped_in_the_repo_is_refused_with_the_documented_numbers() -> None:
    data = json.loads(SHIPPED.read_text(encoding="utf-8"))
    res = presence_head_check(data["weights"], data["bias"])
    assert res.ok is False
    assert res.weight_norm == pytest.approx(3.668, abs=0.01) and res.bias == pytest.approx(8.188, abs=0.01)
    assert res.p_min == pytest.approx(0.989, abs=0.001)


def test_the_sidecar_only_keeps_a_head_that_passed_the_check() -> None:
    src = (ROOT / "scripts" / "ai_inference.py").read_text(encoding="utf-8")
    call = src.index("presence_head_check(candidate_head.w, candidate_head.b)")
    keep = src.index("presence_head = candidate_head")
    refuse = src.index("Presence head REFUSED")
    assert call < src.index("if head_check.ok:") < keep < refuse
    assert src.count("presence_head = candidate_head") == 1 and "PresenceHead(PRESENCE_HEAD)" in src


def test_the_guard_cannot_touch_the_authoritative_verdict() -> None:
    src = (ROOT / "phantom" / "presence_guard.py").read_text(encoding="utf-8")
    assert "is_human" not in src and "targetIdentity" not in src
    assert math.isfinite(presence_head_check(*head(3.0, 1.0)).p_max)
