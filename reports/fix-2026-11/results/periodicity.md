# PS-FIX-09 — fan / periodicity candidate (offline)

peak_ratio = max/median of the spectrum of the top-variance subcarriers, 1-20 Hz, max over nodes 1 and 2. AUC with a moving-block bootstrap 95 % CI.

## grid/window 50Hz/10s

| recording | class | windows | peak_ratio median (q10-q90) | peak at 33.3 Hz-alias |
|--|--|--|--|--|
| s1_empty_1756 | empty | 14 | 54.86 (28.39-95.81) | 0.52 |
| s1_empty_1802 | empty | 29 | 29.43 (14.19-48.21) | 0.74 |
| s1_fan_2039 | empty_fan | 26 | 9.11 (7.13-37.77) | 0.33 |
| s1_two_people_1730 | two_people | 107 | 59.58 (21.14-152.62) | 0.86 |
| s6_empty_1942 | empty | 14 | 9.31 (5.44-18.97) | 0.72 |
| s5_fan_1938 | empty_fan | 20 | 12.77 (5.74-19.65) | 0.62 |
| s1_still_1936 | still | 8 | 18.16 (12.36-34.09) | 0.82 |
| s7_walking_head_1945 | walking | 18 | 11.57 (6.95-23.07) | 0.75 |
| s8_empty_1953 | empty | 319 | 28.56 (8.17-154.00) | 0.46 |
| s9_empty_2047 | empty | 71 | 38.85 (6.78-132.57) | 0.57 |

| session | fan vs empty | person vs empty | fan vs person |
|--|--|--|--|
| oct18/peak_ratio | 0.12 [0.01, 0.32] (n=26/43) | 0.70 [0.59, 0.82] (n=107/43) | 0.08 [0.01, 0.19] (n=26/107) |
| oct27/peak_ratio | 0.56 [0.42, 0.79] (n=20/14) | 0.67 [0.52, 0.90] (n=26/14) | 0.40 [0.20, 0.54] (n=20/26) |

Empty-vs-empty control (C4): passes=False, worst symmetric upper bound 1.00 (limit 0.65).
Label threshold tau fitted on the other session: {oct18: 6.38, oct27: 14.56}.

| veto test | class | mechanical share | detector flag rate | with veto |
|--|--|--|--|--|
| oct18_tau_from_oct27 | calib_empty | 1.00 | 0.05 | 0.00 |
| oct18_tau_from_oct27 | held_empty | 0.86 | 0.15 | 0.03 |
| oct18_tau_from_oct27 | fan | 0.27 | 0.02 | 0.02 |
| oct18_tau_from_oct27 | s1_two_people_1730 | 0.94 | 0.58 | 0.06 |
| oct18_tau_from_oct27 | AUC s1_two_people_1730 | | 0.77 [0.69, 0.86] (n=725/101) | 0.50 [0.48, 0.55] (n=725/101) |
| oct27_tau_from_oct18 | calib_empty | 0.79 | 0.06 | 0.01 |
| oct27_tau_from_oct18 | fan | 0.85 | 0.15 | 0.02 |
| oct27_tau_from_oct18 | s1_still_1936 | 1.00 | 0.60 | 0.11 |
| oct27_tau_from_oct18 | s7_walking_head_1945 | 0.94 | 0.41 | 0.03 |
| oct27_tau_from_oct18 | AUC s1_still_1936 | | 0.88 [0.80, 0.96] (n=63/103) | 0.43 [0.30, 0.50] (n=63/103) |
| oct27_tau_from_oct18 | AUC s7_walking_head_1945 | | 0.74 [0.56, 0.84] (n=125/103) | 0.40 [0.30, 0.50] (n=125/103) |

## grid/window 50Hz/15s

| recording | class | windows | peak_ratio median (q10-q90) | peak at 33.3 Hz-alias |
|--|--|--|--|--|
| s1_empty_1756 | empty | 9 | 96.38 (70.76-151.10) | 0.47 |
| s1_empty_1802 | empty | 19 | 52.76 (28.90-79.81) | 0.82 |
| s1_fan_2039 | empty_fan | 17 | 10.99 (7.70-48.81) | 0.32 |
| s1_two_people_1730 | two_people | 71 | 85.31 (40.03-255.98) | 0.89 |
| s6_empty_1942 | empty | 9 | 11.43 (7.81-34.61) | 0.74 |
| s5_fan_1938 | empty_fan | 13 | 21.56 (11.08-30.34) | 0.73 |
| s1_still_1936 | still | 5 | 37.12 (18.13-66.21) | 0.91 |
| s7_walking_head_1945 | walking | 12 | 19.62 (9.95-30.99) | 0.75 |
| s8_empty_1953 | empty | 212 | 46.70 (10.64-239.99) | 0.53 |
| s9_empty_2047 | empty | 47 | 48.63 (10.33-248.73) | 0.61 |

