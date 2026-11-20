# Automatic test discovery — R1 / F1 correction

Review: [Harness-Automatic-Test-Discovery-Review-R1.md](../../../tasks/Harness-Automatic-Test-Discovery-Review-R1.md).
Base reviewed HEAD: `9052b2f123513e8dbcf0c693234baa78c595d123`.
Implementation: `5c03210e875a45fade50d3266b390b401093cc96`.
Source identity: `6cb988605942eda11bd1fdde5757e8e4c6ef793e12e5b57162c1b66247b22b51`.
Branch: https://github.com/Ermak-P/Knowledge-/tree/codex/automatic-test-discovery.
Product remains unpublished candidate 0.5.0rc1, identified by its new source and wheel hashes.

## Correction

F1 previously stopped valid classic C# projects because only SDK `TargetFramework(s)` fields were queried. Inspection now includes evaluated framework identifier/version/profile and SDK-style classification. The exact review shape resolves `.NETFramework,Version=v4.7.1`; no invented TFM is injected. Classic restore/build uses a full MSBuild executable already authorized by the task's build recipes. Test execution uses the existing trusted `dotnet vstest` against the post-build evaluated assembly and its actual framework moniker/adapter directory. The suffix inventory remains authoritative for both formats.

Full native build tooling is required for classic projects, including normal NuGet asset resolution and project-specific workloads. The package does not discover an unapproved Visual Studio executable or install/retarget SDKs, reference assemblies or user projects. The test harness selects existing Visual Studio tooling and explicitly approves its absolute path in the ordinary build configuration. The native mixed fixture uses SDK 8.0.408, compatible with Visual Studio MSBuild 17.x, and .NET Framework 4.8 with the existing targeting pack/runtime. The pre-existing SDK 10.0.404 route remains in qualification. The exact v4.7.1 review XML is separately evaluated by real broker-owned restore/property processes; that probe does not pretend to execute a test assembly without an adapter.

Inventory/source/config/companion identity, single-writer supervision and strict TRX/result/assembly/freshness checks remain active. No test recipe or per-project test path is required in runner config. No additional project-file writes are granted. The native build executable is selected only from the task-authorized build recipes and participates in protected executable inputs. New generations store metadata-query version 2; old SDK generations retain the original four-property command and cached receipt behavior. Previously failed legacy runs need a new validated run rather than a guessed migration.

## Prerequisites and diagnostics

Classic execution requires native Windows, compatible full CLR 4.x, matching reference assemblies/Developer Pack, full Visual Studio MSBuild 17.8+ compatible with the selected SDK/project imports, and the project's test host/adapter/packages. PackageReference and packages.config restore go through that trusted full build tool; packages.config uses `RestorePackagesConfig=true`. Native mixed tests qualify PackageReference projects; project-specific packages.config/workload combinations are not claimed as separately executed fixtures.

