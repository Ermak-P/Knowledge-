# Knowledge push reliability and incremental source reconciliation

## Production incident

The reported Knowledge 0.5.0rc1 installation had around 44,000 discovered files, 38,000 eligible files, 25,006 pending candidates and 1,394 canonical records. Plan preparation took 61.375 seconds. Six invocations failed under a 30-second OpenCode child-process kill. The reported queue survived and no plans committed.

The installer copies `host/machine_opencode.mjs` into the global OpenCode plugin. The old template ran plan preparation in a command child and killed that child when the timer fired. It also killed a child when the display buffer exceeded its limit. A separate failure came from comparing the repository-wide inventory digest in each pending Git binding. A README edit or unrelated commit changes that digest even when a lexical candidate’s evidence and identity inputs remain valid. The old preparation pipeline also validated the queue during readiness, source detection, and plan construction, and inventoried the repository both before and after preparing an unapproved plan.

## Prepare, observe and approve

| Action | OpenCode command arguments | MCP |
| --- | --- | --- |
| Start or join | `/knowledge-candidates-push` | `knowledge_plan(action="prepare", wait_seconds=0)` |
| Inspect a job | `{"action":"status","job_id":"<job-id>"}` | `knowledge_plan(action="status", job_id="<job-id>")` |
| Request cancellation | `{"action":"cancel","job_id":"<job-id>"}` | `knowledge_plan(action="cancel", job_id="<job-id>")` |
| Retry a cancelled or interrupted preparation | `{"action":"resume","job_id":"<job-id>"}` | `knowledge_plan(action="resume", job_id="<job-id>")` |
| Apply after separate approval | `{"approve":"sha256:<machine-fingerprint>"}` | `knowledge_plan(action="apply", approve="sha256:<machine-fingerprint>")` |
| Recover an already committed apply | `{"action":"recover","plan":"sha256:<approved-machine-fingerprint>"}` | `knowledge_plan(action="recover", approve="sha256:<approved-machine-fingerprint>")` |

The same arguments work with `/knowledge-update`. Omitting the ID from status selects the latest job. Compatible invocations join an active job. Preparation survives host exit and returns a stable ID and named stages from store validation to persistence. Use `knowledge_scan_diagnostics(section="plan-progress")` for the latest stage. Use `knowledge_scan_diagnostics(section="plan-dispositions", plan="<canonical_plan>", cursor=0, limit=20)` to page the disposition of every pending candidate. The canonical plan ID is the diagnostics selector. The separate machine fingerprint is the approval token.

- `KNOWLEDGE_OBSERVE_MS` controls how long the generated plugin follows an active job. The default is 15,000. Zero disables polling.
- `KNOWLEDGE_COMMAND_WAIT_MS` bounds the plugin’s wait for an individual command response. The default is zero, which disables that observer timeout. The child keeps running when the wait expires.
- `wait_seconds` controls the backend response wait on prepare, rebuild and resume. The default is two seconds and the range is zero through 30.
- `execution_seconds` optionally requests a cooperative worker execution deadline. The worker checks it at preparation stages. By default the worker may run until preparation finishes, fails or is explicitly cancelled. Resume can specify a different deadline.

After `OUTCOME_UNKNOWN`, inspect the job ID and resume that prepare. The SQLite transaction rolls back incomplete plan persistence. If the worker died after persistence, re-preparation can reuse the same canonical plan. Apply and acknowledgment still use separate transactions and exact approval. A job can finish if cancellation arrives after its persistence boundary.

## Source reconciliation

- A current exact Git binding remains valid. A positive lexical addition from a recorded complete scan can also retain its original candidate ID and evidence after unrelated drift. Preparation verifies the historical snapshot, the exact bytes and partition of the evidence, and the lexical policy and build configuration. It inspects changed code files in the relevant partition for new identity collisions. This step publishes no candidates.
- A changed, deleted or renamed evidence file defers the old candidate with the affected path and source range. Run `knowledge_scan(action="start", scope="incremental", base="<recorded-base>", head="<current-head>")` or `/knowledge-candidates-update` to discover current positive evidence for modified, renamed and newly added files. With only working-tree changes, the incremental command can use its default current range. Prepare again to see the new candidates and dispositions of the older entries. Source absence alone grants no authority to retire a canonical claim.
- Discovery-policy changes, build configuration changes, incomplete code coverage and missing historical proof can require broader discovery. Reviewed assertions and graph-dependent operations need explicit source reanalysis unless they still have the exact current binding. This preserves their source and approval requirements when lexical verification cannot establish their meaning.
- Confluence uses its registered page identity, snapshot and latest observed version. Stale Confluence candidates show the candidate and observed page revisions and can be reanalyzed independently of Git.
- Every pending candidate at preparation is included, skipped with an explicit reason, or blocked by the atomic plan. A coalesced candidate is included and identified as coalesced on the disposition page. Canonical and queue validation is repeated at apply, including an independent inventory immediately before the canonical commit when Git is in scope. A source change after preparation requires a new exact approval.

## Benchmark