| session | fan vs empty | person vs empty | fan vs person |
|--|--|--|--|
| oct18/peak_ratio | 0.10 [0.00, 0.30] (n=17/28) | 0.68 [0.52, 0.84] (n=71/28) | 0.06 [0.00, 0.16] (n=17/71) |
| oct27/peak_ratio | 0.68 [0.56, 0.93] (n=13/9) | 0.71 [0.62, 0.93] (n=17/9) | 0.45 [0.22, 0.64] (n=13/17) |

Empty-vs-empty control (C4): passes=False, worst symmetric upper bound 1.00 (limit 0.65).
Label threshold tau fitted on the other session: {oct18: 7.65, oct27: 12.99}.

| veto test | class | mechanical share | detector flag rate | with veto |
|--|--|--|--|--|
| oct18_tau_from_oct27 | calib_empty | 1.00 | 0.05 | 0.00 |
| oct18_tau_from_oct27 | held_empty | 1.00 | 0.15 | 0.01 |
| oct18_tau_from_oct27 | fan | 0.47 | 0.02 | 0.02 |
| oct18_tau_from_oct27 | s1_two_people_1730 | 1.00 | 0.58 | 0.02 |
| oct18_tau_from_oct27 | AUC s1_two_people_1730 | | 0.77 [0.66, 0.87] (n=725/101) | 0.46 [0.44, 0.51] (n=725/101) |
| oct27_tau_from_oct18 | calib_empty | 0.89 | 0.06 | 0.01 |
| oct27_tau_from_oct18 | fan | 0.92 | 0.15 | 0.04 |
| oct27_tau_from_oct18 | s1_still_1936 | 1.00 | 0.60 | 0.17 |
| oct27_tau_from_oct18 | s7_walking_head_1945 | 1.00 | 0.41 | 0.04 |
| oct27_tau_from_oct18 | AUC s1_still_1936 | | 0.88 [0.84, 0.95] (n=63/103) | 0.51 [0.40, 0.60] (n=63/103) |
| oct27_tau_from_oct18 | AUC s7_walking_head_1945 | | 0.74 [0.56, 0.83] (n=125/103) | 0.41 [0.39, 0.51] (n=125/103) |

## grid/window 50Hz/20s

| recording | class | windows | peak_ratio median (q10-q90) | peak at 33.3 Hz-alias |
|--|--|--|--|--|
| s1_empty_1756 | empty | 6 | 119.34 (83.45-145.95) | 0.46 |
| s1_empty_1802 | empty | 14 | 59.82 (37.70-79.71) | 0.82 |
| s1_fan_2039 | empty_fan | 12 | 16.89 (7.84-54.49) | 0.33 |
| s1_two_people_1730 | two_people | 53 | 102.74 (34.84-252.39) | 0.91 |
| s6_empty_1942 | empty | 6 | 16.46 (9.09-23.85) | 1.00 |
| s5_fan_1938 | empty_fan | 10 | 21.66 (11.22-28.13) | 0.80 |
| s1_still_1936 | still | 3 | 55.10 (31.85-64.71) | 0.86 |
| s7_walking_head_1945 | walking | 9 | 22.92 (8.56-39.31) | 0.83 |
| s8_empty_1953 | empty | 159 | 57.61 (12.24-293.32) | 0.54 |
| s9_empty_2047 | empty | 35 | 60.08 (9.02-284.84) | 0.61 |

| session | fan vs empty | person vs empty | fan vs person |
|--|--|--|--|
| oct18/peak_ratio | 0.10 [0.00, 0.30] (n=12/20) | 0.70 [0.53, 0.86] (n=53/20) | 0.07 [0.00, 0.19] (n=12/53) |
| oct27/peak_ratio | 0.67 [0.45, 0.92] (n=10/6) | 0.75 [0.60, 1.00] (n=12/6) | 0.34 [0.10, 0.53] (n=10/12) |

