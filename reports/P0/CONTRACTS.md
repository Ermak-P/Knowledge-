# P0 contracts

## Ownership and boundaries

`knowledge-p0` owns the shared Project resolver, canonical records, queue, plans,
SQLite journal, validation, import, migration and read-only retrieval. CLI-only
installation has no third-party runtime dependencies. The optional MCP extra
requires MCP 1.30.0. `harness-p0` depends only on Knowledge and owns its read-only
response budget/configuration. Agent execution is explicitly `not-implemented`.
No Main/subagent executor, shell grant or tool-permission runner is delivered.
A future capture executor may call `submit_automatic`; discovery is a separately
scoped reader; approved import requires the exact fingerprint. These roles do
not imply unrestricted write permission for a future Main agent.

`.knowledge/store.sqlite3` is the only canonical writable store. Tables:
`records` (canonical v1 objects), `queue` (content-addressed immutable candidates),
`plans` (sealed previews and durable state), `history` (import/migration journal),
`metadata` (format, root identity, captured migration manifest). Exports are
snapshots, not alternate writable canonical stores. No executable tools are
copied into project data. `.harness/config.json` contains only consumer settings.

## Project identity and paths

Every public integration calls Project with an explicit existing root. Relative
paths resolve against current working directory; no ancestor/Git search occurs.
Identity is SHA-256 of the OS-normalized absolute path, not a remote repository
name. Linux case sensitivity is preserved; Windows uses native normcase.
Symlinks/junctions in root ancestors and store descendants, special filesystem
objects, hardlinked control files and `..` components are rejected. IDs never
become filesystem paths; SQL uses bound parameters. Evidence references are
metadata, never executed or opened as arbitrary paths by retrieval.

Stores copied to a different absolute root are rejected. Reconstruct from
original candidates or use explicit legacy migration for a different project;
there is no silent rebinding. Native Windows junction, case and locking behavior
is NOT RUN. Linux tests do not certify those semantics.

Trusted local filesystem ownership is assumed: adversarial replacement of
ancestor directories during an operation is outside the P0 guarantee. All
participating application writers must use Store; direct SQLite/file edits are
unsupported and are diagnosed where detectable, not prevented from an OS owner.

## Record, candidate and approval versions

The three provided v1 schema bytes/hashes are retained. Claim `status` is the
legacy confidence classification (`CONFIRMED`, `INFERRED`, `UNKNOWN`,
`NEEDS_HUMAN_CONFIRMATION`), not a lifecycle. Evidence `status` describes active,
retracted or superseded evidence. No confidence promotion occurs during import
or migration. CONFIRMED still requires appropriate direct evidence, reciprocal
substantiation, a location and last_verified, using the supplied validator.
Schema validity never establishes truth, authority, rationale or freshness.

Candidate envelope v1 has exactly `version`, `operation`, `records`; the latter
has arrays `claims`, `evidence`, `relationships`. Only `add` is supported.
Unknown envelope/record fields, lifecycle fields, nonfinite numbers, duplicate
JSON keys, invalid IDs, reused IDs and unsupported operations fail explicitly.
Cross-candidate graph references are checked as a complete batch at prepare;
errors block the entire plan, with structured diagnostics and no partial import.
P1 must introduce explicit versioned lifecycle contracts; it cannot reinterpret
v1 status values or silently accept ignored operations.

New candidate ID is a SHA-256 of canonical UTF-8 JSON. Migrated candidates
retain their original IDs with an immutable manifest binding to the payload hash. Deduplication occurs inside
the write transaction using stable IDs and NFKC/casefold/collapsed-whitespace
statements. Same-ID changed additions and mixed partial duplicates are refused;
fully identical normalized statements return a duplicate result without writes.
This does not detect semantic/paraphrase equivalents.

A plan fingerprint binds project identity, canonical snapshot, exact candidate
payloads and included/skipped/blocked arrays. Preparation is deterministic for
unchanged input. P0 has no partial-accept UI: blocked batch means zero included;
duplicates are reported at submission, so prepared skipped is normally empty.
`apply --approve` must equal the saved plan fingerprint; changed queue or
canonical input requires preparation and new approval. Seals detect changes;
they are not a digital signature or authentication of a human approver.

## Locking, state and recovery

SQLite BEGIN IMMEDIATE coordinates submit_manual, submit_automatic, CLI submit,
prepare, apply, acknowledge and recovery acknowledgments. Read/dedup/write
forms one critical section. Lock contention fails within 150 ms with
`store-busy-retry`; there is no indefinite loop. SQLite owns lock release,
including process death; application code never deletes an allegedly stale lock.
There is no supported raw queue-replacement API or second writer implementation.

State machine: PREPARED → COMMITTED → ACKNOWLEDGED. Canonical rows, COMMITTED
state and the import history entry commit together in one SQLite FULL-sync
rollback-journal transaction. Uncommitted inserts roll back on reopen. Apply
and acknowledgment are intentionally separate transactions. Acknowledgment
checks the immutable candidate payload, exact queue identity/binding, and every
committed canonical value; it never trusts a claim ID alone. Apply/ack retries
are idempotent. `recover` acknowledges only COMMITTED plans after the same checks;
it never applies a PREPARED plan. Unrelated changed records are preserved and
ownership mismatches refuse recovery. Keep recovery journals; never use Git
reset/clean or delete arbitrary files to roll back.

Initialization/migration builds a complete private SQLite store, commits and
closes it, then atomically renames the directory into `.knowledge`. Existing
nonempty targets are never replaced. On POSIX, an empty target directory can
be replaced; Windows requires an absent target. Source and target share a
filesystem. Directory sync is used on POSIX after publication. Crashes before
publication leave an unexposed disposable staging directory; crashes after it
leave a complete readable store. Stale private staging directories may be
inspected/removed manually after stopping their owning process; recovery never
guesses and deletes them. Atomicity relies on SQLite and local filesystem
semantics, not multi-file JSON writes. Network filesystems are not certified.

## Retrieval and adapters

The retained deterministic lexical engine ranks statements, identifiers and
evidence. Normal queries omit unconfirmed claims; opt-in includes explicit
confidence and provenance. Conflicts include partner confidence and warnings,
not an automatic resolution. Result `insufficient-evidence` is an honest
no-match under lexical/status policy, not proof no fact exists anywhere.

`max_bytes` limits serialized Knowledge context JSON in UTF-8; 256..1,000,000
bytes. `max_items` is 1..100. Too-small envelopes return `budget-too-small`.
This is a byte bound, not a model-token guarantee. MCP transport adds its own
protocol envelope. Lookup returns a full validated record or `no-match`.
Harness reserves envelope space and enforces its complete response byte limit.
Missing/busy Knowledge yields explicit degraded/unavailable mode; invalid
canonical data/corruption is never successful empty knowledge. No read-only
operation falls back to another project.

CLI emits one JSON object, exit 0 for success and 1 for operation errors;
argument usage errors use argparse stderr and exit 2. Exact public arguments
are in `knowledge --help` and README. MCP exposes only read tools. Original
MCP concepts/names are retained; server name and argument identifiers are
versioned by this new adapter, not promised identical to unseen integrations.

## Legacy interface limits

`legacy_validator` is a refactored internal validator, not the archived CLI or
installer. Legacy `.ai` writes, old populate CLI, scanner/normalizer defaults and
original writer interfaces are unsupported. Use migration and the shared v1
writer API. There is no dual-write facade. Original missing Harness/writer code
was not repaired or tested in place. The legacy snapshot after migration is an
archived source only. See MIGRATION-REPORT.md for exact supported queue/journal
shapes and preservation guarantees.
