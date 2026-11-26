# Knowledge scan lifecycle and configuration drift recovery

## Reproduction and cause

The reproduction ran against main commit `9d670a77128c046bc2221b6634980c1a71d3e54e`. A synthetic Git project had an existing full job and a durable lexical chunk. Changing only the model, only the endpoint, or only the installed release reproduced the status and cancellation failures over MCP. A separate terminal-job check reproduced the reported resume error. To reproduce on the base commit, start a full scan with `max_files=1`, wait for a durable checkpoint, change one provider field, and call status and cancel. For the terminal case, restore the fixture configuration, cancel and wait, change the field again, then call resume. The production IPM installation was outside this test environment. Its exact changed field remains unconfirmed.

| MCP request after drift | Before | After |
| --- | --- | --- |
| `knowledge_scan(action="status", scope="full")` | `scan-provider-configuration-drift`, `details: null` | `ok: true`, `worker_state: "RUNNING"`, drift and checkpoint metadata |
| `knowledge_scan(action="cancel", scope="full")` | `scan-provider-configuration-drift`, `details: null` | `ok: true`, cancellation requested at a durable chunk boundary |
| `knowledge_scan(action="resume", scope="full")`, old worker active | `active-scan-configuration-drift`, `details: null` | `scan-worker-active`, with the job, scan ID and recovery action |
| `knowledge_scan(action="resume", scope="full")`, terminal worker and compatible checkpoint | `resume-scan-configuration-drift`, `details: null` | `COMPLETED` after verification and continuation under the original scan ID |
| Resume with a changed source snapshot or incompatible checkpoint | Opaque binding or worker error | `resume-scan-configuration-drift` with a specific reason, affected fields, checkpoint state and next action |

The machine used one binding for project identity, the provider reference and the installed release SHA-256. Full equality was required for status, cancellation and resume. Lexical Git/filesystem discovery uses its source policy and extractor and makes zero provider calls.

## Compatibility and persistence

- Observation validates project and scope ownership, reports the worker's process state, and reads bounded job/progress/checkpoint metadata. A verified locator checksum does not verify the SQLite checkpoint or the current source. `source_compatibility` stays `unverified` until an explicit execution check. `worker_state` exposes the worker's terminal state alongside the existing semantic status.
- Runtime release and provider drift appear in `nonblocking_fields`. New jobs retain fingerprints of supported provider fields, which lets diagnostics identify `provider.model` or `provider.endpoint` without returning values. Legacy jobs stored only the aggregate reference hash. Their diagnostics report `provider_reference.hash` when the old component values cannot be recovered.
- Cancellation publishes an atomic marker addressed to the selected job. A worker checks it between durable chunks. Repeated requests reuse the marker. A terminal job returns `already terminal`. Legacy processes with missing creation stamps are reported as unverified. A matching job marker can still request cooperative cancellation while liveness is uncertain.
- Resume uses the original scan ID under the project writer lock. The persistent session validates the SQLite schema, durable chunk chain or supported historical artifact, lexical resume contract, extractor, identity policy, discovery policy, Git branch and revision, scope, and source snapshot before extracting. The same session retains the verified checkpoint for continuation. A large verification can outlast the initial response. Poll status for its final result.
- When the previous outcome is unknown and the locator cannot be used, recovery requires historical inspection and an explicitly observed scan ID. A corrupt durable chunk chain blocks resume even with an observed ID. An incompatible checkpoint stays available for inspection. `fresh` starts a separate execution on explicit request.
- Existing v1 job metadata, v1/v2 locators, legacy SQLite scan rows, R1 chunk chains and R2 compact history remain readable. Pre-optimization Git artifacts without recorded branch identity can be inspected. Their cross-runtime resume returns `scan-git-branch-unverified`. No on-disk migration is required.

For example, after a release change and a source edit, the resume error includes the following fields.

```json
{
  "ok": false,
  "error": "resume-scan-configuration-drift",
  "details": {
    "worker_state": "CANCELLED",
    "changed_fields": ["runtime_release", "source_snapshot"],
    "nonblocking_fields": ["runtime_release"],
    "checkpoint_available": true,
    "execution_compatibility": "incompatible",
    "source_compatibility": "incompatible",
    "resume_allowed": false,
    "reason": "stale-scan-restart-required",
    "next_action": "Restore the recorded working tree and index."
  }
}
```

