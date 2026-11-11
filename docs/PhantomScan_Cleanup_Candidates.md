# Phantom Scan — Cleanup Candidates (Phase 1 Audit)

**This is a read-only report. Nothing listed here has been deleted, moved, or edited.**
Every entry ends with "Recommend: candidate for removal, pending your confirmation" — that
confirmation is the gate for a follow-up session to act on any of it, one confirmed subset at a
time (the same pattern already used for the 12 stale `.jsonl` files discussed below).

Entries are grouped by category, matching `PhantomScan_Repository_File_Map.md`. Protected files
(ADRs, README, real hardware session recordings) are **never** listed here even if every check
came back empty — see that report for how those were handled instead.

---

## Frontend/GCS — unused shadcn/ui scaffold components (27 files)

**Group evidence:** this project scaffolds its component library from shadcn/ui, which generates
one file per primitive whether or not the app ends up using it. For each file below: grepped
`client/src` for any `from "@/components/ui/<name>"` import, and grepped every `.md` file in the
repo for the component/filename — both came back empty. **What this can't rule out:** a dynamic/
lazy `import()` built from a string, or a future page not yet written that will use it. None of
that was found, but a plain grep can't prove a negative for runtime-constructed import paths.

| path | purpose | checks performed |
|---|---|---|
| client/src/components/ui/alert-dialog.tsx | Radix AlertDialog wrapper | 0 importers in client/src; 0 doc mentions |
| client/src/components/ui/alert.tsx | cva-styled Alert banner | 0 importers; 0 doc mentions |
| client/src/components/ui/aspect-ratio.tsx | Radix AspectRatio wrapper | 0 importers; 0 doc mentions |
| client/src/components/ui/avatar.tsx | Radix Avatar wrapper | 0 importers; 0 doc mentions |
| client/src/components/ui/breadcrumb.tsx | Breadcrumb nav trail | 0 importers; 0 doc mentions |
| client/src/components/ui/calendar.tsx | react-day-picker Calendar | 0 importers; 0 doc mentions |
| client/src/components/ui/carousel.tsx | Embla-carousel wrapper | 0 importers; 0 doc mentions |
| client/src/components/ui/chart.tsx | Recharts theming wrapper | 0 importers; 0 doc mentions |
| client/src/components/ui/checkbox.tsx | Radix Checkbox wrapper | 0 importers; 0 doc mentions |
| client/src/components/ui/collapsible.tsx | Radix Collapsible wrapper | 0 importers; 0 doc mentions |
| client/src/components/ui/command.tsx | cmdk Command-palette wrapper | 0 importers (it imports ui/dialog itself, but nothing imports it); 0 doc mentions |
| client/src/components/ui/context-menu.tsx | Radix ContextMenu wrapper | 0 importers; 0 doc mentions |
| client/src/components/ui/drawer.tsx | vaul mobile bottom-sheet Drawer | 0 importers; 0 doc mentions |
| client/src/components/ui/dropdown-menu.tsx | Radix DropdownMenu wrapper | 0 importers; 0 doc mentions |
| client/src/components/ui/form.tsx | react-hook-form + Label form-field wrapper | 0 importers (imports ui/label itself, but nothing imports it); 0 doc mentions |
| client/src/components/ui/hover-card.tsx | Radix HoverCard wrapper | 0 importers; 0 doc mentions |
| client/src/components/ui/input-otp.tsx | input-otp OTP entry wrapper | 0 importers; 0 doc mentions |
| client/src/components/ui/menubar.tsx | Radix Menubar (desktop app menu) | 0 importers; 0 doc mentions |
| client/src/components/ui/navigation-menu.tsx | Radix NavigationMenu wrapper | 0 importers; 0 doc mentions |
| client/src/components/ui/pagination.tsx | Pagination nav built on Button variants | 0 importers; 0 doc mentions |
| client/src/components/ui/popover.tsx | Radix Popover wrapper | 0 importers; 0 doc mentions |
| client/src/components/ui/radio-group.tsx | Radix RadioGroup wrapper | 0 importers; 0 doc mentions |
| client/src/components/ui/resizable.tsx | react-resizable-panels wrapper (distinct from the actually-used resizable-wrapper.tsx) | 0 importers; 0 doc mentions |
| client/src/components/ui/scroll-area.tsx | Radix ScrollArea wrapper | 0 importers; 0 doc mentions |
| client/src/components/ui/select.tsx | Radix Select wrapper | 0 importers; 0 doc mentions |
| client/src/components/ui/table.tsx | Plain `<table>` styling primitives | 0 importers; 0 doc mentions |
| client/src/components/ui/tabs.tsx | Radix Tabs wrapper | 0 importers; 0 doc mentions |
| client/src/components/ui/textarea.tsx | Styled `<textarea>` primitive | 0 importers; 0 doc mentions |

