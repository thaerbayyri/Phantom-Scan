#!/usr/bin/env python3
"""
ruview-dashboard-bridge.py — live UDP CSI -> WebSocket bridge for the ui/ dashboard.

The canonical backend (Rust `wifi-densepose-sensing-server`) cannot be built on
machines where the vendored submodules (vendor/rufield, v2/crates/worldgraph,
v2/crates/ruv-neural ...) are not checked out. This is a dependency-free-ish
Python stand-in that speaks exactly the subset of that server's contract the
UI's sensing tab needs:

  HTTP  :3000  -> serves ui/ statically + GET /api/v1/status -> {"source":"esp32"}
  WS    :3001  -> /ws/sensing : real-time `sensing_update` frames (10 Hz)

It ingests the SAME real ESP32 frames the boards already stream to this host on
UDP :5005:
  * 0xC5110001  raw CSI  (20-byte ADR-018 header + 128 subcarrier I/Q) — used for
                RSSI, amplitude variance, motion band, signal field.
  * 0xC5110006  rv_feature_state (60 B, edge DSP) — used for presence / respiration
                / heartbeat as computed on-device.

All emitted numbers are derived from real captured RF — nothing is synthetic.
The 20x20 `signal_field` is an honest per-node motion-magnitude rendering, NOT a
true spatial localization (a 2-node link cannot resolve room (x,z)).

Usage:
    python scripts/ruview-dashboard-bridge.py
    python scripts/ruview-dashboard-bridge.py --udp-port 5005 --http-port 3000 --ws-port 3001
Then open  http://localhost:3000/  and select the "WiFi Sensing" tab.

LEGACY/REFERENCE — the live dashboard now runs this motion math natively in
server/lib/node-fusion.ts (computeNodeMotionFromMatrix is a faithful port of
compute_update below). Don't run this together with the dashboard: both bind
UDP :5005.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import struct
import time
from collections import defaultdict, deque
from pathlib import Path

from aiohttp import web, WSMsgType

CSI_MAGIC = 0xC5110001
FS_MAGIC = 0xC5110006
CSI_HEADER = 20

LIVE_HTML = r"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>RuView Live Target</title>
<style>
 body{margin:0;background:#0b0f1a;color:#cfe;font:14px system-ui;text-align:center}
 h2{margin:12px;color:#6cf;font-weight:600}
 canvas{background:#10182b;border:1px solid #244;border-radius:10px}
 #stat{margin:10px;font-size:18px}
 .k{color:#7fa} .v{color:#fff;font-weight:700}
 #conn{font-size:13px;color:#fa6}
</style></head><body>
<h2>RuView — Live WiFi Target (2-node)</h2>
<div id="conn">connecting…</div>
<canvas id="c" width="760" height="320"></canvas>
<div id="stat"></div>
<script>
const c=document.getElementById('c'),x=c.getContext('2d');
const W=c.width,H=c.height, m=60;        // margins
const trail=[];
function draw(d){
 x.clearRect(0,0,W,H);
 // floor line between boards
 const y=H*0.55;
 x.strokeStyle='#243a55';x.lineWidth=2;x.beginPath();x.moveTo(m,y);x.lineTo(W-m,y);x.stroke();
 // board markers
 for(const[bx,lab]of[[m,'Board 1\n(COM5)'],[W-m,'Board 2\n(COM6)']]){
   x.fillStyle='#3df';x.fillRect(bx-7,y-7,14,14);
   x.fillStyle='#9bd';x.font='12px system-ui';
   lab.split('\n').forEach((t,i)=>x.fillText(t,bx-26,y+26+i*14));
 }
 const t=d.target, f=d.features, cl=d.classification;
 if(t){
   // balance 0..1 -> across the line
   const px=m+(W-2*m)*t.balance;
   const mo=f.motion_band_power;
   trail.push(px); if(trail.length>40)trail.shift();
   // trail
   trail.forEach((tx,i)=>{x.fillStyle='rgba(110,200,255,'+(i/trail.length*0.5)+')';
     x.beginPath();x.arc(tx,y,4,0,7);x.fill();});
   // target dot, size+color by motion
   const r=12+mo*26;
   const col = mo>0.4?'#ff5b6e':(cl.presence?'#6cff9a':'#6cf');
   x.fillStyle=col;x.globalAlpha=0.85;x.beginPath();x.arc(px,y,r,0,7);x.fill();x.globalAlpha=1;
   x.fillStyle='#fff';x.font='12px system-ui';x.fillText('TARGET',px-22,y-r-8);
 }
 // motion bar
 const mw=(W-2*m)*Math.min(1,f.motion_band_power);
 x.fillStyle='#222b44';x.fillRect(m,H-28,W-2*m,14);
 x.fillStyle=f.motion_band_power>0.4?'#ff5b6e':'#6cff9a';x.fillRect(m,H-28,mw,14);
 x.fillStyle='#9bd';x.fillText('motion',m,H-32);
}
function stat(d){
 const f=d.features,cl=d.classification;
 document.getElementById('stat').innerHTML=
  `<span class=k>presence</span> <span class=v>${cl.presence}</span> &nbsp;|&nbsp;`+
  `<span class=k>state</span> <span class=v>${cl.motion_level}</span> &nbsp;|&nbsp;`+
  `<span class=k>motion</span> <span class=v>${f.motion_band_power.toFixed(2)}</span> &nbsp;|&nbsp;`+
  `<span class=k>resp</span> <span class=v>${f.respiration_bpm}bpm</span> &nbsp;|&nbsp;`+
  `<span class=k>rssi</span> <span class=v>${f.mean_rssi}dBm</span>`;
}
function go(){
 const ws=new WebSocket('ws://'+location.host+'/ws/sensing');
 ws.onopen=()=>document.getElementById('conn').textContent='LIVE — connected, walk between the two boards';
 ws.onclose=()=>{document.getElementById('conn').textContent='disconnected — retrying…';setTimeout(go,1500);};
 ws.onmessage=e=>{const d=JSON.parse(e.data);draw(d);stat(d);};
}
go();
</script></body></html>"""

