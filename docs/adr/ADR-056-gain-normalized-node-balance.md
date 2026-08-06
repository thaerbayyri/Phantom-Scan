# ADR-056: Gain-Normalize r1/r2 Before Computing Two-Node Balance

**Status:** Accepted
**Date:** 2026-08-05
**Closes:** `PS-BEHTEST-004` (MEDIUM), `PHANTOM_SCAN_BEHAVIORAL_TEST_REPORT.md`
**Related:** ADR-054 (fusion display vs authoritative balance), ADR-055 (endpoint velocity boost, measured)
**Decision maker:** Operator (bug report: tracked target only ever displayed near N2)

## Context

The operator reported that the tracked-target dot on the two-node radar
dashboard only ever appears near node 2 (N2), never near N1 or the midpoint.
A read-only investigation ruled out every client-side rendering path —
camera, fog, grid, `NODE_ANCHORS` (N1=x-1.5, N2=x+1.5), and every render gate
in `RadialScene.tsx`/`DirectionalNode.tsx`/`HumanMesh.tsx` are geometrically
symmetric between N1 and N2.

The real cause is in `server/lib/node-fusion.ts`. `fuseTwoNodeTarget`'s
`balance = r1^p/(r1^p+r2^p)` (contrast exponent p=2.0 default) consumes
`r1`/`r2` = each node's raw, **unnormalized** `absStd` (per-subcarrier
temporal std of amplitude) from `computeNodeMotionFromMatrix()`. That
function already computes a `mean`/`base` (mean amplitude) alongside
`absStd`, but only used it to normalize the separate display `motion` field
(`motion = min(1, absStd/base * MOTION_SATURATION_SCALE)`) — never `absStd`
itself, which is what `balance`'s localization math actually consumes.

This was already a known, documented, unfixed finding: `PS-BEHTEST-004`
(severity MEDIUM), proven by a synthetic test in
`tests/behavioral/fusion-invariants.test.ts` — a uniform 2x gain difference
between the two nodes, with **identical real motion**, biases `balance` more
than 0.1 away from 0.5. `std(g·X) = g·std(X)` for a uniform gain `g` applied
to one node's raw amplitude — so any real RSSI/antenna/AGC gain mismatch
between the two physical ESP32 boards flows straight through as an
uncorrected `absStd` asymmetry, systematically pulling the displayed
position toward whichever node has higher effective gain, independent of
where the target actually is. The report's own proposed fix (never
implemented until now): normalize `r1`/`r2` by each node's own `mean` before
computing `balance`.

## Decision

Added `computeGainNormalizedPerturbation(absStd, mean)` in
`server/lib/node-fusion.ts`, alongside the existing `computeLinearBalance`:

```ts
export function computeGainNormalizedPerturbation(absStd: number, mean: number): number {
  const s = Number.isFinite(absStd) ? Math.max(0, absStd) : 0;
  const m = Number.isFinite(mean) && mean > 0 ? mean : 1.0;
  return s / m;
}
```

Wired in at the **one production call site**, `computeFusedTarget()` in
`server/lib/websocket.ts`:

```ts
r1: computeGainNormalizedPerturbation(m1.absStd, m1.mean),
r2: computeGainNormalizedPerturbation(m2.absStd, m2.mean),
```

replacing the previous `r1: m1.absStd, r2: m2.absStd`.

**Why only at the call site, not inside `fuseTwoNodeTarget`/`FuseInput`:**
this keeps `fuseTwoNodeTarget`'s contract, `EPS`, and both exponents
(`BALANCE_CONTRAST_EXPONENT`, `BALANCE_BIAS_EXPONENT`) completely untouched —
every existing direct-call test in `node-fusion.test.ts` (bare numbers like
`r1: 100, r2: 1`) keeps passing unmodified, and `motion1`/`motion2` (the
presence-gate inputs) are untouched.

**`EPS = 1e-6` remains valid for the new ratio scale.** Reasoned from
existing fixture magnitudes: the matrix-motion test's `absStd=5, mean=15`
gives a normalized ratio ≈0.33; `DEFAULT_MOTION_THRESHOLD=0.6` maps back to a
raw ratio of `0.6/MOTION_SATURATION_SCALE = 0.15`. Realistic normalized
ratios for genuine motion sit roughly in 0.01–0.3+ — five-plus orders of
magnitude above `EPS`. No change needed to `EPS`.

## Consequences

- `computeFusedTarget()` feeds the same gain-normalized `r1`/`r2` into both
  `balance` (display) and `balanceLinear` (ADR-054's authoritative,
  undecorated `r2/(r1+r2)` field) — both live-broadcast values shift in
  absolute terms on real hardware if a gain mismatch exists; their
  relationship to each other (display bias/contrast on top of the linear
  ratio) is unchanged.
- `fuseTwoNodeTarget`'s public contract and every existing direct-call unit
  test are unaffected — the fix is entirely in the caller.
- **UNVERIFIED ON REAL HARDWARE.** Proven via synthetic-matrix contract tests
  mirroring the exact scenario that proved the original finding
  (`server/lib/node-fusion.test.ts`, `tests/behavioral/fusion-invariants.test.ts`)
  — not yet validated against a real capture from the two physical boards
  with a measured gain difference. If the boards don't actually have a gain
  mismatch, this change is a no-op (ratio ≈ same on both sides regardless of
  normalization); if they do, this should measurably un-stick the displayed
  target from N2's side. Recommend the operator verify by standing at the
  true physical midpoint between the two boards and confirming `balance`
  reads close to 0.5, per ADR-055's negative-control terminology, once
  hardware is available.
- Checkpoint: `checkpoint/pre-target-presentation-fix` git tag (pushed to
  `origin`) marks the commit immediately before this change and the
  companion single-node presence-gate fix (ADR-057), for rollback if real
  hardware doesn't validate either.
