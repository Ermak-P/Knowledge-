# Agent Task: Optimize SQLite in Knowledge + Harness

Date: November 22, 2026.

Repository: https://github.com/Ermak-P/Knowledge-

Inspected baseline: **`73a3fc70c5fde17536568baae2a03b1b8be8b8a1`**, branch `main`, product `0.5.0rc1`. This commit includes the accepted audit stages 1–2 improvements. At the time this task was prepared, main pointed to this commit.

## 1. Assignment

**Implement measurable SQLite performance improvements**: suitable indexes, fewer repeated reads/deserializations, and less redundant work when validating current state. Deliver working code, a compatible upgrade for existing databases, regression coverage, an installed and verified distribution, and reproducible baseline → candidate results.

Do not stop at recommendations or SQL examples. A changed query plan does not prove that the entire product is faster. First establish the contributions of SQL, JSON, validation, and filesystem work; then implement changes with demonstrated value.

The main user operations are architectural context retrieval, persistent instruction lookup/preflight, recording signals/bindings, queue/plan processing, delivery outbox access, status/cancel, and Harness journal actions.

### Expected outcome

- A specific, justified set of indexes without duplicating primary keys.
- Fewer repeated SQL reads, payload parses, and passes over the same history within a consistent snapshot.
- Elimination of redundant record searches for each event wherever a validated dictionary or bulk read is sufficient.
- If needed, a minimal transactional projection of current state in the existing SQLite database, with validation and recovery.
- Demonstrated gains for at least the problematic database-dominated operations as valid datasets grow; report effects on complete operations and writes separately.
- Preserved integrity, root/scope isolation, authority, concurrency, crash recovery, and compatibility guarantees.

## 2. Scope and constraints

1. Read the applicable `AGENTS.md` files. Work **in place, without worktrees**. Do not discard other people's changes. If HEAD has changed, compare the new code with the baseline and optimize the current version without forcing a rollback.
2. Preserve standalone Knowledge and the Harness → Knowledge dependency direction. Do not introduce a mandatory ORM, server database, new inference service, or additional machine/coordinator database.
3. Preserve the project Knowledge SQLite database, shared Knowledge SQLite database, and Harness journal. Retain history, canonical payloads, IDs, revisions, approvals, receipts, and execution evidence. Do not shorten or delete history to improve benchmark numbers.
4. Use isolated temporary projects and copies of fixture data. Do not modify real IPM databases/configuration, user services, or containers.
5. Do not change the default `journal_mode`, `synchronous=FULL`, foreign-key policy, reference/path safeguards, locks, or bounded busy handling to obtain better numbers. Enabling WAL, disabling synchronization/`quick_check`, or increasing timeouts are not workarounds for completing this task.
6. Do not weaken exact approval, CAS, source/configuration binding, current denials, independent allowlists, or execution checks. Memory, caches, and projections do not grant authority.
7. Preserve the stages 1–2 fixes: coverage gaps, the unified grant contract, scope-transfer recovery, degraded session controls, the current P4 knowledge view, dependency/diagnostic budgets, and replay/history projection.
8. A complete retrieval/RU–EN redesign, Roslyn integration, architectural tests, root relocation, retention, and a new UI are outside scope. Measure filesystem hashing/extraction and inference separately; do not rewrite them to claim database improvements.
9. Merging, rollout, and deployment to the user's machine are outside scope. The implementation and package must be ready for independent review.

## 3. Confirmed baseline observations

### 3.1. Basic indexes already exist

Core tables use `PRIMARY KEY(id)`, `PRIMARY KEY(id, revision)`, `PRIMARY KEY(run, sequence)`, and `PRIMARY KEY(run, id)`. Examples:

- `revisions` and `operational_history`: `(id, revision)`;
- Harness `events`: `(run, sequence)`;
- Harness `actions`: `(run, id)`;
- `records`, `queue`, `plans`, `operational_events`, and `outbox`: primary key `id`.