**Recommend: candidates for removal, pending your confirmation** (as a batch, given the shared
shadcn-scaffold explanation — but confirm each one, since removing a UI primitive is easy to get
wrong if a page you don't remember writing depends on it).

## Frontend/GCS — two self-contained "dead clusters" (6 files)

**What this is:** these files DO have an importer each — but that importer is itself unreferenced
by anything else, so the whole cluster is dead together. Confirmed by grepping each filename
across `client/src` to find its only consumer, then confirming that consumer has no consumer of
its own.

| path | purpose | checks performed |
|---|---|---|
| client/src/components/ui/sidebar.tsx | Composite shadcn "app sidebar" block (cookie-persisted state, mobile detection) | 0 importers anywhere in client/src or docs — the cluster root |
| client/src/components/ui/separator.tsx | Radix Separator wrapper | Only imported by sidebar.tsx (dead) |
| client/src/components/ui/skeleton.tsx | Loading-placeholder pulse div | Only imported by sidebar.tsx (dead) |
| client/src/hooks/use-mobile.tsx | `useIsMobile()` hook (matchMedia 767px) | Only imported by sidebar.tsx (dead) |
| client/src/components/ui/toggle-group.tsx | Radix ToggleGroup wrapper | 0 importers anywhere — the second cluster root |
| client/src/components/ui/toggle.tsx | Radix Toggle wrapper | Only imported by toggle-group.tsx (dead) |

**What this can't rule out:** the same caveat as above (dynamic imports). **Recommend: candidates
for removal, pending your confirmation** — note that `sheet.tsx` and `tooltip.tsx` also happen to
be imported by sidebar.tsx, but both are independently used elsewhere (dashboard.tsx settings
sidebar, App.tsx TooltipProvider) — they are NOT part of this dead cluster and are not listed here.

## Frontend/GCS — other unreferenced files

| path | purpose | checks performed |
|---|---|---|
| client/public/favicon1.png | PNG image, purpose unclear beyond filename (a second favicon variant?) | Grepped `favicon1` across the whole repo (excluding node_modules) → 0 hits; git log shows it added in the same commit as favicon.png. Can't rule out a `<link>` href built dynamically, but none found |

**Recommend: candidate for removal, pending your confirmation.**

### Borderline — named only in prior audit-report docs, not in any functional runbook

Per the audit instructions, a file with one weak reference is included here rather than silently
promoted to "actively referenced." Both of the following show 0 code importers; their only
mentions are inside `PhantomScan_Component_Inventory_Report.md` and `generated_reports/Appendix.md`
— which are themselves prior *inventory listings*, not functional documentation that would explain
active use.

| path | purpose | weak evidence found |
|---|---|---|
| client/src/components/theme-toggle.tsx | Light/dark theme toggle button (imports ui/button) | Named only in the two inventory-listing docs above; 0 code importers |
| client/src/lib/complex.ts | Complex-number math helpers for CSI signal math (client-side) | Named only in the two inventory-listing docs above; 0 code importers |

**Recommend: candidates for removal, pending your confirmation** — flagged as borderline rather
than confident, since the docs mentioning them are themselves not authoritative on current usage.

---

## Backend/DSP (2 files)

| path | purpose | checks performed |
|---|---|---|
| server/storage.ts | `IStorage`/`MemStorage` — generic in-memory CRUD scaffold for a `User` entity | Grepped `storage` across all `.ts` files → only self-referencing hits and unrelated "session storage" hits in other files; grepped `MemStorage`/`IStorage` → only this file's own definitions. It IS described in `AUDIT.md`, `generated_reports/Appendix.md`, and the Component Inventory Report as "persistence for operator records," but no route/module actually imports it. Dynamic `require()`/string-built import paths can't be fully ruled out, but none found |
| server/terminal_router.py | FastAPI `APIRouter` duplicating the TS `/api/v1/system/execute-task` endpoint; its own trailing comment says "To mount this in your main.py" | Grepped `terminal_router` across the entire repo → only this file itself. No `main.py` exists anywhere in the repo (outside an unrelated vendored file) that could mount it via the commented-out `app.include_router(...)`. No CLI/`__main__` signal, no doc mention, not in `requirements-live-ai.txt`/CI. The equivalent functionality is already live in TS at `server/routes.ts`. Can't rule out an external FastAPI app outside this repo mounting it, but none exists here |

**Recommend: candidates for removal, pending your confirmation.**

---

## Scripts/tooling (1 file)

| path | purpose | checks performed |
|---|---|---|
| scripts/rf_validation/__init__.py | Package docstring describing the RF-validation test-infrastructure package (phase_sanitizer/nlos_capture/dual_target_analyzer) | Read in full — docstring only, no code/exports. Grepped `import rf_validation` / `from rf_validation` repo-wide → 0 hits; the sibling scripts in the same folder import each other directly by module name, not via this package, so the `__init__.py` is never actually executed as a package entry. No doc mentions of the filename beyond its own docstring content. Can't rule out ad hoc `sys.path`-based imports outside tracked files or manual REPL use |

**Recommend: candidate for removal, pending your confirmation.**

---

## Tests (1 file)

| path | purpose | checks performed |
|---|---|---|
| tests/test_occupancy.py | Standalone occupancy-counting validation script for `CSIFilterPipeline.count_occupancy`, meant to be run directly (`python tests/test_occupancy.py`) | Matches pytest's `test_*.py` naming pattern so `pytest tests/` attempts to collect it, but it contains zero `def test_*`/`class Test*` functions (only a `run_tests()` called under `if __name__ == "__main__"`). Confirmed via `pytest tests/test_occupancy.py --collect-only -q` → "no tests collected", and the full `pytest tests/ --collect-only` (92 tests total) contains none from this file. No invocation of it as a manual script found in `package.json`, docs, or CI config |

**Recommend: candidate for removal or conversion to real pytest functions, pending your
confirmation** — this one is different in kind from the others: it's not dead code, it's a script
that LOOKS like a test but isn't exercised as one. Converting its logic into real `test_`-prefixed
functions may be more valuable to you than deleting it outright.

---

## Docs and ADRs — non-ADR docs (10 files)

Reminder: **no ADR is listed here** — all 60 files under `docs/adr/` are unconditionally protected
regardless of reference checks (see the main file map for discrepancy flags on individual ADRs
instead).

| path | purpose | checks performed |
|---|---|---|
| docs/RF_VALIDATION_PROTOCOL_DUAL_TARGET.md | RF engineering test-report protocol (VTP-PS-002) for dual-target NLOS breathing-signature detection | Grepped the filename across all `.md` files and across code dirs (server/, client/, scripts/, phantom/, tests/, firmware main/) → 0 hits anywhere. Can't rule out a human test engineer running this protocol manually off-repo |
| docs/compass_artifact_wf-0e193497-a8dd-5b89-a41a-1e0afc5278ef_text_markdown.md | Byte-identical (line-ending differences only) duplicate of `docs/CNN-LSTM Deep Learning for Wi-Fi CSI Human.md`, which IS referenced | Grepped `compass_artifact` across all `.md` → 0 hits beyond its own first line; grepped across code dirs → 0 hits. Likely the original raw research-tool export before being cleaned up/renamed to the CNN-LSTM-titled sibling, which is fine to keep |
| docs/research/13-nv-diamond-neural-magnetometry.md | NV-diamond magnetometers for neural current detection ("Series 13/22") | Grepped filename across all `.md` and code dirs → 0 hits. Not listed in `docs/research/00-rf-topological-sensing-index.md`, whose own index caps at "Total Documents: 12" — so even the internal series index doesn't reach it |
| docs/research/21-sota-neural-decoding-landscape.md | SOTA neural-decoding landscape 2023-2026 ("Series 21/22") | Same checks as above → 0 hits; not in the 00-index |
| docs/research/22-brain-observatory-application-domains.md | Ten application domains for a "Brain State Observatory" ("Series 22/22") | Same checks as above → 0 hits; not in the 00-index |
| docs/research/remote-vital-sign-sensing-modalities.md | Snapshot of RF/radar/quantum modalities for remote vital-sign sensing beyond WiFi-DensePose | Grepped filename across all `.md` and code dirs → 0 hits |
| docs/research/ruview-multistatic-fidelity-sota-2026.md | RuView viewpoint-integrated fidelity enhancement design | Same checks → 0 hits |
| docs/research/ruvsense-multistatic-fidelity-architecture.md | "RuvSense" sensing-first RF mode design | Same checks → 0 hits |
| docs/research/wifi-sensing-ruvector-sota-2026.md | SOTA + 20-year projection for WiFi CSI sensing, vector-DB intelligence | Same checks → 0 hits |
| docs/security-audit-wasm-edge-vendor.md | Security audit (2026-03-03) of 29 `.rs` no_std WASM modules in a `crates/wifi-densepose-wasm-edge` tree | Grepped filename across all `.md` and code dirs → 0 hits. Additional note: the audited path itself (`rust-port/wifi-densepose-rs/crates/...`) doesn't exist anywhere in the current repo either — the audited component appears to have been abandoned/removed along with the rest of the Rust workspace (see the main file map's ADR discrepancy flags) |

