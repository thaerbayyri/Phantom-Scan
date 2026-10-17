/**
 * Phantom Balance Fusion — two-node CSI fusion, 1-D localization.
 *
 * With only two nodes we cannot resolve a true (x, z). What we CAN do is use each
 * node's *absolute, unsaturated* per-window amplitude perturbation (`absStd`) as a
 * proximity proxy, then place the target on the straight line between the two board
 * anchors via
 *
 *     balance = r2 / (r1 + r2)     (0 → at node 1, 0.5 → midpoint, 1 → at node 2)
 *
 * This module is intentionally PURE (no sockets, no clock) so the localization math
 * is unit-tested independently of the websocket pipeline.
 */

export interface NodeAnchor {
  x: number;
  z: number;
}

/**
 * Display-only motion saturation scale (the legacy `* 4` factor).
 *
 * COUPLING WARNING: this constant only affects the *display* `motion` value
 * (localization uses the raw unsaturated `absStd`). But `motion` is exactly what
 * `motionThreshold` is compared against, so it sets where motion saturates to 1.0.
 * If you retune this, re-derive `motionThreshold` in the same change — never
 * independently. See `computeNodeMotion` and `DEFAULT_MOTION_THRESHOLD`.
 */
export const MOTION_SATURATION_SCALE = 4;

/**
 * Presence/motion gate for emitting a fused target. THIS IS THE DETECTOR.
 *
 * Calibrated 2026-07-20 against this rig's measured empty-room baseline
 * (`max(motion1, motion2)` over 296 samples: mean 0.49, sigma 0.027, max 0.58 —
 * see LIVE_HARDWARE_TEST_REPORT.md). 0.6 sits just above that noise ceiling.
 * Re-calibrate via scripts/calibrate-threshold.ts (and re-validate against a
 * negative control: a fan/curtain must be REJECTED while a still, breathing-only
 * person is still detected) if the room or hardware setup changes materially.
 * Override at runtime via PHANTOM_MOTION_THRESHOLD, or persistently via the
 * "Fused Target Presence Threshold" slider (server/lib/runtime-settings.ts).
 */
export const DEFAULT_MOTION_THRESHOLD = Number.parseFloat(
  process.env.PHANTOM_MOTION_THRESHOLD ?? "0.6",
);

/**
 * Deadband for the approach/recede trend, in m/s along the N1–N2 axis.
 *
 * PLACEHOLDER (~0.05 m/s) — calibrate against real data, not settled. At the
 * ~3–7 fps historically measured on this firmware path, balance updates are
 * ~150–330 ms apart and balance itself is noisy over its 3 s window, so the
 * instantaneous velocity estimate is jumpy. This deadband is coupled to the
 * same window/fps assumptions as PHANTOM_MOTION_THRESHOLD — retune together.
 * Override at runtime via PHANTOM_TREND_DEADBAND_MPS.
 */
export const TREND_DEADBAND_MPS = Number.parseFloat(
  process.env.PHANTOM_TREND_DEADBAND_MPS ?? "0.05",
);

/**
 * Endpoint bias for the display projection.
 *
 * 1.0 = linear balance; values below 1 pull the projected x harder toward the
 * nearest node while keeping 0, 0.5, and 1 fixed. This affects only the
 * on-axis displayed position, not the underlying balance ratio.
 */
export const BALANCE_BIAS_EXPONENT = Number.parseFloat(
  process.env.PHANTOM_BALANCE_BIAS_EXPONENT ?? "0.72",
);

/**
 * Contrast exponent applied to the raw per-node perturbations BEFORE the
 * balance ratio: balance = r2^p / (r1^p + r2^p).
 *
 * Both nodes see the same walking person, so r1 and r2 are correlated and the
 * linear ratio compresses toward 0.5 (the dot hugs the midpoint). p > 1 widens
 * balance toward 0/1 when one node clearly sees more perturbation, letting the
 * target reach the node it is actually near. p = 1 restores the linear ratio.
 * Unlike BALANCE_BIAS_EXPONENT (display-only), this shapes the balance VALUE
 * and therefore also the trend velocity. Override via PHANTOM_BALANCE_CONTRAST.
 */
