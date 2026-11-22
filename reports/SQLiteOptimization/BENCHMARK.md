# Installed baseline → candidate benchmark

Baseline `73a3fc70c5fde17536568baae2a03b1b8be8b8a1`; final source `c7be424142692bbd0bdf4dab60c65dfed09d1c87`. Both official core kits were installed outside the checkout; [baseline byte proof](baseline-install.json), [candidate byte proof](candidate-install.json). No editable/source fallback imports.

All paired operation results match. This is a Linux/Python 3.12.14/SQLite 3.53.1 measurement, with runtime details in every raw sample. Native Windows correctness is qualified separately; no Windows speedup is claimed.

## Method and limits

Warm public API calls use fresh connections and full normal validation. Small read cases have 20 samples after warm-up; medium reads 5, large reads 3. Expensive/state-changing calls have 3 repetitions with same-root quiescent snapshot resets. Baseline/candidate halves are interleaved; raw samples and commands are retained. Median is the usual middle/mean-of-two; p95 is nearest rank `ceil(.95*n)` (therefore the maximum for small n). Three samples establish a bounded observation, not a stable tail-latency guarantee.

Generation, validation of fixtures, reset, index DDL, imports and instrumentation are outside public API timings. Profiles separately count traced SQL, approximate VM steps (1000-step callbacks), `knowledge.util.loads` aliases, record/candidate validators, canonical validation, and Path reads; these are supporting counters, not exclusive CPU-time allocations. No check, sync, lock, journal mode or timeout is disabled. OS disk caches and CPU scheduling were not controlled; fresh processes are not cold disks.

Fixtures are synthetic and validated through normal APIs. Rules have 3 revisions, with a separate 128-revision history; binding counters are revision scoped and predecessor links agree. Queues use valid add-evidence envelopes and historical PREPARED snapshots, real empty acknowledged/committed receipts, and 1/10/100% pending. The rare-COMMITTED fixture has one real committed empty plan. No data/history is deleted for speed, no root identity is rewritten, and baseline/candidate restore identical input hashes at the same temporary root.

The requested matrix is reduced at 100,000 queue rows: fully audited 10,000-row calls already take about 3 seconds on the baseline, with schema/filesystem work for every candidate; repeating all 100,000-row queue variants would multiply that cost. Queue coverage is 1,000/10,000 rows at all requested pending fractions, plus legacy and rare/zero COMMITTED cases. Operational events reach 100,000. Outbox uses 1,000/10,000/30,000 entries with complete owner runs, queued-payload receipts and delivery events; the large case has 10,000 historical runs and only three entries for the selected run. No constant-time queue/current-state claim follows.

Logical comparisons preserve IDs/revisions/authority and compare returned outcomes. Only explicitly volatile `at`, wall_seconds and timing fields are removed from API result hashes. Raw database hashes are also retained; event IDs derived from actual wall clocks can legitimately differ across writes. Integrity/atomicity and complete canonical preservation are independently covered by the tests and [installed compatibility probe](compatibility/result.json).

## Complete operation timings

