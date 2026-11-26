# Knowledge consumer access and maintenance

## Install or upgrade

Use Python 3.12. The machine installer defaults to `readonly` on a fresh installation.
Updating an existing installation preserves its recorded mode. Installations
created before modes were introduced retain maintainer access. OpenCode
registration uses the Promise Plugin API and reports missing capabilities with
the observed host version. Local MCP clients can launch the same server directly.

```sh
./install.sh --mcp-dir /path/to/local/knowledge
./install.sh --mcp-dir /path/to/local/knowledge --mode maintainer
/path/to/local/knowledge/bootstrap/bin/python -I -B /path/to/local/knowledge/launch.py mcp --workspace /path/to/project
```

```powershell
.\install.ps1 -McpDir 'C:\LLM\mcp\knowledge' -Mode readonly
.\install.ps1 -McpDir 'C:\LLM\mcp\knowledge' -Mode maintainer
```

The installer stores the mode in the local installation pointer. Reuse the
installation command with an explicit mode to switch it. Restart OpenCode and
other MCP clients after upgrading. A consumer installation requires neither
Harness nor an LLM provider. Its catalog includes context, claims, evidence,
instructions, and capabilities. The backend denies scan, candidate submission,
planning, and source synchronization even when a client sends the tool call
directly.

For a shared database, give consumers read permission on the project database
and control lock plus traversal permission on their parent directories. Allow
source reads where consumers need evidence freshness. Keep write permissions on
the database, project artifacts, and the maintainer installation restricted to
maintainers. Consumers must resolve the project at the same absolute path as
the recorded project identity. The consumer opens SQLite with `mode=ro`. Use
the default rollback-journal store or a consistent SQLite snapshot. Consumer
connections refuse WAL databases because SQLite may create sidecars or update
shared-memory state even under a read-only connection. Installation mode applies
to Knowledge's interfaces. OS permissions govern direct file access.

## Move existing project runtime paths

| Previous project path | Current project path |
| --- | --- |
| `.knowledge/store.sqlite3` and SQLite sidecars | Same path |
| `.maintenance/` | `.knowledge/maintenance/` |
| `.harness-writer.lock` | `.knowledge/locks/.harness-writer.lock` |
| `.knowledge-control.lock` | `.knowledge/locks/.knowledge-control.lock` |
| Initialization and import staging directories in the project root | `.knowledge/tmp/` |

Knowledge and Harness share the stable project writer lock. Knowledge's ordinary
transactions take the control lock in shared mode. Maintenance takes the writer
lock before the exclusive control lock. Harness also retains its project
metadata lease in `.harness/` for compatibility with its process recovery
protocol. Machine worker diagnostics live in per-installation state outside the
project. Shared Knowledge continues to use its existing storage directory.

1. Stop all Knowledge and Harness processes for the project, including detached
   scan and plan workers. Upgrade every runtime that can access the project.
2. Run `knowledge-maintain runtime-migrate --root /path/to/project --offline`
   using the maintainer runtime. A busy legacy lock or conflicting maintenance
   directory causes a refusal with the original data preserved. Retry the
   command after resolving the reported blocker.
3. If migration reports a maintenance recovery fence, finish it with
   `knowledge-maintain recover --root /path/to/project` before resuming writes.
   Restart the upgraded clients after migration succeeds.

The migration preserves the existing database and does not require a full scan.
Run the cutover offline because older runtimes can recreate the old lock files
after a move. An upgrade leaves project paths alone until the offline operation.
Initialization and migration use the repository-local Git exclude file to keep
`.knowledge/` out of Git without editing tracked ignore rules. Source discovery
excludes runtime data even when the discovery policy includes hidden paths.
Content-addressed CR receipts retain their existing evidence verification path.

## Disable Harness capture

Use `"capture": "off"` in the project's `.harness/runner.json`. Omit the field
when setting up a new runner to use the disabled default. `optional` and
`required` remain explicit opt-ins, and upgrades preserve them.

With capture disabled, Harness skips capture extraction and delivery. Its
normal build, test, review, and final source checks still run. Read-only
Knowledge suppresses automatic capture even when the configured Harness policy
is enabled. Disabling capture leaves pending outbox items intact. A delivery
retry reports `capture-disabled`. To resume pending delivery, restore the
run's original validated capture configuration on a maintainer installation,
then invoke its usual capture retry. Other configuration or source drift still
requires revalidation.

## Review plan retention and reclaim SQLite space

Run the CLI with the same Python runtime that writes the database. `storage`
reports SQLite file size, allocated bytes, free pages, and payload bytes by
record or plan status. Builds with SQLite `dbstat` also provide page counts
for tables and indexes.

```sh
knowledge-maintain storage --root /path/to/project
knowledge-maintain plans-preview --root /path/to/project --keep-recent 2 --older-than-days 30 --compact-receipts --vacuum
knowledge-maintain plans-clean --root /path/to/project --input reviewed-preview.json --approve 'sha256:<fingerprint>'
```

Save the exact `preview` object from the second response as
`reviewed-preview.json`. Review the listed fingerprints and use the response's
exact approval fingerprint. The report gives payload bytes eligible for
reclamation. Use the before and after file sizes to measure actual disk
reclamation.

Retention considers prepared plans invalidated by canonical changes and
superseded preparations in the same preparation series. It keeps the current
preparation for each series, all committed plans awaiting acknowledgment, and
all acknowledged plans. Undated obsolete legacy plans are eligible only with
`--include-undated`. Same-base preparations from before tracking began stay
until their canonical base is obsolete. The policy runs only when explicitly
approved. Cleanup uses the project writer lock, the existing maintenance gate,
and one SQLite transaction. A repeated approval can finish an interrupted
cleanup or optional vacuum. While the exclusive maintenance gate is held, new
consumer queries can receive a busy response and retry after maintenance.

Knowledge verifies both legacy full receipts and compact references to the
same canonical plan fingerprint. New commits write references, and the
optional maintenance compaction rewrites eligible acknowledged legacy
receipts in place. Plans and receipts stay in the same database. Back up the
database before downgrading to a runtime that only supports full receipts.
Restoring a pre-upgrade backup restores its earlier canonical state, so
retain the current database if it contains subsequent changes.
