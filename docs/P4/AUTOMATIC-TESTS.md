# Automatic .NET testing (0.5.0rc1)

Runner **v2** is the normal .NET configuration. Keep provider, limits, capture and trusted build recipes; remove all manual test recipes. Coding tasks use task v2 and list only their authorized build recipe names. The runtime owns the mandatory test suite. Runner v1 with task v1/v2 retains its original explicit recipes, including non-.NET flows. Already-started runs keep their original task/configuration hashes. Migration is explicit: finish/recover old work under its original runner, then configure runner v2 and start a new task v2 run. Editing configuration never migrates a pending run's authority.

```json
{"version":2,"provider":{"endpoint":"http://localhost:9000/v1/chat/completions","model":"your-model"},"limits":{},"capture":"required","recipes":{"build":{"kind":"build","argv":["C:\\Program Files\\dotnet\\dotnet.exe","build","Application.sln"],"result":{"format":"exit","path":""},"rerun_safe":true,"env":{}}}}
```

`examples/p4/runner.json`, `task.json` and `configure.py` are the tracked templates; generated kits contain them under `examples/`. The build's absolute `dotnet` executable and environment are shared automatically. Different .NET executable paths or conflicting build environments are errors, not guesses. A wrapper-based build can declare one shared absolute `"dotnet": "..."` setting. A second executable just for tests is unnecessary. Runner v2 rejects manual test branches; runner v1 remains the precise compatibility path for them.

## Read-only inspection

```sh
python -I -m harness.run_cli discover-tests --root /absolute/project
```

The resolved root, identity, count, sorted project paths and file hashes, exclusions and errors are returned as JSON. No process, MSBuild evaluation or test code runs during discovery. On native Windows, owned processes recover missing ProgramFiles/ProgramData directory variables from Windows known-folder APIs when a restricted MCP host omits them; the environment allowlist and explicit approved build values remain in force. The MCP companion also exposes `harness_discover_tests`; its registration name remains `harness_companion`.

Only the **basename** matters: case-insensitive suffix `Tests.csproj`. Both `IpmAzureCommon.UnitTests.csproj` and `IpmAzureAutotests.csproj` match. `FooTests.csproj`, `Foo.Tests.csproj`, `Foo.UnitTests.csproj` and uppercase variants match anywhere inside ordinary project source, even untracked or outside a solution. `TestSupport.csproj`, `FooTests.csproj.bak` and production `tests/App.csproj` do not match. No `IsTestProject`/package precondition hides a suffix match; a match unable to execute actual tests fails verification.

Excluded directory basenames, ignoring case: `bin`, `obj`, `.git`, `.harness`, `.knowledge`, `.ai`, `.maintenance`, `.venv`, `.local`, `.vs`, `TestResults`, `__pycache__`, `node_modules`. These are generated, dependency or control trees. There is no broad `packages`/`vendor`/Git-ignore exclusion. The broker's private-path and filesystem policy still applies. Non-excluded linked directories, matching symlinks/junctions/hardlinks and ambiguous case-folded project paths are explicit discovery errors; they cannot yield a partial successful suite. Links are never followed to discover more authority.

## Execution and evidence

Each new coding run snapshots the project inventory and content hashes under its lease. Run format **v3** carries the v1 automatic-test extension; older runtimes reject that format. Legacy run formats v1/v2 remain supported. A changed project list, rename/removal or project-file hash invalidates the active run and requires a new validated run. Resume and finalization check it again. No project-file editing permission is granted by discovery.

After authorized builds, automatic verification runs sequentially through the same owned-process broker:

1. `dotnet restore PROJECT --disable-parallel -m:1`.
2. Broker-owned MSBuild property inspection resolves the actual target frameworks and assembly target. Multi-target metadata is evaluated per framework where needed.
3. `dotnet test PROJECT --framework FRAMEWORK --logger "trx;LogFilePrefix=harness" --results-directory OWNED_ATTEMPT/trx -m:1 -p:UseSharedCompilation=false -p:TestTfmsInParallel=false` for every target.

There is no blind `--no-build` or `--no-restore`; projects absent from the solution are restored and built too. The installed SDK, project `global.json`, configured environment and package sources are respected. No SDK installation or framework retargeting occurs. The operator must provide an SDK supporting MSBuild `-getProperty` (MSBuild 17.8 / .NET SDK 8 or newer), the project's requested SDK and normal project dependencies. Qualification uses SDK 10.0.404; older unsupported SDKs fail property inspection explicitly. Targets/assemblies must resolve inside the authorized root, and the existing link checks apply.