| Dataset | Operation | n | Baseline median / p95 ms | Default candidate median / p95 ms | Ratio |
| --- | --- | ---: | ---: | ---: | ---: |
| op-32-0 | records | 20 | 19.54 / 25.98 | 14.26 / 22.03 | 1.37× |
| op-32-0 | lookup | 20 | 38.50 / 60.49 | 26.07 / 29.44 | 1.48× |
| op-32-0 | context | 20 | 19.70 / 21.15 | 17.10 / 18.69 | 1.15× |
| op-32-0 | filesystem | 20 | 2.65 / 3.43 | 2.24 / 2.58 | 1.18× |
| op-32-0 | binding-read | 3 | 39.46 / 39.62 | 27.37 / 27.87 | 1.44× |
| op-32-0 | application-read | 3 | 40.25 / 41.46 | 28.18 / 32.77 | 1.43× |
| op-32-1k | records | 20 | 39.79 / 54.06 | 19.80 / 20.93 | 2.01× |
| op-32-1k | lookup | 20 | 62.37 / 76.70 | 39.45 / 46.08 | 1.58× |
| op-32-1k | context | 20 | 26.01 / 28.08 | 23.08 / 24.74 | 1.13× |
| op-32-1k | filesystem | 20 | 2.38 / 3.05 | 2.46 / 3.23 | 0.97× |
| op-32-1k | binding-read | 3 | 74.12 / 79.39 | 38.13 / 40.39 | 1.94× |
| op-32-1k | application-read | 3 | 72.27 / 73.70 | 41.73 / 42.34 | 1.73× |
| op-32-10k | records | 5 | 217.74 / 236.69 | 70.82 / 143.64 | 3.07× |
| op-32-10k | lookup | 5 | 311.20 / 330.29 | 145.67 / 152.91 | 2.14× |
| op-32-10k | context | 5 | 83.68 / 106.91 | 78.42 / 81.92 | 1.07× |
| op-32-10k | filesystem | 5 | 2.25 / 2.61 | 2.62 / 2.88 | 0.86× |
| op-32-10k | binding-read | 3 | 412.68 / 423.27 | 143.83 / 163.50 | 2.87× |
| op-32-10k | application-read | 3 | 356.87 / 361.00 | 147.82 / 149.36 | 2.41× |
| op-256-10k | records | 5 | 466.47 / 478.31 | 103.97 / 165.24 | 4.49× |
| op-256-10k | lookup | 5 | 655.54 / 724.35 | 198.79 / 244.55 | 3.30× |
| op-256-10k | context | 5 | 192.59 / 208.65 | 102.66 / 106.17 | 1.88× |
| op-256-10k | filesystem | 5 | 2.63 / 3.06 | 2.61 / 3.56 | 1.01× |
| op-256-10k | binding-read | 3 | 920.57 / 933.73 | 195.73 / 196.61 | 4.70× |
| op-256-10k | application-read | 3 | 881.94 / 891.98 | 217.73 / 251.76 | 4.05× |
| op-256-100k | records | 3 | 4215.92 / 4275.96 | 625.37 / 643.61 | 6.74× |
| op-256-100k | lookup | 3 | 5849.48 / 5936.53 | 1313.62 / 1316.18 | 4.45× |
| op-256-100k | context | 3 | 1762.43 / 1805.31 | 680.46 / 831.70 | 2.59× |
| op-256-100k | filesystem | 3 | 2.99 / 13.57 | 3.66 / 3.82 | 0.82× |
| op-256-100k | binding-read | 3 | 7919.16 / 7988.89 | 1272.15 / 1299.47 | 6.23× |
| op-256-100k | application-read | 3 | 7512.62 / 7657.92 | 1261.68 / 1326.04 | 5.95× |
| op-long-history | records | 5 | 256.97 / 257.92 | 145.20 / 243.31 | 1.77× |
| op-long-history | lookup | 5 | 406.10 / 516.15 | 268.53 / 319.35 | 1.51× |
| op-long-history | context | 5 | 138.12 / 176.42 | 135.51 / 172.59 | 1.02× |
| op-long-history | filesystem | 5 | 2.24 / 2.74 | 2.69 / 3.31 | 0.83× |
| op-long-history | binding-read | 3 | 504.83 / 505.21 | 258.01 / 264.12 | 1.96× |
| op-long-history | application-read | 3 | 519.78 / 526.23 | 272.68 / 274.20 | 1.91× |
| queue-1k-1 | prepare | 3 | 274.74 / 284.52 | 166.11 / 175.45 | 1.65× |
| queue-1k-1 | recover | 20 | 305.50 / 333.43 | 175.19 / 212.67 | 1.74× |
| queue-1k-1 | duplicate | 20 | 289.66 / 348.39 | 172.30 / 199.11 | 1.68× |
| queue-1k-1 | new | 3 | 293.07 / 320.94 | 183.87 / 210.14 | 1.59× |
| queue-10k-1 | prepare | 3 | 3051.09 / 3258.84 | 1785.81 / 1872.75 | 1.71× |
| queue-10k-1 | recover | 5 | 2937.91 / 3160.86 | 1792.11 / 1887.51 | 1.64× |
| queue-10k-1 | duplicate | 5 | 3100.17 / 3159.42 | 1795.09 / 1924.33 | 1.73× |
| queue-10k-1 | new | 3 | 2874.59 / 2909.41 | 1701.53 / 1792.41 | 1.69× |
| queue-10k-10 | prepare | 3 | 2833.77 / 3202.16 | 1846.19 / 1930.47 | 1.53× |
| queue-10k-10 | recover | 5 | 2818.12 / 2996.26 | 1698.55 / 1806.86 | 1.66× |
| queue-10k-10 | duplicate | 5 | 2892.56 / 2977.11 | 1628.32 / 1841.97 | 1.78× |
| queue-10k-10 | new | 3 | 2932.65 / 3107.22 | 1886.38 / 1934.29 | 1.55× |
| queue-10k-100 | prepare | 3 | 3481.97 / 3579.38 | 2413.12 / 2417.78 | 1.44× |
| queue-10k-100 | recover | 5 | 3065.37 / 3358.22 | 1605.12 / 1884.28 | 1.91× |
| queue-10k-100 | duplicate | 5 | 2921.05 / 3064.96 | 1694.90 / 1794.00 | 1.72× |
| queue-10k-100 | new | 3 | 3079.43 / 3199.62 | 1814.39 / 1916.23 | 1.70× |
| queue-10k-committed | prepare | 3 | 3076.17 / 3137.53 | 1668.07 / 1824.11 | 1.84× |
| queue-10k-committed | recover | 3 | 5713.79 / 6659.55 | 3390.38 / 3505.93 | 1.69× |
| queue-10k-committed | duplicate | 5 | 2885.82 / 3262.10 | 1644.66 / 1694.02 | 1.75× |
| queue-10k-committed | new | 3 | 2819.85 / 2959.12 | 1662.97 / 1729.79 | 1.70× |
| legacy | duplicate | 20 | 4.09 / 4.38 | 4.01 / 7.23 | 1.02× |
| legacy | new | 3 | 5.96 / 6.49 | 5.43 / 6.28 | 1.10× |
| journal-1k | outbox | 20 | 0.81 / 1.07 | 0.96 / 2.47 | 0.85× |
| journal-1k | absent-outbox | 20 | 0.77 / 1.10 | 0.72 / 0.93 | 1.06× |
| journal-1k | status | 20 | 5.29 / 6.17 | 4.17 / 4.50 | 1.27× |
| journal-1k | journal-reads | 20 | 2.93 / 3.44 | 3.12 / 3.37 | 0.94× |
| journal-1k | journal-writes | 3 | 10.62 / 13.08 | 8.80 / 9.37 | 1.21× |
| journal-1k | outbox-write | 3 | 7.91 / 12.20 | 8.90 / 9.34 | 0.89× |
| journal-1k | capture-retry | 3 | 6.53 / 6.66 | 4.73 / 5.65 | 1.38× |
| journal-10k | outbox | 5 | 9.46 / 10.90 | 9.01 / 10.40 | 1.05× |
| journal-10k | absent-outbox | 5 | 9.05 / 10.62 | 9.16 / 9.98 | 0.99× |
| journal-10k | status | 5 | 44.89 / 51.01 | 37.76 / 40.83 | 1.19× |
| journal-10k | journal-reads | 5 | 26.92 / 29.73 | 28.05 / 28.96 | 0.96× |
| journal-10k | journal-writes | 3 | 48.65 / 48.79 | 46.58 / 47.11 | 1.04× |
| journal-10k | outbox-write | 3 | 48.80 / 50.31 | 45.82 / 48.00 | 1.07× |
| journal-10k | capture-retry | 3 | 60.21 / 64.28 | 31.80 / 33.04 | 1.89× |
| journal-30k | outbox | 3 | 28.54 / 36.77 | 26.70 / 28.42 | 1.07× |
| journal-30k | absent-outbox | 3 | 28.17 / 30.36 | 27.67 / 29.11 | 1.02× |
| journal-30k | status | 3 | 146.34 / 159.36 | 121.26 / 121.79 | 1.21× |
| journal-30k | journal-reads | 3 | 89.60 / 93.31 | 92.62 / 112.11 | 0.97× |
| journal-30k | journal-writes | 3 | 144.16 / 149.46 | 136.22 / 153.64 | 1.06× |
| journal-30k | outbox-write | 3 | 121.53 / 124.78 | 126.48 / 178.18 | 0.96× |
| journal-30k | capture-retry | 3 | 169.65 / 177.81 | 102.47 / 104.01 | 1.66× |

