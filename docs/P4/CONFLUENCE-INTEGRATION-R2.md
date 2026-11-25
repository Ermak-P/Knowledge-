# Confluence integration R2

Target: `codex/knowledge-confluence-integration`. Reviewed baseline: `f772e9d3138d5b26f862b8544232094f7017f0a0`. CF-01–CF-04 are fixed. CF-05 cleanup and delivery automation are implemented, but actual Release upload/verification remains unconfirmed. No merge into `main`, database reset, Git rescan, history rewrite or force push was performed.

The final product commit is `7d8ba2ee1a8c494f5b0c0c060465865715638d1e`. Installed Linux regression: **628 tests, 615 PASS, 13 expected native-Windows skips, zero failures/errors**, source unchanged. Native machine qualification of `92953ee3` passed **225/225** tests, installation/upgrade and real OpenCode 2.4.0 checks. The final review-package workflow additionally gates delivery on all Confluence tests on native Windows, including the last legacy-cursor correction. Its source-bound result and asset verification are retained in annotated validation tags. This report does not claim full native-Windows Harness/P4 qualification. All Confluence data is synthetic MCP fixture data; no live corporate Confluence was verified.

| Finding | Status | Root cause | Fix | Regression tests | Remaining risks |
|---|---|---|---|---|---|
| CF-03, P1 | FIXED | `complete=True`/maximum offset lacked continuous coverage; omission could supersede evidence | Durable deterministic chunks bound to exact native version/snapshot/hash/representation; complete certificate; targeted historical evidence reviews | Missing coverage, gaps/hash/range, duplicate chunks, restart, stale native version, omitted fact, documented changes, exact approved apply, independent Git evidence | Coverage proves content receipt, not semantic correctness. Targeted quotes/reasons remain agent reports subject to normal review |
| CF-01, P1 | FIXED | PARTIAL was excluded from resumable states | Explicit/default partial resume, same run/work/page IDs, transient-only retries bounded to three, separate intentional fresh run | 500 pages: 490 unchanged DONE receipts, ten transient recoveries after a new process; actual recovered analyses/replayed receipts produce one claim with expected evidence; budget/pagination/scope guards | Persistent denial/skips need explicit bounded retry or corrected scope. Legacy scalar offsets are not trusted coverage |
| CF-02, P1 | FIXED | Each heartbeat loaded queue/canonical records; collection held an exclusive coordination gate | Separate read-only `progress`, indexed SQL summaries, serialized source writer under shared maintenance gate; legacy `status`/`diagnostics` retain full validation | Matching counters, failed sibling work remains visible, concurrent worker/progress, second-writer/maintenance exclusion, corrupt queue still blocks prepare | Telemetry reports `candidate_validation=NOT_RUN`, `integrity=NOT_RUN`; authoritative operations retain expensive guards |
| CF-04, P2 | FIXED | Six inactive definitions were shadowed by later functions | Remove only earlier definitions, preserve active signatures/call sites | Dependency-free AST equivalent of F811 across Confluence modules; command regressions | Guard covers module-level definitions |
| CF-05, P2 | PARTIALLY FIXED | CI receipt publication copied entire runs/distributions into Git | Remove generated branch outputs; scoped ignores; raw CI outputs in Actions Artifacts; packages in draft Releases; compact source-bound receipts only | Receipt excludes logs/packages/config; uploaded asset digest verification; failure cannot be promoted to PASS; AST/YAML checks | Cleanup reduces the tracked checkout, not historical objects. Artifact retention applies; existing release assets/history remain intact |

## Behavior and compatibility

`start {resume:true}` retains a PARTIAL run and retries TIMEOUT, UNAVAILABLE and INCOMPLETE_RESPONSE at most three times per work item. Permanent failures and skipped work are separate; `fresh:true` deliberately starts a new run. Budgets remain monotonic and scope changes refuse resume. Previously completed work is not repeated.

Snapshot reads return deterministic 2000-Unicode-code-point chunk descriptors and the exact coverage binding. Submit descriptors with partial/final findings. Duplicates are idempotent; gaps and stale bindings reject completion. Durable coverage survives restart. The cursor is reconstructed from the continuous verified prefix, including when an older client supplied a larger numeric cursor. Buffered findings/history survive.

Complete coverage alone never invalidates omitted facts. Invalidation needs a targeted review of that evidence ID and expected revision, a literal current quote and reason, and the ordinary separately approved application plan. Independent Git/other-page evidence is preserved. Legacy uncertified outboxes retain their original batches/counts in quarantine: newly certified analysis can regenerate matching positive proposals; omission-based negative proposals require normal human disposition. Same-body refresh cannot bypass quarantine. No store reset or full Git rescan is needed.

`progress` reads only source telemetry with read-only SQLite and an authorizer restricting table access. It does not load canonical records, candidates or bodies. `status` retains its public detailed response; `diagnostics` is its explicit alias, and `finish` retains full integrity verification. No canonical guard or timeout was relaxed. Existing indexes cover the measured queries; EXPLAIN did not justify another index. No DDL/index migration is necessary. New fields use existing checksummed JSON rows; existing transactional source-schema migration remains tested.

