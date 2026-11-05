import type { TargetState, VitalSigns } from "@shared/schema";

export type VitalsBadge = "NO TARGET" | "SIMULATED" | "CALIBRATING";

/**
 * Header badge for the Vital Signs card. Vitals are only meaningful while the
 * presence state machine vouches for a target, so "NO TARGET" always wins.
 * Demo (synthetic) vitals are scripted, never measured, and are flagged as
 * such; otherwise a visible target with no reading yet is "CALIBRATING".
 * Returns null when a real reading is on display (no badge needed).
 */
export function getVitalsBadge(
  targetState: TargetState | null | undefined,
  vitals: VitalSigns | null | undefined,
): VitalsBadge | null {
  if (!targetState?.target_visible) {
    return "NO TARGET";
  }
  if (targetState.source_mode === "synthetic") {
    return "SIMULATED";
  }
  const hasReading = (vitals?.heartRateBpm ?? 0) > 0;
  if (!vitals?.vitalsReliable && !hasReading) {
    return "CALIBRATING";
  }
  return null;
}
