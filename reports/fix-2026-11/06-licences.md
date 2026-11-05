# 06 — Licences and provenance of vendored models, weights and datasets

**Provenance.** Inventory taken 2026-11-03 from the working tree (HEAD `744ce43`, dirty). File sizes and SHA-256 prefixes were computed locally (`sha256sum`). **No licence was verified at its source: this session fetched nothing from the web.** Every "declared licence" below is what the repo's own files say (README front matter, ADR text, licence files). Anything not stated in the repo is `[UNVERIFIED]`. **Nothing was deleted, moved or edited because of this inventory.** This is a technical inventory, not legal advice: a commercial or government deliverable needs a legal review of the rows flagged below.

## Summary of flags

| flag | item | why it matters |
|--|--|--|
| **CC BY-NC 4.0 (non-commercial)** | **MM-Fi dataset** (not vendored; referenced as the primary training set in `docs/adr/ADR-015-public-dataset-training-strategy.md:62`, "**License:** CC BY-NC 4.0", and line 161 "compatible with research and internal use") and anything trained on it, notably the separate upstream model `ruvnet/wifi-densepose-mmfi-pose` (linked from the model README; **not present in this repo**) | non-commercial terms propagate to what you can claim about weights trained on it; not usable in a commercial/government deliverable without a legal ruling |
| **"Research use" (not an open licence)** | **Wi-Pose dataset** (not vendored; ADR-015:80 "License: Research use") | no clear right to redistribute or use commercially |
| **Provenance unknown → treat as potentially restricted** | `pose_v1.safetensors` (507,032 B) | the shipped README does not say what data it was trained on (it calls it a "camera-free pose" model at 2.5 % PCK@20); whether it derives from MM-Fi is **unverified**. It is also **untracked inside the nested model repo** (not part of the pinned commit `39a01a1`), so its origin cannot be reconstructed from git. The sidecar loads it (`scripts/ai_inference.py`, `POSE_WEIGHTS`) but never renders its output. |
| **Model licence ≠ training-data licence** | all RuView weights below ("MIT" per README front matter) | an MIT label on weights says nothing about the licence of the data they were trained on; for the encoder the README says the data were RuView's own local capture (not shipped), which is not a public-dataset concern |
| **Human-subject data** | `data/datasets/room1/` (our own recordings, 25 files, 1.6 GB, gitignored) | personal data of volunteers; consent records are not in the repo `[UNVERIFIED]` |

## A. `ai model and densepose/model/` — nested git repository

* It is a **nested repository** (gitlink `160000`, pinned `39a01a1`; `origin` = `https://huggingface.co/ruvnet/wifi-densepose-pretrained`), so the superproject does not track its files. It already contained uncommitted README edits and the untracked `pose_v1.safetensors` before this task.
* Declared licence: README front matter `license: mit`; README line "**License**: MIT". Source of the README: RuView (`github.com/ruvnet/RuView`, `huggingface.co/ruv/ruview` per its own text). `[UNVERIFIED at source]`.

