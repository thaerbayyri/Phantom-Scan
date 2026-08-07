# ADR-058: Firmware-Side SFO/PDD Cross-Subcarrier Regression — Out of Scope for Now

**Status:** Accepted
**Date:** 2026-08-06
**Closes:** Item 7, `PhantomScan_FixAll_Session_Report.md` (fix-all session following `PhantomScan_Research_Gap_Analysis.md`)
**Related:** `docs/research/csi-phase-in-wifi-sensing.md`, ADR-014 (SOTA Signal Processing), ADR-051 (Runtime Authority)
**Decision maker:** Operator mandate — "evaluate, then act or formally defer" (explicit instruction for this item)

## Context

`docs/research/csi-phase-in-wifi-sensing.md` documents that
`scripts/rf_validation/phase_sanitizer.py` implements an offline cross-subcarrier
linear-fit SFO (Sampling Frequency Offset) / PDD (Packet Detection Delay)
correction (`φ(k) = a·k + b`, subtract the fit; synthetic self-test confirms
breathing-correlation recovery `>0.90` and SFO error `<0.01` rad), while
`firmware/esp32-csi-node/main/edge_processing.c` only performs temporal phase
unwrapping (`unwrap_phase`, called at lines 469 and 666) — no cross-subcarrier
regression exists on the firmware path. Re-verified directly against the current
firmware source on 2026-08-06 (grep for `SFO`/`PDD`/regression logic in
`edge_processing.c` and `edge_dsp_pure.c`: only `unwrap_phase` present).

Separately, re-verified that the live TS authority path already cancels
SFO/PDD via conjugate multiplication before computing phase-dependent
quantities: `server/lib/websocket.ts:802-804` —
`h1_conj_h2 = mul(h1Proc, conj(h2Proc))`, with the comment "Multiply H1 by the
conjugate of H2 to remove CFO and extract relative phase." This is the ADR-014
technique, applied on the path that actually drives detection.

Firmware's own phase-derived outputs (breathing/heart-rate BPM via
`edge_dsp_pure.c`'s zero-crossing/autocorrelation estimators) are routed to the
board's own local presence verdict and the "Board DSP" telemetry card
(`server/lib/udp-server.ts`) — **never fused into the host/live target or
presence decision** (confirmed in `PhantomScan_Research_Gap_Analysis.md` §2.1).

## Decision

**Do not port the cross-subcarrier SFO/PDD regression into firmware at this
time.** Per the explicit decision criteria for this item: the live TS path
already cancels SFO/PDD via conjugate multiplication, and firmware phase is
not relied on for any authoritative decision today. Implementing it now would
be effort spent hardening a code path whose output the system already
disregards for detection purposes — this ADR formally marks it out of scope
for the current phase rather than leaving it as an ambiguous, rediscoverable
"unfixed bug."

## Consequences

- If firmware-side phase (breathing/heart-rate BPM shown on the Board DSP
  card, or any future feature that consumes it directly) is ever promoted to
  an authoritative role — e.g., feeding the sovereign presence verdict, or a
  standalone-firmware deployment mode without a host — this gap must be
  closed or the promoted feature must be re-scoped to account for
  uncorrected SFO/PDD phase error first. Revisit this ADR before that
  promotion happens.
- The board's current phase-dependent outputs (breathing/heart-rate BPM,
  `EDGE_RESP_PERIOD_CV_MIN` periodicity gating) are unaffected by this
  decision in terms of correctness-as-shipped-today, since their own
  validation (per `PHANTOM_SCAN_REMEDIATION_REPORT.md`) was already
  synthetic-data-only and pending real-hardware negative controls
  independent of this specific gap.
- `docs/research/csi-phase-in-wifi-sensing.md` remains the reference
  documentation for this gap; this ADR is the formal disposition record.
