# PS-FIX-37 — frame alternation and parity (measured from recordings)

**Source:** the multi-node recordings in `data/datasets/room1` (read-only, via the repo loader). NOT `data/sessions/` (that folder holds dashboard session summaries and is never read here).

## Preprocessing behind every lag figure

Four variants are reported so that figures from different preprocessings are never compared by accident:

* **raw** — cosine of the raw amplitude vectors (nothing removed: the static channel dominates, so every lag is ~1)
* **shape** — each frame's own mean over subcarriers removed (Pearson across subcarriers); the static spectral SHAPE is kept
* **timedemean** — each frame divided by its own mean, then the per-subcarrier TIME mean removed (static channel gone). This is the primary variant and the one behind the ~0 lag-1 figure quoted earlier
* **highpass** — timedemean, plus a centred ~1 s moving mean removed (slow drift cannot masquerade as structure)

Tables 1–2 use `timedemean` (and `hp` = `highpass`). Table 0 shows all four side by side.

## Table 0 — median lag cosine by preprocessing (median over recordings)

| node | raw lag1 / lag2 / lag3 | shape lag1 / lag2 / lag3 | timedemean lag1 / lag2 / lag3 | highpass lag1 / lag2 / lag3 |
|--|--|--|--|--|
| N1 | 0.9880 / 0.9914 / 0.9882 | 0.7140 / 0.7735 / 0.7140 | -0.0195 / 0.4438 / 0.0213 | -0.1712 / 0.2880 / -0.1325 |
| N2 | 0.9850 / 0.9913 / 0.9849 | 0.8157 / 0.8685 / 0.8213 | -0.1890 / 0.4536 / -0.1478 | -0.2790 / 0.4120 / -0.2358 |
| N3 | 0.9811 / 0.9865 / 0.9813 | 0.7447 / 0.8266 / 0.7502 | 0.0201 / 0.4496 / 0.0629 | -0.2204 / 0.3584 / -0.1336 |
| N4 | 0.9824 / 0.9861 / 0.9820 | 0.7101 / 0.8379 / 0.7130 | -0.0218 / 0.4556 / 0.0432 | -0.1237 / 0.2760 / -0.0689 |

### Table 0b — session s6 (the session of the reviewer's figures), lag1 / lag2 / lag3 by preprocessing

| node | raw | shape | timedemean | highpass |
|--|--|--|--|--|
| N1 | 0.995 / 0.996 / 0.996 | 0.919 / 0.932 / 0.921 | -0.175 / 0.172 / -0.131 | -0.191 / 0.161 / -0.147 |
| N2 | 0.996 / 0.997 / 0.996 | 0.910 / 0.935 / 0.912 | -0.307 / 0.305 / -0.254 | -0.300 / 0.301 / -0.249 |
| N3 | 0.990 / 0.994 / 0.991 | 0.716 / 0.821 / 0.736 | -0.412 / 0.377 / -0.306 | -0.416 / 0.371 / -0.311 |
| N4 | 0.987 / 0.989 / 0.988 | 0.839 / 0.874 / 0.855 | -0.063 / 0.138 / 0.030 | -0.088 / 0.125 / 0.010 |

Reading: a reviewer figure of the form "N3 lag-1 0.72, lag-2 0.82" is reproduced by the `shape` row (per-frame subcarrier mean removed, static spectral shape kept), not by `raw` (about 0.99 everywhere) and not by `timedemean` (negative lag-1). The exact preprocessing of the reviewer's script was not seen `[UNVERIFIED]`; the match is numerical.

A raw or `shape` lag-1 close to 1 is expected for ANY stream (the static channel is common to every frame); only the variants that remove it can show alternation. The alternation test is therefore the DIFFERENCE between lag 2 and lags 1 and 3 in the `timedemean` / `highpass` rows (and, more weakly, in the 4th decimal of `shape`).

Lag columns are the mean cosine between frame t and t+lag (gain-removed, time-demeaned); `Δ21` = lag2 − lag1; `zz` = lag-2 beats BOTH lag-1 and lag-3 by more than 0.01 (an alternation signature); `hp` = high-pass variant. RSSI columns are mean |ΔRSSI| in dB. `decor` ratio = median decor of the same-parity substreams / median decor of all frames (a lag-2 pair is less similar than a lag-1 pair in a smooth process, so a ratio < 1 is evidence of interleaving).

## Table 1 — lag correlation per recording and node

