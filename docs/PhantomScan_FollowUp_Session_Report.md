# Phantom Scan — Follow-Up Session Report

**Date:** 2026-08-07
**Scope:** Items A-D from the close-out task following `PhantomScan_FixAll_Session_Report.md`.
**Baseline before this session:** 189/189 TS, 86 pass + 1 skip Python — confirmed unchanged at session start.

---

## 1. Status table

| Item | Title | Status | One-line reason |
|---|---|---|---|
| A | PS-GAP-MUSIC-001 live-dashboard severity | **Done — reaches live display, proposal drafted, not applied** | `isarFrame` → `AoASpectrum` panel is on by default (`isarEnabled: true`); test-pin failure messages fixed to point at the defect instead of reading backwards |
| B | REAL_TEST_REPORT.md contradictory status | **Needs Thaer's decision — both options drafted, neither applied** | Contradiction re-confirmed live; no successor doc exists anywhere in the repo |
| C | ADR-058 foundation | **Confirmed solid — no mismatch found** | Every claim traces to its stated source with matching numbers; commit `920595d` verified on `origin/main` via fresh fetch |
| D | JSONL root-clutter fix | **Done — fixed, tested twice, verified clean** | Root cause was `output_dir=""` in one test file; fixed, plus a related finding (12 files are *tracked*, not untracked as previously assumed) flagged for a decision |

## 2. Item A — PS-GAP-MUSIC-001 severity: reaches the live display

**Trace, confirmed with certainty:**
`computeMUSICSpectrum` (`server/lib/signal-processing.ts`) → called at `server/lib/websocket.ts:830` inside `processFrame()`, gated only on `this.config.isarEnabled` (**default `true`**, `shared/schema.ts:136`) and `sampleBuffer.length >= arrayLength` (**default `16`**, `shared/schema.ts:137` — satisfied within under a second of streaming at the measured ~41-43 pps) → broadcast as `isarFrame` (`websocket.ts:845`) → `client/src/hooks/use-websocket.ts:302-305` stores it in React state → `client/src/pages/dashboard.tsx:175` renders `<AoASpectrum frame={isarFrame} .../>` → `client/src/components/dashboard/aoa-spectrum.tsx` plots the **full spectrum curve** (all bins) plus a **peak-angle marker** (red diamond) every frame, labeled "AoA Spectrum (MUSIC — derived)."

This is not behind a flag, not dormant, and not synthetic-only-by-configuration — it runs and renders under default settings for any operator watching the dashboard today.

**Severity is worse than originally scoped.** The prior finding (three clean plane-wave inputs at 0°/+30°/-30° collapsing to the identical peak) could be read as "single-source AoA is unreliable." Re-tested this session with production-realistic input — two **completely unrelated random N=16 buffers** (arbitrary magnitude/phase noise, not clean steering vectors, N=16 matching the live `arrayLength` default):

```
peakA { angle: 5, power: -9.05509561470928 } peakB { angle: 5, power: -9.05509561470928 }
max |power diff| across all 121 bins: 3.552713678800501e-15
```

The entire spectrum — not just the peak — is bit-for-bit frozen regardless of input. The panel redraws every frame (looks live) but its content is mathematically decoupled from the CSI stream. The existing code comment ("useful as a stable signal signature") undersells this: it implies imprecise-but-real signal correlation, when there is currently ~zero dependence on the input at all.

**Proposal (NOT applied — awaiting your go-ahead):** follow the existing `canPresentLiveTargetPosition`/`getLivePositionCaveat` pattern (`shared/target-presentation.ts`) rather than inventing a new one:

1. Add a permanent (not conditional — the defect is unconditional) caveat banner to `AoASpectrum`, replacing/augmenting the "(MUSIC — derived)" subtitle with something like **"KNOWN DEFECT — SPECTRUM NOT INPUT-DEPENDENT (PS-GAP-MUSIC-001)"**, styled consistently with the existing "ON-AXIS ESTIMATE — NOT ROOM POSITION" caveat treatment.
2. Specifically hide or grey out the **peak marker and angle readout** — that's the most actively misleading element (a confident-looking specific-angle number), more so than the curve shape itself.
3. Do not remove the panel — the curve may still carry latent research value once PS-GAP-MUSIC-001 is actually fixed (multi-snapshot/spatial-smoothing covariance), and an honest caveat is cheaper and more reversible than deleting the feature.

This is a UI-only change (no detection/gating logic touched), low risk, but I did not implement it per the explicit instruction to propose, not apply, pending your review.

**Test-pin message fix (applied):** the two `assert.equal` messages in `signal-processing.test.ts`'s PS-GAP-MUSIC-001 test fired their custom text on the *failure* path, but the original wording ("collapsed to the same angle") only made sense on the *success* path — worded backwards for the exact scenario it exists to handle (someone fixes MUSIC, the test starts failing). Reworded both messages to explicitly say the failure means the defect was fixed and the test should be updated/removed, not treated as a regression. Verified: `server/lib/signal-processing.test.ts` — 22/22 still pass.

