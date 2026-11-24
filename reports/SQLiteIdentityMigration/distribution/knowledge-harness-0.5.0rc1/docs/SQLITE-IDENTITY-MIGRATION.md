# SQLite project identity migration / Перенос SQLite при смене идентичности

This is an explicit SQLite-to-SQLite operation, not `.ai` migration, an empty
initialization, a metadata UPDATE, maintenance restore to another root, or a
replacement source scan. Codex supplies implementation/static review only.
**The owner's IPM database has not been inspected or migrated by Codex.**
Automated regressions and native Windows execution are NOT_RUN for this delivery.

## Contract and preservation rules

An identity is a hash of a normalized absolute root; the old hash cannot reveal
the old root. A connected MCP and successful knowledge_capabilities do not open
or validate the project database. Restart/registration/fresh do not fix its
recorded identity. Ordinary Store validation still requires the current identity.
Only the migration inventory validates a supplied old identity against a
recognized source; it exposes no general alternate-identity Store connection.

The first supported rule is
`canonical-and-revisions-active-control-objects-historical-v1`. Review and approve
this rule explicitly; it does **not** keep old approvals or pending work live:

| Source data | Destination / effect |
|---|---|
| records: claims/evidence/relationships | Same IDs, exact payload strings and values, confidence/provenance/lifecycle preserved in active records |
| lifecycle revisions and history | Same revision payloads, ordering, retirement/supersession and audit events; old plan references remain historical references |
| every source table, including metadata | Every original row and column mapping copied into checksummed identity_archive, including a duplicate of active-preserved rows |
| queue: pending/imported/rejected/deferred | Original IDs, payloads, dispositions and bindings accessible through identity-history; not activated in the new live queue |
| PREPARED/COMMITTED/ACKNOWLEDGED plans, receipts/reviews | Exact original values in accessible history; old approval cannot prepare/apply/acknowledge a new-root effect |
| scans, CR sessions, capture/provider/refresh/transfer receipts | Accessible original history, never resumed as current jobs or grants |
| operational current/history/events | Original intent, IDs, history and events accessible in history; no active operational extension is copied into the new environment |
| .knowledge supporting files | Entire original directory archived externally; CR artifact hashes validated; explicit discovery.json copied to staged metadata |
| .harness, when present | Validated recognized state and consistent DB snapshot, all files archived externally; processes/enrollments never resumed automatically |
| machine.json / provider enrollment | Original archived, no global provider rewrite; later explicit knowledge-init binds the current installation normally |

The active queue/plan tables deliberately start with no historical execution
authority. **This does not discard the observed 697 candidates or the one plan**:
they remain row-for-row readable through the supported history interface. Status
and export expose identity_history counts/dispositions alongside current live
data. Canonical knowledge is populated from the source, not rediscovered as
replacement facts. A backup ZIP alone is not the usable destination.

Review old pending candidates using identity-history, validate their meaning,
current evidence and expected revisions, and submit freshly reviewed v2 proposals
with current source binding using existing Knowledge APIs. Keep old archived IDs
and decisions as audit history; do not copy SQL rows back into live tables or
reuse an old plan fingerprint. Re-enroll operational instructions through the
supported memory APIs only after reviewing their applicability/intent and
obtaining any current required execution permission. Original operational grants
and process IDs are historical data only. No model/provider change is required.

Absolute evidence references remain unchanged and explicitly unresolved: the
inventory identifies record ID/field/reference hash, without guessing an old
root or globally replacing strings. Migration does not establish freshness.
Current root-relative evidence is evaluated later by normal freshness checks;
missing/absolute/unverifiable evidence remains identifiable for reconciliation.
All discovered metadata artifact paths have a path-to-archive mapping and content
hashes. CR supporting references require actual existing matching bytes; missing
or inconsistent artifacts block. External source references are not read as an
unrestricted filesystem backup. Archived process/configuration paths grant no
permission to execute or control the resources they name.

Unknown user tables/metadata extensions, modified Knowledge DDL/constraints,
unknown scan extractors, inconsistent revisions/receipts, and unresolved transfer
state block. This version does not accept a second identity relocation of an
already migrated store: its migration extension is an explicit unsupported source
until a separate supported rule is implemented. It never silently omits it.
Nonempty/empty `.ai` input also requires separate explicit resolution; this
operation does not combine two different source contracts automatically.

## Quiescence, backup, staging and recovery

Stop old MCP clients, detached workers and Harness runs through their normal
interfaces. Do not kill unrelated processes. The implementation takes the
participating execution lease, exclusive maintenance gate and SQLite reservations;
pending process specifications are handled by existing maintenance coordination.
An open native Windows handle can still make rename fail: the fence remains and
recovery is required. Arbitrary programs ignoring Knowledge coordination are not
made safe by a SQLite identity hash; keep old versions and direct SQL writers
quiescent throughout preview/apply/recovery.

