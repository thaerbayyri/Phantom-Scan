# Sensitivity of the post-hoc epoch boundary rule

**Rule status: POST HOC (chosen after inspecting these recordings; not pre-registered).** Node set N1+N2. The empty-recording hold limit stays at 60 s in every row.

| step | hold | in-recording events | boundaries from them | ambiguous | s7 N1 step is a boundary (onset) | epochs with ≥ 2 empties | … and walking or still | … and two_people |
|--|--|--|--|--|--|--|--|--|
| 4 dB | 10 s | 22 | 4 | 18 | yes (+193 s) | E06, E11 | none | none |
| 4 dB | 30 s | 5 | 1 | 4 | NO | E04, E08 | none | none |
| 4 dB | 60 s | 3 | 2 | 1 | NO | E05, E09 | none | none |
| 6 dB | 10 s | 11 | 1 | 10 | yes (+193 s) | E02, E07 | none | E02 |
| 6 dB | 30 s | 3 | 0 | 3 | NO | E02, E06 | none | E02 |
| 6 dB | 60 s | 2 | 1 | 1 | NO | E03, E07 | none | E03 |
| 8 dB | 10 s | 6 | 1 | 5 | yes (+194 s) | E02, E07 | none | E02 |
| 8 dB | 30 s | 2 | 0 | 2 | NO | E02, E06 | none | E02 |
| 8 dB | 60 s | 1 | 0 | 1 | NO | E02, E06 | none | E02 |

## Every ambiguous step at the default setting (6 dB, 10 s)

| recording | label | node | event | at | Δ dB | fps | held s | persistent | why it is not a boundary |
|--|--|--|--|--|--|--|--|--|--|
| s1__two_people__2026101 | two_people | N1 | rssi_step | 10-18 17:34:14 (+199 s) | +9 | 65→66 | 316 | False | occupied recording, not persistent: may be the person's own body |
| s1__two_people__2026101 | two_people | N1 | rssi_step | 10-18 17:38:34 (+459 s) | +6 | 66→65 | 53 | False | occupied recording, not persistent: may be the person's own body |
| s1__two_people__2026101 | two_people | N1 | rssi_step | 10-18 17:39:45 (+530 s) | -6 | 66→66 | 225 | False | occupied recording, not persistent: may be the person's own body |
| s2__still__20261025T195 | still | N1 | rate_collapse | 10-25 19:59:22 (+47 s) |  | 54→16 |  | False | occupied recording, not persistent: may be the person's own body |
| s2__still__20261025T195 | still | N1 | rssi_step | 10-25 20:00:07 (+92 s) | +8 | 56→60 | 136 | False | occupied recording, not persistent: may be the person's own body |
| s3__two_people__2026102 | two_people | N1 | rate_collapse | 10-25 20:14:58 (+169 s) |  | 57→38 |  | None | occupied recording, last recording of its day: persistence cannot be confirmed |
| s1__still__20261027T193 | still | N1 | rssi_step | 10-27 19:36:44 (+34 s) | -7 | 66→66 | 19 | False | occupied recording, not persistent: may be the person's own body |
| s5__empty_fan__20261027 | empty_fan | N1 | rssi_step | 10-27 19:40:41 (+138 s) | -7 | 65→60 | 16 | False | empty/fan recording but held only 16 s (< 60 s): excursion |
| s7__walking__20261027T1 | walking | N1 | rate_collapse | 10-27 19:48:51 (+194 s) |  | 63→42 |  | False | occupied recording, not persistent: may be the person's own body |
| s10__still__20261027T21 | still | N1 | rssi_step | 10-27 21:25:33 (+265 s) | -9 | 67→56 | 12 | None | occupied recording, last recording of its day: persistence cannot be confirmed |
