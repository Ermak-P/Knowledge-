# Before candidate changes

Baseline: 73a3fc70c5fde17536568baae2a03b1b8be8b8a1. Working tree initially clean;
the former audit branch had identical content. Python 3.12; FULL synchronization,
rollback journal, quick_check, gates and 150ms SQLite timeout are held constant.

| Query/work | Frequency in one operation | Expected cost | Hypothesis to test |
| --- | --- | --- | --- |
| operational history by ID | rules × two current validations | SQL round trips and repeated JSON/hash validation | One bulk ordered history read and one validated transaction view |
| operational events | twice validating current, then selecting signals | JSON parsing and events × rules searches | ID dictionary and rowid ordered reduction while validating every event |
| binding allocation | full audit twice plus extra event pass | JSON/record searches; must remain atomic | Reuse the validated revision-scoped binding state inside BEGIN IMMEDIATE |
| candidate identity | candidate validation, then validation again for digest | schema reads/JSON; queue linear per public open | Hash the already validated candidate, preserving legacy manifest identity |
| duplicate id OR payload | one full queue scan after full control audit | SQL scan plus parsing already audited rows | Exact ID/raw-payload lookup in the same validated snapshot; no digest column |
| queue pending, plans COMMITTED | subset after full mandatory audit | subset SQL may be small relative to all-row validation | Compare ordinary/partial indexes, including writes/size; exclude if negligible end-to-end |
| outbox by run | status once, capture final state three times | scan among many unrelated runs, plus quick_check | run index and reuse final outbox; measure complete Journal API |
| status actions | twice per status | separate BEGIN IMMEDIATE/quick_check | Reuse actions for metrics; retain all existing transaction modes |
| lifecycle latest | repeated correlated MAX | existing (id,revision) PK already helps | No speculative DESC index; retain unless profile demonstrates need |
| canonical validation/source traversal | graph/schema/temp files/source hashing | filesystem work independent of SQL | Report separately; do not weaken or replace it |

No projection or process-global cache is planned. Full corruption detection remains
linear in authoritative history. A cache, if useful, will be tied to one explicit
SQLite transaction, invalidated on mutation, commit and rollback, with uncached
fallback for ordinary sqlite3 connections. No worktree, real user database or
execution effects are used. Ordinary reads must not create indexes.

Benchmark uses installed baseline and candidate in external virtual environments,
same-root quiescent resets, canonical logical-result comparisons, 20 small read
samples after warm-up, and bounded medium/large repetitions. Generation and
instrumentation are excluded from uninstrumented timings. Fresh connections are
not described as cold disks. Index plans are diagnostics, not a product speed claim.