## Measured performance

[Samples, transaction durations, query counts, module hashes and EXPLAIN plans](CONFLUENCE-R2-BENCHMARK.json). Seven samples, nearest-rank p95, isolated synthetic databases, one real discovery worker thread. Counts are claims/evidence/unrelated pending candidates/pages. Final controlled measurements followed completion of other local qualification. The measured commit is `7072632c`; final progress/storage code is byte-identical to it. Later runtime changes normalize legacy snapshot cursors.

| Scenario | Counts | Before idle p50 / p95, ms | After idle p50 / p95, ms | After worker-active p95, ms | SQL statements before → after |
|---|---|---|---|---|---|
| Small | 200/400/100/50 | 47.58 / 86.41 | 0.91 / 1.13 | 20.67 | 117 → 7 |
| IPM-like | 1000/2000/12500/500 | 2099.43 / 2337.07 | 2.97 / 3.45 | 46.23 | 567 → 7 |
| Stress | 10000/20000/50000/5000 | 12268.10 / 13030.91 | 31.80 / 34.42 | 98.95 | 5067 → 7 |

Before: all seven requests in each active-worker phase failed at the coordination lock. After: all succeeded. All seven IPM/stress samples began while the worker was active; the small worker ended before two later samples. The IPM target is met. Keeping 500 pages but reducing unrelated candidates from 12500 to 100 gave p95 5.78 ms, demonstrating no proportional queue cost.

An additional run under simultaneous full .NET qualification load gave IPM worker-active p95 **203.57 ms**, with no lock errors. That run and the earlier development measurements are retained. CPU/GIL scheduling and shared-host load remain material; seven samples are not a production latency guarantee. Worker validation itself still uses canonical guards and is not claimed to have become constant-time.

## Validation and failures

[Final compact validation record](CONFLUENCE-R2-VALIDATION.json), [initial full qualification](CONFLUENCE-R2-INITIAL-VALIDATION.json).

| Route | Tested commit | Observed result |
|---|---|---|
| Final installed Linux regression, actual generated `verify_p4.py` driver | `7d8ba2ee` | 628 tests; 615 PASS, 13 expected native-only skips; zero failures/errors; source unchanged |
| Final focused Confluence/compatibility/static suite | `7d8ba2ee` | 91 PASS, including legacy/unverified and verified noncontiguous cursors |
| Local installed Confluence release gate | product `7d8ba2ee` | 141 PASS, no skips |
| Local full P4 qualification | `4491919d` | PASS_PORTABLE; 28/28 phases, source unchanged; 641 executions included 44 repeated imported base cases, subsequently removed from duplicate discovery |
| Local installed machine/upgrade/OpenCode | `ba64b4bc` | PASS_PORTABLE; 223 tests, two native-only skips; all seven phases PASS |
| CI installed Linux machine/upgrade/OpenCode | `92953ee3` | PASS_PORTABLE; 225 tests, two native-only skips; all phases PASS |
| CI native Windows machine/upgrade/OpenCode | `92953ee3` | PASS_NATIVE; 225/225 PASS, zero skips; all phases PASS |
| Final tagged distribution | review tag below | Native Confluence gate must pass, then uploaded ZIP/SHA256 are downloaded and compared; actual results are in validation tags |

Native machine evidence: https://github.com/Ermak-P/Knowledge-/actions/runs/45680604700 . Full native-Windows P4 results for this revision are not asserted. The earlier reviewed full Windows run failed in unchanged bootstrap teardown with WinError 5 and its recorder then lost results on `_ErrorHolder`; the recorder now retains these errors. Qualification continues independent installer/native-host phases after unit failures, while any failed phase still forces final FAILED. Fault-injection tests verify this for both drivers.

Failed attempts remain visible:

- Original regression cases failed before fixes: absent/gapped coverage and extraction omission; PARTIAL changed run ID; progress failed during a worker; AST found duplicate definitions.
- Native `4491919d`: 239/240 PASS, one error in the new corruption fixture. Its raw SQLite connection is now explicitly closed, preserving all assertions.
- Native `7072632c`: 221/222 PASS, PermissionError/WinError 32 in unchanged `ScanReliability.test_observed_resume_recovers_committed_chunk_without_helper_checkpoint`.
- Native `ba64b4bc`: failure in unchanged `ScanReliability.test_atomic_metadata_reader_and_writer_do_not_share_incomplete_json`. These earlier transient failures are not used as PASS evidence; their exact causes were not established from compact summaries. The later native machine run above passed both.
- A one-off local wrapper lacked a `__main__` guard: 626 executions had one `test_p4_r1.R1Tests.test_spawned_child_does_not_reenter_installed_regression_driver` failure caused by that wrapper. The final 628-test run uses the repository's actual generated driver and passes. Initial development module-name errors and missing optional YAML parser were corrected before final verification.

Actual/reproducible commands (Python 3.12):

