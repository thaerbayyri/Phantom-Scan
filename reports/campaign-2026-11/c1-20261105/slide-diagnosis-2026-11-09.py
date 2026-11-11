"""Read-only diagnosis of shared fps slides in campaign-raw-2026-11 recordings.
Scratchpad glue, not repo code. Pure stdlib (low host memory). Prints a text report.
Usage: python -I slide_analysis.py <raw_dir> <label>=<base> [<label>=<base> ...]
"""
import datetime
import glob
import re
import sys
from array import array
from collections import Counter

FR = re.compile(rb'"t":([0-9.]+),"n":([0-9]+),"rssi":(-?[0-9]+)')
BIN_S = 10
SHARED = (1, 2, 4)          # analysed set after the 2026-11-09 amendment
SLIDE_BELOW = 0.9            # smoothed ratio below this = slide
DEEP_BELOW = 0.7
NORMAL_ABOVE = 0.97
LOCAL = datetime.timedelta(hours=3)


def load(raw, base):
    files = sorted(glob.glob(f"{raw}/{base}*.jsonl"), key=lambda p: (0 if ".part" not in p else int(p.split(".part")[1].split(".")[0])))
    t, r, ln = {}, {}, {}
    for f in files:
        with open(f, "rb") as fh:
            for line in fh:
                m = FR.search(line)
                if not m:
                    continue
                n = int(m.group(2))
                if n not in t:
                    t[n], r[n], ln[n] = array("q"), array("h"), array("H")
                t[n].append(int(float(m.group(1))))
                r[n].append(int(m.group(3)))
                ln[n].append(line.count(b",") - 3)
    return files, t, r, ln


def smooth(x, w):
    half = w // 2
    return [sum(x[max(0, i - half):i + half + 1]) / len(x[max(0, i - half):i + half + 1]) for i in range(len(x))]


def runs(flag, min_len, merge_gap):
    raw, k, n = [], 0, len(flag)
    while k < n:
        if flag[k]:
            j = k
            while j < n and flag[j]:
                j += 1
            raw.append([k, j])
            k = j
        else:
            k += 1
    merged = []
    for a, b in raw:
        if merged and a - merged[-1][1] <= merge_gap:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return [(a, b) for a, b in merged if b - a >= min_len]


def pearson(x, y):
    n = len(x)
    if n < 10:
        return float("nan")
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    return sxy / (sxx * syy) ** 0.5 if sxx > 0 and syy > 0 else float("nan")


def acf_peaks(x, minutes_per_bin):
    n = len(x)
    m = sum(x) / n
    den = sum((v - m) ** 2 for v in x) or 1.0
    a = [sum((x[i] - m) * (x[i + lag] - m) for i in range(n - lag)) / den for lag in range(0, n // 2 + 1)]
    peaks = [(a[i], i) for i in range(2, len(a) - 1) if a[i] > a[i - 1] and a[i] >= a[i + 1] and a[i] > 0.15]
    peaks.sort(reverse=True)
    return [(round(v, 2), round(i * minutes_per_bin, 1)) for v, i in peaks[:4]]


def utc(ms):
    return datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).strftime("%H:%M:%S")


def loc(ms):
    return (datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc) + LOCAL).strftime("%H:%M:%S")


