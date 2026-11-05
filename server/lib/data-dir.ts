/**
 * Base directory for ALL runtime data the server reads or writes (sessions, audit log, operator seed, runtime settings, datasets,
 * phase-test logs). Default is the repo-relative `data/`, exactly as before; set PHANTOM_DATA_DIR to point a throw-away server
 * (e.g. the opt-in e2e tests, see tests/e2e_guard.py) at its own directory so it can never write into an operator's data/sessions.
 *
 * Read when called: modules that compute a constant at import time (session store, runtime settings) see the variable as it was
 * when they were first loaded, as before. Narrower overrides (PHANTOM_AUDIT_DIR, PHANTOM_OPERATOR_SEED_PATH,
 * PHANTOM_PHASE_LOG_DIR) still take precedence over this base.
 */
import path from "path";

export function dataDir(...parts: string[]): string {
  return path.resolve(process.env.PHANTOM_DATA_DIR || "data", ...parts);
}