```sh
python scripts/setup_p3.py
.venv/bin/python -B scripts/verify_p4.py
.venv/bin/python -B scripts/verify_machine.py
# Final local full-suite execution extracted the actual repository driver:
.venv/bin/python -I -B /tmp/confluence-r2-run-repository-driver.py
# Equivalent installed test discovery:
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -I -B scripts/confluence_release_tests.py --output /tmp/confluence-release-tests.json
PYTHONPATH=tests .venv/bin/python -m unittest test_confluence_r2_compat test_confluence_r2 test_confluence_command test_confluence_sync test_confluence_source test_confluence_static -q
PYTHONPATH=tests .venv/bin/python -m unittest test_ci_artifacts test_confluence_static -q
PYTHONPATH=packages/knowledge/src .venv/bin/python scripts/confluence_r2_benchmark.py --phase before --output /tmp/confluence-r2-before.json --samples 7
PYTHONPATH=packages/knowledge/src .venv/bin/python scripts/confluence_r2_benchmark.py --phase after --output /tmp/confluence-r2-controlled-after.json --samples 7
PYTHONPATH=packages/knowledge/src .venv/bin/python scripts/confluence_r2_benchmark.py --phase after --output /tmp/confluence-r2-controlled-control.json --scenarios ipm-queue-control --samples 7
```

Native Windows commands (PowerShell 5.1, UTF-8 and a normal-spelling fixture TEMP selected by the workflow):

```powershell
python scripts/setup_p3.py
& .venv/Scripts/python.exe -X utf8 -B scripts/verify_machine.py
& .venv/Scripts/python.exe -X utf8 -B scripts/confluence_release_tests.py --output reports/confluence-release-tests.json
```

The before benchmark must use reviewed `f772e9d3` product modules; the checked-in driver supports that status API. Python AST, duplicate-definition checks and `git diff --check` pass. Workflow YAML was parsed using temporary development-only PyYAML 6.0.3; no product/lockfile dependency was added. Git works in this Cloud environment, while `api.github.com` is denied. Compact CI receipts are retrieved through the `knowledge-validation-receipts` branch; this does not constitute independent local verification of raw Actions logs/assets. Local raw logs remain under `/tmp`; CI raw outputs remain in linked Actions Artifacts.

## Cleanup and delivery

Removed **1289 tracked generated files, 37,755,921 bytes (36.0 MiB)**. [Exact file inventory](CONFLUENCE-R2-REMOVED-FILES.csv), [group totals](CONFLUENCE-R2-CLEANUP.json). Essential historical reports remain; baseline archives used by compatibility tests remain fixtures. No new generated distribution is tracked. Historical Git objects still occupy space. Optional history cleanup needs a separate approved filter-repo/archive/clone-reset plan; no such cleanup or force push was performed.

The first delivery tag has no verified receipt. Static audit found that the new Windows checkout omitted the existing process-local `core.longpaths` configuration, while preserved baseline paths reach 310 characters. The gate now uses the accepted native checkout and TEMP/TMP/TMPDIR settings. The original tag/assets are retained.

Review-package tag: **`knowledge-confluence-r2-7d8ba2ee-v2`** (last runtime commit plus the review packet and release gate). `knowledge-release.yml` creates a **draft** Release, never replaces existing assets, downloads the uploaded ZIP/SHA256 and checks their bytes. The final source-bound receipt is the annotated `validation-release-<tag-commit>` tag; the native gate also records `validation-confluence-<tag-commit>-<run>-<attempt>`. These receipts carry the actual URL, asset hashes and native result when delivery succeeds. At final observation neither the native result tag nor asset-verification tag existed; workflow execution/queue/failure could not be inspected because GitHub API and manual dispatch return Forbidden. An owner-visible workflow status is required to complete delivery. [Delivery checkpoint](CONFLUENCE-R2-DELIVERY.json). No draft Release, public release or deployment is claimed.

Rebuild: `.venv/bin/python scripts/build_p4.py --output /tmp/knowledge-r2-kit --source-id <commit>`. The locally rebuilt wheel was checked byte-for-byte against the final coverage/sync/progress/store/MCP source modules. Installation/upgrade from either the branch checkout or extracted review kit uses the existing command:

```powershell
.\install.ps1 -McpDir 'C:\LLM\mcp\knowledge'
```

## Commits

- `3c5728da`: CF-03 deterministic coverage and targeted revalidation.
- `7a555e7c`: CF-01 partial-run recovery.
- `94753176`: CF-02 lightweight progress and benchmark.
- `caaa708a`: CF-04 duplicate definitions.
- `4491919d`: CF-05 tracked-output cleanup and compact receipts.
- `7072632c`: legacy proposal quarantine/revalidation, accurate failure counts, Windows fixture closure.
- `ba64b4bc`: final benchmark evidence and draft asset verification.
- `92953ee3`: complete independent installation evidence while preserving failure status.
- `7d8ba2ee`: reconstruct legacy/current cursors from verified coverage.

The subsequent packet/delivery commits change CI verification and reports; runtime source remains the qualified `7d8ba2ee` code.

The final packet checkout correction passed actionlint 1.7.7. Its official release checksum was verified; no dependency was added to the product.