**Recommend: candidates for removal, pending your confirmation.** For the 3 unindexed
`docs/research/` numbered docs (13, 21, 22), consider whether they were meant to be added to the
00-index and simply never were, rather than being truly abandoned — that's a judgment call only
you can make.

---

## Data — generated_reports/ (2 files)

Reminder: raw hardware recordings (`recordings/`, `data/sessions/`) are **never** listed here — see
the main file map's Protected section.

| path | purpose | checks performed |
|---|---|---|
| generated_reports/PhantomScan_FINAL -docunent - edited.docx | Appears to be a manually hand-edited variant of the final report (filename has a typo, "docunent") | Grepped "PhantomScan_FINAL" and "docunent - edited" across all `.md` → 0 hits outside its own filename. Not among the filenames `scripts/build_academic_reports.py` actually emits (Task-1..5, Chapter-6, Final-Phantom-Scan-Project-Report.docx only). Same commit as the batch of other report files, no distinguishing commit message. Can't rule out this being an off-repo manually-saved edit a human still needs to reference |
| generated_reports/how project detact the humen.docx | Informally-named DOCX (title suggests a plain-language "how the project detects humans" explainer) | Grepped "how project detact"/"detact the humen" across all `.md` → 0 hits. Not part of build_academic_reports.py's emitted filename set. No doc cross-reference found |

