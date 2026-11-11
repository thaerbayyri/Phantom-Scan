# Phantom Scan 4-Node — How to Train the AI (Activity Model) and the CNN (People Count)

Written 18 Oct 2026 · branch `feat/two-node-radar-live-detection` · follows `PhantomScan_RuView_Port_Full_Report.md`

---

## 1. Where things stand

| Item | State |
|---|---|
| Training code (activity + count CNN) | Built, tested, committed |
| Recorder + dashboard "Training Data Capture" panel | Built, tested |
| **Recorded data** | **One file only:** `data/datasets/room1/room1__s1__walking__20261017T204650Z.jsonl` |
| Trained models | **None** (`models/` does not exist) |

With one `walking` recording, both trainers will refuse to run. That is correct behaviour, and it is the whole reason for this guide: **the work left is recording data, not writing code.**

The previous report (§7) showed the hand-made perturbation metric does not separate empty from occupied in this room. The models below learn from the raw per-subcarrier amplitudes instead, so they may succeed where the metric failed. That is not guaranteed. The trainers are built to say so honestly when it fails.

---

## 2. The two models

| | Activity model ("the AI") | People-count CNN |
|---|---|---|
| Question answered | empty / still / walking / active | 0 / 1 / 2-or-more people |
| Model | Logistic regression on 15 hand-built features | `CountNet`: 3 dilated Conv1d layers → mean over time → Linear |
| Input | 1 s window per node, 51 subcarriers (hop 0.5 s) | 40-frame window per node, 51 subcarriers (hop 20 frames) |
| Code | `phantom/features.py`, `activity_train.py`, `activity_model.py` | `phantom/count_model.py`, `count_train.py` |
| Output files | `models/rooms/<room>/activity.json` | `count.safetensors` + `count.json` |
| Needs | numpy + scikit-learn | + PyTorch + safetensors |
| Role | Advisory only, never gates the deterministic target | Same |

Labels map like this:

- Activity: `empty` and `empty_fan` → **empty**; `still`; `walking`; `active`. `two_people` and `three_people` are skipped by the activity model.
- Count: taken from the recording's `count` field, clipped to 0 / 1 / 2+. `empty` → 0; `still`, `walking`, `active` → 1; `two_people` → 2.

Both models treat each node's stream as a separate sample. Count predictions from the four nodes are fused at runtime by summing calibrated log-probabilities.

---

## 3. Recording the data (the part that matters)

Follow `docs/DATASET_PROTOCOL.md`. The dataset must come from **the room you will deploy in**; RuView found that models do not transfer between rooms or people.

### 3.1 Before you press record
1. All four boards on the MAC-filter firmware, all showing `active` in the dashboard.
2. Put the real measured node positions in `config/room.json`.
3. **Fix the frame rate first (see §6.1).** This is the biggest blocker found while reading the training code.
4. Set a room id (e.g. `room1`) and a subject id per person (`s1`, `s2`).
5. Do not move boards, router or furniture between takes of a session.

### 3.2 Recording plan (minimum viable)

| Label | People | What to do | Per session |
|---|---|---|---|
| `empty` | 0 | Everyone out, door closed | 5 min |
| `empty_fan` | 0 | Empty, fan / curtain / HVAC running | 5 min |
| `still` | 1 | Stand or sit still; **different spot each take** (4 corners + centre) | 5 min total |
| `walking` | 1 | Walk the whole room, corners, wall midpoints, centre | 5 min |
| `active` | 1 | Turn, reach, sit down / stand up | 5 min |
| `two_people` | 2 | Both move independently | 5 min |

- **3 sessions on different days or times of day.** The trainers hold out whole sessions, so fewer than three cannot be judged.
- **2 subjects** if you can; a different `subjectId` for each.
- Use the 10 s countdown to leave the room or take position before frames are labelled.
- **Never contaminate a recording.** One person walking past during `empty` poisons that file. Stop and re-record instead of trimming.
- Total effort: about 6 labels × 5 min × 3 sessions ≈ 90 min of recording.

### 3.3 Verify each recording
After each take check the file in `data/datasets/<room>/`:
- It has a header line and frame lines for **all four nodes** (`"n":1…4`).
- The frame count is plausible: 5 min × your real fps per node. A recording with 3,000 frames per node is healthy; 500 means a node was starving.
- Only the `walking` file exists today. Delete nothing; just add to it.

---

## 4. Training

### 4.1 One-time setup
Use the Python that has the dependencies (the notes in this repo say the vendored DOCX libs need 3.13; the training scripts need `torch`, `safetensors`, `scikit-learn`):

```
py -3.13 -m pip install -r requirements.txt
```

### 4.2 Run
```
py -3.13 scripts/train/train_activity.py --room room1
py -3.13 scripts/train/train_count.py    --room room1
```
Useful options: `--data-root`, `--models-root`, `--permutations` (null runs: 50 activity, 10 count), `--epochs` (count, default 25), and `--group-by recording|day` for the activity model.

Run `--group-by day` once you have ≥3 days. It is the stricter test: it asks whether the model survives a different day's RF conditions.