`records`, `lookup`, `binding-read` and `application-read` include the full corruption audit. `prepare`, `recover`, duplicate/new submission are real Store APIs. `status` includes Journal construction; journal reads/writes are grouped sequences of public methods; outbox-write inserts/updates a complete delivery payload, records its delivery event and run capture state, then reads through actual APIs. Capture retry uses already delivered outbox entries and performs no new execution effects. Every outbox owner is validated by the normal Journal.load method at generation time; all candidate receipts agree. `context` is the complete facade including source/freshness/dependency/budget work; `filesystem` is an unchanged inventory/analysis component, not a product operation or a claimed SQL gain. Default Journal.outbox/events/action read bodies are unchanged; ratios for those paths include sampling/noise and are not claimed algorithmic gains.

Fresh complete CLI processes (including imports/JSON transport and source checks):

| Dataset | n | Baseline median / p95 ms | Candidate median / p95 ms |
| --- | ---: | ---: | ---: |
| small | 20 | 67.99 / 71.64 | 65.26 / 89.46 |
| large | 5 | 1547.33 / 1621.11 | 690.06 / 750.44 |

## Index tradeoff and write costs

The default creates no additional indexes. The `outbox(run)` profile is opt-in: subset reads improve, but its additional quick_check pages slow unrelated journal calls. The implementation supports normal new-journal initialization with `index_outbox=True` and exact-approved, backed-up upgrade/rollback for existing journals. A run-specific partial index cannot serve arbitrary other/absent runs. Queue/status and plan/status ordinary/partial candidates are excluded: faster subset SQL is dominated by the mandatory full audit.