Linux returns `legacy-dotnet-framework-requires-native-windows` with a non-successful gate. Missing approved full build tooling returns `legacy-full-msbuild-required` (or `legacy-packages-config-requires-trusted-native-msbuild` for that restore style). Missing CLR returns `legacy-dotnet-framework-runtime-missing`; missing reference assemblies (`MSB3644`) remain an explicit failed build / `legacy-reference-assemblies-missing` automatic diagnostic. Unsupported identifiers/versions/profiles fail without hiding the project. Setup: [Russian project instructions](../../../docs/P4/PROJECT-SETUP-RU.md) and [detailed compatibility](../../../docs/P4/AUTOMATIC-TESTS.md#legacy-net-framework-projects-r1).

Build/install: `python scripts/setup_p3.py`, `.venv/bin/python scripts/build_p4.py --output .local/p4-release`. Full installed qualification: `.venv/bin/python scripts/verify_p4.py`. Focused real driver: `INSTALLED_PYTHON -I -X utf8 -B scripts/legacy_test_discovery.py OUTPUT`.

## Acceptance evidence

**F1 corrected and ready for review.** [Exact-source CI 44679688067](https://github.com/Ermak-P/Knowledge-/actions/runs/44679688067) completed successfully on both platforms. [qualification.json](qualification.json) binds the exact implementation/source identity, installed regression results, every route check, native prerequisites and equal Linux/Windows wheel hashes. Raw additional distributions are retained in the [CI evidence branch](https://github.com/Ermak-P/Knowledge-/tree/p4-ci-evidence/5c03210e875a45fade50d3266b390b401093cc96).

| Executed profile | Installed regressions | Full installed route |
| --- | --- | --- |
| Linux, Python 3.12, SDK 10.0.404 | 239 total; 228 PASS, 11 native-only SKIP, 0 failures/errors | PASS_PORTABLE |
| Windows Server 2022, NTFS, PowerShell 5.1, Python 3.12 | 239 PASS, 0 SKIP/failures/errors | PASS_NATIVE |

Native mixed tooling: **SDK 8.0.408**, **full MSBuild 17.14.60+43b635718 for .NET Framework**, existing **.NET Framework 4.8 reference assemblies**, compatible full CLR release **533509**. Actual absolute tool/reference paths and CLR release are retained in the native driver's result. Existing SDK 10.0.404 CLI/MCP/multi-target/repair/recovery/tamper checks also passed from the new installed package.

[L]: evidence/5c03210e875a45fade50d3266b390b401093cc96/Linux
[W]: evidence/5c03210e875a45fade50d3266b390b401093cc96/Windows

| Required observation | Linux | Native Windows | Evidence relative to profile root |
| --- | --- | --- | --- |
| Exact review non-SDK metadata (`TargetFramework(s)` empty, v4.7.1) | [PASS][L] | [PASS][W] | `legacy-automatic-tests/metadata/result.json`, two real broker restore/inspection processes, raw logs/status |
| Unsupported host never succeeds | [PASS][L]: explicit `legacy-dotnet-framework-requires-native-windows`, false gate | Native supported host | `legacy-automatic-tests/metadata/status.json` and driver result |
| Mixed solution: two SDK projects and one non-SDK .NET Framework project | Execution NOT_RUN: unsupported host | [PASS][W]: 3 executed/passed, 0 skipped | `legacy-automatic-tests/cli-recovery-repair/status.json` |
| Genuine legacy failure blocks full success; authorized repair needs fresh suite | Native execution NOT_RUN | [PASS][W]: first generation 2 SDK PASS / legacy FAIL, second generation 3 PASS; 6 distinct TRX | CLI status, `artifacts/*/0/trx`, real nonzero legacy VSTest result |
| Death after legacy build receipt, resume without replay | Native execution NOT_RUN; existing SDK recovery PASS | [PASS][W]: exit 73, resumed execution, 26 total processes across 2 generations | Driver `result.json` command receipts, interrupted/resume logs and CLI status |
| Enrolled supported MCP flow executes the same mixed inventory | Existing SDK MCP PASS | [PASS][W]: 3 executed/passed, 3 fresh TRX, 13 owned processes | `legacy-automatic-tests/mcp/status.json`, artifacts and driver result |
| Trusted executable, path authority, old SDK metadata/receipts | [PASS][L] | [PASS][W] | `tests.json`: `test_legacy_discovery.LegacyMetadata.*`, existing authority/recovery regressions |
| Rebuilt installed package, original SDK flow and transferable kit | [PASS][L] | [PASS][W] | `run.json`, `automatic-tests/`, `first-use/`, `distribution/.../RELEASE.json`, all command-log hashes |

The PASS links open the profile evidence root. [Regression sources](../../../tests/test_legacy_discovery.py), [classic fixtures](../../../tests/legacy_fixtures.py), [real installed driver](../../../scripts/legacy_test_discovery.py), [runtime](../../../packages/harness/src/harness/testing.py). `SHA256SUMS.json` protects all retained raw evidence, including native CRLF bytes. The Linux NOT_RUN cells describe unsupported native execution; they are not promoted to executed passes.

The build-only configuration still has no test project list or TRX path. With full MSBuild as the trusted build executable, the existing shared `dotnet` field supplies the SDK/VSTest host once. Schematic configuration excerpt (provider/limits/capture omitted):

```json
{"version":2,"dotnet":"C:\\Program Files\\dotnet\\dotnet.exe","recipes":{"build":{"kind":"build","argv":["C:\\Program Files\\Microsoft Visual Studio\\2022\\Enterprise\\MSBuild\\Current\\Bin\\MSBuild.exe","Application.sln","-restore","-m:1"],"result":{"format":"exit","path":""},"rerun_safe":true,"env":{}}}}
```

The task continues to authorize `"recipes":["build"]`. Select an installed full MSBuild compatible with the project's SDK/global.json; no production configuration or project is retargeted by Harness.
 Model decisions use a scripted HTTP provider; SDK/MSBuild/VSTest, .NET Framework test hosts, TRX, MCP, file operations and recovery are real. No private IPM/UMUH, live model or OpenCode desktop qualification is claimed.
