# Knowledge IPM integration validation — local Windows agent

Run these steps locally only after the owner authorizes deployment. Codex did not
modify the owner's Windows installation, provider, OpenCode configuration or IPM.
Synthetic/CI results are not production acceptance. Report each local verdict.
Use Windows PowerShell 5.1, Python 3.12 and OpenCode 2.4.0. Substitute the actual
IPM root and downloaded source/kit path; never invent an IPM path in core code.

## 1. Record and back up the current installation

Close OpenCode and observe/cancel any active scan through its supported status
and cancel API before taking a quiescent copy. Preserve logs for unknown outcomes.
Choose a new absent backup directory outside IPM and McpDir:

```powershell
$McpDir = 'C:\LLM\mcp\knowledge'
$Project = 'C:\REPLACE\actual-IPM-root'
$Delivery = 'C:\REPLACE\Knowledge-core-delivery'
$Backup = 'C:\REPLACE\new-absent-backup-directory'
New-Item -ItemType Directory -Path $Backup -ErrorAction Stop | Out-Null
$Current = Get-Content -Raw -Encoding UTF8 (Join-Path $McpDir 'current.json') | ConvertFrom-Json
$Runtime = Join-Path (Join-Path $McpDir $Current.runtime) 'Scripts\python.exe'
$HostConfig = if ($env:XDG_CONFIG_HOME) { Join-Path $env:XDG_CONFIG_HOME 'opencode' } else { Join-Path $HOME '.config\opencode' }
Copy-Item -Recurse -LiteralPath $McpDir -Destination (Join-Path $Backup 'machine')
if (Test-Path -LiteralPath $HostConfig) { Copy-Item -Recurse -LiteralPath $HostConfig -Destination (Join-Path $Backup 'opencode') }
```

This private copy can contain provider configuration: protect it, never attach
it publicly. Record current source identity/release, OpenCode/Python version,
canonical revisions, candidate IDs and decisions. Obtain project state using
supported CLI, not SQLite queries:

```powershell
& $Runtime -I -m knowledge.cli status --root $Project
& $Runtime -I -m knowledge.cli export --root $Project
$Raw = & $Runtime -I -m knowledge.maintain_cli backup-preview --root $Project --destination (Join-Path $Backup 'project.zip')
$Preview = $Raw | ConvertFrom-Json
if (-not $Preview.ok) { throw $Raw }
$Input = Join-Path $Backup 'backup-preview.json'
[IO.File]::WriteAllText($Input, ($Preview.preview | ConvertTo-Json -Depth 100), (New-Object Text.UTF8Encoding($false)))
```

Review the preview and archive destination, then explicitly authorize that exact
maintenance fingerprint before running:

```powershell
& $Runtime -I -m knowledge.maintain_cli apply --root $Project --input $Input --approve $Preview.fingerprint
if ($LASTEXITCODE) { throw 'Backup failed; stop deployment' }
```

Do not apply any candidate plan as part of backup. These status/export outputs
can contain project knowledge: keep privately or redact before sharing.

## 2. Update through the supported installer

Fetch branch `codex/core-reliability-fix` and verify the commit/release hashes
against `reports/CoreReliability`. From the new source or its verified ready kit:

```powershell
& (Join-Path $Delivery 'install.ps1') -McpDir $McpDir
if ($LASTEXITCODE) { throw 'Installation failed; keep logs and repeat only after diagnosis' }
$Current = Get-Content -Raw -Encoding UTF8 (Join-Path $McpDir 'current.json') | ConvertFrom-Json
$Runtime = Join-Path (Join-Path $McpDir $Current.runtime) 'Scripts\python.exe'
$BootstrapPython = Join-Path $McpDir 'bootstrap\Scripts\python.exe'
& $BootstrapPython -I -B (Join-Path $McpDir 'launch.py') mcp --self-test
```

Expect INSTALLED/UPDATED/verified UNCHANGED and a full log path. No TEMP/TMP edits,
deletion of McpDir or site-packages patches are required. If it fails, retain the
rejected path/reason and full log. Compare preserved provider/config/shared data
and project canonical revisions/candidate IDs with the before snapshot.