| Dataset | Operation | Default candidate ms | Opt-in candidate ms | Opt-in / default |
| --- | --- | ---: | ---: | ---: |
| journal-1k | outbox | 0.96 | 0.94 | 0.98 |
| journal-1k | absent-outbox | 0.72 | 0.72 | 0.99 |
| journal-1k | status | 4.17 | 4.14 | 0.99 |
| journal-1k | journal-reads | 3.12 | 3.00 | 0.96 |
| journal-1k | journal-writes | 8.80 | 8.65 | 0.98 |
| journal-1k | outbox-write | 8.90 | 9.19 | 1.03 |
| journal-1k | capture-retry | 4.73 | 5.00 | 1.06 |
| journal-10k | outbox | 9.01 | 7.68 | 0.85 |
| journal-10k | absent-outbox | 9.16 | 7.83 | 0.86 |
| journal-10k | status | 37.76 | 33.69 | 0.89 |
| journal-10k | journal-reads | 28.05 | 26.29 | 0.94 |
| journal-10k | journal-writes | 46.58 | 45.84 | 0.98 |
| journal-10k | outbox-write | 45.82 | 41.48 | 0.91 |
| journal-10k | capture-retry | 31.80 | 30.43 | 0.96 |
| journal-30k | outbox | 26.70 | 25.06 | 0.94 |
| journal-30k | absent-outbox | 27.67 | 22.46 | 0.81 |
| journal-30k | status | 121.26 | 112.95 | 0.93 |
| journal-30k | journal-reads | 92.62 | 89.26 | 0.96 |
| journal-30k | journal-writes | 136.22 | 145.00 | 1.06 |
| journal-30k | outbox-write | 126.48 | 134.08 | 1.06 |
| journal-30k | capture-retry | 102.47 | 91.79 | 0.90 |

These are separate interleaved runs, so small differences include scheduling/fsync noise. The primary write costs appear above (`new`, `prepare`, binding/application-read, journal-writes and outbox-write), with identical initial states. The opt-in index occupies 483,328 bytes on the fully owned 30,000-entry fixture (118 additional 4KiB pages); default storage adds zero index pages. In bounded samples, some indexed write sequences cost more; no universal read/write benefit is claimed. Storage, PRAGMA index_list/index_xinfo, exact plans, valid-row queue/plan INSERT/status UPDATE samples and post-DML validator checks are in [indexes](indexes/); page/freelist/index allocation is in [inventory](inventory/). Outbox INSERT/payload UPDATE costs use the public API scenarios, and its SQL diagnostic is read-only. SQL-only timings do not replace API results.

Full history audits remain linear. FS hashing/extraction is unchanged and independently timed. No inference, real Docker/IPM service, or whole-agent productivity gain is measured. No projection/retention/trust-boundary change is used.

Reproduce with [REPRODUCE.md](REPRODUCE.md). All machine-readable samples are in [benchmarks/results.json](benchmarks/results.json) and [indexed-benchmarks/results.json](indexed-benchmarks/results.json); per-dataset raw files and separate profiles are adjacent. Exploratory/superseded data is excluded from these final tables.

Additional complete prepare calls on the valid 10,000-row / 1%-pending fixture (3 timed repetitions each):

| Variant | Median ms |
| --- | ---: |
| no extra index (main interleaved run) | 1785.81 |
| ordinary | 1662.60 |
| partial | 1711.18 |

These short runs are not evidence that the subset index improves the full audit: JSON/schema work remains identical, and the subset SELECT budget is small relative to the complete call. The rare-COMMITTED SQL probe is read-only; an unsupported DML-lab attempt (no acknowledged target in that fixture) is preserved with its actual failure log and replaced by this separate probe. No product/qualification result was rewritten.
