"""PS-FIX-40: does the 33.3 Hz ping cadence alias into the bands the project analyses, and does it matter in production?

    PRESENCE_EVAL_OUT=reports/fix-2026-11 python -m scripts.presence_eval.alias_check

Facts (read from source, not assumed):
  * Nodes ping every 30 ms (csi_ping_pure.h CSI_PING_INTERVAL_MS) and the recordings show ~2 frames per ping with an alternation
    between the two (PS-FIX-37), so the amplitude stream carries a real 33.3 Hz component and its harmonics.
  * The ONLY uniform resampler in the repo is this evaluation tool's (periodicity.py, linear interpolation onto GRID_HZ, 50 Hz before
    PS-FIX-40). Production code does not resample; it (a) measures fs from timestamps in the AI sidecar (ai_inference.py _estimate_fs) and
    (b) in the legacy per-tick path (websocket.ts processFrame, setInterval 50 ms) takes ONE queued sample per tick, i.e. a 20 Hz
    decimation with no anti-alias filter, which feeds MotionGate, MicroDopplerClassifier and VitalsComputer (all assume sampleRate 20).
  * MicroDopplerClassifier (signal-processing.ts) scores "mechanical" from highFreqRatio = power above 5 Hz / total of a 40-sample
    (2 s) window at 20 Hz, plus an autocorrelation peak; it can SUPPRESS a presence claim. A 33.3 Hz line folded to 20 Hz lands at
    6.67 Hz, inside its high-frequency band.

This module: alias arithmetic, a synthetic demonstration, and a replay of the real recordings through a REPLICA of the classifier's
scoring with the decimation done two ways (production-like nearest-sample, and anti-aliased). LIMITS (also in the output): the scalar
fed to the replica is the per-frame mean amplitude of ONE node, a proxy for the production ``dynamicAmplitude`` (clutter-removed complex
channel, nodes interleaved by a round-robin queue); the decimation emulation picks the first frame at or after each 50 ms tick. The
replay measures the MECHANISM, not the live label rates. Nothing here changes a threshold, a setting or the firmware.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from .jsonutil import dump_json
from .provenance import default_out_dir, provenance
from .recordings import NodeSeries, group_recordings, load_recording
from .tables import REC_CACHE, ROOM_DIR

OUT_DIR = default_out_dir()
PING_HZ = 1000.0 / 30.0                       # csi_ping_pure.h CSI_PING_INTERVAL_MS = 30
BANDS_HZ = {"respiration": (0.1, 0.5), "cardiac": (0.8, 2.0), "periodicity_1_20": (1.0, 20.0)}
DC_HZ = 0.05                                  # an alias this close to 0 Hz is removed by detrending
BAND_MARGIN_HZ = 0.05
K_MAX = 6                                     # ping harmonics considered (k * 33.33 Hz)
TICK_MS = 50.0                                # websocket.ts: setInterval(processFrame, 50)
CLASSIFIER_FS_HZ = 20.0                       # signal-processing.ts MicroDopplerClassifier sampleRate
CLASSIFIER_N = 40                             # ... bufferSize
CLASSIFIER_HIGH_HZ = 5.0                      # ... highFreqRatio band start
FINE_HZ = 200.0                               # intermediate grid for the anti-aliased path (Nyquist 100 Hz > 33.3 Hz)
FIR_TAPS = 255
MAX_GAP_MS = 500.0
MIN_SEGMENT_S = 4.0
WINDOW_STRIDE = 10                            # classifier windows advance by 10 samples (0.5 s) in the replay
MECHANICAL_REJECT_HUMAN_PROB_MAX = 0.2        # node-fusion.ts DEFAULT_MECHANICAL_REJECT_HUMAN_PROB_MAX (placeholder): label "mechanical" AND humanProb <= this suppresses a presence claim


# ---- alias arithmetic ------------------------------------------------------------------------


def alias_frequency(f_hz: float, fs_hz: float) -> float:
    """Frequency (Hz, in [0, fs/2]) at which a tone of f_hz appears after sampling at fs_hz."""
    r = f_hz % fs_hz
    return float(min(r, fs_hz - r))


def ping_alias_table(fs_hz: float, k_max: int = K_MAX) -> list[dict]:
    return [{"k": k, "tone_hz": k * PING_HZ, "alias_hz": alias_frequency(k * PING_HZ, fs_hz)} for k in range(1, k_max + 1)]


def bands_hit(fs_hz: float, k_max: int = K_MAX) -> dict[str, list[dict]]:
    """For each analysed band, the ping harmonics whose alias lands inside it (a DC alias is ignored: detrending removes it)."""
    out: dict[str, list[dict]] = {}
    for name, (lo, hi) in BANDS_HZ.items():
        out[name] = [r for r in ping_alias_table(fs_hz, k_max)
                     if r["alias_hz"] > DC_HZ and lo - BAND_MARGIN_HZ <= r["alias_hz"] <= hi + BAND_MARGIN_HZ]
    return out


# ---- resampling paths ------------------------------------------------------------------------


def uniform_linear(t_ms: np.ndarray, x: np.ndarray, fs_hz: float) -> np.ndarray:
    """Point-wise linear interpolation onto a uniform grid (what periodicity.py does): NO anti-alias filter."""
    t = np.asarray(t_ms, dtype=np.float64)
    grid = np.arange(t[0], t[-1], 1000.0 / fs_hz)
    return np.interp(grid, t, np.asarray(x, dtype=np.float64))


def decimate_nearest(t_ms: np.ndarray, x: np.ndarray, tick_ms: float = TICK_MS) -> np.ndarray:
    """Production-like: one sample per tick, the first frame at or after the tick. NO anti-alias filter."""
    t = np.asarray(t_ms, dtype=np.float64)
    ticks = np.arange(t[0], t[-1], tick_ms)
    idx = np.clip(np.searchsorted(t, ticks, side="left"), 0, len(t) - 1)
    return np.asarray(x, dtype=np.float64)[idx]


def fir_lowpass(cutoff_hz: float, fs_hz: float, taps: int = FIR_TAPS) -> np.ndarray:
    n = np.arange(taps) - (taps - 1) / 2.0
    h = 2.0 * cutoff_hz / fs_hz * np.sinc(2.0 * cutoff_hz / fs_hz * n) * np.hamming(taps)
    return h / h.sum()


def decimate_antialiased(t_ms: np.ndarray, x: np.ndarray, fs_out_hz: float) -> np.ndarray:
    """Linear interpolation to FINE_HZ (content up to 33 Hz is represented without folding), a windowed-sinc low-pass at 0.4 * fs_out,
    then every (FINE_HZ / fs_out)-th sample. FINE_HZ / fs_out must be an integer."""
    step = FINE_HZ / fs_out_hz
    if abs(step - round(step)) > 1e-9:
        raise ValueError(f"FINE_HZ={FINE_HZ} is not an integer multiple of fs_out={fs_out_hz}")
    fine = uniform_linear(t_ms, x, FINE_HZ)
    lp = np.convolve(fine, fir_lowpass(0.4 * fs_out_hz, FINE_HZ), mode="same")
    half = FIR_TAPS // 2
    trimmed = lp[half:len(lp) - half] if len(lp) > 2 * half else lp   # drop the filter's edge transient
    return trimmed[:: int(round(step))]


# ---- spectra ---------------------------------------------------------------------------------


def _spectrum(x: np.ndarray, fs_hz: float) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(x, dtype=np.float64)
    x = (x - x.mean()) * np.hanning(len(x))
    return np.fft.rfftfreq(len(x), d=1.0 / fs_hz), np.abs(np.fft.rfft(x)) ** 2


def power_share(x: np.ndarray, fs_hz: float, lo_hz: float, hi_hz: float) -> float:
    f, p = _spectrum(x, fs_hz)
    tot = p[1:].sum()
    sel = (f >= lo_hz) & (f <= hi_hz) & (f > 0)
    return float(p[sel].sum() / tot) if tot > 0 else float("nan")


def peak_hz(x: np.ndarray, fs_hz: float, lo_hz: float, hi_hz: float) -> float:
    f, p = _spectrum(x, fs_hz)
    sel = (f >= lo_hz) & (f <= hi_hz)
    return float(f[sel][np.argmax(p[sel])]) if sel.any() else float("nan")


# ---- replica of MicroDopplerClassifier.push (server/lib/signal-processing.ts) -------------------


def classifier_features(window: np.ndarray, fs_hz: float = CLASSIFIER_FS_HZ) -> dict:
    """highFreqRatio, autocorr peak, humanProb and label exactly as the TS code computes them for a full buffer."""
    w = np.asarray(window, dtype=np.float64)
    n = len(w)
    c = w - w.mean()
    power = np.abs(np.fft.rfft(c)) ** 2                    # bins 0 .. floor(n/2), as the O(N^2) DFT loop
    total = power[1:].sum() + 1e-10
    start = math.ceil(CLASSIFIER_HIGH_HZ / (fs_hz / n))
    hf = float(power[start:].sum() / total)
    ac0 = float(np.dot(c, c))
    acmax = 0.0
    if ac0 > 1e-10:
        for lag in range(3, n // 2):
            acmax = max(acmax, float(np.dot(c[: n - lag], c[lag:])) / ac0)
    mech = min(1.0, hf * 3) * 0.5 + min(1.0, acmax * 1.5) * 0.5
    human = max(0.0, min(1.0, 1.0 - mech))
    label = "human" if human > 0.65 else "mechanical" if human < 0.35 else "unknown"
    return {"high_freq_ratio": hf, "autocorr_max": acmax, "human_prob": human, "label": label}


def classifier_windows(x20: np.ndarray, stride: int = WINDOW_STRIDE) -> list[dict]:
    return [classifier_features(x20[i:i + CLASSIFIER_N]) for i in range(0, len(x20) - CLASSIFIER_N + 1, stride)]


# ---- synthetic demonstration -------------------------------------------------------------------


def synthetic_stream(seconds: float = 120.0, depth: float = 0.3, resp_hz: float = 0.3, card_hz: float = 1.2, seed: int = 20261104) -> tuple[np.ndarray, np.ndarray]:
    """Two frames per 30 ms ping that alternate in kind (a real 33.3 Hz component), plus a respiration and a cardiac tone."""
    rng = np.random.default_rng(seed)
    pings = np.arange(0.0, seconds * 1000.0, 30.0)
    t = np.sort(np.concatenate([pings, pings + 13.0]) + rng.normal(0, 1.5, 2 * len(pings)))
    kind = np.where(np.arange(len(t)) % 2 == 0, 1.0, -1.0)
    ts = t / 1000.0
    x = 10.0 + 0.05 * np.sin(2 * np.pi * resp_hz * ts) + 0.02 * np.sin(2 * np.pi * card_hz * ts) + depth * kind + rng.normal(0, 0.02, len(t))
    return t, x


def synthetic_demo(grids_hz: tuple[float, ...] = (50.0, 64.0, 100.0)) -> dict:
    t, x = synthetic_stream()
    rows = []
    for fs in grids_hz:
        y = uniform_linear(t, x, fs)
        rows.append({"path": f"linear interpolation to {fs:g} Hz", "fs_hz": fs, "predicted_alias_hz": alias_frequency(PING_HZ, fs),
                     "peak_above_2p5hz": peak_hz(y, fs, 2.5, fs / 2), "resp_peak": peak_hz(y, fs, 0.1, 0.5), "cardiac_peak": peak_hz(y, fs, 0.8, 2.0),
                     "share_in_resp_band": power_share(y, fs, *BANDS_HZ["respiration"]), "share_in_cardiac_band": power_share(y, fs, *BANDS_HZ["cardiac"])})
    for name, y in (("20 Hz nearest-sample decimation (production-like)", decimate_nearest(t, x)), ("20 Hz anti-aliased decimation", decimate_antialiased(t, x, 20.0))):
        rows.append({"path": name, "fs_hz": 20.0, "predicted_alias_hz": alias_frequency(PING_HZ, 20.0), "peak_above_2p5hz": peak_hz(y, 20.0, 2.5, 10.0),
                     "resp_peak": peak_hz(y, 20.0, 0.1, 0.5), "cardiac_peak": peak_hz(y, 20.0, 0.8, 2.0),
                     "share_in_resp_band": power_share(y, 20.0, *BANDS_HZ["respiration"]), "share_in_cardiac_band": power_share(y, 20.0, *BANDS_HZ["cardiac"]),
                     "classifier_high_freq_ratio_median": float(np.median([w["high_freq_ratio"] for w in classifier_windows(y)]))})
    return {"ping_hz": PING_HZ, "rows": rows}


# ---- replay of the real recordings --------------------------------------------------------------


def segments(t_ms: np.ndarray) -> list[tuple[int, int]]:
    """Index ranges without a gap > MAX_GAP_MS and at least MIN_SEGMENT_S long."""
    cuts = np.flatnonzero(np.diff(t_ms.astype(np.float64)) > MAX_GAP_MS) + 1
    bounds = np.concatenate([[0], cuts, [len(t_ms)]])
    return [(int(a), int(b)) for a, b in zip(bounds[:-1], bounds[1:]) if b - a > 2 and (t_ms[b - 1] - t_ms[a]) / 1000.0 >= MIN_SEGMENT_S]


def replay_node(s: NodeSeries) -> dict:
    """Classifier replica on the node's mean-amplitude scalar: nearest-sample versus anti-aliased 20 Hz decimation."""
    raw_w, aa_w = [], []
    x_all = s.a.astype(np.float64).mean(axis=1)
    for a, b in segments(s.t):
        raw_w += classifier_windows(decimate_nearest(s.t[a:b], x_all[a:b]))
        aa_w += classifier_windows(decimate_antialiased(s.t[a:b], x_all[a:b], 20.0))
    return {"raw": raw_w, "aa": aa_w}