| recording | node | frames | lag1 | lag2 | lag3 | lag4 | Δ21 | zz | hp lag1 / lag2 / lag3 | hp zz |
|--|--|--|--|--|--|--|--|--|--|--|
| room1__s10__still__20261027T212107Z | 1 | 23893 | -0.045 | 0.620 | -0.036 | 0.600 | 0.665 | True | -0.389 / 0.493 / -0.379 | True |
| room1__s10__still__20261027T212107Z | 2 | 23373 | -0.273 | 0.597 | -0.231 | 0.538 | 0.869 | True | -0.411 / 0.553 / -0.361 | True |
| room1__s10__still__20261027T212107Z | 3 | 21581 | 0.034 | 0.294 | 0.088 | 0.248 | 0.260 | True | -0.197 / 0.212 / -0.119 | True |
| room1__s10__still__20261027T212107Z | 4 | 20943 | 0.091 | 0.259 | 0.107 | 0.223 | 0.168 | True | -0.137 / 0.180 / -0.088 | True |
| room1__s1__empty__20261018T175601Z | 1 | 9734 | -0.765 | 0.746 | -0.670 | 0.654 | 1.511 | True | -0.766 / 0.743 / -0.673 | True |
| room1__s1__empty__20261018T175601Z | 2 | 9628 | -0.276 | 0.508 | -0.219 | 0.445 | 0.785 | True | -0.292 / 0.499 / -0.244 | True |
| room1__s1__empty__20261018T175601Z | 3 | 9642 | -0.403 | 0.589 | -0.337 | 0.521 | 0.992 | True | -0.396 / 0.589 / -0.337 | True |
| room1__s1__empty__20261018T175601Z | 4 | 9650 | -0.684 | 0.652 | -0.584 | 0.559 | 1.336 | True | -0.649 / 0.639 / -0.560 | True |
| room1__s1__empty__20261018T180250Z | 1 | 19861 | -0.665 | 0.698 | -0.623 | 0.666 | 1.363 | True | -0.699 / 0.697 / -0.657 | True |
| room1__s1__empty__20261018T180250Z | 2 | 19657 | -0.108 | 0.429 | -0.079 | 0.411 | 0.537 | True | -0.243 / 0.405 / -0.209 | True |
| room1__s1__empty__20261018T180250Z | 3 | 19639 | -0.400 | 0.560 | -0.365 | 0.531 | 0.961 | True | -0.435 / 0.551 / -0.399 | True |
| room1__s1__empty__20261018T180250Z | 4 | 19749 | -0.726 | 0.738 | -0.676 | 0.690 | 1.464 | True | -0.693 / 0.708 / -0.648 | True |
| room1__s1__empty_fan__20261018T203921Z | 1 | 17077 | -0.021 | 0.356 | 0.028 | 0.313 | 0.377 | True | -0.124 / 0.308 / -0.065 | True |
| room1__s1__empty_fan__20261018T203921Z | 2 | 16998 | -0.355 | 0.502 | -0.226 | 0.396 | 0.857 | True | -0.366 / 0.501 / -0.241 | True |
| room1__s1__empty_fan__20261018T203921Z | 3 | 15598 | 0.058 | 0.453 | 0.170 | 0.367 | 0.394 | True | -0.301 / 0.359 / -0.128 | True |
| room1__s1__empty_fan__20261018T203921Z | 4 | 16771 | -0.568 | 0.528 | -0.373 | 0.372 | 1.095 | True | -0.590 / 0.527 / -0.393 | True |
| room1__s1__still__20261027T193610Z | 1 | 6164 | -0.131 | 0.456 | -0.101 | 0.406 | 0.588 | True | -0.294 / 0.403 / -0.260 | True |
| room1__s1__still__20261027T193610Z | 2 | 6194 | -0.080 | 0.478 | -0.062 | 0.430 | 0.559 | True | -0.215 / 0.419 / -0.198 | True |
| room1__s1__still__20261027T193610Z | 3 | 5536 | 0.218 | 0.519 | 0.253 | 0.440 | 0.300 | True | -0.112 / 0.360 / -0.049 | True |
| room1__s1__still__20261027T193610Z | 4 | 5159 | 0.202 | 0.437 | 0.256 | 0.366 | 0.235 | True | -0.049 / 0.294 / 0.024 | True |
| room1__s1__two_people__20261018T173055Z | 1 | 70710 | 0.015 | 0.651 | 0.048 | 0.621 | 0.636 | True | -0.515 / 0.598 / -0.457 | True |
| room1__s1__two_people__20261018T173055Z | 2 | 70136 | 0.076 | 0.574 | 0.110 | 0.545 | 0.498 | True | -0.449 / 0.538 / -0.386 | True |
| room1__s1__two_people__20261018T173055Z | 3 | 70098 | -0.074 | 0.606 | -0.039 | 0.567 | 0.680 | True | -0.414 / 0.533 / -0.368 | True |
| room1__s1__two_people__20261018T173055Z | 4 | 69856 | -0.146 | 0.526 | -0.097 | 0.484 | 0.672 | True | -0.479 / 0.502 / -0.410 | True |
| room1__s1__walking__20261017T204650Z | 1 | 4720 | 0.551 | 0.452 | 0.391 | 0.342 | -0.100 | False | 0.482 / 0.377 / 0.315 | False |
| room1__s1__walking__20261017T204650Z | 2 | 4923 | 0.355 | 0.282 | 0.237 | 0.186 | -0.073 | False | 0.300 / 0.211 / 0.159 | False |
| room1__s1__walking__20261017T204650Z | 3 | 4841 | 0.464 | 0.365 | 0.296 | 0.241 | -0.099 | False | 0.425 / 0.325 / 0.248 | False |
| room1__s1__walking__20261017T204650Z | 4 | 4916 | 0.565 | 0.474 | 0.427 | 0.378 | -0.092 | False | 0.366 / 0.258 / 0.200 | False |
| room1__s2__still__20261025T195835Z | 1 | 12911 | 0.295 | 0.436 | 0.292 | 0.366 | 0.141 | True | -0.026 / 0.268 / -0.010 | True |
| room1__s2__still__20261025T195835Z | 2 | 14060 | 0.019 | 0.320 | 0.049 | 0.241 | 0.301 | True | -0.099 / 0.264 / -0.063 | True |
| room1__s2__still__20261025T195835Z | 3 | 14309 | 0.211 | 0.452 | 0.171 | 0.354 | 0.241 | True | -0.011 / 0.338 / -0.055 | True |
| room1__s2__still__20261025T195835Z | 4 | 11299 | 0.137 | 0.175 | 0.125 | 0.128 | 0.039 | True | 0.045 / 0.102 / 0.037 | True |
| room1__s3__two_people__20261025T201209Z | 1 | 12326 | 0.591 | 0.610 | 0.574 | 0.592 | 0.019 | True | 0.099 / 0.121 / 0.037 | True |
| room1__s3__two_people__20261025T201209Z | 2 | 16117 | 0.131 | 0.287 | 0.140 | 0.271 | 0.156 | True | 0.000 / 0.208 / 0.012 | True |
| room1__s3__two_people__20261025T201209Z | 3 | 16269 | 0.141 | 0.212 | 0.113 | 0.204 | 0.071 | True | 0.014 / 0.113 / -0.016 | True |
| room1__s3__two_people__20261025T201209Z | 4 | 13054 | 0.051 | 0.125 | 0.056 | 0.105 | 0.073 | True | -0.056 / 0.038 / -0.047 | True |
| room1__s5__empty_fan__20261027T193823Z | 1 | 12747 | -0.187 | 0.218 | -0.147 | 0.180 | 0.404 | True | -0.221 / 0.201 / -0.180 | True |
| room1__s5__empty_fan__20261027T193823Z | 2 | 12946 | -0.253 | 0.312 | -0.217 | 0.282 | 0.565 | True | -0.266 / 0.303 / -0.231 | True |
| room1__s5__empty_fan__20261027T193823Z | 3 | 12198 | -0.293 | 0.337 | -0.211 | 0.268 | 0.630 | True | -0.325 / 0.331 / -0.242 | True |
| room1__s5__empty_fan__20261027T193823Z | 4 | 9787 | 0.019 | 0.126 | 0.078 | 0.105 | 0.107 | True | -0.028 / 0.113 / 0.039 | True |
| room1__s6__empty__20261027T194207Z | 1 | 9939 | -0.175 | 0.172 | -0.131 | 0.140 | 0.346 | True | -0.191 / 0.161 / -0.147 | True |
| room1__s6__empty__20261027T194207Z | 2 | 10161 | -0.307 | 0.305 | -0.254 | 0.261 | 0.612 | True | -0.300 / 0.301 / -0.249 | True |
| room1__s6__empty__20261027T194207Z | 3 | 9161 | -0.412 | 0.377 | -0.306 | 0.289 | 0.789 | True | -0.416 / 0.371 / -0.311 | True |
| room1__s6__empty__20261027T194207Z | 4 | 8188 | -0.063 | 0.138 | 0.030 | 0.086 | 0.201 | True | -0.088 / 0.125 / 0.010 | True |
| room1__s7__walking__20261027T194537Z | 1 | 13737 | -0.018 | 0.302 | 0.014 | 0.237 | 0.320 | True | -0.152 / 0.218 / -0.118 | True |
| room1__s7__walking__20261027T194537Z | 2 | 14356 | -0.192 | 0.360 | -0.123 | 0.283 | 0.552 | True | -0.264 / 0.317 / -0.191 | True |
| room1__s7__walking__20261027T194537Z | 3 | 12457 | -0.031 | 0.453 | 0.037 | 0.353 | 0.484 | True | -0.244 / 0.358 / -0.163 | True |
| room1__s7__walking__20261027T194537Z | 4 | 12940 | 0.040 | 0.328 | 0.091 | 0.241 | 0.288 | True | -0.110 / 0.236 / -0.050 | True |
| room1__s8__empty__20261027T195356Z | 1 | 145595 | 0.120 | 0.283 | 0.153 | 0.260 | 0.162 | True | 0.035 / 0.207 / 0.069 | True |
| room1__s8__empty__20261027T195356Z | 2 | 214319 | -0.186 | 0.515 | -0.173 | 0.484 | 0.701 | True | -0.462 / 0.500 / -0.445 | True |
| room1__s8__empty__20261027T195356Z | 3 | 210311 | 0.006 | 0.448 | 0.035 | 0.412 | 0.442 | True | -0.172 / 0.383 / -0.139 | True |
| room1__s8__empty__20261027T195356Z | 4 | 207255 | -0.332 | 0.494 | -0.251 | 0.410 | 0.826 | True | -0.500 / 0.507 / -0.413 | True |
| room1__s9__empty__20261027T204759Z | 1 | 34344 | 0.014 | 0.197 | 0.067 | 0.164 | 0.183 | True | -0.023 / 0.179 / 0.036 | True |
| room1__s9__empty__20261027T204759Z | 2 | 48964 | -0.343 | 0.540 | -0.296 | 0.455 | 0.883 | True | -0.459 / 0.510 / -0.404 | True |
| room1__s9__empty__20261027T204759Z | 3 | 47532 | 0.250 | 0.376 | 0.176 | 0.313 | 0.126 | True | 0.032 / 0.314 / -0.027 | True |
| room1__s9__empty__20261027T204759Z | 4 | 47875 | -0.375 | 0.566 | -0.307 | 0.466 | 0.942 | True | -0.450 / 0.533 / -0.396 | True |

