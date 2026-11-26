# Git knowledge discovery performance and recovery

This change starts from `60d7a97fcd2126605d0720dc3bf191fa63d7b1ad` and is
available on `codex/knowledge-discovery-optimization`. It applies to deterministic
Git and filesystem discovery, incremental candidate updates, and the Knowledge
producer used by Harness. Confluence keeps its own acquisition, semantic review,
and approval flow.

## Execution and storage

| Path | Audited implementation | Optimized implementation |
| --- | --- | --- |
| Managed scan worker | One Python CLI process per chunk, with initialization, inventories, and reconciliation repeated on each invocation | One worker owns the scan, keeps a validated snapshot and extraction state in memory, and checkpoints at each durable boundary |
| Source verification | The entire repository was read before extraction and again inside the chunk transaction | The worker inventories at entry or resume and before terminal publication. Each extracted file's original bytes are checked against its expected digest, including the suffix of a bounded structured preview |
| Provisional scan | Replaced a growing JSON artifact after each chunk | One compressed initial record and an ordered chain of compressed, checksummed chunk deltas. Coverage counters advance with each delta |
| Final publication | Performed extraction, evidence analysis and work on the candidate queue while holding the write reservation | Validates the graph and queue in one SQLite read snapshot, stages changes, verifies source, and promotes to a short atomic write. The durable terminal artifact uses the existing format |
| Incremental scope | Looked for unchanged paths in historical scan payloads and repeatedly walked their observations | Uses an exact per-file observation cache and groups current and cached observations by identity, including equivalent occurrences and ambiguous declarations |
| Harness capture | Analyzed all included source, then selected observations for changed paths | Checks the supplied changed paths against the same cache and verifies source before recording capture receipts. Harness continues to persist and replay its outbox |
| Evidence and progress | Recomputed impact and dependency closure on each CLI chunk | Computes final impact and reconciliation against the verified graph using indexed identities and reverse dependencies. Managed progress comes from compact files and paginated diagnostics remain available |

The inventory preserves exact raw hashes, Git revision and relevant index entries,
dirty and untracked source, project partitions, discovery policy, and path safety.
A persistent execution also records the symbolic branch. It will refuse an
incompatible branch at resume or final publication even if both branches point
to the same commit. A fresh worker verifies the whole snapshot before replaying
an interrupted inventory. Public one-shot CLI invocations independently verify
source when there is no shared worker.

`source_verified` distinguishes a published snapshot from provisional worker
progress. A verified snapshot can still have extraction or identity coverage
gaps. Approval and application retain authoritative source and plan validation.
Candidate review still requires human approval. A lexical absence or a coverage
gap cannot authorize retirement on its own. Evidence from a current registered
Confluence snapshot remains independent of Git changes.

## Existing stores

The format of canonical records, evidence, revisions, approvals, queue payloads,
and terminal scan history is retained. Two provisional tables are created
lazily. Their initial record and ordered chunk hash chain are verified on
recovery. Terminal publication deletes the provisional rows in the same
transaction that records the terminal artifact and eligible candidates. A
corrupt or superseded checkpoint is rejected before extracting more source.

The derived file cache keeps one entry per path. It binds project identity, path,
exact bytes, extractor and identity versions, discovery configuration, nearest
project partition and its project file, and shared build configuration files.
Renames create a new path binding. Deletions are removed from the current scope
and obsolete cache entries can be discarded on verified publication. File cache
rows never serve as canonical evidence on their own. Older complete artifacts can
supply compatible observations lazily when they retained every occurrence. If an
older artifact discarded ambiguous members or source configuration changed, the
consumer reports missing coverage. An explicitly requested full scan or reviewed
candidate submission is the existing recovery path. Software installation alone
does not start a scan.

A final run uses the original ownership and maintenance boundaries. Only the
provisional checkpoint path skips the whole-store integrity check. It checks
format, project binding, extension state, and the maintenance fence, and uses a
SQLite authorizer restricted to the checkpoint tables and historical scan reads.
Scan startup and final publication, public reconciliation, preparation, approval,
migration and recovery retain their authority checks. A known SQLite busy rollback
can retry the staged checkpoint without re-extracting source. The existing SQLite
timeout and journal mode are retained.

## Benchmark method