export const BALANCE_CONTRAST_EXPONENT = Number.parseFloat(
  process.env.PHANTOM_BALANCE_CONTRAST ?? "2.0",
);

export type NodeTrend = "approaching" | "receding" | "stable";

// ── Classifier corroboration (Item 1 / PS-GAP-001) ─────────────────────────
//
// `MicroDopplerClassifier` (server/lib/signal-processing.ts) computes a
// human/mechanical/unknown label from deterministic DFT + autocorrelation
// features on the raw amplitude signal — it is NOT an ML/AI model, so wiring
// it into the presence gate does not touch the advisory-only AI firewall
// (F1 / PS-AUDIT-014, server/lib/websocket.ts:366-390). It mirrors the
// firmware's own `edge_evaluate_human_presence` pattern (edge_dsp_pure.c):
// motion AND NOT-confidently-mechanical, never the classifier alone.
//
// This is deliberately a CORROBORATING gate, not a replacement for the
// energy/motion gate: the classifier can only SUPPRESS a presence claim the
// energy gate already made (when it confidently asserts "mechanical"); it
// can never assert presence on its own. This preserves the project's
// deterministic-first, energy-gate-is-primary design.

export type ClassifierCorroboration = "confirmed" | "contradicted" | "inconclusive" | "not_evaluated";

export interface ClassifierGateInput {
  label: "human" | "mechanical" | "unknown";
  humanProb: number;
}

/**
 * How confidently the classifier must assert "mechanical" (humanProb at or
 * below this) before it's allowed to suppress a presence claim. Deliberately
 * stricter than the classifier's own label boundary (0.35, see
 * MicroDopplerClassifier) so a merely-borderline "mechanical" label does not
 * suppress a real detection — only a confident one does. PLACEHOLDER pending
 * the Item 2 real-hardware fan/HVAC negative-control session; re-tune once
 * that data exists. Override at runtime via PHANTOM_MECHANICAL_REJECT_MAX.
 */
export const DEFAULT_MECHANICAL_REJECT_HUMAN_PROB_MAX = Number.parseFloat(
  process.env.PHANTOM_MECHANICAL_REJECT_MAX ?? "0.2",
);

/**
 * Pure corroboration decision: does the (optional) classifier evidence
 * suppress an otherwise-passing energy gate? Exposed standalone (in addition
 * to being used inside `fuseTwoNodeTarget`/`hasSingleNodePresenceEvidence`)
 * so callers can log/observe the reason a target was or wasn't suppressed —
 * e.g. for the Item 2 negative-control analysis, which needs to distinguish
 * "energy gate never fired" from "energy gate fired but classifier vetoed."
 */
export function evaluateClassifierCorroboration(
  classifier: ClassifierGateInput | undefined,
  mechanicalRejectHumanProbMax: number = DEFAULT_MECHANICAL_REJECT_HUMAN_PROB_MAX,
): { suppress: boolean; corroboration: ClassifierCorroboration } {
  if (!classifier) {
    return { suppress: false, corroboration: "not_evaluated" };
  }
  if (classifier.label === "mechanical" && classifier.humanProb <= mechanicalRejectHumanProbMax) {
    return { suppress: true, corroboration: "contradicted" };
  }
  if (classifier.label === "human") {
    return { suppress: false, corroboration: "confirmed" };
  }
  // "mechanical" below the confident-reject bar, or "unknown" — ambiguous:
  // must not become stricter than today's energy-gate-only baseline.
  return { suppress: false, corroboration: "inconclusive" };
}

/**
 * Per-node approach/recede trend from the signed axis velocity.
 *
 * `axisVelMps` > 0 means balance rising = target moving toward node 2.
 * Inside the deadband the PREVIOUS trends are kept (hysteresis) so the label
 * doesn't flicker between frames; pass `{ 1: "stable", 2: "stable" }` when no
 * live target exists.
 */