Inspect generated `launch.py`: Windows dispatch must load `windows-process.py`
and wait for its result; POSIX retains execv. Verify helper file presence and
release/installed hashes. Do not hand-edit the launcher. The self-test must print
the 12-tool catalog and exit; repeat it three times and check for owned orphan
processes using PID/creation identity, never kill all Python processes.

## 3. OpenCode and Code Mode preflight

Restart OpenCode 2.4.0 in the actual IPM workspace. Confirm the native global
commands `/knowledge-init`, `/knowledge-candidates-update`,
`/knowledge-candidates-push`, and connected `knowledge_machine` MCP. Remove no
unrelated commands or MCPs. Resolve duplicate project/global names explicitly.

Ask the agent to use actual Code Mode `execute` and
`search({namespace:"knowledge_machine",limit:30})`. Save returned paths/signatures
and invoke the discovered `knowledge_capabilities` path. Expect contract
knowledge-machine-v2 and 12 advertised tools listed in CORE-RELIABILITY.md.
Compare search visibility with host permissions: a denied tool may be absent
from search even though registered. Report host permission, connection, old
backend or sandbox API failures separately. No fs/child_process/fetch/shell/SQL
fallback inside Code Mode. Trusted native plugin execution is a separate host
mechanism and must also respect its permission decisions.

## 4. Validate the owner's corrected production provider

Privately inspect `<McpDir>\config\provider.json` (schema documented in
AutomaticInstallation-RU.md). Verify endpoint/model correspond to the owner's
real service and `evidence` is explicitly `live`. Keep secrets in `key_env` and
the host process environment. Do not overwrite owner settings with demo defaults.
Call `knowledge_semantic_preflight` without test opt-in. Check endpoint/model/mode
match; this performs no inference and does not establish network availability.
Use the host's normal authorized model operation to verify actual connectivity
and identify which model performed semantic review. Do not infer model success
from lexical scanning. Previous demo configuration was acknowledged user error;
do not manufacture a corruption investigation or promote its output.

## 5. Fresh scan, precise gaps and project policy

First inspect existing status/reconciliation and preserve its diagnostics. Use
`knowledge_scan(action="fresh",scope="full",max_files=100)` through the actual
discovered path (or `/knowledge-init {"fresh":true,"max_files":100}`). A fresh
scan gets a new ID. It does not delete canonical knowledge or pending candidates.
If an old job is active, explicitly cancel, observe terminal state, then fresh.

Observe `knowledge_scan(action="status",scope="full")` at most four times per
agent turn. Record scan/job/source IDs, revision, counters, remaining files,
phase, elapsed time and diagnostics location. A detached worker progresses
through chunks without a new agent call for each chunk. Use
`knowledge_scan_diagnostics(section="failures",cursor=0,limit=20)` and follow
next_cursor; also inspect coverage, policy, identity, impact and reconciliation.
Collect exact paths/stages/reason codes/encoding/bytes/limit/retry fields for the
previously blocked files. Do not change encodings or delete application files to
force coverage success. Keep contents/secrets out of diagnostic summaries.

An optional `.knowledge/discovery.json` example to review for this project:

```json
{
  "version": 1,
  "exclude": [{"glob": "reports/generated/**", "reason": "Reproducible reports; owner confirmed not authoritative application input"}],
  "include": ["reports/generated/Contract.json"],
  "legacy_encodings": {"docs/legacy/*.md": "windows-1251"},
  "format_limits": {".json": 1048576}
}
```

Apply only rules supported by inspection/owner intent, not a blanket exclusion
of XML/JSON/YAML/deployment/docs. Policy changes require a new compatible scan.
See CORE-RELIABILITY.md for defaults/caps, UTF-16/XML declaration handling,
preview gaps and YAML content-inventory limitation.

## 6. Checkpoint, cancellation and resume

Observe a committed chunk/scan ID. Use `knowledge_scan(action="cancel")`, wait for
CANCELLED or already-terminal result, then `knowledge_scan(action="resume")`.
Expect the same compatible scan ID and no repeated committed paths/candidates.
Source/policy/provider/release/base/head changes must refuse incompatible resume;
use explicit fresh after review. Restart the host while a worker runs and verify
status finds that same worker. A duplicate start must observe rather than fork.
Never kill a production worker merely to test recovery.

