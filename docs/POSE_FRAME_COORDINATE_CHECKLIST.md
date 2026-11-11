# Pose Coordinate Frame — Manual Measurement Checklist

**Purpose**: Prove the coordinate frame of `poseFrame.keypoints` relative to `radialTarget` before any code is written. No files are modified during this procedure.

**Run date**: ___________________  
**Operator**: ___________________  
**Port**: 5000  
**Data source used**: [ ] demo  [ ] live ESP32  
**Node IDs connected** (live only): N___ , N___

---

## Prerequisites

1. Dashboard is running (`npm run dev`) and accessible at `http://localhost:5000`.
2. Processing is **started** (green indicator in top bar).
3. If using demo mode: switch to "Demo" in the control panel — the synthetic human target should appear automatically.
4. If using live mode: both ESP32 nodes are active, you are standing between them, and the skeleton is visible.

---

## Part 1 — Install the Console Probe (no repo changes)

Open the browser **DevTools → Console** tab (`F12`).

Paste the following snippet once. It attaches to the WebSocket message stream and prints a tab-separated log row every time both `radialTarget` and `poseFrame` arrive in the same WebSocket tick:

```javascript
(function installProbe() {
  // Intercept all WebSocket messages on the page
  const _origWS = window.WebSocket;
  let _rt = null, _pf = null;

  window.WebSocket = function(...args) {
    const ws = new _origWS(...args);
    ws.addEventListener('message', e => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'radialTarget')  _rt = msg.data;
        if (msg.type === 'poseFrame')     _pf = msg.data;

        // Print a row when both are fresh (same-ish tick)
        if (_rt && _pf && msg.type === 'poseFrame') {
          const kpMap = Object.fromEntries(_pf.keypoints.map(k => [k.name, k]));
          const lh = kpMap['left_hip'], rh = kpMap['right_hip'];
          const ls = kpMap['left_shoulder'], rs = kpMap['right_shoulder'];

          const hipX  = lh && rh ? (lh.x + rh.x) / 2 : null;
          const hipZ  = lh && rh ? (lh.z + rh.z) / 2 : null;
          const shX   = ls && rs ? (ls.x + rs.x) / 2 : null;
          const shZ   = ls && rs ? (ls.z + rs.z) / 2 : null;

          const row = {
            ts:         new Date().toISOString(),
            state:      '(see targetState)',
            rt_x:       _rt.x.toFixed(3),
            rt_z:       _rt.z.toFixed(3),
            hip_x:      hipX != null ? hipX.toFixed(3) : 'n/a',
            hip_z:      hipZ != null ? hipZ.toFixed(3) : 'n/a',
            dx_hip:     hipX != null ? (hipX - _rt.x).toFixed(3) : 'n/a',
            dz_hip:     hipZ != null ? (hipZ - _rt.z).toFixed(3) : 'n/a',
            sh_x:       shX != null ? shX.toFixed(3) : 'n/a',
            sh_z:       shZ != null ? shZ.toFixed(3) : 'n/a',
            dx_sh:      shX != null ? (shX - _rt.x).toFixed(3) : 'n/a',
            dz_sh:      shZ != null ? (shZ - _rt.z).toFixed(3) : 'n/a',
            kp_count:   _pf.keypoints.length,
          };
          console.table([row]);
        }
      } catch (_) {}
    });
    return ws;
  };
  Object.assign(window.WebSocket, _origWS);
  console.log('[probe] installed — reload the page to activate');
})();
```

> **Important**: The probe must be installed **before** the WebSocket connection opens. After pasting, **reload the page** and log in. The probe will then intercept messages from the new connection.

---

## Part 2 — Snapshot Procedure

For each test position/state below, let the system stabilise for 3–5 seconds, then copy **5 consecutive rows** from the console table into the log table at the end of this document.

### Test A — Demo Mode, Human Target Stationary

- Data source: **demo**
- Processing: started
- Expected: synthetic human target visible at a fixed position, skeleton rendering

**What to record**:
- Are `dx_hip` and `dz_hip` stable row to row? ___
- Approximate value of `dx_hip`: ___.___  `dz_hip`: ___.___
- Are `dx_sh` and `dz_sh` stable row to row? ___
- Approximate value of `dx_sh`: ___.___  `dz_sh`: ___.___

**Preliminary classification** (tick one):

| Pattern | Classification |
|---|---|
| `dx_hip` and `dz_hip` both near **zero** (< ±0.05) | `kp.x/z` are target-rooted → current code **double-offsets** by adding `target.x/z` again |
| `dx_hip` and `dz_hip` stable but **non-zero** (e.g., always +0.3, −0.1) | `kp.x/z` are in a body-local frame with consistent offset — fix needs a root subtraction |
| `dx_hip` and `dz_hip` vary by > ±0.3 frame-to-frame | Pose stream is unstable — anchoring code alone will not fix presentation |

Tick: [ ] target-rooted  [ ] body-local with offset  [ ] unstable/noisy

---

### Test B — Demo Mode, Human Target Moving

- Move the simulated target (demo mode cycles automatically).
- Observe ~10 rows while `rt_x` is changing.

**What to record**:
- Does `dx_hip` stay approximately constant as `rt_x` changes? ___
- If yes: the offset is rigid (good — a fixed root subtraction will fix it).
- If `dx_hip` grows as `rt_x` grows: the bug is multiplicative (scale mismatch in the model output).

**Observed `dx_hip` range while moving**: min ___.___  max ___.___ 

