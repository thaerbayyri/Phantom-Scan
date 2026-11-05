# PS-FIX-06 — presence-head guard and licence inventory

**Provenance.** 2026-11-03, HEAD `744ce43` (dirty tree). Footprint `results/footprint-06-PS-FIX-06.txt` (M `scripts/ai_inference.py`; A `phantom/presence_guard.py`, `tests/test_presence_guard.py`). Patch `patches/06-PS-FIX-06.patch`. Backup `.tmp/fix-backups/06-PS-FIX-06/`. Licence deliverable: `06-licences.md`. Tests: `90-test-report.md`.

## Change

* **`phantom/presence_guard.py` (new, pure numpy):** `presence_head_check(weights, bias, input_norm=1.0)`. A logistic head can express both classes only if its logit range straddles 0; for inputs of norm ≤ R the logit lies in `[b − ‖w‖R, b + ‖w‖R]`, so the head is accepted iff `‖w‖·R > |b|` (**strict**; with R = 1 this is the requested `‖w‖ > |bias|`). Invalid heads (empty, non-finite, bad shape, bad `input_norm`) are refused, not crashed.
* **`scripts/ai_inference.py`:** the loaded head is only kept if the check passes (default R = 1). A refused head leaves `presence_prob = None` ("advisory presence unavailable"), prints the reason, and **changes nothing else**: no new message fields (the F1 tests scan this file's source for message types and the substring `aoa`; they still pass), nothing touches the authoritative verdict.
* **`tests/test_presence_guard.py` (17 tests):** the known-saturated shape (‖w‖ 3.67, bias 8.19 → refused, p_min ≥ 0.989); the mirror case (bias −8.19 → "always absent", refused); a healthy head accepted; the equality boundary refused; invalid inputs refused; the `input_norm` parameter; **the head actually shipped in the repo is refused with ‖w‖ = 3.668, bias = 8.188, p_min = 0.989**; a source-level wiring check that the sidecar assigns the head only inside `if head_check.ok:`; the guard module contains no verdict names.

## Evidence (before / after)

| | before | after |
|--|--|--|
| `PHANTOM_AI_PRESENCE_HEAD=1` with the shipped head | loaded; p(present) ≥ 0.989 for any unit-norm input (and the head's own docstring says it is uncalibrated) | **refused**; presence advisory is `None`; deterministic pipeline unaffected |
| Default (head disabled) | no presence evidence | unchanged |
| Python suite (scratch venv) | 233 passed + 5 opt-in skips | **250 passed + 5 skips** |
| TS suite; F1/F2; AI-firewall | 418/418; 3/3; 11/11 | 418/418; 3/3; 11/11 |

## Judgement call you should know about

The sidecar's own docstring says the head is meant to be applied to the **un-normalised** 128-d activation (‖pre‖ ≈ 15), where it "gives a full 0..1 spread" — a claim I could **not** verify here (no hardware/data run). With R = 15 the shipped numbers would pass (`test_input_norm_is_part_of_the_condition…` documents this). I applied the requested conservative R = 1, which refuses the shipped head. If a measured, calibrated spread on our own recordings is later demonstrated, the right change is to pass a measured `input_norm`, not to relax the check. Until then the head stays unavailable.

## Licences

`06-licences.md` lists every vendored model, weight, dataset and firmware component with size, hash, declared licence and provenance. Flags: **MM-Fi is CC BY-NC 4.0** (stated in `docs/adr/ADR-015-…:62`; the dataset and the upstream `ruvnet/wifi-densepose-mmfi-pose` model are *not* vendored here); the Wi-Pose dataset is "Research use"; **`pose_v1.safetensors` has unverified provenance and is untracked inside a nested git repository**; RuView's weights are labelled MIT by their own README but that says nothing about their training data. No licence was verified at its source (no web access used) and nothing was deleted.

Both failure directions: the guard only removes an advisory input that was saturated (cannot cause a ghost target or a miss in the authoritative path).