Empty-vs-empty control (C4): passes=False, worst symmetric upper bound 0.84 (limit 0.65).
Label threshold tau fitted on the other session: {oct18: 6.80, oct27: 9.44}.

| veto test | class | mechanical share | detector flag rate | with veto |
|--|--|--|--|--|
| oct18_tau_from_oct27 | calib_empty | 1.00 | 0.05 | 0.01 |
| oct18_tau_from_oct27 | held_empty | 1.00 | 0.15 | 0.02 |
| oct18_tau_from_oct27 | fan | 0.75 | 0.02 | 0.01 |
| oct18_tau_from_oct27 | s1_two_people_1730 | 1.00 | 0.58 | 0.02 |
| oct18_tau_from_oct27 | AUC s1_two_people_1730 | | 0.77 [0.66, 0.88] (n=725/101) | 0.41 [0.42, 0.52] (n=725/101) |
| oct27_tau_from_oct18 | calib_empty | 1.00 | 0.06 | 0.00 |
| oct27_tau_from_oct18 | fan | 1.00 | 0.15 | 0.01 |
| oct27_tau_from_oct18 | s1_still_1936 | 1.00 | 0.60 | 0.27 |
| oct27_tau_from_oct18 | s7_walking_head_1945 | 1.00 | 0.41 | 0.06 |
| oct27_tau_from_oct18 | AUC s1_still_1936 | | 0.88 [0.88, 0.92] (n=63/103) | 0.61 [0.57, 0.69] (n=63/103) |
| oct27_tau_from_oct18 | AUC s7_walking_head_1945 | | 0.74 [0.57, 0.80] (n=125/103) | 0.42 [0.41, 0.52] (n=125/103) |

## grid/window 64Hz/10s

| recording | class | windows | peak_ratio median (q10-q90) | peak at 33.3 Hz-alias |
|--|--|--|--|--|
| s1_empty_1756 | empty | 14 | 10.89 (7.06-13.83) | 0.00 |
| s1_empty_1802 | empty | 29 | 9.57 (7.57-12.75) | 0.00 |
| s1_fan_2039 | empty_fan | 26 | 9.14 (7.18-12.12) | 0.00 |
| s1_two_people_1730 | two_people | 107 | 8.92 (5.88-14.10) | 0.00 |
| s6_empty_1942 | empty | 14 | 6.25 (4.93-7.14) | 0.00 |
| s5_fan_1938 | empty_fan | 20 | 6.29 (4.78-8.95) | 0.00 |
| s1_still_1936 | still | 8 | 7.17 (5.26-13.71) | 0.00 |
| s7_walking_head_1945 | walking | 18 | 7.21 (5.19-9.29) | 0.00 |
| s8_empty_1953 | empty | 319 | 7.95 (5.80-11.32) | 0.00 |
| s9_empty_2047 | empty | 71 | 7.02 (5.20-10.39) | 0.00 |

| session | fan vs empty | person vs empty | fan vs person |
|--|--|--|--|
| oct18/peak_ratio | 0.38 [0.28, 0.54] (n=26/43) | 0.39 [0.30, 0.49] (n=107/43) | 0.52 [0.42, 0.65] (n=26/107) |
| oct27/peak_ratio | 0.51 [0.26, 0.68] (n=20/14) | 0.74 [0.54, 0.86] (n=26/14) | 0.33 [0.18, 0.53] (n=20/26) |

Empty-vs-empty control (C4): passes=False, worst symmetric upper bound 1.00 (limit 0.65).
Label threshold tau fitted on the other session: {oct18: 7.48, oct27: 19.50}.

| veto test | class | mechanical share | detector flag rate | with veto |
|--|--|--|--|--|
| oct18_tau_from_oct27 | calib_empty | 0.00 | 0.05 | 0.05 |
| oct18_tau_from_oct27 | held_empty | 0.00 | 0.15 | 0.15 |
| oct18_tau_from_oct27 | fan | 0.00 | 0.02 | 0.02 |
| oct18_tau_from_oct27 | s1_two_people_1730 | 0.02 | 0.58 | 0.57 |
| oct18_tau_from_oct27 | AUC s1_two_people_1730 | | 0.77 [0.69, 0.86] (n=725/101) | 0.75 [0.67, 0.84] (n=725/101) |
| oct27_tau_from_oct18 | calib_empty | 0.00 | 0.06 | 0.06 |
| oct27_tau_from_oct18 | fan | 0.20 | 0.15 | 0.10 |
| oct27_tau_from_oct18 | s1_still_1936 | 0.50 | 0.60 | 0.33 |
| oct27_tau_from_oct18 | s7_walking_head_1945 | 0.39 | 0.41 | 0.19 |
| oct27_tau_from_oct18 | AUC s1_still_1936 | | 0.88 [0.80, 0.96] (n=63/103) | 0.47 [0.05, 0.53] (n=63/103) |
| oct27_tau_from_oct18 | AUC s7_walking_head_1945 | | 0.74 [0.56, 0.84] (n=125/103) | 0.43 [0.36, 0.52] (n=125/103) |

