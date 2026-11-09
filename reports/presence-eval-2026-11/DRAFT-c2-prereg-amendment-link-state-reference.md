# Amendment to the recording-campaign pre-registration, for campaign c2 only

**Status: finalized by the owner's instruction and committed; applies to c2 only.** Drafted 2026-11-09 (evening, Asia/Amman).

**Sign line:** Owner instruction 2026-11-10 00:00 Amman to finalize; final text not re-read by the owner at signing; owner to read before the soak; may be amended before any c2 recording.

## Declarations (required wording)

1. **Made before any c2 recording.** No c2 block exists at the time of drafting. The only recordings in the new link-state epoch are two, and neither is a c2 block: a 10-minute empty-room reference (`data/datasets/epoch2-ref-2026-11/`, 22:16 to 22:26 Amman), taken to describe the epoch after the router change, and a 126-second `smoke-test` recording of 23:02 Amman (`data/datasets/smoke-test/`), made to check the recorder after the dashboard restart. No number from either was used to choose any value below.
2. **Not used to rescue c1.** c1 (`campaign_id c1-20261105`) is evaluated under the frozen `PREREG-2026-11-recording-campaign.md` exactly as written. Nothing here changes how c1 is validated, scored or reported; the c1 validator results (two between-block 6 dB failures, the aborted block 5 attempt, blocks 5 and 6 missing) stay as they are, and this amendment cannot make c1 pass. The values below (the whole-block rule, 3 h, 1 h, 54 fps, one re-record) are the owner's. The c1 numbers were known when they were chosen (the chronology is in A1); they are published there in full and are not used as a basis for anything.
3. **Scope.** c2 and later campaigns recorded in the link-state epoch that began with the router change of 2026-11-09 (channel 2 fixed, width 20 MHz, mode b/g/n mixed, password unchanged; ledger entry "campaign environment, 2026-11-09 evening"). No RSSI or rate comparison between c1 and c2 is made.

## A1. Link-state check between blocks (replaces the first-60-s reference)

**Convention (decided by the owner): the check fails at 6 dB or more and passes below 6 dB, the same convention as the frozen rule (`STEP_DB`).**

**One rule for every block, long or short: whole-block medians.**

| comparison | c1 (frozen) | c2 (this draft) |
|---|---|---|
| any block against the first block of its link state | the median RSSI of the **first 60 s** of the block against the first block (`REF_S = 60` in `scripts/presence_eval/campaign.py`); a node shift of 6 dB or more fails | not used in c2 |
| `empty_1` against `empty_2` (the two long blocks) | as above | the **whole-block median RSSI** of each, per node of `nodes_expected`; passes when the difference is **below 6 dB** on every node |
| `fan_alone`, `walking`, `still`, `fan_with_person` against the adjacent empty block | as above | the block's **whole-block median RSSI** against the **whole-block median of its adjacent empty block**, per node; passes when the difference is **below 6 dB** on every node |

Definitions (fixed here, before any c2 recording):
* **Adjacent empty block:** `empty_1` for `fan_alone`, `walking` and `still`; `empty_2` for `fan_with_person` (confirmed by the owner, 2026-11-10).
* **Median:** over all frames of the block, per node, from the untrimmed recording (the last-20-s trim of person blocks applies to the scoring windows only). **The medians are compared unrounded:** the median of an even number of values is the mean of the two middle values, and the difference is compared with 6 dB as computed (5.99 dB passes, 6.00 dB fails). Nothing is rounded to whole dB before the comparison.
* **The in-block gates are unchanged and apply to every block:** no held RSSI step of 6 dB or more inside a block, and the 0.7 frame-rate collapse gate, exactly as in c1.
* **A shift of 6 dB or more fails the block; it cannot inflate a result.** If a block's whole-block median RSSI differs from its adjacent empty block's by 6 dB or more on any node, the block fails this check as a link change, whatever the cause. A person (walking, still, or with the fan) can move a node's median, but so can the fan or the link alone: in c1, `fan_alone`, with no person in the room, moved node 4's whole-block median by 4 dB against `empty_1`. A failed block is invalid and is not analysed; the check uses RSSI only, is decided before any score is computed, and every failed attempt is reported.

