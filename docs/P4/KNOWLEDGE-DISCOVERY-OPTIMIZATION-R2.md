# Knowledge Discovery Optimization R2

The review branch is `codex/knowledge-discovery-optimization`. The reviewed
implementation was `2943052a48a919376ff44e8e029470a75277967c`. R2 behavior was
implemented in `19d6e2f7dcdb21f82c9194b6e4bb8f066195c17a` and hardened in
`6a24ea4928a95c94fa147badb9bb685e2da89d58`. The final product revision is
`259850439a4751590a91731e1ae4ebee05dfd513`, which compacts shared full coverage fields.

| Finding | Status | Root cause | Fix | Regression tests | Remaining risks |
| --- | --- | --- | --- | --- | --- |
| KD-01 | FIXED | Capture wrote receipts while retaining old file hash bindings | Publish verified changed-file and dependency observations with receipts in one SQLite transaction | Ten deliveries against full-analysis proposals, repeat/empty results, rename/deletion, config drift, corrupt/missing cache, read-only preview, concurrency and process death on both sides of commit | Configuration changes can explicitly invalidate compatible cache coverage |
| KD-02 | FIXED | Each terminal execution stored a complete, repeated inventory | Versioned compressed terminal manifests share immutable inventory blocks across runs | Exact artifact reconstruction, block sharing, corruption, summary pagination, checkpoint recovery, and both historical store formats | First use on a legacy database creates shared blocks once. Full reconstruction adds about 0.10 s of CPU in the read probe |
| KD-03 | FIXED | Each outbox item opened a separate authoritative Knowledge transaction | Admit up to 100 compatible candidates in one transaction and retain individual acknowledgments | Single/batch identity parity, invalid input, duplicate and historical candidates, source drift, contention, crash before commit and restart before outbox acknowledgment | A new batch verifies its exact Git source once. Candidate preparation and approval still perform their own validation |
| KD-04 | BLOCKED BY ENVIRONMENT | The P4 setup job failed and the Discovery jobs reported no steps. The cause remains undetermined | Removed the pre-checkout status API dependency and added installed machine/OpenCode verification to the discovery job | Exact Linux installed tests and the CI metadata inspection below | Native Windows requires an actual successful runner execution. R2 remains short of a release GO |

## Storage and compatibility

A compact terminal artifact keeps the original scan ID, snapshot identity,
coverage, observations, candidates, and reconciliation metadata. A stable
path hash groups file and index metadata into 1,024 buckets. Blocks are
content-addressed, and unchanged blocks are shared even when a scan has a
new ID or Git revision. Exclusions also use an immutable shared block. Full coverage records store
only fields added or changed by processing when the remaining fields can
be reconstructed exactly.
The terminal manifest and any new blocks commit together with queue, cache,
and checkpoint updates. A checksum or missing block fails artifact reconstruction.
Paginated scan listings use checksummed summaries. Full artifact readers
reconstruct the original shape and retain the existing verification boundaries.

The writer creates the versioned format lazily in its first publication
transaction. Existing JSON artifacts remain readable in the same table.
Legacy records, plans, approval fingerprints, candidate dispositions,
and Confluence data keep their existing formats. Identity migration recognizes
both provisional and terminal discovery tables and archives the original data
under the existing project-move rules. Standard backup copies all SQLite
tables. Historical blocks are authoritative inputs to terminal reconstruction
and are retained. The observation cache is derived and keeps its existing
pruning rules. A restore to the R1 runtime requires an R1-compatible backup
because R1 cannot read the R2 terminal envelope.

Coverage gaps remain explicit. A successful read-only preview has no persistent
side effects. A failed capture check leaves both cache rows and receipts
unchanged. A subsequent verified extraction can repair its own corrupt cache
row. Corrupt rows used as unchanged evidence still fail closed.

A delivery batch requires Git candidates with the same source identity.
Malformed payloads or source drift leave the entire batch pending. Valid
candidate IDs, duplicate disposition, and source-refresh rules follow
single-candidate admission. A committed batch can be replayed in its original
order when per-item acknowledgments are missing. Canonical application continues
to require a separately approved plan.

## Measurements

The [machine-readable summary](KNOWLEDGE-DISCOVERY-OPTIMIZATION-R2.json) records
per-operation elapsed time, extraction and inventory counts, validations,
transactions, SQLite pages, and storage. Run the reproduction from the
repository root with Python 3.12, Git, and the development environment.

```bash
python scripts/setup_p3.py
.venv/bin/python -B scripts/discovery_r2_benchmark.py --worker --implementation-commit "$(git rev-parse HEAD)" --output /tmp/discovery-series.json
.venv/bin/python -B scripts/discovery_r2_benchmark.py --batch --implementation-commit "$(git rev-parse HEAD)" --output /tmp/discovery-batch.json
```