The workspace must be new/absent, private, outside the project, with an existing
parent on the **same volume**. It contains:

* source.sqlite3: SQLite backup-API snapshot, validated under the old identity;
* harness-source.sqlite3 if applicable: consistent supported Harness snapshot;
* physical-knowledge / physical-harness and physical-manifest.json: pre-release
  physical files, including WAL/journal bytes, excluding coordination lock files;
* staged: new database before publication;
* knowledge-original / harness-original: original directories after cutover;
* rolled-back-new if a published destination is rolled back.

The API snapshot is the consistent SQLite backup; raw main/WAL copies alone are
not presented as a safe database backup. Nonempty rollback journals block before
the migration opens writer reservations: resolve with the original runtime's
supported recovery, never delete a journal. SQLite may checkpoint when normal
reservations close; pre-release physical bytes and the consistent snapshot remain
retained separately. No source SQL row is updated during migration.

Preview binds source schema, every table's columns, count and ordered row digests,
logical snapshot identity, old/new identities/root, artifact hashes/locations,
workspace/staging/original paths, rules and collision policy. Apply recomputes the
preview, checks the exact approval, validates backup and staged state and compares
active row digests and every archived row before publishing. Unknown/inconsistent
data fails closed. Input/state/artifact changes require a new preview; counts
alone do not prove preservation. The default aggregate source/file limit is
128 MiB per source row snapshot/file; exceeding it is a blocker, not truncation.

Journal: `<root>/.maintenance/identity-<transaction>.json`. BUILDING records
prepublication progress; PREPARED plus active.json fences cutover. Publication
renames original directories into the external workspace and staged .knowledge
into place. Under the fence, the published store validates before COMPLETED is
recorded and the fence removed. Original plans and grants are never re-signed.
Before a fence, a failed build leaves the original state valid and a recovery
journal. During cutover, ordinary operations are fenced. Recovery rolls back
incomplete cutover deterministically; completed recovery only validates/clears
its own fence. A mismatched fence/intervening destination write blocks recovery.

Repeat apply of an already completed exact preview returns already-completed
after current identity/archive validation. Another preview/source/root cannot
reuse its approval. Completed rollback requires a separate rollback preview and
its exact approval; it refuses new metadata/database writes after migration.
After fresh scans/new decisions, keep those writes and use a separately reviewed
recovery plan rather than forcing this immediate rollback. No database merging,
marker deletion, file-hash patch or SQLite repair is part of the runbook.

## Local IPM agent: English / Русский порядок действий

Codex implements the product; the local agent inventories real data, shows the
concrete preview to the owner, then applies **only its explicitly approved exact
fingerprint**. Do not manufacture approval from the preview's fingerprint field.
Do not upload the owner's DB, source, private previews or logs to GitHub.

1. Back up the installed machine/host configuration privately and quiesce old
   clients/writers. Update from branch `codex/sqlite-identity-migration` or its
   verified kit using the existing one-parameter installer. No site-packages edit.

```powershell
.\install.ps1 -McpDir 'C:\LLM\mcp\knowledge'
$McpDir = 'C:\LLM\mcp\knowledge'
$Current = Get-Content -Raw -Encoding UTF8 (Join-Path $McpDir 'current.json') | ConvertFrom-Json
$Runtime = Join-Path (Join-Path $McpDir $Current.runtime) 'Scripts\python.exe'
$Project = 'C:\Git\IPM'
$Old = '9288d2dc6272e55eb712c34023bbbc9f29da28487a92d95ea5d52a21a71bf0ad'
$Parent = 'C:\LLM\knowledge-migrations'
New-Item -ItemType Directory -Force -Path $Parent | Out-Null
$Work = Join-Path $Parent 'IPM-new-absent-migration'
```

The actual root should compute expected identity
`3d53c8adb5c1bbae152228bca9fc52694a0e341b7c8b4b3a5358144bdac4e81b`.
If the local inventory reports another root/identity or changed counts, stop and
establish that explicit new snapshot; do not force old incident numbers.

2. Инвентаризация только для чтения. `records=1394` — сумма разных типов,
   не 1394 claims. Исходно наблюдались queue=697 и plans=1; их состояния ещё
   неизвестны. Проверить каждый table/extension, actual counts by kind/state,
   revisions, artifacts and incomplete recovery state.

```powershell
& $Runtime -I -X utf8 -m knowledge.maintain_cli identity-inventory --root $Project --old-identity $Old
$Raw = & $Runtime -I -X utf8 -m knowledge.maintain_cli identity-preview --root $Project --old-identity $Old --workspace $Work
$Preview = $Raw | ConvertFrom-Json
if ($LASTEXITCODE -or -not $Preview.ok) { throw 'Preview blocked; preserve diagnostics and resolve the stated cause' }
$PreviewFile = Join-Path $Parent 'IPM-identity-preview.json'
[IO.File]::WriteAllText($PreviewFile, ($Preview.preview | ConvertTo-Json -Depth 100), (New-Object Text.UTF8Encoding($false)))
$Preview.fingerprint
```

