import type { DemoStatus } from "@shared/schema";

export interface DemoBanner {
  readonly tone: "simulated" | "replay" | "error";
  readonly headline: string;
  readonly detail: string;
}

const REPLAY_CAVEAT =
  "The real detector decides what it sees from recorded data, so it may show no target.";

/**
 * Copy for the permanent demo banner. A demo is never a live measurement, so
 * the banner always says what it is: a scripted scene, or a recorded session
 * run through the real pipeline. Null when no demo is running (and no failure
 * to report).
 */
export function describeDemoBanner(status: DemoStatus | null | undefined): DemoBanner | null {
  if (!status) return null;

  if (status.phase === "error") {
    return {
      tone: "error",
      headline: "DEMO FAILED",
      detail: status.message ?? "The demo could not start.",
    };
  }
  if (!status.active || !status.mode) return null;

  if (status.mode === "synthetic") {
    return {
      tone: "simulated",
      headline: "DEMO - SIMULATED WALKER",
      detail: "A scripted scene, not a measurement. Nothing shown here comes from the sensors.",
    };
  }

  if (status.phase === "loading") {
    return {
      tone: "replay",
      headline: "DEMO - LOADING RECORDING",
      detail: "Reading the recorded session...",
    };
  }

  const clip = status.clip ?? "recording";
  const detail =
    status.phase === "calibrating"
      ? `Calibrating baselines on the recorded empty-room lead-in (${Math.round(status.positionS)}s). ${REPLAY_CAVEAT}`
      : `Replaying a recorded session, not live. ${REPLAY_CAVEAT}`;
  return { tone: "replay", headline: `DEMO - REPLAY: ${clip}`, detail };
}
