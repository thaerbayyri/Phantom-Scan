/**
 * Test-runner setup (loaded with `tsx --import ./server/test-setup.ts --test ...`).
 *
 * The audit logger singleton (server/audit/logger.ts) reads PHANTOM_AUDIT_DIR when its module is
 * first loaded and otherwise appends to data/audit/audit-current.jsonl. Without this, running the
 * test suite writes auth events into the operator's real audit log (PS-EVAL-019). Each test process
 * gets its own temp directory, removed on exit. An explicit PHANTOM_AUDIT_DIR is respected.
 */
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

if (!process.env.PHANTOM_AUDIT_DIR) {
  const dir = mkdtempSync(path.join(tmpdir(), "phantom-audit-test-"));
  process.env.PHANTOM_AUDIT_DIR = dir;
  process.on("exit", () => {
    try {
      rmSync(dir, { recursive: true, force: true });
    } catch {
      /* best effort: a leftover temp directory is harmless */
    }
  });
}
