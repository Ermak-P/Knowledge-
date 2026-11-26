# Knowledge Confluence Integration — Reliability and Performance Fixes

## 1. Objective

Resolve the findings identified during the external review of the Confluence integration.

Repository: `Ermak-P/Knowledge-`

Target branch: `codex/knowledge-confluence-integration`

Reviewed commit: `f772e9d3138d5b26f862b8544232094f7017f0a0`

Preserve the existing architecture, public commands, Git integration, canonical knowledge lifecycle, and backward compatibility with existing Knowledge databases.

Knowledge must support only the two currently required knowledge sources: Git and Confluence. Do not introduce unnecessary abstractions for hypothetical future sources.

## 2. Required fixes

### CF-01 — Resume partially completed Confluence discovery

**Priority: P1**

File: `packages/knowledge/src/knowledge/confluence_command.py`

The current `start()` implementation excludes the `PARTIAL` state from resumable runs.

Consequently, restarting after a partially successful discovery may create a new run and repeat previously completed operations.

Requirements:

- Provide an explicit resume mechanism for partially completed runs.
- Preserve the existing run ID, completed work, pagination cursors, analysis checkpoints, and discovered page identities.
- Retry transiently failed operations without repeating successfully completed operations.
- Distinguish retryable failures from permanent failures and intentionally skipped pages.
- Prevent infinite retry loops.
- Preserve the existing operation budget mechanism.
- Allow an intentional new discovery run when requested.
- Preserve existing scope-change protection.

Acceptance criteria:

- Simulate discovery of 500 pages with 490 successfully processed pages and 10 transient failures.
- Resume the existing run.
- Previously completed operations must not be repeated.
- Successfully recovered pages must not create duplicate candidates.
- Interrupted pagination and partial semantic analysis must resume correctly.
- Verify recovery after process termination and restart.

### CF-02 — Optimize Confluence progress reporting and SQLite access

**Priority: P1**

Files:

- `confluence_command.py`
- `confluence_sync.py`
- Related SQLite storage and lifecycle modules, where necessary.

The current `status()` implementation performs expensive database operations, including loading pending candidates, canonical records, source bindings, and conflict information.

Because `complete_work()` invokes `status()` repeatedly, the total processing cost may increase significantly with project size.

This is especially important for large repositories such as IPM, where Knowledge has already experienced request timeouts and `store-busy-retry` failures.

Requirements:

- Separate lightweight progress reporting from comprehensive diagnostics.
- Preserve backward compatibility with existing public status consumers.
- Ensure frequent progress requests do not load the entire canonical knowledge graph or candidate queue.
- Use SQL aggregations and indexed queries where appropriate.
- Avoid loading Confluence page bodies for routine progress reporting.
- Avoid repeated JSON deserialization of unrelated records.
- Avoid unnecessary database connections and transactions.
- Minimize the duration of write transactions and exclusive coordination locks.
- Inspect query plans using `EXPLAIN QUERY PLAN`.
- Add indexes only where measurements demonstrate a benefit.
- Ensure existing databases receive required schema and index migrations automatically.
- Do not hide database contention by simply increasing timeouts or retry counts.

Lightweight progress reporting should include:

- Current run state.
- Discovered pages.
- Processed pages.
- New, changed, and unchanged pages.
- Failed pages.
- Remaining work.
- Operation budget and completed operations.
- Current processing stage.

Detailed conflict information, full candidate validation, and integrity verification should be available separately.

Acceptance criteria:

- Benchmark the current implementation before making changes.
- Repeat benchmarks after implementing the optimization.
- Include at least three representative database sizes:

| Scenario | Claims | Evidence | Pending candidates | Confluence pages |
|---|---:|---:|---:|---:|
| Small | 200 | 400 | 100 | 50 |
| IPM-like | 1,000 | 2,000 | 12,500 | 500 |
| Stress | 10,000 | 20,000 | 50,000 | 5,000 |