def summarize_windows(ws: list[dict]) -> dict:
    n = len(ws)
    if not n:
        return {"windows": 0}
    lab = [w["label"] for w in ws]
    return {"windows": n, "median_high_freq_ratio": float(np.median([w["high_freq_ratio"] for w in ws])),
            "median_human_prob": float(np.median([w["human_prob"] for w in ws])),
            "share_mechanical": lab.count("mechanical") / n, "share_unknown": lab.count("unknown") / n, "share_human": lab.count("human") / n,
            "share_would_suppress": sum(1 for w in ws if w["label"] == "mechanical" and w["human_prob"] <= MECHANICAL_REJECT_HUMAN_PROB_MAX) / n}


def replay_by_class(room_dir: Path = ROOM_DIR) -> dict:
    groups = group_recordings(room_dir)
    pooled: dict[str, dict[str, list]] = {}
    per_rec = {}
    for name, paths in groups.items():
        rec = load_recording(paths, REC_CACHE)
        cls = rec.label
        for node, s in sorted(rec.nodes.items()):
            if len(s.t) < 200:
                continue
            r = replay_node(s)
            p = pooled.setdefault(cls, {"raw": [], "aa": []})
            p["raw"] += r["raw"]
            p["aa"] += r["aa"]
            per_rec.setdefault(name, {})[str(node)] = {"raw": summarize_windows(r["raw"]), "aa": summarize_windows(r["aa"])}
    by_class = {}
    for cls, p in pooled.items():
        n = min(len(p["raw"]), len(p["aa"]))
        changed = sum(1 for a, b in zip(p["raw"][:n], p["aa"][:n]) if a["label"] != b["label"]) / n if n else float("nan")
        by_class[cls] = {"raw": summarize_windows(p["raw"]), "aa": summarize_windows(p["aa"]), "share_windows_label_changes_if_antialiased": changed}
    return {"by_class": by_class, "per_recording": per_rec}


