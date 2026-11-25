# Confluence integration R2 — reliability and performance

Branch: `codex/knowledge-confluence-integration`; reviewed baseline: `f772e9d3138d5b26f862b8544232094f7017f0a0`.

Implementation complete; final installed Linux/native Windows qualification is pending. No overall GO is asserted while those results are pending. All Confluence content in tests is synthetic MCP data, never live corporate access.

| Finding | Status | Root cause | Fix | Regression tests | Remaining risks |
|---|---|---|---|---|---|
| CF-03, P1 | FIXED | `complete=True` and a maximum cursor were accepted without continuous coverage; absence was treated as invalidation | Durable deterministic 2000-code-point chunks bound to native version/snapshot/hash/representation; completion certificate; exact-revision historical evidence reviews | Missing coverage, gaps/hash/offset, duplicate chunks, subprocess restart, stale version, extraction omission, genuine targeted supersession and approved apply | Descriptors prove content coverage, not semantic correctness. Targeted quotes/reasons remain agent reports reviewed through the existing approval workflow |
| CF-01, P1 | FIXED | PARTIAL was excluded from resumable runs | `start {resume:true}`, automatic PARTIAL continuation, transient-only bounded retries; `fresh:true` for intentional new run | 500-page fixture: 490 immutable DONE receipts, 10 TIMEOUT recoveries in the same run after a new process; replay, pagination, partial analysis, scope/budget guards | Three retries per work item; persistent denial/skips require explicit bounded retry or corrected scope |
| CF-02, P1 | FIXED | Every heartbeat ran full control/queue/canonical validation and collection held an exclusive maintenance gate | Read-only, authorizer-restricted `progress`; SQL summaries; collection writer lease under a shared gate; `status`/`diagnostics` retain full validation | Counters match legacy status; concurrent worker/progress, second-writer and maintenance exclusion; corrupt queue still blocks canonical prepare | Progress explicitly reports `candidate_validation=NOT_RUN` and `integrity=NOT_RUN`; full diagnostics remain intentionally expensive |
| CF-04, P2 | FIXED | Six earlier definitions were silently shadowed | Remove only inactive definitions, preserve active signatures and call sites | AST duplicate module-level function check across Confluence modules; 23 command/static tests PASS | AST guard is the dependency-free F811 equivalent for this finding |
| CF-05, P2 | FIXED | Qualification receipts copied whole runs, packages and logs into Git | Scoped ignores; Actions Artifacts for raw CI outputs; compact receipt branch; manual draft Releases workflow for packages; remove branch-generated tracked outputs | Compact receipt excludes logs/packages/configuration; Python AST and workflow YAML syntax checks | Existing Git objects/history and release assets are retained; Actions artifacts have retention limits. Release workflow is manual, not published by this change |

## Evidence and benchmark

Original regressions were run before their fixes: CF-03 accepted missing coverage and invalidated omitted evidence; CF-01 changed run ID/lost resumable work; CF-02 rejected progress under an active worker; CF-04 detected duplicate definitions.

Seven samples per scenario, nearest-rank p95, isolated synthetic SQLite databases and one actual discovery worker thread. Counts are claims/evidence/unrelated pending candidates/pages. Compact samples, transaction durations, query counts, module hashes and EXPLAIN plans: [CONFLUENCE-R2-BENCHMARK.json](CONFLUENCE-R2-BENCHMARK.json). `before.commit` identifies the clean reviewed source. `after.commit` identifies its parent checkout during development; the recorded module SHA-256 hashes identify the measured CF-02 working source, subsequently committed as `94753176`. CF-04 removes inactive definitions only.

| Scenario | Counts | Before idle p50 / p95, ms | After idle p50 / p95, ms | After worker-active p95, ms | SQL statements before → after |
|---|---|---|---|---|---|
| Small | 200/400/100/50 | 47.58 / 86.41 | 1.08 / 1.25 | 27.98 | 117 → 7 |
| IPM-like | 1000/2000/12500/500 | 2099.43 / 2337.07 | 2.90 / 3.37 | 43.77 | 567 → 7 |
| Stress | 10000/20000/50000/5000 | 12268.10 / 13030.91 | 29.63 / 31.24 | 74.95 | 5067 → 7 |

All seven before requests in **each** worker-active scenario failed with the coordination lock; all seven after requests succeeded. The IPM-like target is met on this Linux environment. With the same 500 pages but only 100 unrelated candidates, control p95 was 3.47 ms: increasing the unrelated queue to 12500 did not produce proportional progress cost. This is a small synthetic sample, not a production latency guarantee. Worker validation itself still uses canonical guards; it is not claimed to have become constant-time.

