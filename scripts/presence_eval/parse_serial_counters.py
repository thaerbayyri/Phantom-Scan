"""PS-FIX-37: parse a PASTED serial log of one node's firmware counters. Reads a text file only: no serial port, no sockets.

    python -m scripts.presence_eval.parse_serial_counters <log.txt> [--node N] [--json out.json]

The firmware (firmware/esp32-csi-node/main/csi_collector.c, read, not run) prints two kinds of lines:

  * every ~1 s ("medium tick"):
      medium tick: yield=<n>pps csi_cb=<n> send_fail=<n> rate_skip=<n> cb_drop=<n>
    ``yield``  = frames actually sent in that tick (s_send_ok delta); ``csi_cb`` = CSI callbacks in that tick (s_cb_count delta, ALL
    transmitters); ``send_fail`` / ``rate_skip`` / ``cb_drop`` are CUMULATIVE since boot.
  * the first 3 callbacks, then every 250th:
      CSI cb #<n>: len=<n> rssi=<n> ch=<n> mac_skip=<n>
    ``#n`` and ``mac_skip`` are cumulative since boot (frames dropped by the source-MAC filter before the send gate).

What the numbers can separate (the question of PS-FIX-37: why ~2 accepted frames per 30 ms ping?):
  * MAC filter:  mac_skip delta / callback delta  = share of callbacks from OTHER transmitters (dropped before the send gate),
  * send gate:   rate_skip delta per second       = frames the 10 ms gate (CSI_MIN_SEND_INTERVAL_MS) refused,
  * accepted:    yield (pps) x 0.030 s            = frames sent per 30 ms ping interval (CSI_PING_INTERVAL_MS).
The log cannot say WHICH frame types are counted: the callback does not report a frame type.

Everything is descriptive. Nothing here changes a threshold, a setting or the firmware, and nothing is written unless ``--json`` is given.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
TS = re.compile(r"^[A-Z]\s\((\d+)\)\s")  # "I (12345) csi_collector: ..." -> uptime ms
TICK = re.compile(r"medium tick:\s*yield=(\d+)pps\s+csi_cb=(\d+)\s+send_fail=(\d+)\s+rate_skip=(\d+)\s+cb_drop=(\d+)")
CB = re.compile(r"CSI cb #(\d+):\s*len=(-?\d+)\s+rssi=(-?\d+)\s+ch=(\d+)\s+mac_skip=(\d+)")
PING_INTERVAL_S = 0.030          # CSI_PING_INTERVAL_MS (csi_ping_pure.h)
SEND_GATE_PPS_CAP = 100.0        # 1000 / CSI_MIN_SEND_INTERVAL_MS (10 ms), csi_ping_pure.h
MIN_TICKS = 10


def parse_text(text: str) -> dict:
    ticks: list[dict] = []
    cbs: list[dict] = []
    ignored = 0
    for raw in text.splitlines():
        line = ANSI.sub("", raw).strip()
        if not line:
            continue
        ts = TS.match(line)
        t_ms = int(ts.group(1)) if ts else None
        m = TICK.search(line)
        if m:
            y, cb, sf, rs, dr = (int(x) for x in m.groups())
            ticks.append({"t_ms": t_ms, "yield_pps": y, "cb_delta": cb, "send_fail": sf, "rate_skip": rs, "cb_drop": dr})
            continue
        m = CB.search(line)
        if m:
            n, ln, rssi, ch, ms = (int(x) for x in m.groups())
            cbs.append({"t_ms": t_ms, "cb_no": n, "len": ln, "rssi": rssi, "channel": ch, "mac_skip": ms})
            continue
        ignored += 1
    return {"ticks": ticks, "callbacks": cbs, "ignored_lines": ignored}


def _resets(values: list[int]) -> int:
    return sum(1 for a, b in zip(values, values[1:]) if b < a)


def _mean(xs: list[float]) -> float | None:
    return float(sum(xs) / len(xs)) if xs else None


def summarize(parsed: dict, node: int | None = None) -> dict:
    ticks, cbs = parsed["ticks"], parsed["callbacks"]
    out: dict = {"node": node, "ticks": len(ticks), "callback_lines": len(cbs), "ignored_lines": parsed["ignored_lines"], "warnings": []}
    if len(ticks) < MIN_TICKS:
        out["warnings"].append(f"only {len(ticks)} 'medium tick' lines (< {MIN_TICKS}): too short to summarise; capture at least 2 minutes")
    if ticks:
        y = [t["yield_pps"] for t in ticks]
        c = [t["cb_delta"] for t in ticks]
        rs = [t["rate_skip"] for t in ticks]
        resets = {"rate_skip": _resets(rs), "send_fail": _resets([t["send_fail"] for t in ticks]), "cb_drop": _resets([t["cb_drop"] for t in ticks])}
        if any(resets.values()):
            out["warnings"].append(f"cumulative counters went DOWN {resets}: the node rebooted during the capture (a link change); split the log at the reset")
        span_s = (ticks[-1]["t_ms"] - ticks[0]["t_ms"]) / 1000.0 if ticks[0]["t_ms"] is not None and ticks[-1]["t_ms"] is not None else None
        # rate_skip is cumulative: per-second figure = (last - first) / elapsed (ticks are ~1 s apart when no timestamps exist)
        elapsed = span_s if span_s and span_s > 0 else max(len(ticks) - 1, 1)
        out.update({
            "mean_yield_pps": _mean(y), "min_yield_pps": min(y), "max_yield_pps": max(y),
            "mean_callbacks_per_s": _mean(c),
            "yield_over_callbacks": (sum(y) / sum(c)) if sum(c) else None,
            "frames_per_ping_interval": (_mean(y) or 0.0) * PING_INTERVAL_S,
            "rate_skip_per_s": (rs[-1] - rs[0]) / elapsed if not resets["rate_skip"] else None,
            "send_fail_total_delta": ticks[-1]["send_fail"] - ticks[0]["send_fail"] if not resets["send_fail"] else None,
            "cb_drop_total_delta": ticks[-1]["cb_drop"] - ticks[0]["cb_drop"] if not resets["cb_drop"] else None,
            "send_gate_cap_pps": SEND_GATE_PPS_CAP,
            "share_ticks_at_gate_cap": sum(1 for v in y if v >= SEND_GATE_PPS_CAP) / len(y),
            "span_s": span_s,
        })
    if len(cbs) >= 2:
        d_cb = cbs[-1]["cb_no"] - cbs[0]["cb_no"]
        d_mac = cbs[-1]["mac_skip"] - cbs[0]["mac_skip"]
        if d_cb < 0 or d_mac < 0:
            out["warnings"].append("callback counters went down between the first and last 'CSI cb' line: reboot during capture; mac_skip share not computed")
        elif d_cb > 0:
            out["mac_skip_share_of_callbacks"] = d_mac / d_cb
            out["callbacks_spanned"] = d_cb
        out["channels_seen"] = sorted({c["channel"] for c in cbs})
        out["rssi_min_max"] = [min(c["rssi"] for c in cbs), max(c["rssi"] for c in cbs)]
    elif cbs:
        out["warnings"].append("a single 'CSI cb' line: mac_skip share needs at least two (they print every 250th callback)")
    return out


def render(s: dict) -> str:
    f = lambda v, spec=".2f": "n/a" if v is None else format(v, spec)  # noqa: E731
    L = [f"serial counters, node {s['node'] if s['node'] is not None else '?'}: {s['ticks']} ticks, {s['callback_lines']} callback lines, {s['ignored_lines']} other lines ignored"]
    if s["ticks"]:
        L += [f"  yield (frames sent/s): mean {f(s.get('mean_yield_pps'), '.1f')}, min {s.get('min_yield_pps')}, max {s.get('max_yield_pps')}  (send-gate cap {s.get('send_gate_cap_pps'):.0f}; share of ticks at the cap {f(s.get('share_ticks_at_gate_cap'))})",
              f"  frames per 30 ms ping interval: {f(s.get('frames_per_ping_interval'))}",
              f"  CSI callbacks/s (all transmitters): mean {f(s.get('mean_callbacks_per_s'), '.1f')}; sent/callbacks = {f(s.get('yield_over_callbacks'))}",
              f"  rate_skip per second (refused by the 10 ms gate): {f(s.get('rate_skip_per_s'), '.1f')}; send_fail delta {s.get('send_fail_total_delta')}; cb_drop delta {s.get('cb_drop_total_delta')}"]
    if "mac_skip_share_of_callbacks" in s:
        L.append(f"  share of callbacks dropped by the MAC filter (other transmitters): {f(s['mac_skip_share_of_callbacks'])} over {s['callbacks_spanned']} callbacks; channels {s['channels_seen']}; RSSI {s['rssi_min_max']}")
    L += [f"  WARNING: {w}" for w in s["warnings"]]
    L.append("  The log cannot say which frame TYPES are counted (the callback reports none).")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("log", type=Path, help="text file with the pasted serial output of ONE node")
    ap.add_argument("--node", type=int, default=None, help="node id, for the report only")
    ap.add_argument("--json", type=Path, default=None, help="also write the summary as JSON here")
    args = ap.parse_args(argv)
    if not args.log.is_file():
        print(f"error: {args.log} is not a file", file=sys.stderr)
        return 2
    summary = summarize(parse_text(args.log.read_text(encoding="utf-8", errors="replace")), args.node)
    print(render(summary))
    if args.json:
        args.json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0 if summary["ticks"] or summary["callback_lines"] else 1


if __name__ == "__main__":
    sys.exit(main())
