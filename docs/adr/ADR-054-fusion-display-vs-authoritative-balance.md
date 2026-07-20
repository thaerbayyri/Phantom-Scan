# ADR-054: Fusion Balance Has Two Values — Display and Authoritative

**Status:** Accepted
**Date:** 2026-07-20
**Closes:** PS-AUDIT-003 (HIGH), PS-AUDIT-011 (DOC) from `PHANTOM_SCAN_BEHAVIOR_AUDIT_REPORT.md`
**Decision maker:** Operator (remediation WP-15 decision gate)

## Context

The audit found that the live TS fusion path (`server/lib/node-fusion.ts`) does not
implement a plain linear `balance = r2/(r1+r2)` model: it applies a contrast exponent
(`BALANCE_CONTRAST_EXPONENT`, default 2.0) before forming the ratio, then a separate
nearest-node display bias (`BALANCE_BIAS_EXPONENT`, default 0.72) when placing the
on-screen `x` position. `README.md` described a bare linear model and a 3-second window,
neither of which matched the actual 1500 ms-default, contrast+bias-shaped code. Two
options were considered: (A) remove the contrast/bias shaping and restore a literal
linear model driving the live UI, or (B) keep the tuned display behavior as intentional
and add a separate authoritative/canonical value alongside it.

Removing the display shaping (option A) is a real behavioral change to a live,
already-working detector — it would need real-hardware re-validation (empty-room and
fan/HVAC negative controls) before it could be trusted, which this remediation pass
cannot perform without physical board access. The operator confirmed the safer path:
keep today's display behavior unchanged and make the canonical value available
alongside it.

## Decision

**Option B.** Two distinct balance values now exist on `FusedTarget` /
`RadialTarget`:

- **`balance`** (existing field) — the **display value**. Contrast-shaped
  (`r1^p/(r1^p+r2^p)` form) and, for the rendered `x`/`z` position specifically, further
  passed through `biasBalanceTowardNearestNode()`. This is intentionally tuned for
  on-screen legibility and is what the live UI has always shown. **Unchanged by this ADR.**
- **`balanceLinear`** (new field, WP-15) — the **authoritative/canonical** value:
  the plain, undecorated `r2/(r1+r2)` ratio, computed by the new
  `computeLinearBalance()` helper in `server/lib/node-fusion.ts`. It is independent of
  both the contrast exponent and the display bias, and is the value any
  analytics/ground-truth/comparison consumer should read.

Neither the on-screen target position, the `trend` computation, nor
`distToNearestNodeM` changes in this ADR — `balanceLinear` is purely additive telemetry.

`README.md`'s "Two-Node Live Localization" section was also corrected in the same pass
to describe the actual 1500 ms window and the actual contrast+bias transform, since
those were factual documentation errors independent of this decision.

## Consequences

- `radialTarget.balanceLinear` is now available on every fused frame for cross-checking
  against `balance`, without any risk to the live, already-tuned display behavior.
- Any future decision to make the display track the linear model exactly (or vice
  versa) is a separate, explicit behavioral change requiring real-hardware
  re-validation — this ADR does not authorize or imply that change.
- Downstream consumers (recordings, replay tooling, future analytics) can now
  distinguish "what was shown" from "what the canonical ratio was" for the same frame.