export function computeNodeTrends(
  axisVelMps: number,
  prev: { 1: NodeTrend; 2: NodeTrend },
  deadbandMps: number = TREND_DEADBAND_MPS,
): { 1: NodeTrend; 2: NodeTrend } {
  if (!Number.isFinite(axisVelMps) || Math.abs(axisVelMps) < deadbandMps) {
    return prev;
  }
  return axisVelMps > 0
    ? { 1: "receding", 2: "approaching" } // balance rising -> toward N2
    : { 1: "approaching", 2: "receding" };
}

const EPS = 1e-6;

export interface NodeMotion {
  /** Mean amplitude over the window. */
  mean: number;
  /** Raw, UNSATURATED per-window std of amplitude — used for `balance`. */
  absStd: number;
  /** Saturated 0..1 motion for display/thresholding only. */
  motion: number;
}

/**
 * Per-node motion energy from a window of per-subcarrier amplitude FRAMES
 * (each frame = amplitude vector for one received packet).
 *
 * Per-node update step:
 *   k         = min frame length (subcarrier count)
 *   sub_std_j = temporal pstdev of subcarrier j across the window
 *   absStd    = mean(sub_std)          — raw, unsaturated → balance
 *   base      = mean frame amplitude   — normalizer
 *   motion    = min(1, absStd/base·4)  — display/threshold only
 *
 * This is what makes balance track a moving person: per-subcarrier temporal
 * variation is human-induced perturbation, whereas a single "best subcarrier"
 * scalar changes selection index frame-to-frame and its std is mostly noise.
 */
export function computeNodeMotionFromMatrix(frames: number[][]): NodeMotion {
  const usable = frames.filter((f) => f.length > 0);
  if (usable.length < 2) {
    return { mean: 0, absStd: 0, motion: 0 };
  }
  const k = Math.min(...usable.map((f) => f.length));
  if (k === 0) {
    return { mean: 0, absStd: 0, motion: 0 };
  }

  // Per-subcarrier temporal std: for each subcarrier j, measure how much its
  // amplitude varied across the window, then average the k stds into absStd —
  // the raw (unsaturated) perturbation that feeds the balance ratio.
  let stdSum = 0;
  for (let j = 0; j < k; j++) {
    let m = 0;
    for (const f of usable) m += f[j];
    m /= usable.length;
    let acc = 0;
    for (const f of usable) {
      const d = f[j] - m;
      acc += d * d;
    }
    stdSum += Math.sqrt(acc / usable.length);
  }
  const absStd = stdSum / k;

  // Baseline amplitude (mean over subcarriers, then over frames) — normalizes
  // absStd so `motion` is a relative perturbation comparable across nodes with
  // different RSSI/gain. `|| 1.0` guards divide-by-zero on silent input.
  let base = 0;
  for (const f of usable) {
    let s = 0;
    for (let j = 0; j < k; j++) s += f[j];
    base += s / k;
  }
  base = base / usable.length || 1.0;

  const motion = Math.min(1.0, (absStd / base) * MOTION_SATURATION_SCALE);
  return { mean: base, absStd, motion };
}

export interface FuseInput {
  /** Raw unsaturated perturbation (absStd) for node 1 and node 2. */
  r1: number;
  r2: number;
  /** Saturated display motion for node 1 and node 2 (for the presence gate). */
  motion1: number;
  motion2: number;
  anchors: { 1: NodeAnchor; 2: NodeAnchor };
  motionThreshold?: number;
  /** Balance contrast exponent p (default BALANCE_CONTRAST_EXPONENT). */
  contrastExponent?: number;
  /** Optional corroborating classifier evidence — see evaluateClassifierCorroboration. */
  classifier?: ClassifierGateInput;
  /** Override for DEFAULT_MECHANICAL_REJECT_HUMAN_PROB_MAX. */
  mechanicalRejectHumanProbMax?: number;
}