## grid/window 64Hz/15s

| recording | class | windows | peak_ratio median (q10-q90) | peak at 33.3 Hz-alias |
|--|--|--|--|--|
| s1_empty_1756 | empty | 9 | 9.48 (7.92-10.78) | 0.00 |
| s1_empty_1802 | empty | 19 | 10.21 (7.96-15.82) | 0.00 |
| s1_fan_2039 | empty_fan | 17 | 9.05 (7.83-11.51) | 0.00 |
| s1_two_people_1730 | two_people | 71 | 9.72 (6.67-15.06) | 0.00 |
| s6_empty_1942 | empty | 9 | 6.71 (6.27-7.28) | 0.00 |
| s5_fan_1938 | empty_fan | 13 | 7.51 (5.05-10.96) | 0.00 |
| s1_still_1936 | still | 5 | 8.53 (6.71-12.88) | 0.00 |
| s7_walking_head_1945 | walking | 12 | 7.90 (5.73-10.82) | 0.00 |
| s8_empty_1953 | empty | 212 | 8.94 (6.71-13.30) | 0.00 |
| s9_empty_2047 | empty | 47 | 8.36 (5.88-13.62) | 0.00 |

| session | fan vs empty | person vs empty | fan vs person |
|--|--|--|--|
| oct18/peak_ratio | 0.39 [0.29, 0.64] (n=17/28) | 0.46 [0.37, 0.61] (n=71/28) | 0.45 [0.34, 0.58] (n=17/71) |
| oct27/peak_ratio | 0.60 [0.37, 0.77] (n=13/9) | 0.70 [0.41, 0.84] (n=17/9) | 0.38 [0.22, 0.64] (n=13/17) |

Empty-vs-empty control (C4): passes=False, worst symmetric upper bound 1.00 (limit 0.65).
Label threshold tau fitted on the other session: {oct18: 8.69, oct27: 7.01}.

| veto test | class | mechanical share | detector flag rate | with veto |
|--|--|--|--|--|
| oct18_tau_from_oct27 | calib_empty | 0.89 | 0.05 | 0.01 |
| oct18_tau_from_oct27 | held_empty | 0.95 | 0.15 | 0.01 |
| oct18_tau_from_oct27 | fan | 1.00 | 0.02 | 0.00 |
| oct18_tau_from_oct27 | s1_two_people_1730 | 0.85 | 0.58 | 0.09 |
| oct18_tau_from_oct27 | AUC s1_two_people_1730 | | 0.77 [0.66, 0.87] (n=725/101) | 0.49 [0.48, 0.60] (n=725/101) |
| oct27_tau_from_oct18 | calib_empty | 0.00 | 0.06 | 0.06 |
| oct27_tau_from_oct18 | fan | 0.31 | 0.15 | 0.07 |
| oct27_tau_from_oct18 | s1_still_1936 | 0.40 | 0.60 | 0.41 |
| oct27_tau_from_oct18 | s7_walking_head_1945 | 0.42 | 0.41 | 0.12 |
| oct27_tau_from_oct18 | AUC s1_still_1936 | | 0.88 [0.84, 0.95] (n=63/103) | 0.59 [0.43, 0.58] (n=63/103) |
| oct27_tau_from_oct18 | AUC s7_walking_head_1945 | | 0.74 [0.56, 0.83] (n=125/103) | 0.37 [0.21, 0.58] (n=125/103) |

## grid/window 64Hz/20s

