# Handoff for a fresh session (written 2026-11-05)

Project: Phantom Scan. Lead Thaer Bayyari; supervisor Dr. Ahmad Al-Nawasrah; stakeholder JODDB. Branch `feat/two-node-radar-live-detection`, nothing pushed.

## State

* **HEAD `dbf2748`.** The 88b run is complete: 26 commits (`e3b87ca` … `4e0ea25`), every staged `--stat` identical to the expected one, final tree proven equal to the pre-commit tree (1,903 files). Then `f3aab82` PS-FIX-45 (`pose_v1` read only when `PHANTOM_AI_POSE` is on), `cfe9158` campaign code matches the frozen pre-registration (C2 interval, C1b/C2b separate claims, C7 report-only, 10 min fan-with-person), `dbf2748` reports.
* **Pre-registration frozen** in `e3b87ca` with every owner value (`reports/presence-eval-2026-11/PREREG-2026-11-recording-campaign.md`, no `[OWNER TO …]` left). `run_campaign.py` refuses to analyse unless it is committed and unmodified.
* **Suites at HEAD** (`.tmp/tools/run_suites.ps1 -Label X`, output in `.tmp/suite-output/X/`): TS 450/450, `tsc` 0 errors, Python 545 passed + 5 skipped (scratch venv `D:\WIFI csi\phanotm\_scratch_venv_fulltest`), F1/F2 3/3, AI firewall 46/46 whole and 11/11 filtered. Sessions guard PASS (738 files / 166 entries): `python .tmp/tools/sessions_guard.py check .tmp/tools/sessions-baseline-2026-11-05.json`.
* Full record: `reports/fix-2026-11/09-WAVE3-addendum.md` (sections 0–11), ledger `80-issues-ledger.md`, gate `89-merge-gate.md`, test output `90-test-report.md`.
* Uncommitted on purpose: this file, `.tmp/` (backup `.tmp/pre-wave3-backup`, runner `.tmp/commit-steps/`), the nested repo `ai model and densepose/model` (owner's; README modified, `pose_v1.safetensors` untracked), `data/` (owner's live data).

## Work order for the next session

1. **PS-FIX-42**: the exported PDF's "Confidence: NN.N %" is only the dominant-label share of frames. Relabel it "dominant-label share of frames" with the single-antenna caveat, or remove it. Check PDF, CSV, Arabic and English templates (`scripts/build_academic_reports.py`, server exporters).
2. **PS-FIX-45**: done (`f3aab82`). Nothing left except noting it in release text.
3. **Item E**: a `no_data` verdict. Conditions: backward compatible (an unknown enum value must never crash the client; add a client test); a test that the AI/advisory client cannot write `no_data`; re-run F1/F2 and the firewall tests; replay on real sessions in both directions with numbers; show the `websocket.ts` conflict with PS-FIX-27 and resolve it in a separate hunk.
4. **Item F**: firmware, host-tested only, Kconfig default OFF, never flashed.

Demoted or standing: Item G only when the owner plans to flash; PS-FIX-43 (20 Hz decimation) stays measured-not-changed; Gate 3 questions are in `10-PS-FIX-12-design.md`.

## Owner items (not for the agent to decide)

Arabic pitch sentence needs a native read; PS-EVAL-010 / -013 (threshold decisions); PS-FIX-26 provenance; nine commits (P, O1–O8) lack the `Co-Authored-By` trailer, so decide before any push whether to rewrite them; the real Wi-Fi PSK is still in git history until rotated or scrubbed (MEDIUM-1); the classifier replay used proxy inputs; the firmware `--no-reset` flag and COM mapping (COM8 = node 4, COM9 = node 2) are unverified.

* Security: an old Wi-Fi password exists in older git history (already on the remote). Rotate the router password after the campaign; this requires re-provisioning the nodes, so do it together with any firmware reflash. Do not rewrite history.

## Rules (all still in force)

* Hardware truth: two-node fused is primary; one Rx antenna per node; no AoA, pose or body shape; only 1-D on-axis energy balance. Keep `getLivePositionCaveat`, `canPresentLiveTargetPosition`, `canRenderConfidentHuman`.
* F1: AI/ML never writes the authoritative verdict. F2: the dashboard never writes upstream to nodes, serial or firmware. Re-run `tests/test_invariants.py::test_f1_*`, `test_f2_*` and the firewall tests after every relevant item.
* **No safety-constant changes:** presence threshold 0.6, room tiers 4/7/14, fallback 0.05.
* Honesty: `[TO BE MEASURED]`, `[UNVERIFIED]`; re-verify earlier claims; negative results are valid; give both failure directions with numbers.
* **Never touch the running dashboard or the owner's live data.** Server tests use port 5099 only; never bind 5000 or 5005 (the dashboard owns UDP 5005). Never write into `data/sessions/` (the diff-guard must PASS; new dashboard output such as `000000205`, `000000206`, `test_21_*` is never read or classified).
* **No flashing, no serial writes, no push, no deleting files without asking.**
* One item at a time; stop on the first red; full suites before and after each item; one commit per item with the attribution trailer.
* Tooling notes: autocrlf is on (blobs are LF); many repo files are CRLF, so edit them byte-safely; the GateGuard hook denies the first create/edit of a file until the four facts are stated, then the identical retry passes.
