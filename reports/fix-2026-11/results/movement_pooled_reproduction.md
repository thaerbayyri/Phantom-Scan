# Reproduction of the externally reported pooled self-baseline table

pooled empties s6 + s8 part 1 + s9 part 1, no epochs (as reported externally)

AUC [window-block 95 % CI]; 0.5 = chance. NOT a detection claim; one walking recording; the choice of two lookbacks and four configurations is in-sample.

| config | walking (s7 whole) | walking (head only, no step tail) | still s10 | still s1 | fan s5 | drift control s8p1 vs s6 |
|--|--|--|--|--|--|--|
| N1+N2+N3+N4/decor/raw | 0.17 [0.08, 0.24] | 0.16 [0.06, 0.23] | 0.79 [0.70, 0.89] | 0.16 [0.11, 0.23] | 0.01 [0.00, 0.01] | 1.00 [1.00, 1.00] |
| N1+N2+N3+N4/decor/self/L90 | 0.76 [0.61, 0.91] | 0.72 [0.53, 0.88] | 0.70 [0.59, 0.81] | 0.68 [0.54, 0.77] | 0.23 [0.11, 0.33] | 0.76 [0.65, 0.84] |
| N1+N2/perturb/raw | 0.41 [0.23, 0.54] | 0.34 [0.21, 0.45] | 0.95 [0.92, 0.98] | 0.47 [0.31, 0.61] | 0.15 [0.09, 0.21] | 0.92 [0.88, 0.95] |
| N1+N2/perturb/self/L90 | 0.74 [0.62, 0.87] | 0.69 [0.55, 0.82] | 0.70 [0.59, 0.81] | 0.33 [0.22, 0.43] | 0.52 [0.41, 0.64] | 0.62 [0.53, 0.70] |
| N1+N2+N3+N4/decor/self/L45 | 0.64 [0.47, 0.78] | 0.60 [0.44, 0.74] | 0.74 [0.65, 0.83] | 0.72 [0.59, 0.80] | 0.20 [0.10, 0.27] | 0.84 [0.76, 0.89] |
| N1+N2/perturb/self/L45 | 0.63 [0.49, 0.74] | 0.58 [0.44, 0.69] | 0.67 [0.58, 0.76] | 0.39 [0.28, 0.46] | 0.46 [0.36, 0.57] | 0.62 [0.56, 0.70] |
