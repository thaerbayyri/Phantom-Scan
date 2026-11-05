# Movement score (not a presence detector)

**movement score: relative to this node's own recent past; fades under sustained motion and is zero for a motionless person; NOT presence, and never evidence that a room is empty.**

AUC = movement score of the named class vs the EMPTY segments of the same group (an epoch, or all epochs). The first interval is a window-block bootstrap (optimistic); `sb` is the session-blocked interval (needs ≥ 2 recordings in each class, otherwise `[no CI]`).

## N1+N2/perturb/L45

| group | empties | walking | still | two_people | fan (negative control) | empty-vs-empty C4 |
|--|--|--|--|--|--|--|
| epoch E02 | 2 seg / 253 win | n/a | n/a | 0.70 [0.64, 0.75] | 0.55 [0.49, 0.62] | FAIL (0.70) |
| epoch E03 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E04 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E05 | 1 seg / 79 win | 0.64 [0.53, 0.76] | n/a | n/a | 0.54 [0.41, 0.65] | n/a (< 2 empties) |
| epoch E07 | 2 seg / 2574 win | n/a | n/a | n/a | n/a | pass (0.54) |
| epoch E08 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| ACROSS epochs | 5 seg / 2906 win | 0.57 [0.47, 0.68] | 0.68 [0.61, 0.75] sb 0.68 [0.60, 0.75] | 0.71 [0.66, 0.75] sb 0.71 [0.54, 0.75] | 0.53 [0.48, 0.59] sb 0.53 [0.40, 0.61] | FAIL (0.79) |

## N1+N2/perturb/L90

| group | empties | walking | still | two_people | fan (negative control) | empty-vs-empty C4 |
|--|--|--|--|--|--|--|
| epoch E02 | 1 seg / 152 win | n/a | n/a | 0.76 [0.70, 0.81] | 0.60 [0.52, 0.65] | n/a (< 2 empties) |
| epoch E03 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E04 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E05 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E07 | 2 seg / 2526 win | n/a | n/a | n/a | n/a | pass (0.54) |
| epoch E08 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| ACROSS epochs | 3 seg / 2678 win | 0.68 [0.54, 0.79] | 0.67 [0.59, 0.75] sb 0.67 [0.53, 0.74] | 0.74 [0.69, 0.79] sb 0.74 [0.58, 0.79] | 0.56 [0.50, 0.63] sb 0.56 [0.44, 0.62] | pass (0.57) |

## N1+N2/perturb_agc/L45

| group | empties | walking | still | two_people | fan (negative control) | empty-vs-empty C4 |
|--|--|--|--|--|--|--|
| epoch E02 | 2 seg / 253 win | n/a | n/a | 0.69 [0.62, 0.74] | 0.56 [0.50, 0.63] | FAIL (0.67) |
| epoch E03 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E04 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E05 | 1 seg / 79 win | 0.61 [0.50, 0.73] | n/a | n/a | 0.53 [0.40, 0.64] | n/a (< 2 empties) |
| epoch E07 | 2 seg / 2574 win | n/a | n/a | n/a | n/a | pass (0.54) |
| epoch E08 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| ACROSS epochs | 5 seg / 2906 win | 0.59 [0.49, 0.69] | 0.66 [0.59, 0.74] sb 0.66 [0.59, 0.74] | 0.68 [0.64, 0.73] sb 0.68 [0.54, 0.73] | 0.54 [0.50, 0.60] sb 0.54 [0.45, 0.60] | FAIL (0.72) |

## N1+N2/perturb_agc/L90

| group | empties | walking | still | two_people | fan (negative control) | empty-vs-empty C4 |
|--|--|--|--|--|--|--|
| epoch E02 | 1 seg / 152 win | n/a | n/a | 0.75 [0.69, 0.80] | 0.60 [0.51, 0.65] | n/a (< 2 empties) |
| epoch E03 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E04 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E05 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E07 | 2 seg / 2526 win | n/a | n/a | n/a | n/a | pass (0.54) |
| epoch E08 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| ACROSS epochs | 3 seg / 2678 win | 0.70 [0.55, 0.79] | 0.65 [0.57, 0.73] sb 0.65 [0.52, 0.72] | 0.73 [0.67, 0.78] sb 0.73 [0.58, 0.78] | 0.58 [0.52, 0.64] sb 0.58 [0.49, 0.63] | pass (0.57) |

## N1+N2/decor/L45

