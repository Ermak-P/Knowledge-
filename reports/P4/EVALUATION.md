# Synthetic P3/P4 comparison

Predeclared manifest: runs/d68c9865460a4fcbab2bdbaaa466f072/comparison/scenario-manifest.json. Exact accepted P3 package; independent source copies and fixed tests; three repeats for positive cases. Provider usage is synthetic, live quality/benefit NOT_ESTABLISHED. Raw failures are retained.

| Policy | Scenario | Successful runs | max Coding/Main bytes | calls | input bytes | reported tokens | unknown | rotations | seconds |
|---|---|---|---|---|---|---|---|---|---|
| P3 | simple | 3/3 | 4475/7946 | 14 | 57920 | 252 | 0 | 0 | 0.608 |
| P3 | multi-file | 3/3 | 6248/8234 | 14 | 62003 | 252 | 0 | 0 | 0.798 |
| P3 | multi-pressure | 3/3 | 23708/8351 | 24 | 279961 | 432 | 0 | 0 | 1.114 |
| P3 | persistent-failure | 0/1 | 4477/16015 | 34 | 165177 | 612 | 0 | 0 | 1.611 |
| P4 | simple | 3/3 | 5524/10535 | 10 | 64903 | 180 | 0 | 0 | 0.571 |
| P4 | multi-file | 3/3 | 7108/17147 | 15 | 119058 | 270 | 0 | 0 | 0.912 |
| P4 | multi-pressure | 3/3 | 15710/16341 | 25 | 222432 | 450 | 0 | 4 | 1.282 |
| P4 | persistent-failure | 0/1 | 5747/4940 | 10 | 50945 | 180 | 0 | 0 | 1.213 |

Maxima cover all repetitions; other table totals show the first repeat. Persistent failure is expected to remain non-success. Complete per-repeat totals and attempted calls are retained in the raw results.