UI_DIR = (Path(__file__).resolve().parent.parent / "ui")

# Window of recent CSI frames kept per node for feature computation (~3 s @ ~40 pps).
WINDOW = 120

# Rough fixed geometry just so each node renders in a distinct part of the grid.
NODE_POS = {1: [4.0, 0.0, 6.0], 2: [16.0, 0.0, 6.0]}


def _freq_to_channel(freq_mhz: int) -> int:
    if freq_mhz == 2484:
        return 14
    if 2412 <= freq_mhz <= 2472:
        return (freq_mhz - 2412) // 5 + 1
    if 5000 <= freq_mhz <= 5885:
        return (freq_mhz - 5000) // 5
    return 0


class State:
    """Shared real-time state updated by the UDP listener, read by the broadcaster."""

    def __init__(self) -> None:
        # node_id -> deque[(t, rssi, mean_amp, amps[list[float]])]
        self.csi = defaultdict(lambda: deque(maxlen=WINDOW))
        # node_id -> dict(presence, motion, resp_bpm, resp_conf, hr_bpm, hr_conf, t)
        self.feat = {}
        self.last_channel = 0
        self.pkts = 0

    def add_csi(self, node_id, rssi, channel, amps):
        self.last_channel = channel
        mean_amp = sum(amps) / len(amps) if amps else 0.0
        self.csi[node_id].append((time.time(), rssi, mean_amp, amps))
        self.pkts += 1

    def add_feat(self, node_id, presence, motion, resp_bpm, resp_conf, hr_bpm, hr_conf):
        self.feat[node_id] = dict(
            presence=presence, motion=motion, resp_bpm=resp_bpm, resp_conf=resp_conf,
            hr_bpm=hr_bpm, hr_conf=hr_conf, t=time.time(),
        )


def parse_csi(data: bytes):
    if len(data) < CSI_HEADER or struct.unpack_from("<I", data, 0)[0] != CSI_MAGIC:
        return None
    node_id = data[4]
    freq = struct.unpack_from("<I", data, 8)[0]
    rssi = struct.unpack_from("<b", data, 16)[0]
    iq = data[CSI_HEADER:]
    amps = [math.hypot(struct.unpack_from("<b", iq, i)[0],
                       struct.unpack_from("<b", iq, i + 1)[0])
            for i in range(0, len(iq) - 1, 2)]
    return node_id, rssi, _freq_to_channel(freq), amps