Inspect the actual indexes using `PRAGMA index_list`, `PRAGMA index_xinfo`, and `sqlite_schema`. A separate index on `id` or the leftmost prefix of an existing composite key is usually unnecessary; provide evidence for any exception you retain.

### 3.2. Index candidates

| Actual baseline query | Candidate | Required measurements |
|---|---|---|
| `SELECT id,payload FROM queue WHERE status='pending' ORDER BY id` | `queue(status, id)` or a justified partial index for pending rows | Effects at 1%, 10%, and 100% pending; status update costs and size |
| `SELECT id,payload FROM outbox WHERE run=?` | `outbox(run)` | Retrieving one run among many completed runs; insertion cost |
| Queries for `plans.status='COMMITTED'`, including `ORDER BY id` | `(status, id)` or a narrow partial index | Benefit when COMMITTED rows are rare and the plans table is sufficiently large |
| `queue WHERE id=? OR payload=?` | Analyze the SQL fast path and exact deduplication | A primary key on id does not eliminate the scan caused by the unindexed second OR branch |

The first two candidates expressed in SQL:

```sql
CREATE INDEX ix_queue_status_id ON queue(status, id);
CREATE INDEX ix_outbox_run ON outbox(run);
```

These are **implementation candidates to evaluate through measurement**, not permission to edit a live database manually. The final set may differ. Do not add every candidate automatically or index entire large JSON payloads without demonstrated need.

In an earlier isolated experiment using SQLite 3.53.1 and 10,000 synthetic rows, the first two indexes changed the relevant plans from SCAN to SEARCH. Reading all `operational_events` and the OR-based duplicate lookup still produced scans. This was not an application benchmark and does not prove a speedup on the target Windows/Python SQLite runtime.

### 3.3. The workload extends beyond finding rows

Inspect at least the following:

- `Store._connection()` performs `quick_check` and `_check_control` whenever a transaction is opened. `_check_control` reads and validates operations, transfers, plans, the queue, history, revisions, and receipts.
- `OperationalStore.records()` subsequently calls `current(db)` again, then reads events again to obtain the latest signals/bindings.
- `operations.current()` validates history for each record and searches for a matching record using `any(...)` for each event; `records()` uses a similar `next(...)`. This creates redundant SQL round trips and work proportional to events × records.
- `binding_event()` scans events again to allocate the next revision-scoped sequence.
- `lifecycle.latest()` uses a correlated MAX-revision query. The existing primary key already helps the inner lookup; do not add a DESC index based on speculation.
- Harness `Journal._db()` uses `BEGIN IMMEDIATE` and `quick_check` for read calls as well. Establish their cost and the guarantees each operation requires before changing transaction modes.
- Capture/delivery/status may read outbox/actions repeatedly within one user operation.

## 4. Essential integrity requirement

**A speedup obtained by silently removing checks is unacceptable.**

Do not move full history validation into `doctor` merely because it is expensive. First identify the violations detected by the current public path and preserve that contract. In particular, a correct projection must not hide a corrupted authoritative record, history entry, or event.

Prioritize these safe improvements:

- Parse and validate once instead of repeating identical work within one stable read transaction.
- Read history in bulk instead of querying it separately for every record, while preserving the same checks.
- Use validated dictionaries keyed by ID instead of repeatedly searching all records for every event.
- Reuse validated objects **only within the same snapshot**; invalidate them after mutation, commit, or rollback.
- Use narrower SQL queries and suitable indexes when only a small subset of rows is genuinely required.

Process-global trust in a previously validated database based only on modification time, size, or row counts is insufficient. It can hide external corruption, root changes, restores, and new denials. Do not promote an unsafe experimental cache into the product.

If detecting arbitrary history corruption on every read requires linear work, **do not promise constant-time reads** while retaining that contract. Reducing redundant passes and quadratic work is already a useful optimization. Document the remaining limit and any possible separate contract, while preserving the safe default in this task.

