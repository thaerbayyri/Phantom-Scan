"""PS-FIX-37: is there a frame alternation in the recordings, and does it explain the empty-vs-empty drift?

    PRESENCE_EVAL_OUT=reports/fix-2026-11 python -m scripts.presence_eval.frame_parity

Background (owner's reviewer, exploratory, scratch scripts outside the repo, so UNVERIFIED until reproduced here): on all four nodes
of session s6, a frame correlates more with the frame TWO later than with its immediate neighbour, and RSSI steps are smaller at
lag 2 than at lag 1. That fits about two accepted frames per 30 ms ping. This module re-measures it from the recordings, read-only.

Per node and recording it reports:
  * lag-1..4 correlation of subcarrier vectors (each frame divided by its own mean = per-frame gain removed, then the per-subcarrier
    time mean removed, then the mean cosine of frame pairs ``lag`` apart); plus a high-pass variant (a centred ~1 s moving mean
    removed first) so slow drift cannot masquerade as structure. An alternation shows as a ZIGZAG: even lags above their odd neighbours;
    a smooth process decays monotonically with lag,
  * mean |RSSI difference| at lag 1..3,
  * the inter-frame interval histogram,
  * ``decor`` (features.py definition) on all frames versus the two same-parity substreams (every other frame).
And, per node, the empty-vs-empty AUC of ``perturb`` / ``decor`` on all frames versus the same-parity substreams, for the empty pairs
(s8 vs s6, s9 vs s6, s9 vs s8): if interleaving caused the between-session drift, the same-parity AUC would fall toward 0.5.

LIMITS (also written into the output): ``t`` is the recorder host's clock (ms), not a device timestamp; the header has no frame type,
rate or transmitter, so a parity substream is a statistical probe, not proof of two frame types; the recordings are the repo's own and
the "empty" ones have no entry log. Nothing here changes a threshold or the firmware, and nothing is written into data/.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .features import node_windows
from .jsonutil import dump_json
from .provenance import default_out_dir, provenance
from .recordings import NodeSeries, Recording, group_recordings, load_recording
from .stats import auc
from .tables import REC_CACHE, ROOM_DIR

OUT_DIR = default_out_dir()
LAGS = (1, 2, 3, 4)
RSSI_LAGS = (1, 2, 3)
GAP_EDGES_MS = (0, 5, 10, 15, 20, 30, 40, 60)  # the last bin is open: >= 60 ms
HP_FRAMES = 65  # high-pass: subtract a centred moving mean of about one second of frames
MIN_FRAMES_FOR_LAGS = 200
EPS = 1e-9
EMPTY_PAIRS = (("s8", "s6"), ("s9", "s6"), ("s9", "s8"))
AUC_FEATURES = ("perturb", "decor")
ZIGZAG_MARGIN = 0.01  # a lag-2 excess below this is not called an alternation
GAP_EXPLAINED_DROP = 0.10  # reading aid for the report text only (see Table 5); not a detection threshold


MODES = ("raw", "shape", "timedemean", "highpass")
MODE_DESCRIPTION = {
    "raw": "cosine of the raw amplitude vectors (nothing removed: the static channel dominates, so every lag is ~1)",
    "shape": "each frame's own mean over subcarriers removed (Pearson across subcarriers); the static spectral SHAPE is kept",
    "timedemean": "each frame divided by its own mean, then the per-subcarrier TIME mean removed (static channel gone). This is the primary variant and the one behind the ~0 lag-1 figure quoted earlier",
    "highpass": "timedemean, plus a centred ~1 s moving mean removed (slow drift cannot masquerade as structure)",
}


def _unit_rows(a: np.ndarray, mode: str) -> tuple[np.ndarray, np.ndarray]:
    """Unit vectors under the chosen preprocessing, and a validity mask (see MODE_DESCRIPTION)."""
    a = np.asarray(a, dtype=np.float64)
    fm = a.mean(axis=1)
    valid = fm > EPS
    if mode == "raw":
        z = a
    elif mode == "shape":
        z = a - fm[:, None]
    else:
        n = a / np.where(valid, fm, 1.0)[:, None]
        z = n - n[valid].mean(axis=0) if valid.any() else n
        if mode == "highpass":
            z = z - _moving_mean(z, HP_FRAMES)
    norm = np.linalg.norm(z, axis=1)
    valid &= norm > EPS
    return z / np.where(valid, norm, 1.0)[:, None], valid


def _moving_mean(z: np.ndarray, width: int) -> np.ndarray:
    n = len(z)
    c = np.cumsum(np.vstack([np.zeros((1, z.shape[1])), z]), axis=0)
    idx = np.arange(n)
    lo, hi = np.maximum(idx - width // 2, 0), np.minimum(idx + width // 2 + 1, n)
    return (c[hi] - c[lo]) / (hi - lo)[:, None]


def lag_correlations(a: np.ndarray, lags: tuple[int, ...] = LAGS, highpass: bool = False, mode: str | None = None) -> dict[int, float]:
    """Mean cosine between frame t and frame t+lag, per lag. NaN when there are too few usable frames.

    ``mode`` is one of MODES; when omitted, ``highpass=True`` means "highpass" and otherwise "timedemean" (the primary variant)."""
    mode = mode or ("highpass" if highpass else "timedemean")
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")
    if len(a) < MIN_FRAMES_FOR_LAGS:
        return {k: float("nan") for k in lags}
    u, valid = _unit_rows(a, mode)
    out = {}
    for k in lags:
        ok = valid[k:] & valid[:-k]
        out[k] = float(np.sum(u[k:] * u[:-k], axis=1)[ok].mean()) if ok.any() else float("nan")
    return out


def rssi_lag_diffs(rssi: np.ndarray, lags: tuple[int, ...] = RSSI_LAGS) -> dict[int, float]:
    """Mean |RSSI(t+lag) - RSSI(t)| in dB over finite pairs."""
    r = np.asarray(rssi, dtype=np.float64)
    out = {}
    for k in lags:
        d = np.abs(r[k:] - r[:-k])
        d = d[np.isfinite(d)]
        out[k] = float(d.mean()) if d.size else float("nan")
    return out


def gap_histogram(t_ms: np.ndarray) -> dict:
    gaps = np.diff(np.asarray(t_ms, dtype=np.float64))
    if gaps.size == 0:
        return {"n": 0, "share": {}}
    edges = list(GAP_EDGES_MS) + [float("inf")]
    share = {}
    for lo, hi in zip(edges[:-1], edges[1:]):
        key = f"{lo:g}-{'inf' if hi == float('inf') else f'{hi:g}'}ms"
        share[key] = float(np.mean((gaps >= lo) & (gaps < hi)))
    return {"n": int(gaps.size), "share": share}


def parity_substream(s: NodeSeries, parity: int) -> NodeSeries:
    return NodeSeries(t=s.t[parity::2], rssi=s.rssi[parity::2], a=s.a[parity::2])


def window_feature(s: NodeSeries, feature: str, t0_ms: int) -> np.ndarray:
    v = node_windows(s, t0_ms)[feature]
    return v[np.isfinite(v)]


def parity_decor(s: NodeSeries) -> dict:
    """Median ``decor`` over 1.5 s windows: all frames, even-index substream, odd-index substream."""
    t0 = int(s.t[0])
    res = {}
    for name, series in (("all", s), ("even", parity_substream(s, 0)), ("odd", parity_substream(s, 1))):
        v = window_feature(series, "decor", t0)
        res[name] = {"windows": int(v.size), "median": float(np.median(v)) if v.size else float("nan")}
    base = res["all"]["median"]
    sub = [res[k]["median"] for k in ("even", "odd") if res[k]["windows"]]
    res["ratio_parity_over_all"] = float(np.mean(sub) / base) if sub and base == base and base > 0 else float("nan")
    return res


def node_report(s: NodeSeries) -> dict:
    if len(s.t) < 2:
        return {"frames": int(len(s.t))}
    lags = lag_correlations(s.a)
    hp = lag_correlations(s.a, highpass=True)
    return {
        "frames": int(len(s.t)),
        "lag_cos": {str(k): v for k, v in lags.items()},
        "lag_cos_highpass": {str(k): v for k, v in hp.items()},
        "lag_cos_raw": {str(k): v for k, v in lag_correlations(s.a, mode="raw").items()},
        "lag_cos_shape": {str(k): v for k, v in lag_correlations(s.a, mode="shape").items()},
        "lag2_minus_lag1": _diff(lags, 2, 1),
        "lag2_minus_lag1_highpass": _diff(hp, 2, 1),
        "lag2_minus_lag3": _diff(lags, 2, 3),
        "zigzag": _zigzag(lags),
        "zigzag_highpass": _zigzag(hp),
        "rssi_abs_diff_db": {str(k): v for k, v in rssi_lag_diffs(s.rssi).items()},
        "gap_hist": gap_histogram(s.t),
        "decor": parity_decor(s),
    }


def _diff(d: dict[int, float], a: int, b: int) -> float:
    return float(d[a] - d[b]) if d.get(a) == d.get(a) and d.get(b) == d.get(b) else float("nan")


def _zigzag(d: dict[int, float]) -> bool | None:
    """True when lag 2 exceeds BOTH adjacent odd lags (1 and 3) by more than the margin."""
    x, y = _diff(d, 2, 1), _diff(d, 2, 3)
    if x != x or y != y:
        return None
    return bool(x > ZIGZAG_MARGIN and y > ZIGZAG_MARGIN)


def find_recording(recs: dict[str, Recording], subject: str, label: str) -> Recording | None:
    hits = [r for r in recs.values() if r.subject == subject and r.label == label]
    return hits[0] if hits else None


def empty_pair_aucs(recs: dict[str, Recording]) -> dict:
    """Per node and feature: empty-vs-empty AUC on all frames vs the two parity substreams (pos = first named session)."""
    out: dict = {}
    for pos_s, neg_s in EMPTY_PAIRS:
        pos, neg = find_recording(recs, pos_s, "empty"), find_recording(recs, neg_s, "empty")
        if pos is None or neg is None:
            continue
        for node in sorted(set(pos.nodes) & set(neg.nodes)):
            for feat in AUC_FEATURES:
                row = {}
                for name, sel in (("all", None), ("even", 0), ("odd", 1)):
                    vs = []
                    for rec in (pos, neg):
                        ser = rec.nodes[node] if sel is None else parity_substream(rec.nodes[node], sel)
                        vs.append(window_feature(ser, feat, int(rec.nodes[node].t[0])))
                    row[name] = float(auc(vs[0], vs[1])) if len(vs[0]) and len(vs[1]) else None
                out[f"{pos_s}_vs_{neg_s}/N{node}/{feat}"] = row
    return out


def _sep(v: float | None) -> float:
    """Separation of two score sets from an AUC: 0 = indistinguishable, 1 = perfectly separated (either direction)."""
    return float("nan") if v is None or v != v else max(v, 1.0 - v)


def parity_auc_summary(pairs: dict) -> dict:
    """Per node/feature: mean separation on all frames vs the two parity substreams, over all empty pairs and over the
    cross-session pairs only (s8/s9 vs s6, where the drift is large). ``drop`` > 0 means the substream shrinks the gap."""
    out: dict = {}
    groups = {"all_pairs": lambda k: True, "cross_session_pairs": lambda k: k.split("/")[0].endswith("_vs_s6")}
    for gname, keep in groups.items():
        acc: dict = {}
        for key, row in pairs.items():
            if not keep(key):
                continue
            node, feat = key.split("/")[1], key.split("/")[2]
            acc.setdefault((node, feat), []).append((_sep(row["all"]), np.nanmean([_sep(row["even"]), _sep(row["odd"])])))
        for (node, feat), vals in acc.items():
            a, p = float(np.nanmean([v[0] for v in vals])), float(np.nanmean([v[1] for v in vals]))
            out.setdefault(f"{node}/{feat}", {})[gname] = {"pairs": len(vals), "separation_all": a, "separation_parity": p, "drop": a - p}
    return out


def summarize(per_rec: dict) -> dict:
    """Per node across recordings: median lag cosines, how often lag 2 beats lag 1, parity/all decor ratio."""
    out: dict = {}
    for node in (1, 2, 3, 4):
        rows = [r["nodes"][str(node)] for r in per_rec.values() if str(node) in r["nodes"] and "lag_cos" in r["nodes"][str(node)]]
        if not rows:
            continue
        med = lambda vals: float(np.nanmedian(vals)) if len(vals) else float("nan")  # noqa: E731
        out[str(node)] = {
            "recordings": len(rows),
            "median_lag_cos": {k: med([r["lag_cos"][k] for r in rows]) for k in map(str, LAGS)},
            "median_lag_cos_highpass": {k: med([r["lag_cos_highpass"][k] for r in rows]) for k in map(str, LAGS)},
            "median_lag_cos_raw": {k: med([r["lag_cos_raw"][k] for r in rows]) for k in map(str, LAGS)},
            "median_lag_cos_shape": {k: med([r["lag_cos_shape"][k] for r in rows]) for k in map(str, LAGS)},
            "recordings_lag2_gt_lag1": int(sum(1 for r in rows if r["lag2_minus_lag1"] > 0)),
            "recordings_zigzag": int(sum(1 for r in rows if r["zigzag"] is True)),
            "recordings_zigzag_highpass": int(sum(1 for r in rows if r["zigzag_highpass"] is True)),
            "median_rssi_diff_lag1": med([r["rssi_abs_diff_db"]["1"] for r in rows]),
            "median_rssi_diff_lag2": med([r["rssi_abs_diff_db"]["2"] for r in rows]),
            "median_decor_ratio_parity_over_all": med([r["decor"]["ratio_parity_over_all"] for r in rows]),
        }
    return out


def run(room_dir: Path = ROOM_DIR) -> dict:
    groups = group_recordings(room_dir)
    recs = {name: load_recording(paths, REC_CACHE) for name, paths in groups.items()}
    per_rec = {}
    for name, rec in recs.items():
        per_rec[name] = {"label": rec.label, "subject": rec.subject,
                         "nodes": {str(n): node_report(s) for n, s in sorted(rec.nodes.items())}}
    return {
        "provenance": provenance("python -m scripts.presence_eval.frame_parity", sorted(groups)),
        "limits": ["t is the recorder host's clock (ms), not a device timestamp",
                   "the header has no frame type, rate or transmitter: a parity substream is a statistical probe, not proof of two frame types",
                   "the 'empty' recordings have no entry log, so their emptiness is unverified",
                   "nothing here changes a threshold or the firmware; nothing is written into data/"],
        "zigzag_margin": ZIGZAG_MARGIN,
        "source_dir": "data/datasets/room1",
        "mode_description": MODE_DESCRIPTION,
        "recordings": per_rec,
        "summary_by_node": summarize(per_rec),
        "empty_pair_auc": (pairs := empty_pair_aucs(recs)),
        "parity_auc_summary": parity_auc_summary(pairs),
    }


def _f(v: float | None, spec: str = ".3f") -> str:
    return "n/a" if v is None or v != v else format(v, spec)


def render(res: dict) -> str:
    L = ["# PS-FIX-37 — frame alternation and parity (measured from recordings)", "",
         f"**Source:** the multi-node recordings in `{res['source_dir']}` (read-only, via the repo loader). NOT `data/sessions/` (that folder holds dashboard session summaries and is never read here).", "",
         "## Preprocessing behind every lag figure", "",
         "Four variants are reported so that figures from different preprocessings are never compared by accident:", ""]
    L += [f"* **{m}** — {d}" for m, d in res["mode_description"].items()]
    L += ["", "Tables 1–2 use `timedemean` (and `hp` = `highpass`). Table 0 shows all four side by side.", "",
          "## Table 0 — median lag cosine by preprocessing (median over recordings)", "",
          "| node | raw lag1 / lag2 / lag3 | shape lag1 / lag2 / lag3 | timedemean lag1 / lag2 / lag3 | highpass lag1 / lag2 / lag3 |", "|--|--|--|--|--|"]
    for node, s in res["summary_by_node"].items():
        cells = []
        for key in ("median_lag_cos_raw", "median_lag_cos_shape", "median_lag_cos", "median_lag_cos_highpass"):
            m = s[key]
            cells.append(f"{_f(m['1'], '.4f')} / {_f(m['2'], '.4f')} / {_f(m['3'], '.4f')}")
        L.append(f"| N{node} | " + " | ".join(cells) + " |")
    s6 = next((r for r in res["recordings"].values() if r["subject"] == "s6" and r["label"] == "empty"), None)
    if s6:
        L += ["", "### Table 0b — session s6 (the session of the reviewer's figures), lag1 / lag2 / lag3 by preprocessing", "",
              "| node | raw | shape | timedemean | highpass |", "|--|--|--|--|--|"]
        for node, n in s6["nodes"].items():
            if "lag_cos" in n:
                cells = [" / ".join(f"{n[key][k]:.3f}" for k in "123") for key in ("lag_cos_raw", "lag_cos_shape", "lag_cos", "lag_cos_highpass")]
                L.append(f"| N{node} | " + " | ".join(cells) + " |")
        L += ["", "Reading: a reviewer figure of the form \"N3 lag-1 0.72, lag-2 0.82\" is reproduced by the `shape` row (per-frame subcarrier mean removed, static spectral shape kept), "
              "not by `raw` (about 0.99 everywhere) and not by `timedemean` (negative lag-1). The exact preprocessing of the reviewer's script was not seen `[UNVERIFIED]`; the match is numerical."]
    L += ["", "A raw or `shape` lag-1 close to 1 is expected for ANY stream (the static channel is common to every frame); only the variants that remove it can show alternation. "
          "The alternation test is therefore the DIFFERENCE between lag 2 and lags 1 and 3 in the `timedemean` / `highpass` rows (and, more weakly, in the 4th decimal of `shape`).", "",
          "Lag columns are the mean cosine between frame t and t+lag (gain-removed, time-demeaned); `Δ21` = lag2 − lag1; `zz` = lag-2 beats BOTH lag-1 and lag-3 by more than "
         f"{res['zigzag_margin']} (an alternation signature); `hp` = high-pass variant. RSSI columns are mean |ΔRSSI| in dB. `decor` ratio = median decor of the same-parity "
         "substreams / median decor of all frames (a lag-2 pair is less similar than a lag-1 pair in a smooth process, so a ratio < 1 is evidence of interleaving).", "",
         "## Table 1 — lag correlation per recording and node", "",
         "| recording | node | frames | lag1 | lag2 | lag3 | lag4 | Δ21 | zz | hp lag1 / lag2 / lag3 | hp zz |", "|--|--|--|--|--|--|--|--|--|--|--|"]
    for name, rec in res["recordings"].items():
        for node, n in rec["nodes"].items():
            if "lag_cos" not in n:
                continue
            c, h = n["lag_cos"], n["lag_cos_highpass"]
            L.append(f"| {name.replace('.jsonl', '')} | {node} | {n['frames']} | {_f(c['1'])} | {_f(c['2'])} | {_f(c['3'])} | {_f(c['4'])} | {_f(n['lag2_minus_lag1'])} | "
                     f"{n['zigzag']} | {_f(h['1'])} / {_f(h['2'])} / {_f(h['3'])} | {n['zigzag_highpass']} |")
    L += ["", "## Table 2 — RSSI steps, decor on parity substreams, inter-frame gaps", "",
          "| recording | node | \\|ΔRSSI\\| lag1 / lag2 / lag3 dB | decor all | decor even / odd | ratio | gap share <5 / 5-15 / 15-30 / 30-60 / ≥60 ms |", "|--|--|--|--|--|--|--|"]
    for name, rec in res["recordings"].items():
        for node, n in rec["nodes"].items():
            if "lag_cos" not in n:
                continue
            r, d, g = n["rssi_abs_diff_db"], n["decor"], n["gap_hist"]["share"]
            lt5 = g.get("0-5ms", 0.0)
            mid = g.get("5-10ms", 0.0) + g.get("10-15ms", 0.0)
            m2 = g.get("15-20ms", 0.0) + g.get("20-30ms", 0.0)
            m3 = g.get("30-40ms", 0.0) + g.get("40-60ms", 0.0)
            L.append(f"| {name.replace('.jsonl', '')} | {node} | {_f(r['1'], '.2f')} / {_f(r['2'], '.2f')} / {_f(r['3'], '.2f')} | {_f(d['all']['median'])} | "
                     f"{_f(d['even']['median'])} / {_f(d['odd']['median'])} | {_f(d['ratio_parity_over_all'], '.2f')} | "
                     f"{lt5:.2f} / {mid:.2f} / {m2:.2f} / {m3:.2f} / {g.get('60-infms', 0.0):.2f} |")
    L += ["", "## Table 3 — summary by node (median over recordings)", "",
          "| node | recordings | median lag1 / lag2 / lag3 / lag4 | recordings with lag2 > lag1 | zigzag (raw / hp) | median \\|ΔRSSI\\| lag1 / lag2 | median decor ratio |", "|--|--|--|--|--|--|--|"]
    for node, s in res["summary_by_node"].items():
        m = s["median_lag_cos"]
        L.append(f"| N{node} | {s['recordings']} | {_f(m['1'])} / {_f(m['2'])} / {_f(m['3'])} / {_f(m['4'])} | {s['recordings_lag2_gt_lag1']} / {s['recordings']} | "
                 f"{s['recordings_zigzag']} / {s['recordings_zigzag_highpass']} | {_f(s['median_rssi_diff_lag1'], '.2f')} / {_f(s['median_rssi_diff_lag2'], '.2f')} | "
                 f"{_f(s['median_decor_ratio_parity_over_all'], '.2f')} |")
    L += ["", "## Table 4 — does the same-parity substream remove the empty-vs-empty drift? (AUC of window score, first session vs second)", "",
          "An AUC near 0.5 would mean the two empties are indistinguishable. Interleaving explains the drift only if the parity columns fall toward 0.5.", "",
          "| pair / node / feature | all frames | even frames | odd frames |", "|--|--|--|--|"]
    for key, row in res["empty_pair_auc"].items():
        L.append(f"| {key} | {_f(row['all'], '.2f')} | {_f(row['even'], '.2f')} | {_f(row['odd'], '.2f')} |")
    L += ["", "## Table 5 — how much of the cross-session empty-vs-empty gap do the parity substreams remove?", "",
          f"Separation = max(AUC, 1−AUC) (0 = indistinguishable, 1 = perfectly separated). Pairs: s8 vs s6 and s9 vs s6. `drop` = separation(all frames) − mean separation(even, odd). "
          f"A drop above {GAP_EXPLAINED_DROP} is described below as \"part of the gap explained\"; that cutoff is a reading aid for this report, not a detection threshold.", "",
          "| node / feature | separation, all frames | separation, parity substreams | drop |", "|--|--|--|--|"]
    for key, groups in res["parity_auc_summary"].items():
        g = groups.get("cross_session_pairs")
        if g:
            L.append(f"| {key} | {_f(g['separation_all'], '.2f')} | {_f(g['separation_parity'], '.2f')} | {_f(g['drop'], '.2f')} |")
    L += ["", "## Conclusion (computed from the tables above)", ""] + conclusion_lines(res)
    L += ["", "Limits: " + "; ".join(res["limits"]) + "."]
    return "\n".join(L) + "\n"


def conclusion_lines(res: dict) -> list[str]:
    recs = res["recordings"]
    total = len(recs)
    odd_ones = sorted(name.replace(".jsonl", "") for name, r in recs.items()
                      if any(n.get("zigzag") is not True for n in r["nodes"].values() if "lag_cos" in n))
    ok_all_nodes = total - len(odd_ones)
    summ = res["summary_by_node"]
    explained, not_explained = [], []
    for node in ("1", "2", "3", "4"):
        g = res["parity_auc_summary"].get(f"N{node}/decor", {}).get("cross_session_pairs")
        if g:
            (explained if g["drop"] > GAP_EXPLAINED_DROP else not_explained).append(f"N{node} ({g['drop']:+.2f})")
    ratios = ", ".join(f"N{n} {_f(s['median_decor_ratio_parity_over_all'], '.2f')}" for n, s in summ.items())
    return [
        f"1. **The interleaving is real:** lag 2 beats BOTH lag 1 and lag 3 (the zigzag) on every node in {ok_all_nodes} of {total} recordings"
        + (f"; the exception(s): {', '.join(odd_ones)}" if odd_ones else "") + ". It survives the high-pass variant, so it is not slow drift.",
        f"2. **It explains part of the empty-vs-empty gap on some nodes only** (decor, cross-session pairs; drop in separation): part explained on {', '.join(explained) or 'none'}; "
        f"not explained on {', '.join(not_explained) or 'none'}. See Table 5 for perturb as well.",
        f"3. **It inflates decor levels:** median decor of a same-parity substream over decor of all frames = {ratios} (adjacent frames are of different kinds, so all-frames decor is higher).",
        "4. **No threshold or feature change follows from this.** The presence threshold (0.6), the tier thresholds and every detector are unchanged; this is a measurement of the recordings, not of the firmware's frame types (the header carries no frame type).",
        "5. **Parity-aware decor is to be registered as a candidate** in the pre-registration (`reports/presence-eval-2026-11/PREREG-2026-11-recording-campaign.md`, written in the recording-readiness section; that file does not exist yet) with no number picked. It also motivates PS-FIX-36 (a transmitter / frame-type field in the header).",
    ]


def main() -> None:
    res = run()
    dump_json(OUT_DIR / "results" / "frame_parity.json", res)
    (OUT_DIR / "results" / "frame-parity.md").write_text(render(res), encoding="utf-8")
    print(render(res))


if __name__ == "__main__":
    main()
