# SQLite identity migration — implementation/static review

Request: tasks/Knowledge-SQLite-Identity-Migration-Codex-Task-EN.md.
Branch: codex/sqlite-identity-migration; base 925b10d4 (current main, including
the prior core reliability implementation). This is a product implementation,
not a migration of the owner's database.

**Automated tests: NOT_RUN, explicitly prohibited by this request.**
**Windows execution / actual inventory / staged database validation / IPM cutover:
NOT_RUN here.** The implementation requires backup/integrity/product validation
locally before publication; those runtime checks must not be skipped. Packaging
and AST/manifest review do not establish that those runtime checks have passed.
No source/provider/model/SDK changes on the owner's machine were performed.

## Root cause and code boundaries

Store._connection enforces metadata.project == Project.identity (normalized
absolute-root hash). Capability discovery does not call this check. Therefore
capabilities can succeed while initialization fails before creating a worker.
Fresh, registration and restart do not alter this compatibility boundary.
The incident numbers (1394 records of multiple kinds, 697 queue entries, 1 plan)
and supplied old/new identities are user observations, not a remote inventory.
The old root is not derivable from its hash.

The new identity_migration module validates an explicitly supplied old identity
only while reading/validating a recognized source. It returns no alternate-
identity Store handle. Ordinary Store identity checks remain mandatory; their
error now contains database path, expected/stored identity and actionable next
step. Same-root maintenance restore and the distinct .ai migration are unchanged.
No source UPDATE of metadata.project is used. A new staged DB is built and
validated, then directories cut over under existing maintenance coordination.

## Explicit preservation rule

Canonical records, exact payload strings, IDs, history and lifecycle revisions
are copied to active tables unchanged. Every original row of every recognized
source table is also preserved in identity_archive with original columns,
ordering and per-row hash. Source DDL is inventoried; no supplied DDL is executed
to construct the destination. Recognized P0/P1/operations schemas are checked
against trusted definitions; unknown structures block.

Queue payloads/IDs/dispositions, plans and committed/imported bindings, receipts,
scans, CR/transfer/provider/capture state and operational records/events remain
accessible through identity-history, retaining all original relationships in the
archive. They are intentionally not current execution authority. Old prepared
or committed plan IDs are absent from live plans, so normal apply/acknowledge
cannot execute them under the new identity. Source ownership receipts remain
auditable, not automatic permission to overwrite reviewed canonical knowledge.

This deliberately quarantines old pending candidates and operational instructions
as history rather than re-signing their bindings. The local preview makes this
consequence explicit. Later fresh v2 submissions require meaning/evidence/revision
review and a separate current approval. Operational intent/history is readable,
but current applicability and grants require explicit supported re-enrollment.
Canonical data is usable through normal lookup/history/export/reconciliation,
not an empty store awaiting a replacement scan. Normal status/export additionally
reports archived counts so live-queue emptiness is not mistaken for data loss.

Absolute evidence is retained unchanged/unresolved with ID/field/reference-hash
diagnostics. No old root or global string mapping is invented. Metadata artifacts
are mapped to the external original directories and hashed; CR artifacts require
their recorded matching bytes. Machine configuration/Harness process state is
archived rather than automatically rebound or resumed. Recognized Harness
tables are inventoried and a consistent snapshot retained when present; unknown
tables/indexes/columns block. This adds no dependency on Harness for standalone
Knowledge use without Harness state.

## Static review of publication/recovery

* Read-only source inventory uses a SQLite transaction and integrity_check, not
  a main-file copy. Supplied source identity, schema/extension, every table and
  logical row fingerprint are checked. Histories and canonical graph validate.
* Preview holds existing participating writer/maintenance locks, inventories
  incomplete state and binds all source/artifact/workspace/rule choices. A
  nonempty rollback journal, incomplete transfer/maintenance/migration or unknown
  extension is a blocker; recovery files are not deleted to bypass it.
* Apply requires the exact preview fingerprint, recomputes the approved source,
  uses the SQLite backup API, revalidates that snapshot, builds a distinct staged
  DB and compares active and archived row digests. Staged and published DBs run
  full integrity and product validation before success.