For R1, put that revision's `packages/knowledge/src` and `packages/harness/src`
ahead of the installed package on `PYTHONPATH`. Use the audited R1 SHA as
`--implementation-commit`. The synthetic fixture has 38,350 eligible files,
a seeded canonical graph, independent registered Confluence evidence, and
12,500 pending candidate batches. The no-change test uses a fresh ID each time
to measure real history growth. The edit phases commit each source delta.
Cache and OS page state are warm after the first full scan. SQL trace bytes
measure submitted write text. SQLite used-page and file sizes measure logical
allocation and physical growth separately.

After 20 fresh no-change scans, R1 added 388.18 MB of terminal payloads.
R2 added 1.40 MB, a **99.64% reduction**, and reused every inventory block.
The mean R2 terminal increment was **68.55 KiB per scan**. R2 used 1.41 MB
of additional logical SQLite pages and reused allocated free pages for all
20 runs. R1 allocated another 388.56 MB on disk.

### Populated 38,350-file repository

The matched subset reran the same inputs with each implementation in sequence.
The longer storage cohorts shared the executor with other qualification work.
Their elapsed values are retained in the JSON, with operation counts and storage
as the more stable comparison. The long R2 cohort used `19d6e2f`; the matched
subset and separate active-worker probe used the final product revision.

| Scenario | R1 | R2 | Extracted files |
| --- | ---: | ---: | ---: |
| Full scan | 88.31 s | 68.89 s | 38,350 |
| No-change incremental | 37.19 s | 23.93 s | 0 |
| Four-file incremental | 40.51 s | 15.72 s | 4 |
| 100-file incremental | 30.05 s | 15.89 s | 100 |
| First four-file Harness capture and delivery, with replay | 67.33 s | 25.83 s | 4 |
| Resume a durable 100-file checkpoint | 124.05 s | 38.55 s | 38,250 |

Each managed full or incremental run used two inventories and zero per-chunk
Python processes. The first R2 Harness workload used three inventories,
including one final exact-source verification for new batch admission.
The equivalent R1 delivery used two. Across ten consecutive four-file
Harness tasks, R1 delivered **1 of 10** and returned
`capture-observation-cache-incomplete` for the other nine. R2 delivered
**10 of 10**, extracted four files per task, and replayed all outboxes
with the same receipts. The different recovery times came from separate
cohorts under different concurrent load. Both resumed from the last
durable checkpoint.

The active exact-revision R2 worker recorded **11.59 ms p95**
over 1,385 progress observations,
with a maximum formatted response of 1,723 bytes.
The reviewed R1 implementation measured 10.6 ms p95 during active extraction.
The final R2 worker peak process RSS was 494.1 MB.


| Phase | R1 physical growth | R2 physical growth | R1 logical growth | R2 logical growth |
| --- | ---: | ---: | ---: | ---: |
| 20 fresh no-change scans | 388.56 MB | 0.00 MB | 388.56 MB | 1.41 MB |
| 20 four-file updates | 391.02 MB | 2.58 MB | 391.02 MB | 4.17 MB |
| 10 100-file updates | 213.20 MB | 23.08 MB | 213.20 MB | 23.08 MB |
| 10 Harness deliveries | 0.03 MB | 0.17 MB | 0.03 MB | 0.17 MB |

The first R1 full artifact exposed 19.35 MB of inventory JSON, 28.22 MB
of coverage, and 1.31 MB of observations. In the matched run, initial SQLite
used pages went from **81.10 MB to 39.23 MB**.
R2 used 1.16 MB of terminal payloads and 6.16 MB
of allocated inventory blocks. On that R2 database, the cache, canonical
records/revisions, candidate queue and indexes occupied
8.09, 2.86,
17.94, and 2.91 MB respectively.
Repeated four-file updates stored only affected buckets and their new manifest.
With concurrent load, whole worktree verification and authoritative store
checks remain the largest warm update costs. The matched authoritative artifact
read took 5.28 s on R1 and
4.33 s on R2.

On the 10,000-file two-chunk probe, both revisions used one inventory, two
writes and one control validation. Write p95 was 21.8, 28.6 ms for R1 and
26.2, 22.2 ms for R2 in the two samples each.

### Candidate delivery

These populated-store samples time Knowledge submission and replay. They
exclude Harness execution and lexical capture. R2 uses the public single-item
route for one candidate, then a compatible batch for larger inputs.

| Candidates | R1 delivery | R2 delivery | R1 replay | R2 replay | Delivery validations |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1.58 s | 2.44 s | 1.60 s | 2.69 s | 1 → 1 |
| 5 | 8.57 s | 3.60 s | 8.11 s | 3.23 s | 5 → 1 |
| 10 | 17.52 s | 7.50 s | 18.20 s | 5.83 s | 10 → 1 |
| 50 | 91.09 s | 8.27 s | 239.47 s | 6.27 s | 50 → 1 |
| 100 | 515.41 s | 5.51 s | 506.80 s | 4.50 s | 100 → 1 |

The five-candidate delivery used **80% fewer authoritative validations**
and finished **2.38× faster** in this sample. Co-running tasks affected
elapsed times, especially the larger R1 samples. Validation and transaction
counts are directly comparable. The JSON includes exact throughput, SQL trace
volume, and write transaction p50/p95. Independent direct submission and batch
submission produced identical candidate IDs and canonical records after exact
plan approval and acknowledgment.

