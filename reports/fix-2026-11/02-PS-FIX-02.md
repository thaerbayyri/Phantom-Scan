# PS-FIX-02 — dataset loader hardening (PS-EVAL-004)

**Provenance.** 2026-11-02, branch `feat/two-node-radar-live-detection`, HEAD `744ce43` (dirty tree). Footprint: `results/footprint-02-PS-FIX-02.txt` (M `phantom/dataset.py`, A `tests/test_dataset_loader.py`). Patch: `patches/02-PS-FIX-02.patch`. Backup: `.tmp/fix-backups/02-PS-FIX-02/`. Test output: `90-test-report.md`.

## Change

`phantom/dataset.py` (was clean in git):

| before | after |
|--|--|
| raised `ValueError` on the first malformed line | **skips and counts** (`Recording.report: LoadReport`: `lines, frames, malformed_lines, bad_frames, modal_width, width_mismatch_frames`); `strict=True` raises as before |
| `int(obj["n"])`, `float(obj["rssi"])`: `KeyError`/`TypeError` on a frame with missing or odd fields | frames with unusable fields (non-int node, non-finite timestamp, empty/non-finite/non-numeric amplitudes) are counted as `bad_frames`; missing `rssi` → NaN |
| `width = min(len(v) …)`; **every** frame of the node silently truncated to the shortest one | the node's **most common width is kept; other-width frames are dropped and counted** (`width_mismatch_frames`), never truncated; `strict=True` raises on mixed widths |
| whole recording as Python `list[list[float]]` | rows converted to numpy in 4096-row chunks (`_CHUNK_ROWS`), same float64 `NodeStream` arrays |
| `sorted(paths)` (lexical: `part10` before `part2`) | numeric part order; header taken from the lowest part |
| header missing / schema ≠ 1 | unchanged: always raises (schema 2 handling is PS-FIX-03) |

`load_room_dataset(..., strict=False)` passes the flag through. `Recording` gained an optional trailing field `report` (default `None`), so hand-built recordings in existing tests still construct.

## Evidence

* **Tests:** `tests/test_dataset_loader.py` (11 tests): clean file/report, malformed and truncated-final lines counted, bad frames counted, missing RSSI → NaN, mixed widths never truncated (old behaviour would have cut 5 good frames to width 5), strict raises on every irregularity while the tolerant default still loads the same file, header/schema errors always raise, numeric part order, chunked ≡ single-chunk output, `load_room_dataset` strict pass-through. The existing `test_train_activity.py` and `test_count_model.py` (the loader's consumers) pass unchanged.
* **Real data cross-check:** on s6, s1-empty-18Oct (the spaced-JSON file) and s9 the new loader's per-node frame counts equal the independent evaluation loader's exactly, report `clean=True`, modal width 51 on every node.
* **Output identity:** on s9 (2 parts, 178,715 frames) the old and new loaders return **bit-identical arrays**.
* **Memory (tracemalloc peak, s9):** old **388 MB** → new **172 MB**; time 20.8 s → 18.6 s. (The remaining 172 MB is mostly the final float64 arrays; the loader still returns whole recordings, only the intermediate Python lists are gone. A true generator API was not added: no consumer needs it.)
* Suites: TS 407/407; Python 216 passed + 5 skipped (live-server tests, opt-in); F1/F2 3/3; AI-firewall 11/11.

Both failure directions: not applicable (offline loader; no detection behaviour touched). Training-input difference to be aware of: a recording that has mixed-width frames now trains on the modal-width frames instead of everything truncated to the shortest width; on the real `room1` recordings the report is clean, so no existing result changes.

## Not done

* Schema 2 headers (PS-FIX-03). A streaming generator API. The `Recording` float64 dtype was kept for compatibility.