export interface FusedTarget {
  x: number;
  z: number;
  /** 0 → at node 1, 0.5 → midpoint, 1 → at node 2. Contrast-shaped (see
   * BALANCE_CONTRAST_EXPONENT) — this is the DISPLAY value; it is what
   * positions the on-screen target, not the canonical linear ratio.
   * Undefined when this target came from `fuseNodeTargets` (3+ nodes) —
   * a single axis-balance scalar has no meaning once the target is a true
   * 2-D room centroid. */
  balance?: number;
  /** Canonical, undecorated balance = r2/(r1+r2) — independent of
   * BALANCE_CONTRAST_EXPONENT and BALANCE_BIAS_EXPONENT. Authoritative
   * cross-check value (PS-AUDIT-003/011, ADR-054); never drives the
   * on-screen target position, which remains `balance` above. Undefined
   * for the same reason as `balance` above when N > 2 nodes fused it. */
  balanceLinear?: number;
  /** Range to the NEAREST node anchor in meters (physically meaningful). */
  distToNearestNodeM: number;
  /** Whether the optional classifier corroborated, contradicted, or was
   * inconclusive/not-evaluated this tick — see evaluateClassifierCorroboration. */
  classifierCorroboration: ClassifierCorroboration;
}

function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value));
}

/**
 * Canonical linear balance = r2/(r1+r2), with no contrast exponent or
 * display bias applied. This is the authoritative/canonical cross-check
 * value (PS-AUDIT-003/011, ADR-054) — it is NEVER used to place the
 * on-screen target, which uses the contrast+bias-shaped `balance` instead.
 */
export function computeLinearBalance(r1: number, r2: number): number {
  const a = Number.isFinite(r1) ? Math.max(0, r1) : 0;
  const b = Number.isFinite(r2) ? Math.max(0, r2) : 0;
  return a + b > EPS ? b / (a + b) : 0.5;
}

/**
 * Gain-normalize a node's raw perturbation (`absStd`) by that same node's own
 * mean amplitude (`mean`/`base`), producing a dimensionless, UNSATURATED
 * relative-perturbation ratio invariant to any per-node multiplicative
 * gain/RSSI/antenna mismatch (PS-BEHTEST-004).
 *
 * `std(g·X) = g·std(X)` for a uniform gain `g` applied to one node's raw
 * amplitude, and that same `g` scales that node's own mean identically — so
 * `absStd/mean` cancels `g` exactly, regardless of which node it comes from.
 * This is the same ratio `computeNodeMotionFromMatrix`'s display `motion`
 * field already uses, minus its `* MOTION_SATURATION_SCALE` and
 * `Math.min(1, …)` clamp: `balance`'s localization math needs the raw
 * unsaturated ratio, not the saturated display value (two nodes both past
 * saturation would otherwise collapse to a false midpoint).
 */
export function computeGainNormalizedPerturbation(absStd: number, mean: number): number {
  const s = Number.isFinite(absStd) ? Math.max(0, absStd) : 0;
  const m = Number.isFinite(mean) && mean > 0 ? mean : 1.0;
  return s / m;
}

/**
 * AGC-normalized link perturbation (RuView ADR-345 per-link motion metric).
 *
 * Each frame is first divided by ITS OWN mean amplitude across subcarriers,
 * then the per-subcarrier temporal std is averaged. A frame-to-frame gain
 * change (receiver AGC, TX power, a uniform broadband fade) scales every
 * subcarrier together and cancels out; what remains is a change in the
 * multipath SHAPE across subcarriers — what a moving body does to a link.
 * computeGainNormalizedPerturbation only cancels a constant per-node gain,
 * so AGC swings in an empty room read as motion there.
 *
 * Dimensionless and invariant to any per-node or per-frame gain. Frames
 * with a non-positive mean are skipped; returns 0 for <2 usable frames.
 */
export function computeAgcNormalizedPerturbation(frames: number[][]): number {
  const normalized: number[][] = [];
  for (const frame of frames) {
    if (frame.length === 0) continue;
    const mean = frame.reduce((s, a) => s + a, 0) / frame.length;
    if (!(mean > EPS)) continue;
    normalized.push(frame.map((a) => a / mean));
  }
  if (normalized.length < 2) return 0;
  const k = Math.min(...normalized.map((f) => f.length));
  let stdSum = 0;
  for (let j = 0; j < k; j++) {
    let m = 0;
    for (const f of normalized) m += f[j];
    m /= normalized.length;
    let acc = 0;
    for (const f of normalized) acc += (f[j] - m) ** 2;
    stdSum += Math.sqrt(acc / normalized.length);
  }
  return stdSum / k;
}