- Measure p50 and p95 latency.
- Measure SQL query counts and transaction duration.
- Measure progress reporting while a discovery worker is active.
- Target p95 lightweight status latency below 100 ms for the IPM-like scenario on the benchmark environment.
- Demonstrate that lightweight status does not scale linearly with the total canonical knowledge graph or unrelated candidate queue.
- No regressions in canonical knowledge consistency.
- Report actual measurements, not theoretical estimates.

### CF-03 — Prevent evidence invalidation after incomplete semantic analysis

**Priority: P1 — highest functional priority**

File: `packages/knowledge/src/knowledge/confluence_sync.py`

The current implementation allows `complete=True` without mandatory verification of complete page analysis.

An incomplete analysis may incorrectly cause previously valid evidence to become superseded.

Requirements:

- Introduce durable semantic analysis coverage tracking.
- Bind coverage to the exact Confluence snapshot, native page version, content hash, and representation.
- Track analyzed content ranges or deterministic chunks.
- Detect missing ranges, invalid offsets, and incomplete coverage.
- Do not treat the maximum analyzed offset as proof of continuous coverage.
- Require explicit, complete coverage before finalizing an analysis.
- Preserve completed coverage checkpoints across process restarts.
- Reject completion requests with incomplete coverage.
- Ensure duplicate chunk submissions are idempotent.
- Reset or safely invalidate incomplete analysis checkpoints when the source revision changes.
- Preserve existing canonical knowledge and independent Git evidence.
- Do not mark old evidence as superseded or retracted merely because a finding was absent from an incomplete analysis.
- Even after complete coverage, distinguish confirmed removal or changed meaning from an extraction omission. Absence of a finding alone is not sufficient proof that previously recorded knowledge is invalid.
- Require targeted revalidation of affected historical evidence before proposing its invalidation.
- Preserve the existing candidate review and canonical application workflow.

Knowledge must distinguish deterministic content coverage from agent-reported semantic correctness. Do not claim that complete content coverage proves the correctness of LLM-generated findings.

Acceptance criteria:

- Analyze only the first portion of a large page and submit `complete=True`: completion must be rejected.
- Submit non-contiguous analyzed ranges: completion must be rejected.
- Submit duplicate chunks: no duplicate candidates or incorrect coverage counts.
- Restart the process during analysis: durable coverage must be preserved.
- Change the Confluence version during analysis: stale completion must be rejected.
- Analyze a complete page with an unchanged historical fact omitted from the findings: the existing evidence must remain valid unless targeted revalidation establishes otherwise.
- Confirm that transient MCP failures do not invalidate existing evidence.
- Confirm that genuine documented changes can generate evidence supersession candidates.
- Confirm that independent Git evidence remains unaffected.
- Confirm that canonical knowledge changes only through the existing approved application workflow.

### CF-04 — Remove duplicate function definitions

**Priority: P2**

File: `packages/knowledge/src/knowledge/confluence_command.py`

Remove duplicate definitions of:

- `validate_control`
- `enable`
- `checked`
- `state`
- `save_state`
- `integrity`

Requirements:

- Preserve the intended behavior of the active implementations.
- Verify all call sites.
- Add a static regression check for duplicate module-level function definitions.
- Use Ruff F811 or an equivalent check.
- Avoid introducing unnecessary runtime dependencies.
- Do not perform unrelated formatting or refactoring.

Acceptance criteria:

- No duplicate function definitions in the affected modules.
- Static validation passes.
- Existing Confluence command tests pass.

### CF-05 — Stop repository growth caused by generated artifacts

**Priority: P2**

The branch contains generated installation packages, ZIP archives, WHL files, extracted distributions, CI logs, and duplicated documentation.

Requirements:

