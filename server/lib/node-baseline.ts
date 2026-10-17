// ── Per-node adaptive baseline + presence tiers (fused_room) ───────
//
// Port of RuView's sensing-server smooth_and_classify_node idea to this
// project's per-node perturbation metric. The fixed DEFAULT_MOTION_THRESHOLD
// (0.6 on the saturated 0..1 motion scale) was calibrated on the 2-node rig
// and saturates on ~half of 4-node ticks; every node also has its own static
// multipath level. Each node instead learns its OWN empty-room level and
// reports how far it currently rises above it:
//
//   smoothed  EMA of the raw perturbation, τ = 0.6154 s
//   baseline  slow EMA, τ = 33.28 s (fast 1 s τ during the 5 s warm-up);
//             only updated when raw is not spiking above smoothed, and NOT
//             while a target is being held (bounded by maxFreezeMs) — so a
//             person standing still is not absorbed into the baseline
//   rise      max(0, smoothed / baseline − 1): dimensionless and gain-
//             invariant ("how many times above this node's own empty room")
//
// Every α is derived from the actual elapsed time (α = 1 − exp(−dt/τ)), so
// behaviour does not change with the tick or packet rate.
//
// Tier thresholds on `rise` are PROVISIONAL defaults pending the live 4-node
// empty-room calibration (scripts/calibrate-threshold.ts); override with
// PHANTOM_ROOM_TIER_STILL / _MOVING / _ACTIVE.

export type PresenceTier = "absent" | "present_still" | "present_moving" | "active";

const TIER_RANK: Record<PresenceTier, number> = {
  absent: 0,
  present_still: 1,
  present_moving: 2,
  active: 3,
};

export function tierAtLeast(tier: PresenceTier, floor: PresenceTier): boolean {
  return TIER_RANK[tier] >= TIER_RANK[floor];
}

export interface TierThresholds {
  /** rise at/above which a node reports present_still. */
  still: number;
  /** rise at/above which a node reports present_moving. */
  moving: number;
  /** rise at/above which a node reports active. */
  active: number;
}

const PROVISIONAL_THRESHOLDS: TierThresholds = Object.freeze({ still: 0.15, moving: 0.5, active: 1.5 });

function thresholdsFromEnv(env: Record<string, string | undefined>): TierThresholds {
  const read = (key: string, fallback: number) => {
    const value = Number.parseFloat(env[key] ?? "");
    return Number.isFinite(value) && value > 0 ? value : fallback;
  };
  const candidate = {
    still: read("PHANTOM_ROOM_TIER_STILL", PROVISIONAL_THRESHOLDS.still),
    moving: read("PHANTOM_ROOM_TIER_MOVING", PROVISIONAL_THRESHOLDS.moving),
    active: read("PHANTOM_ROOM_TIER_ACTIVE", PROVISIONAL_THRESHOLDS.active),
  };
  if (!(candidate.still < candidate.moving && candidate.moving < candidate.active)) {
    console.warn(
      `[ROOM] PHANTOM_ROOM_TIER_* must satisfy still < moving < active (got ${JSON.stringify(candidate)}); using defaults`,
    );
    return PROVISIONAL_THRESHOLDS;
  }
  return Object.freeze(candidate);
}

export const DEFAULT_TIER_THRESHOLDS: TierThresholds = thresholdsFromEnv(process.env);

export interface BaselineTrackerOptions {
  smoothTauS?: number;
  baselineTauS?: number;
  warmupS?: number;
  warmupTauS?: number;
  debounceS?: number;
  /** raw above smoothed·(1 + spikeMargin) is a spike and never updates the baseline. */
  spikeMargin?: number;
  /** Longest a held target may freeze the baseline (protects against a false
   *  target pinning it forever). */
  maxFreezeMs?: number;
  thresholds?: TierThresholds;
}

export interface BaselineUpdate {
  smoothed: number;
  baseline: number;
  rise: number;
  /** Debounced tier. */
  tier: PresenceTier;
  warmingUp: boolean;
}

const EPS = 1e-9;
/** Cap one update's dt so a long silence can't jump the EMAs in one step. */
const MAX_DT_S = 1.0;

function alphaFor(dtS: number, tauS: number): number {
  return tauS > 0 ? 1 - Math.exp(-dtS / tauS) : 1;
}

export class NodeBaselineTracker {
  private readonly smoothTauS: number;
  private readonly baselineTauS: number;
  private readonly warmupMs: number;
  private readonly warmupTauS: number;
  private readonly debounceMs: number;
  private readonly spikeMargin: number;
  private readonly maxFreezeMs: number;
  private readonly thresholds: TierThresholds;