### Failed blocks and re-recording: the frozen text, then the c2 wording

The frozen pre-registration (`PREREG-2026-11-recording-campaign.md`, section 2) says:

> A campaign (or a block) that fails any gate is **invalid and is not analysed**; a failed gate is a valid outcome and is reported, not worked around.
>
> Gate "RSSI step": "no held RSSI step ≥ 6 dB inside a block, and no ≥ 6 dB shift of a node's median between blocks of the same link state".
>
> Gate "epochs segmented": "every block names a `link_state_id`; a LINK CHANGE ends the block (stop, log, wait 2 min, new block); at least one link state contains all six block types".

and the recording data spec (`RECORDING-DATA-SPEC.md`, section 2) says:

> A block that contains a link change is invalid. The new block gets a new `link_state_id` unless the operator can show the level returned to its earlier value. Blocks are only compared inside one `link_state_id`; at least one link state must contain all six block types.

The frozen text sets **no limit on the number of attempts**, and it does **not say how an operator shows that "the level returned"**. Both are fixed below, before any c2 recording.

c2 wording, following the frozen text:
* A block that fails the A1 check is **invalid and is not analysed**, and the failure is reported (frozen: a failed gate is reported, not worked around).
* A re-recording is a **new block** (a new recorder file, after the 2-minute wait of the frozen LINK CHANGE rule). It keeps the failed block's `link_state_id` only if the operator shows that the level returned; in c2 that is shown by the A1 check passing for the new block (confirmed by the owner, 2026-11-10). Otherwise it gets a new `link_state_id`, as in the frozen text, and the campaign still needs one link state with all six block types.
* **At most one re-record per block type.** A second failure of the same block type ends c2 as **"link-state check not satisfied"**. All data is kept and reported; no rule is changed to rescue it.

### Chronology, and the c1 numbers (published for transparency; not a basis for the rule)

**Chronology.** The owner's values and the whole-block rule were chosen **after** the c1 numbers were known: the c1 whole-block medians, all within about 4 dB of each other, had already been reported before the rule was proposed. The c1 numbers are published here in full. The rule is **not used to rescue c1**, which is judged under the frozen rule exactly as written, under which it fails (two between-block 6 dB shifts against the first-60-s reference, an aborted block 5 attempt, no block 6). The protection against a rescue is that the numbers are published and that the rule is declared before any c2 recording, not the order of events. Block 5 was aborted and block 6 was never recorded, so `empty_1` against `empty_2` cannot be evaluated on c1.

Measured 2026-11-09 from the c1 recordings, nodes 1, 2 and 4 (node 3 excluded as in c1), true unrounded medians over all frames (every one of these medians happens to fall on a whole dB). Block 1: whole block N1 -29, N2 -26, N4 -45 dBm; first 5 min N1 -33, N2 -26, N4 -43 dBm. Blocks 2, 3 and 4 are 5 to 9 minutes long, so their first-5-min and whole-block medians are equal: block 2 N1 -28, N2 -28, N4 -49; block 3 N1 -30, N2 -25, N4 -46; block 4 N1 -27, N2 -27, N4 -46.

| c1 block against block 1 | c2 rule, whole-block reference: difference N1, N2, N4 | result (fail at 6 dB or more) | for comparison only, block 1's first-5-min median: difference N1, N2, N4 | result |
|---|---|---|---|---|
| 2 `fan_alone` | +1, -2, -4 (largest 4 dB) | pass | +5, -2, -6 (largest 6 dB, node 4) | **fail** |
| 3 `walking` | -1, +1, -1 (largest 1 dB) | pass | +3, +1, -3 (largest 3 dB) | pass |
| 4 `still` | +2, -1, -1 (largest 2 dB) | pass | +6, -1, -3 (largest 6 dB, node 1) | **fail** |

The choice of reference decides the outcome for c1 blocks 2 and 4: the whole-block reference passes blocks 2, 3 and 4; block 1's first-5-min median would fail blocks 2 and 4 at exactly 6 dB.

