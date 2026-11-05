## Link-state epochs for N1+N2

Cause of every change: **unconfirmed** (the audit log has only recording start/stop).

| boundary (UTC) | reason |
|--|--|
| 2026-10-18 17:30:55 | new calendar day |
| 2026-10-25 19:58:35 | new calendar day |
| 2026-10-25 20:12:09 | N1 gap_step -12 dB (-33 -> -45 dBm) fps 62 -> 42 |
| 2026-10-27 19:36:10 | new calendar day |
| 2026-10-27 19:48:50 | N1 rssi_step -12 dB (-35 -> -48 dBm) fps 63 -> 44 |
| 2026-10-27 19:53:56 | N1 gap_collapse fps 61 -> 41 |
| 2026-10-27 21:21:08 | N1 gap_step +8 dB (-47 -> -39 dBm) fps 38 -> 66 |

### Detected events (all nodes; `boundary` = used to split)

| recording | label | event | at | held s | persistent | boundary |
|--|--|--|--|--|--|--|
| s1__two_people__2026101 | two_people | N1 rssi_step +9 dB (-39→-30) fps 65→66 | +199 s | 316 | False | False |
| s1__two_people__2026101 | two_people | N1 rssi_step +6 dB (-36→-30) fps 66→65 | +459 s | 53 | False | False |
| s1__two_people__2026101 | two_people | N1 rssi_step -6 dB (-31→-38) fps 66→66 | +530 s | 225 | False | False |
| s2__still__20261025T195 | still | N1 rate_collapse fps 54→16 | +47 s |  | False | False |
| s2__still__20261025T195 | still | N1 rssi_step +8 dB (-40→-33) fps 56→60 | +92 s | 136 | False | False |
| s3__two_people__2026102 | two_people | N1 rate_collapse fps 57→38 | +169 s |  | None | False |
| s1__still__20261027T193 | still | N1 rssi_step -7 dB (-36→-43) fps 66→66 | +34 s | 19 | False | False |
| s5__empty_fan__20261027 | empty_fan | N1 rssi_step -7 dB (-36→-43) fps 65→60 | +138 s | 16 | False | False |
| s5__empty_fan__20261027 | empty_fan | N3 rate_collapse fps 58→28 | +165 s |  | False | False |
| s6__empty__20261027T194 | empty | N3 rate_collapse fps 62→43 | +111 s |  | False | False |
| s7__walking__20261027T1 | walking | N1 rssi_step -12 dB (-35→-48) fps 63→44 | +193 s | 20 | True | True |
| s7__walking__20261027T1 | walking | N1 rate_collapse fps 63→42 | +194 s |  | False | False |
| s7__walking__20261027T1 | walking | N3 rate_collapse fps 61→32 | +165 s |  | False | False |
| s8__empty__20261027T195 | empty | N3 rate_collapse fps 64→44 | +1751 s |  | False | False |
| s10__still__20261027T21 | still | N1 rssi_step -9 dB (-37→-46) fps 67→56 | +265 s | 12 | None | False |

### Segments (recording × epoch); transitional windows removed

| segment | label | kept windows | transitional dropped | N1+N2 windows | evaluated |
|--|--|--|--|--|--|
| s1_two_people_1018_1730@E02 | two_people | 725 | 0 | 725 | yes |
| s1_empty_1018_1756@E02 | empty | 101 | 0 | 101 | yes |
| s1_empty_1018_1802@E02 | empty | 200 | 0 | 200 | yes |
| s1_empty_fan_1018_2039@E02 | empty_fan | 184 | 0 | 184 | yes |
| s2_still_1025_1958@E03 | still | 149 | 0 | 149 | yes |
| s3_two_people_1025_2012@E04 | two_people | 164 | 0 | 164 | yes |
| s1_still_1027_1936@E05 | still | 63 | 0 | 63 | yes |
| s5_empty_fan_1027_1938@E05 | empty_fan | 135 | 0 | 135 | yes |
| s6_empty_1027_1942@E05 | empty | 103 | 0 | 103 | yes |
| s7_walking_1027_1945@E05 | walking | 125 | 4 | 125 | yes |
| s7_walking_1027_1945@E06 | walking | 0 | 13 | 0 | too few |
| s8_empty_1027_1953@E07 | empty | 2140 | 0 | 2140 | yes |
| s9_empty_1027_2047@E07 | empty | 482 | 0 | 482 | yes |
| s10_still_1027_2121@E08 | still | 242 | 0 | 242 | yes |

### Candidate `decor/max` (window-block CIs, optimistic; session-blocked shown where ≥ 2 recordings per class exist)