Each project/framework/generation has its own stable action and unique owned attempt directory. Report identity, fresh timestamps, assembly binding, executed/passed/failed/skipped counts and actual result/definition rows must agree. Missing/malformed/stale/foreign reports, zero tests or skipped/not-executed results fail. One failed project prevents completion; projects not reached remain NOT_RUN. Failed/partial suites never become successful totals. Cached receipts are reusable only while their owned logs, TRX and assembly hashes agree. Unknown automatic process outcomes are conservatively non-rerun-safe; receipt recovery does not replay a known completed process. A non-inherited controller lock serializes resume/recovery before stale PID inspection; the original inherited project lease still owns all processes. A live competing driver is not treated as an orphan supervisor.

User recipe limits do not limit discovered projects. Request/time/process budgets may stop work explicitly, retaining the complete inventory and unfinished statuses. Read-only tasks do not execute tests. P4 repairs preserve attempts and global budgets; a changed source receives fresh full verification. Intermediate items may explicitly use narrower build-only verification, but the final item/repair always requires the complete authorized inventory and independent source/config-bound review.

`harness-run status --root ROOT --run-id ID` exposes full `automatic_tests`, generations, per-project/framework status/counts/artifacts and the `@automatic-tests` aggregate gate. Planning/Main/Reviewing receive a bounded summary and `test_inventory(offset,limit)`; full inventory/evidence stays durable. Omitting a Testing delegation or selecting only build cannot disable the gate.


## Legacy .NET Framework projects (R1)

The same suffix rule includes non-SDK `ToolsVersion` projects. Framework resolution queries evaluated `TargetFrameworkIdentifier`, `TargetFrameworkVersion`, `TargetFrameworkProfile` and `UsingMicrosoftNETSdk` alongside the SDK fields and assembly path. For a classic project with empty `TargetFramework`/`TargetFrameworks`, `.NETFramework` + `v4.7.1` resolves to the native moniker `.NETFramework,Version=v4.7.1`; no `TargetFramework=net471` is injected and project files are never converted or retargeted.

Classic .NET Framework 4.x execution requires **native Windows**, an installed compatible CLR 4.x, matching reference assemblies/Developer Pack, the project's NuGet dependencies and an adapter/test host compatible with its target. The native mixed qualification uses .NET SDK 8.0.408 with Visual Studio MSBuild 17.x and an existing .NET Framework 4.8 targeting pack/runtime; the existing SDK 10.0.404 checks remain separate. The exact review `v4.7.1` metadata shape is evaluated separately. Linux metadata evaluation works, but execution stops with `legacy-dotnet-framework-requires-native-windows`. Missing runtime reports `legacy-dotnet-framework-runtime-missing`; missing reference assemblies (`MSB3644`) report `legacy-reference-assemblies-missing`. Other framework identifiers/unsupported versions fail explicitly; no partial suite passes.

After restore/metadata inspection, each classic project receives broker-owned restore and build, then fresh post-build target evaluation. `dotnet vstest ASSEMBLY /Framework:EVALUATED_MONIKER /TestAdapterPath:ASSEMBLY_DIRECTORY /Logger:trx;LogFileName=harness.trx /ResultsDirectory:OWNED_ATTEMPT/trx` executes the actual assembly through the already trusted SDK. The ordinary adapter in the output directory is used; zero/missing/skipped/foreign/stale TRX still fails. SDK-style projects retain `dotnet test --framework TFM`, including multi-target behavior.

Classic projects require full Visual Studio MSBuild (including its NuGet asset resolver and any project workloads). They must already have one unambiguous absolute `MSBuild.exe` in the configured trusted **build** recipes authorized by the task. Harness reuses that executable for classic restore/build/property evaluation and uses `-p:RestorePackagesConfig=true` where applicable. It does not discover or execute an unapproved Visual Studio tool. If the build identifies MSBuild rather than dotnet, provide the existing one shared absolute `dotnet` setting for SDK/VSTest; no manual test recipe, project list or report path is introduced. Full MSBuild must support property inspection (17.8+) and be compatible with the selected SDK/project imports. Missing the trusted full build tool reports `legacy-full-msbuild-required`. Missing native restore tooling for packages.config reports `legacy-packages-config-requires-trusted-native-msbuild`; missing Visual Studio workloads/imports remain explicit build failures. No SDK, targeting pack or workload is installed automatically.

New verification generations record metadata-query version 2. Existing generations keep their original four-property SDK query, cached receipts and authority. Old SDK receipts remain readable. A prior legacy run already stopped under the old metadata policy needs a newly validated run; incomplete legacy metadata is never guessed into a test command. Inventory/source/config/entry guards, non-rerun-safe unknown outcomes, owned artifacts and final complete-suite validation remain unchanged.