| file | size (B) | sha256[:16] | what it is | declared licence | provenance / concern |
|--|--|--|--|--|--|
| `csi-embed-v2.safetensors` | 39,672 | `183c988b918abad3` | 8→64→128 contrastive CSI encoder (v2) | MIT (README) | README: trained on RuView's own capture `overnight-1775217646.csi.jsonl`, 6,063 feature frames, one room, two nodes (data not shipped); metrics are RuView's, not ours |
| `csi-embed-v2-int4.bin` | 4,672 | `59b7f030fac2b291` | 4-bit quantised encoder + input standardiser (fp16 mean/std) | MIT (README) | same |
| `csi-embed-v2.py`, `csi-embed-v2-metrics.json` | 1,152 / 763 | `1422906680889591` / `45b1f892332efb16` | model definition / RuView's metrics | MIT (README) | the "82.3 %" is RuView's held-out triplet accuracy, **not** a presence accuracy and not measured on our data |
| `model.safetensors` | 48,840 | `d85fbc9e839908de` | v1 encoder/LoRA container (`config.json`: sona-lora, 60,630 frames) | MIT (README) | RuView capture, not ours |
| `model-q2.bin`, `model-q4.bin`, `model-q8.bin` | 4,096 / 8,192 / 16,384 | `1ebcafeb2d05c21f`, `4c97dd3696f72438`, `7c1356de682be372` | quantised variants | MIT (README) | same |
| `model.rvf.jsonl`, `config.json`, `training-metrics.json` | 695 / 617 / 3,343 | `aa4e3ccb8f6eeab6`, `f6db7921c63985b7`, `7c97a01657579031` | RuView container/config/metrics | MIT (README) | same |
| `node-1.json`, `node-2.json` | 21,697 / 21,660 | `ac15b2768322f090`, `8e0b54bbd190a6ef` | LoRA rank-4 **room adapters trained for other rooms** | MIT (README) | not valid for our rooms; opt-in only in the sidecar |
| `presence-head.json` | 2,619 | `9a6ddce665dbc173` | logistic presence head, 128 weights | MIT (README) | **saturated: ‖w‖ = 3.668 < bias = 8.188 ⇒ p(present) ≥ 0.989 for any unit-norm input** (RuView issue #1521 shape). The sidecar now **refuses** it (PS-FIX-06; `phantom/presence_guard.py`) |
| **`pose_v1.safetensors`** | 507,032 | `eb249b9a6b2e1013` | pose network (56→34 outputs), ~2.5 % PCK@20 per README | **not stated** | **provenance unverified; untracked in the nested repo — see flags above** |
| `README.md`, `.gitattributes` | 10,427 | — | upstream text | MIT (README) | contains RuView's own accuracy/pose/vitals/through-wall claims; a Phantom Scan banner was added (PS-FIX-05) |

## B. `ai model and densepose/wifi_densepose/`

`__init__.py` only: a docstring-level package stub ("WiFi-DensePose — WiFi-based human pose estimation using CSI data"). No licence file in the directory; origin `[UNVERIFIED]`.

## C. Datasets

| item | where | licence / status |
|--|--|--|
| Our recordings `data/datasets/room1/` (25 files, 14 recordings, subjects s1–s10, 17–27 Oct 2026) | local, **gitignored** (`.gitignore:31`) | ours; contains human-subject data; consent record `[UNVERIFIED]`; never commit |
| `data/sessions/`, `data/audit/`, `recordings/` | local, gitignored | ours; session CSV/PDF and audit logs (may contain operator names/IPs) |
| `models/rooms/` | absent here (gitignored, `.gitignore:32`) | would hold models we train from our recordings; none exist (the training tests refuse export without honest baselines) |
| **MM-Fi** | **not vendored** | **CC BY-NC 4.0** (ADR-015:62) — flagged |
| **Wi-Pose** | **not vendored** | "Research use" (ADR-015:80) — flagged |

## D. Firmware third-party components (`firmware/esp32-csi-node/managed_components/`)

| component | licence file | licence |
|--|--|--|
| `espressif__esp_lcd_touch` | `license.txt` | Apache-2.0 |
| `espressif__esp_lcd_touch_cst816s` | `license.txt` | Apache-2.0 |
| `lvgl__lvgl` | `LICENCE.txt` | MIT |

No 3D/model/font/image binaries were found under `client/`; no other `.safetensors/.bin/.onnx/.npz/.pt/.glb` files exist in tracked or untracked-non-ignored paths outside the nested model repo.

## E. What to decide (not done here)

1. Whether `pose_v1.safetensors` may stay in any deliverable until its training data is identified (recommended: treat as restricted until proven otherwise; keep out of the commercial/government package).
2. Whether to keep RuView weights at all in the deliverable: none of them has been validated on our hardware or data, the presence head is unusable, and the LoRA adapters belong to other rooms. They are advisory-only (F1) and optional.
3. Obtain the licence text of the upstream repo(s) at source (`huggingface.co/ruvnet/wifi-densepose-pretrained`, `github.com/ruvnet/RuView`) and ask the upstream author for the training-data provenance of `pose_v1`.
4. Confirm volunteer consent and a data-retention rule for `data/datasets`.