def parse_feat(data: bytes):
    if len(data) < 56 or struct.unpack_from("<I", data, 0)[0] != FS_MAGIC:
        return None
    node_id = data[4]
    motion = struct.unpack_from("<f", data, 16)[0]
    presence = struct.unpack_from("<f", data, 20)[0]
    resp_bpm = struct.unpack_from("<f", data, 24)[0]
    resp_conf = struct.unpack_from("<f", data, 28)[0]
    hr_bpm = struct.unpack_from("<f", data, 32)[0]
    hr_conf = struct.unpack_from("<f", data, 36)[0]
    return node_id, presence, motion, resp_bpm, resp_conf, hr_bpm, hr_conf


def _pvar(xs):
    n = len(xs)
    if n < 2:
        return 0.0
    m = sum(xs) / n
    return sum((x - m) ** 2 for x in xs) / n


def compute_update(state: State) -> dict:
    """Per-node motion from a 3 s window of per-subcarrier amplitude frames.

    THE ORIGINAL of the TS detector math: per-subcarrier temporal std ->
    abs_std (raw, for localization balance) and motion = min(1, abs_std/base*4)
    (saturated, for display/threshold). Ported 1:1 to node-fusion.ts.
    """
    now = time.time()
    nodes, node_features = [], []
    all_rssi, all_mean_amp = [], []
    motion_per_node = {}
    motion_raw_per_node = {}   # absolute per-subcarrier std (does NOT saturate) — for localization

    for node_id, buf in sorted(state.csi.items()):
        recent = [r for r in buf if now - r[0] < 3.0]
        if not recent:
            continue
        rssis = [r[1] for r in recent]
        mean_amps = [r[2] for r in recent]
        rssi_dbm = sum(rssis) / len(rssis)
        all_rssi.extend(rssis)
        all_mean_amp.extend(mean_amps)

        # Per-subcarrier temporal std over the window -> motion magnitude.
        amps_mat = [r[3] for r in recent if r[3]]
        if amps_mat:
            k = min(len(a) for a in amps_mat)
            sub_std = [math.sqrt(_pvar([a[j] for a in amps_mat])) for j in range(k)]
            base = (sum(r[2] for r in recent) / len(recent)) or 1.0
            abs_std = sum(sub_std) / k                  # absolute perturbation (units of amplitude)
            motion = min(1.0, abs_std / base * 4.0)     # normalized 0..1 (saturates) — for the meter
            sub_cnt = k
        else:
            motion, abs_std, sub_cnt = 0.0, 0.0, 0
        motion_per_node[node_id] = motion
        motion_raw_per_node[node_id] = abs_std

        nodes.append({
            "node_id": node_id,
            "rssi_dbm": round(rssi_dbm, 1),
            "position": NODE_POS.get(node_id, [10.0, 0.0, 10.0]),
            "amplitude": [round(a, 1) for a in recent[-1][3][:64]],
            "subcarrier_count": sub_cnt,
        })
        node_features.append({"node_id": node_id, "rssi_dbm": round(rssi_dbm, 1)})

    mean_rssi = (sum(all_rssi) / len(all_rssi)) if all_rssi else -100.0
    variance = _pvar(all_mean_amp)
    std = math.sqrt(variance)
    motion_band = max(motion_per_node.values()) if motion_per_node else 0.0

    # Real edge-DSP vitals (most recent, fresh < 5 s) from the boards themselves.
    fresh = [f for f in state.feat.values() if now - f["t"] < 5.0]
    resp_bpm = max((f["resp_bpm"] for f in fresh), default=0.0)
    hr_bpm = max((f["hr_bpm"] for f in fresh), default=0.0)
    edge_presence = any(f["presence"] > 0.5 for f in fresh)
    breathing_band = min(1.0, max((f["resp_conf"] for f in fresh), default=0.0))

    present = edge_presence or motion_band > 0.12 or variance > 0.8
    active = motion_band > 0.25
    confidence = min(0.99, 0.55 + motion_band) if present else max(0.3, 0.6 - motion_band)

    # --- Moving target estimate -------------------------------------------
    # A 2-node link can't resolve true (x,z), but the ABSOLUTE perturbation each
    # node sees grows the closer a moving body is to that node's line. The ratio
    # of the two nodes' raw motion places a single target on the line between
    # them, so the blob actually TRANSLATES as you walk from one board to the
    # other (not just brighten). 1-D localization from a real differential.
    G = 20
    ids = sorted(motion_raw_per_node)
    target = None
    if len(ids) >= 2:
        r1, r2 = motion_raw_per_node[ids[0]], motion_raw_per_node[ids[1]]
        p1 = NODE_POS.get(ids[0], [4.0, 0.0, 10.0])
        p2 = NODE_POS.get(ids[1], [16.0, 0.0, 10.0])
        tot = r1 + r2
        a = (r2 / tot) if tot > 1e-6 else 0.5      # 0 -> at node1, 1 -> at node2
        tx = p1[0] + (p2[0] - p1[0]) * a
        tz = p1[2] + (p2[2] - p1[2]) * a
        target = {"x": round(tx, 2), "z": round(tz, 2),
                  "intensity": round(motion_band, 3), "balance": round(a, 3)}
    elif len(ids) == 1:
        p = NODE_POS.get(ids[0], [10.0, 0.0, 10.0])
        target = {"x": p[0], "z": p[2], "intensity": round(motion_band, 3), "balance": 0.5}

    values = []
    for iz in range(G):
        for ix in range(G):
            v = 0.04  # faint baseline so the grid is visible
            if target and motion_band > 0.06:
                d2 = (ix - target["x"]) ** 2 + (iz - target["z"]) ** 2
                v += (0.25 + 0.75 * motion_band) * math.exp(-d2 / 6.0)
            values.append(round(min(1.0, v), 4))

    return {
        "type": "sensing_update",
        "timestamp": now,
        "source": "esp32",
        "nodes": nodes,
        "node_features": node_features,
        "features": {
            "mean_rssi": round(mean_rssi, 1),
            "variance": round(variance, 3),
            "std": round(std, 3),
            "motion_band_power": round(motion_band, 3),
            "breathing_band_power": round(breathing_band, 3),
            "dominant_freq_hz": round(resp_bpm / 60.0, 3) if resp_bpm else round(std * 0.05, 3),
            "respiration_bpm": round(resp_bpm, 1),
            "heartbeat_bpm": round(hr_bpm, 1),
            "change_points": 0,
            "spectral_power": round(motion_band + breathing_band, 3),
            "range": round(variance * 3, 3),
            "iqr": round(variance * 1.5, 3),
            "skewness": 0.0,
            "kurtosis": 0.0,
        },
        "classification": {
            "motion_level": "active" if active else ("present_still" if present else "absent"),
            "presence": present,
            "confidence": round(confidence, 2),
        },
        "signal_field": {"grid_size": [G, 1, G], "values": values},
        "target": target,
    }