### 4.3 What the scripts do (so you can trust the result)
1. **Windowing.** Activity: 1 s windows, hop 0.5 s, windows with <16 frames skipped. Count: 40 frames, hop 20, windows spanning more than 3 s skipped.
2. **Grouped evaluation.** Test data is always a *whole recording* (or day), never random frames. Adjacent windows of one recording are near-duplicates, so a random split would report fantasy accuracy.
3. **Three yardsticks on the same held-out data:** majority class, a "motion-energy" decision tree (what a threshold can already do), and a shuffled-label null (whole-recording labels permuted).
4. **Export gate.** The model is written **only if** balanced accuracy beats the majority and the heuristic by ≥ 0.02 **and** beats the 95th percentile of the shuffled null. Otherwise `TrainingRefused` is raised and only `*.report.json` is written.
5. **Calibration (count).** Temperature fitted on out-of-fold logits; ECE before/after reported, so the shown confidence tracks real accuracy.

### 4.4 Data minimums enforced by the code

| Rule | Activity | Count |
|---|---|---|
| Recordings per class | ≥ 2 | ≥ 2 |
| Windows per class | ≥ 20 | ≥ 40 |
| Held-out groups | ≥ 3 | ≥ 3 recordings |
| Classes present | ≥ 2 | ≥ 2 |

These are floors for *running*, not for *good results*. Aim for the 3×6 plan above.

### 4.5 Reading the report
Open `models/rooms/<room>/activity.report.json` / `count.report.json`:
- `model_balanced_accuracy` vs `majority_…`, `heuristic_…`, `permutation_null_p95`.
- `confusion_matrix`: which classes get confused. Expect `still` vs `empty` to be the hardest pair, and `2+` vs `1` the hardest count pair.
- Count only: `temperature`, `ece_before`, `ece_after` (want `ece_after` well under ~0.1).
- `exported: true` means the model passed the gate.

**If it refuses:** that is information, not a bug. Do not lower `MARGIN`, `MIN_*` or remove baselines to force an export. Instead: record more sessions, fix contaminated or low-fps takes, then re-run.

---

## 5. Using the trained models
1. Models land in `models/rooms/<roomId>/`.
2. Start the AI sidecar with `PHANTOM_ROOM_ID=<roomId>` (plus `PHANTOM_AI_USERNAME` / `PHANTOM_AI_PASSWORD`) so it loads them.
3. Press **Calibrate Empty Room** before relying on the AI panel.
4. Predictions stay advisory. The deterministic tiers keep driving the target and position; the F1 invariant test guarantees the AI cannot change them.
5. **Retrain whenever the room changes** (moved furniture, node moved, new router channel) and treat accuracy as valid only for the recorded room and subjects.

---

## 6. Problems to fix or watch before/while training

### 6.1 Frame rate vs. the window rules (important)
The previous report measured **10–20 fps per node** (peaks 55). The trainers assume more:
- Activity requires ≥ 16 frames per 1 s window → at ~10–15 fps most windows are **silently skipped**, leaving too few windows to train.
- Count windows need 40 frames within 3 s (≥ ~13 fps); slower nodes yield **no windows at all**.
- The protocol itself assumes 30–50 fps.

Action: after recording the first file, count windows per node (a short `build_windows` / `build_count_windows` call shows it). If most are dropped, raise the frame rate first (isolate router vs. four boards sharing the channel, check the transmitter cadence), or deliberately retune `min_frames`, `WINDOW_FRAMES` and `MAX_WINDOW_SPAN_MS` together and keep them identical at train and serve time.

### 6.2 Label hygiene
The models learn exactly what the label says. Any wrong label is worse than no data. Keep the protocol's rule: stay in condition for the entire recording; if not, re-record.

### 6.3 Confounds to avoid
- Always record `empty` on every day. A model that sees `empty` only on day 1 and `walking` only on day 2 learns the *day*, not the person. The shuffled-null and by-day split guard against this, but only if the data allow it.
- Record `empty_fan`, otherwise any moving curtain reads as a person.
- Vary `still` position; otherwise "still at one spot" can be memorised.

### 6.4 Count CNN limits
- Classes are 0 / 1 / 2+. RuView's own count CNN reached only 62 %; expect modest accuracy and judge by the confusion matrix and ECE, not a headline number.
- The count label comes from the header (`count`), so a `two_people` take where one person leaves early silently mislabels frames.
- Only 51 subcarriers per node; recordings with a different width are skipped.

### 6.5 Small-data risk
Few recordings → each fold is 1–2 recordings → noisy scores. The permutation null exists for this reason. More sessions beat more epochs.

---

## 7. Suggested order of work
1. Restore a healthy frame rate (§6.1) and fill `config/room.json`.
2. Run the 5-minute empty-room calibration (`npx tsx scripts/calibrate-threshold.ts --seconds 300`).
3. Record **session 1** (all six labels). Run the trainers. Expect refusal; read the report to check windows per class.
4. Record **sessions 2 and 3** on other days/times (second subject if possible). Retrain with `--group-by recording`, then `--group-by day`.
5. Inspect the confusion matrices. If a model is exported, test it live with the sidecar and compare against the deterministic tiers.
6. If it still refuses with clean data, the raw 1-antenna ESP32 CSI may genuinely not carry the signal in this room; the next options would be better node placement, or more subjects and sessions — not threshold tuning.

---

## 8. Quick checklist

- [ ] 4 nodes active, filter firmware, healthy fps
- [ ] `config/room.json` real positions
- [ ] 6 labels × 5 min × ≥3 sessions (≥2 subjects)
- [ ] Each file verified (4 nodes, plausible frame count, clean label)
- [ ] `py -3.13 scripts/train/train_activity.py --room room1`
- [ ] `py -3.13 scripts/train/train_count.py --room room1`
- [ ] Reports read; model beats majority, heuristic and null; ECE acceptable
- [ ] `PHANTOM_ROOM_ID=room1` set; sidecar loads models; empty room calibrated