| recording | class | windows | peak_ratio median (q10-q90) | peak at 33.3 Hz-alias |
|--|--|--|--|--|
| s1_empty_1756 | empty | 6 | 10.79 (8.94-11.58) | 0.00 |
| s1_empty_1802 | empty | 14 | 13.34 (9.79-21.17) | 0.00 |
| s1_fan_2039 | empty_fan | 12 | 11.76 (8.63-16.52) | 0.00 |
| s1_two_people_1730 | two_people | 53 | 10.75 (7.03-16.48) | 0.00 |
| s6_empty_1942 | empty | 6 | 6.43 (4.47-7.72) | 0.00 |
| s5_fan_1938 | empty_fan | 10 | 7.34 (5.25-9.87) | 0.00 |
| s1_still_1936 | still | 3 | 10.23 (9.00-19.64) | 0.00 |
| s7_walking_head_1945 | walking | 9 | 7.72 (5.84-9.95) | 0.00 |
| s8_empty_1953 | empty | 159 | 10.07 (7.53-14.99) | 0.00 |
| s9_empty_2047 | empty | 35 | 8.36 (6.66-14.63) | 0.00 |

| session | fan vs empty | person vs empty | fan vs person |
|--|--|--|--|
| oct18/peak_ratio | 0.47 [0.29, 0.70] (n=12/20) | 0.39 [0.22, 0.54] (n=53/20) | 0.59 [0.47, 0.75] (n=12/53) |
| oct27/peak_ratio | 0.70 [0.37, 0.83] (n=10/6) | 0.82 [0.53, 0.90] (n=12/6) | 0.33 [0.12, 0.64] (n=10/12) |

Empty-vs-empty control (C4): passes=False, worst symmetric upper bound 0.98 (limit 0.65).
Label threshold tau fitted on the other session: {oct18: 14.78, oct27: 4.90}.

| veto test | class | mechanical share | detector flag rate | with veto |
|--|--|--|--|--|
| oct18_tau_from_oct27 | calib_empty | 1.00 | 0.05 | 0.01 |
| oct18_tau_from_oct27 | held_empty | 1.00 | 0.15 | 0.02 |
| oct18_tau_from_oct27 | fan | 1.00 | 0.02 | 0.00 |
| oct18_tau_from_oct27 | s1_two_people_1730 | 1.00 | 0.58 | 0.02 |
| oct18_tau_from_oct27 | AUC s1_two_people_1730 | | 0.77 [0.66, 0.88] (n=725/101) | 0.41 [0.42, 0.52] (n=725/101) |
| oct27_tau_from_oct18 | calib_empty | 0.00 | 0.06 | 0.06 |
| oct27_tau_from_oct18 | fan | 0.00 | 0.15 | 0.15 |
| oct27_tau_from_oct18 | s1_still_1936 | 0.33 | 0.60 | 0.51 |
| oct27_tau_from_oct18 | s7_walking_head_1945 | 0.00 | 0.41 | 0.41 |
| oct27_tau_from_oct18 | AUC s1_still_1936 | | 0.88 [0.88, 0.92] (n=63/103) | 0.70 [0.69, 0.74] (n=63/103) |
| oct27_tau_from_oct18 | AUC s7_walking_head_1945 | | 0.74 [0.57, 0.80] (n=125/103) | 0.74 [0.57, 0.80] (n=125/103) |

## grid/window 100Hz/10s

| recording | class | windows | peak_ratio median (q10-q90) | peak at 33.3 Hz-alias |
|--|--|--|--|--|
| s1_empty_1756 | empty | 14 | 10.41 (6.85-15.06) | 0.00 |
| s1_empty_1802 | empty | 28 | 10.62 (6.87-14.03) | 0.00 |
| s1_fan_2039 | empty_fan | 26 | 8.80 (6.60-11.47) | 0.00 |
| s1_two_people_1730 | two_people | 107 | 8.69 (6.23-14.33) | 0.00 |
| s6_empty_1942 | empty | 14 | 5.80 (5.03-6.44) | 0.00 |
| s5_fan_1938 | empty_fan | 20 | 5.91 (4.74-8.62) | 0.00 |
| s1_still_1936 | still | 8 | 7.80 (5.35-14.15) | 0.00 |
| s7_walking_head_1945 | walking | 18 | 7.54 (5.46-9.84) | 0.00 |
| s8_empty_1953 | empty | 319 | 7.92 (5.69-11.01) | 0.00 |
| s9_empty_2047 | empty | 71 | 6.44 (5.06-9.64) | 0.00 |

