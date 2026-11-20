# Feature test on the third-party reporafin ESP32 dataset (2026-11-20)

Question: do the project's 15 window features (30 Hz resampled, 1 s windows) and the per-room activity trainer
separate empty / still / walking on someone else's ESP32 data? If not, the problem is not only our recordings.

## Data and converter

* `data/datasets/external-esp32-csi-pipeline/dataset/` (github.com/reporafin/esp32-csi-pipeline, CC BY 4.0):
  3 sessions (room1_quiet, room1_noisy, room2_quiet) × empty / stationary / moving, 1 file each, 210-385 s each.
* Converter `phantom/external/reporafin.py` (tests `tests/test_external_reporafin.py`, 5 passed): 52 subcarrier
  amplitudes (6-58 without DC 32), time from the packet counter at the author's assumed 100 Hz, no RSSI (set to 0),
  `stationary` → `still`, `moving` → `walking`, `day` = session folder (so `group_by="day"` holds out whole sessions).

## Result: the unchanged trainer and export gate (`phantom.activity_train.train_activity`)

| Hold-out | Model balanced acc. | Motion heuristic | Majority | Shuffled-label null p95 | Verdict |
|---|---|---|---|---|---|
| per recording | 0.318 | 0.164 | 0.000 | 0.526 | REFUSED |
| per session/room | 0.377 | 0.265 | 0.278 | 0.510 | REFUSED |

Confusion, per session (rows true; empty / still / walking): empty 556 / 451 / 671; still 450 / 248 / 893;
walking 93 / 444 / 969. Windows: empty 1,678, still 1,591, walking 1,506. Reports in
`reports/external-2026-11/reporafin-by-recording/` and `reporafin-by-room/` (no model exported).

## Why: per-session level swamps the activity

Per-recording medians of the 1 s window features:

| Session | Label | temporal_variance | motion_band_power | 10 s std of mean amplitude |
|---|---|---|---|---|
| room1_noisy | empty | **31.95** | **1.30** | 8.06 |
| room1_noisy | walking | 22.79 | 0.85 | 5.10 |
| room1_noisy | still | 11.96 | 0.39 | 4.25 |
| room1_quiet | empty | 12.85 | 0.32 | 3.72 |
| room1_quiet | walking | 20.64 | 0.84 | 4.44 |
| room1_quiet | still | 2.53 | 0.05 | 1.93 |
| room2_quiet | empty | 7.00 | 0.17 | 2.62 |
| room2_quiet | walking | **1.41** | **0.04** | 1.29 |
| room2_quiet | still | 2.35 | 0.06 | 2.09 |

Within one session the order is sometimes sensible (room1_quiet: walking > empty > still), but across sessions the
absolute levels do not line up: the noisy-channel empty room "moves" more than any walking recording, and room2's
walking is the quietest file of all. A model on absolute variance/power cannot generalise across sessions; the same
happened with our own data (rate drops, different days).

## What this implies for Phantom Scan

1. The failure is **not only** our recordings: the current 15 absolute features over 1 s windows do not separate the
   three states across sessions even on clean third-party data.
2. Features must be **relative to the same session's empty baseline** (e.g. variance / empty-room variance), or the
   pipeline must calibrate per session, which our protocol already records (empty first, then activities).
3. Longer windows (5-10 s) and correlation/Doppler-type features are worth testing before more recordings.
4. Caveat: reporafin's own data quality is unverified (one file per class per session, timestamps assumed, the
   room2 `moving` file being the quietest is suspicious); conclusions are about our features, not their labels.

## Second test: ESP32-S3 HAR dataset (still vs walking), 2026-11-20

* `data/datasets/external-esp32s3-har-2025/` (huggingface.co/datasets/imPiglet/esp32s3-csi-har-2025, CC BY 4.0):
  80 CSVs (20 each sitting / standing / lying / walking), ESP32-S3, one board, one session (29 July 2025), ~19.9 Hz,
  192 subcarriers, 13-33 s each. Converter `phantom/external/esp32s3_har.py` (tests
  `tests/test_external_esp32s3_har.py`, 4 passed): sitting/standing/lying → `still`, walking → `walking`. No empty class.
* Same unchanged trainer and gate, held out by recording (80 groups): **passes the gate**.

| Model balanced acc. | Motion heuristic | Majority | Shuffled-label null p95 |
|---|---|---|---|
| **0.915** | 0.806 | 0.500 | 0.563 |

Confusion (rows true; still / walking): still 2391 / 265; walking 49 / 657. Model files in
`reports/external-2026-11/esp32s3-har-by-recording/` (a third-party room; not a Phantom Scan model).

Reading: with one consistent session (same board, same day, same rate), the 15 features separate still from walking
well (0.915, clearly above the motion rule and chance). Together with the reporafin result, this points to session
consistency (rate, channel, noise level, day) as the main problem, not the feature set itself. It is still one
session, so the score is optimistic and says nothing about empty vs still.

## Third test: session-relative features, 2026-11-20

Code: `phantom/session_norm.py` (tests `tests/test_session_norm.py`, 5 passed) divides the 10 scale-type features by
the median of the same session's empty-room calibration windows and subtracts it from RSSI; shape features stay.
Evaluation: `python -m scripts.eval.relative_features_eval {reporafin|train-ep2}` (logistic regression, balanced class
weights). The first 30 % of each session's empty recording is used **only** for calibration, never evaluated.

| Data | Hold-out | Absolute | Relative |
|---|---|---|---|
| reporafin, 3 sessions | leave one session out | 0.408 | **0.444** |
| train-ep2-2026-11, nodes 1, 2, 4 | leave one recording out (1 session) | 0.465 | 0.465 |

reporafin confusion (rows true; empty / still / walking): absolute empty 487 / 316 / 372, still 434 / 255 / 902,
walking 87 / 441 / 978; relative empty **944** / 73 / 158, still 667 / 593 / 331, walking 622 / 651 / **233**.

Reading:
* Relative features help only a little (+0.036) and change the errors: empty is found far more often (944 vs 487
  of 1,175), but walking collapses (233 vs 978 of 1,506). Not a fix on its own; three sessions with one file per class
  are also too few to learn a session-independent rule.
* On our own data there is one session (one day), so a per-session constant changes nothing after standardisation:
  identical 0.465. The idea can only be tested on our data after sessions 2 and 3 exist on other days.
* Not wired into the trainer or the sidecar. No model exported.
