# 05 — Motion display specification (document only; no runtime or UI change made)

**Status.** Specification of what a display of movement can *honestly* show on the two-node (N1+N2) rig. Nothing in `client/`, `server/` or `shared/` was changed. Evidence base: `01-…04-*.md` in this folder and the code reads cited below (read-only, this session, HEAD `744ce43` + Thaer's uncommitted edits).

## 0. Precondition from T4

**No scoring candidate met the pre-registered criteria** (04-two-node-eval.md). The data therefore do *not* support a display that says "a person is present" or "the room is empty" from these scores. What follows specifies the most a display can truthfully do with them: show *how much each node's signal is currently changing*, labelled as uncalibrated, and keep the existing, already-caveated one-dimensional axis indicator behind its existing gates. Any threshold, colour break or "motion/no motion" cut-off is `[TO BE MEASURED]` (T6 campaign) and is deliberately **not** specified here.

## 1. What may be shown

| element | content | source / reuse | honest label |
|--|--|--|--|
| **Per-node motion-intensity trace** (N1, N2) | A slow trace over the last few minutes of the node's perturbation relative to *that node's own recent baseline* (per-node robust z, as in 04). Never a probability, never a percentage "confidence". | Existing per-node tracker output (`NodeBaselineTracker`, smoothing τ = 0.6154 s, `server/lib/node-baseline.ts:141`) or the T4 per-node z. | Caveat in the existing `{primary, secondary}` shape (proposal): primary **"MOTION INTENSITY — UNCALIBRATED"**, secondary **"relative to this node's own recent baseline; no motion does not mean nobody is there"**. |
| **State chip per node and overall** | `MOTION` / `NO MOTION` / `NODE STALE` (and `DEGRADED` when the existing `targetState.state === "degraded"`). | Maps onto the existing `TargetState.state` enum `none | stale | idle | moving | degraded` (`shared/schema.ts:355`) plus the per-node `stale` flag. | `NO MOTION` is the only quiet-state wording allowed. **Never "EMPTY", "CLEAR" or "NO PERSON".** |
| **Baseline age** | Time since the reference was learned/refreshed, shown beside the trace. | Needed because drift (03-drift.md) makes an old reference unreliable; adaptive trackers already exist. | "reference age: 14 min — may no longer match the room". No numeric limit is specified (`[TO BE MEASURED]`). |
| **1-D on-axis indicator** | The existing fused_two_node dot on the N1–N2 line, only where the existing gates already allow it. | `canPresentLiveTargetPosition`, `getLivePositionCaveat` (`shared/target-presentation.ts:33,57`) — reuse unchanged. For `fused_two_node` the caveat is already **"ON-AXIS ESTIMATE - NOT ROOM POSITION" / "front/back ambiguous - off-axis subjects project onto the baseline"**. | Unchanged. The indicator is a *balance* of the two nodes' perturbation, not a range measurement. |

**What the trace can resolve.** The tracker's smoothing time constant is 0.6154 s (a first-order low-pass with corner ≈ 1/(2π·0.6154) ≈ **0.26 Hz**; the brief's ≈ 0.33 Hz is `[UNVERIFIED]` — it would correspond to τ ≈ 0.48 s and I did not find a stage with that constant), computed from 1.5 s windows in the offline work and 800 ms windows in the live tracker. The display therefore shows **slow trends (several seconds), not fast limb or gait dynamics**, and must not be animated as if it did. The brief's "render decay k ≈ 8, τ ≈ 125 ms" is `DECAY_RATES.speed = 8` in `client/src/lib/smooth-follow.ts:57` and applies only to the smoothed *speed* that scales the visual; position decay rates in the same table are 25–128. It adds visual smoothness; it is not the estimator bandwidth and adds no information.

## 2. What the display must NOT claim

1. **Room position.** Two nodes with one antenna each give a 1-D on-axis value only; off-axis subjects project onto the baseline and front/back is ambiguous (the existing caveat). No 2-D dot, no heat-map, no "zone".
2. **Pose, body shape, limbs, breathing-rate overlays.** `canPresentVolumetricTarget` is hard-wired `false` ("the system cannot honestly claim body shape from CSI"); keep it. (A defect list entry below concerns a path that bypasses it.)
3. **Bearing / angle of arrival.** No spatial angle exists on this hardware. `decor`, MUSIC and "signature" quantities are *temporal signal features*; any panel showing them must say "temporal feature, not a direction".
4. **"Empty" from "no motion".** Still people, and people in the shadow of a quiet link, produce no motion on a trace. `NO MOTION` ≠ `NOBODY`.
5. **Detection confidence / accuracy.** No percentage, "probability human", or accuracy figure may be shown for this scoring until the criteria in 04 §1 are met on independent data and a threshold is calibrated (T6). Demo/replay data must keep their existing permanent banner and `source_mode`.
6. **Fan/mechanical immunity.** In these data the fan moves the scores in a node-dependent direction (02-reproduction.md, point 4); do not label a rise as "human".
7. **That the display is calibrated.** It is relative to a baseline that drifts by more than the effect being shown (03-drift.md, Findings 1–2).

