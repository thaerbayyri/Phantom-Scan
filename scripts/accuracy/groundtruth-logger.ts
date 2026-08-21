/**
 * Minimal operator-keypress ground-truth logger for the accuracy harness.
 * Single purpose: timestamp present/absent/sync events to a CSV that
 * ground-truth-adapter.ts can parse. Timestamps are host Date.now() —
 * the same clock source run-accuracy-trial.ts's live-mode WS tap uses
 * (see system-state-adapter.ts's LiveCaptureResult doc).
 *
 * Usage:
 *   tsx scripts/accuracy/groundtruth-logger.ts --out=groundtruth/2026-08-12_S3.csv --subject=subject-1
 *
 * Keys:
 *   s  mark a sync event (press this the moment you also trigger the
 *      system-side sync — e.g. right as you start the live capture or the
 *      recording session)
 *   p  toggle present/absent (first press = subject enters sensing volume,
 *      second press = subject leaves)
 *   q  quit and save (auto-closes an open "present" interval)
 */
import * as fs from "fs";
import * as path from "path";
import * as readline from "readline";

function parseArgs(argv: string[]): Map<string, string> {
  const args = new Map<string, string>();
  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i];
    if (!key.startsWith("--")) continue;
    const eq = key.indexOf("=");
    if (eq >= 0) {
      args.set(key.slice(0, eq), key.slice(eq + 1));
      continue;
    }
    args.set(key, argv[i + 1] ?? "");
    i += 1;
  }
  return args;
}

const args = parseArgs(process.argv.slice(2));
const outPath = args.get("--out");
const subjectId = args.get("--subject") ?? "";

if (!outPath) {
  console.error(
    "Usage: tsx scripts/accuracy/groundtruth-logger.ts --out=<path.csv> [--subject=<id>]\n  Keys: [s] sync marker  [p] toggle present/absent  [q] quit and save",
  );
  process.exit(1);
}

const rows: string[] = ["t_start_ms,t_end_ms,label,subject_id"];
const startedAtMs = Date.now();
let presentStartMs: number | null = null;

function elapsedMs(): number {
  return Date.now() - startedAtMs;
}

function appendRow(tStartMs: number, tEndMs: number, label: string): void {
  rows.push(`${tStartMs},${tEndMs},${label},${subjectId}`);
}

function save(): void {
  fs.mkdirSync(path.dirname(path.resolve(outPath as string)), { recursive: true });
  fs.writeFileSync(path.resolve(outPath as string), rows.join("\n") + "\n", "utf-8");
}

function finish(): void {
  if (presentStartMs !== null) {
    const t = elapsedMs();
    appendRow(presentStartMs, t, "present");
    console.log(`[present END, auto-closed on quit] t=${t}ms`);
  }
  save();
  console.log(`Saved ${rows.length - 1} row(s) to ${outPath}`);
  process.exit(0);
}

console.log("Ground-truth keypress logger. Keys: [s] sync marker  [p] toggle present/absent  [q] quit and save");
console.log(`Writing to ${outPath}`);

readline.emitKeypressEvents(process.stdin);
if (process.stdin.isTTY) {
  process.stdin.setRawMode(true);
}
process.stdin.resume();

process.stdin.on("keypress", (_str: string, key: { name?: string; ctrl?: boolean } | undefined) => {
  if (!key) return;
  if (key.ctrl && key.name === "c") {
    finish();
    return;
  }

  switch (key.name) {
    case "s": {
      const t = elapsedMs();
      appendRow(t, t, "sync");
      console.log(`[sync] t=${t}ms`);
      save();
      break;
    }
    case "p": {
      const t = elapsedMs();
      if (presentStartMs === null) {
        presentStartMs = t;
        console.log(`[present START] t=${t}ms`);
      } else {
        appendRow(presentStartMs, t, "present");
        console.log(`[present END] t=${t}ms (interval ${presentStartMs}-${t}ms)`);
        presentStartMs = null;
        save();
      }
      break;
    }
    case "q":
      finish();
      break;
    default:
      break;
  }
});
