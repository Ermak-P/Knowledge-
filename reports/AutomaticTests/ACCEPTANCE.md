# Automatic .NET test discovery — acceptance

Repository: https://github.com/Ermak-P/Knowledge-
Branch: https://github.com/Ermak-P/Knowledge-/tree/codex/automatic-test-discovery
Base: `5ec03763dac825adaca754828ac8decd821b1d5c` (latest main, integrated-fixes PR #7 merged). The old integrated-fixes remote branch was already removed.
Implementation: `c6a200b2558c94b58b83015c691d39442bb0a7c8`
Candidate: **0.5.0rc1**, unpublished. Requirements: [task](../../tasks/Harness-Automatic-Test-Discovery-Codex-Task.md).

## Configuration and inspection

Before, runner v1/task v1 or v2 explicitly approved a build and a test recipe. The tracked demo's v1 test recipe was a Python verifier with a second executable setting; other legacy .NET recipes explicitly supplied test project/TRX arguments. Original demo excerpt:

```json
{"version":1,"recipes":{"test":{"kind":"test","argv":["/ABSOLUTE/PATH/TO/python","test_feature.py","/ABSOLUTE/PATH/TO/dotnet"],"result":{"format":"unittest","path":""},"rerun_safe":true,"env":{}}}}
```

After, normal .NET runner v2/task v2 has only the trusted build configuration:

```json
{"version":2,"recipes":{"build":{"kind":"build","argv":["C:\\Program Files\\dotnet\\dotnet.exe","build","Application.sln"],"result":{"format":"exit","path":""},"rerun_safe":true,"env":{}}}}
```

This excerpt omits the unchanged provider/limits/capture fields. The task uses `"recipes":["build"]`; no project list, test command or TRX path moves elsewhere. A wrapper build may supply one shared absolute `dotnet` setting; otherwise the build executable/environment are inferred. Full tracked examples: [runner](../../examples/p4/runner.json), [task](../../examples/p4/task.json).

Exact inspection command, using the installed runtime:

```powershell
C:\LLM\harness-runtime\Scripts\python.exe -I -m harness.run_cli discover-tests --root C:\Projects\Application
```

Representative actual CLI output (project rows shortened to paths; the real JSON includes hashes/root/identity/exclusions):

```json
{"ok":true,"count":3,"errors":[],"projects":[
 {"path":"integration/IpmAzureAutotests.csproj"},
 {"path":"unconventional/IpmAzureCommon.UnitTests.csproj"},
 {"path":"zz outside solution/Тесты Ω/ZZZTests.csproj"}
]}
```

Discovery itself is read-only. Case-insensitive basename suffix matching includes untracked files and projects outside a solution. No matching projects and partial/zero/skipped test suites fail the mandatory final gate. Every project/framework is restored, inspected and tested sequentially via the existing broker, with fresh owned TRX and strict result/assembly/source/config/inventory binding. See [runtime contract](../../docs/P4/AUTOMATIC-TESTS.md) and [agent instructions](../../docs/P4/DOTNET-AGENTS.md).

## Migration and boundaries

Finish/recover already-started runner v1 work under its original configuration, then explicitly configure runner v2 and start a new task v2. Runner v1 preserves non-.NET/explicit test workflows. Run formats v1/v2 remain readable; automatic coding uses format v3, rejected by older runtimes. Maintenance backup/restore supports the new state and preserves exact approval semantics without a Harness import in Knowledge.

Inventory add/rename/remove/content drift refuses resume/finalization and requires a new validated run. Discovery grants no project-file editing rights. Known receipts recover without replay; unknown automatic process outcomes remain blocked rather than guessed safe to rerun. Controller recovery is serialized before stale PID handling, while the inherited project execution lease and existing supervisor retain process ownership.

For permanent installation, choose `--env` outside the removable staging tree, as in INSTALL-RU.md. The usage demo may use disposable environments under its extracted kit.

The installed SDK must support MSBuild `-getProperty` (17.8 / SDK 8+) and the project's actual SDK/frameworks/package sources. Qualification pins SDK 10.0.404. The parser accepts at most 2,000,000 bytes per TRX and at most 32 resolved frameworks per project; exceeding those bounds fails explicitly. Project-file size, logs, elapsed execution and cancellation retain the configured limits. No automatic SDK acquisition or retargeting occurs in the product. Model decisions in executable acceptance are scripted HTTP; builds/tests, MCP, supervision, repair, review/capture and package installation are real. No live-model or OpenCode desktop qualification is claimed.

The repository contains the existing offline core-wheel `install.py --env --profile knowledge|full` installer. It supports staging removal and independent Knowledge installation. A standalone wrapper implementing `--mcp-dir PARENT` / `PARENT/harness` is absent; rebuilding that unrelated installer is outside this task. Optional MCP retains its existing separately selected pinned online dependencies and `harness_companion` registration. [Machine installation RU](../../docs/P4/INSTALL-RU.md) and [project setup RU](../../docs/P4/PROJECT-SETUP-RU.md) remain separate.

Build: `python scripts/setup_p3.py`, then `.venv/bin/python scripts/build_p4.py --output .local/p4-release`. Full installed qualification: `.venv/bin/python scripts/verify_p4.py`; native Windows: `powershell -NoProfile -File scripts/verify-p4-windows.ps1`.

## Platform qualification and acceptance

Implementation is **ready for review**. The exact-source installed route passed on Linux and native Windows; these are the executed profiles, separate from live-model/desktop qualification. Final CI: [44615158655](https://github.com/Ermak-P/Knowledge-/actions/runs/44615158655). Tested implementation: `c6a200b2558c94b58b83015c691d39442bb0a7c8`. Source identity: `7e87a2eb6ac2e321f995bcf3473665360be8e5fb5419eb71c1f4738addf9bc59`.

| Profile | Installed regressions | Full route | Automatic SDK scenarios |
| --- | --- | --- | --- |
| Linux / Python 3.12 / SDK 10.0.404 | 236 total: 225 PASS, 11 native-only SKIP, 0 failures/errors | PASS_PORTABLE | CLI, MCP, repair, new zero-test project, crash/resume, TRX tamper PASS |
| Windows Server 2022 / NTFS / PowerShell 5.1 / Python 3.12 / SDK 10.0.404 | 236 PASS, 0 SKIP/failures/errors | PASS_NATIVE | Same scenarios PASS, including restricted MCP environment |

[Machine-readable qualification](qualification.json) records receipts, source identity, all route checks and wheel/ZIP hashes. Both OS runs produced identical core wheel hashes. Profile ZIP hashes are retained separately. [Expected source](expected-source.json) is checked against both receipts. Full raw distributions and remaining qualification artifacts are retained at the [exact-source CI evidence branch](https://github.com/Ermak-P/Knowledge-/tree/p4-ci-evidence/c6a200b2558c94b58b83015c691d39442bb0a7c8).

[L]: evidence/c6a200b2558c94b58b83015c691d39442bb0a7c8/Linux
[W]: evidence/c6a200b2558c94b58b83015c691d39442bb0a7c8/Windows

The PASS links below open the profile evidence root. `automatic-tests/` contains raw status/action journals, recipe logs, fresh TRX, inspection output, race and empty-project results. `tests.json` contains the outcome of every named regression. Source tests: [automatic contract](../../tests/test_automatic_discovery.py), [native safety](../../tests/test_p3_platform.py); real installed driver: [automatic_test_discovery.py](../../scripts/automatic_test_discovery.py).


| ID | Linux | Windows | Evidence exercised | Execution kind |
| --- | --- | --- | --- | --- |
| AT-01 | [PASS][L] | [PASS][W] | `test_AT01_exact_names_case_suffix_and_readonly_inspection`; CLI `*-inspect.log` | Real filesystem, both OS; no process during inspection |
| AT-02 | [PASS][L] | [PASS][W] | `automatic-tests/result.json`: CLI + enrolled MCP; task authorizes only build | Real HTTP + MCP + SDK + independent review |
| AT-03 | [PASS][L] | [PASS][W] | Three directories; third absent from solution; CLI multi-target; unique TRX per generation/framework | Real SDK, 4 tests in final CLI suite and 3 in MCP |
| AT-04 | [PASS][L] | [PASS][W] | CLI first generation: 2 projects pass and 1 fails; authorized repair; second full generation passes | Real failing/passing TRX, fresh action directories |
| AT-05 | [PASS][L] | [PASS][W] | `test_AT05_*`; `empty-project-result.json`; `tamper-status.json` | Parser negative fixtures/no-project pure runtime; real zero-test/zero-exit and deleted TRX |
| AT-06 | [PASS][L] | [PASS][W] | `test_AT06_*`; `empty-project-result.json`; recovery drift refusal | Unit add/rename/remove; real active/completed resume refusal and next-run inventory 4 |
| AT-07 | [PASS][L] | [PASS][W] | `test_AT07_over_twenty_visible_with_budget_and_cancellation_not_success` | 23 projects, 69 broker scheduling operations with synthetic receipts; all 23 unfinished on early budget/cancel |
| AT-08 | [PASS][L] | [PASS][W] | `test_AT08_*`; CLI paths containing spaces/Cyrillic/Ω; owned artifact trees | Real filesystem/path guards and actual SDK argv/artifacts |
| AT-09 | [PASS][L] | [PASS][W] | `recovery-race.json`; `test_AT09_*`; existing recovery regressions | Real exit 73, competing resume, exactly 10 processes/1 patch, no replay; scoped write refusals |
| AT-10 | [PASS][L] | [PASS][W] | Full installed `tests.json`; P3 marked/unmarked/pending lifecycle; rc3 interruption upgrade; real legacy .NET application | Existing suite plus backup/restore of runner v2/run v3; explicit non-.NET recipes retained |
| AT-11 | [PASS][L] | [PASS][W] | Source-bound `RELEASE.json`; `first-use/result.json` and logs; automatic suite imported from installed prefix | Actual outside-checkout install, offline core profiles, deleted staging, SDK tests and candidate-only capture |

Acceptance statuses are derived from the qualified platform receipts, never from this description alone. Full test identifiers/results are retained in each platform's `tests.json`; raw automatic generations and per-framework TRX are in `automatic-tests/`.

The case-collision fixture runs on Linux, where two case-distinct filenames can be created; default NTFS does not permit that pair. Native path identity, aliases, junctions, symlinks and hardlinks are covered by Windows safety cases. The 23-project scheduling case uses synthetic receipts, explicitly separated from the actual three-project SDK scenarios.

## Recorded correction during qualification

The first exact-source CI run ([44609619323](https://github.com/Ermak-P/Knowledge-/actions/runs/44609619323), implementation `fd113f264c1c77313edc8db69680c65cf5449d65`) found one failure on each OS in `test_p2_r1.ReviewCorrections.test_r3_configuration_is_reloaded_under_ownership_before_capture`. A redundant configuration check outside the legacy driver's error boundary raised instead of returning the established structured refusal. Commit `b23f288` removes that duplicate; automatic mode retains its early configuration/inventory guard, and the existing driver still checks legacy configuration before effects. The specific installed regression then passed locally. Complete original failed tests/ledgers/logs are retained under `failed/fd113f264c1c77313edc8db69680c65cf5449d65/`; they do not qualify the final implementation.


The second run ([44610771988](https://github.com/Ermak-P/Knowledge-/actions/runs/44610771988), `b23f288`) passed the complete Linux route and all 235 native Windows regressions. Native automatic CLI/multi-target/empty-project checks passed, then the MCP case failed its trusted build: NuGet `GetRestoreSettingsTask` reported null `path1`. The MCP SDK client intentionally omits ProgramFiles variables from its inherited environment; direct CLI had those variables. The final correction recovers only missing ProgramFiles/ProgramData directory defaults from Windows known-folder APIs, preserving the process environment allowlist and explicit approved values. A native restricted-environment regression and portable no-secret/override assertion cover this boundary; the final real MCP/SDK qualification passed on both profiles. The failed native ledger is retained under `failed/b23f2886147ab7572064f231109e459802e69c3d/Windows/`; it is not a final native PASS.
