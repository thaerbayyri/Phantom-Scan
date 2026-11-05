# 00 — Summary of the fix task (state at Gate 1: Wave 0 and Wave 1 done, stopped for approval)

**Asked.** Fix what the offline evaluation found, using what is useful from RuView, in guarded waves with approval gates; never change safety constants from one session of data; report negative results.

**Done (Wave 0 + Wave 1, no runtime detection behaviour changed).**
* **Baseline:** TS 407/407; Python full suite now runnable in a scratch venv outside the repo: 210 passed, count-CNN test 68.0 s (closes PS-EVAL-001).
* **Test hygiene (01):** the TS suite no longer writes to the real audit log; the live-server Python tests are opt-in; `scikit-learn` declared as an optional `train` extra.
* **Loader (02):** `phantom/dataset.py` tolerates and counts bad lines/frames, never truncates mixed widths, streams in chunks (peak 388 → 172 MB, bit-identical output), strict mode kept.
* **Recorders (03):** both recorders write the same compact JSON and header schema 2 (per-part start, geometry hash, operator-stated capture conditions, "node moved / room not empty" annotation); readers accept schema 1 and 2.
* **Evaluation tooling (04):** rank AUC with block-bootstrap CIs in TS; `--nodes`/`--window-ms`; session-blocked AUC, empty-vs-empty control (C4), always-absent control, abstentions as misses, `null` instead of `NaN`. **Result on our data: still no candidate meets the pre-registered criteria; all 15 fail C4.** Session-blocked CIs are much wider than window CIs (the earlier intervals were over-confident).
* **Docs (05):** frame-rate/cap and geometry statements corrected; capability figures labelled "[TO BE MEASURED]"; sweep of every claim in `results/doc-claims-audit.txt`; dated records left untouched.
* **Guard + licences (06):** the AI sidecar refuses the shipped presence head (‖w‖ 3.668 < bias 8.188 ⇒ p ≥ 0.989 for any unit-norm input); licence/provenance inventory (`06-licences.md`) flags MM-Fi (CC BY-NC 4.0) and `pose_v1.safetensors` (unverified provenance).
* **After Wave 1:** TS **418/418**, Python **250 passed + 5 opt-in skips**, F1/F2 3/3, AI-firewall 11/11 (filtered run, name pattern `F1|AI|advisory|firewall`; the whole file is 46 tests: see 09-WAVE3-addendum.md).

**Not claimed.** No improved detection: nothing in Wave 1 changes what the system detects. The answer from the evaluation stands: the data cannot support a calibrated presence score, mainly because empty recordings drift more than a person changes the signal, and the emptiness of those recordings is unverified.

**Needs your action before anything is committed.**
1. **PS-FIX-23:** my Wave 0 full-suite run executed the live-server tests against your running dashboard and left 6 files in `data/sessions/` plus 2 entries in the tracked `data/sessions/_index.json` (restore recipe in `80-issues-ledger.md`; nothing was deleted). Tests are opt-in now.
2. **PS-FIX-24/-26:** the model directory is a nested git repo with an untracked `pose_v1.safetensors` of unverified provenance, and MM-Fi is CC BY-NC: decide what may ship.
3. **Decisions I raised, not made:** PS-EVAL-010 (threshold 0.6 vs 0.05), PS-EVAL-013 (two nodes use the legacy gate), PS-EVAL-018 (stray `bash.exe.stackdump`, 4 files listed), CC BY-NC assets.

**Gate 1 — which Wave 2 items do you approve?** PS-FIX-07 frame-rate truth, -08 integrity guard in shadow mode, -09 fan/periodicity candidate (offline), -10 background-match prior (offline), -11 calibration tooling. All are analysis/shadow only; none changes the authoritative output.

## Wave 2 so far (after your addendum; details in `08-WAVE2-addendum.md`)