EXPLAIN confirms current-run work/seen searches use existing prefix indexes and applied-page lookups use the page primary key. The bounded stage sort uses a temporary B-tree; measurements did not justify a new index. No DDL/index migration is needed. New coverage and retry fields live in existing checksummed JSON rows. Legacy stores/records remain readable; old uncertified analysis is revisited on the next Confluence run without a Git rescan. Legacy PREPARED complete analysis needs coverage revalidation before new submission. Existing source-schema migration stays transactional.

## Validation commands and observed results

Local targeted runs:

```sh
.venv/bin/python -m pip install --no-deps --no-build-isolation --force-reinstall ./packages/knowledge
PYTHONPATH=tests .venv/bin/python -m unittest test_confluence_r2 test_confluence_command test_confluence_source test_confluence_sync -q
# 62 tests PASS (CF-03)
PYTHONPATH=tests .venv/bin/python -m unittest test_confluence_resume test_confluence_command -q
# 68 tests PASS (CF-01, including inherited command scenarios)
PYTHONPATH=packages/knowledge/src:tests .venv/bin/python -m unittest test_confluence_progress test_confluence_resume test_confluence_r2 test_confluence_command test_confluence_source test_confluence_sync -q
# 155 tests PASS (CF-02, including inherited command scenarios)
PYTHONPATH=packages/knowledge/src:tests .venv/bin/python -m unittest test_confluence_static test_confluence_command -q
# 23 tests PASS (CF-04)
PYTHONPATH=packages/knowledge/src:tests .venv/bin/python -m unittest test_ci_artifacts test_confluence_static -q
# 2 tests PASS (CF-05)
PYTHONPATH=packages/knowledge/src .venv/bin/python scripts/confluence_r2_benchmark.py --phase before --output /tmp/confluence-r2-before.json --samples 7
PYTHONPATH=packages/knowledge/src .venv/bin/python scripts/confluence_r2_benchmark.py --phase after --output /tmp/confluence-r2-after.json --samples 7
PYTHONPATH=packages/knowledge/src .venv/bin/python scripts/confluence_r2_benchmark.py --phase after --output /tmp/confluence-r2-queue-control.json --scenarios ipm-queue-control --samples 7
```

Python AST parsing and `git diff --check` pass. Workflow YAML parsed with temporary development-only PyYAML 6.0.3; no dependency added to product or lockfile. An initial parser attempt failed because PyYAML was absent, then the isolated parser check passed.

Final validation commands/results will be recorded after execution: `scripts/verify_p4.py` and `scripts/verify_machine.py` on Linux, native Actions Windows matrix. These cover Git discovery, migrations, candidate dedup/application, concurrency/restart, evidence/conflicts, `/knowledge-confluence`, `/knowledge-update`, `/knowledge-init`, `/update-by-CR`, and transferred-kit installation/upgrade. Previous reviewed full Windows CI had an inherited bootstrap teardown `WinError 5`; its recorder also crashed on `_ErrorHolder`. The recorder now retains such errors rather than losing the results. No test or failure is suppressed.

The Cloud network profile denies `api.github.com`; Git transport works. Native CI receipts are available via the compact `knowledge-validation-receipts` branch, `<commit>/<full|machine-fast>/<Linux|Windows>/<run>/receipt.json`. Raw logs/packages remain in the linked Actions Artifacts. A compact receipt attests the job's reported result and source hashes; it does not independently verify raw artifact bytes locally.

## Repository cleanup and distribution

Removed **1289 tracked generated files, 37,755,921 bytes (36.0 MiB)** relative to branch work, including its generated latest pointers. [Exact removed-file inventory](CONFLUENCE-R2-REMOVED-FILES.csv) and [group totals](CONFLUENCE-R2-CLEANUP.json) are retained. Essential earlier review reports and their compact summary remain. Baseline release archives used as compatibility test fixtures remain tracked; source, installer templates and tests remain intact.

This reduces the tracked checkout, not historical Git object storage. No history rewrite, force push or release asset removal occurred. Optional future history cleanup would require a separate approved filter-repo plan, archived evidence, coordinated clone reset and force push; it is outside this change.

Reproduce the kit with `.venv/bin/python scripts/build_p4.py --output /tmp/knowledge-r2-kit --source-id <commit>`. The wheel and transferred installer include the coverage, recovery and progress fixes. Raw packages are uploaded by CI as Actions Artifacts. The manual `knowledge-release.yml` workflow creates a **new draft Release** for an explicitly selected `knowledge-*` tag and never replaces an existing release. For long-term distribution retain its ZIP/SHA256 in Releases; no release was published during this task.

## Commits

- `3c5728da`: CF-03 coverage and targeted evidence revalidation.
- `7a555e7c`: CF-01 durable partial-run recovery.
- `94753176`: CF-02 read-only progress and measured benchmark.
- `caaa708a`: CF-04 duplicate-definition removal.
- CF-05 cleanup/CI and final qualification commits: pending final recording.

No merge into `main`.
