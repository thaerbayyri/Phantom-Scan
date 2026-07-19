import test from "node:test";
import assert from "node:assert/strict";
import fs from "fs";
import os from "os";
import path from "path";
import { AuditLogger } from "../../server/audit/logger";

/**
 * B5 — log-injection: a crafted username/details field with adversarial
 * bytes (embedded newlines, raw JSON-breaking quotes, control characters,
 * a fake pre-formed JSONL record) must not corrupt the JSONL file
 * structure. server/audit/logger.ts uses JSON.stringify per record — this
 * proves that holds under adversarial input, rather than asserting it from
 * code inspection alone.
 */

test("AuditLogger: adversarial username/details content cannot break JSONL record structure", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "phantom-behtest-loginject-"));
  const logger = new AuditLogger(tempDir);

  const adversarialUsername = 'attacker\n{"event_type":"operator_bootstrap_success","success":true,"username":"forged"}\n';
  const adversarialDetails = {
    note: 'line1\nline2\r\n{"injected":"record"}',
    quote: 'value with "embedded quotes" and \\backslashes\\',
    control: "\x00\x01\x02control-chars",
    nested: { deep: ["a\nb", 'c"d'] },
  };

  await logger.log({
    event_type: "login_failure",
    success: false,
    username: adversarialUsername,
    details: adversarialDetails,
  });
  await logger.log({ event_type: "login_success", success: true, username: "legit-operator" });

  // Read the raw file directly — this is the actual on-disk defense the
  // canon relies on, not just the logger's own parser round-tripping.
  const logPath = path.join(tempDir, "audit-current.jsonl");
  const raw = fs.readFileSync(logPath, "utf-8");
  const lines = raw.split("\n").filter((l) => l.length > 0);

  // Exactly 2 log calls -> exactly 2 lines, regardless of how many
  // newlines were embedded in the adversarial content. If injection had
  // broken record boundaries, this would be >2.
  assert.equal(lines.length, 2, "embedded newlines in a field must not create extra JSONL lines");

  for (const line of lines) {
    assert.doesNotThrow(() => JSON.parse(line), `line must remain valid JSON: ${line.slice(0, 80)}...`);
  }

  const firstRecord = JSON.parse(lines[0]);
  assert.equal(firstRecord.username, adversarialUsername, "adversarial content must round-trip byte-for-byte through JSON escaping, not get truncated/corrupted");
  assert.equal(firstRecord.details.note, adversarialDetails.note);

  // Confirm the logger's own reader also sees exactly 2 well-formed records
  // (not 2 real + N phantom records from a "successful" injection).
  const result = await logger.list({ limit: 10, offset: 0 });
  assert.equal(result.total, 2);
  assert.equal(result.records.some((r) => r.username === "forged"), false, "the embedded fake record must never be parsed as a real, separate audit entry");
});