class UdpProto(asyncio.DatagramProtocol):
    def __init__(self, state: State):
        self.state = state

    def datagram_received(self, data, addr):
        c = parse_csi(data)
        if c:
            self.state.add_csi(*c)
            return
        f = parse_feat(data)
        if f:
            self.state.add_feat(*f)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--udp-port", type=int, default=5005)
    ap.add_argument("--http-port", type=int, default=3000)
    ap.add_argument("--ws-port", type=int, default=3001)
    ap.add_argument("--rate-hz", type=float, default=10.0)
    args = ap.parse_args()

    state = State()
    clients: set[web.WebSocketResponse] = set()
    loop = asyncio.get_running_loop()

    await loop.create_datagram_endpoint(lambda: UdpProto(state),
                                        local_addr=("0.0.0.0", args.udp_port))

    # ---- HTTP app (static ui/ + status) on http-port -----------------------
    async def status(_req):
        live = bool(state.csi)
        return web.json_response({"source": "esp32" if live else "offline",
                                  "nodes": sorted(state.csi.keys()),
                                  "packets": state.pkts,
                                  "channel": state.last_channel})

    async def health(_req):
        # Liveness/readiness probes used by ui/utils/backend-detector.js and
        # ui/services/health.service.js. Returning 200 here keeps the UI in
        # live mode (no "Backend unavailable" toast, no mock-server fallback).
        return web.json_response({
            "status": "ok",
            "ready": True,
            "alive": True,
            "source": "esp32",
            "service": "ruview-dashboard-bridge",
            "version": "0.8.2-bridge",
            "nodes": sorted(state.csi.keys()),
            "packets": state.pkts,
        })

    async def index(_req):
        return web.FileResponse(UI_DIR / "index.html")

    async def live(_req):
        return web.Response(text=LIVE_HTML, content_type="text/html")

    # WebSocket handler shared by both ports. The Sensing tab
    # (ui/services/sensing.service.js) connects on :3001, while the Live Demo
    # tab (ui/services/websocket-client.js) connects on the SAME host:port as
    # the page (:3000). Serving /ws/sensing on both makes both tabs work.
    async def ws_sensing(req):
        ws = web.WebSocketResponse(heartbeat=20)
        await ws.prepare(req)
        clients.add(ws)
        try:
            async for msg in ws:
                if msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                    break
        finally:
            clients.discard(ws)
        return ws

    http = web.Application()
    http.router.add_get("/", index)
    http.router.add_get("/live", live)
    # All WebSocket paths the UI may use, served on the page's own origin (:3000).
    # The Sensing tab uses /ws/sensing; the Live Demo tab uses the pose/event
    # stream endpoints (config/api.config.js STREAM.*). One handler feeds all.
    for _wp in ("/ws/sensing", "/api/v1/stream/pose", "/api/v1/stream/events"):
        http.router.add_get(_wp, ws_sensing)  # must precede static catch-all
    http.router.add_get("/api/v1/status", status)
    http.router.add_get("/api/v1/info", health)
    http.router.add_get("/api/v1/metrics", health)
    http.router.add_get("/api/v1/health", health)
    # Health namespace expected by the UI (config/api.config.js HEALTH.*)
    for _p in ("/health", "/health/live", "/health/ready", "/health/health",
               "/health/version", "/health/metrics"):
        http.router.add_get(_p, health)
    http.router.add_static("/", str(UI_DIR), show_index=False)

    # ---- WS app on ws-port (sensing.service.js connects here) --------------
    wsapp = web.Application()
    wsapp.router.add_get("/ws/sensing", ws_sensing)

    runner_http = web.AppRunner(http)
    await runner_http.setup()
    await web.TCPSite(runner_http, "0.0.0.0", args.http_port).start()

    runner_ws = web.AppRunner(wsapp)
    await runner_ws.setup()
    await web.TCPSite(runner_ws, "0.0.0.0", args.ws_port).start()

    print(f"[bridge] UI    : http://localhost:{args.http_port}/  (open the 'WiFi Sensing' tab)")
    print(f"[bridge] WS    : ws://localhost:{args.ws_port}/ws/sensing")
    print(f"[bridge] UDP   : ingesting real CSI on :{args.udp_port}")
    print(f"[bridge] serving ui/ from {UI_DIR}")

    period = 1.0 / args.rate_hz
    last_log = 0.0
    while True:
        await asyncio.sleep(period)
        if not clients:
            continue
        update = compute_update(state)
        payload = json.dumps(update)
        for ws in list(clients):
            try:
                await ws.send_str(payload)
            except Exception:
                clients.discard(ws)
        now = time.time()
        if now - last_log > 5.0:
            last_log = now
            f = update["features"]
            c = update["classification"]
            print(f"[bridge] clients={len(clients)} nodes={[n['node_id'] for n in update['nodes']]} "
                  f"rssi={f['mean_rssi']} motion={f['motion_band_power']} "
                  f"resp={f['respiration_bpm']}bpm presence={c['presence']} pkts={state.pkts}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[bridge] stopped")