  private smoothed = 0;
  private baseline = 0;
  private startMs: number | null = null;
  private lastMs = 0;
  private tier: PresenceTier = "absent";
  private pendingTier: PresenceTier | null = null;
  private pendingSinceMs = 0;
  private frozenSinceMs: number | null = null;

  constructor(options: BaselineTrackerOptions = {}) {
    this.smoothTauS = options.smoothTauS ?? 0.6154;
    this.baselineTauS = options.baselineTauS ?? 33.28;
    this.warmupMs = (options.warmupS ?? 5) * 1000;
    this.warmupTauS = options.warmupTauS ?? 1.0;
    this.debounceMs = (options.debounceS ?? 0.4) * 1000;
    this.spikeMargin = options.spikeMargin ?? 0.05;
    this.maxFreezeMs = options.maxFreezeMs ?? 120_000;
    this.thresholds = options.thresholds ?? DEFAULT_TIER_THRESHOLDS;
  }

  /**
   * Advance with one raw perturbation sample.
   * @param freeze true while a fused target is being held — the baseline must
   *               not learn a present (possibly still) person as "empty".
   */
  update(raw: number, nowMs: number, freeze: boolean): BaselineUpdate {
    const value = Number.isFinite(raw) && raw > 0 ? raw : 0;
    if (this.startMs === null) {
      this.startMs = nowMs;
      this.lastMs = nowMs;
      this.smoothed = value;
      this.baseline = value;
      return this.snapshot(nowMs);
    }
    const dtS = Math.min(MAX_DT_S, Math.max(0, (nowMs - this.lastMs) / 1000));
    this.lastMs = nowMs;
    this.smoothed += alphaFor(dtS, this.smoothTauS) * (value - this.smoothed);

    const warmingUp = nowMs - this.startMs < this.warmupMs;
    this.frozenSinceMs = freeze ? this.frozenSinceMs ?? nowMs : null;
    const frozen = freeze && !warmingUp && nowMs - (this.frozenSinceMs ?? nowMs) < this.maxFreezeMs;
    const isSpike = value > this.smoothed * (1 + this.spikeMargin);
    if (warmingUp) {
      this.baseline += alphaFor(dtS, this.warmupTauS) * (value - this.baseline);
    } else if (!frozen && !isSpike) {
      this.baseline += alphaFor(dtS, this.baselineTauS) * (value - this.baseline);
    }

    this.applyDebounce(this.classify(this.rise()), nowMs);
    return this.snapshot(nowMs);
  }

  private rise(): number {
    return this.baseline > EPS ? Math.max(0, this.smoothed / this.baseline - 1) : 0;
  }

  private classify(rise: number): PresenceTier {
    if (rise >= this.thresholds.active) return "active";
    if (rise >= this.thresholds.moving) return "present_moving";
    if (rise >= this.thresholds.still) return "present_still";
    return "absent";
  }

  private applyDebounce(candidate: PresenceTier, nowMs: number): void {
    if (candidate === this.tier) {
      this.pendingTier = null;
      return;
    }
    if (this.pendingTier !== candidate) {
      this.pendingTier = candidate;
      this.pendingSinceMs = nowMs;
      return;
    }
    if (nowMs - this.pendingSinceMs >= this.debounceMs) {
      this.tier = candidate;
      this.pendingTier = null;
    }
  }

  private snapshot(nowMs: number): BaselineUpdate {
    return {
      smoothed: this.smoothed,
      baseline: this.baseline,
      rise: this.rise(),
      tier: this.tier,
      warmingUp: this.startMs !== null && nowMs - this.startMs < this.warmupMs,
    };
  }
}

/**
 * Room-level presence: the strongest node tier, applied immediately on an
 * upgrade (a person entering must not lag) and held for `holdMs` after the
 * stronger evidence was last seen before downgrading (RuView ADR-297 room
 * debounce, 1.5 s).
 */
export class RoomPresence {
  private current: PresenceTier = "absent";
  private lastSupportedMs = 0;

  constructor(private readonly holdMs = 1500) {}

  update(nodeTiers: readonly PresenceTier[], nowMs: number): PresenceTier {
    const strongest = nodeTiers.reduce<PresenceTier>(
      (best, t) => (TIER_RANK[t] > TIER_RANK[best] ? t : best),
      "absent",
    );
    if (TIER_RANK[strongest] >= TIER_RANK[this.current]) {
      this.current = strongest;
      this.lastSupportedMs = nowMs;
    } else if (nowMs - this.lastSupportedMs >= this.holdMs) {
      this.current = strongest;
      this.lastSupportedMs = nowMs;
    }
    return this.current;
  }

  get tier(): PresenceTier {
    return this.current;
  }

  reset(): void {
    this.current = "absent";
    this.lastSupportedMs = 0;
  }
}
