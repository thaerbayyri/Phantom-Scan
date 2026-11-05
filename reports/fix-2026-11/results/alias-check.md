# PS-FIX-40 — does the 33.3 Hz ping cadence alias, and where does it land?

Ping cadence 33.33 Hz (30 ms). Bands analysed: respiration 0.1–0.5 Hz, cardiac 0.8–2.0 Hz, the periodicity tool's 1–20 Hz.

## 1. Where the ping harmonics land, by sampling rate (alias = |k·33.33 − n·fs|)

| fs (Hz) | k=1 | k=2 | k=3 | k=4 | k=5 | k=6 | harmonics inside respiration / cardiac / 1–20 Hz |
|--|--|--|--|--|--|--|--|
| 20 | 6.67 | 6.67 | 0.00 | 6.67 | 6.67 | 0.00 | 0 / 0 / 4 |
| 50 | 16.67 | 16.67 | 0.00 | 16.67 | 16.67 | 0.00 | 0 / 0 / 4 |
| 64 | 30.67 | 2.67 | 28.00 | 5.33 | 25.33 | 8.00 | 0 / 0 / 3 |
| 100 | 33.33 | 33.33 | 0.00 | 33.33 | 33.33 | 0.00 | 0 / 0 / 0 |

100 Hz = 3 × 33.33 Hz is the only grid here where every harmonic folds to 0 Hz (removed by detrending) or to 33.33 Hz (above 20 Hz); 64 Hz moves the fundamental out of 1–20 Hz but its 2nd, 4th and 6th harmonics (2.67, 5.33, 8.00 Hz) land inside it.

## 2. Synthetic stream (two frames per ping, alternating kind; 0.3 Hz respiration and 1.2 Hz cardiac tones added)

| path | predicted alias (Hz) | strongest line above 2.5 Hz (Hz) | respiration peak | cardiac peak | power share resp / cardiac | classifier high-freq ratio (median) |
|--|--|--|--|--|--|--|
| linear interpolation to 50 Hz | 16.67 | 16.67 | 0.30 | 1.20 | 0.0350 / 0.0082 | n/a |
| linear interpolation to 64 Hz | 30.67 | 30.67 | 0.30 | 1.20 | 0.0399 / 0.0076 | n/a |
| linear interpolation to 100 Hz | 33.33 | 33.34 | 0.30 | 1.20 | 0.0339 / 0.0059 | n/a |
| 20 Hz nearest-sample decimation (production-like) | 6.67 | 6.67 | 0.30 | 1.20 | 0.0259 / 0.0420 | 0.824 |
| 20 Hz anti-aliased decimation | 6.67 | 4.29 | 0.30 | 1.20 | 0.8051 / 0.1362 | 0.054 |

The alias lands outside BOTH vital bands on every path; the respiration and cardiac tones are recovered at their true frequencies. The damage is to the 1–20 Hz periodicity feature (50 Hz grid: 16.67 Hz) and to the classifier's >5 Hz band (20 Hz decimation: 6.67 Hz).

## 3. Real recordings: classifier replica with production-like decimation vs anti-aliased decimation (all nodes pooled by class)

A window would SUPPRESS a presence claim only if its label is `mechanical` AND humanProb <= 0.2 (node-fusion.ts, a placeholder constant); that is the column that matters for the two failure directions.

| class | windows | median high-freq ratio raw → AA | median humanProb raw → AA | share labelled mechanical raw → AA | **share that would suppress, raw → AA** | windows whose label changes |
|--|--|--|--|--|--|--|
| still | 5398 | 0.556 → 0.354 | 0.338 → 0.351 | 0.591 → 0.496 | **0.0202 → 0.0308** | 0.510 |
| empty | 36138 | 0.565 → 0.372 | 0.335 → 0.346 | 0.613 → 0.522 | **0.0353 → 0.0304** | 0.497 |
| empty_fan | 3764 | 0.548 → 0.367 | 0.341 → 0.347 | 0.567 → 0.512 | **0.0101 → 0.0270** | 0.499 |
| two_people | 10628 | 0.558 → 0.363 | 0.337 → 0.347 | 0.605 → 0.515 | **0.0199 → 0.0336** | 0.498 |
| walking | 1662 | 0.537 → 0.356 | 0.342 → 0.347 | 0.557 → 0.514 | **0.0078 → 0.0364** | 0.477 |

Limits: the replica's input is the per-frame mean amplitude of ONE node, a proxy for the production dynamicAmplitude (clutter-removed complex channel; nodes are interleaved by a round-robin queue in the live path); decimation is emulated as the first frame at or after each 50 ms tick; the live queue/round-robin dynamics are not reproduced; the replay measures the mechanism (does anti-aliasing change the classifier's inputs and labels), not live label rates; recorder timestamps are host clock (ms); nothing here changes a threshold, a setting or the firmware; nothing is written into data/.