* **Session cleanup (PS-FIX-23): done and verified** (index hash = baseline; 5 files moved to `.tmp/quarantine-sessions-2026-11-03/`, nothing deleted).
* **A. Link-state epochs:** your s7 evidence reproduced independently (N1 −35 → −48 dBm at +193…195 s, fps 63 → 44, node 4 dip −71 dBm at +203 s; audit log has only start/stop). Per-node step detector, epochs and transitional exclusion built (s7: 125 windows kept, 17 transitional dropped). **Cause: unconfirmed.** Finding: **no epoch has both ≥ 2 empties and a walking or still recording**, and drift persists *inside* epoch E07 (N1 steady at −47 dBm, s8 vs s9).
* **B. Movement score** (labelled "not presence"): within an epoch the empty-vs-empty gate drops from 1.00 to 0.54–0.73 and walking-vs-empty is 0.61–0.78 against a single empty; across epochs it still fails; it fades for a still person (s10 0.31 → 0.08). Below the pre-registered criteria.
* **C. Recorder sidecar** (`<part>.summary.json`, first/last 10 s RSSI median and fps, step flag): done in both recorders with a shared parity test.
* **Tests:** TS 423/423, Python 305 passed + 5 opt-in skips (scratch venv), 290 + 7 skips in your own `.venv`; F1/F2 and AI-firewall green.
* ~~Not started: PS-FIX-07, -08 audit/guard, -09, -10, -11~~ — **superseded: see "Wave 2 complete" below.** PS-FIX-32 was confirmed by you (post hoc, with sensitivity).

## ملخص قصير بالعربية

* **ما تم (الموجة 0 و1):** لم يتغير أي سلوك كشف في وقت التشغيل. أصلحنا الاختبارات (لا كتابة في سجل التدقيق الحقيقي، واختبارات الخادم الحي أصبحت اختيارية)، وحسّنا `dataset loader` (يحسب الأسطر التالفة ولا يقصّ الأبعاد بصمت)، ووحّدنا صيغة المسجِّلين مع header schema 2، وقوّينا أدوات التقييم (فواصل ثقة block-bootstrap وضابط empty-vs-empty وضابط الحساسية)، وصحّحنا الوثائق (معدل الإطارات الفعلي 64–67 إطار/ث بدل 41–43، وهندسة 4 م)، وجرد التراخيص.
* **النتيجة:** ما زال **لا يوجد** مرشّح يحقق المعايير المسجَّلة مسبقًا؛ التسجيلات "الفارغة" تختلف عن بعضها أكثر مما يغيّره الشخص، ولا يمكن التحقق من أنها كانت فارغة فعلًا. لا نزعم تحسّنًا في الكشف.
* **تحذير يحتاج إجراءً منك:** تشغيلي للاختبارات الكاملة نفّذ اختبارات `live server` على الـ dashboard الشغّال لديك وترك 6 ملفات في `data/sessions/` وسجلّين في `_index.json` (لم أحذف شيئًا؛ طريقة الاستعادة في `80-issues-ledger.md`). الاختبارات اختيارية الآن.
* **قرارات تخصّك:** حدّ الحركة 0.6 مقابل 0.05، وبوابة الطاقة القديمة مع عقدتين، وأصول CC BY-NC (MM-Fi) و`pose_v1.safetensors` مجهول المصدر.
* **التالي:** وافق على عناصر الموجة 2 (تحليل وshadow فقط): PS-FIX-07 إلى -11.

---

## Wave 2 complete (your order: 08 → 07 → 11 → 09; 10 skipped; 15 deferred)

| item | outcome | report |
|--|--|--|
| decisions batch (walking-AUC gap closed, PS-FIX-32 sensitivity, PS-FIX-27 `PHANTOM_DATA_DIR`, PS-FIX-28 head norms) | done; the shipped presence head has AUC 0.48–0.56 vs empty on our data and stays refused | `09-DECISIONS.md` |
| **PS-FIX-08** header-offset audit + PHY guard | parsers match the firmware serializer (RSSI = int8 @17), proven with one hand-built frame in both test suites; guard runs in **shadow mode** (counts/logs, never drops). The header has no bandwidth/sig_mode/transmitter (PS-FIX-36); "guarded vs unguarded AUC" cannot be computed offline | `11-PS-FIX-08.md` |
| **PS-FIX-07** frame-rate truth | ~**65 fps/node ≈ 2 frames per 30 ms ping interval** (firmware comment says ~40 fps), irregular arrivals, **0 duplicate frames**; why two per ping is unobservable (PS-FIX-37) | `12-PS-FIX-07.md` |
| **PS-FIX-11** calibration tooling | live empty run < 60 min / fan < 5 min refuses to start; single runs no longer print "suggested" thresholds; `--evaluate` refuses on short soak, missing fan, pooled link states/days, drift. **On our recordings it refuses in every combination** (node 1 −36 → −47 dBm; drift sym. bound 0.68–0.91). Never writes settings | `13-PS-FIX-11.md` |
| **PS-FIX-09** fan/periodicity | **negative**: feature does not identify a fan (AUC 0.39–0.60, CIs include 0.5), empties separate from each other, a veto would cut walking AUC 0.74 → 0.37. Found that a 50 Hz resampling aliases the ping cadence to 16.7 Hz | `14-PS-FIX-09.md` |
| PS-FIX-10 | skipped (your decision) | — |