def analyse(label, raw, base):
    files, T, R, L = load(raw, base)
    nodes = sorted(T)
    t0 = min(T[n][0] for n in nodes)
    t1 = max(T[n][-1] for n in nodes)
    nb = int((t1 - t0) // (BIN_S * 1000))
    print(f"\n==================== {label}  ({base})")
    print(f"files={len(files)} start={utc(t0)}Z/{loc(t0)} local, end={utc(t1)}Z/{loc(t1)} local, span={(t1 - t0) / 60000:.1f} min, 10 s bins={nb}")
    cnt = {n: [0] * nb for n in nodes}
    for n in nodes:
        for tt in T[n]:
            k = int((tt - t0) // (BIN_S * 1000))
            if k < nb:
                cnt[n][k] += 1
    fps = {n: [c / BIN_S for c in cnt[n]] for n in nodes}
    ref = {}
    for n in nodes:
        c = Counter(round(v) for v in fps[n] if v >= 50)
        ref[n] = c.most_common(1)[0][0] if c else max(fps[n])
    ratio = {n: [v / ref[n] for v in fps[n]] for n in nodes}
    print("reference fps (mode of 10 s bins):", {n: ref[n] for n in nodes})
    shared = [n for n in SHARED if n in nodes]
    rm = [sum(ratio[n][k] for n in shared) / len(shared) for k in range(nb)]
    rms = smooth(rm, 3)
    # item 1
    segs = runs([v < SLIDE_BELOW for v in rms], 6, 6)
    print(f"-- ITEM 1: shared slide segments (smoothed mean ratio of nodes {shared} < {SLIDE_BELOW}, >= 60 s): {len(segs)}")
    for a, b in segs:
        depth_roll = smooth(rm, 6)[a:b]
        dmin = min(depth_roll)
        per_node = {n: round(min(smooth(ratio[n], 6)[a:b]), 2) for n in nodes}
        onset = {}
        for n in nodes:
            sn = smooth(ratio[n], 3)
            hit = [k for k in range(max(0, a - 6), b) if sn[k] < SLIDE_BELOW]
            onset[n] = (hit[0] - a) * BIN_S if hit else None
        below_frac = {n: round(sum(1 for k in range(a, b) if smooth(ratio[n], 3)[k] < SLIDE_BELOW) / (b - a), 2) for n in nodes}
        ta, tb = t0 + a * BIN_S * 1000, t0 + b * BIN_S * 1000
        print(f"   {utc(ta)}Z -> {utc(tb)}Z  local {loc(ta)} -> {loc(tb)}  elapsed {(ta - t0) / 60000:.1f} -> {(tb - t0) / 60000:.1f} min  dur {(tb - ta) / 60000:.1f} min")
        print(f"      depth (min 60 s mean ratio, nodes {shared}): {dmin:.2f}   per-node min ratio: {per_node}")
        print(f"      onset offset vs segment start (s): {onset}   share of segment below {SLIDE_BELOW}: {below_frac}")
    for n in nodes:
        own = runs([v < SLIDE_BELOW for v in smooth(ratio[n], 3)], 6, 6)
        print(f"   node {n} own drops below {SLIDE_BELOW} (>= 60 s): {len(own)}", [(round((a * BIN_S) / 60, 1), round((b * BIN_S) / 60, 1)) for a, b in own][:8])
    pairs = [(a, b) for i, a in enumerate(nodes) for b in nodes[i + 1:]]
    print("   Pearson of 10 s fps series between nodes:", {f"{a}-{b}": round(pearson(fps[a], fps[b]), 2) for a, b in pairs})
    # item 3: period
    if nb >= 60:
        print("-- ITEM 3: autocorrelation peaks of the shared ratio (value, lag in min):", acf_peaks(rm, BIN_S / 60))
        starts = [t0 + a * BIN_S * 1000 for a, b in segs]
        ends = [t0 + b * BIN_S * 1000 for a, b in segs]
        if len(starts) > 1:
            print("   spacing of slide starts (min):", [round((starts[i + 1] - starts[i]) / 60000, 1) for i in range(len(starts) - 1)],
                  " spacing of ends (min):", [round((ends[i + 1] - ends[i]) / 60000, 1) for i in range(len(ends) - 1)])
    # item 2: structure
    cls = []
    for k in range(nb):
        cls.append("deep" if rms[k] < DEEP_BELOW else ("normal" if rms[k] >= NORMAL_ABOVE else "mid"))
    nbins = Counter(cls)
    print(f"-- ITEM 2: bins by class {dict(nbins)}")
    for n in nodes:
        d = {"normal": array("H"), "deep": array("H")}
        rs = {"normal": Counter(), "deep": Counter()}
        al = {"normal": Counter(), "deep": Counter()}
        tn, rn, lnn = T[n], R[n], L[n]
        for i in range(1, len(tn)):
            k = int((tn[i] - t0) // (BIN_S * 1000))
            if k >= nb:
                continue
            c = cls[k]
            if c == "mid":
                continue
            d[c].append(min(tn[i] - tn[i - 1], 65535))
            rs[c][rn[i]] += 1
            al[c][lnn[i]] += 1
        for c in ("normal", "deep"):
            arr = d[c]
            if len(arr) < 50:
                print(f"   node {n} {c}: too few intervals ({len(arr)})")
                continue
            tot = len(arr)
            hist = Counter(arr)
            modes = [(v, round(x / tot, 3)) for v, x in hist.most_common(6)]
            shares = {"<=20ms": round(sum(x for v, x in hist.items() if v <= 20) / tot, 3),
                      "21-40ms": round(sum(x for v, x in hist.items() if 20 < v <= 40) / tot, 3),
                      "41-100ms": round(sum(x for v, x in hist.items() if 40 < v <= 100) / tot, 3),
                      ">100ms": round(sum(x for v, x in hist.items() if v > 100) / tot, 3)}
            mean = sum(arr) / tot
            l1 = pearson(list(arr[:-1]), list(arr[1:]))
            l2 = pearson(list(arr[:-2]), list(arr[2:]))
            medr = sorted(rs[c].elements())[sum(rs[c].values()) // 2]
            print(f"   node {n} {c}: intervals={tot} mean={mean:.1f} ms  modes(ms,share)={modes}")
            print(f"       shares={shares}  lag1={l1:.2f} lag2={l2:.2f}  median RSSI={medr}  len(a) top={al[c].most_common(3)}")


if __name__ == "__main__":
    raw = sys.argv[1]
    for spec in sys.argv[2:]:
        label, base = spec.split("=", 1)
        analyse(label, raw, base)