## 3. Item B — REAL_TEST_REPORT.md: both options drafted, neither applied

**Re-confirmed the contradiction still holds:** `REAL_TEST_REPORT.md:1` still reads `> **HISTORICAL (superseded):** point-in-time record...`, while the file remains the only P0-S8 campaign structure in the repo. Searched fresh: no file matching `*campaign*` exists anywhere; the only other files mentioning "P0"/"S8"/"positional-fidelity campaign" are `PhantomScan_Research_Gap_Analysis.md` and `PhantomScan_FixAll_Session_Report.md` (both *about* this file, not replacements for it); `git log` shows the file's last real edit is still commit `10c6ef6` (2026-07-08), predating every ADR-05x fix session. Nothing has moved since the prior report.

**Option (a) — un-flag it as live** (minimal patch, ready to apply verbatim):

```diff
- > **HISTORICAL (superseded):** point-in-time record. Current runtime: the TS dashboard (`npm run dev`, :5000) is the sole UDP :5005 ingest — see README.md and RUN.md.
+ > **Live campaign plan.** Runtime context note (2026-08-07): the TS dashboard (`npm run dev`, :5000) is the sole UDP :5005 ingest — see README.md and RUN.md. This is a runtime-authority note only; the P0-S8 stage structure below remains the live positional-fidelity campaign plan.
```

**Option (b) — successor doc skeleton** (ready to save as `docs/POSITIONAL_FIDELITY_CAMPAIGN.md` if this path is chosen, carrying the P0-S8 structure forward with the runtime-authority language corrected at the source instead of patched around):

```markdown
# Positional-Fidelity Campaign (P0-S8)

> Supersedes REAL_TEST_REPORT.md as the live campaign plan. That file remains
> in the repo as the historical record of the pre-ADR-056/057/058 runtime
> and is not further updated.

Trial log for the two-node ESP32-S3 positional-fidelity campaign. One row per
real trial. Synthetic runs never go in this file.

Runtime context: the TS dashboard (`npm run dev`, :5000) is the sole UDP
:5005 ingest — see README.md and RUN.md.

[Carry forward baseline geometry, P0-S8 stage tables, Analysis Rules, and
Known Honest Limits sections verbatim from REAL_TEST_REPORT.md — omitted
here to avoid duplicating ~120 lines in a proposal; the source structure is
unchanged, only the framing/status header differs.]
```

**Recommendation (not a decision — yours to make):** option (a) is lower-risk (one-line change, zero duplication, no new file to keep in sync) and matches how the project already resolved an analogous "docs vs. shipped reality" conflict in ADR-051. I did not apply either.

## 4. Item C — ADR-058 foundation: confirmed solid, no mismatch

- `docs/research/csi-phase-in-wifi-sensing.md` read in full on current `main`. Every number ADR-058 attributes to it matches exactly: `phase_sanitizer.py`'s self-test correlation `>0.90` and SFO error `<0.01` rad, and the "firmware only does temporal unwrapping, not cross-subcarrier regression" claim.
- ADR-058's *other* claims (live-path conjugate-multiplication cancellation at `websocket.ts:802-804`; firmware output routed only to the Board DSP card, never fused) are correctly **not** attributed to the csi-phase doc — they're independently sourced from direct code re-verification and `PhantomScan_Research_Gap_Analysis.md` §2.1, exactly as ADR-058's own text states. No overclaiming.
- Line citations re-verified against current source, unchanged since ADR-058 was written: `edge_processing.c:469,666` (`unwrap_phase` calls) and `websocket.ts:802-804` (`h1_conj_h2 = mul(h1Proc, conj(h2Proc))`) — exact matches.
- Commit provenance: `git fetch origin main` (fresh) confirms `920595d` is an ancestor of `origin/main` (`9177ad3` merge → `920595d` → `ef184c4`), and `git show origin/main:docs/research/csi-phase-in-wifi-sensing.md` returns the expected content. The *local* `main` branch ref is stale (still points at an older `f2674de`, since this session works from a feature branch and local `main` was never fetched/fast-forwarded) — a local bookkeeping non-issue, not a problem with the actual remote repository.

**Conclusion: no patch needed to ADR-058.**

## 5. Item D — JSONL clutter: fixed, tested twice, one new finding flagged

**Root cause, confirmed exactly:** `tests/test_phantom_cross_node_correlation.py:53` passed `RuntimeConfig(output_dir="", ...)`. `phantom/recording.py`'s `Path("")` resolves to the process CWD, which is the repo root under a normal `pytest tests/` invocation. This was the *only* test file with this pattern — grepped all of `tests/*.py` for `RuntimeConfig(`/`JsonlSessionWriter`/`output_dir` and confirmed every other call site already uses `tmp_path`.