---

### Test C — Live ESP32 Mode (if hardware available)

- Switch to live mode, stand near N1 (left side).
- Record 5 rows, note position: ___________________
- Move to midpoint, record 5 rows.
- Move near N2 (right side), record 5 rows.

**Does `dx_hip` remain stable across positions?** [ ] Yes — fixed offset  [ ] No — varies with position

---

## Part 3 — Confidence Gate Validation (no console probe needed)

Verify visually. Tick each item:

### 3a — Confident human target → skeleton visible

| Check | Pass | Fail | Notes |
|---|---|---|---|
| `targetState.state` is `moving` or `idle` (not `degraded`) | [ ] | [ ] | |
| `position_confident` is `true` in targetState panel | [ ] | [ ] | |
| Full skeleton (joints + bones) is visible in scene | [ ] | [ ] | |
| Skeleton centre appears collocated with target dot | [ ] | [ ] | |

### 3b — Degraded live target → dot only, no skeleton

Trigger: use single-node live mode, or kill one node so `node_mode = single_node`.

| Check | Pass | Fail | Notes |
|---|---|---|---|
| `targetState.state` is `degraded` | [ ] | [ ] | |
| `position_confident` is `false` | [ ] | [ ] | |
| `DirectionalNode` dot is visible | [ ] | [ ] | |
| **No skeleton** is visible | [ ] | [ ] | |

### 3c — Stale target (~1.5 s after disconnect) → dot still shown, state `stale`

| Check | Pass | Fail | Notes |
|---|---|---|---|
| `targetState.stale` flips to `true` within ~1.5 s of node disconnect | [ ] | [ ] | |
| `targetState.state` = `stale` | [ ] | [ ] | |
| Target dot still visible during stale hold | [ ] | [ ] | |

### 3d — Cleared target (~5 s after disconnect) → everything removed

| Check | Pass | Fail | Notes |
|---|---|---|---|
| Target dot disappears by ~5 s | [ ] | [ ] | |
| Skeleton removed | [ ] | [ ] | |
| `targetState.state` = `none` or `stale` with `target_visible = false` | [ ] | [ ] | |

---

## Part 4 — Procedural Fallback Validation

Force the AI-pose path to be absent (either stop the AI inference process, or ensure `poseFrame` is not arriving):

| Check | Pass | Fail | Notes |
|---|---|---|---|
| `kp_count` column shows 0 or rows stop appearing in console | [ ] | [ ] | |
| Procedural body (capsule skeleton) is visible | [ ] | [ ] | |
| Procedural body centre tracks the target dot as dot moves | [ ] | [ ] | |
| No skeleton drift from the dot observed | [ ] | [ ] | |

If procedural body is correctly anchored ✓ and AI-pose body drifts ✗, the bug is **isolated** to the `jointsMap` coordinate arithmetic in `HumanMesh.tsx` and the `getAnatomicalRoot` fix is the correct remedy.

---

## Part 5 — Log Table

Copy console rows here (5 per test position). Paste as-is from the browser or reformat:

```
ts | state | rt_x | rt_z | hip_x | hip_z | dx_hip | dz_hip | sh_x | sh_z | dx_sh | dz_sh | kp_count
---|-------|------|------|-------|-------|--------|--------|------|------|-------|-------|----------
   |       |      |      |       |       |        |        |      |      |       |       |
   |       |      |      |       |       |        |        |      |      |       |       |
   |       |      |      |       |       |        |        |      |      |       |       |
   |       |      |      |       |       |        |        |      |      |       |       |
   |       |      |      |       |       |        |        |      |      |       |       |
```

---

## Part 6 — Screenshots

Attach or embed images here:

| Scenario | File / Description |
|---|---|
| Skeleton aligned with dot (demo) | |
| Skeleton drifted from dot | |
| Degraded target — dot only | |
| Stale target — dot still shown | |
| Cleared — empty scene | |

---

## Part 7 — Frame Classification Decision

Based on the above measurements, tick the conclusion that determines the code fix:

**[ ] CASE A — kp.x/z are target-rooted (deltas near zero)**  
→ Current `target.x + kp.x * 1.5` is a double-offset error.  
→ Fix: remove `target.x/z` from joint placement entirely; place joints as `[kp.x, kp.y, kp.z]` inside a `<group position={[target.x, 0, target.z]}>`.  
→ No anatomical-root subtraction needed.

**[ ] CASE B — kp.x/z are in a body-local frame (stable non-zero deltas)**  
→ Fix: subtract the anatomical root (hip/shoulder midpoint from the keypoints) to get local offsets, then add `target.x/z`.  
→ This is the `getAnatomicalRoot` approach in the revised plan.

**[ ] CASE C — kp.x/z are unstable (deltas wander > ±0.3)**  
→ The pose stream is noisy. Anchoring code alone will not fix visual stability.  
→ Action before code change: investigate AI inference pipeline stability.  
→ Consider adding a per-keypoint confidence filter (only use keypoints with `kp.confidence > 0.4`).

---

## Sign-off

| Item | Confirmed |
|---|---|
| Console probe installed and rows collected | [ ] |
| Frame classification determined (Case A / B / C) | [ ] |
| Confidence gate passes (3a–3d all green) | [ ] |
| Procedural fallback correctly anchored | [ ] |
| Implementation plan updated with observed Case | [ ] |

**Determined case**: ___  
**Recommended next step**: ___________________  
**Date completed**: ___________________