| protocol/group | empty windows | walking AUC | still AUC | fan AUC | walking TPR@1% | still TPR@1% | empty FPR@1% | fan FPR@1% | empty-vs-empty gate C4 |
|--|--|--|--|--|--|--|--|--|--|
| epoch_cross/E02->E03 | 0 | n/a | n/a | n/a | n/a | 11% | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E02->E04 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E02->E05 | 103 | 0.95 [0.90, 0.98] | 0.88 [0.79, 0.95] | 0.28 [0.18, 0.41] | 5% | 5% | 0% | 0% | n/a (needs ≥ 2 empties) |
| epoch_cross/E02->E07 | 2622 | n/a | n/a | n/a | n/a | n/a | 0% | n/a | pass (worst sym. upper 0.58) |
| epoch_cross/E02->E08 | 0 | n/a | n/a | n/a | n/a | 90% | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E05->E02 | 301 | n/a | n/a | 0.00 [0.00, 0.00] | n/a | n/a | 100% | 100% | FAIL (worst sym. upper 0.94) |
| epoch_cross/E05->E03 | 0 | n/a | n/a | n/a | n/a | 91% | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E05->E04 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E05->E07 | 2622 | n/a | n/a | n/a | n/a | n/a | 100% | n/a | FAIL (worst sym. upper 0.77) |
| epoch_cross/E05->E08 | 0 | n/a | n/a | n/a | n/a | 99% | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E07->E02 | 301 | n/a | n/a | 0.01 [0.00, 0.02] | n/a | n/a | 100% | 60% | FAIL (worst sym. upper 0.94) |
| epoch_cross/E07->E03 | 0 | n/a | n/a | n/a | n/a | 32% | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E07->E04 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E07->E05 | 103 | 0.96 [0.93, 0.98] | 0.88 [0.79, 0.95] | 0.29 [0.18, 0.41] | 6% | 8% | 0% | 0% | n/a (needs ≥ 2 empties) |
| epoch_cross/E07->E08 | 0 | n/a | n/a | n/a | n/a | 90% | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_within/E02 | 301 | n/a | n/a | 0.91 [0.86, 0.96] | n/a | n/a | 2% | 45% | FAIL (worst sym. upper 0.96) |
| epoch_within/E05 | 0 | n/a | n/a | n/a | 97% | 83% | n/a | 13% | n/a (needs ≥ 2 empties) |
| epoch_within/E07 | 2622 | n/a | n/a | n/a | n/a | n/a | 12% | n/a | FAIL (worst sym. upper 0.91) |

### Candidate `perturb_agc/max` (window-block CIs, optimistic; session-blocked shown where ≥ 2 recordings per class exist)

| protocol/group | empty windows | walking AUC | still AUC | fan AUC | walking TPR@1% | still TPR@1% | empty FPR@1% | fan FPR@1% | empty-vs-empty gate C4 |
|--|--|--|--|--|--|--|--|--|--|
| epoch_cross/E02->E03 | 0 | n/a | n/a | n/a | n/a | 32% | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E02->E04 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E02->E05 | 103 | 0.71 [0.61, 0.78] | 0.77 [0.63, 0.86] | 0.43 [0.32, 0.52] | 0% | 2% | 0% | 0% | n/a (needs ≥ 2 empties) |
| epoch_cross/E02->E07 | 2622 | n/a | n/a | n/a | n/a | n/a | 0% | n/a | FAIL (worst sym. upper 0.82) |
| epoch_cross/E02->E08 | 0 | n/a | n/a | n/a | n/a | 46% | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E05->E02 | 301 | n/a | n/a | 0.01 [0.00, 0.02] | n/a | n/a | 100% | 89% | FAIL (worst sym. upper 0.77) |
| epoch_cross/E05->E03 | 0 | n/a | n/a | n/a | n/a | 87% | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E05->E04 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E05->E07 | 2622 | n/a | n/a | n/a | n/a | n/a | 76% | n/a | pass (worst sym. upper 0.56) |
| epoch_cross/E05->E08 | 0 | n/a | n/a | n/a | n/a | 99% | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E07->E02 | 301 | n/a | n/a | 0.21 [0.16, 0.27] | n/a | n/a | 92% | 44% | FAIL (worst sym. upper 0.74) |
| epoch_cross/E07->E03 | 0 | n/a | n/a | n/a | n/a | 50% | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E07->E04 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E07->E05 | 103 | 0.74 [0.63, 0.82] | 0.87 [0.79, 0.94] | 0.46 [0.36, 0.56] | 7% | 17% | 0% | 1% | n/a (needs ≥ 2 empties) |
| epoch_cross/E07->E08 | 0 | n/a | n/a | n/a | n/a | 83% | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_within/E02 | 301 | n/a | n/a | 0.32 [0.24, 0.38] | n/a | n/a | 1% | 1% | FAIL (worst sym. upper 0.83) |
| epoch_within/E05 | 0 | n/a | n/a | n/a | 34% | 56% | n/a | 10% | n/a (needs ≥ 2 empties) |
| epoch_within/E07 | 2622 | n/a | n/a | n/a | n/a | n/a | 5% | n/a | FAIL (worst sym. upper 0.82) |

### Candidate `decor/n2` (window-block CIs, optimistic; session-blocked shown where ≥ 2 recordings per class exist)

