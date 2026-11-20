# Harness — automatic .NET test project discovery

## Goal and finish line

Implement and commit this behavior in the GitHub repository `Ermak-P/Knowledge-`. For a configured .NET project, Harness automatically recognizes every eligible project whose filename ends with `Tests.csproj`, ignoring letter case. It runs all discovered test projects, validates their actual results and uses the aggregate as a mandatory completion gate for coding tasks. The user no longer maintains a `test` branch in the runner configuration or lists test projects in task files. The deliverable is a reviewable implementation pushed to a GitHub task branch, including tests, templates and documentation.

These real user examples MUST both be recognized:

- `IpmAzureCommon.UnitTests.csproj`
- `IpmAzureAutotests.csproj`

The second example makes case-insensitive suffix matching essential. Matching is based on the filename, independent of directory name, namespace, solution membership or the presence of `.UnitTests` specifically. Implement deterministic product behavior, supported by agent instructions. A prompt-only naming convention does not satisfy this task.

## Inputs, baseline and working rules

Repository: https://github.com/Ermak-P/Knowledge-

Start from the latest branch that includes the accepted integrated fixes. Inspect current main and `codex/integrated-fixes`, select the appropriate descendant and record the exact base commit. The previously inspected delivery was `bec0c98e8a33059edeed91208e1a64e43852294d`; do not assume main already includes it. Preserve the integrated recovery, authority, capture and verification fixes.

The repository is the implementation source of truth. No standalone ZIP attachment is required. Update its actual product sources and tracked configuration examples, agent instructions, tests and documentation. An archive-only patch or a replacement archive with no committed runtime changes does not satisfy this task.

Work autonomously through implementation, meaningful tests, self-review and fixes. Use ordinary checkouts and in-place execution. Preserve unrelated edits and data. Commit and push the completed work to a dedicated branch such as `codex/automatic-test-discovery`, then return its GitHub URL and exact revision. Do not merge into main or publish a release; the user controls those steps. Private IPM/UMUH source, local model files and a desktop session are not required.

## 1. Discovery contract

Recursively scan the resolved, authorized project root. Compare the basename with the suffix `Tests.csproj` using case-insensitive matching on both Windows and Linux. At minimum, recognize `FooTests.csproj`, `Foo.Tests.csproj`, `Foo.UnitTests.csproj`, the two user examples above and uppercase suffix variants. Do not classify `TestSupport.csproj`, `FooTests.csproj.bak` or a production project merely located inside a folder called `tests` as matches.

Include matching projects even when they are outside conventional test folders or absent from the selected solution. Include eligible untracked project files in the ordinary source scope. Do not require `IsTestProject` or package metadata to make a suffix match eligible. If a matching project cannot actually execute tests, report that failure explicitly.

Apply documented exclusions for build outputs and Harness/Knowledge/Git metadata, including `bin`, `obj`, `.git`, `.harness` and `.knowledge`. Avoid broad ignore rules that silently discard real application test projects. Stay inside the resolved project root, prevent symlink/junction escapes and avoid duplicate execution of the same file. Resolve path identity consistently on each platform and report ambiguous collisions. Sort the final project list deterministically.

Expose a read-only discovery/inspection result through the existing diagnostic surface or a small dedicated command. It must show the resolved root, matched project paths, count and relevant exclusions/errors. Discovery must not execute project code or start test processes.

Discover automatically for each new coding run. Adding another matching project before the next run requires no configuration changes. Record the inventory and its identity in durable run state and bind verification evidence to it. Before final completion, verify that the eligible inventory still agrees with the approved run state. A project added, renamed or removed during an active run must invalidate affected evidence and trigger the established revalidation/approval behavior. Resume must detect inventory drift rather than silently reuse a reduced or different set. Do not expand the agent's project-file editing permissions as a side effect of this change.

## 2. Remove manual test configuration

