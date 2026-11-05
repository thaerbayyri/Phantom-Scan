"""PS-FIX-09: fan / periodicity candidate, OFFLINE. Output is the design of an ADVISORY "mechanical periodicity" label, never a veto.

    PRESENCE_EVAL_OUT=reports/fix-2026-11 python -m scripts.presence_eval.periodicity

Feature (per node, per tumbling window of WIN_S seconds on a grid shared by all nodes of a recording): resample the amplitudes to a
uniform grid from the recorder timestamps (linear interpolation; windows with a gap > MAX_GAP_MS or too few frames are dropped),
detrend, keep the TOPK highest-variance subcarriers, Hann + FFT, normalise each subcarrier's band power to 1, average, and report
  peak_ratio   = max / median of the averaged spectrum inside BAND_HZ       (how peaky the spectrum is)
  narrow_share = share of band power within +/- NARROW_HZ of that peak      (how much of the power the peak holds)
  peak_hz      = frequency of the peak.
The grid rate is below the true arrival rate and the arrivals are jittered (PS-FIX-07), so content above ~20 Hz is not observable and a
fan whose blades pass faster than that is aliased or invisible. The feature is data-driven; no fan frequency is assumed.

Criteria (from the task): fan false-positive rate <= empty false-positive rate, and the walking AUC lower bound reduced by <= 0.05, when
a would-be veto flags windows as mechanical. The reference detector is the repo's AGC-normalised perturbation (1.5 s windows, max over
nodes 1 and 2), thresholded at the 95th percentile of the session's calibration empty. The label threshold is fitted on the OTHER session
(cross-session). Only two sessions have a fan; no recording has a person AND a fan, which this analysis cannot see around.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.signal import detrend

from .features import fuse_max
from .jsonutil import dump_json
from .provenance import default_out_dir, provenance
from .recordings import NodeSeries, group_recordings, load_recording
from .stats import block_bootstrap_auc, empty_pair_control
from .tables import REC_CACHE, ROOM_DIR, load_tables

OUT_DIR = default_out_dir()
# PS-FIX-40: a point-wise linear resample folds the 33.3 Hz ping cadence (and its harmonics) onto |k*33.33 - n*fs|. On 50 Hz that is 16.67 Hz and on
# 64 Hz the fundamental leaves 1-20 Hz (30.67 Hz) but harmonics 2, 4, 6 land at 2.67, 5.33, 8.0 Hz, all inside it. 100 Hz = 3 x 33.33 Hz is the grid
# on which EVERY harmonic folds to 0 Hz (removed by detrending) or to 33.33 Hz (above the 20 Hz band): see scripts/presence_eval/alias_check.py.
GRID_HZ = 100.0
GRIDS_HZ = (50.0, 64.0, 100.0)   # the two older grids stay so that earlier results remain reproducible and comparable
PING_HZ = 1000.0 / 30.0
MAX_GAP_MS = 500
MIN_FRAME_RATE = 20.0
BAND_HZ = (1.0, 20.0)
NARROW_HZ = 0.5
CONSTANT_RELATIVE_TOL = 1e-9
TOPK = 8
WINDOWS_S = (10, 15, 20)
MAIN_WIN_S = 15
DETECTOR_WINDOW_S = 1.5
DETECTOR_QUANTILE = 0.95
FEATURES = ("peak_ratio", "narrow_share")
BOOT_BLOCK = 4
S7_HEAD_S = 187.5     # s7 walking before node 1's persistent step (see movement.py S7_HEAD_LAST_K)


def resample_uniform(t_ms: np.ndarray, a: np.ndarray, t_ref_ms: int, fs: float, max_gap_ms: int = MAX_GAP_MS) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Grid in seconds since ``t_ref_ms`` (shared by all nodes), linearly interpolated amplitudes, and a per-point validity flag
    (inside the node's own time span AND the bracketing gap <= max_gap_ms)."""
    t = (t_ms - t_ref_ms) / 1000.0
    grid = np.arange(0.0, t[-1], 1.0 / fs)
    idx = np.clip(np.searchsorted(t, grid), 1, len(t) - 1)
    valid = ((t_ms[idx] - t_ms[idx - 1]) <= max_gap_ms) & (grid >= t[0]) & (grid <= t[-1])
    out = np.empty((len(grid), a.shape[1]))
    for c in range(a.shape[1]):
        out[:, c] = np.interp(grid, t, a[:, c])
    return grid, out, valid