| Modules | Changes |
| --- | --- |
| `project_commands.py`, `machine_mcp.py` | Lexical lifecycle routing, history by scan ID, checkpoint diagnostics and provider drift telemetry |
| `scan_jobs.py`, `auto_init.py` | Job ownership and cancellation, locator validation, worker handoff and structured resume diagnostics |
| `discovery.py`, `discovery_checkpoint.py`, `store.py` | Resume compatibility verification, reuse of the persistent session, and lightweight counts before job creation |
| `tests/test_scan_lifecycle_recovery.py`, `scripts/discovery_benchmark.py` | Lifecycle regressions and active worker status measurements |

Semantic candidate submission and plan approval still validate strict provider bindings. Harness execution and Confluence review retain their own checks.

## Qualification

| Input | Commit |
| --- | --- |
| Discovery Optimization R1 | `2943052a48a919376ff44e8e029470a75277967c` |
| Base main and R2 | `9d670a77128c046bc2221b6634980c1a71d3e54e` |
| Recovery implementation | `a905385c461a01d7bf557eba08638eebc0de6dda` |

The focused and integration suites ran 270 tests on Linux with 257 passing and 13 Windows-specific skips. Coverage included Discovery R1/R2, machine commands, core reliability, checkpoint and persistence recovery, automatic Harness capture, Confluence, and installer validation.

The installed Linux test used actual R1 and R2 wheels followed by a new generation of the recovery build. Its release manifest SHA-256 was `59c55c6cfb73801189a2b65900cf9d1756ad4fb7b1f522d74403cf1a79cff633`. For both routes, the new MCP observed the live old worker, rejected transfer while it was active, cancelled it, and resumed to completion under the original scan ID. It skipped four durably processed files from R1 and six from R2. The installer preserved the modified provider settings. The standard installer trial also passed all 13 checks on the immediately preceding implementation build `799d51939fc4d2825836f0610f1d8faf8b3f9760`.

The Linux MCP round-trip benchmark used 200 steady-state polls after 25 warm-ups. The fixture contained 38,350 source files, 1,000 synthetic claims, 2,000 evidence records, 12,500 pending candidates and seeded history. The worker was held at a durable boundary so the measurement isolates observation. A second benchmark measured status formatting and MCP serialization during extraction with `scripts/discovery_benchmark.py --mode worker --sizes 1000 --samples 2 --populated` on each checkout.

| Linux status latency | Before p50 | Before p95 | After p50 | After p95 |
| --- | ---: | ---: | ---: | ---: |
| MCP stdio round trip, 38,350 files | 6.50 ms | 9.46 ms | 7.88 ms | 12.19 ms |
| Worker extracting, 1,000 files | 8.51 ms | 33.98 ms | 13.46 ms | 63.44 ms |

Normal polling performed no full inventory, checkpoint-chain reconstruction or full store validation. Each new locator adds a job ID, and each new SQLite run header adds a resume contract marker. The extracting-worker benchmark reported zero per-chunk Python subprocesses. Compatible continuation skipped already completed extraction, preserved the original ID and retained canonical records and prior queue entries.

Under concurrent qualification load, the recovery stdio probe measured 55.41 ms p95. Native Windows and production IPM remain unverified. On large projects the explicit source/checkpoint verification can take longer than one MCP call. Older Git artifacts without branch evidence require separate recovery using their earlier runtime or an explicit fresh scan.

### Native Windows qualification

Run from the recovery checkout in Windows PowerShell 5.1 with Python 3.12 and Git. Output from the installer trial stays in a temporary directory.

```powershell
py -3.12 scripts/setup_p3.py
$Runtime = (Resolve-Path '.venv\Scripts\python.exe').Path
$env:PYTHONPATH = 'tests'
& $Runtime -B -m unittest test_scan_lifecycle_recovery test_discovery_optimization test_discovery_r2 test_machine_commands test_core_reliability test_core_bootstrap test_plan_recovery_diagnostics test_persistence_recovery test_integrated_capture test_integrated_knowledge test_confluence_source test_confluence_sync test_confluence_command test_confluence_r2 test_confluence_r2_compat test_confluence_resume test_confluence_progress test_confluence_static test_p3_installer test_p3_platform
if ($LASTEXITCODE) { throw 'Regression suite failed' }
$Output = Join-Path $env:TEMP ('knowledge-recovery-' + [guid]::NewGuid())
$Commit = (git rev-parse HEAD).Trim()
& $Runtime -B scripts/build_p4.py --source-id $Commit --output (Join-Path $Output 'build')
if ($LASTEXITCODE) { throw 'Build failed' }
$Kit = Join-Path $Output 'build\knowledge-harness-0.5.0rc1'
& $Runtime -B scripts/machine_installer_trial.py $Kit (Join-Path $Output 'installer')
if ($LASTEXITCODE) { throw 'Installer trial failed' }
```