## Table 2 — RSSI steps, decor on parity substreams, inter-frame gaps

| recording | node | \|ΔRSSI\| lag1 / lag2 / lag3 dB | decor all | decor even / odd | ratio | gap share <5 / 5-15 / 15-30 / 30-60 / ≥60 ms |
|--|--|--|--|--|--|--|
| room1__s10__still__20261027T212107Z | 1 | 5.02 / 2.81 / 5.03 | 0.322 | 0.121 / 0.137 | 0.40 | 0.01 / 0.42 / 0.56 / 0.01 / 0.00 |
| room1__s10__still__20261027T212107Z | 2 | 3.80 / 2.32 / 3.85 | 1.005 | 0.280 / 0.263 | 0.27 | 0.01 / 0.40 / 0.58 / 0.01 / 0.00 |
| room1__s10__still__20261027T212107Z | 3 | 2.36 / 1.71 / 2.24 | 0.214 | 0.176 / 0.161 | 0.79 | 0.02 / 0.37 / 0.56 / 0.05 / 0.00 |
| room1__s10__still__20261027T212107Z | 4 | 3.43 / 2.35 / 3.22 | 0.095 | 0.078 / 0.080 | 0.83 | 0.01 / 0.36 / 0.57 / 0.06 / 0.00 |
| room1__s1__empty__20261018T175601Z | 1 | 8.82 / 1.99 / 8.44 | 1.339 | 0.211 / 0.209 | 0.16 | 0.02 / 0.40 / 0.57 / 0.01 / 0.00 |
| room1__s1__empty__20261018T175601Z | 2 | 0.58 / 0.56 / 0.58 | 0.166 | 0.144 / 0.133 | 0.83 | 0.02 / 0.39 / 0.57 / 0.02 / 0.00 |
| room1__s1__empty__20261018T175601Z | 3 | 0.64 / 0.60 / 0.64 | 0.209 | 0.141 / 0.133 | 0.65 | 0.03 / 0.39 / 0.56 / 0.02 / 0.00 |
| room1__s1__empty__20261018T175601Z | 4 | 1.41 / 1.10 / 1.40 | 0.258 | 0.113 / 0.120 | 0.45 | 0.04 / 0.39 / 0.55 / 0.02 / 0.00 |
| room1__s1__empty__20261018T180250Z | 1 | 9.84 / 2.13 / 9.67 | 1.207 | 0.231 / 0.228 | 0.19 | 0.05 / 0.42 / 0.51 / 0.02 / 0.00 |
| room1__s1__empty__20261018T180250Z | 2 | 0.70 / 0.62 / 0.72 | 0.156 | 0.128 / 0.141 | 0.86 | 0.05 / 0.42 / 0.50 / 0.02 / 0.00 |
| room1__s1__empty__20261018T180250Z | 3 | 1.09 / 0.78 / 1.07 | 0.300 | 0.160 / 0.164 | 0.54 | 0.06 / 0.42 / 0.50 / 0.03 / 0.00 |
| room1__s1__empty__20261018T180250Z | 4 | 2.03 / 1.27 / 2.01 | 0.324 | 0.104 / 0.111 | 0.33 | 0.06 / 0.41 / 0.49 / 0.03 / 0.00 |
| room1__s1__empty_fan__20261018T203921Z | 1 | 2.28 / 1.84 / 2.27 | 0.163 | 0.115 / 0.119 | 0.72 | 0.04 / 0.41 / 0.51 / 0.04 / 0.00 |
| room1__s1__empty_fan__20261018T203921Z | 2 | 2.23 / 1.33 / 2.12 | 0.351 | 0.194 / 0.205 | 0.57 | 0.02 / 0.42 / 0.53 / 0.03 / 0.00 |
| room1__s1__empty_fan__20261018T203921Z | 3 | 2.59 / 1.64 / 2.32 | 0.163 | 0.122 / 0.126 | 0.76 | 0.04 / 0.36 / 0.50 / 0.09 / 0.00 |
| room1__s1__empty_fan__20261018T203921Z | 4 | 1.55 / 0.89 / 1.50 | 0.511 | 0.222 / 0.224 | 0.44 | 0.03 / 0.40 / 0.53 / 0.04 / 0.00 |
| room1__s1__still__20261027T193610Z | 1 | 8.57 / 3.54 / 8.38 | 0.154 | 0.088 / 0.085 | 0.56 | 0.01 / 0.43 / 0.55 / 0.01 / 0.00 |
| room1__s1__still__20261027T193610Z | 2 | 2.45 / 0.93 / 2.38 | 0.138 | 0.080 / 0.088 | 0.61 | 0.01 / 0.41 / 0.57 / 0.01 / 0.00 |
| room1__s1__still__20261027T193610Z | 3 | 3.63 / 1.67 / 3.28 | 0.218 | 0.138 / 0.122 | 0.60 | 0.10 / 0.34 / 0.51 / 0.04 / 0.01 |
| room1__s1__still__20261027T193610Z | 4 | 3.73 / 2.30 / 3.36 | 0.281 | 0.162 / 0.202 | 0.65 | 0.02 / 0.32 / 0.55 / 0.11 / 0.00 |
| room1__s1__two_people__20261018T173055Z | 1 | 5.42 / 2.44 / 5.26 | 0.722 | 0.231 / 0.226 | 0.32 | 0.02 / 0.42 / 0.54 / 0.01 / 0.00 |
| room1__s1__two_people__20261018T173055Z | 2 | 3.06 / 1.16 / 2.95 | 0.312 | 0.103 / 0.103 | 0.33 | 0.03 / 0.41 / 0.54 / 0.02 / 0.00 |
| room1__s1__two_people__20261018T173055Z | 3 | 4.31 / 1.22 / 4.12 | 0.296 | 0.092 / 0.092 | 0.31 | 0.04 / 0.41 / 0.53 / 0.02 / 0.00 |
| room1__s1__two_people__20261018T173055Z | 4 | 1.67 / 0.66 / 1.60 | 0.308 | 0.116 / 0.114 | 0.37 | 0.04 / 0.41 / 0.52 / 0.03 / 0.00 |
| room1__s1__walking__20261017T204650Z | 1 | 3.43 / 3.68 / 3.84 | 0.139 | n/a / n/a | n/a | 0.01 / 0.06 / 0.69 / 0.09 / 0.15 |
| room1__s1__walking__20261017T204650Z | 2 | 2.63 / 2.76 / 2.82 | 0.263 | n/a / n/a | n/a | 0.03 / 0.05 / 0.65 / 0.10 / 0.16 |
| room1__s1__walking__20261017T204650Z | 3 | 1.57 / 1.66 / 1.72 | 0.238 | n/a / n/a | n/a | 0.01 / 0.04 / 0.70 / 0.09 / 0.16 |
| room1__s1__walking__20261017T204650Z | 4 | 2.78 / 2.98 / 3.08 | 0.183 | n/a / n/a | n/a | 0.02 / 0.07 / 0.65 / 0.11 / 0.16 |
| room1__s2__still__20261025T195835Z | 1 | 4.51 / 3.75 / 4.29 | 0.192 | 0.119 / 0.139 | 0.67 | 0.09 / 0.34 / 0.50 / 0.06 / 0.01 |
| room1__s2__still__20261025T195835Z | 2 | 3.51 / 2.05 / 3.27 | 0.211 | 0.157 / 0.161 | 0.75 | 0.09 / 0.36 / 0.50 / 0.04 / 0.01 |
| room1__s2__still__20261025T195835Z | 3 | 2.40 / 1.70 / 2.58 | 0.148 | 0.103 / 0.114 | 0.73 | 0.09 / 0.38 / 0.48 / 0.04 / 0.01 |
| room1__s2__still__20261025T195835Z | 4 | 1.61 / 1.49 / 1.71 | 0.182 | 0.167 / 0.170 | 0.93 | 0.09 / 0.25 / 0.49 / 0.15 / 0.02 |
| room1__s3__two_people__20261025T201209Z | 1 | 3.82 / 3.51 / 3.72 | 0.299 | 0.273 / 0.276 | 0.92 | 0.02 / 0.31 / 0.51 / 0.15 / 0.01 |
| room1__s3__two_people__20261025T201209Z | 2 | 0.79 / 0.65 / 0.77 | 0.221 | 0.186 / 0.174 | 0.82 | 0.03 / 0.45 / 0.50 / 0.02 / 0.00 |
| room1__s3__two_people__20261025T201209Z | 3 | 2.05 / 1.78 / 1.95 | 0.139 | 0.126 / 0.114 | 0.86 | 0.03 / 0.45 / 0.51 / 0.01 / 0.00 |
| room1__s3__two_people__20261025T201209Z | 4 | 0.95 / 0.96 / 1.01 | 0.125 | 0.122 / 0.122 | 0.98 | 0.02 / 0.33 / 0.51 / 0.13 / 0.00 |
| room1__s5__empty_fan__20261027T193823Z | 1 | 5.78 / 4.21 / 5.71 | 0.077 | 0.066 / 0.062 | 0.84 | 0.05 / 0.40 / 0.52 / 0.04 / 0.01 |
| room1__s5__empty_fan__20261027T193823Z | 2 | 1.67 / 0.90 / 1.61 | 0.078 | 0.054 / 0.053 | 0.68 | 0.04 / 0.40 / 0.53 / 0.02 / 0.01 |
| room1__s5__empty_fan__20261027T193823Z | 3 | 3.89 / 1.52 / 3.59 | 0.148 | 0.100 / 0.093 | 0.65 | 0.07 / 0.37 / 0.51 / 0.04 / 0.01 |
| room1__s5__empty_fan__20261027T193823Z | 4 | 5.30 / 4.06 / 4.69 | 0.112 | 0.097 / 0.095 | 0.85 | 0.05 / 0.26 / 0.48 / 0.20 / 0.01 |
| room1__s6__empty__20261027T194207Z | 1 | 5.82 / 4.27 / 5.76 | 0.081 | 0.066 / 0.069 | 0.83 | 0.06 / 0.42 / 0.48 / 0.04 / 0.00 |
| room1__s6__empty__20261027T194207Z | 2 | 1.99 / 1.09 / 1.87 | 0.090 | 0.067 / 0.062 | 0.72 | 0.05 / 0.44 / 0.49 / 0.03 / 0.00 |
| room1__s6__empty__20261027T194207Z | 3 | 4.24 / 1.83 / 3.88 | 0.282 | 0.172 / 0.175 | 0.62 | 0.22 / 0.34 / 0.38 / 0.05 / 0.01 |
| room1__s6__empty__20261027T194207Z | 4 | 5.69 / 3.77 / 4.86 | 0.162 | 0.125 / 0.124 | 0.77 | 0.05 / 0.32 / 0.48 / 0.15 / 0.00 |
| room1__s7__walking__20261027T194537Z | 1 | 6.44 / 4.01 / 6.16 | 0.141 | 0.124 / 0.120 | 0.87 | 0.06 / 0.43 / 0.47 / 0.03 / 0.00 |
| room1__s7__walking__20261027T194537Z | 2 | 2.30 / 1.06 / 2.13 | 0.142 | 0.094 / 0.099 | 0.68 | 0.05 / 0.46 / 0.48 / 0.02 / 0.00 |
| room1__s7__walking__20261027T194537Z | 3 | 3.71 / 1.82 / 3.42 | 0.255 | 0.138 / 0.141 | 0.55 | 0.20 / 0.35 / 0.37 / 0.06 / 0.02 |
| room1__s7__walking__20261027T194537Z | 4 | 4.27 / 2.35 / 3.80 | 0.269 | 0.217 / 0.198 | 0.77 | 0.06 / 0.39 / 0.48 / 0.07 / 0.00 |
| room1__s8__empty__20261027T195356Z | 1 | 0.88 / 0.78 / 0.84 | 0.347 | 0.316 / 0.311 | 0.90 | 0.01 / 0.23 / 0.49 / 0.27 / 0.00 |
| room1__s8__empty__20261027T195356Z | 2 | 2.43 / 0.60 / 2.37 | 0.151 | 0.070 / 0.069 | 0.46 | 0.02 / 0.45 / 0.53 / 0.01 / 0.00 |
| room1__s8__empty__20261027T195356Z | 3 | 5.63 / 2.29 / 5.44 | 0.468 | 0.254 / 0.248 | 0.54 | 0.03 / 0.43 / 0.51 / 0.02 / 0.00 |
| room1__s8__empty__20261027T195356Z | 4 | 6.33 / 2.13 / 5.94 | 0.629 | 0.316 / 0.308 | 0.50 | 0.02 / 0.43 / 0.53 / 0.02 / 0.00 |
| room1__s9__empty__20261027T204759Z | 1 | 0.53 / 0.49 / 0.51 | 0.259 | 0.233 / 0.238 | 0.91 | 0.01 / 0.28 / 0.49 / 0.22 / 0.00 |
| room1__s9__empty__20261027T204759Z | 2 | 2.65 / 1.00 / 2.42 | 0.139 | 0.081 / 0.083 | 0.59 | 0.02 / 0.50 / 0.47 / 0.01 / 0.00 |
| room1__s9__empty__20261027T204759Z | 3 | 4.86 / 2.46 / 4.78 | 0.355 | 0.269 / 0.262 | 0.75 | 0.04 / 0.44 / 0.49 / 0.02 / 0.00 |
| room1__s9__empty__20261027T204759Z | 4 | 4.35 / 1.79 / 4.29 | 0.700 | 0.309 / 0.313 | 0.44 | 0.02 / 0.49 / 0.47 / 0.02 / 0.00 |