def spectral_features(x: np.ndarray, fs: float) -> dict[str, float]:
    nan = {"peak_ratio": float("nan"), "narrow_share": float("nan"), "peak_hz": float("nan")}
    x = np.asarray(x, dtype=np.float64)
    if np.ptp(x, axis=0).max() <= CONSTANT_RELATIVE_TOL * max(1.0, float(np.abs(x).max())):
        return nan      # a constant window has no spectrum; detrending would leave float residue that looks like a huge peak
    x = detrend(x, axis=0, type="linear")
    keep = np.argsort(x.var(axis=0))[-TOPK:]
    xs = x[:, keep] * np.hanning(len(x))[:, None]
    power = np.abs(np.fft.rfft(xs, axis=0)) ** 2
    freq = np.fft.rfftfreq(len(x), 1.0 / fs)
    sel = (freq >= BAND_HZ[0]) & (freq <= BAND_HZ[1])
    band, f = power[sel], freq[sel]
    tot = band.sum(axis=0)
    if band.shape[0] < 5 or not np.all(tot > 0):
        return nan
    mean = (band / tot).mean(axis=1)
    peak = int(np.argmax(mean))
    w = max(1, int(math.ceil(NARROW_HZ / (f[1] - f[0]))))
    return {"peak_ratio": float(mean[peak] / np.median(mean)), "narrow_share": float(mean[max(0, peak - w): peak + w + 1].sum()), "peak_hz": float(f[peak])}