/**
 * fused_room per-node approach/recede trend from the 2-D target velocity:
 * radial velocity toward node i is −v·(p − aᵢ)/|p − aᵢ| (positive = closing
 * in). Inside `deadbandMps` the node reads "stable". computeNodeTrends only
 * handles the 2-node axis, which is why room-mode trend arrows were inert.
 */
export function computeRadialTrends(
  position: { x: number; z: number },
  velocity: { vx: number; vz: number },
  anchors: Record<number, { x: number; z: number }>,
  deadbandMps: number = TREND_DEADBAND_MPS,
): Record<number, NodeTrend> {
  const trends: Record<number, NodeTrend> = {};
  for (const [key, anchor] of Object.entries(anchors)) {
    const dx = position.x - anchor.x;
    const dz = position.z - anchor.z;
    const dist = Math.hypot(dx, dz);
    if (dist < EPS || !Number.isFinite(velocity.vx) || !Number.isFinite(velocity.vz)) {
      trends[Number(key)] = "stable";
      continue;
    }
    const closingMps = -(velocity.vx * dx + velocity.vz * dz) / dist;
    trends[Number(key)] =
      Math.abs(closingMps) < deadbandMps ? "stable" : closingMps > 0 ? "approaching" : "receding";
  }
  return trends;
}

/**
 * Bias the projected display position toward the nearest node while preserving
 * 0, 0.5, and 1 exactly. Used only for the displayed on-axis estimate.
 */
export function biasBalanceTowardNearestNode(
  balance: number,
  exponent: number = BALANCE_BIAS_EXPONENT,
): number {
  const clamped = clamp01(balance);
  const signed = clamped * 2 - 1;
  const magnitude = Math.abs(signed);
  if (magnitude <= EPS) {
    return 0.5;
  }
  const biasedMagnitude = Math.pow(magnitude, exponent);
  return clamp01(0.5 + Math.sign(signed) * biasedMagnitude * 0.5);
}

/**
 * Fuse two nodes into a 1-D target on the line between the anchors.
 *
 * Returns `null` (NO target — not a centered ghost) when neither node clears the
 * motion threshold, or when there is effectively no perturbation. This is the
 * empty-room gate: a quiet room must not paint a target at the midpoint.
 */
/**
 * The raw energy/motion presence gate alone, with no classifier involved —
 * factored out of `fuseTwoNodeTarget` so `wasSuppressedByClassifier` can
 * reuse the exact same formula rather than risk drifting out of sync with
 * a second, independently-maintained copy.
 */
function computeEnergyGatePassed(input: FuseInput, r1: number, r2: number): boolean {
  const threshold = input.motionThreshold ?? DEFAULT_MOTION_THRESHOLD;
  return Math.max(input.motion1, input.motion2) >= threshold && r1 + r2 > EPS;
}

/**
 * Observability helper (Item 1): true only when the energy gate demonstrably
 * passed AND the classifier is what suppressed the target — as opposed to
 * the energy gate never having fired at all. `fuseTwoNodeTarget` itself
 * only returns null either way, which is sufficient to gate but not to
 * distinguish the cause; this lets the Item 2 negative-control analysis
 * (and the live single_node/fused_two_node hold-reason logging in
 * websocket.ts) tell the two suppression causes apart.
 */
export function wasSuppressedByClassifier(input: FuseInput): boolean {
  const r1 = Number.isFinite(input.r1) ? Math.max(0, input.r1) : 0;
  const r2 = Number.isFinite(input.r2) ? Math.max(0, input.r2) : 0;
  if (!computeEnergyGatePassed(input, r1, r2)) {
    return false;
  }
  return evaluateClassifierCorroboration(input.classifier, input.mechanicalRejectHumanProbMax).suppress;
}