Remove `recipes.test` and equivalent per-project test recipes from the new normal .NET runner template. Do not move the same mandatory test command, project list, glob or TRX filename into another section. The built-in naming convention is sufficient.

Keep provider settings, limits, capture policy and the existing trusted build configuration. Resolve the trusted absolute `dotnet` executable from that configuration when unambiguous. If necessary, introduce one documented shared .NET executable setting, with a clear validation error for ambiguity. The user must not configure a second executable path just for tests when the build already identifies it.

Update task validation, generated tasks, role tools, CLI, MCP/companion entry points and final-gate checks. A coding task with a build recipe and no configured test recipe must be valid and must still run mandatory automatic testing. New task templates must not require a `test` entry referring to a nonexistent configured recipe. Do not require users to list generated test recipe names. The model cannot disable mandatory final testing by selecting only build or omitting a Testing delegation.

Use explicit schema versions if needed. Define compatibility for supported old runner/task files and already-started runs. Preserve the existing non-.NET explicit test recipe path where supported. Do not silently reinterpret old approved commands or discard active run authority. For legacy .NET configurations, provide an explicit, documented migration or a precise compatibility path. The default newly configured .NET workflow must contain no manual test branch.

## 3. Execution and actual result verification

Run the discovered projects through the existing owned-process broker. Execute sequentially by default to respect local resource limits. Pass each project path as a literal argv element, including paths with spaces or Unicode. Do not rely on shell glob expansion.

Each project execution gets a unique owned attempt/artifact directory and real machine-readable TRX output. Avoid cross-project and cross-attempt filename collisions. Reuse existing supervision, time limits, cancellation, source binding, receipts and retry/recovery rules. Automatic generation of commands must not bypass the trusted-executable and path checks.

Handle restore/build requirements correctly for projects outside the selected solution. Do not assume that building the solution built every discovered test project. In particular, do not add `--no-build` or `--no-restore` blindly. Document the actual behavior and respect the project's configured SDK and package sources. No automatic SDK installation or framework retargeting is part of this task.

Aggregate success requires every discovered project to pass under the existing verification policy. A zero exit code alone is insufficient. Missing, stale, malformed or mismatched reports, zero executed tests, failed tests and disallowed skipped/not-executed tests must prevent success. Preserve existing strict parsing checks and correctly account for supported multi-target projects without losing or overwriting reports.

Expose per-project status, executed/passed/failed/skipped counts, artifact references and aggregate status. Projects not reached because of cancellation, a budget limit or a failure must be recorded as not run. Never label a partial suite successful. No matching projects must produce an explicit non-success test-gate result for a coding task under this .NET convention. Read-only tasks remain free of build/test execution.

The current configuration has a limit on the number of user-defined recipes. Discovered projects must not consume that small recipe limit or be silently truncated to it. Exercise discovery/scheduling with more than 20 matching projects. Resource limits may stop a run explicitly, with pending projects visible.

## 4. Integration with agent roles and durable execution

Give Planning, Main and Reviewing bounded access to the discovered inventory and verification summary. Agent instructions must explicitly explain the suffix rule, including both user examples. Keep execution in the deterministic Building/Testing verifier path where automatic verification already exists. Testing verifies and reports results; existing authorized coding/repair flow handles source changes. This task does not redesign role ownership.

Preserve P4 item execution, bounded context, repair limits and final review. Intermediate items may use the existing narrower verification policy, but final success requires the complete current authorized test inventory plus the build and review gates. A repair invalidating earlier results must lead to fresh required verification. Old artifacts and stale summaries cannot satisfy the new gate.

Preserve companion enrollment and task/config/source identity checks, single-writer leases, interruption recovery and capture behavior. Adding automatic commands must not introduce a second execution path with weaker guards. Keep Knowledge independent and do not change canonical knowledge approval semantics.

## 5. Repository templates, documentation and packaging

Update the runner/task templates and configuration documentation tracked in the repository. Update the existing packaging/build sources so normal package generation includes the changed runtime and templates. Adjust version identities and tracked hashes where the release tooling requires it. Verify a package built from this branch outside the source checkout. Do not limit the implementation to the repository's development import path.