## Восстановление сканирования IPM

1. Укажите реальные пути к IPM, каталогу установки и проверенному исходному коду или комплекту обновления. Сохраните каталог `.knowledge` проекта и `state\projects` установки. Для согласованной резервной копии воспользуйтесь штатным механизмом `knowledge.maintain_cli backup-preview/apply` или сделайте копию после завершения рабочего процесса. Инструкции по резервной копии приведены в [проверке интеграции IPM](Knowledge-IPM-Integration-Validation.md).
2. Обновите существующую установку штатным установщиком. Если файл отсутствует или не проходит проверку установщика, поместите действительную конфигурацию в `config/provider.json`. Установщик принимает новую корректную конфигурацию. После обновления перезапустите OpenCode, чтобы MCP подключился к новой версии.

```powershell
$McpDir = 'C:\LLM\mcp\knowledge'
$Project = 'C:\замените\корень-IPM'
$Delivery = 'C:\замените\комплект-обновления'
& (Join-Path $Delivery 'install.ps1') -McpDir $McpDir
if ($LASTEXITCODE) { throw 'Ошибка установки Knowledge' }
$Bootstrap = Join-Path $McpDir 'bootstrap\Scripts\python.exe'
$Launch = Join-Path $McpDir 'launch.py'
$ScanId = '093a543caa8232f2693d7fac5743804854479256bb8b729e4d061bd8794a6a06'
```

3. В MCP, открытом в корне IPM, проверьте состояние и контрольную точку.

```text
knowledge_scan(action="status", scope="full")
knowledge_scan_diagnostics(scope="full", section="checkpoint")
knowledge_scan_diagnostics(scope="full", section="scans", scan_id="093a543caa8232f2693d7fac5743804854479256bb8b729e4d061bd8794a6a06")
```

4. Если `worker_state` показывает `RUNNING` или `STARTING`, дождитесь завершения или запросите отмену. Повторяйте `status` до терминального состояния. Если вывод показывает `OUTCOME_UNKNOWN`, сначала найдите сохранённый идентификатор в разделе `scans` и проверьте состояние контрольной точки.

```text
knowledge_scan(action="cancel", scope="full")
knowledge_scan(action="status", scope="full")
```

5. Продолжите совместимое сканирование. При отсутствующем или повреждённом файле-указателе передайте `observed_scan_id` только после того, как нашли этот ID в истории IPM. При отказе смотрите `details.reason` и `details.next_action`. Например, для изменения ветки или исходников восстановите исходную рабочую копию и повторите `resume`.

```text
knowledge_scan(action="resume", scope="full")
knowledge_scan(action="resume", scope="full", observed_scan_id="093a543caa8232f2693d7fac5743804854479256bb8b729e4d061bd8794a6a06")
```

Те же действия можно выполнить без OpenCode. Выберите одну из двух команд продолжения по состоянию указателя.

```powershell
'{"action":"status"}' | & $Bootstrap -I -B $Launch command --root $Project knowledge-init
'{"action":"cancel"}' | & $Bootstrap -I -B $Launch command --root $Project knowledge-init
$Current = Get-Content -Raw -Encoding UTF8 (Join-Path $McpDir 'current.json') | ConvertFrom-Json
$Runtime = Join-Path (Join-Path $McpDir $Current.runtime) 'Scripts\python.exe'
& $Runtime -I -B -m knowledge.cli scan-status --root $Project --scan-id $ScanId
'{"resume":true}' | & $Bootstrap -I -B $Launch command --root $Project knowledge-init
(@{resume=$true; observed_scan_id=$ScanId} | ConvertTo-Json -Compress) | & $Bootstrap -I -B $Launch command --root $Project knowledge-init
```

Для инкрементального задания используйте `scope="incremental"` в MCP или `knowledge-candidates-update` в командной строке. Без диапазона выбирается последнее инкрементальное задание. Для другого диапазона передайте сохранённые `base` и `head`.