def window_table(series: NodeSeries, t0_ms: int, win_s: float, end_ms: int | None = None, fs: float = GRID_HZ) -> dict[str, np.ndarray]:
    """Tumbling windows on the grid anchored at ``t0_ms`` (the recording's first frame, shared by all nodes); k = window number."""
    sel = slice(None) if end_ms is None else (series.t <= end_ms)
    t, a = series.t[sel], series.a[sel]
    empty = {"k": np.zeros(0, dtype=np.int64), "peak_ratio": np.zeros(0), "narrow_share": np.zeros(0), "peak_hz": np.zeros(0)}
    if len(t) < 2 or t[-1] - t0_ms < win_s * 1000:
        return empty
    grid, ag, valid = resample_uniform(t, a, t0_ms, fs)
    n = int(win_s * fs)
    rows: dict[str, list[float]] = {"k": [], "peak_ratio": [], "narrow_share": [], "peak_hz": []}
    for i in range(len(grid) // n):
        sl = slice(i * n, (i + 1) * n)
        lo, hi = t0_ms + grid[sl][0] * 1000, t0_ms + grid[sl][-1] * 1000
        frames = int(np.searchsorted(t, hi, side="right") - np.searchsorted(t, lo, side="left"))
        if not valid[sl].all() or frames < MIN_FRAME_RATE * win_s:
            continue
        feats = spectral_features(ag[sl], fs)
        rows["k"].append(i)
        for f in ("peak_ratio", "narrow_share", "peak_hz"):
            rows[f].append(feats[f])
    return {f: np.asarray(v, dtype=np.int64 if f == "k" else np.float64) for f, v in rows.items()}


@dataclass(frozen=True)
class Spec:
    key: str
    subject: str
    label: str
    stamp: str
    cut_s: float | None = None


SESSIONS: dict[str, dict] = {
    "oct18": {
        "calib_empty": Spec("s1_empty_1756", "s1", "empty", "20261018T175601Z"),
        "held_empty": Spec("s1_empty_1802", "s1", "empty", "20261018T180250Z"),
        "fan": Spec("s1_fan_2039", "s1", "empty_fan", "20261018T203921Z"),
        "person": [Spec("s1_two_people_1730", "s1", "two_people", "20261018T173055Z")],
    },
    "oct27": {
        "calib_empty": Spec("s6_empty_1942", "s6", "empty", "20261027T194207Z"),
        "held_empty": None,
        "fan": Spec("s5_fan_1938", "s5", "empty_fan", "20261027T193823Z"),
        "person": [Spec("s1_still_1936", "s1", "still", "20261027T193610Z"), Spec("s7_walking_head_1945", "s7", "walking", "20261027T194537Z", S7_HEAD_S)],
    },
}
EXTRA_EMPTIES = (Spec("s8_empty_1953", "s8", "empty", "20261027T195356Z"), Spec("s9_empty_2047", "s9", "empty", "20261027T204759Z"))


def _paths(spec: Spec):
    for name, paths in group_recordings(ROOM_DIR).items():
        parts = name.split("__")
        if parts[1] == spec.subject and parts[2] == spec.label and parts[3].startswith(spec.stamp):
            return paths
    raise LookupError(f"recording not found: {spec}")


def load_spec(spec: Spec, win_s: int, fs: float = GRID_HZ) -> dict:
    paths = _paths(spec)
    rec = load_recording(paths, REC_CACHE)
    end = None if spec.cut_s is None else int(rec.t_min + spec.cut_s * 1000)
    spectral = {n: window_table(s, rec.t_min, win_s, end, fs) for n, s in rec.nodes.items() if n in (1, 2)}
    tabs = load_tables(paths)
    det: dict = {}
    if 1 in tabs.nodes and 2 in tabs.nodes:
        k, v = fuse_max(tabs.nodes, (1, 2), "perturb_agc")
        if spec.cut_s is not None:
            keep = (k + 1) * DETECTOR_WINDOW_S * 1000 <= spec.cut_s * 1000
            k, v = k[keep], v[keep]
        det = {"k": k, "score": v}
    return {"spec": spec, "spectral": spectral, "detector": det, "rssi_median": {n: float(np.nanmedian(s.rssi)) for n, s in rec.nodes.items()}, "label": spec.label}


def fused_peak(rec: dict, feature: str = "peak_ratio") -> tuple[np.ndarray, np.ndarray]:
    """Per window: max over nodes 1 and 2 where both are finite."""
    t = rec["spectral"]
    if 1 not in t or 2 not in t:
        return np.zeros(0, dtype=np.int64), np.zeros(0)
    common = np.intersect1d(t[1]["k"][np.isfinite(t[1][feature])], t[2]["k"][np.isfinite(t[2][feature])])
    if common.size == 0:
        return common, np.zeros(0)
    v = np.vstack([t[n][feature][np.searchsorted(t[n]["k"], common)] for n in (1, 2)]).max(axis=0)
    return common, v


def youden_threshold(pos: np.ndarray, neg: np.ndarray) -> float | None:
    """Value c maximising P(pos >= c) - P(neg >= c); None when a class is empty."""
    if pos.size == 0 or neg.size == 0:
        return None
    best = max(((float(np.mean(pos >= c) - np.mean(neg >= c)), float(c)) for c in np.unique(np.concatenate([pos, neg]))))
    return best[1]


def mech_windows(rec: dict, tau: float) -> set[int]:
    k, v = fused_peak(rec)
    return {int(a) for a, b in zip(k, v) if b >= tau}


def _vetoed(det_k: np.ndarray, mech: set[int], win_s: int) -> np.ndarray:
    ratio = int(round(win_s / DETECTOR_WINDOW_S))
    return np.array([(int(k) // ratio) in mech for k in det_k], dtype=bool)


def _rate(f: np.ndarray) -> float | None:
    return float(f.mean()) if f.size else None


def veto_session(name: str, recs: dict[str, dict], tau: float | None, win_s: int) -> dict:
    theta = float(np.quantile(recs["calib_empty"]["detector"]["score"], DETECTOR_QUANTILE))
    out: dict = {"session": name, "tau": tau, "theta_detector": theta, "window_s": win_s, "classes": {}}
    if tau is None:
        out["status"] = "no tau: the training session has an empty class"
        return out
    for cls, rec in recs.items():
        det = rec["detector"]
        mech = mech_windows(rec, tau)
        n_spec = fused_peak(rec)[0].size
        flagged = det["score"] > theta
        out["classes"][cls] = {"label": rec["label"], "spectral_windows": int(n_spec), "mechanical_share": float(len(mech) / n_spec) if n_spec else None,
                                "detector_windows": int(flagged.size), "flag_rate": _rate(flagged), "flag_rate_with_veto": _rate(flagged & ~_vetoed(det["k"], mech, win_s))}
    return out


def auc_with_and_without_veto(recs: dict[str, dict], person_key: str, tau: float, win_s: int, seed: int = 20261103) -> dict:
    out = {}
    for name, veto in (("without_veto", False), ("with_veto", True)):
        scores = []
        for rec in (recs[person_key], recs["calib_empty"]):
            s = rec["detector"]["score"].copy()
            if veto:
                s[_vetoed(rec["detector"]["k"], mech_windows(rec, tau), win_s)] = -np.inf
            scores.append(s)
        out[name] = block_bootstrap_auc(scores[0], scores[1], block=BOOT_BLOCK * int(win_s / DETECTOR_WINDOW_S), seed=seed)
    return out


def _pool(items: list, feature: str = "peak_ratio") -> np.ndarray:
    parts = [fused_peak(r, feature)[1] for r in items if r is not None]
    return np.concatenate(parts) if parts else np.zeros(0)


def alias_share(rec: dict, fs: float) -> float | None:
    """Share of node-1/2 windows whose spectral peak sits within 0.3 Hz of the alias of the 33.3 Hz ping cadence on this grid."""
    target = abs(fs - PING_HZ) if PING_HZ > fs / 2 else PING_HZ
    pk = np.concatenate([rec["spectral"][n]["peak_hz"] for n in (1, 2) if n in rec["spectral"]])
    pk = pk[np.isfinite(pk)]
    return float(np.mean(np.abs(pk - target) <= 0.3)) if pk.size else None


def analyse_window(loaded: dict, extra: list[dict], win_s: int, fs: float) -> dict:
    out: dict = {"recordings": {}, "separability": {}, "control_empty_vs_empty": {}, "veto": {}}
    flat: dict[str, dict] = {}
    for roles in loaded.values():
        for v in roles.values():
            for r in (v if isinstance(v, list) else [v]):
                if r is not None:
                    flat[r["spec"].key] = r
    for r in extra:
        flat[r["spec"].key] = r
    for key, r in flat.items():
        k, v = fused_peak(r)
        ns = fused_peak(r, "narrow_share")[1]
        out["recordings"][key] = {"label": r["label"], "windows": int(k.size), "peak_ratio_median": float(np.median(v)) if v.size else None,
                                  "peak_ratio_q10_q90": [float(np.quantile(v, 0.1)), float(np.quantile(v, 0.9))] if v.size else None,
                                  "narrow_share_median": float(np.median(ns)) if ns.size else None, "share_peak_at_ping_alias": alias_share(r, fs), "rssi_median_dbm": r["rssi_median"]}
    for sname, roles in loaded.items():
        for f in FEATURES:
            emp = _pool([roles["calib_empty"], roles["held_empty"]], f)
            fan, pers = _pool([roles["fan"]], f), _pool(roles["person"], f)
            out["separability"][f"{sname}/{f}"] = {"fan_vs_empty": block_bootstrap_auc(fan, emp, block=BOOT_BLOCK), "person_vs_empty": block_bootstrap_auc(pers, emp, block=BOOT_BLOCK),
                                                   "fan_vs_person": block_bootstrap_auc(fan, pers, block=BOOT_BLOCK)}
    empties = {r["spec"].key: fused_peak(r)[1] for r in (loaded["oct18"]["calib_empty"], loaded["oct18"]["held_empty"], loaded["oct27"]["calib_empty"], *extra)}
    out["control_empty_vs_empty"] = empty_pair_control(empties, block=BOOT_BLOCK, min_windows=8)
    taus = {s: youden_threshold(_pool([r["fan"]]), np.concatenate([_pool([r["calib_empty"], r["held_empty"]]), _pool(r["person"])])) for s, r in loaded.items()}
    out["tau_fitted_on"] = taus
    for target, source in (("oct18", "oct27"), ("oct27", "oct18")):
        tau = taus[source]
        roles = loaded[target]
        recs = {"calib_empty": roles["calib_empty"], "held_empty": roles["held_empty"], "fan": roles["fan"], **{p["spec"].key: p for p in roles["person"]}}
        recs = {k: v for k, v in recs.items() if v is not None}
        v = veto_session(target, recs, tau, win_s)
        if tau is not None:
            v["auc_person_vs_calib_empty"] = {p["spec"].key: auc_with_and_without_veto(recs, p["spec"].key, tau, win_s) for p in roles["person"]}
        out["veto"][f"{target}_tau_from_{source}"] = v
    return out


def run() -> dict:
    res: dict = {"provenance": provenance("python -m scripts.presence_eval.periodicity"), "config": {
        "grids_hz": GRIDS_HZ, "band_hz": BAND_HZ, "topk": TOPK, "windows_s": WINDOWS_S, "main_window_s": MAIN_WIN_S, "narrow_hz": NARROW_HZ, "ping_hz": PING_HZ,
        "detector": f"perturb_agc max(N1,N2), q{int(DETECTOR_QUANTILE * 100)} of the session calibration empty"}, "by_grid_window": {}}
    for fs in GRIDS_HZ:
        for win_s in WINDOWS_S:
            loaded = {s: {role: ([load_spec(p, win_s, fs) for p in v] if isinstance(v, list) else (load_spec(v, win_s, fs) if v else None)) for role, v in roles.items()} for s, roles in SESSIONS.items()}
            res["by_grid_window"][f"{fs:g}Hz/{win_s}s"] = analyse_window(loaded, [load_spec(e, win_s, fs) for e in EXTRA_EMPTIES], win_s, fs)
    return res


def _f(v: float | None) -> str:
    return "n/a" if v is None or v != v else f"{v:.2f}"


def _ci(d: dict) -> str:
    return f"{_f(d['auc'])} [{_f(d['lo'])}, {_f(d['hi'])}] (n={d['n_pos']}/{d['n_neg']})"


def render(res: dict) -> str:
    lines = ["# PS-FIX-09 — fan / periodicity candidate (offline)", "",
             "peak_ratio = max/median of the spectrum of the top-variance subcarriers, 1-20 Hz, max over nodes 1 and 2. AUC with a moving-block bootstrap 95 % CI.", ""]
    for key, b in res["by_grid_window"].items():
        lines += [f"## grid/window {key}", "", "| recording | class | windows | peak_ratio median (q10-q90) | peak at 33.3 Hz-alias |", "|--|--|--|--|--|"]
        for name, v in b["recordings"].items():
            q = v["peak_ratio_q10_q90"] or [None, None]
            lines.append(f"| {name} | {v['label']} | {v['windows']} | {_f(v['peak_ratio_median'])} ({_f(q[0])}-{_f(q[1])}) | {_f(v['share_peak_at_ping_alias'])} |")
        lines += ["", "| session | fan vs empty | person vs empty | fan vs person |", "|--|--|--|--|"]
        for name, v in b["separability"].items():
            if name.endswith("peak_ratio"):
                lines.append(f"| {name} | {_ci(v['fan_vs_empty'])} | {_ci(v['person_vs_empty'])} | {_ci(v['fan_vs_person'])} |")
        c = b["control_empty_vs_empty"]
        lines += ["", f"Empty-vs-empty control (C4): passes={c.get('passes')}, worst symmetric upper bound {_f(c.get('worst_symmetric_upper_bound'))} (limit 0.65).",
                  f"Label threshold tau fitted on the other session: {{{', '.join(f'{k}: {_f(v)}' for k, v in b['tau_fitted_on'].items())}}}.", "",
                  "| veto test | class | mechanical share | detector flag rate | with veto |", "|--|--|--|--|--|"]
        for vk, v in b["veto"].items():
            for cls, x in v["classes"].items():
                lines.append(f"| {vk} | {cls} | {_f(x['mechanical_share'])} | {_f(x['flag_rate'])} | {_f(x['flag_rate_with_veto'])} |")
            for person, a in v.get("auc_person_vs_calib_empty", {}).items():
                lines.append(f"| {vk} | AUC {person} | | {_ci(a['without_veto'])} | {_ci(a['with_veto'])} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    res = run()
    dump_json(OUT_DIR / "results" / "periodicity.json", res)
    (OUT_DIR / "results" / "periodicity.md").write_text(render(res), encoding="utf-8")
    print(f"written {OUT_DIR / 'results' / 'periodicity.json'} and periodicity.md")


if __name__ == "__main__":
    main()
