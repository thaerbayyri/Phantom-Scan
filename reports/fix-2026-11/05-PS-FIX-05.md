# PS-FIX-05 — documentation truth (PS-EVAL-002, -003, -011, -012, -014 + claim sweep)

**Provenance.** 2026-11-02/03, HEAD `744ce43` (dirty tree). Footprint `results/footprint-05-PS-FIX-05.txt` (15 files + 1 file in a nested repo). Patch `patches/05-PS-FIX-05.patch` (16 file diffs). Backups `.tmp/fix-backups/05-PS-FIX-05/`. Sweep output `results/doc-claims-audit.txt`. Tests: `90-test-report.md`. All edits are exact-match replacements with asserted match counts; **CRLF/LF style of every file was preserved** (checked byte-wise); `README.md` (already dirty) changed 6 + 1 lines.

## What was wrong and what changed

| finding | evidence | change |
|--|--|--|
| **Frame rate / cap (PS-EVAL-002).** Docs said "50 Hz cap, ~41–43 pps" and "self-ping ~50 Hz". Committed firmware: send gate 10 ms (`CSI_MIN_SEND_INTERVAL_MS`), self-ping every 30 ms (`CSI_PING_INTERVAL_MS`), both in `firmware/esp32-csi-node/main/csi_ping_pure.h:25,29` since commit `428d3a5` (2026-10-18). Recordings: 64–67 frames/s per well-linked node, 45–60 on weaker links, bursty host receive time (`reports/presence-eval-2026-11/01-data-inventory.md`). | rewritten in `README.md` (3 places), `firmware/esp32-csi-node/README.md` (5), `generated_reports/Appendix.md` (3), `generated_reports/Section-1.2-…md`, `docs/system_architecture_methodology.md`, `JODDB_PHASE2_TECHNICAL_PROPOSAL.md` (3), `Phantom-Scan-Final-Project-Report-4Node.md` (2) and the report generator `scripts/build_academic_reports.py` (7 strings, still compiles). The old 41–43 pps figure is kept where it is a *measurement from a named earlier session*, now labelled "pre-2026-10-18 firmware". |
| **Open point I noticed:** the recorded 64–67 frames/s exceed the 33 Hz ping rate, so CSI frames also come from other traffic. Not asserted in any doc. | `csi_ping_pure.h`; 01-data-inventory | → PS-FIX-07 |
| **Geometry (PS-EVAL-014).** Docs describe a fixed 3 m baseline `(-1.5,0)/(+1.5,0)` citing `shared/schema.ts`; the committed geometry is a 4 m baseline (`DEFAULT_NODE_ANCHORS`, 4 × 6 m room; `config/room.json`). Both are real: 3 m was the original July rig. | `shared/schema.ts:394-401`, `config/room.json` | `JODDB…`, `DETECTION_REPORT.md`, `MEASUREMENT_PLAN.md` now say which is which and to use the distance actually measured |
| **`canRenderConfidentHuman` (PS-EVAL-011).** Does not exist; the real helpers are `canPresentTruthfulTarget`, `canPresentLiveTargetPosition`, `canPresentIllustrativeBody`, `canPresentVolumetricTarget`, `canPresentAxisMotionVector`. | grep over md/ts/tsx/py: the only hit is in `PhantomScan_HardwareReality_Alignment_Report.md:122`, a **dated report** | not edited (dated record); listed here and in the ledger |
| **Bandwidth 0.33 Hz (PS-EVAL-012).** Code: tracker τ = 0.6154 s ≈ 0.26 Hz. | `server/lib/node-baseline.ts:141` | no statement of 0.33 Hz exists in the repo (it lives in notes outside it): nothing to correct here |
| **October report "seven labelled recordings, no still/active" (PS-EVAL-003).** | `Phantom-Scan-Final-Project-Report-Oct2026.md:1027` and `REPORT-NOTES-Oct2026.md:36` are **outside the repo** (`D:\WIFI csi\documants\…`) | not edited; the files-vs-recordings correction stays on the ledger for Thaer |
| **Capability figures (through-wall, pose, jitter, accuracy, range) without a measurement.** | sweep: 3 pattern groups, hits by class below | status note "design goals, [TO BE MEASURED]; the two-node one-antenna rig has no pose or spatial-angle capability" added to `JODDB…`, `docs/SYSTEM_DESIGN_TECHNICAL_ARCHITECTURE.md`, `docs/PHANTOM_SCAN_PRELIMINARY_TECHNICAL_DELIVERABLE.md`; in that last file `✅ Up to 8 m through drywall/concrete` (an achieved-looking claim) became `[TO BE MEASURED]`, and two jitter lines were labelled as targets; `README.md` headline qualified; presenter note on the pitch title; `.agents/AGENTS.md` bullet qualified; `docs/WIFI_DENSEPOSE_INTEGRATION.md` sentence "literally 'see' human postures through walls" reworded as an unvalidated upstream claim; the firmware README's upstream "resolves 3D pose with <30 mm jitter" labelled as not a Phantom Scan capability |
| **RuView headline claims in upstream text** | `ai model and densepose/model/README.md` (82.3 %, 82.69 % PCK, through-wall, vitals) | banner added at the top: upstream text, figures not measured on our hardware/data, licences → `06-licences.md`. **That directory is a nested git repository** (gitlink, pinned `39a01a1`) that already had uncommitted README edits (earlier "100 % accuracy → [TO BE MEASURED]" corrections); my change is 2 added lines on top, recorded by hand in the footprint because the superproject guard cannot see inside a gitlink. |