**Recommend: candidates for removal, pending your confirmation.**

---

## Root-level docs — investigation/session reports (12 files)

| path | purpose | checks performed |
|---|---|---|
| 2-node-esp32s3-run.md | Portable bring-up guide for 2×ESP32-S3 CSI sensing, mapped to Layers A-E | Grepped filename across all other `.md` files → 0 hits. Last modified 2026-07-08. Can't rule out informal/manual use by the operator outside version control |
| DISCONNECT_AND_STOP_SCAN_FIX.md | Fix write-up: ghost target on ESP32 disconnect + stop-scan quiesce/reconnect hardening | Grepped filename across all other `.md` → 0 hits. The file's own text says it was "written before this session's changes" — i.e. it's internally stale even beyond being unreferenced |
| HARDWARE_TEST_CHECKLIST.md | Blank operator sign-off template for a full two-node ESP32 hardware test session | Grepped filename across all other `.md` → 0 hits |
| INTEGRATION_NOTES.md | Marked HISTORICAL; describes Python `phantom/` as "Milestone 1 authority" for live ingest | Grepped filename across all other `.md` → 0 hits. Its own content directly contradicts the current, actively-maintained README/ADR-051 (Node/TS is now the sole authority) — stale in substance, not just unreferenced |
| JODDB_PHASE2_TECHNICAL_PROPOSAL.md | Phase-2 technical proposal for multi-node through-wall sensing, prepared for external (JODDB) review | Grepped filename across all other `.md` → 0 hits, despite this document itself citing many other reports. Recent (2026-08-21) and external-facing in purpose — flagging for your judgment rather than treating this as clearly abandoned |
| LIVE_HARDWARE_TEST_REPORT.md | Live two-board hardware test report (COM5/COM6, WP-16 tonal-aliasing firmware) | Grepped filename across all other `.md` → 0 hits |
| POSE_FRAME_COORDINATE_CHECKLIST.md | Blank manual-measurement checklist to prove `poseFrame.keypoints` coordinate frame vs `radialTarget` | Grepped filename across all other `.md` → 0 hits |
| PhantomScan_4Node_FusedRoom_Test_Report.md | Independent verification of the 4-node `fused_room` implementation; flags a geometry change needing sign-off | Grepped filename across all other `.md` → 0 hits. This is the single newest file in the repo (2026-08-25) — likely just too new to have been linked from anywhere yet, not necessarily abandoned |
| PhantomScan_Component_Inventory_Report.md | Full component map of the repo (server/client/phantom/firmware/scripts/shared/docs) | Grepped filename across all other `.md` → 0 hits. Ironic finding: this report's own content was cited as evidence throughout this very audit (e.g. for the stray root data files) — it clearly still has reference value even though nothing formally links to it |
| PhantomScan_Dashboard_Audit_Report.md | Full dashboard behavior audit (client hook → components, server broadcast, WebSocket reconnect) over a 10-min live replay | Grepped filename across all other `.md` → 0 hits |
| RUN_LOG.md | Marked HISTORICAL; staged run/test validation log with `[TO BE MEASURED]` placeholders | Grepped filename across all other `.md` → 0 hits |
| SESSION_CHATLOG_2026-08-07.md | Structured multi-phase summary of one Claude Code session (2026-08-06→07) | Grepped filename across all other `.md` → 0 hits. This file itself cites 7 other reports outward (FixAll, FollowUp, etc.), but none of those reports links back to it — it's a citation sink, never a citation target |