A strategy that changes when corruption is detected or changes the trust boundary is a separate architectural change. Do not present it as a transparent optimization or treat it as accepted merely because old tests pass. Complete the remaining safe optimizations and document the unresolved tradeoff for review.

## 5. Implementation requirements

### 5.1. Indexes and SQL

- Inventory SQL/DDL and call frequencies for the selected hot paths. Use actual parameters, dataset sizes, and data distributions.
- Compare ordinary and partial indexes for SELECT, INSERT, status updates, size, and compatibility. Account for the query predicate required for the planner to use a partial index.
- When changing duplicate lookup, preserve exact payload comparison, legacy candidate IDs, known statuses, replay, and identity conflicts. A new digest does not replace equality checks when a conflict or collision occurs.
- If introducing `payload_hash` or a similar auxiliary key, correctly backfill existing rows, keep writes consistent, and detect inconsistencies. Do not add a UNIQUE constraint without proving compatibility with existing data.
- Retain EXPLAIN output as diagnostics for a specific SQLite version. Do not assert the complete textual plan representation in product tests; its format is not a stable API. Verify index use and elapsed time through suitable independent methods.
- Do not prohibit all scans: full audits and small tables may legitimately read everything. Eliminate unnecessary traversal, not the word SCAN itself.

### 5.2. Current state and events

- First eliminate repeated validation and deserialization within one operation/snapshot. Do not turn public methods into unvalidated direct SQL reads.
- Link events to records/revisions and group history without scanning every record again for each event.
- Preserve ordering semantics. Allocate binding sequences atomically for each ID/revision; equal or backward wall-clock timestamps must not change which state is latest. Preserve the established application-event order; events from an older revision must not become the state of a newer revision.
- For multiple actions in one preflight, consider reusing one consistent, validated read view instead of repeating identical reads of the same stores. Preserve project/shared isolation and recheck current restrictions immediately before effects occur.
- A projection of current signals/bindings or auxiliary keys is permitted **only when measurements establish its necessity**. It is derived data in the existing SQLite database, updated in the same transaction, referencing authoritative IDs/revisions/events, and must not replace user intent.
- Define behavior for missing, stale, or corrupted projections: a safe validated fallback or an explicit recoverable error. Do not disguise a partial response as the absence of a rule or denial. Rebuilding must not use a model to reinterpret the original wording or issue grants.
- Do not require a new projection if simply eliminating duplicated work provides the same useful result.

### 5.3. Transactions, concurrency, and the journal

- Determine which Harness methods are pure reads and which perform read-modify-write operations. Any separation of read and write transactions must be explicit and measured.
- Do not replace write transactions with read transactions for CAS, sequence allocation, cancel/recovery state, or operations with effects. Prevent lock-upgrade races.
- Preserve the execution lease, maintenance gate/fence, and lock order. Pure reads must not bypass an active restore/transfer fence.
- Keep waits and retries bounded. Speeding up one reader does not justify losing cancellation, concurrent writes, bounded busy errors, or recovery from unknown outcomes.
- Group reads within one logical operation without keeping a SQLite transaction open during HTTP inference, lengthy builds/tests, or user waits.

### 5.4. Compatible upgrades

- Create indexes for new databases through the normal initialization path. Provide an explicit supported upgrade/maintenance path for existing nonempty stores, with the normal locks, backup/fingerprint handling, and crash semantics.
- Ordinary read/lookup/status operations must not automatically execute DDL, ANALYZE, backfills, or auxiliary data writes. A separately authorized maintenance/recovery operation may do so under its own contract.
- Repeated upgrade/recovery must be idempotent. Do not delete a database or initialize over existing data.
- Account for older readers/writers. If they cannot maintain a new projection, define a safe compatible fallback or explicit refusal. An older writer must not silently invalidate the current projection.
- Preserve prepared/committed/acknowledged plans, pending queue entries, rejected/deferred dispositions, historical receipts, transfer intents, and pending Harness runs. A schema change must neither approve candidates nor repeat execution.
- Verify backup/restore/rollback, including the new indexes/auxiliary tables. Removing only derived objects must not delete history; do not rewrite root identity or approvals.
- Follow the project's versioning policy. Record the exact source/package hash of the new kit: earlier CI results or an unchanged version number do not qualify different bytes.

