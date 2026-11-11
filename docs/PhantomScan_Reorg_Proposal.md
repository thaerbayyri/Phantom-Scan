# Phantom Scan — Reorganization Proposal (Phase 1 Audit)

**This is a proposal only. No files were moved to produce this report — every move below is
unexecuted.** Per the audit's own ground rules, any reorganization from this document would become
its own scoped follow-up session, executed one directory/category at a time with a full test-suite
re-run after each move — never as a single bulk operation.

Two reorganizations are worth proposing. A third candidate (consolidating the ~45 root-level
investigation reports) was considered and is presented with caveats rather than a firm
recommendation, because the cost/benefit is genuinely borderline — see below.

---

## Proposal 1: Merge `script/` into `scripts/` (naming inconsistency)

**Finding:** the repo has two top-level directories for tooling that differ only by pluralization:
`script/` (2 files: `build.ts`, `dev-full.cjs`) and `scripts/` (47 files: the accuracy harness,
Python capture/analysis tools, provisioning helpers, reporting module, etc.). There is no
functional reason for the split found during this audit — `script/` simply holds the two files
most central to the npm build/dev pipeline, while everything else landed in `scripts/`. This reads
as an organic accident (two directories created at different times) rather than an intentional
separation.

| current path | proposed path | references that would need updating |
|---|---|---|
| script/build.ts | scripts/build.ts | `package.json` → `"build": "tsx script/build.ts"` |
| script/dev-full.cjs | scripts/dev-full.cjs | `package.json` → `"dev": "node script/dev-full.cjs"` |

**Full reference list found:** only `package.json`'s two script entries reference these paths by
name (confirmed via grep across the whole repo for `script/build` and `script/dev-full`, and for
the bare directory name `script/` in any `.md` doc — no doc mentions its path either). No CI
workflow, no other script, no doc runbook references `script/` directly.

**Why this is worth doing:** it's a 2-file move with exactly 2 known reference updates, both in one
file (`package.json`), and it removes a genuinely confusing "which one is the real scripts folder"
question for anyone new to the repo. Low risk, low effort, clear benefit.

**What could break if done carelessly:** nothing beyond the two `package.json` script strings —
just confirm `npm run dev` and `npm run build` both still work after the move and the path edit.

---

## Proposal 2: Give `scripts/rf_validation/` a real reason to have an `__init__.py`, or drop it

**Finding:** this is a smaller, more surgical proposal that fell out of the cleanup-candidates
investigation rather than a structural reorg, but it belongs here because it's about internal
package structure, not deletion. `scripts/rf_validation/__init__.py` exists (a package docstring,
no code) but the three sibling scripts in that folder (`dual_target_analyzer.py`, `nlos_capture.py`,
`phase_sanitizer.py`) import each other directly by bare module name (e.g. `from phase_sanitizer
import PhaseSanitizer`), never via `rf_validation.phase_sanitizer` — so the package boundary the
`__init__.py` implies is never actually exercised.

**Two options, not a recommendation between them (your call):**
- **Option A (matches the Cleanup Candidates report):** delete `__init__.py`, since these are three
  independent CLI scripts that happen to share a folder, not a real Python package.
- **Option B (an actual reorg, if you want the package boundary to be real):** change the sibling
  scripts' imports to `from scripts.rf_validation.phase_sanitizer import PhaseSanitizer` (relative
  to repo root) so the `__init__.py` is doing real work. This would require editing the `import`
  line in `dual_target_analyzer.py` (its one cross-import), and would only matter if you intend to
  import this package from somewhere outside its own folder in the future.

No file move is proposed here either way — flagging the structural question, not a location change.

---

## Considered and NOT recommended as a firm proposal: consolidating root-level reports

**What was considered:** the repo root currently holds ~45 investigation/session `.md` reports
(`PhantomScan_*_Report.md`, `PhantomScan_*_Fix.md`, `SESSION_CHATLOG_*.md`, and similar) alongside
its `README.md` and config files. A tidier layout would group these under something like
`docs/reports/` or `docs/sessions/`, leaving the repo root to just README + config + the small
number of files that must live at root by tool convention (package.json, tsconfig.json, etc.).

**Why this is NOT a confident recommendation:**

1. **Reference volume makes this expensive to do safely.** Per the file map compiled in this
   audit, most of these ~45 reports are cross-referenced by 2-10 *other* reports each (e.g.
   `PHANTOM_SCAN_REMEDIATION_REPORT.md` is hyperlinked twice from `README.md` and cited by at least
   4 other reports; `REAL_TEST_REPORT.md` is referenced by 6+ documents). A move would require
   rewriting every one of those cross-references — plausibly 100+ individual link edits across ~45
   files — to avoid leaving broken relative paths behind. This audit did not enumerate every single
   link (that enumeration is itself a multi-hour task warranting its own session), so the "exact
   list of references to update" this format calls for cannot be produced responsibly here without
   either guessing or re-running the full cross-reference sweep per file.
2. **README.md itself has a curated "doc index" table** that links to a subset of these reports
   under explicit "Current/binding" vs. "Historical/archived" headings. Moving files would mean
   editing README's doc index anyway — which is arguably the more valuable fix (curating that
   index further) independent of whether the underlying files also move directory.
3. **A meaningful fraction of these files are already flagged as cleanup candidates** (see
   `PhantomScan_Cleanup_Candidates.md`) — moving files that might get deleted in the very next
   session is wasted churn. It's more efficient to resolve the cleanup-candidates confirmation
   first, then decide whether a location reorg is still worth doing for whatever remains.

**If you do want this later:** the lowest-risk version would be to move only the files README.md's
own doc index table already links to (a known, bounded set — README would need its links updated
either way), leave everything else in place, and treat the rest as a separate decision after the
cleanup-candidates pass. That would bound the "references to update" list to exactly README.md's
doc-index section, which is small and already enumerated in README itself.

---

## Nothing else proposed

No other reorganization was found worth proposing. Specifically checked and found already
reasonably organized: `client/src/` (standard Vite/React layout), `server/` (flat `lib/` + `auth/`
split matches its size), `docs/adr/` + `docs/research/` (clear purpose-based split), `tests/`
(flat, matches pytest/tsx-test discovery conventions), and `firmware/esp32-csi-node/` (standard
ESP-IDF project layout — not this audit's place to restructure regardless, since ESP-IDF's own
tooling expects `main/` and `components/` at fixed relative locations).
