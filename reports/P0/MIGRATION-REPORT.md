# Legacy migration report

## Provenance and supported input

Every record in `tests/fixtures.py::legacy_fixture` is synthetic. The supplied
ZIP contains empty canonical scaffolding, not production claims, durable queues,
or historical transaction state. No production migration parity is asserted.

Supported `.ai` snapshots use the provided exact v1 manifest/schema semantics,
JSON claim/evidence/relationship files under `knowledge/claims`, `evidence`,
`knowledge/relationships`, and optional offline transaction state. Unknown
record formats, invalid graphs, altered schemas, unfinished/orphaned journals,
or journals missing plans are refused before publication.

The actual supplied population transaction layout is checked:
`state/population/transactions/<plan-sha>/journal.json` references a sealed
`state/population/plans/<plan-sha>.json` with format `population-plan-v1`.
Plan/journal hashes use the original ensure_ascii encoding. Only terminal
COMMITTED/ROLLED_BACK journals are accepted. Seals prove content binding,
not historical human approval or business truth. No approvals are fabricated.
The synthetic sealed plan is deliberately minimal fixture history, not a
claim that the original private transaction data was available.

Because original candidate writers were intentionally omitted, the only
supported queue interchange is documented explicitly: `state/candidates.json`
is an array of `{id, payload, status, history}`, where payload is the new
candidate-operation v1 envelope and status is `pending` or `imported`. Other
private queue formats must be separately audited and converted; they are not
silently interpreted. Imported candidates must match actual canonical values.
Original IDs, values/status/history are retained in the immutable migration
manifest and migration history. Migrated operational queue keys also retain the
original candidate IDs; the captured payload digest validates their identity.
Imported operational entries receive a new migration-marked ACKNOWLEDGED
binding to exact canonical values, not invented historical approval receipts.

## Executed evidence

`python scripts/migration_evidence.py` writes `migration-results.json` with
before/after records, original queue, source-file byte manifest, semantic diff,
repeat result and restoration check. It uses confirmed and inferred claims,
active evidence, reciprocal conflict, dependency relationship, pending and
imported candidates, and sealed synthetic plan/journal history.

The semantic comparison checks exact object values and IDs, including confidence,
provenance, evidence links, depends_on, conflicts_with, relationships, candidate
states and import history. Zero removed/modified fields is the expected result;
file count alone is not the comparison. Source files are byte-equal after apply.

`MigrationTests` additionally executes missing-plan diagnosis, ambiguous dual
stores, stale preview approval, existing target refusal, process death during
staging, immediately before publication, and immediately after publication.
Retries safely complete or report already-migrated; no second canonical store
is merged. See `product-tests.log` for actual outcomes.

## Protocol and recovery

1. Stop all legacy writers and use an offline quiescent source copy.
2. Run `knowledge migrate-preview --root ROOT`; inspect records, preserved
   bytes and semantic diff. Its fingerprint binds source bytes and project.
3. Run `knowledge migrate-apply --root ROOT --approve EXACT_FINGERPRINT`.
   Source is re-read before atomic publication. Any changed source or nonempty
   target is refused. A private staging SQLite database is committed/closed,
   then the complete directory is renamed into the canonical path.
4. Validate/query `.knowledge`; retain `.ai` only as an archived immutable input.
   All new writes use Knowledge. Arbitrary legacy writes are not synchronized
   with the new store; offline/quiescent input is a prerequisite.
5. After a process interruption, inspect the store and retry the exact migration.
   Before publication, source is intact and target absent/empty. After publication,
   the complete store exists; identical retry is a no-op. Staging directories
   are never deleted by ownership guesswork.

For restore, use `knowledge restore-legacy --root ROOT --destination ABSENT_DIR`.
The destination must be a new absolute path without linked ancestors; files
are restored byte-for-byte from the captured manifest. This restores the input
snapshot, including original IDs/history; it does not overwrite active state.
The executable evidence checks complete byte equality and refusal to overwrite
an existing destination. Full ongoing SQLite-store backups should use SQLite's
backup API or copy only after all processes stop. Preserve hot journals after
crashes and run `knowledge recover`; never delete journals or reset Git.

Native Windows/NTFS, Windows junctions and cross-platform backup restoration
remain NOT RUN. The Linux protocol is tested; it does not certify a production
Windows upgrade/uninstall/rollback release, which belongs to P3.

## R1 discovery correction

Discovery includes the known external `.harness/knowledge/candidates/queue.jsonl`.
Its adapter is intentionally unsupported: present empty, nonempty, malformed and
coexisting files all refuse before publication with actionable discovery details.
No source is deleted or chosen silently. Convert on an offline copy to the supported
interchange envelope, retaining IDs, payloads, states/history and an external backup,
and explicitly resolve/remove the external file from selected input before retrying.
Supported queue bytes, selected/absent discovery states and source hashes bind
approval. Appearance of an external queue or any interchange byte change invalidates
the old preview. Restoration covers every selected source; unsupported external
sources are never claimed migrated or backed up.