## 6. Reproducible benchmark

### Datasets

Use at least small, medium, and large datasets. The following matrix may be reduced with a documented justification based on runtime:

| Dimension | Values |
|---|---|
| Operational rules | 32 and 256 |
| Application/binding events | 0, 1,000, 10,000, 100,000 |
| History/revisions | Several revisions per record; a separate long-history case |
| Queue | 1,000 / 10,000 / 100,000; 1%, 10%, and 100% pending |
| Plans | Rare COMMITTED rows among historical PREPARED/ACKNOWLEDGED rows; also zero COMMITTED rows |
| Outbox | Many runs, few entries for the selected run; queries for both existing and absent runs |

Datasets must be structurally and semantically valid: IDs, payload hashes, revisions, history, receipts, and ownership must agree. Synthetic bulk generation is allowed for fixture preparation; verify the result using the normal validator and exclude generation from user-operation timings. Separately measure writes through actual product APIs.

Do not transplant root-bound stores into another root and rewrite identity for benchmarking. Generate consistent datasets for each root or use quiescent snapshots/restore within the same temporary root. Give baseline and candidate equivalent canonical data, sources, and configuration.

### Operations

Measure at least:

1. Reading operational rules/current signals and looking up one applicable instruction among irrelevant ones.
2. Writing an application/binding event and subsequently reading current state.
3. Preparing a queue with a small pending fraction and reading plans for recovery.
4. Submitting a duplicate and a new candidate, including a legacy-compatible case.
5. Reading one run's outbox, including capture/status/retry paths without new execution effects.
6. Harness load/action/events/status/cancel reads and the corresponding writes.
7. A complete `knowledge context`/MCP operation or broker preflight/P4 delivery on a representative project, showing how much SQL improvements matter when external checks are included.

For expensive or state-changing operations, choose a bounded number of repetitions with identical initial state and report that number explicitly. Do not substitute a direct SELECT that bypasses validation for an end-to-end read.

### Method and metrics

- Use a baseline binary/package from the pinned commit and a candidate from the current diff, both installed outside the checkout. Verify that imports resolve to site-packages.
- For the small dataset, collect at least 20 read samples after warm-up; justify the repetition count for larger datasets. Measure expensive writes separately with fixture resets. Interleave baseline/candidate runs where possible.
- Preserve raw samples, median/p95, repetition counts, and the p95 calculation method. Do not impose a noisy absolute timing gate across all CI without justification.
- Distinguish fresh processes/connections from warmed runs. Do not call a fresh process a cold disk-cache measurement unless the OS cache was controlled. Do not flush system caches in someone else's environment.
- Record Python/SQLite/OS versions, page/database sizes, and indexes; where feasible, also record SQL counts, SQL VM work/rows processed, JSON parses, validator passes, and filesystem work separately. Instrumentation must not dominate the workload or disable checks.
- Measure INSERT/UPDATE costs and disk growth. If an index slows the overall scenario or provides no material benefit, justify excluding it from the final set.
- Compare baseline/candidate logical results, errors, selected IDs/revisions, queue/plan outcomes, and guards. Permitted differences in benchmark IDs/roots must not conceal changes in authority or data loss.
- Record hypotheses and target operations before candidate measurements. Report the actual gain and its limits. The goal is useful improvement in database-dominated product paths, not merely a fast microquery.

If the complete `context` operation is dominated by filesystem analysis, that is a valid finding. Show the database gain separately and verify that the complete operation does not regress; do not attribute inference or semantic-search gains to a database index.

## 7. Required correctness checks