3. Представить владельцу preview, точный fingerprint и последствия правила:
   canonical/revisions останутся рабочими; старая queue, планы, operational memory
   и сессии станут доступной историей без действующих полномочий. Показать
   реальные количества, сохранённые ID/hash mappings, unresolved absolute evidence,
   backup/staging/archive paths и blockers. **Остановиться до отдельного approval.**

```powershell
$Approved = 'PASTE_ONLY_THE_FINGERPRINT_EXPLICITLY_APPROVED_BY_THE_OWNER'
& $Runtime -I -X utf8 -m knowledge.maintain_cli identity-apply --root $Project --input $PreviewFile --approve $Approved
if ($LASTEXITCODE) { throw 'No success claimed; inspect maintenance status/recovery journal' }
```

4. Сохранить transaction ID из ответа. Проверки consistency, backup/staged/source
   equality и full product validation обязательны и выполняются внутри apply до
   cutover. Локально подтвердить итог обычными интерфейсами:

```powershell
& $Runtime -I -X utf8 -m knowledge.cli validate --root $Project
& $Runtime -I -X utf8 -m knowledge.cli status --root $Project
& $Runtime -I -X utf8 -m knowledge.maintain_cli identity-history --root $Project
& $Runtime -I -X utf8 -m knowledge.maintain_cli identity-history --root $Project --table queue --cursor 0 --limit 20
```

`--contents` explicitly returns original row values for private local review;
default history pages expose hashes/ordinals only. `columns` supplies the mapping
to original ID/payload/status/binding. Follow next_cursor. Read plans, receipts,
operational_current/history/events, scans, reviews, metadata and history the same
way. This is not an unrestricted SQL executor and cannot run an archived plan.
For full canonical/lifecycle values use ordinary lookup/history/export. Reconcile
all original tables and row digests with the private preview, not just counts.

5. Повторно открыть IPM в OpenCode, проверить intended workspace/provider и
   выполнить обычный `/knowledge-init` для reconciliation сохранённых фактов.
   Нет автоматического переноса approval, перепривязки grant, применения queue
   или сброса уверенности/retirement. Не создавать все старые знания как новые
   факты. Ownership/absolute-evidence gaps требуют review. После review новые
   source-bound предложения и `/knowledge-candidates-push` — отдельный workflow
   с новым конкретным approval, не approval миграции.

## Interruption and rollback commands

```powershell
& $Runtime -I -X utf8 -m knowledge.maintain_cli status --root $Project
# Read identity_transactions / active fence; choose the reported transaction:
$Txn = 'REPORTED_32_HEX_TRANSACTION'
& $Runtime -I -X utf8 -m knowledge.maintain_cli identity-recover --root $Project --transaction $Txn
```

For an incomplete migration this restores the original directories and validates
the old snapshot. The old identity mismatch is then expected again; no empty DB
was initialized. Completed recover validates the completed destination and never
replays its old plans. Normal maintain_cli recover also recognizes an active
identity fence; BUILDING without a fence uses explicit identity-recover above.

Immediately rolling back a completed, unchanged migration is a separate approval:

```powershell
$Raw = & $Runtime -I -X utf8 -m knowledge.maintain_cli identity-rollback-preview --root $Project --transaction $Txn
$Rollback = $Raw | ConvertFrom-Json
if (-not $Rollback.ok) { throw 'Rollback blocked; do not overwrite intervening data' }
$Rollback.fingerprint
# Present the concrete rollback preview; wait for explicit owner approval.
$RollbackApproved = 'EXPLICITLY_APPROVED_ROLLBACK_FINGERPRINT'
& $Runtime -I -X utf8 -m knowledge.maintain_cli identity-rollback --root $Project --transaction $Txn --approve $RollbackApproved
```

Keep all backup/workspace/journal files until the owner's retention decision.
Do not delete active.json, journals or WALs to unstick recovery. On a conflict,
retain both states and report the exact code/path/transaction privately.

## Required local final report / Итог локального агента

Report actual old/new identities and root, exact approved source/fingerprint,
all active and archived table counts/digests (including the incident baseline
1394 records / 697 candidates / 1 plan or an explicitly revised snapshot),
lifecycle/queue/receipt preservation, unresolved evidence and re-enrollment,
backup/original/raw-copy locations, integrity/staged/product validation results,
transaction and rollback command. Distinguish migration success from semantic
reconciliation and later separately approved candidate application. Never state
that Codex migrated the private database remotely.