| protocol/group | empty windows | walking AUC | still AUC | fan AUC | walking TPR@1% | still TPR@1% | empty FPR@1% | fan FPR@1% | empty-vs-empty gate C4 |
|--|--|--|--|--|--|--|--|--|--|
| epoch_cross/E02->E03 | 0 | n/a | n/a | n/a | n/a | 11% | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E02->E04 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E02->E05 | 103 | 0.95 [0.90, 0.98] | 0.88 [0.79, 0.95] | 0.28 [0.18, 0.41] | 5% | 5% | 0% | 0% | n/a (needs ≥ 2 empties) |
| epoch_cross/E02->E07 | 2622 | n/a | n/a | n/a | n/a | n/a | 0% | n/a | pass (worst sym. upper 0.58) |
| epoch_cross/E02->E08 | 0 | n/a | n/a | n/a | n/a | 90% | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E05->E02 | 301 | n/a | n/a | 0.95 [0.92, 0.98] | n/a | n/a | 82% | 100% | pass (worst sym. upper 0.62) |
| epoch_cross/E05->E03 | 0 | n/a | n/a | n/a | n/a | 88% | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E05->E04 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E05->E07 | 2622 | n/a | n/a | n/a | n/a | n/a | 68% | n/a | pass (worst sym. upper 0.58) |
| epoch_cross/E05->E08 | 0 | n/a | n/a | n/a | n/a | 99% | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E07->E02 | 301 | n/a | n/a | 0.95 [0.92, 0.98] | n/a | n/a | 5% | 76% | pass (worst sym. upper 0.62) |
| epoch_cross/E07->E03 | 0 | n/a | n/a | n/a | n/a | 28% | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E07->E04 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E07->E05 | 103 | 0.95 [0.90, 0.98] | 0.88 [0.79, 0.95] | 0.28 [0.18, 0.41] | 9% | 16% | 0% | 0% | n/a (needs ≥ 2 empties) |
| epoch_cross/E07->E08 | 0 | n/a | n/a | n/a | n/a | 90% | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_within/E02 | 301 | n/a | n/a | 0.95 [0.92, 0.98] | n/a | n/a | 2% | 45% | FAIL (worst sym. upper 0.66) |
| epoch_within/E05 | 0 | n/a | n/a | n/a | 81% | 75% | n/a | 10% | n/a (needs ≥ 2 empties) |
| epoch_within/E07 | 2622 | n/a | n/a | n/a | n/a | n/a | 17% | n/a | pass (worst sym. upper 0.60) |

### Candidate `perturb/max` (window-block CIs, optimistic; session-blocked shown where ≥ 2 recordings per class exist)

| protocol/group | empty windows | walking AUC | still AUC | fan AUC | walking TPR@1% | still TPR@1% | empty FPR@1% | fan FPR@1% | empty-vs-empty gate C4 |
|--|--|--|--|--|--|--|--|--|--|
| epoch_cross/E02->E03 | 0 | n/a | n/a | n/a | n/a | 28% | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E02->E04 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E02->E05 | 103 | 0.73 [0.60, 0.81] | 0.89 [0.81, 0.95] | 0.50 [0.40, 0.59] | 0% | 0% | 0% | 0% | n/a (needs ≥ 2 empties) |
| epoch_cross/E02->E07 | 2622 | n/a | n/a | n/a | n/a | n/a | 0% | n/a | FAIL (worst sym. upper 0.78) |
| epoch_cross/E02->E08 | 0 | n/a | n/a | n/a | n/a | 29% | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E05->E02 | 301 | n/a | n/a | 0.02 [0.01, 0.03] | n/a | n/a | 100% | 96% | FAIL (worst sym. upper 0.76) |
| epoch_cross/E05->E03 | 0 | n/a | n/a | n/a | n/a | 88% | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E05->E04 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E05->E07 | 2622 | n/a | n/a | n/a | n/a | n/a | 63% | n/a | FAIL (worst sym. upper 0.74) |
| epoch_cross/E05->E08 | 0 | n/a | n/a | n/a | n/a | 100% | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E07->E02 | 301 | n/a | n/a | 0.08 [0.05, 0.11] | n/a | n/a | 98% | 42% | pass (worst sym. upper 0.59) |
| epoch_cross/E07->E03 | 0 | n/a | n/a | n/a | n/a | 51% | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E07->E04 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_cross/E07->E05 | 103 | 0.72 [0.59, 0.80] | 0.89 [0.81, 0.95] | 0.50 [0.39, 0.59] | 8% | 13% | 0% | 1% | n/a (needs ≥ 2 empties) |
| epoch_cross/E07->E08 | 0 | n/a | n/a | n/a | n/a | 82% | n/a | n/a | n/a (needs ≥ 2 empties) |
| epoch_within/E02 | 301 | n/a | n/a | 0.05 [0.02, 0.07] | n/a | n/a | 3% | 0% | FAIL (worst sym. upper 0.74) |
| epoch_within/E05 | 0 | n/a | n/a | n/a | 35% | 54% | n/a | 11% | n/a (needs ≥ 2 empties) |
| epoch_within/E07 | 2622 | n/a | n/a | n/a | n/a | n/a | 5% | n/a | FAIL (worst sym. upper 0.82) |
