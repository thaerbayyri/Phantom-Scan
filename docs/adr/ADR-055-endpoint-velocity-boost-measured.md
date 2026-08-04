# ADR-055: Endpoint Velocity Boost — Measured, Confirmed Intentional (No Change)

**Status:** Accepted
**Date:** 2026-08-02
**Closes:** PR-2 Area 4 gate (radar-target-velocity remediation plan, B1)
**Related:** ADR-054 (fusion display vs authoritative balance)
**Decision maker:** measurement-gated per the approved remediation plan

## Context

The radar-target-velocity remediation plan flagged `server/lib/websocket.ts`'s
`updateFusedSnapshot` endpoint boost (up to +35% velocity near a node,
`endpointBoost = 1 + Math.pow(endpointStrength, 0.8) * 0.35`) as suspect: a
prior review round claimed the boost "under-compensates near the endpoints,"
implying removing it would produce a *smaller* velocity there. That claim was
flagged as internally contradictory unless the bias transfer function
`s(b) = d(biased)/d(balance)` (where `biased = biasBalanceTowardNearestNode(balance)`,
exponent 0.72) actually goes to zero at the endpoints — which would make the
*unboosted* velocity larger there, not smaller. The plan gated any change to
this boost behind measuring `s(b)` first (B1). No code changed as part of this
ADR; this documents the measurement and its conclusion.

## Measurement (B1)

`biasBalanceTowardNearestNode` was numerically differentiated (central
difference, h=1e-5) against the actual production function in
`server/lib/node-fusion.ts`, at `balance ∈ [0, 1]` in 0.02 steps:

| balance | biased | s(b) | balance | biased | s(b) |
|---|---|---|---|---|---|
| 0.00 | 0.0000 | 0.7200 | 0.52 | 0.5493 | 1.7732 |
| 0.02 | 0.0145 | 0.7283 | 0.54 | 0.5811 | 1.4604 |
| 0.04 | 0.0291 | 0.7370 | 0.56 | 0.6086 | 1.3037 |
| 0.06 | 0.0440 | 0.7462 | 0.58 | 0.6336 | 1.2028 |
| 0.08 | 0.0590 | 0.7560 | 0.60 | 0.6569 | 1.1299 |
| 0.10 | 0.0742 | 0.7664 | 0.62 | 0.6789 | 1.0737 |
| 0.12 | 0.0896 | 0.7775 | 0.64 | 0.7000 | 1.0283 |
| 0.14 | 0.1053 | 0.7894 | 0.66 | 0.7201 | 0.9906 |
| 0.16 | 0.1212 | 0.8021 | 0.68 | 0.7396 | 0.9584 |
| 0.18 | 0.1374 | 0.8158 | 0.70 | 0.7585 | 0.9306 |
| 0.20 | 0.1539 | 0.8307 | 0.72 | 0.7769 | 0.9061 |
| 0.22 | 0.1706 | 0.8469 | 0.74 | 0.7948 | 0.8843 |
| 0.24 | 0.1878 | 0.8647 | 0.76 | 0.8122 | 0.8647 |
| 0.26 | 0.2052 | 0.8843 | 0.78 | 0.8294 | 0.8469 |
| 0.28 | 0.2231 | 0.9061 | 0.80 | 0.8461 | 0.8307 |
| 0.30 | 0.2415 | 0.9306 | 0.82 | 0.8626 | 0.8158 |
| 0.32 | 0.2604 | 0.9584 | 0.84 | 0.8788 | 0.8021 |
| 0.34 | 0.2799 | 0.9906 | 0.86 | 0.8947 | 0.7894 |
| 0.36 | 0.3000 | 1.0283 | 0.88 | 0.9104 | 0.7775 |
| 0.38 | 0.3211 | 1.0737 | 0.90 | 0.9258 | 0.7664 |
| 0.40 | 0.3431 | 1.1299 | 0.92 | 0.9410 | 0.7560 |
| 0.42 | 0.3664 | 1.2028 | 0.94 | 0.9560 | 0.7462 |
| 0.44 | 0.3914 | 1.3037 | 0.96 | 0.9709 | 0.7370 |
| 0.46 | 0.4189 | 1.4604 | 0.98 | 0.9855 | 0.7283 |
| 0.48 | 0.4507 | 1.7732 | 1.00 | 1.0000 | 0.7200 |
| 0.50 | 0.5000 | →∞ (cusp) | | | |