## Table 3 — summary by node (median over recordings)

| node | recordings | median lag1 / lag2 / lag3 / lag4 | recordings with lag2 > lag1 | zigzag (raw / hp) | median \|ΔRSSI\| lag1 / lag2 | median decor ratio |
|--|--|--|--|--|--|--|
| N1 | 14 | -0.019 / 0.444 / 0.021 / 0.354 | 13 / 14 | 13 / 13 | 5.22 / 3.16 | 0.72 |
| N2 | 14 | -0.189 / 0.454 / -0.148 / 0.404 | 13 / 14 | 13 / 13 | 2.37 / 1.03 | 0.68 |
| N3 | 14 | 0.020 / 0.450 / 0.063 / 0.354 | 13 / 14 | 13 / 13 | 3.11 / 1.68 | 0.65 |
| N4 | 14 | -0.022 / 0.456 / 0.043 / 0.369 | 13 / 14 | 13 / 13 | 3.11 / 1.96 | 0.65 |

## Table 4 — does the same-parity substream remove the empty-vs-empty drift? (AUC of window score, first session vs second)

An AUC near 0.5 would mean the two empties are indistinguishable. Interleaving explains the drift only if the parity columns fall toward 0.5.

| pair / node / feature | all frames | even frames | odd frames |
|--|--|--|--|
| s8_vs_s6/N1/perturb | 0.81 | 0.75 | 0.71 |
| s8_vs_s6/N1/decor | 1.00 | 0.99 | 0.99 |
| s8_vs_s6/N2/perturb | 0.91 | 0.68 | 0.73 |
| s8_vs_s6/N2/decor | 0.88 | 0.55 | 0.58 |
| s8_vs_s6/N3/perturb | 0.97 | 0.92 | 0.92 |
| s8_vs_s6/N3/decor | 0.71 | 0.72 | 0.71 |
| s8_vs_s6/N4/perturb | 1.00 | 0.96 | 0.95 |
| s8_vs_s6/N4/decor | 1.00 | 0.94 | 0.95 |
| s9_vs_s6/N1/perturb | 0.69 | 0.66 | 0.58 |
| s9_vs_s6/N1/decor | 1.00 | 0.99 | 0.99 |
| s9_vs_s6/N2/perturb | 0.96 | 0.89 | 0.88 |
| s9_vs_s6/N2/decor | 0.98 | 0.69 | 0.76 |
| s9_vs_s6/N3/perturb | 0.99 | 0.98 | 0.98 |
| s9_vs_s6/N3/decor | 0.65 | 0.78 | 0.78 |
| s9_vs_s6/N4/perturb | 1.00 | 0.98 | 0.98 |
| s9_vs_s6/N4/decor | 1.00 | 0.96 | 0.96 |
| s9_vs_s8/N1/perturb | 0.40 | 0.44 | 0.40 |
| s9_vs_s8/N1/decor | 0.28 | 0.32 | 0.33 |
| s9_vs_s8/N2/perturb | 0.76 | 0.74 | 0.71 |
| s9_vs_s8/N2/decor | 0.47 | 0.57 | 0.60 |
| s9_vs_s8/N3/perturb | 0.62 | 0.62 | 0.63 |
| s9_vs_s8/N3/decor | 0.37 | 0.54 | 0.55 |
| s9_vs_s8/N4/perturb | 0.60 | 0.50 | 0.53 |
| s9_vs_s8/N4/decor | 0.60 | 0.50 | 0.51 |