**Tests after Wave 2:** TS 444/444, `tsc` 0 errors, Python 342 passed + 5 opt-in skips (scratch venv), F1/F2 3/3, AI-firewall 46/46, `data/sessions` 730 and audit log 2250 unchanged.

**Still true:** nothing in Wave 2 improves detection. The data cannot support a calibrated presence score: empty recordings drift more than a person changes the signal, the emptiness of the empties is unverified, and no link-state epoch holds ≥ 2 empties plus a walking/still recording. What is needed is **new recordings** (protocol below), not more analysis.

**New-recording protocol that would unblock Gate 2 / Wave 3 (one link state, nothing moved):** ≥ 60 min empty (entry log kept) → 5 min fan alone → 5 min walking → 5 min still → another ≥ 60 min empty at the end, then a fan **with** a person; record via the dashboard recorder so the part sidecars and `capture` fields are filled; read the firmware serial counters once to answer PS-FIX-37.

**Gate 2 — your decisions:** (1) approve/decline each Wave 3 item (PS-FIX-12 rate-scaled timing, -13 PHY enforcement, -14 firmware robustness, -16 fail-closed outputs; -15 stays deferred); (2) PS-FIX-36 header schema v2 (firmware change); (3) PS-FIX-24/-26 licences; (4) PS-EVAL-010 / -013 constants and the legacy two-node gate; (5) edit the docs that still say "pick mean + k·sigma" (PS-FIX-38).

### ملخص الموجة 2 بالعربية
* **PS-FIX-08:** تأكدنا أن محلّلَي الترويسة (TS وPython) يقرآن RSSI من البايت الصحيح (int8 عند 17) باختبار بإطار مبني يدويًا؛ وأضفنا حارس PHY بوضع shadow فقط (يسجّل ولا يُسقط أي إطار). الترويسة لا تحمل bandwidth ولا sig_mode ولا عنوان المرسِل.
* **PS-FIX-07:** المعدل الفعلي ≈ **65 إطار/ث لكل عقدة ≈ إطاران لكل فاصل ping (30 ms)** وليس ~40؛ لا إطارات مكررة؛ سبب الإطارين غير قابل للرصد من الترويسة (يحتاج قراءة عدّادات الـ serial).
* **PS-FIX-11:** أداة المعايرة ترفض الآن أي تشغيل أقصر من 60 دقيقة (فارغ) أو 5 دقائق (مروحة)، ولا تطبع حدًّا مقترحًا من تشغيل واحد، وترفض عند drift أو خلط حالات الربط. على تسجيلاتنا الحالية **ترفض في كل الحالات**. لا تكتب أي إعداد.
* **PS-FIX-09:** نتيجة سلبية: ميزة الدورية الطيفية لا تميّز المروحة، والفارغ يختلف عن الفارغ، والـ veto يخفض AUC للمشي من 0.74 إلى 0.37. واكتشفنا أن إعادة التقطيع عند 50 Hz تُظهر خطًا وهميًا عند 16.7 Hz (alias لإيقاع الـ ping).
* **المطلوب منك:** قرارات الموجة 3 (PS-FIX-12/13/14/16)، وتسجيلات جديدة وفق البروتوكول أعلاه (فارغ ≥ 60 دقيقة، مروحة، مشي، سكون، مروحة مع شخص)، وبقية القرارات المذكورة في 00-summary.