* Pre-release physical copies include main/WAL/journal bytes; a consistent API
  snapshot is retained separately. Original directories are renamed intact into
  the external same-volume workspace, preserving metadata artifacts and recovery
  files. SQLite can checkpoint on closing reservations; raw pre-release bytes
  are retained separately. Coordination lock bytes are not user artifacts.
* BUILDING/PREPARED journal and maintenance fence cover interruption. SQLite and
  legacy metadata handles close before Windows directory rename; the stable
  execution lock and exclusive gate remain held. Failure leaves old valid state
  or a recovery fence, never an asserted successful empty initialization.
* Recovery identifies its own root/rule/transaction/approval and refuses another
  active fence or intervening destination changes. It restores old source state
  for incomplete operations and validates completed state without replaying plans.
  Completed rollback requires its own separately approved rollback preview.
* Reapply of the same completed preview validates its archive transaction and is
  idempotent. Different root/source/workspace changes the fingerprint; rolled-back
  or incomplete transactions require recovery/new preview, not approval reuse.
* Missing job/checkpoint returns bounded NOT_STARTED/PRE_SCAN diagnostics with
  actual existing counts only after normal identity validation. Identity mismatch
  is reported before inventing a scan ID or claiming prior data is absent.

Static limitations: this rule supports recognized first-time SQLite identity
cutover only, not unrelated destination merging or a second relocation of its
own new extension. A .ai directory requires separate explicit resolution.
External evidence without verified mapping stays unresolved. All old operational
memory is historical, not an automatic active-instruction copy. Backups/workspace
must be private, absent, outside the project and on its volume. Quiescence applies
to old clients/direct SQL programs too; arbitrary nonparticipating writers cannot
be made safe by an identity hash. Archive validation is proportional to archived
rows, with transaction-local validation reuse, not a persistent trust cache.

## Required future regression cases — documented, not executed

| Case | Required oracle |
|---|---|
| Nonempty P0 and P1 | Every canonical ID/payload/revision/graph and history matches approved source |
| 1394/697/1-shaped synthetic input | Counts by kind/state plus every per-row digest; never infer 1394 claims |
| rejected/deferred/imported/pending candidates | Original payloads/IDs/dispositions/bindings readable; no auto import/ack |
| COMMITTED/PREPARED/ACKNOWLEDGED plans | Original receipts remain consistent history; old approval cannot apply new-root effects |
| Operational memory / CR / transfers / scans | Original IDs/intents/history preserved; no inherited grants, process control or resume |
| Unknown/altered extension/schema/version | Explicit blocker, source and journals preserved |
| Stale DB/WAL/artifact or wrong fingerprint/root | Cutover refused, approval cannot be reused |
| Missing/corrupt CR artifact / absolute evidence | Required artifact blocks; unverified evidence stays identifiable, never freshly verified by migration |
| Held writer / Windows sharing violation | No unrelated kill, no success; recoverable own fence |
| Fault at BUILDING/fenced/old-dir rename/new publication/commit | Valid original, valid published or clear fence; deterministic recovery preserves both states |
| Recovery interrupted during rollback | Repeated recovery validates original and restores remaining archived directories |
| Completed rollback / post-migration writes | Separate rollback approval; intervening writes prevent destructive overwrite |
| Completed reapply / different input | Same completed preview idempotent; changed source/destination cannot reuse approval |
| Foreign/malformed destination, source SQLite hot journal | Refuse merge/corruption, do not delete recovery files |
| No job/incremental pointer/checkpoint | Bounded pre-scan diagnostics, detailed project mismatch, no claim of empty DB |
| Wheel/kit/source update | New module, packaged runbook and CLI delivered; no site-packages/marker edits |

The English/Russian runbook is docs/P4/SQLITE-IDENTITY-MIGRATION.md and is mirrored
byte-for-byte in the wheel's knowledge/docs directory. The existing kit builder
copies docs/P4 into kit/runtime docs. See source/static/asset manifests in this
packet for actual static and packaging checks, without runtime test claims.
