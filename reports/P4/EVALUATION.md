# Synthetic evaluation

Exact accepted P3 archive versus installed P4. Reported tokens are fixture constants, not measured live-model use. Time is local wall time, not a general performance claim. Three repeats per positive scenario; raw rows retained.

| Policy | Scenario | Correct runs | max Coding/Main bytes | calls | total input bytes | reported tokens | unknown usage | rotations | wall seconds |
|---|---|---|---|---|---|---|---|---|---|
| P3 | simple | 3/3 | 4061/7415 | 13 | 56310 | 234 | 0 | 0 | 0.747 |
| P3 | pressure | 3/3 | 23668/7414 | 21 | 229174 | 378 | 0 | 0 | 0.968 |
| P3 | failure | 0/1 | 4059/8168 | 13 | 59255 | 234 | 0 | 0 | 0.705 |
| P4 | simple | 3/3 | 3925/7461 | 9 | 42765 | 162 | 0 | 0 | 0.555 |
| P4 | pressure | 3/3 | 13034/7461 | 17 | 106861 | 306 | 0 | 2 | 0.896 |
| P4 | failure | 0/1 | 4637/3986 | 11 | 44213 | 198 | 0 | 0 | 1.266 |

Failure rows must remain non-success. Aggregate input/call values and elapsed time show the first repeat; maxima cover all repeats. Software fixtures establish bounded orchestration, not model quality. Live token/speed benefit NOT_ESTABLISHED.