Linux, Python 3.12. One instrumented preparation per implementation on equivalent repositories with 38,000 eligible files, 6,000 excluded files, 25,006 individually queued Git-bound candidates, and 1,394 canonical records. Before is recovery-branch commit `63dfe4e35bdc1c2a3af0a3099749371bfb90b1b6`. After is the preparation implementation in `97df28d1c0c98a2fc6b9dfd0aad4c9cf14c61e8e`. These are synthetic timings.

| Measurement | Before | After |
| --- | ---: | ---: |
| Readiness through persisted plan | 24.95 s | 12.70 s |
| Inventory traversal, Git inspection and hashing | 7.86 s | 4.72 s |
| File hashes counted | 76,000 | 38,000 |
| SQLite control validation | 10.57 s across 3 passes | 3.60 s across 1 pass |
| Candidate validations | 75,018 | 25,006 |
| Instrumented SQLite SELECT calls | 96 | 34 |
| SQLite plan insert | 0.22 s | 0.29 s |
| Source binding validation | 0.10 s | 0.03 s |
| Deduplication | 1.06 s | 0.98 s |
| Simulation | 2.08 s | 2.08 s |
| Canonical plan serialization for storage | 0.29 s | 0.31 s |
| Canonical SQLite plan | 28,654,349 bytes | 28,654,349 bytes |
| `last-plan.json` | 46,158,691 bytes | 1,067 bytes |
| Process peak RSS | 347 MiB | 371 MiB |

Timers overlap. The old `last-plan.json` duplicated the authoritative SQLite plan as pretty-printed JSON. The new file holds the bounded summary. The canonical payload is serialized once for fingerprint and persistence. Holding the inventory alongside the validated queue increased peak memory on this fixture. The transaction still materializes the plan for exact deduplication, graph simulation and a stable fingerprint. Disposition pages also decode the selected persisted plan. Neither status polling nor cancellation reads candidate bodies.

Run the fixture with `python -B scripts/push_benchmark.py --output /path/outside/the/checkout/result.json`. The script can target the previous package sources through `PYTHONPATH` while using the same fixture and instrumentation.

## Installation and acceptance

The Linux regression run reported 323 passes and 13 Windows-only skips. It covered discovery and checkpoint recovery, the generated plugin peer, a worker held for more than 30 seconds, a 25,006-candidate durable plan, concurrent invocations, cancellation, a crash before SQLite commit, and Git and Confluence changes before or during apply.

The standard Linux installer trial passed all 13 checks on `97df28d1c0c98a2fc6b9dfd0aad4c9cf14c61e8e`. The native Linux OpenCode 2.4.0 trial passed all 11 checks with `07af696eac2343501cacf887fb308fb3b7667e6f`, including global command registration, permissions, exact approval and acknowledgment. An actual upgrade from the previous installed recovery runtime `a905385c461a01d7bf557eba08638eebc0de6dda` preserved the canonical store and all 13 queued fixture candidates, installed the generated plugin, retained the canonical plan ID, and required a fresh machine approval before commit. The tested release manifest SHA-256 was `05e66028c16e80707db7575e789314622ffe7fef8ca5404843419fad62462ed5`.

The production repository and native Windows remain unverified.

Install the updated kit over the existing machine directory using the normal installer, then restart OpenCode so it loads the generated plugin and command templates. The change uses the existing SQLite tables and adds plan job metadata alongside the installation’s project state. Existing candidates, decisions and histories remain available. An approval sealed to an earlier runtime may require re-preparation and a new explicit approval after upgrade.

For Windows qualification, build a kit from the recovery checkout with Python 3.12 and Node.js and run the native installer, native host and focused tests in PowerShell.

```powershell
py -3.12 scripts/setup_p3.py
$Runtime = (Resolve-Path '.venv\Scripts\python.exe').Path
$env:PYTHONPATH = 'tests'
& $Runtime -B -m unittest test_push_reliability test_machine_commands test_core_reliability test_core_bootstrap test_plan_deduplication test_confluence_source test_p3_platform
if ($LASTEXITCODE) { throw 'Regression suite failed' }
$Output = Join-Path $env:TEMP ('knowledge-push-' + [guid]::NewGuid())
$Commit = (git rev-parse HEAD).Trim()
& $Runtime -B scripts/build_p4.py --source-id $Commit --output (Join-Path $Output 'build')
if ($LASTEXITCODE) { throw 'Build failed' }
$Kit = Join-Path $Output 'build\knowledge-harness-0.5.0rc1'
& $Runtime -B scripts/machine_installer_trial.py $Kit (Join-Path $Output 'installer')
if ($LASTEXITCODE) { throw 'Installer trial failed' }
$OpenCodeDir = Join-Path $Output 'host'
& $Runtime -B scripts/setup_machine_host.py --output $OpenCodeDir --evidence (Join-Path $Output 'provenance')
if ($LASTEXITCODE) { throw 'OpenCode setup failed' }
& $Runtime -B scripts/machine_native_trial.py --kit $Kit --host (Join-Path $OpenCodeDir 'opencode.exe') --output (Join-Path $Output 'native')
if ($LASTEXITCODE) { throw 'Native OpenCode trial failed' }
```