**Fix applied:** `_run_two_node_session` now takes `output_dir: Path` explicitly; its three callers (`test_cross_node_correlation_is_not_structurally_zero`, `test_correlated_motion_scores_higher_than_independent_motion`, `test_on_axis_position_uses_motion_energy_through_real_pipeline_wiring`) now accept pytest's `tmp_path` fixture and thread it through (the two-call test uses `tmp_path / "a"` and `tmp_path / "b"` so the two sessions don't collide).

**Double-run proof:**
```
=== run 1 === 3 passed in 2.70s — 0 new jsonl files in repo root
=== run 2 === 3 passed in 4.45s — 0 new jsonl files in repo root
```

**Stray-file cleanup — correction to the prior report's premise:** re-checked the files the prior report called "untracked stray files from 2026-07-23." `git ls-files "*.jsonl"` shows those **12 files are actually tracked in git**, added in commit `643f25a` ("Release v1.2.0: fix continuous moving-target tracking, chart colors, and threshold persistence" — an unrelated release commit, confirming they were an accidental byproduct, not deliberate fixtures; not referenced by name anywhere in the codebase). That's a materially different situation from "untracked clutter to delete" — removing tracked files is a repository-hygiene decision, not a cleanup of ephemeral output, so I did **not** `git rm` them. I did delete the 4 genuinely untracked `.jsonl` files this session's own (pre-fix) baseline run had created, which were unambiguous ephemeral test byproducts matching the exact bug just fixed.

**`.gitignore` update (applied):** added a root-anchored `/*.jsonl` rule (not a blanket `*.jsonl`, so `data/sessions/*.jsonl` — already covered by the existing `data/sessions/` rule — and any future legitimate nested `.jsonl` content stay unaffected). Confirmed before adding: neither `phantom/runtime.py` (defaults to `data/sessions`) nor `scripts/record-csi-udp.py` (defaults to `data/recordings`) intentionally targets the repo root.

## 6. Final test suite state (real output)

```
> npx tsx --test server/**/*.test.ts
ℹ tests 189
ℹ suites 0
ℹ pass 189
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0

> python -m pytest tests/
=========== 86 passed, 1 skipped, 7551 warnings in 78.07s (0:01:18) ===========
```

No regression from the prior session's exit state (189 TS / 86+1 skip Python — identical counts). The 1 pytest skip is the same pre-existing hardware-conditional `tests/test_esp_capture_e2e.py` recordings test as before. Confirmed zero new `.jsonl` files appeared in the repo root from this full-suite run (`git status --short | grep jsonl` → empty).

**F1/F2 explicit re-run (both suites, this session, after all Item A-D changes):**
```
> npx tsx --test server/lib/websocket.test.ts
ℹ tests 8
ℹ pass 8
ℹ fail 0

> python -m pytest tests/test_invariants.py -v
tests/test_invariants.py::test_dual_node_equal_balance_midpoint PASSED
tests/test_invariants.py::test_f1_ai_perturbations_do_not_change_deterministic_human_gate PASSED
tests/test_invariants.py::test_f1_ai_path_does_not_emit_authoritative_identity_or_aoa PASSED
tests/test_invariants.py::test_f2_dashboard_live_surface_has_no_upstream_hardware_controls PASSED
tests/test_invariants.py::test_runtime_scope_guard_has_no_flight_control_imports PASSED
============================== 5 passed in 0.16s ===============================
```

## 7. Decisions needed from Thaer

1. **Item A:** go-ahead (or not) to apply the proposed `AoASpectrum` honesty-caveat treatment (permanent defect banner + hide peak marker). Not applied.
2. **Item B:** pick option (a) un-flag `REAL_TEST_REPORT.md` in place, or option (b) create a successor doc. Neither applied.
3. **Item D (new, not in the original open-questions list):** the 12 tracked legacy `.jsonl` files from commit `643f25a` — confirm they should be `git rm`'d as accidental release-commit clutter, or if there's a reason to keep them.
4. **Carried over, still open, unchanged by this session:**
   - Open question 3 (prior report): is the MUSIC multi-snapshot covariance fix worth scheduling, especially now that Item A confirms it's live-visible, not just a documented limitation?
   - Open question 4 (prior report): hardware session sequencing (negative-control + spatial calibration together) — still pending, no hardware session has occurred.
   - Open question 2 (prior report) — **now resolved by Item C**: `docs/research/csi-phase-in-wifi-sensing.md`'s permanence is confirmed (it's on `origin/main`, commit `920595d`), and ADR-058's dependency on it is confirmed sound.