Checkpoint and compact progress live under the status diagnostics directory;
retain their hashes privately. A corrupt checkpoint must not be trusted. If a
chunk committed before checkpoint storage failed, observe
`knowledge_scan_diagnostics(section="scans")`, verify the root/source/scope and
exact durable scan ID, then explicitly call
`knowledge_scan(action="resume",observed_scan_id="<verified 64-hex ID>")`.
No direct database/checkpoint repair is required or supported. Unknown outcomes
must be observed before retrying a mutation.

## 7. Semantic reconciliation and candidate safety

Distinguish physical completion from semantic PARTIAL. For every relevant claim,
inspect paged reconciliation/impact, current bounded `knowledge_source_read`,
canonical history, consumers and critical nonchanges. Record checked obligations
and remaining gaps. Do not treat absent/unreadable/excluded/preview-only source
as retirement proof. Invalid/partial files must never produce whole-file proof.

Submit reviewed source-bound v2 proposals through knowledge_submit_candidates
(contract/examples in UPDATE-BY-CR.md and existing lifecycle APIs). Preserve
stable IDs, expected revisions, evidence anchors, graph relationships and
dispositions. Test-double semantic submissions need explicit opt-in and cannot
create CONFIRMED claims. Provider/source drift must invalidate preparation/apply,
not reuse old semantic authority. Confirm no automatic canonical application.
Prepare with knowledge_plan(action="prepare") or /knowledge-candidates-push;
review the exact plan and obtain a separate explicit owner approval before any
knowledge_plan(action="apply",approve="<exact fingerprint>"). If not authorized,
leave it prepared. Record acknowledgements and compare canonical/pending state
with the backup; unrelated decisions must remain unchanged.

## 8. Real performance and acceptance report

Measure host/MCP startup, fresh and resume wall time, per-chunk progression,
eligible/processed/partial/failed/excluded counts, peak worker memory, number of
MCP calls, checkpoint timing where observable, DB prepare time and provider/model
latency separately. Save machine/Python/OpenCode versions and source/policy
identities. Use the same immutable production snapshot for before/after where
possible; do not compare an early failed run with a complete run as equal work.
Synthetic improvements alone establish no IPM performance claim.

Acceptance: launcher handshakes/shuts down repeatedly; actual Code Mode searches
and calls supported tools; no unauthorized fallback; independent files after an
early extraction failure are processed; counters balance and remaining reaches
zero; gaps stay explicit; resume preserves ID/work and fresh creates a new ID;
no duplicates or orphan MCP; canonical/pending/history remain intact; semantic
review uses the real provider and separately approved current plans only.
Report Core, regression, Windows, OpenCode, upgrade and production verdicts
separately. Production stays UNVERIFIED until these local checks complete.

For a new core defect send Codex the delivery commit/source identity, OS/host
versions, sanitized minimal fixture, exact command/tool arguments, state/IDs,
diagnostic reason/stage/counters and full redacted log. Distinguish host denial,
provider/network failure and product error. Do not include keys or private source.

## 9. Rollback if needed

Stop new host/writers through supported cancel/status. Preserve new logs and a
new backup. With everything quiescent, move the new machine directory to a new
absent recovery location and restore the complete private `machine` snapshot to
the original McpDir; restore the host config snapshot after preserving any later
owner edits. Keep paths/base Python unchanged. This restores the old owned
launcher/config/runtime as a unit without manual pointer or SQLite edits.
Reopen the old host only after checking its actual bootstrap/provider.

If project restoration is actually required, use the new runtime's supported
maintenance API at the same root/OS, not archive extraction over live SQLite:

```powershell
$Raw = & $Runtime -I -m knowledge.maintain_cli restore-preview --root $Project --archive (Join-Path $Backup 'project.zip') --recovery (Join-Path $Backup 'new-absent-project-recovery')
$Restore = $Raw | ConvertFrom-Json
if (-not $Restore.ok) { throw $Raw }
$Input = Join-Path $Backup 'restore-preview.json'
[IO.File]::WriteAllText($Input, ($Restore.preview | ConvertTo-Json -Depth 100), (New-Object Text.UTF8Encoding($false)))
```

Review destructive restoration and get explicit authorization, then run the
same maintain_cli apply with `$Restore.fingerprint`. Preserve the new runtime
at its original location until restoration is finished (before moving machine
directories). Do not run the old and new code concurrently. Restored old scans
are not automatically compatible with new reader metadata; choose fresh only
after observing the restored state.
