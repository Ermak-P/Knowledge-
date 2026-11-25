# Agent Task: Preserve Existing Knowledge During SQLite Project Identity Migration

Repository: https://github.com/Ermak-P/Knowledge-

Implement a supported, explicit migration from an existing Knowledge SQLite store whose recorded project identity differs from the current project identity. The user wants the existing data transferred into a usable new database, not an empty initialization or replacement by a new source scan.

This is a Knowledge product task for Codex. Access to the user's Windows computer or private database is not assumed. A local agent will perform inventory and the actual migration using the installed implementation. Do not claim that the user's data has been migrated merely because code or instructions were delivered.

## 1. Confirmed incident and inputs

The installed machine MCP is connected, `knowledge_capabilities` resolves the intended workspace and provider, but `/knowledge-init` fails with `project-identity-mismatch` before a worker/scan ID is created.

The user ran a read-only query using the installed runtime and supplied:

```json
{
  "root": "C:\\Git\\IPM",
  "database": "C:\\Git\\IPM\\.knowledge\\store.sqlite3",
  "expected_identity": "3d53c8adb5c1bbae152228bca9fc52694a0e341b7c8b4b3a5358144bdac4e81b",
  "stored_identity": "9288d2dc6272e55eb712c34023bbbc9f29da28487a92d95ea5d52a21a71bf0ad",
  "matches": false,
  "counts": {
    "records": 1394,
    "queue": 697,
    "plans": 1
  }
}
```

These are observed baseline counts, not a complete inventory. `records` includes multiple record kinds; do not describe all 1394 records as claims. The queue dispositions and the plan state are not yet known. The old root cannot be recovered from a hash alone; do not invent it. The user identifies this as their old database and explicitly wants its data retained for IPM.

In the inspected implementation, `Store._connection` compares `metadata.project` against `Project.identity`. The current identity is a digest of the normalized absolute root. `knowledge_capabilities` does not open/validate this store, so its success does not establish database compatibility. Ordinary restart, MCP registration, or a fresh scan cannot resolve this stored identity mismatch.

## 2. Existing product boundaries to inspect

Inspect the current checkout and AGENTS.md, particularly:

- `knowledge/project.py`, `store.py`, and all root-bound validation paths.
- `knowledge/migration.py`, `maintenance.py`, and their CLI entry points.
- `project_commands.py`, `machine_mcp.py`, scan jobs, and project configuration.
- Lifecycle revisions, queue/plan/receipt bindings, operational memory, transfers, CR workflows, and any other installed SQLite extensions.

The existing `.ai` migration is a different input contract. It must not be presented as a working SQLite-to-SQLite migration. Current maintenance restore deliberately refuses another root; changing a root-bound store requires a separate explicit operation, not removal of that guard.

Do not implement the fix as `UPDATE metadata SET value=...`, disabling identity checks, deleting `.knowledge`, or renaming the old database away and calling ordinary init. Those approaches do not establish preservation or consistency of the remaining bound objects.

## 3. Required migration workflow

Expose a documented preview/apply/recovery interface for this SQLite source contract. Choose names consistent with the existing CLI; names suggested here are design requirements to implement, not claims that such commands already exist.

### 3.1. Read-only inventory and actionable preview

Provide an explicit source-store reader that checks the supplied old identity and recognized source format without requiring the source to match the destination root. Keep this exception confined to migration inventory/validation; ordinary store operations must retain their identity enforcement.

Inventory every user table, schema/extension version, record kind, lifecycle revision/history, queue disposition, plan/receipt state, operational-memory record and event, and referenced artifact. Inspect any incomplete transaction or existing recovery state before choosing a migration route. Unknown or inconsistent structures must produce an explicit blocker rather than silently being omitted.

The preview must bind the exact source database/snapshot, old identity, destination root/new identity, selected migration rules, complete preservation manifest, artifact locations, backup and staging destinations, and collision policy. Report actual counts by kind/state, preservation mapping, unsupported items and required decisions. Do not expose private record contents or credentials in ordinary terminal output.

The local incident source is already located at the final database path. Treat this as an in-place cutover from old bytes to a staged new database, with the old bytes archived intact. Do not require a fictitious usable source checkout merely to pass normal root checks.

### 3.2. Consistent backup and staging

Before any cutover, quiesce participating Knowledge/Harness writers using supported ownership/maintenance coordination. Account for other versions and unresolved transactions; do not kill unrelated processes.

Capture a consistent source using the SQLite backup API or another documented consistent snapshot mechanism. Preserve the original source and the required referenced artifacts, including recovery files where relevant. Do not copy only the main SQLite file while ignoring an active WAL/hot journal, and do not delete recovery journals. Archive material outside the project's scanned source tree.

Build the destination in a separate staging area. Do not update source rows in place. Preserve source fingerprints and validate that the approved source has not changed before publication.

### 3.3. Preserve data and distinguish historical authority