| ID | Check | Required evidence |
|---|---|---|
| DB-01 | New database and nonempty predecessor database | Required indexes/upgrades work; canonical data and root identity are preserved |
| DB-02 | Index predicates/status changes | Pending/imported/rejected/deferred entries and plan states are returned without loss; stale approvals are not revived |
| DB-03 | Outbox for selected/other/absent runs | No run mixing, duplicate delivery, or repeated execution effects |
| DB-04 | Duplicate candidate, legacy ID, mismatched payload | Deduplication and identity conflicts follow the contract; hashes do not conceal differences |
| DB-05 | Current/history/revision corruption, including an unselected record | Public operations preserve the previously required detection; caches do not hide corruption |
| DB-06 | Orphan/invalid event and invalid authoritative payload | A correct projection does not turn source corruption into success/no-match |
| DB-07 | Missing/stale/corrupt projection, if introduced | Validated fallback/recovery or an explicit blocking error; no denial is lost |
| DB-08 | Faults during event insertion/projection update/commit | Atomic rollback/recovery; no partial current state or extra application/grant |
| DB-09 | Equal/backward clocks; events from an older revision | Correct revision-scoped sequences and latest state |
| DB-10 | Fresh process, different project/shared roots, restore | No cache/identity leakage between roots; previously established trust is not reused |
| DB-11 | Concurrent readers/writers/CLI processes | No lost updates, deadlocks, or unbounded retries; bounded busy handling is preserved |
| DB-12 | cancel/resume, unknown process outcome, recovery_stop | Transaction-mode/read-grouping changes neither repeat nor lose effects |
| DB-13 | Maintenance freeze, backup/restore, and interrupted upgrade | Reads do not bypass fences; snapshots and recovery remain consistent |
| DB-14 | Repeated upgrade, older code/data, and rollback | Idempotence and documented compatibility; history is not destroyed |
| DB-15 | Scope transfer and degraded session | Revisions/CAS/current restrictions are preserved through the new hot paths |
| DB-16 | P4 current facts, cached receipts/history, dependencies/diagnostics | Optimized reads cannot bypass withholding, staleness checks, or budgets |
| DB-17 | Pure read path | No hidden DDL/ANALYZE/backfill/auto-approval mutations |
| DB-18 | Standalone Knowledge and externally installed kit | New assets are packaged; Harness/MCP remain optional for the core |
| DB-19 | Valid, growing benchmark fixtures | Results/errors match baseline; measurements cover actual execution |
| DB-20 | All previous regressions | Integrity, grants, encoding, complete tests, recovery, and native contracts are preserved |

Test projections, caches, and backfills beyond positive cases. Use real SQLite transactions/rollbacks and separate processes. Query plans and helper call counts are supporting evidence, not substitutes for public-operation outcomes.

## 8. Work sequence and qualification

1. Record HEAD/dirty state, versions, and current schemas/indexes. Establish the baseline and profile representative workloads.
2. Prepare a short table: query → frequency → cost → index/rewrite/repeated validation → hypothesis. Save it before changes; ordinary authorized work does not require separate interim approval.
3. Add the necessary regression/benchmark fixtures. Implement a small set of indexes and safe hot-path simplifications; measure changes independently and together.
4. Introduce projection/transaction-mode changes only if simpler fixes are insufficient and measurements establish their value. Preserve the strict integrity contract.
5. Test upgrade/backfill/rollback against valid nonempty predecessor state and injected faults. Do not weaken validators or rewrite results from an earlier failed run.
6. Build the kit, install it outside the checkout, and rerun focused checks plus the full suite. The baseline source suite contains 343 tests; known results are 332 PASS / 11 native-only SKIP on Linux and 343 PASS on Windows. Verify test contents and outcomes, not just counts.
7. Use the existing qualification entry points:

```text
python scripts/setup_p3.py
.venv/bin/python -B -m unittest discover -s tests -v
.venv/bin/python -B scripts/verify_p4.py

# Native Windows / Windows PowerShell 5.1
powershell -NoProfile -File scripts/verify-p4-windows.ps1
```

