"""T4: leakage-proof API, determinism, fusion rules with known answers, insufficient-data behaviour."""
from __future__ import annotations

import inspect
import json

import numpy as np
import pytest

from scripts.presence_eval import twonode
from scripts.presence_eval.features import COVARIATES, FEATURES
from scripts.presence_eval.tables import RecTables
from scripts.presence_eval.twonode import (
    InsufficientData, LeakageError, MIN_WIN, Split, aggregate, assert_disjoint, combine, criteria, fit_model,
    run, run_candidate, score, splits_adjacent, splits_cross_session, splits_loro,
)


def table(n: int, mu: float, seed: int, sd: float = 1.0) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    t = {f: mu + sd * rng.standard_normal(n) for f in FEATURES}
    t.update({c: np.zeros(n) for c in COVARIATES})
    t["k"] = np.arange(n, dtype=np.int64)
    t["nframes"] = np.full(n, 90, dtype=np.int64)
    return t


def rec(subject: str, label: str, day: str, mu1: float, mu2: float, n: int = 300, seed: int = 0, t0: int = 0) -> RecTables:
    return RecTables(rid=f"{subject}_{label}_{day[4:]}_{t0:04d}", name=f"room1__{subject}__{label}__{day}T000000Z.jsonl", label=label,
                     subject=subject, day=day, t0_ms=t0, duration_s=n * 1.5, parts=1,
                     nodes={1: table(n, mu1, seed + 1), 2: table(n, mu2, seed + 2)})


def world() -> dict[str, RecTables]:
    recs = [
        rec("e1", "empty", "20261018", 0, 0, seed=10, t0=1), rec("e2", "empty", "20261018", 0, 0, seed=20, t0=2),
        rec("e3", "empty", "20261027", 0, 0, seed=30, t0=3), rec("e4", "empty", "20261027", 0, 0, seed=40, t0=4),
        rec("w1", "walking", "20261027", 10, 0, seed=50, t0=5),   # only node 1 sees the person
        rec("f1", "empty_fan", "20261027", 0, 0, seed=60, t0=6), rec("s1", "still", "20261025", 10, 10, seed=70, t0=7),
    ]
    return {r.rid: r for r in recs}


# ---- leakage -----------------------------------------------------------------------------

def test_fit_model_signature_has_no_way_to_receive_a_test_recording() -> None:
    assert list(inspect.signature(fit_model).parameters) == ["train", "feature", "rule", "alphas"]


def test_model_is_independent_of_the_test_recording() -> None:
    w = world()
    train = [w[r] for r in w if w[r].label == "empty"]
    before = fit_model(train, "decor", "max")
    w[next(r for r in w if w[r].label == "walking")].nodes[1]["decor"][:] = 1e9   # corrupt the test recording
    after = fit_model(train, "decor", "max")
    assert before == after


def test_models_refuse_non_empty_and_duplicate_training_recordings() -> None:
    w = world()
    empties = [t for t in w.values() if t.label == "empty"]
    for bad in ("walking", "empty_fan", "still"):
        with pytest.raises(LeakageError):
            fit_model([*empties[:2], next(t for t in w.values() if t.label == bad)], "decor", "max")
    with pytest.raises(LeakageError):
        fit_model([empties[0], empties[0]], "decor", "max")


def test_every_generated_split_keeps_test_out_of_train_and_trains_on_empties_only() -> None:
    w = world()
    for sp in (*splits_loro(w), *splits_adjacent(w), *splits_cross_session(w)):
        assert_disjoint(sp)
        assert all(w[r].label == "empty" for r in sp.train_ids)
        if sp.protocol == "cross_session":
            assert all(w[r].day != w[sp.test_id].day for r in sp.train_ids)
        if sp.protocol == "adjacent":
            assert w[sp.train_ids[0]].day == w[sp.test_id].day and len(sp.train_ids) == 1


def test_a_split_that_contains_its_own_test_recording_is_rejected() -> None:
    w = world()
    e = next(r for r in w if w[r].label == "empty")
    with pytest.raises(LeakageError):
        run_candidate(w, [Split("loro", e, (e, "x"), "pooled")], "decor", "max")


def test_threshold_is_the_training_quantile() -> None:
    w = world()
    train = [t for t in w.values() if t.label == "empty"]
    m = fit_model(train, "perturb", "max")
    flagged = np.concatenate([score(m, t)[1] >= m.threshold(0.05) for t in train])
    assert flagged.mean() == pytest.approx(0.05, abs=0.01)
    assert m.threshold(0.01) > m.threshold(0.05)


# ---- fusion rules with known answers -------------------------------------------------------

def test_combine_known_values() -> None:
    z1, z2 = np.array([1.0, 5.0, -1.0]), np.array([3.0, 2.0, -4.0])
    assert combine(z1, z2, "n1").tolist() == [1, 5, -1]
    assert combine(z1, z2, "n2").tolist() == [3, 2, -4]
    assert combine(z1, z2, "max").tolist() == [3, 5, -1]
    assert combine(z1, z2, "mean").tolist() == [2.0, 3.5, -2.5]
    assert combine(z1, z2, "and").tolist() == [1, 2, -4]
    with pytest.raises(ValueError):
        combine(z1, z2, "xor")


def test_rules_on_synthetic_world_where_only_node_1_sees_the_person() -> None:
    w = world()
    out = {}
    for rule in ("n1", "n2", "max", "and"):
        rows = run_candidate(w, splits_loro(w), "decor", rule)
        out[rule] = aggregate(rows)["loro/pooled"]["auc"]["walking"]["auc"]
    assert out["n1"] > 0.99 and out["max"] > 0.99          # sees node 1 / OR
    assert 0.35 < out["n2"] < 0.65                          # node 2 is blind
    assert out["and"] < 0.65                                # AND needs both nodes


# ---- determinism ---------------------------------------------------------------------------

def test_run_is_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(twonode, "N_BOOT", 25)
    monkeypatch.setattr(twonode, "FEATS", ("decor",))
    monkeypatch.setattr(twonode, "RULES", ("max", "and"))
    a, b = run(world()), run(world())
    strip = lambda d: {k: v for k, v in d.items() if k != "provenance"}
    assert json.dumps(strip(a), sort_keys=True, default=float) == json.dumps(strip(b), sort_keys=True, default=float)


# ---- insufficient data ---------------------------------------------------------------------

def test_class_with_fewer_than_min_windows_gets_insufficient_data_not_a_number() -> None:
    w = world()
    walk = next(t for t in w.values() if t.label == "walking")
    for node in (1, 2):                                       # truncate the positive class below MIN_WIN
        walk.nodes[node] = {c: v[: MIN_WIN - 1] for c, v in walk.nodes[node].items()}
    cell = aggregate(run_candidate(w, splits_loro(w), "decor", "max"))["loro/pooled"]
    assert cell["auc"]["walking"] == "insufficient data"
    assert cell["tpr"]["walking@1%"] == "insufficient data"
    assert criteria({"loro/pooled": cell, "cross_session/x": cell})["C1"] is False


def test_fit_model_with_too_few_training_windows_raises() -> None:
    tiny = rec("e", "empty", "20261018", 0, 0, n=MIN_WIN - 1)
    with pytest.raises(InsufficientData):
        fit_model([tiny], "decor", "max")


def test_missing_node_gives_no_windows_not_zero_filled() -> None:
    r = rec("e", "empty", "20261018", 0, 0)
    del r.nodes[2]
    k, x1, x2 = twonode.pair_series(r, "decor")
    assert k.size == x1.size == x2.size == 0