Where the repository already implements the portable installer, preserve these properties:

- Installation sources can be staged in `C:\Temp\Harness`.
- `--mcp-dir` remains a configurable absolute parent directory. For example, `C:\LLM\mcp` produces `C:\LLM\mcp\harness`.
- After installation, deleting the staging folder does not break Harness.
- Installation uses the bundled offline runtime packages and the documented Python prerequisite. Do not add a GitHub checkout or an external Python package download as an end-user installation requirement.
- Knowledge installation stays separate. Preserve the existing `harness_companion` MCP name and supported OpenCode registration contract.
- Keep the short Russian machine-installation and per-project-setup instructions separate. Project setup must explain the suffix rule, automatic execution and inspection of discovered projects. Remove the obsolete request to fill in a test project path or TRX path manually.

Commit all changed packaging sources and document the existing build command. Exercise the installed package outside the repository. If the portable installer exists, also verify operation after staging removal. If the standalone ZIP wrappers are absent from this repository, report that precisely; reconstructing an unrelated archive installer is outside this task. Producing or attaching a new ZIP is not a prerequisite for delivering the requested GitHub fix.

## 6. Required acceptance evidence

Use focused unit/integration tests and real .NET processes for the behavior being changed. A mocked process runner alone does not establish working test discovery and execution.

| ID | Required observable outcome |
| --- | --- |
| AT-01 | Both exact user filenames are found. Mixed-case suffixes work on Windows and Linux. Negative filename examples are excluded. |
| AT-02 | A clean config with no manual test branch and a task without per-project test names completes the actual build/test/review path through both CLI and the supported MCP entry point. |
| AT-03 | At least three real test projects in different directories run, including one absent from the solution. Unique fresh TRX evidence accounts for every project. |
| AT-04 | One failing project prevents completion even when the others pass. After an authorized repair, required fresh verification passes. |
| AT-05 | Zero discovered projects, zero executed tests, missing/malformed/stale TRX and disallowed skipped tests cannot produce a successful gate. |
| AT-06 | Adding a matching project before a new run includes it automatically. Inventory changes during an active/resumed run cannot reuse stale approvals or evidence. |
| AT-07 | More than 20 matches are discovered/scheduled without the user recipe limit truncating the suite. Cancellation/budget exhaustion reports all unfinished projects. |
| AT-08 | Paths with spaces/Unicode, generated-output exclusions, duplicate/path escape handling and owned artifact isolation behave correctly. |
| AT-09 | Interruption/resume and competing execution retain process ownership and existing retry semantics. New discovery does not grant extra source/config write permissions. |
| AT-10 | Supported legacy configuration and non-.NET test flows retain their documented behavior. Existing integrated-fix regressions remain passing. |
| AT-11 | A package built from the task branch runs the changed flow outside the checkout. Shipped .NET templates have no manual test branch. Existing portable installation behavior remains passing where that installer is present in the repository. |

Run relevant existing regression checks once, plus focused tests for changed behavior. Execute native Windows and Linux checks where runners are available. Clearly distinguish actual execution from static inspection or mocks. If a required environment is unavailable, finish the implementation and executable checks, identify the precise missing evidence and mark that acceptance item NOT_RUN. Do not describe unexecuted checks as passed.

## 7. Handoff

Return the pushed GitHub branch URL and exact commit, a short before/after configuration example, the exact inspection command and representative output containing the two user filenames. Include an acceptance table with test/evidence paths, important design decisions, migration steps and any remaining limitations. Commit the implementation, regression tests, updated templates and documentation together as reviewable repository work. State implementation readiness and tested platform qualification separately. Do not return only a plan, a text patch or an archive.

The user should be able to inspect the discovered projects, run Harness and receive trustworthy complete test results without maintaining test project paths in configuration. That is the acceptance boundary.