export function fuseTwoNodeTarget(input: FuseInput): FusedTarget | null {
  const r1 = Number.isFinite(input.r1) ? Math.max(0, input.r1) : 0;
  const r2 = Number.isFinite(input.r2) ? Math.max(0, input.r2) : 0;

  // PRESENCE GATE: someone is "present" only if at least one node's saturated
  // motion clears the calibrated threshold AND there is real perturbation
  // energy (r1+r2 > EPS). Failing either → null → the UI shows an empty room.
  const energyGatePassed = computeEnergyGatePassed(input, r1, r2);

  // CORROBORATING GATE (Item 1): the energy gate remains primary/authoritative.
  // The classifier can only suppress a presence claim the energy gate already
  // made — it can never assert presence on its own (see evaluateClassifierCorroboration).
  const { suppress, corroboration } = evaluateClassifierCorroboration(
    input.classifier,
    input.mechanicalRejectHumanProbMax,
  );
  const present = energyGatePassed && !suppress;
  if (!present) {
    return null;
  }

  // Contrast-sharpened ratio (see BALANCE_CONTRAST_EXPONENT): widens balance
  // toward the node that clearly sees more perturbation.
  const p = input.contrastExponent ?? BALANCE_CONTRAST_EXPONENT;
  const r1p = Math.pow(r1, p);
  const r2p = Math.pow(r2, p);
  const balance = r1p + r2p > EPS ? r2p / (r1p + r2p) : 0.5;
  // Place the target on the straight N1–N2 line by linear interpolation of the
  // (display-biased) balance: 0 → exactly at node 1, 1 → exactly at node 2.
  const biasedBalance = biasBalanceTowardNearestNode(balance);
  const n1 = input.anchors[1];
  const n2 = input.anchors[2];
  const x = n1.x + (n2.x - n1.x) * biasedBalance;
  const z = n1.z + (n2.z - n1.z) * biasedBalance;

  // Distance to the nearest anchor is the only physically meaningful range in
  // this 1-D geometry (feeds the "distance" readout on the dashboard).
  const d1 = Math.hypot(x - n1.x, z - n1.z);
  const d2 = Math.hypot(x - n2.x, z - n2.z);

  const balanceLinear = computeLinearBalance(r1, r2);

  return { x, z, balance, balanceLinear, distToNearestNodeM: Math.min(d1, d2), classifierCorroboration: corroboration };
}

// ── Fallback (non-Kalman, non-fused) velocity — Area 5/NEW-1 ───────────────

export interface FallbackVelocitySample {
  x: number;
  z: number;
  atMs: number;
}

export interface FallbackVelocityResult {
  vx: number;
  vz: number;
  speed: number;
}

/** Real-time gap beyond which a fallback sample is treated as a fresh start, never diffed. */
export const FALLBACK_VELOCITY_MAX_GAP_S = 0.25;
/** Floor on dt so a near-zero interval can't blow up the velocity. */
export const FALLBACK_VELOCITY_MIN_DT_S = 0.02;

/**
 * Frame-rate-independent instantaneous velocity for the non-Kalman, non-fused
 * fallback path (used when the primary DBSCAN/Kalman tracker misses this tick).
 * Returns zero — never a spike — when there is no previous sample or the real
 * elapsed gap exceeds `FALLBACK_VELOCITY_MAX_GAP_S`.
 *
 * Callers own invalidating `prev` (passing `null`) on every condition that
 * breaks positional continuity: primary-tracker success, a fused_two_node
 * <-> single_node mode transition, and the 5s hard-clear/1.5s stale-hold
 * lifecycle — this function only guards the generic real-time-gap case.
 */
export function computeFallbackVelocity(
  prev: FallbackVelocitySample | null,
  raw: { x: number; z: number },
  nowMs: number,
): FallbackVelocityResult {
  if (!prev) {
    return { vx: 0, vz: 0, speed: 0 };
  }
  const realGapS = (nowMs - prev.atMs) / 1000;
  if (realGapS > FALLBACK_VELOCITY_MAX_GAP_S) {
    return { vx: 0, vz: 0, speed: 0 };
  }
  const dt = Math.max(realGapS, FALLBACK_VELOCITY_MIN_DT_S);
  const vx = (raw.x - prev.x) / dt;
  const vz = (raw.z - prev.z) / dt;
  return { vx, vz, speed: Math.hypot(vx, vz) };
}

