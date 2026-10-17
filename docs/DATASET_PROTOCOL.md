# Training-data capture protocol

Per-room models (activity classifier, people-count CNN — `scripts/train/`) only
mean something if they are trained and evaluated on recordings made the way
this document describes. RuView's own findings: models do not transfer between
rooms or subjects, so capture **in the room you will deploy in**.

## Prerequisites

1. All 4 boards flashed with the source-MAC filter firmware and showing `active`
   in the dashboard (check `mac_skip > 0` on serial, ~30–50 fps per node).
2. `config/room.json` holds the real measured node positions.
3. Dashboard → **Training Data Capture** panel. Files are written to
   `data/datasets/<roomId>/…jsonl` (gitignored, local only).

## What to record

| Label | What happens during the recording | People |
|---|---|---|
| `empty` | Nobody in or near the room, door closed | 0 |
| `empty_fan` | Empty room with a fan / HVAC / curtain moving | 0 |
| `still` | One person stands or sits still at a different spot each take | 1 |
| `walking` | One person walks the whole room (corners, wall midpoints, centre) | 1 |
| `active` | One person moves vigorously (turning, reaching, sitting down/standing) | 1 |
| `two_people` | Two people moving independently | 2 |
| `three_people` | Optional | 3 |

* **5 minutes per label per session.** Use the 10 s countdown to leave the
  room / take position before frames are labelled.
* **At least 3 sessions on different days or times** (different RF conditions).
  Evaluation holds out whole sessions, so fewer than 3 sessions per label
  cannot be evaluated honestly.
* **At least 2 subjects** if available; use a different `subjectId` per person.
* Stay inside the labelled condition for the **entire** recording; a mislabeled
  second of walking in an `empty` file poisons the model. Stop and re-record
  instead.
* Do not touch the boards or router between takes of one session.

## Training

```
py -3.13 scripts/train/train_activity.py --room room1
py -3.13 scripts/train/train_count.py --room room1
```

Both scripts split by **recording/session** (never by frame), report the
confusion matrix against the deterministic baseline, and **refuse to write a
model** that does not beat the majority-class baseline and the deterministic
tiers on held-out sessions. Models land in `models/rooms/<roomId>/` and are
loaded by the AI sidecar when `PHANTOM_ROOM_ID=<roomId>` is set. They are
advisory only and never gate the deterministic target.
