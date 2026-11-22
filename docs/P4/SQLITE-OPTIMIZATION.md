# SQLite performance and compatible maintenance

This revision retains knowledge-sqlite-v1, optional P1/operations v1, journal v1,
product 0.5.0rc1, and all authority/approval formats. Identify its distribution by
the exact source identity and RELEASE.json/wheel/ZIP hashes, not just the version.

Operational reads bulk-read history and validate each revision once, reduce every
event in rowid order using an ID dictionary, and reuse this validated view only
inside the same owned SQLite transaction. Binding allocation remains revision
scoped under BEGIN IMMEDIATE; application order is insertion order, independent
of clocks. Old-revision signals cannot become the state of a newer revision.
Every authoritative row is still checked, including unrelated rules, history and
events. Reads remain linear in total history. No projection, trust by file time,
global cache, model reinterpretation or new authority source is introduced.

Mutation, transaction boundaries, cursors and SQL tracing invalidate the local
view; ordinary sqlite3 connections have an uncached fallback. Returned public
records are detached copies. Queue IDs hash an already validated candidate once;
duplicate lookup reuses checked rows and compares exact payload text and then
objects, preserving predecessor IDs and identity conflicts. No payload hash column
or uniqueness/backfill is added. Canonical/schema/filesystem validation remains.

An optional outbox profile creates `ix_outbox_run ON outbox(run)`. The default
leaves it absent: measured subset reads improve, but its extra quick_check pages
slow unrelated journal reads/writes. Select it for an outbox-dominated workload,
not as a general agent speedup. New journals can select it through the normal
initialization API `Journal(root, index_outbox=True)`. For an existing journal that
request refuses a missing index and directs the operator to explicit maintenance.
Existing journals are
validated on opening, without CREATE/ANALYZE/migration. The index is optional:
missing indexes preserve correct reads and writes. SQLite maintains it even for
older writers. Queue/status and plan/status indexes were evaluated and excluded:
their faster subset SELECT did not improve the fully audited operation enough to
justify storage/write costs. The outbox profile is also opt-in because of measured
write/read costs elsewhere. Primary keys already support all ID/composite-prefix
lookups. No DESC, event or whole-JSON index is added.

All journal transaction modes remain BEGIN IMMEDIATE. FULL sync, quick_check,
foreign-key policy, 150ms SQLite timeout, execution leases, gates and fences are
unchanged. Status reuses actions for metrics; capture reuses its final outbox read.
No database transaction is held across HTTP, subprocess execution or user waits.

## Upgrade, recovery and rollback

Stop older/nonparticipating clients before maintenance, as with existing restore.
Use the installed `knowledge-maintain` command against the original project root:

```text
knowledge-maintain index-upgrade-preview --root ROOT --destination ABSENT_BACKUP.zip
```

Save the returned `preview` object to `preview.json`, inspect it, then apply its
exact returned fingerprint (the wrapper object is not the apply input):

```text
knowledge-maintain apply --root ROOT --input preview.json --approve sha256:FINGERPRINT
```

This explicitly approved operation takes the normal execution lease, exclusive
gate and SQLite reservations; validates and backs up all existing Knowledge and
Harness state; fingerprints canonical rows, schema and source; and writes the
normal durable maintenance journal/fence before DDL. The index is transactional.
Crashes before/after its commit retain the fence. Ordinary clients refuse access
until `knowledge-maintain recover --root ROOT` verifies canonical fingerprints and
idempotently finishes. Stale approvals and conflicting index definitions refuse.
Prepared plans, denials, transfers, receipts, queue dispositions, pending runs and
execution evidence are not changed or acknowledged by index maintenance.

`index-rollback-preview` uses the same preview/apply/backup protocol and removes
only this derived index. Repeated apply/recover is idempotent. A normal same-root,
same-OS restore of the retained pre-upgrade archive also removes the index while
restoring its snapshot; preserve newer state before an intentional historical
restore. Do not transplant databases or rewrite root identities.

Standalone Knowledge and shared operational databases need no schema migration
for these changes. This index maintenance path has no Harness import; a project
without a journal is an explicit no-op with backup. It does not initialize or
modify a shared store. Existing shared backup/gate rules continue to apply.

See `reports/SQLiteOptimization` for hypotheses, reproducible valid fixtures,
baseline/candidate timings, writes/storage and exact-source qualification. A SQL
plan change is diagnostic; it does not establish a whole-agent speedup.