// ── Single-node presence gate (ADR-057) ────────────────────────────────────

/**
 * Whether single-node mode has ANY real evidence a target is present this
 * tick, before broadcasting a fresh `radialTarget`. Unlike `fuseTwoNodeTarget`
 * (which already gates on `present = max(motion1,motion2) >= threshold`),
 * single-node mode had no equivalent check at all — the MUSIC-spectrum point
 * cloud and DBSCAN/Kalman tracker can both cluster ambient noise/multipath
 * with nobody in the room, and that noise-derived target was broadcast
 * unconditionally every tick.
 *
 * Uses `motionDetected OR a confident tracked cluster` (not motion alone) so
 * a real-but-stationary person — who may not trip the temporal motion gate,
 * but can still form a spatial DBSCAN cluster — is not treated as absent.
 * This does not fully solve detecting a perfectly still person via spatial
 * clustering alone (that needs a calibrated absolute noise floor, unverified
 * on real hardware); it solves the reported bug (continuous ghost target
 * with nobody present) by requiring at least one real evidence signal.
 *
 * Item 1: `classifier` is the same optional corroborating evidence
 * `fuseTwoNodeTarget` accepts — it can only SUPPRESS presence the energy
 * evidence (motion OR tracked cluster) already established, never assert it
 * alone. Omitting `classifier` (existing call sites) is fully backward
 * compatible — behavior is unchanged from before this gate existed.
 */
// ── N-node room fusion (fused_room mode, 3-4 active nodes) ─────────────────

/**
 * Per-node input sample for `fuseNodeTargets`: this node's raw unsaturated
 * perturbation (`r`, same quantity as `r1`/`r2` above), its saturated display
 * motion (feeds the presence gate), and its fixed anchor position.
 */
export interface NodeFuseSample {
  id: number;
  r: number;
  motion: number;
  anchor: NodeAnchor;
}

export interface FusedRoomTarget {
  x: number;
  z: number;
  /** Per-node contrast-weighted share (sums to 1) — generalizes `balance`. */
  weights: Record<number, number>;
  nearestNodeId: number;
  /** Range to the NEAREST node anchor in meters (physically meaningful). */
  distToNearestNodeM: number;
  classifierCorroboration: ClassifierCorroboration;
}

/**
 * Fuse 3+ nodes into a 2-D position via a contrast-weighted centroid of the
 * active node anchors: `pos = Σ(anchor_i · r_i^p) / Σ(r_i^p)`.
 *
 * This is the direct N-node generalization of `fuseTwoNodeTarget`'s balance
 * math: expanding `n1·(1-balance) + n2·balance` with
 * `balance = r2^p/(r1^p+r2^p)` gives exactly `n1·r1^p/(r1^p+r2^p) +
 * n2·r2^p/(r1^p+r2^p)` — a 2-point weighted centroid with weight `r_i^p`.
 * Same perturbation-proxy honesty as the 2-node case: this is NOT RF
 * ranging/multilateration, just where the strongest CSI perturbation sits
 * relative to the node ring. Unlike `fuseTwoNodeTarget`, no
 * `biasBalanceTowardNearestNode` display squeeze is applied here — that step
 * only makes sense projected onto a single N1-N2 axis; the contrast exponent
 * alone does the equivalent "pull toward the dominant node" work in 2-D.
 *
 * Returns `null` under the same empty-room gate as `fuseTwoNodeTarget`: no
 * node's saturated motion clears the threshold, or there is no perturbation
 * energy at all.
 */
