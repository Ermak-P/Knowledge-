# Synthetic P3/P4 comparison

Predeclared manifest: runs/df1cbbc388e4417da464fc74fb5ed925/comparison/scenario-manifest.json. Exact accepted P3 package; independent source copies and fixed tests; three repeats for positive cases. Provider usage is synthetic, live quality/benefit NOT_ESTABLISHED. Raw failures are retained.

| Policy | Scenario | Successful runs | max Coding/Main bytes | calls | input bytes | reported tokens | unknown | rotations | seconds |
|---|---|---|---|---|---|---|---|---|---|
| P3 | simple | 3/3 | 4475/7946 | 14 | 57920 | 252 | 0 | 0 | 0.676 |
| P3 | multi-file | 3/3 | 6248/8234 | 14 | 62003 | 252 | 0 | 0 | 0.741 |
| P3 | multi-pressure | 3/3 | 23708/8351 | 24 | 279957 | 432 | 0 | 0 | 1.049 |
| P3 | persistent-failure | 0/1 | 4477/16019 | 34 | 165189 | 612 | 0 | 0 | 1.823 |
| P4 | simple | 3/3 | 5524/10535 | 10 | 64903 | 180 | 0 | 0 | 0.581 |
| P4 | multi-file | 3/3 | 7108/17147 | 15 | 119058 | 270 | 0 | 0 | 0.853 |
| P4 | multi-pressure | 3/3 | 15710/16337 | 25 | 222432 | 450 | 0 | 4 | 1.334 |
| P4 | persistent-failure | 0/1 | 5747/4940 | 10 | 50945 | 180 | 0 | 0 | 1.063 |

Maxima cover all repetitions; other table totals show the first repeat. Persistent failure is expected to remain non-success. Complete per-repeat totals and attempted calls are retained in the raw results.