## Table 5 — how much of the cross-session empty-vs-empty gap do the parity substreams remove?

Separation = max(AUC, 1−AUC) (0 = indistinguishable, 1 = perfectly separated). Pairs: s8 vs s6 and s9 vs s6. `drop` = separation(all frames) − mean separation(even, odd). A drop above 0.1 is described below as "part of the gap explained"; that cutoff is a reading aid for this report, not a detection threshold.

| node / feature | separation, all frames | separation, parity substreams | drop |
|--|--|--|--|
| N1/perturb | 0.75 | 0.67 | 0.07 |
| N1/decor | 1.00 | 0.99 | 0.01 |
| N2/perturb | 0.94 | 0.79 | 0.14 |
| N2/decor | 0.93 | 0.64 | 0.29 |
| N3/perturb | 0.98 | 0.95 | 0.03 |
| N3/decor | 0.68 | 0.75 | -0.06 |
| N4/perturb | 1.00 | 0.97 | 0.03 |
| N4/decor | 1.00 | 0.95 | 0.05 |

## Conclusion (computed from the tables above)

1. **The interleaving is real:** lag 2 beats BOTH lag 1 and lag 3 (the zigzag) on every node in 13 of 14 recordings; the exception(s): room1__s1__walking__20261017T204650Z. It survives the high-pass variant, so it is not slow drift.
2. **It explains part of the empty-vs-empty gap on some nodes only** (decor, cross-session pairs; drop in separation): part explained on N2 (+0.29); not explained on N1 (+0.01), N3 (-0.06), N4 (+0.05). See Table 5 for perturb as well.
3. **It inflates decor levels:** median decor of a same-parity substream over decor of all frames = N1 0.72, N2 0.68, N3 0.65, N4 0.65 (adjacent frames are of different kinds, so all-frames decor is higher).
4. **No threshold or feature change follows from this.** The presence threshold (0.6), the tier thresholds and every detector are unchanged; this is a measurement of the recordings, not of the firmware's frame types (the header carries no frame type).
5. **Parity-aware decor is to be registered as a candidate** in the pre-registration (`reports/presence-eval-2026-11/PREREG-2026-11-recording-campaign.md`, written in the recording-readiness section; that file does not exist yet) with no number picked. It also motivates PS-FIX-36 (a transmitter / frame-type field in the header).

Limits: t is the recorder host's clock (ms), not a device timestamp; the header has no frame type, rate or transmitter: a parity substream is a statistical probe, not proof of two frame types; the 'empty' recordings have no entry log, so their emptiness is unverified; nothing here changes a threshold or the firmware; nothing is written into data/.