export function fuseNodeTargets(
  samples: NodeFuseSample[],
  opts: {
    motionThreshold?: number;
    contrastExponent?: number;
    classifier?: ClassifierGateInput;
    mechanicalRejectHumanProbMax?: number;
  } = {},
): FusedRoomTarget | null {
  const clean = samples.map((s) => ({
    ...s,
    r: Number.isFinite(s.r) ? Math.max(0, s.r) : 0,
    motion: Number.isFinite(s.motion) ? s.motion : 0,
  }));
  if (clean.length === 0) {
    return null;
  }

  const threshold = opts.motionThreshold ?? DEFAULT_MOTION_THRESHOLD;
  const totalR = clean.reduce((sum, s) => sum + s.r, 0);
  const maxMotion = clean.reduce((max, s) => Math.max(max, s.motion), 0);
  const energyGatePassed = maxMotion >= threshold && totalR > EPS;

  const { suppress, corroboration } = evaluateClassifierCorroboration(
    opts.classifier,
    opts.mechanicalRejectHumanProbMax,
  );
  if (!energyGatePassed || suppress) {
    return null;
  }

  const p = opts.contrastExponent ?? BALANCE_CONTRAST_EXPONENT;
  const weighted = clean.map((s) => ({ ...s, w: Math.pow(s.r, p) }));
  const totalW = weighted.reduce((sum, s) => sum + s.w, 0);

  const weights: Record<number, number> = {};
  let x = 0;
  let z = 0;
  if (totalW > EPS) {
    for (const s of weighted) {
      const share = s.w / totalW;
      weights[s.id] = share;
      x += s.anchor.x * share;
      z += s.anchor.z * share;
    }
  } else {
    // No node clearly dominates (degenerate all-zero perturbation) — fall
    // back to a plain unweighted centroid of the active anchors.
    for (const s of weighted) weights[s.id] = 1 / weighted.length;
    x = weighted.reduce((sum, s) => sum + s.anchor.x, 0) / weighted.length;
    z = weighted.reduce((sum, s) => sum + s.anchor.z, 0) / weighted.length;
  }

  let nearestNodeId = clean[0].id;
  let distToNearestNodeM = Infinity;
  for (const s of clean) {
    const d = Math.hypot(x - s.anchor.x, z - s.anchor.z);
    if (d < distToNearestNodeM) {
      distToNearestNodeM = d;
      nearestNodeId = s.id;
    }
  }

  return { x, z, weights, nearestNodeId, distToNearestNodeM, classifierCorroboration: corroboration };
}

export function hasSingleNodePresenceEvidence(
  motionDetected: boolean,
  hasTrackedTarget: boolean,
  classifier?: ClassifierGateInput,
  mechanicalRejectHumanProbMax?: number,
): boolean {
  const energyGatePassed = motionDetected || hasTrackedTarget;
  if (!energyGatePassed) {
    return false;
  }
  const { suppress } = evaluateClassifierCorroboration(classifier, mechanicalRejectHumanProbMax);
  return !suppress;
}

/**
 * Heuristic DISPLAY radius (m) of a fused_room centroid — "the person is
 * somewhere within about this distance of the marker". It is NOT a measured
 * error: with one antenna per node and an amplitude-perturbation centroid the
 * true error has never been validated against ground truth. It encodes three
 * honest facts: the estimate is coarse (base ≈ 35% of the shorter room side),
 * stronger evidence makes it better (confidence 0..1), and when one node
 * dominates the weights the centroid snaps toward that node's corner, which
 * is least trustworthy (+50% at full dominance).
 */
export function computePositionUncertaintyM(
  weights: Record<number, number>,
  confidence: number,
  roomMinDimM: number,
): number {
  const room = Number.isFinite(roomMinDimM) && roomMinDimM > 0 ? roomMinDimM : 4;
  const conf = Number.isFinite(confidence) ? Math.min(1, Math.max(0, confidence)) : 0;
  const maxShare = Math.max(0, ...Object.values(weights).filter(Number.isFinite));
  const dominance = Math.min(1, Math.max(0, (maxShare - 0.5) / 0.5));
  const radius = 0.35 * room * (1.4 - 0.6 * conf) * (1 + 0.5 * dominance);
  return Math.round(Math.min(0.6 * room, Math.max(0.3, radius)) * 100) / 100;
}