Run the profiler against Python 3.12 with Git on the path. It generates its own
C# checkout and uses different file sizes, project directories and partitions,
package references, and repeated and ambiguous observations. The populated
scenario seeds 1,001 claims, 2,001 pieces of evidence, approximately 12,500 pending
batches, a historical scan, dependency relationships, and a registered
Confluence document with independent canonical evidence. The stress fixture
raises the graph to 10,001 claims and 20,001 evidence records.

```bash
python scripts/setup_p3.py
.venv/bin/python -B scripts/discovery_benchmark.py --populated --samples 2 --output /tmp/discovery.json
.venv/bin/python -B scripts/discovery_benchmark.py --mode worker --sizes 1000 --samples 3 --output /tmp/discovery-worker.json
.venv/bin/python -B scripts/discovery_benchmark.py --stress --full-only --sizes 1000 --samples 2 --output /tmp/discovery-stress.json
```

For the audited comparison, use the same script and put the audited checkout's
`packages/knowledge/src` and `packages/harness/src` first on `PYTHONPATH`.
Pass `--implementation-commit 60d7a97fcd2126605d0720dc3bf191fa63d7b1ad`.
For worker measurements, add `--worker-python` pointing to a Python environment
with the audited package installed. This also binds its isolated per-chunk CLI
children to the audited code. `--baseline-probe 2` limits measurement to two
chunks on repositories whose original full scan is impractical. Cold refers
to the initial discovery on a new test checkout and store with no matching file
cache. Warm refers to the same store after a completed scan. Both modes use the OS page cache normally.

Phase timers overlap. The extraction and hashing counters record calls to the
actual production functions. SQL totals are traced statements and SQLite write
time begins at `BEGIN IMMEDIATE` or the first write statement in a deferred
transaction. SQL text bytes are a write-volume proxy, including SQLite trace
rendering of BLOBs. They are distinct from physical filesystem writes. Peak RSS
is a process high-water mark and excludes children. The worker benchmark measures
the production job-status formatter while the scan runs. Its MCP latency
captures local status and serialization, with stdio and network time excluded.