## 3. Gating rules (reuse, do not invent)

* Draw nothing positional unless `canPresentLiveTargetPosition(input)` is true; render `getLivePositionCaveat(input)` whenever a position is drawn (existing pattern: both are in `shared/target-presentation.ts`; the demo path returns `null` and relies on its banner).
* `canPresentIllustrativeBody` already withholds the body for `label === "mechanical"` and follows the live-position gate; do not widen it.
* Any new caveat for the intensity trace must use the same `TargetPresentationCaveat { primary, secondary }` type and sit next to the trace, not in a tooltip.
* F1/F2 stay untouched: the display is a passive viewer (no writes to nodes/serial/firmware) and AI advisories never write the authoritative verdict.

## 4. Current-code mismatches found while reading (issues, not fixed)

| ID | mismatch | evidence |
|--|--|--|
| PS-EVAL-011 | The brief and `PhantomScan_HardwareReality_Alignment_Report.md:122` refer to `canRenderConfidentHuman`; **no such function exists** in the code. The real gates are `canPresentTruthfulTarget`, `canPresentLiveTargetPosition`, `canPresentIllustrativeBody`, `canPresentVolumetricTarget`, `canPresentAxisMotionVector` (`shared/target-presentation.ts:22–115`). | Grep over `*.ts, *.tsx, *.md, *.py`: one hit, in that report. |
| PS-EVAL-012 | "k ≈ 8, τ ≈ 125 ms" is speed-only smoothing (`client/src/lib/smooth-follow.ts:57`), not a display filter for node intensity; the estimator corner is ≈ 0.26 Hz from τ = 0.6154 s, not 0.33 Hz. | `smooth-follow.ts:50–62`; `node-baseline.ts:141`. |
| PS-EVAL-013 | Two live nodes run the **legacy energy gate** (`fuseTwoNodeTarget`: `max(motion1, motion2) ≥ threshold`), whereas 3–4 nodes run the adaptive per-node tier trackers + `RoomPresence`. The drift-tolerant logic is therefore not used on the two-node rig. In the offline reference run the legacy gate at its default fired for 12.6 % of walking ticks (04 §5). | `server/lib/node-fusion.ts:435`; `server/lib/websocket.ts:246–262, 1274–1314`. |
| PS-EVAL-010 | Threshold defaults disagree: `DEFAULT_MOTION_THRESHOLD = 0.6` (`node-fusion.ts:43`) vs `motionThreshold ?? 0.05` (`websocket.ts:152`). Not changed. | as cited. |
| PS-EVAL-014 | `config/room.json` declares four anchors (N1 (−2,−3), N2 (2,−3), N3 (2,3), N4 (−2,3)) and a router at N2's anchor; with only N1/N2 streaming the system is `fused_two_node` on the N1–N2 line (4 m). The brief says the July rig used 3 m; the committed geometry should be re-measured on the next recording (T6) — position-scale labels depend on it. | `config/room.json`; brief (`[UNVERIFIED]` for 3 m). |
| PS-EVAL-015 | The node-1 link changed by ≈ 11 dB mid-evening (01 §3) and nothing in the live UI or dataset header records node moves; a display that shows relative intensity needs that provenance to warn "reference may be invalid". | 01-data-inventory.md §3. |

## 5. Acceptance checks for whoever implements this later

1. With a recorded empty-room file replayed through the real pipeline, the UI never shows the words EMPTY, CLEAR, or a person icon, only `NO MOTION`.
2. Every intensity trace has its caveat text visible without hover; removing the caveat prop fails a test.
3. A `stale` node shows `NODE STALE` and its trace greys out; the overall state never reads `MOTION` from a stale node alone.
4. The trace's smoothing constant is imported from the tracker, not duplicated; a test fails if the displayed bandwidth is claimed above the tracker's.
5. No new numeric threshold or colour break appears in code before T6 provides measured values.