8. Run the available Linux/native Windows profiles. If the environment blocks a particular external check, preserve its exact FAILED/BLOCKED outcome and run the remaining independent checks separately. Someone else's CI or results from older source do not qualify the new kit.
9. Update schema, upgrade, integrity, index, benchmark, and limitations documentation. Prepare a concrete diff/commits and a review report. Continue within the authorized scope until the result is ready; an unavailable real host does not block independent implementation or checks.

A known external limitation from the earlier cloud audit: the IPC socket for an out-of-process MSBuild task host could return `Permission denied` with MSB4216. Do not bypass this by weakening build/test checks. The core database benchmark itself does not require OpenCode, a live model, Docker, or real IPM.

## 9. Deliverables for independent review

Prepare a package consistent with the repository layout, for example `reports/SQLiteOptimization/`, without unnecessarily copying all historical artifacts:

- `REVIEW.md`: improved operations, rationale for the selected indexes/changes, remaining linear work and why it remains, compatibility/integrity tradeoffs, exact source commit/identity, and package hashes.
- `BENCHMARK.md` and machine-readable results: baseline/candidate, dataset manifest, raw samples, median/p95, writes, sizes, query plans, JSON/validator work, and product-level timings.
- Benchmark reproduction commands/code with root-safe fixture generation/reset. Fixture source and the oracle must be included in reviewable source.
- `ACCEPTANCE.json`: DB-01…DB-20, PASS/FAIL/SKIP/BLOCKED by profile, commands, actual outcomes, and evidence links.
- Documented upgrade/recovery/rollback for new and existing stores; evidence that read-only paths have no hidden mutations.
- Comparison of logical rows/payloads/history before and after, plus corruption/concurrency/crash-boundary checks.

In the final response, report concrete gains by operation and dataset size, write/storage costs, passed test counts, and anything not verified. Do not present SCAN → SEARCH, synthetic SQL timings, or one favorable run as proof that the entire agent workflow is faster.

## 10. Acceptance readiness

The task is ready for independent review when:

- Implemented indexes and hot-path changes are supported by measurements of product operations on growing valid datasets.
- No redundant or unjustified indexes remain; SELECT benefits are compared with write and storage costs.
- Canonical data, history, authority, and previously required integrity validation are preserved; caches/projections do not hide corruption or new denials.
- Existing stores upgrade through the supported path and recover after faults; reads do not migrate databases; root identity remains unchanged.
- There are no lost updates, broken cancel/resume paths, or repeated effects; standalone operation and the installed package have been verified.
- Reproducible baseline/candidate evidence, complete verification statuses, and honest limits on speedups are provided.

A useful reduction in repeated linear passes without weakening guarantees is preferable to nominally constant-time reads that trust unvalidated history.

## References to the inspected source

- [Knowledge Store and `_check_control`](https://github.com/Ermak-P/Knowledge-/blob/73a3fc70c5fde17536568baae2a03b1b8be8b8a1/packages/knowledge/src/knowledge/store.py#L125)
- [Operational records/history/events](https://github.com/Ermak-P/Knowledge-/blob/73a3fc70c5fde17536568baae2a03b1b8be8b8a1/packages/knowledge/src/knowledge/operations.py#L77)
- [Lifecycle latest revisions](https://github.com/Ermak-P/Knowledge-/blob/73a3fc70c5fde17536568baae2a03b1b8be8b8a1/packages/knowledge/src/knowledge/lifecycle.py#L55)
- [Harness journal and outbox](https://github.com/Ermak-P/Knowledge-/blob/73a3fc70c5fde17536568baae2a03b1b8be8b8a1/packages/harness/src/harness/runtime.py#L103)
- [P4 delivery](https://github.com/Ermak-P/Knowledge-/blob/73a3fc70c5fde17536568baae2a03b1b8be8b8a1/packages/harness/src/harness/delivery.py)
- [SQLite query planning](https://www.sqlite.org/queryplanner.html)
- [EXPLAIN QUERY PLAN and output stability limits](https://www.sqlite.org/eqp.html)
- [SQLite partial indexes](https://www.sqlite.org/partialindex.html)
