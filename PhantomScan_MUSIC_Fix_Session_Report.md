# Phantom Scan — PS-GAP-MUSIC-001 Fix Session Report

**Date:** 2026-08-07
**Scope:** Proper algorithmic resolution of PS-GAP-MUSIC-001 (`computeMUSICSpectrum` output mathematically independent of its input), per the investigate-first mandate.
**Baseline at session start:** 189/189 TS, 86 pass + 1 skip Python — re-verified before any change.

---

## 1. Task 0 finding (stated first, as required)

**`sampleBuffer` contains a rolling window of 16 TIME-SEQUENTIAL single-antenna CSI scalars, interleaved from two clock-unsynchronized nodes — NOT spatial antenna channels.** Confirmed via:

- `server/lib/websocket.ts:815` — `this.sampleBuffer.push(estimate.nulledSignal)`, one push per processed packet; `nulledSignal` is `h1Proc` (line 796), the clutter-removed `sample.h1`.
- `shared/schema.ts:13` — `h1` is a single complex scalar per sample. `server/lib/udp-server.ts` (verified in the original gap-analysis session) selects the max-power subcarrier's I/Q from **antenna 1** as that scalar; with one antenna present, `h2` is a crash-guard duplicate of `h1`. The firmware/ADR-018 payload carries `n_antennas=1` on this hardware.
- Buffer capacity is `config.arrayLength` (default 16, `shared/schema.ts:137`) — so the 16 "elements" are the last 16 received packets in time order.
- **Node mixing:** `dequeueHardwareSample` (`server/lib/websocket.ts:1774-1779`) deliberately alternates between node IDs when both are streaming, and `processFrame` pushes whatever sample it dequeued into the one shared `sampleBuffer` with no per-node separation. So the buffer *interleaves both nodes'* samples. Since the two ESP32 nodes share no clock or phase reference (`docs/research/csi-phase-in-wifi-sensing.md`: cross-node phase comparison is explicitly avoided for exactly this reason), even a "two-element array" reading is physically invalid.

**Consequently the Task 1B / Task 2B path applies:** no eigen-math fix can recover spatial angle-of-arrival from this input — the fix below restores genuine *input dependence* (a temporal/spectral signature), and the UI framing was changed to stop claiming a spatial angle.

## 2. The algorithmic fix (Task 1B)

**Why the old code produced input-independent output** — two compounding bugs in `server/lib/signal-processing.ts`:

1. **Rank-1 covariance:** the old code's comment claimed "averaging over sliding windows," but the implementation built `R[i][j] = samples[i]·conj(samples[j])` — a single outer product `R = x·x^H`, exactly rank 1 for *any* input.
2. **Deflation collapse:** `powerIterationEigen` extracts the one real eigenpair, deflates, and the residual matrix is then numerically ~zero. The power iteration's `norm < 1e-10` guard fired on the first multiply of every subsequent deflation step, silently leaving each "eigenvector" as its **raw deterministic seeded start vector** — fixed constants independent of the input, and not orthogonal to the extracted signal eigenvector. With `numSignals=1`, the noise subspace `En` was therefore a fixed fake basis, and the MUSIC spectrum `1/|a(θ)^H·En|²` depended only on constants — hence bit-for-bit identical output for any input.

**Fix 1 — deflation guard (`powerIterationEigen`):** after each deflation step's power iteration, the candidate eigenvector is now **Gram-Schmidt-orthogonalized against every previously extracted eigenvector** (with a deterministic canonical-basis fallback if the candidate lies entirely in their span). For a rank-deficient covariance this is the mathematically correct behavior: the remaining eigenvectors must span the orthogonal complement of the signal subspace — which *depends on the input* — rather than a fixed seed basis. Degenerate cases can no longer silently produce a fixed, input-independent spectrum.

