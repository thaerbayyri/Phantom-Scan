/**
 * Shared reporting primitives for the accuracy harness (see build prompt
 * "Human Movement Detection Accuracy Harness" §4.4 / §6 A7). Every derived
 * accuracy metric in a report MUST be wrapped in a MetricValue so the report
 * can never carry a bare number with no evidence trail — status is always
 * MEASURED or TO_BE_MEASURED, never inferred from the value alone.
 */

export type MetricStatus = "MEASURED" | "TO_BE_MEASURED";

export interface MetricValue {
  value: number | null;
  status: MetricStatus;
  evidence: string;
}

export function measured(value: number, evidence: string): MetricValue {
  return { value, status: "MEASURED", evidence };
}

export function toBeMeasured(evidence: string): MetricValue {
  return { value: null, status: "TO_BE_MEASURED", evidence };
}

/** Throws if a MetricValue doesn't satisfy the {value,status,evidence} contract. */
export function assertMetricValueShape(metric: unknown, path: string): void {
  if (metric === null || typeof metric !== "object") {
    throw new Error(`${path} is not a MetricValue object`);
  }
  const rec = metric as Record<string, unknown>;
  if (rec.status !== "MEASURED" && rec.status !== "TO_BE_MEASURED") {
    throw new Error(`${path}.status must be MEASURED or TO_BE_MEASURED, got ${String(rec.status)}`);
  }
  if (!("value" in rec) || !("evidence" in rec)) {
    throw new Error(`${path} is missing value/evidence alongside status`);
  }
  if (typeof rec.evidence !== "string" || rec.evidence.length === 0) {
    throw new Error(`${path}.evidence must be a non-empty string`);
  }
  if (rec.status === "MEASURED" && typeof rec.value !== "number") {
    throw new Error(`${path}.value must be a number when status is MEASURED`);
  }
  if (rec.status === "TO_BE_MEASURED" && rec.value !== null) {
    throw new Error(`${path}.value must be null when status is TO_BE_MEASURED`);
  }
}