| group | empties | walking | still | two_people | fan (negative control) | empty-vs-empty C4 |
|--|--|--|--|--|--|--|
| epoch E02 | 2 seg / 253 win | n/a | n/a | 0.72 [0.66, 0.78] | 0.39 [0.29, 0.50] | FAIL (0.73) |
| epoch E03 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E04 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E05 | 1 seg / 79 win | 0.78 [0.70, 0.86] | n/a | n/a | 0.50 [0.34, 0.60] | n/a (< 2 empties) |
| epoch E07 | 2 seg / 2574 win | n/a | n/a | n/a | n/a | pass (0.57) |
| epoch E08 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| ACROSS epochs | 5 seg / 2906 win | 0.47 [0.37, 0.57] | 0.68 [0.61, 0.75] sb 0.68 [0.52, 0.79] | 0.74 [0.70, 0.78] sb 0.74 [0.70, 0.80] | 0.37 [0.31, 0.44] sb 0.37 [0.20, 0.54] | FAIL (1.00) |

## N1+N2/decor/L90

| group | empties | walking | still | two_people | fan (negative control) | empty-vs-empty C4 |
|--|--|--|--|--|--|--|
| epoch E02 | 1 seg / 152 win | n/a | n/a | 0.76 [0.70, 0.82] | 0.48 [0.33, 0.61] | n/a (< 2 empties) |
| epoch E03 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E04 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E05 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E07 | 2 seg / 2526 win | n/a | n/a | n/a | n/a | pass (0.57) |
| epoch E08 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| ACROSS epochs | 3 seg / 2678 win | 0.55 [0.44, 0.67] | 0.62 [0.53, 0.72] sb 0.62 [0.45, 0.73] | 0.74 [0.69, 0.78] sb 0.74 [0.66, 0.79] | 0.41 [0.33, 0.48] sb 0.41 [0.20, 0.54] | pass (0.64) |

## N1+N2+N3+N4/perturb/L45

| group | empties | walking | still | two_people | fan (negative control) | empty-vs-empty C4 |
|--|--|--|--|--|--|--|
| epoch E02 | 2 seg / 253 win | n/a | n/a | 0.70 [0.65, 0.76] | 0.58 [0.52, 0.64] | pass (0.64) |
| epoch E03 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E04 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E05 | 1 seg / 78 win | 0.68 [0.55, 0.84] | n/a | n/a | 0.56 [0.43, 0.67] | n/a (< 2 empties) |
| epoch E07 | 2 seg / 2574 win | n/a | n/a | n/a | n/a | pass (0.56) |
| epoch E08 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| ACROSS epochs | 5 seg / 2905 win | 0.60 [0.44, 0.78] | 0.78 [0.73, 0.84] sb 0.78 [0.70, 0.86] | 0.75 [0.71, 0.80] sb 0.75 [0.60, 0.80] | 0.59 [0.53, 0.65] sb 0.59 [0.41, 0.72] | FAIL (0.82) |

## N1+N2+N3+N4/perturb/L90

| group | empties | walking | still | two_people | fan (negative control) | empty-vs-empty C4 |
|--|--|--|--|--|--|--|
| epoch E02 | 1 seg / 152 win | n/a | n/a | 0.75 [0.70, 0.81] | 0.67 [0.58, 0.76] | n/a (< 2 empties) |
| epoch E03 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E04 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E05 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E07 | 2 seg / 2526 win | n/a | n/a | n/a | n/a | pass (0.58) |
| epoch E08 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| ACROSS epochs | 3 seg / 2678 win | 0.73 [0.54, 0.90] | 0.82 [0.77, 0.88] sb 0.82 [0.71, 0.88] | 0.78 [0.74, 0.83] sb 0.78 [0.60, 0.83] | 0.67 [0.59, 0.75] sb 0.67 [0.42, 0.80] | FAIL (0.70) |

## N1+N2+N3+N4/perturb_agc/L45

| group | empties | walking | still | two_people | fan (negative control) | empty-vs-empty C4 |
|--|--|--|--|--|--|--|
| epoch E02 | 2 seg / 253 win | n/a | n/a | 0.67 [0.61, 0.72] | 0.54 [0.49, 0.62] | pass (0.64) |
| epoch E03 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E04 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E05 | 1 seg / 78 win | 0.70 [0.57, 0.84] | n/a | n/a | 0.55 [0.41, 0.67] | n/a (< 2 empties) |
| epoch E07 | 2 seg / 2574 win | n/a | n/a | n/a | n/a | pass (0.55) |
| epoch E08 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| ACROSS epochs | 5 seg / 2905 win | 0.66 [0.51, 0.81] | 0.73 [0.67, 0.81] sb 0.73 [0.63, 0.85] | 0.74 [0.69, 0.78] sb 0.74 [0.61, 0.78] | 0.60 [0.53, 0.65] sb 0.60 [0.45, 0.69] | FAIL (0.78) |