In an alternating in-memory reader probe with the same 38,350-path inventory
and coverage, median CPU time for a full artifact was 0.544 s for R1 JSON and
0.649 s for the final R2 manifest over seven reads each. The initial compact
decoder used 0.793 s in an earlier probe. The remaining approximately 0.10 s of
CPU is spent on checked reconstruction. Paginated scan summaries skip it.


## Qualification

GitHub reported failure for the [P4 revision job](https://github.com/Ermak-P/Knowledge-/actions/runs/45767444914/job/139731669867).
Its verify matrix was skipped. Both jobs in the [discovery qualification run](https://github.com/Ermak-P/Knowledge-/actions/runs/45766976018)
also failed. The GitHub App returned empty step lists, no retained artifacts,
and HTTP 404 `BlobNotFound` for each job log. There is no recorded Discovery test execution. The diagnostic gap leaves runner provisioning,
billing, permissions, and setup causes undetermined.

The exact final product SHA passed source-locked Linux portable qualification,
including installed package tests, machine install/upgrade, and real OpenCode
MCP commands. The receipt is `71c76f151b694f4684d8eb134a04c67a`. The installed
machine suite ran 248 tests with 246 passes and two skips. An earlier
comprehensive Linux wheel run on `6a24ea4` ran 649 tests with zero failures and
13 skips. An initial mixed-runtime probe had two isolated child-process errors
because those children loaded R1 against compact R2 data. The installed R2 run
resolved both.

Archived copies of `60d7a97fcd2126605d0720dc3bf191fa63d7b1ad` and
`2943052a48a919376ff44e8e029470a75277967c` generated real pre-R2 fixtures.
R2 preserved their exported knowledge, candidate approval fingerprints and
exact scan artifacts, created backups, and resumed prior checkpoints without
re-extracting completed paths. Explicit identity relocation also archived
R2 compact history successfully.

The connector returned no published Windows qualification status. Direct
Actions API access received HTTP 403 at the environment proxy. This executor
is Linux, so native Windows remains blocked.

The separate exact-revision installed-wheel suite also ran **649 tests** with
**zero failures** and **13 skips**.

For native Windows qualification, run the following in PowerShell on the
exact product revision. The installed P4 route is also available through
`scripts/verify-p4-windows.ps1`.

```powershell
git switch --detach 259850439a4751590a91731e1ae4ebee05dfd513
py -3.12 scripts/setup_p3.py
if ($LASTEXITCODE) { exit $LASTEXITCODE }
$env:PYTHONPATH = 'tests'
$Python = '.venv/Scripts/python.exe'
& $Python -X utf8 -B -m unittest test_discovery_optimization test_discovery_r2 test_core_reliability test_machine_commands test_p3_platform test_integrated_capture test_integrated_knowledge test_persistence_recovery test_confluence_source test_confluence_sync
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& $Python -X utf8 -B scripts/verify_machine.py
exit $LASTEXITCODE
```

## Обновление и проверка IPM

1. Запишите используемое поколение Knowledge и Git-ревизию IPM. Дождитесь
   завершения активных scan/Harness jobs либо отмените их штатной командой и
   дождитесь терминального состояния. Закройте OpenCode.
2. Создайте резервную копию через `knowledge.maintain_cli backup-preview` и
   одобрите только точный fingerprint плана резервного копирования. Сохраните
   текущий `current.json`, настройки OpenCode и приватную выгрузку
   `knowledge.cli export`. Команды приведены в разделе 1
   [инструкции IPM](Knowledge-IPM-Integration-Validation.md).
3. Запустите `install.ps1 -McpDir <текущий каталог установки>` из проверенной
   ревизии R2. Перезапустите OpenCode. Выполните `knowledge.cli validate`,
   `status` и `export`. Сравните canonical claims, evidence, ревизии,
   решения очереди и исходные fingerprints подготовленных планов. Для
   совместимой базы полный scan при установке не требуется.
4. На изолированной копии исходников выполните warm
   `/knowledge-candidates-update {"base":"HEAD","head":"HEAD"}`. Запишите
   scan ID, source identity и число извлечённых файлов. Проверьте исторический
   scan через `scan-status --scan-id`. Затем выполните два последовательных
   Harness задания с изменениями в разных файлах и повторите доставку.
   Сверьте идентификаторы кандидатов и статусы outbox.
5. При `capture-observation-cache-incomplete` проверьте изменённые настройки
   проекта и указанные пути. Если совместимых наблюдений действительно
   недостаточно, используйте явное восстановление покрытия через
   `/knowledge-init` или ручную проверку кандидатов.
6. Перед откатом сохраните актуальное состояние R2 отдельно. Старый runtime
   следует запускать с совместимой резервной копией, созданной до R2.
   Используйте процедуру восстановления из
   [инструкции IPM](Knowledge-IPM-Integration-Validation.md).