**Why the whole-block reference.** The owner's stated reason is estimator stability: the whole-block median of an empty block uses every frame (about 320,000 per node for an 80-minute block) against about 20,000 for its first 5 minutes, and the first minutes of a long empty block can sit away from its later level (c1 block 1, node 1: -33 dBm over the first 5 minutes, -29 dBm over the whole block).

## A2. Soak gate before the first c2 block

Immediately before the c2 session, the same evening, record one **soak**: an empty room in the c2 link state, **at least 3 hours**, fan off, door closed, every node in `nodes_expected` streaming. **One timing rule: c2 block 1 starts at most 1 hour after the soak ends, and no router, firmware, node placement or channel change occurs between the soak and c2 block 1; otherwise a new soak is needed.**

**Pass condition: all three of the following, for every analysed node, over the whole soak.**
1. **Rate:** the 60-second rolling median of the frame rate never falls below **0.7 x** that node's reference rate (the median rate of the soak's first 10 minutes), and the existing per-recording gates hold (at least 90 % frame coverage per node, median rate inside 20 to 100 fps).
2. **Level:** the median frame rate of the soak's first 10 minutes is **at least 54 fps** per node (0.8 x about 67 fps, the delivered rate seen in c1 and in the epoch-2 reference).
3. **RSSI:** no held RSSI step of 6 dB or more: the 60-second rolling median RSSI of a node never differs from that node's first-10-minute median RSSI by 6 dB or more.

**Report-only, not part of the pass condition:** the produced rate from `seq` and the `D+P` / `D` / `D?` / `P` labels from `scripts/presence_eval/seq_report.py` are reported for the soak and never decide the gate.

* **Why a rolling 60-second median and not the repo detector:** the repo detector compares each second with the preceding 30 seconds and is blind to a gradual slide (measured in c1, ledger PS-FIX-46). The 0.7 ratio is the existing pre-registered collapse ratio, unchanged.
* **Why 3 hours: an observation from two recordings (n = 2), not a derived period.** In the two c1 recordings in which two slides were recorded (block 5 attempt 1: deep slides, 0.52 to 0.56 of the reference; the 8 Nov recording: shallow dips, 0.85 to 0.87), the first slide began 33 and 26 minutes after the start and the two slides began 68 and 71 minutes apart; a third recording (block 1 attempt 4) had one slide at +40 minutes. With n = 2 **no stable schedule was established** (neither wall-clock nor elapsed-time alignment; ledger PS-FIX-46), so 3 hours is the owner's chosen minimum, long enough to span more than two such intervals if they recur, and not a prediction that they will.
* **If the soak fails:** no c2 block starts. The soak recording is kept, not deleted, and not scored; the cause is investigated and a new soak is recorded. **If it passes:** c2 blocks may start, within the timing rule above.
* The soak is not a block, is never scored, and is never used to set a threshold.

## Implementation work before any c2 recording (not started)

1. `scripts/presence_eval/campaign.py`: a link-state mode, **default off** so the frozen c1 behaviour is unchanged, that applies the A1 rule (whole-block medians, adjacent empty block, unrounded, fail at 6 dB or more) next to the unchanged in-block gates.
2. A read-only soak checker (new script) for A2: the rate, level and RSSI conditions, the timing rule (c2 block 1 starts at most 1 h after the soak ends; no router, firmware, node placement or channel change in between), and the report-only `seq_report` summary. It never writes under `data/`.
3. Tests: the link-state mode (each pair rule, the 5.99 / 6.00 dB boundary, an even-count median compared unrounded, a person-induced shift failing the block, default mode reproducing today's validator output unchanged) and the soak checker (each of the three conditions failing alone, a passing soak, the 1 h window and the change rule, the report-only labels not affecting the verdict).

## Not changed

Presence threshold 0.6, room tiers 4/7/14, fallback 0.05; criteria C1 to C7; the six-block list and durations; the analysis-window rule (last 20 s of person blocks); the 6 dB rule; the C4 empty-versus-empty bound; invariants F1 and F2.

## Open points

* **[OWNER TO CONFIRM]** the node set of c2 (`nodes_expected`). c1 used nodes 1, 2 and 4 after the node-3 amendment (`5f797e7`); this amendment does not say which nodes c2 uses, and the soak checker takes the node list as an argument.
