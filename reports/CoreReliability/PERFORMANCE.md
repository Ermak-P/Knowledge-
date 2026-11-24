# Synthetic performance and resources

Linux x64, Python 3.12.14; shared execution host. No IPM/production measurements.
Three interleaved before/after clean runs, identical 307-file raw inputs, 301 candidates, four CLI chunks, complete in both versions. Medians:

| Metric | Before | After |
|---|---:|---:|
| driver_seconds | 3.998419 | 1.297900 |
| inventory_seconds | 0.097064 | 0.168290 |
| largest_child_peak_rss_bytes | 32739328.000000 | 27111424.000000 |
| checkpoint_seconds | 0.004045 | 0.003665 |
| prepare_seconds | 0.211310 | 0.163677 |

Raw records: benchmarks/*-final-clean-*/result.json and progress.log; driver.log preserves subprocess output. repetitions.json binds final installed source identity and driver SHA256. repeat_workloads.py records reproduction commands (substitute private fixture paths). Baseline uses the tracked prior Windows-path-fix archive; after uses the source-bound delivered kit. Original one-shot measurements are retained separately.

Mixed fixtures include invalid UTF-8 JSON, UTF-16 XML, declared CP1251 XML and a 1.1 MB JSON. Before stops after 100 attempts with 203 remaining and no candidates. After processes all 307 eligible files: 305 fully read, one failed, one preview-partial, remaining zero, 301 safe lexical candidates, COMPLETED_WITH_GAPS and exit 2. This is improved recovery/coverage, not an equal-work timing speedup. The extra discovered/default-excluded file is the administrative writer lock; pruned metadata directories do not fabricate descendant counts.

Microbenchmarks before-metrics.json/after-metrics.json preserve five samples each: direct MCP and stable bootstrap handshake/catalog/shutdown, 100 UTF-8 extractions, mixed encoding inventory, full large-file hashing, explicit checkpoint resume and preparation. MCP catalog increased from 4 to 12 tools. Startup median rose about 0.47 to 0.55 seconds on this host; the few-millisecond bootstrap delta is within noise. UTF-8 extraction increased about 0.004 to 0.011 seconds per 100 files because of strict bounded reads, policy/path checks and identity validation. Large-file inventory hashes all 1.1 MB now instead of rejecting a prefix, so its higher cost is unequal work. Resume preserved its ID in both versions.

Prepare profiling is retained in *-prepare-profile.txt with five unprofiled samples: medians approximately 0.23 vs 0.30 seconds. The bulk of work remains schema/queue validation and source-bound simulation; additional inventory/path/hash checks contribute overhead. Shared-host variation is substantial. Checks were not weakened to improve timing. Transaction-local candidate indexing removed repeated whole-queue decoding: the initial equal-work scan was 4.14 vs 1.34 seconds, and repeated final measurements above qualify that single result.

Parent tracemalloc measures the driver only; largest child RSS is Linux RUSAGE_CHILDREN, in bytes, not a sum of concurrent processes. Per-chunk and checkpoint timings, queue preparation and CLI call counts are preserved in each raw result. Deterministic scan uses no model and zero scan MCP calls; the separate startup microbenchmark used 20 actual MCP requests across ten sessions. Semantic inference quality/latency and actual Windows/IPM performance are delegated to the local handoff. No production speed or memory claim follows from these fixtures.
