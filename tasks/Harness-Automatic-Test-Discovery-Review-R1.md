# Automatic test discovery — independent review R1

Date: 2026-11-20

Repository: https://github.com/Ermak-P/Knowledge-

Reviewed branch: `codex/automatic-test-discovery`

Reviewed HEAD: `9052b2f123513e8dbcf0c693234baa78c595d123`

Implementation revision: `c6a200b2558c94b58b83015c691d39442bb0a7c8`

Base: `5ec03763dac825adaca754828ac8decd821b1d5c`

## Verdict

The requested automatic discovery and verification flow works for the exercised SDK-style .NET projects. Runner v2 removes manual test recipes, recognizes both user filenames without case sensitivity and enforces complete automatic testing through the owned broker.

**Changes requested before approving generic mixed .NET/IPM use.** One confirmed P1 compatibility defect prevents legacy-format .NET Framework test projects from reaching test execution. There is no false success in that case, but a valid matching project makes the automatic suite unusable. The user's naming rule was not limited to SDK-style project files. The review did not inspect private IPM/UMUH files and does not assert that the two supplied filenames themselves use the legacy format.

## F1 — P1: legacy .NET Framework test projects have no supported framework resolution

Location: [testing.py lines 184–185](https://github.com/Ermak-P/Knowledge-/blob/9052b2f123513e8dbcf0c693234baa78c595d123/packages/harness/src/harness/testing.py#L184). Property inspection is constructed at [lines 99–103](https://github.com/Ermak-P/Knowledge-/blob/9052b2f123513e8dbcf0c693234baa78c595d123/packages/harness/src/harness/testing.py#L99).

The runtime queries `TargetFramework`, `TargetFrameworks`, `AssemblyName` and `TargetPath`, then requires a nonempty framework list from the first two properties. A normal non-SDK .NET Framework project uses `TargetFrameworkVersion`, for example `v4.7.1`. Its evaluated `TargetFramework` and `TargetFrameworks` are empty, even when the assembly name/path resolve successfully.

I reproduced this using the package built from the reviewed revision, the real broker, and the installed SDK 10.0.404. A minimal legacy `LegacyTests.csproj` was discovered successfully. Both broker-owned restore and MSBuild property inspection succeeded. Verification then raised `invalid-or-unresolved-test-frameworks` before launching any test operation.

Observed result:

```json
{
  "error": "invalid-or-unresolved-test-frameworks",
  "discovered": 1,
  "gate_ok": false,
  "commands": [
    {
      "phase": "inspect",
      "ok": true,
      "properties": {
        "AssemblyName": "LegacyTests",
        "TargetFramework": "",
        "TargetFrameworks": "",
        "TargetPath": ".../bin/Debug/LegacyTests.dll"
      }
    },
    {"phase": "restore", "ok": true}
  ]
}
```

The reproduction project needs no NuGet test adapter to expose this metadata defect:

```xml
<Project ToolsVersion="15.0"
         xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <Import Project="$(MSBuildExtensionsPath)/$(MSBuildToolsVersion)/Microsoft.Common.props"
          Condition="Exists('$(MSBuildExtensionsPath)/$(MSBuildToolsVersion)/Microsoft.Common.props')" />
  <PropertyGroup>
    <OutputType>Library</OutputType>
    <AssemblyName>LegacyTests</AssemblyName>
    <TargetFrameworkVersion>v4.7.1</TargetFrameworkVersion>
    <OutputPath>bin/Debug/</OutputPath>
  </PropertyGroup>
  <Import Project="$(MSBuildToolsPath)/Microsoft.CSharp.targets" />
</Project>
```

Run the current inspection command against that file:

```sh
dotnet msbuild LegacyTests.csproj -nologo -getProperty:TargetFramework,TargetFrameworks,AssemblyName,TargetPath
```

The metadata evaluation and broker refusal were executed on Linux. This reproduces the framework-resolution defect independently of Windows reference assemblies or test execution availability. It does not claim that Linux can run .NET Framework tests. Successful execution of the correction must be demonstrated on native Windows with the required existing tooling/reference assemblies.

## What passed and how it was checked

| Check | Independent observation |
| --- | --- |
| Source provenance | Computed source identity `7e87a2eb6ac2e321f995bcf3473665360be8e5fb5419eb71c1f4738addf9bc59`, identical to the source qualified in CI. |
| Package build/install | Built 0.5.0rc1 wheels and installed into an isolated prefix outside the checkout. Harness wheel SHA-256 `b351b776e4998147a4d9e0afe3c1e506f35132816ba3b24809e900c8980d4aa0`; Knowledge wheel SHA-256 `13db276d90d3250335e5f7182e1e37d73314791c283b9b933423f2579b43534b`. Both match the retained CI qualification. |
| Automatic CLI route | Executed the installed driver with real SDK 10.0.404. Three projects in different directories, both exact user filenames, Unicode/spaces, one project absent from the solution, and a multi-target project were exercised. Final result: four executed/passed tests, two verification generations, eight distinct TRX artifacts. |
| Failure and repair | The CLI scenario first produced a failing test, performed the scoped repair and required a fresh full passing suite. A newly added zero-test project prevented success; inventory drift refused resume. |
| Automatic MCP route | Independently executed the enrolled installed MCP flow with real SDK processes. Three discovered projects, three executed/passed tests and three distinct TRX artifacts. |
| Installed regressions | Ran all 236 discovered tests against the installed package. The initial independent driver omitted a multiprocessing main guard, causing the dedicated driver-reentry regression to fail. Corrected the review driver and reran that exact test successfully. Across the full run plus targeted rerun, 225 unique cases passed and 11 native-Windows-only cases skipped. The initial run itself was not a clean pass; this was a review-harness error, not a product finding. |
| Native Windows evidence | Queried actual GitHub Actions jobs for [run 44615158655](https://github.com/Ermak-P/Knowledge-/actions/runs/44615158655). Both verification jobs succeeded. Retained source-bound receipts report 236/236 PASS on native Windows and 225 PASS / 11 native-only SKIP on Linux. Native Windows was not independently rerun in this Linux workspace. |

Build/test/model decisions in the supplied installed acceptance driver use a scripted HTTP provider. .NET processes, test adapters, TRX, MCP transport and file operations are real. No live-model or live OpenCode qualification is claimed.

No product source files were modified during this review. The portable `--mcp-dir` wrapper is absent from this repository and was explicitly outside the amended GitHub task. Its absence is not a finding here.

## Focused correction for Codex

Fix F1 on the existing task branch and preserve the currently passing SDK-style behavior. Complete the following work autonomously, then commit and push the result for another review.

1. Support evaluated metadata for non-SDK .NET Framework test projects, including `TargetFrameworkVersion` and the corresponding identifier/profile where necessary. Resolve the actual executable assembly and appropriate native test invocation through the trusted toolchain. Do not simply inject an invented `TargetFramework` value and assume the existing SDK command works.
2. Keep suffix recognition authoritative for both SDK-style and legacy projects. Do not hide legacy matches, report them as passed without tests, restore a mandatory manual `recipes.test` branch, weaken TRX checks or retarget/convert user projects.
3. Preserve existing executable/path authority, inventory/source/config binding, process ownership, interruption/resume and strict complete-suite gating. Additional project-file write permissions are not part of this fix.
4. Add a regression for the exact metadata shape above, plus a real native Windows mixed solution containing an SDK-style test project and a non-SDK .NET Framework test project. Demonstrate passing execution of both, one real failure preventing completion, and fresh success after an authorized repair. Clearly identify any unavailable native prerequisite instead of replacing execution evidence with a mock.
5. Extend the short compatibility/setup documentation with the actual supported toolchain requirements and explicit diagnostics for missing prerequisites. Unsupported host/framework combinations must fail clearly and remain non-successful.
6. Rerun relevant existing automatic-discovery and recovery checks, rebuild/install the package and record the exact new source identity/commit. Return the branch URL, acceptance results and actual Windows evidence. Do not merge main.

The correction is complete when a matching legacy .NET Framework test project is tested successfully on a supported native Windows setup alongside the existing automatic SDK-style suite, without per-project test paths in runner configuration.