| session | fan vs empty | person vs empty | fan vs person |
|--|--|--|--|
| oct18/peak_ratio | 0.32 [0.22, 0.47] (n=26/42) | 0.38 [0.30, 0.49] (n=107/42) | 0.47 [0.35, 0.59] (n=26/107) |
| oct27/peak_ratio | 0.55 [0.37, 0.74] (n=20/14) | 0.79 [0.60, 0.89] (n=26/14) | 0.31 [0.19, 0.49] (n=20/26) |

Empty-vs-empty control (C4): passes=False, worst symmetric upper bound 1.00 (limit 0.65).
Label threshold tau fitted on the other session: {oct18: 7.07, oct27: 18.34}.

| veto test | class | mechanical share | detector flag rate | with veto |
|--|--|--|--|--|
| oct18_tau_from_oct27 | calib_empty | 0.00 | 0.05 | 0.05 |
| oct18_tau_from_oct27 | held_empty | 0.00 | 0.15 | 0.15 |
| oct18_tau_from_oct27 | fan | 0.00 | 0.02 | 0.02 |
| oct18_tau_from_oct27 | s1_two_people_1730 | 0.02 | 0.58 | 0.57 |
| oct18_tau_from_oct27 | AUC s1_two_people_1730 | | 0.77 [0.69, 0.86] (n=725/101) | 0.75 [0.67, 0.84] (n=725/101) |
| oct27_tau_from_oct18 | calib_empty | 0.07 | 0.06 | 0.05 |
| oct27_tau_from_oct18 | fan | 0.35 | 0.15 | 0.09 |
| oct27_tau_from_oct18 | s1_still_1936 | 0.50 | 0.60 | 0.33 |
| oct27_tau_from_oct18 | s7_walking_head_1945 | 0.56 | 0.41 | 0.12 |
| oct27_tau_from_oct18 | AUC s1_still_1936 | | 0.88 [0.80, 0.96] (n=63/103) | 0.50 [0.08, 0.57] (n=63/103) |
| oct27_tau_from_oct18 | AUC s7_walking_head_1945 | | 0.74 [0.56, 0.84] (n=125/103) | 0.34 [0.21, 0.46] (n=125/103) |

## grid/window 100Hz/15s

| recording | class | windows | peak_ratio median (q10-q90) | peak at 33.3 Hz-alias |
|--|--|--|--|--|
| s1_empty_1756 | empty | 9 | 9.61 (8.29-11.25) | 0.00 |
| s1_empty_1802 | empty | 18 | 9.90 (8.38-16.27) | 0.00 |
| s1_fan_2039 | empty_fan | 17 | 8.84 (7.62-11.36) | 0.00 |
| s1_two_people_1730 | two_people | 71 | 9.33 (7.58-15.85) | 0.00 |
| s6_empty_1942 | empty | 9 | 6.83 (5.87-7.07) | 0.00 |
| s5_fan_1938 | empty_fan | 13 | 6.80 (5.14-11.70) | 0.00 |
| s1_still_1936 | still | 5 | 9.54 (6.96-13.10) | 0.00 |
| s7_walking_head_1945 | walking | 12 | 8.67 (6.14-11.81) | 0.00 |
| s8_empty_1953 | empty | 212 | 8.93 (6.56-12.50) | 0.00 |
| s9_empty_2047 | empty | 47 | 7.11 (5.58-10.04) | 0.00 |

| session | fan vs empty | person vs empty | fan vs person |
|--|--|--|--|
| oct18/peak_ratio | 0.36 [0.23, 0.62] (n=17/27) | 0.44 [0.34, 0.57] (n=71/27) | 0.44 [0.33, 0.59] (n=17/71) |
| oct27/peak_ratio | 0.53 [0.32, 0.74] (n=13/9) | 0.81 [0.59, 0.92] (n=17/9) | 0.35 [0.21, 0.60] (n=13/17) |

Empty-vs-empty control (C4): passes=False, worst symmetric upper bound 1.00 (limit 0.65).
Label threshold tau fitted on the other session: {oct18: 7.40, oct27: 18.06}.