def run(room_dir: Path = ROOM_DIR) -> dict:
    grids = (20.0, 50.0, 64.0, 100.0)
    return {
        "provenance": provenance("python -m scripts.presence_eval.alias_check", sorted(group_recordings(room_dir))),
        "ping_hz": PING_HZ,
        "alias_tables": {f"{g:g}": ping_alias_table(g) for g in grids},
        "bands_hit": {f"{g:g}": bands_hit(g) for g in grids},
        "synthetic": synthetic_demo(),
        "replay": replay_by_class(room_dir),
        "limits": ["the replica's input is the per-frame mean amplitude of ONE node, a proxy for the production dynamicAmplitude (clutter-removed complex "
                   "channel; nodes are interleaved by a round-robin queue in the live path)",
                   "decimation is emulated as the first frame at or after each 50 ms tick; the live queue/round-robin dynamics are not reproduced",
                   "the replay measures the mechanism (does anti-aliasing change the classifier's inputs and labels), not live label rates",
                   "recorder timestamps are host clock (ms); nothing here changes a threshold, a setting or the firmware; nothing is written into data/"],
    }


def _f(v: float | None, spec: str = ".3f") -> str:
    return "n/a" if v is None or v != v else format(v, spec)


def render(res: dict) -> str:
    L = ["# PS-FIX-40 — does the 33.3 Hz ping cadence alias, and where does it land?", "",
         f"Ping cadence {res['ping_hz']:.2f} Hz (30 ms). Bands analysed: respiration 0.1–0.5 Hz, cardiac 0.8–2.0 Hz, the periodicity tool's 1–20 Hz.", "",
         "## 1. Where the ping harmonics land, by sampling rate (alias = |k·33.33 − n·fs|)", "",
         "| fs (Hz) | k=1 | k=2 | k=3 | k=4 | k=5 | k=6 | harmonics inside respiration / cardiac / 1–20 Hz |", "|--|--|--|--|--|--|--|--|"]
    for fs, rows in res["alias_tables"].items():
        hits = res["bands_hit"][fs]
        L.append(f"| {fs} | " + " | ".join(f"{r['alias_hz']:.2f}" for r in rows) + f" | {len(hits['respiration'])} / {len(hits['cardiac'])} / {len(hits['periodicity_1_20'])} |")
    L += ["", "100 Hz = 3 × 33.33 Hz is the only grid here where every harmonic folds to 0 Hz (removed by detrending) or to 33.33 Hz (above 20 Hz); 64 Hz moves the fundamental out of 1–20 Hz but its 2nd, 4th and 6th harmonics (2.67, 5.33, 8.00 Hz) land inside it.", "",
          "## 2. Synthetic stream (two frames per ping, alternating kind; 0.3 Hz respiration and 1.2 Hz cardiac tones added)", "",
          "| path | predicted alias (Hz) | strongest line above 2.5 Hz (Hz) | respiration peak | cardiac peak | power share resp / cardiac | classifier high-freq ratio (median) |", "|--|--|--|--|--|--|--|"]
    for r in res["synthetic"]["rows"]:
        L.append(f"| {r['path']} | {r['predicted_alias_hz']:.2f} | {_f(r['peak_above_2p5hz'], '.2f')} | {_f(r['resp_peak'], '.2f')} | {_f(r['cardiac_peak'], '.2f')} | "
                 f"{_f(r['share_in_resp_band'], '.4f')} / {_f(r['share_in_cardiac_band'], '.4f')} | {_f(r.get('classifier_high_freq_ratio_median'), '.3f')} |")
    L += ["", "The alias lands outside BOTH vital bands on every path; the respiration and cardiac tones are recovered at their true frequencies. The damage is to the 1–20 Hz periodicity feature (50 Hz grid: 16.67 Hz) and to the classifier's >5 Hz band (20 Hz decimation: 6.67 Hz).", "",
          "## 3. Real recordings: classifier replica with production-like decimation vs anti-aliased decimation (all nodes pooled by class)", "",
          "A window would SUPPRESS a presence claim only if its label is `mechanical` AND humanProb <= 0.2 (node-fusion.ts, a placeholder constant); that is the column that matters for the two failure directions.", "",
          "| class | windows | median high-freq ratio raw → AA | median humanProb raw → AA | share labelled mechanical raw → AA | **share that would suppress, raw → AA** | windows whose label changes |", "|--|--|--|--|--|--|--|"]
    for cls, c in res["replay"]["by_class"].items():
        r, a = c["raw"], c["aa"]
        L.append(f"| {cls} | {r.get('windows')} | {_f(r.get('median_high_freq_ratio'))} → {_f(a.get('median_high_freq_ratio'))} | {_f(r.get('median_human_prob'))} → {_f(a.get('median_human_prob'))} | "
                 f"{_f(r.get('share_mechanical'), '.3f')} → {_f(a.get('share_mechanical'), '.3f')} | **{_f(r.get('share_would_suppress'), '.4f')} → {_f(a.get('share_would_suppress'), '.4f')}** | {_f(c['share_windows_label_changes_if_antialiased'], '.3f')} |")
    L += ["", "Limits: " + "; ".join(res["limits"]) + "."]
    return "\n".join(L) + "\n"


def main() -> None:
    res = run()
    dump_json(OUT_DIR / "results" / "alias_check.json", res)
    (OUT_DIR / "results" / "alias-check.md").write_text(render(res), encoding="utf-8")
    print(render(res))


if __name__ == "__main__":
    main()