## N1+N2+N3+N4/perturb_agc/L90

| group | empties | walking | still | two_people | fan (negative control) | empty-vs-empty C4 |
|--|--|--|--|--|--|--|
| epoch E02 | 1 seg / 152 win | n/a | n/a | 0.74 [0.68, 0.80] | 0.63 [0.53, 0.72] | n/a (< 2 empties) |
| epoch E03 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E04 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E05 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E07 | 2 seg / 2526 win | n/a | n/a | n/a | n/a | pass (0.54) |
| epoch E08 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| ACROSS epochs | 3 seg / 2678 win | 0.77 [0.60, 0.92] | 0.75 [0.68, 0.82] sb 0.75 [0.65, 0.84] | 0.78 [0.74, 0.83] sb 0.78 [0.61, 0.83] | 0.68 [0.61, 0.75] sb 0.68 [0.49, 0.78] | FAIL (0.69) |

## N1+N2+N3+N4/decor/L45

| group | empties | walking | still | two_people | fan (negative control) | empty-vs-empty C4 |
|--|--|--|--|--|--|--|
| epoch E02 | 2 seg / 253 win | n/a | n/a | 0.80 [0.75, 0.84] | 0.52 [0.40, 0.64] | FAIL (0.66) |
| epoch E03 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E04 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E05 | 1 seg / 78 win | 0.76 [0.63, 0.87] | n/a | n/a | 0.35 [0.23, 0.47] | n/a (< 2 empties) |
| epoch E07 | 2 seg / 2574 win | n/a | n/a | n/a | n/a | pass (0.65) |
| epoch E08 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| ACROSS epochs | 5 seg / 2905 win | 0.55 [0.39, 0.71] | 0.67 [0.60, 0.73] sb 0.67 [0.54, 0.78] | 0.75 [0.71, 0.80] sb 0.75 [0.63, 0.84] | 0.37 [0.28, 0.44] sb 0.37 [0.13, 0.60] | FAIL (0.88) |

## N1+N2+N3+N4/decor/L90

| group | empties | walking | still | two_people | fan (negative control) | empty-vs-empty C4 |
|--|--|--|--|--|--|--|
| epoch E02 | 1 seg / 152 win | n/a | n/a | 0.82 [0.78, 0.88] | 0.58 [0.41, 0.74] | n/a (< 2 empties) |
| epoch E03 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E04 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E05 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| epoch E07 | 2 seg / 2526 win | n/a | n/a | n/a | n/a | FAIL (0.65) |
| epoch E08 | 0 seg / 0 win | n/a | n/a | n/a | n/a | n/a (< 2 empties) |
| ACROSS epochs | 3 seg / 2678 win | 0.67 [0.49, 0.84] | 0.64 [0.56, 0.73] sb 0.64 [0.51, 0.73] | 0.77 [0.72, 0.82] sb 0.77 [0.57, 0.86] | 0.43 [0.32, 0.53] sb 0.43 [0.14, 0.63] | FAIL (0.67) |

## Does it fade? median score by third of each segment (N1+N2/decor/L45)

| segment | first third | middle | last third |
|--|--|--|--|
| s1_two_people_1018_1730@E02 | 0.194 | 0.254 | 0.11 |
| s1_empty_1018_1756@E02 | 0.0589 | 0.101 | 0.102 |
| s1_empty_1018_1802@E02 | 0.0651 | 0.0694 | 0.0715 |
| s1_empty_fan_1018_2039@E02 | 0.0302 | 0.0727 | 0.0586 |
| s2_still_1025_1958@E03 | 0.11 | 0.0538 | 0.149 |
| s3_two_people_1025_2012@E04 | 0.117 | 0.103 | 0.346 |
| s5_empty_fan_1027_1938@E05 | 0.00877 | 0.0131 | 0.0103 |
| s6_empty_1027_1942@E05 | 0.0143 | 0.0124 | 0.00745 |
| s7_walking_1027_1945@E05 | 0.0199 | 0.0232 | 0.156 |
| s8_empty_1027_1953@E07 | 0.0618 | 0.0652 | 0.0421 |
| s9_empty_1027_2047@E07 | 0.0217 | 0.0705 | 0.0532 |
| s10_still_1027_2121@E08 | 0.314 | 0.23 | 0.0752 |