| veto test | class | mechanical share | detector flag rate | with veto |
|--|--|--|--|--|
| oct18_tau_from_oct27 | calib_empty | 0.00 | 0.05 | 0.05 |
| oct18_tau_from_oct27 | held_empty | 0.00 | 0.15 | 0.15 |
| oct18_tau_from_oct27 | fan | 0.00 | 0.02 | 0.02 |
| oct18_tau_from_oct27 | s1_two_people_1730 | 0.06 | 0.58 | 0.56 |
| oct18_tau_from_oct27 | AUC s1_two_people_1730 | | 0.77 [0.66, 0.87] (n=725/101) | 0.74 [0.64, 0.84] (n=725/101) |
| oct27_tau_from_oct18 | calib_empty | 0.00 | 0.06 | 0.06 |
| oct27_tau_from_oct18 | fan | 0.46 | 0.15 | 0.04 |
| oct27_tau_from_oct18 | s1_still_1936 | 0.80 | 0.60 | 0.22 |
| oct27_tau_from_oct18 | s7_walking_head_1945 | 0.67 | 0.41 | 0.08 |
| oct27_tau_from_oct18 | AUC s1_still_1936 | | 0.88 [0.84, 0.95] (n=63/103) | 0.31 [0.00, 0.26] (n=63/103) |
| oct27_tau_from_oct18 | AUC s7_walking_head_1945 | | 0.74 [0.56, 0.83] (n=125/103) | 0.22 [0.08, 0.40] (n=125/103) |

## grid/window 100Hz/20s

| recording | class | windows | peak_ratio median (q10-q90) | peak at 33.3 Hz-alias |
|--|--|--|--|--|
| s1_empty_1756 | empty | 6 | 10.61 (9.24-11.41) | 0.00 |
| s1_empty_1802 | empty | 13 | 14.24 (8.36-21.19) | 0.00 |
| s1_fan_2039 | empty_fan | 12 | 10.79 (7.82-17.30) | 0.00 |
| s1_two_people_1730 | two_people | 53 | 10.29 (7.20-16.94) | 0.00 |
| s6_empty_1942 | empty | 6 | 6.39 (4.88-7.61) | 0.00 |
| s5_fan_1938 | empty_fan | 10 | 7.31 (6.13-9.67) | 0.00 |
| s1_still_1936 | still | 3 | 10.29 (9.59-20.65) | 0.00 |
| s7_walking_head_1945 | walking | 9 | 8.20 (6.11-9.49) | 0.00 |
| s8_empty_1953 | empty | 159 | 9.47 (7.34-13.66) | 0.00 |
| s9_empty_2047 | empty | 35 | 8.06 (6.54-10.29) | 0.00 |

| session | fan vs empty | person vs empty | fan vs person |
|--|--|--|--|
| oct18/peak_ratio | 0.43 [0.28, 0.61] (n=12/19) | 0.39 [0.23, 0.55] (n=53/19) | 0.57 [0.44, 0.71] (n=12/53) |
| oct27/peak_ratio | 0.72 [0.38, 0.90] (n=10/6) | 0.89 [0.62, 1.00] (n=12/6) | 0.32 [0.10, 0.63] (n=10/12) |

Empty-vs-empty control (C4): passes=False, worst symmetric upper bound 1.00 (limit 0.65).
Label threshold tau fitted on the other session: {oct18: 14.75, oct27: 6.22}.

| veto test | class | mechanical share | detector flag rate | with veto |
|--|--|--|--|--|
| oct18_tau_from_oct27 | calib_empty | 1.00 | 0.05 | 0.01 |
| oct18_tau_from_oct27 | held_empty | 1.00 | 0.15 | 0.03 |
| oct18_tau_from_oct27 | fan | 1.00 | 0.02 | 0.00 |
| oct18_tau_from_oct27 | s1_two_people_1730 | 0.98 | 0.58 | 0.04 |
| oct18_tau_from_oct27 | AUC s1_two_people_1730 | | 0.77 [0.66, 0.88] (n=725/101) | 0.43 [0.43, 0.53] (n=725/101) |
| oct27_tau_from_oct18 | calib_empty | 0.00 | 0.06 | 0.06 |
| oct27_tau_from_oct18 | fan | 0.00 | 0.15 | 0.15 |
| oct27_tau_from_oct18 | s1_still_1936 | 0.33 | 0.60 | 0.51 |
| oct27_tau_from_oct18 | s7_walking_head_1945 | 0.00 | 0.41 | 0.41 |
| oct27_tau_from_oct18 | AUC s1_still_1936 | | 0.88 [0.88, 0.92] (n=63/103) | 0.70 [0.69, 0.74] (n=63/103) |
| oct27_tau_from_oct18 | AUC s7_walking_head_1945 | | 0.74 [0.57, 0.80] (n=125/103) | 0.74 [0.57, 0.80] (n=125/103) |