**Recommend: candidates for removal, pending your confirmation.** Given how many of these are
one-off investigation write-ups that already served their purpose (the bug they investigated is
resolved, or the report's substance was folded into `PHANTOM_SCAN_REMEDIATION_REPORT.md`), this
group is a reasonable one to review together — but `JODDB_PHASE2_TECHNICAL_PROPOSAL.md` and
`PhantomScan_4Node_FusedRoom_Test_Report.md` in particular look like they may still be
active/pending deliverables rather than dead weight; treat those two differently from the rest.

---

## Root-level stray data files (13 files)

### The 12 hash-named root `.jsonl` files

**Group evidence (applies to all 12):** all were committed together in the "Release v1.2.0"
commit (2026-07-20), which predates the repo's own `.gitignore` rule `/*.jsonl` (added later, with
an explanatory comment citing `PhantomScan_FollowUp_Session_Report.md`). `git check-ignore`/`git
ls-files` confirm they remain tracked despite the rule — pre-existing tracked files aren't
retroactively untracked by a later `.gitignore` addition. Grepped across `*.md,*.ts,*.py,*.json`
and did a full-text search for each exact 32-character hex hash — zero hits repo-wide, for every
one of the 12. Spot-checked 3 of the 12 directly: all are `record_type: session_header` CSI
recordings (`dsp_config.pipeline: deterministic_m1`, `expected_nodes: [1,2]`), i.e. legitimate
session data that landed in the wrong place (root instead of `data/sessions/`) rather than
corrupted output. `PhantomScan_Component_Inventory_Report.md` itself independently labels these
loose root `.jsonl` files as "ad hoc capture dumps from prior sessions," corroborating this from
inside the repo's own documentation. **What this can't rule out:** these could theoretically still
be referenced by a session identifier stored somewhere off-repo (a bug tracker, a chat log outside
this codebase) — but nothing inside the tracked repo points to them.