- Preserve canonical claims, evidence, relationships, stable IDs, confidence, provenance, and lifecycle state. Do not silently promote confidence, reactivate retired claims, or erase supersession/history.
- Preserve every queue candidate, its original payload/identity and disposition, including rejected/deferred items. Root/source-bound pending candidates require current evidence and revision validation before any later application; migration must not apply or acknowledge them automatically.
- Preserve the existing plan and all receipts/history as auditable historical data. An old approval must never become authority for effects under the new identity. Document how committed/imported queue bindings and historical receipts remain internally consistent and readable without re-signing them as new approval.
- Preserve operational instructions and their history. Machine/resource-specific execution grants and bindings must not automatically become current grants for a changed environment. Retain the original intent and show any required revalidation/rebinding.
- Preserve discovered scans, CR workflow data, transfer state, and other extensions as supported current data or explicit accessible historical archives with mappings. Historical sessions, process IDs, approvals, or ownership receipts must not become permission to control new processes or resume an old run in the new root.
- Handle absolute evidence/artifact paths by an explicit verified mapping. Do not globally replace strings, invent an old root, or claim evidence freshness from successful migration. Keep unverifiable evidence identifiable for later reconciliation.
- If some objects must remain in an immutable archive to preserve their original bindings, make them accessible and explicitly account for them in the report. A backup ZIP alone is not a substitute for making the preserved project knowledge usable in the new database.

### 3.4. Validate, apply and recover

Use the existing exact-preview approval pattern for migration publication. The user's stated intent authorizes preparing the implementation and migration preview; do not manufacture a fingerprint approval or reuse an unrelated old plan's approval. Present the concrete local preview before cutover.

Before publication, require successful SQLite integrity checks and full product validation against the destination identity. Compare record IDs and payloads/semantic values, revisions/history, candidate dispositions and every preservation-manifest entry. Counts alone do not establish preservation. Any changed binding or archived object needs a documented mapping and a reason.

Publish only the validated staged state under the maintenance fence. Preserve the original state and provide a deterministic journaled rollback/recovery path appropriate to native Windows file locking. Do not report success before the new store and local references validate. On interruption, ordinary operations must see either the valid old state, the valid new state, or a clear recovery fence.

Repeated application of the same completed migration must be idempotent. A different source fingerprint or destination must not silently reuse an old approval. Do not merge into an unrelated populated destination automatically.

## 4. Diagnostics before scan creation

Fix the misleading failure path that led to this incident:

- Report the database path and expected/stored project identities with `project-identity-mismatch`, without dumping database contents.
- Provide bounded diagnostics when no scan/job/checkpoint exists yet. Missing job files must not become an unhelpful generic `project-or-filesystem-error`.
- Do not suggest that restarting/re-registering MCP or selecting `fresh` repairs a database identity mismatch.
- Distinguish database project identity from declaration/symbol identity diagnostics and provider/run bindings.
- A blocked scan does not prove the database is empty or that previous candidates were never queued. Distinguish the failed invocation from pre-existing database data.

## 5. Delivery and local application runbook

Deliver the migration implementation and a short English/Russian runbook with exact commands from the implemented CLI. Include it in the installed wheels/kit and machine update workflow; no edits to installed `site-packages`, ownership markers or file hashes by hand.

Separate the two roles:

1. Codex implements the generic supported migration and provides a static implementation review. It must not claim to inspect or modify `C:\Git\IPM` from a remote environment.
2. The local IPM agent updates the installed product, inventories the real old database read-only, produces the source-bound preview and backup/staging plan, and presents its exact fingerprint. It applies only the specifically approved migration, validates the new store, and records the archival/rollback locations.
3. After successful migration, ordinary `/knowledge-init` reconciles the retained knowledge with current sources. It must not treat all existing knowledge as new facts or automatically apply a newly generated candidate plan. `/knowledge-candidates-push` remains a separate exact-approval workflow.

The final local report must account for the observed baseline of 1394 records, 697 queue items and 1 plan, plus every other table/extension discovered. If actual counts have changed, establish a new explicit snapshot rather than forcing the database to match this older report. List preserved active data, accessible archived data, unresolved evidence/bindings, integrity/validation results, old/new identities, backup location and rollback command.

## 6. Execution limits

Do not run automated tests unless the user separately requests them. Perform static review now and document unexecuted regression cases. Operational inventory, consistent backup, migration preview, and integrity/product validation of a locally staged or migrated database are part of the data-preservation workflow; they must not be skipped or falsely reported as executed.

Required future regression coverage to document: nonempty lifecycle/queue/receipt preservation, unknown extension refusal, stale-source/approval refusal, interrupted Windows cutover, idempotent reapply, malformed/foreign destination, no-job diagnostics, preservation of rejected/deferred candidates, and old approvals not authorizing new-root effects.

Do not upload the user's database, private source or logs to GitHub. Use synthetic minimal examples if fixture code is needed. No model, provider endpoint, SDK, subagent architecture or unrelated Harness changes are required for this task.