## Sweep result (every hit listed in `results/doc-claims-audit.txt`)

| pattern group | dated/upstream records (not edited) | dated session/audit reports (not edited) | living docs/code after the edits |
|--|--|--|--|
| RuView headline figures (82.3 %, 92.9 %, PCK@20, 54K fps, <30 mm) | 9 | 2 | 9 — all already labelled target/[TO BE MEASURED] (jitter lines in the two design docs, now under the status note), a code comment stating "pose_v1 ~2.5 % PCK@20, never rendered" (honest), and the firmware-README tip (now labelled) |
| frame-rate cap (41–43 pps, 50 Hz cap) | 7 | 14 | 10 — my own corrective sentences quoting the old figure, plus **two firmware source comments** (`csi_collector.c:312`, `csi_filter_pure.h:12`, "50 Hz send gate") deliberately left: firmware source is outside this docs item (ledger PS-FIX-22) |
| capability figures (through-wall, range, accuracy %) | 76 | 16 | 39 — mostly literature citations and the through-wall *validation protocols* (`docs/RF_VALIDATION_PROTOCOL_DUAL_TARGET.md`, `scripts/rf_validation`), design statements now covered by the status notes, and an "8 m" UI scale comment in `distance-meter.tsx` |

Dated records (ADRs, research notes, `PhantomScan_*_Report*.md`, session/audit reports) were **not** rewritten: that would falsify history. Where an ADR or report states a stale figure, the living doc above it now carries the correction.

## Evidence

* Suites after the item: TS **418/418**; Python (scratch venv) **233 passed + 5 opt-in skips**; F1/F2 3/3; AI-firewall 11/11; `data/sessions` unchanged (735).
* Docs-only change plus strings in the report generator (`python -m py_compile scripts/build_academic_reports.py` passes; the generator itself was **not run**, so the regenerated DOCX output is `[UNVERIFIED]`).

Both failure directions: not applicable (no detection behaviour touched).

## Not done

* Files outside the repo (Oct 2026 report, notes, the `.docx` deliverables) — listed, not edited.
* The generated `.docx` files in `generated_reports/` still contain the old sentences until `scripts/build_academic_reports.py` is re-run (not run here).
* Firmware source comments (PS-FIX-22).