- Audit tracked generated files introduced by this branch.
- Remove unnecessary generated artifacts from the tracked working tree.
- Update `.gitignore` with appropriately scoped rules.
- Preserve source files, test fixtures, installer sources, and essential review reports.
- Store generated CI outputs using GitHub Actions Artifacts.
- Store distributable release packages using GitHub Releases.
- Keep compact benchmark summaries and validation reports in Git when useful.
- Prevent CI workflows from committing generated distributions back into the repository.
- Ensure reproducible package generation remains available.
- Do not rewrite Git history, force-push, or remove existing release assets without explicit approval.

Acceptance criteria:

- Generated distributions are no longer tracked in the resulting working tree.
- CI and packaging workflows continue to work.
- Provide a report showing removed tracked files and their total size.
- Explain the difference between working-tree cleanup and actual Git history size reduction.
- Provide a separate optional history-cleanup recommendation if required.

## 3. Architecture constraints

- Keep Knowledge independent from Harness.
- Preserve Git and Confluence as independent knowledge sources.
- Use native Confluence page versions as the primary change indicator.
- Use content hashes to detect unchanged content across different versions.
- Continue using the existing Confluence MCP integration.
- Do not introduce a direct Confluence REST client.
- Do not introduce a new LLM provider.
- Do not bypass candidate validation, approval, or canonical application.
- Do not delete or rebuild existing Knowledge databases.
- Do not require a full Git repository rescan after the upgrade.
- Preserve existing project and machine installation mechanisms.
- Preserve compatibility with Windows, Linux, and OpenCode.
- Avoid unnecessary dependencies and configuration changes.

## 4. Implementation order

1. Reproduce the reported issues and add failing regression tests.
2. Fix CF-03: semantic coverage and evidence safety.
3. Fix CF-01: partial run recovery.
4. Fix CF-02: database and progress optimization.
5. Fix CF-04: duplicate definitions.
6. Fix CF-05: repository artifact management.
7. Execute complete regression and installation validation.

Use a test-first approach wherever practical.

Do not weaken existing tests merely to make the implementation pass.

## 5. Required validation

Run and report:

- Confluence unit and integration tests.
- Git knowledge discovery regression tests.
- SQLite migration and compatibility tests.
- Candidate submission, deduplication, and application tests.
- Interrupted execution and restart recovery tests.
- Concurrent access and database contention tests.
- Evidence lifecycle and source conflict tests.
- `/knowledge-confluence` command validation.
- `/knowledge-update` command validation.
- `/knowledge-init` regression tests.
- `/update-by-CR` regression tests.
- Windows and Linux installation and upgrade validation.
- Static code quality checks.
- Before-and-after performance benchmarks.

Use synthetic Confluence MCP fixtures when live corporate Confluence access is unavailable. Clearly distinguish simulated integration tests from live integration verification.

## 6. Deliverables

Produce:

- Separate logical commits for each finding or closely related group.
- Regression tests reproducing the original defects.
- Updated documentation where behavior has changed.
- Database migration implementation, if required.
- Before-and-after benchmark results.
- Repository cleanup report.
- A compact final review report:

`docs/P4/CONFLUENCE-INTEGRATION-R2.md`

The final report must contain:

| Finding | Status | Root cause | Fix | Regression tests | Remaining risks |
|---|---|---|---|---|---|

For each finding, use one of the following statuses:

- FIXED
- PARTIALLY FIXED
- NOT FIXED
- NOT REPRODUCED

Include exact test commands, measured results, failed tests, environmental limitations, and commit hashes.

## 7. Definition of Done

The task is complete only when:

- All five findings have been addressed.
- Incomplete semantic analysis cannot incorrectly invalidate existing evidence.
- Partially completed discovery can resume without repeating successful work.
- Lightweight progress reporting demonstrates measurable performance improvements.
- Existing Knowledge databases can be upgraded without data loss.
- Git knowledge processing remains unaffected.
- Generated distributions are no longer unnecessarily committed.
- Relevant regression tests pass.
- Remaining limitations are explicitly documented.

Do not merge into `main`.

Keep the completed implementation in the target branch for external review.

Do not report GO if any P1 finding remains unresolved.