| path |
|---|
| 141f11c49ad744dc8556caa9c54e8b25.jsonl |
| 392bd31c585146b38986f8905b908f09.jsonl |
| 3b548879bb744ec1847eabba5181973b.jsonl |
| 5980adc5b08146f69628f2ff7f722bb1.jsonl |
| 84301822059245ab8e719bdd9718d536.jsonl |
| 8fac5164ee2b44bea3a3576d3493b1ee.jsonl |
| 97bb342f4077433fb98885ea48fe5353.jsonl |
| a0fdaac8ff8b428f94a9b41da67b2ba9.jsonl |
| c384453d98df4ba299ae7b7136a37b26.jsonl |
| d4f8c6debc0342b983582ac6dbebdb3a.jsonl |
| d716c90abe74491693f4c381674f9473.jsonl |
| dc05162149a1432d9a774e379b096ea8.jsonl |

**Recommend: candidates for removal, pending your confirmation** (this is the same class of file
as the "12 stale `.jsonl` files" your own prior sessions already established a precedent for
confirming-then-removing — these appear to be that same category, tracked separately here for a
fresh, independent confirmation rather than assuming the precedent already covered these exact 12).

### Other stray root files

| path | purpose | checks performed |
|---|---|---|
| dual_target_analysis.png | Plot artifact generated by `scripts/rf_validation/dual_target_analyzer.py` (its `output_dir` defaults to `'.'`, landing at repo root when run without `--output-dir`) | Confirmed the default-output-path behavior by reading the script (line ~727). Only "referenced" in the sense of appearing in `CURRENT_STATE.md`'s directory-tree dump, not consumed by any code/doc as an input. This is a generated artifact, not authored content |

**Recommend: candidate for removal (or relocation to a reports/output directory), pending your
confirmation.**

### Untracked stray files (outside git, checked for completeness per audit instructions)

These are **not part of the 1,682 git-tracked files** and technically outside this audit's formal
scope, but are the same class of stray capture dump as the items above, so they're surfaced here
rather than silently ignored:

| path | note |
|---|---|
| csi_recording_1775465108.csv | Untracked, gitignored via `*.csv`; 57 bytes — essentially an empty/failed capture |
| csi_recording_1779232555.csv | Untracked, gitignored via `*.csv`; confirmed exactly 0 bytes |
| test_capture.csv | Untracked, gitignored via `*.csv`; ~2.1 MB |

`PhantomScan_Component_Inventory_Report.md` already labels these as "ad hoc capture dumps." Since
they aren't git-tracked, deleting them has zero effect on repo history — this is closer to routine
disk cleanup than a repo change, but listed here since you may want to clear them in the same pass.

---

## Discrepancies flagged elsewhere (NOT cleanup candidates — do not act on these here)

For completeness, two items came up during this audit that are explicitly **not** in this cleanup
list because the hard-protection rules override any "unreferenced" finding:

- **`data/sessions/undefined.json`** — protected as historical record, but its filename and schema
  suggest a bug (a session ID resolving to JS `undefined`). See the main file map's Data section.
- **24 ADRs + 1 non-ADR security-audit doc** describing a Rust/Tauri/Expo workspace
  (`rust-port/`, `crates/`, `src-tauri/`) that doesn't exist anywhere in the repo. ADRs are
  unconditionally protected; see the main file map's Docs and ADRs section for the full list.

Both are flagged there for your review, not listed here, per the audit's explicit instruction not
to extend "no reference found" to anything in the hard-protections list.