`KNOWLEDGE-DISCOVERY-OPTIMIZATION.json` contains compact measurements. The
[qualification workflow](https://github.com/Ermak-P/Knowledge-/actions/workflows/discovery-optimization.yml)
retains full run data and logs as Actions artifacts.

## Measured results

The Linux executor had a two-CPU quota. Other qualification tasks shared it
during parts of profiling, so elapsed ratios are less controlled than operation
counts. The table compares the same 10,000-file populated fixture through two
100-file chunks. Two runs were recorded for each implementation.

| Metric | Audited | Optimized |
| --- | ---: | ---: |
| Full inventories | 4 | 1 |
| File fingerprints | 40,000 | 10,000 |
| Files extracted | 200 | 200 |
| Git subprocesses | 24 | 6 |
| SQLite connections and transactions | 4 | 3 |
| Write transactions | 2 | 2 |
| Whole-store integrity and control checks | 4 | 1 |
| Write p50 across runs | 15.40–21.61 s | 40–42 ms |
| Write p95 across runs | 17.70–22.53 s | 75–78 ms |
| SQL write trace bytes | 18.79 MB | 2.00 MB |
| SQLite file after two chunks | 26.53 MB | 19.12 MB |
| Peak process RSS across runs | 273–283 MB | 142–144 MB |
| Median elapsed time | 52.74 s | 6.91 s |

The 1,000-file worker test measured a median of 27.15 s audited and 3.49 s
optimized over three runs. The helper launched 10 Python chunk children per
audited run and zero per optimized run. Both used the same extraction budget.
The optimized 38,350-file worker also used zero Python chunk children, two
inventories and 12 Git subprocesses. It served status with a 10.6 ms p95 over 1,215 samples and
a maximum 1,723-byte formatted MCP response. The machine launcher is a
separate, fixed process boundary.

Both audited 38,350-file probes stopped at the 15-second subprocess timeout in
`git check-ignore`, during the first inventory and before extracting a file.
That invocation received every tracked file. Git ignores tracked paths for this
operation, so the optimized invocation receives only unindexed paths. No
end-to-end speedup multiple is established for the 38,350-file full,
incremental, or Harness scenarios.

The optimized populated fixtures produced the following samples. Recovery
starts after a durable 100-file chunk. It resumes the same scan and extracts
the remaining 38,250 paths. The outbox benchmark runs real Harness delivery
and then replays it, with five candidates delivered in both samples.

| Scenario | Eligible files | Source extractions | Full inventories | Elapsed samples |
| --- | ---: | ---: | ---: | --- |
| Cold full, small | 1,000 | 1,000 | 2 | 8.28, 8.29 s |
| Cold full, medium | 10,000 | 10,000 | 2 | 28.40, 36.11 s |
| Cold full, IPM-like | 38,350 | 38,350 | 2 | 61.30, 36.59 s |
| Warm, zero changes | 38,350 | 0 | 2 | 33.18, 14.68 s |
| Warm, four changes | 38,350 | 4 | 2 | 28.10, 15.83 s |
| Warm, 100 changes | 38,350 | 100 | 2 | 24.85, 17.17 s |
| Harness four-file capture, delivery and replay | 38,350 | 4 | 2 | 51.53, 29.62 s |
| Recovery after a 100-file checkpoint | 38,350 | 38,250 | 2 | 48.54, 36.42 s |
| Larger canonical graph | 1,000 | 1,000 | 2 | 27.01, 19.09 s |

The largest full run executed 44,664 traced SQL statements and 384 write
transactions, one for each 100-file chunk or terminal remainder. Initial and
terminal database validation produced two `quick_check` calls. The first
sample recorded a 4.2 ms write p50 and 29.3 ms write p95. The full run's trace
included 85.8 MB of write SQL, including expanded compressed BLOBs and the
terminal artifact. The medium two-chunk comparison above isolates provisional
checkpoint cost without the terminal artifact.
## Regression results and commit references

| Coverage | Revision | Result |
| --- | --- | --- |
| Audited baseline | `60d7a97fcd2126605d0720dc3bf191fa63d7b1ad` | Source and benchmark comparison |
| Populated repository and outbox measurements | `2b978c60e928377f5424d204f81bfdc60718288f` | Linux, repeat samples in the JSON companion |
| Linux packaged installer and real host commands | `c8b7ebd325f8e8826e5f3dbc32bf357d58eff959` | Source-locked `PASS_PORTABLE`. 225 installed tests passed and two platform cases skipped |
| Final helper and recovery regressions | `84bc2975e3fb5fe2cf8b15ecd0fbd38d717086dd` | 51 Linux tests passed |
| Native Windows worker and filesystem qualification | Review branch | Windows job configured. A completed result was unavailable from this executor |

The comprehensive installed-wheel suite at
`d83588f9d72887228cb62d8ed6e1db9744c42456` ran 637 tests with zero failures
and 13 skips. The final 51-test helper run covers the subsequent default-mode
and diagnostic-file changes. The source-locked Linux installation and native
OpenCode receipt is `944c70b756c74fbebcc83183e79f0d5e`.

Regression coverage includes checkpoint checksums and interruption before and
after a commit, same-size source drift, branch changes at the same Git revision,
unmerged index entries, retries after SQLite contention, legacy backfill,
cross-file ambiguity, equivalent observations, outbox replay, existing approval
fingerprints, Confluence independence, and installed `/update-by-CR` replay.

The review branch is available [on GitHub](https://github.com/Ermak-P/Knowledge-/tree/codex/knowledge-discovery-optimization).

## Remaining costs and limits

Exact inventories still dominate the warm update path. At IPM scale each full
pair fingerprinted roughly 75 MB of source. Authoritative control checks also
remain visible with 12,500 pending batches. The first outbox benchmark measured
21.3 s in six control validations across capture and five candidate submissions.
The outbox uses the existing per-item submission boundary so each item can
record and retry its delivery independently.

The format-compatible terminal artifact remains the largest persistent write.
A first full run occupied roughly 81 MB including the seeded store. A new
no-change incremental artifact occupied another 19.4 MB even with zero source
extractions. This is a tradeoff of retaining self-contained terminal history
and historical approval tooling. The derivative cache keeps one row per path.
Further compaction would need a compatible terminal-history migration. Peak
process RSS of the 38,350-file worker was about 529 MB with instrumentation.
The audited 38,350-file timeout prevents a peak-memory comparison at successful
completion. Source inventories and per-file working state account for storage
and memory proportional to the repository; subsequent chunks append only
their own data.

An extraction-only probe on 4,000 files took medians of 5.16 s sequential,
4.97 s with two threads, and 4.60 s with two spawned workers. All produced the
same observation digest. This was a two-sample Linux microbenchmark under
shared load. The observed reduction and the cost of another process pool led
to keeping sequential extraction in production.

## Обновление действующей установки и проверка IPM

1. Уточните путь к IPM, текущую ветку и активное поколение Knowledge. Дождитесь
   завершения scan/Harness job или отмените его через поддерживаемую команду и
   дождитесь терминального статуса. Закройте OpenCode перед резервным
   копированием и переключением runtime.
2. В отдельном приватном каталоге сохраните копию каталога установки, текущий
   `current.json` и конфигурацию OpenCode. Для IPM используйте
   `knowledge.maintain_cli backup-preview` и одобрите только fingerprint плана
   резервного копирования. Точные команды приведены в разделе 1
   [инструкции IPM](Knowledge-IPM-Integration-Validation.md). Сохраните
   результаты `knowledge.cli validate`, `status` и `export` для сравнения.
   Выгрузки могут содержать внутренние данные IPM.
3. Возьмите проверенную ревизию этой ветки. Запустите штатный установщик в тот
   же каталог. Откройте OpenCode заново и проверьте MCP. Каталог проекта и
   `.knowledge` сохраняются.

   ```powershell
   $McpDir = 'C:\LLM\mcp\knowledge'
   $Project = 'C:\REPLACE\actual-IPM-root'
   $Delivery = 'C:\REPLACE\verified-knowledge-source'
   & (Join-Path $Delivery 'install.ps1') -McpDir $McpDir
   if ($LASTEXITCODE) { throw 'Ошибка обновления Knowledge' }

   $Current = Get-Content -Raw -Encoding UTF8 (Join-Path $McpDir 'current.json') | ConvertFrom-Json
   $Runtime = Join-Path (Join-Path $McpDir $Current.runtime) 'Scripts\python.exe'
   & $Runtime -I -m knowledge.cli validate --root $Project
   & $Runtime -I -m knowledge.cli status --root $Project
   ```

4. Сравните canonical claims, evidence, ревизии, идентификаторы и решения очереди
   с сохранённой выгрузкой. Проверьте существующие Confluence-записи и прежние
   подготовленные планы в рамках их исходных условий. Подтверждать планы для
   проверки обновления не требуется.
5. В OpenCode сначала вызовите статус `/knowledge-init {"action":"status"}`.
   Совместимый прерванный scan продолжайте с `{"resume":true}`. Если лог
   прервался после коммита, используйте пагинированный раздел диагностики
   `scans`, затем явно передайте `observed_scan_id` вместе с `resume`.
   Несовместимый snapshot требует нового явного запуска с `{"fresh":true}`.
6. На изолированном рабочем дереве с настроенным Knowledge проверьте чистый
   `/knowledge-candidates-update {"base":"HEAD","head":"HEAD"}`, затем сценарий
   с четырьмя изменёнными C# файлами. Запишите число извлечённых файлов,
   `identity_verification`, elapsed time и периодические статусы. Если старая
   история не покрывает неизменённые файлы, зафиксируйте показанные пробелы и
   запустите явный `/knowledge-init {"fresh":true,"max_files":100}` только после
   решения о перестроении производного кэша. Существующие claims и очередь при этом
   сохраняются.
7. Для контрольного Harness запуска проверьте точный набор изменённых путей и
   повтор доставки. При `capture-observation-cache-incomplete` следуйте
   диагностике и повторите capture после восстановления покрытия либо проведите
   ручную проверку. Сравните количество уникальных кандидатов и убедитесь, что
   Confluence и `/update-by-CR` работают в прежнем режиме. Перед любым
   canonical apply используйте штатное отдельное одобрение.

Откат поколения выполняйте по [процедуре IPM](Knowledge-IPM-Integration-Validation.md)
после завершения новых scan job. Перед откатом сохраните актуальную копию базы,
чтобы иметь возможность восстановить более свежие записи и решения.