Script run directly against the production `biasBalanceTowardNearestNode` (not a
re-derivation) and discarded after capture; the table above is reproducible from
the function as committed.

**Key finding:** `s(b)` is symmetric, **minimized at the endpoints** (`s(0) = s(1) =
0.72`, exactly `BALANCE_BIAS_EXPONENT`) and **diverges toward the midpoint**
(`b → 0.5`, a cusp from the fractional power `magnitude^0.72` at `magnitude → 0`).
This is the mirror image of the claim that motivated Area 4: the displayed
position's rate of change is *smallest* (most compressed) near the endpoints and
*largest* (amplified) near the midpoint — not the reverse.

`s(b_endpoint) = 0.72`, close to the plan's `≈ 0.74 (≈ 1/1.35)` hypothesis. Per the
plan's own pre-registered branch: *"If `s(b_endpoint) ≈ 0.74`, the existing boost
was calibrated on purpose."*

## Analysis

`updateFusedSnapshot`'s `velMps` is a finite difference of the **already-biased**
display `x` (`(x - prevFusedX) / dt`), not of raw `balance`. Because `s(b)` is
smallest at the endpoints, a fixed unit of real balance change produces the
*smallest* displayed-`x` displacement there — meaning the raw finite-difference
velocity under-reports the true rate of balance change close to a node. Recovering
the undamped rate requires scaling up by approximately `1/s(b)`, which at the
endpoint is `1/0.72 ≈ 1.39` — closely matching the existing code's boost ceiling of
**1.35×**, applied via a smooth ramp (`Math.pow(endpointStrength, 0.8)`) that is
~0 at the midpoint (where `s(b)` is large and no compensation is needed or wanted)
and ramps toward its ceiling near the endpoints (where `s(b)` is smallest and
compression is worst).

**Conclusion:** the boost's direction, shape, and rough magnitude are consistent
with deliberate compensation for the display bias's endpoint compression, not a
bug. The original "under-compensates" claim that motivated Area 4 does not survive
measurement.

## Decision

**No change to Area 4.** `updateFusedSnapshot`'s endpoint boost formula in
`server/lib/websocket.ts` is left as-is. This closes the Area 4 gate as "measured,
confirmed intentional" rather than as a formula change — no re-validation campaign
(B5) is triggered because nothing behavioral changes.

This also resolves **N5** (the plan's display/number-divergence question) without
needing to pick from its three options: the current code already derives velocity
from the **displayed** `x` (post-bias), which is exactly N5's recommended Option 2
— it was already the shipped behavior, not a change to make. `radialTarget.speed`
stays **[TO BE MEASURED]** in the report per B6 regardless (this ADR measures the
*display-bias derivative*, not real-world tracking accuracy).

## Consequences

- Area 4 requires no code change, no consumer audit gate, and no contract tests —
  those (B2/B4) remain required only for Area 5 (the unrelated fallback-path dt bug),
  which proceeds independently.
- If a future change proposes deriving velocity from **raw** `balance` instead of
  displayed `x` (the plan's N5 Option 3), it must re-run this measurement's
  reasoning against the new formula and re-open this ADR — the 1.35× ceiling is
  calibrated for the displayed-`x` finite difference specifically, not for a
  raw-balance-derived velocity.
- The `s(b)` table above is the reference measurement for any future revisit of
  `BALANCE_BIAS_EXPONENT` or the endpoint boost ceiling; both are coupled (changing
  one without re-measuring the other will silently mis-calibrate the boost).