**Fix 2 — multi-snapshot covariance (`computeMUSICSpectrum`):** the covariance is now genuinely averaged over K forward sub-window snapshots: `R = (1/K)·Σ x_k·x_k^H` with sub-window length `M = max(3, floor(N/2))` (M=8, K=9 at the production N=16), giving rank up to K for real varied signals and a genuine noise subspace. Steering vectors correspondingly use M elements. Public signature unchanged — no caller modifications needed.

**Fix 3 — degenerate input:** an all-zero/flat input now returns an **empty spectrum** instead of a plausible-looking fake curve — the client's existing honest empty state ("no live stream") renders for an empty spectrum, matching the component's own stated convention.

An honesty note was added to `computeMUSICSpectrum`'s doc comment stating the temporal (non-spatial) nature of its production input.

## 3. Before/after demonstration (real output)

**Before (from the follow-up session's investigation — the bug proof):**
```
peakA { angle: 5, power: -9.05509561470928 } peakB { angle: 5, power: -9.05509561470928 }
max |power diff| across all 121 bins: 3.552713678800501e-15
```

**After (same two unrelated random N=16 buffers, same script):**
```
DEMO1 peakA { angle: 18, power: 7.171985058731432 } peakB { angle: -16, power: -5.5957281316695395 }
DEMO1 max |power diff| across all 121 bins: 14.809506697884196
DEMO2 true angle 0 -> peak { angle: 0, power: 100 }
DEMO2 true angle 30 -> peak { angle: 30, power: 100 }
DEMO2 true angle -30 -> peak { angle: -30, power: 100 }
DEMO3 zero-input spectrum length: 0
```

Unrelated inputs now produce genuinely different spectra (14.8 dB max divergence vs. 3.6e-15); clean synthetic steering vectors resolve their exact input angle (proving the *math* is correct); degenerate input returns the honest empty spectrum. **DEMO2 validates the mathematics on synthetic vectors only — it is NOT a claim of spatial-AoA capability on the real hardware, whose input is temporal (Task 0).**

## 4. Test changes (Task 2B)

`server/lib/signal-processing.test.ts` — the pinned known-broken test ("peak is angle-independent") was **replaced** with three regression tests for the fixed behavior:
- clean steering input resolves its true synthetic angle within 3° (0/+30/-30);
- the exact input pair that proved the bug must now differ by >1 dB somewhere (fails if input-independence ever regresses);
- all-zero input returns `[]`, not a fake curve.

File count: 22 → 24 tests, all passing. The pre-existing determinism test (identical input → identical output) still passes, confirming the fix didn't introduce nondeterminism.

## 5. UI relabeling (Task 2B — applied, as it follows directly from Task 0)

`client/src/components/dashboard/aoa-spectrum.tsx` and `metrics-panel.tsx` (full diff below):
- Panel title: "AoA Spectrum (MUSIC — derived)" → **"Signal Signature (temporal MUSIC)"**, with a permanent caveat line **"TEMPORAL SIGNATURE — NOT SPATIAL ANGLE"** in the same visual convention as the existing `getLivePositionCaveat` treatment.
- X-axis: "Angle (deg)" → "Steering coordinate (not physical direction)"; hover text no longer uses the ° symbol.
- Peak marker de-emphasized (red solid diamond size 10 → muted open diamond size 6) with hover text "Signature peak (steering coord X — not a spatial angle)".
- Metrics card: "Peak AoA …°" → **"Signature Peak"** with no degree unit (testId kept stable).

This is a false-precision fix, not data-hiding: the (now genuinely input-dependent) spectrum is still fully displayed — it's just no longer labeled as something the hardware cannot measure.

<details><summary>Component diff (screenshot-equivalent)</summary>

```diff
--- a/client/src/components/dashboard/aoa-spectrum.tsx
+++ b/client/src/components/dashboard/aoa-spectrum.tsx
-        <CardHeader className="flex flex-row items-center gap-2 px-4 pb-2 pt-4">
-          <Radio className="h-4 w-4 text-chart-1" />
-          <CardTitle className="text-sm">AoA Spectrum (MUSIC — derived)</CardTitle>
+        <CardHeader className="flex flex-col gap-0.5 px-4 pb-2 pt-4">
+          <div className="flex flex-row items-center gap-2">
+            <Radio className="h-4 w-4 text-chart-1" />
+            <CardTitle className="text-sm">Signal Signature (temporal MUSIC)</CardTitle>
+          </div>
+          <span className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground/70">
+            TEMPORAL SIGNATURE — NOT SPATIAL ANGLE
+          </span>
         </CardHeader>
...
-              hovertemplate: "Angle: %{x}°<br>Power: %{y:.1f} dB<extra></extra>",
+              hovertemplate: "Steering coord: %{x}<br>Power: %{y:.1f} dB<extra></extra>",
...
-                color: "hsl(0, 84%, 60%)", size: 10, symbol: "diamond",
+                color: "hsl(217, 30%, 55%)", size: 6, symbol: "diamond-open",
...
-              hovertemplate: "Peak: %{x}°<extra></extra>",
+              hovertemplate: "Signature peak (steering coord %{x} — not a spatial angle)<extra></extra>",
...
-              title: "Angle (deg)",
+              title: "Steering coordinate (not physical direction)",

--- a/client/src/components/dashboard/metrics-panel.tsx
+++ b/client/src/components/dashboard/metrics-panel.tsx
-        label="Peak AoA"
+        label="Signature Peak"
         value={peakAngle}
-        unit="°"
+        unit=""
```
</details>

## 6. Full verification (Task 3, real output)

```
> npx tsc            (project typecheck, server + client)
exit: 0

> npx tsx --test server/**/*.test.ts
ℹ tests 191
ℹ pass 191
ℹ fail 0

> python -m pytest tests/
========== 86 passed, 1 skipped, 7551 warnings in 148.73s (0:02:28) ===========
```

TS count 189 → 191 is exactly the intentional Task 2 test-content change (−1 pinned-defect test, +3 fixed-behavior tests); Python unchanged (same 1 pre-existing hardware-conditional skip). **F1/F2 invariants explicitly re-run after all changes:**

```
> npx tsx --test server/lib/websocket.test.ts
ℹ tests 8 / pass 8 / fail 0

> python -m pytest tests/test_invariants.py -v
test_dual_node_equal_balance_midpoint PASSED
test_f1_ai_perturbations_do_not_change_deterministic_human_gate PASSED
test_f1_ai_path_does_not_emit_authoritative_identity_or_aoa PASSED
test_f2_dashboard_live_surface_has_no_upstream_hardware_controls PASSED
test_runtime_scope_guard_has_no_flight_control_imports PASSED
5 passed
```

## 7. Remaining `[UNVERIFIED]` / `[TO BE MEASURED]`

- **No spatial-AoA or positional-accuracy claim is made or implied by this fix.** Per Task 0, the production input is temporal single-antenna data; the fixed spectrum is a temporal signal signature. Real direction-finding would require multi-antenna hardware — a hardware change, not a software fix.
- **`[UNVERIFIED]` on real hardware:** how the now-input-dependent signature spectrum behaves on live CSI (e.g., whether its peak drifts usefully with target motion) has not been observed on a real rig — only synthetic validation exists. Worth a look during the next hardware session, but no operational meaning should be assigned to it until then.
- **Downstream note (pre-existing wiring, unchanged):** `peak.angle` still feeds the single-node fallback bearing (`websocket.ts` radial-target path) exactly as before this session. That path was already labeled "SINGLE-NODE BEARING — UNVALIDATED" by `getLivePositionCaveat`, is superseded by tracker/fused positions whenever they exist, and its input is now at least signal-dependent rather than frozen — but it remains as unvalidated as its existing caveat states. Not modified (out of scope; flagged for completeness).
- The prior sessions' open hardware items (negative-control run, spatial calibration, P0-S8) remain exactly as previously reported — untouched by this session.
