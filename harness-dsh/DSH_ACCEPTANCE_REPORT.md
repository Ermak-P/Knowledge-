# DSH integration acceptance

Validated on 2026-11-26 from `feature/deepseek-harness` at `9618f682a822422bac671cc1fadff05f7bd20a33`. The hardening branch is `codex/dsh-integration-hardening`. Changes are confined to `harness-dsh/`.

| Verdict | Decision | Basis |
|---|---|---|
| Implementation readiness | CONDITIONAL GO | The qualified native tool profile, task-scoped gate, and Linux SDK workflows pass. The workspace must contain its verification inputs inside the supported Git scope. |
| Native integration readiness | CONDITIONAL GO | The released DSH runtime and Cordis loader pass on the tested Linux configuration. The deployed profile, sandbox and UI still need live acceptance. |
| Windows deployment readiness | NO-GO | Windows-native PowerShell, SDK and sandbox acceptance remain outstanding. |
| Production readiness | NO-GO | Mandatory deployed-profile, Windows and live model acceptance remain open. |

## Confirmed defects and fixes

- The npm manifest named verification packages absent from the registry. It now uses the upstream release archives at a fixed source revision, with archive integrity in the lockfile. The archives declare peers for the older Goal plugin. The project npm config bypasses automatic peer installation and the manifest explicitly supplies the imports needed by the library and the test composition.
- Native DSH exposes session history through `snapshotEvents()`. The plugin now uses that API and permits DSH’s scoped `structured_output` call on assigned children. The guard resolves file paths against the execution session’s working directory. A native loader test exercises real tool admission, role handoff and registration removal.
- The verification release archive differs from the source tree at its distribution commit. Its selector binder still matches capture failures by evidence type. Recording all capture failures as `command_output` let stale successful file or test evidence survive a later interrupted check. Capture failures now carry the frozen criterion’s type. Repair also establishes a new evidence floor, even when the filesystem remains byte-for-byte unchanged.
- Final DSH tool results can be replaced by post-execution policy. A task check now binds only when the final result matches a host-produced receipt keyed by the native execution token. Results still carry the original task contract, producer session, and result ordering. Verification summaries exposed to tools and progress are bounded.
- The gate checks the workspace before and after command execution, while loading evidence, and after Reviewing. The supplemental snapshot checks file identity and modification/change times alongside stalegreen’s Git fingerprint and rejects unsupported index state and nonregular inputs. Explicitly ignored files cannot be selected as task inputs. The snapshot also rejects common ignored .NET inputs outside standard generated directories. A latest failed or unavailable result supersedes successful evidence.
- Verification now runs missing build checks before tests and repairs a confirmed compile failure before trying tests that depend on that build. Unknown process outcomes, cancelled jobs, missing results, invalid TRX and skipped tests remain unverified. The .NET invocation disables persistent build servers.
- Native cancellation reaches the role activation and command signal. The runtime test cancels a verification child, verifies child teardown and reopens the JSONL session in a fresh runtime. The restarted session requires a new request and evaluates new evidence.

Alternative D uses the public verification primitives while owning contracts and evidence per Harness task. The upstream Goal service is never activated. A single managed workspace runs one Harness lifecycle at a time. Concurrent native dispatch is tested at the evidence boundary. A restart discards the live evidence book, while native session history remains visible.

## Compatibility matrix

| Component | Exact exercised version or reference | Environment | Status | Qualification boundary |
|---|---|---|---|---|
| DSH core, native tool executor, subagent runtime and local spawn provider | `0.2.3-alpha.2` / tag `dsh-v0.2.3-alpha.2` / `4b399c39a6d1479cd84ca591b4d7c88e24d38a96` | Linux x64 | PASS — NATIVE | Cordis test composition using real runtime services and scripted model replies |
| Cordis and loader | `4.2.0-alpha.1` and `1.2.0-alpha.1` | Linux x64 | PASS — NATIVE | Absolute TypeScript plugin entry discovery, activation, unload |
| Other DSH prereleases and installed distributions | Target-dependent | — | NOT RUN | Evaluate each deployment version and preset |
| Verification and Evidence archives | `1.0.0`, fetched from `f7828e9b77095e570eefe221f7e48bfbf44a3944`. Archive contents last changed at `0217893de4bc499e4d55d3dbafa10dc5e7ecaed5` | Linux x64 | PASS — NATIVE | Actual library binding, oracle and gate tests. The checked-in archives and source were inspected independently. |
| stalegreen | Registry `0.1.1` at `b54c968aa4e72a5b893bb501fbc5acf5f5ec93ef`. Source reference `9e4cbca4787558ea739c2e4ae9cc8314cdc9c173` | Linux x64 / Git | PASS — NATIVE | No diff in `src/` between the two commits |
| Node.js | `24.22.3`, `26.13.1` | Linux x64 | PASS — NATIVE | Clean install and test commands listed below |
| .NET SDK | `10.0.404` | Linux x64 / native DSH Bash | PASS — NATIVE | Real multi-project build, tests and TRX |
| .NET SDK + DSH PowerShell | SDK 10 and deployed DSH | Windows | BLOCKED | Windows execution environment unavailable in this task |
| Knowledge MCP | `knowledge-p0 0.5.0rc1`, `mcp 1.30.0`, Python `3.12.14` | Real local stdio MCP and temporary DB | PASS — NATIVE | Read-only subset, with capture absent |
| OpenAI-compatible inference transport | DSH `dsh-llm-pi-ai 0.2.3-alpha.2` | Local HTTP/SSE fixture | PASS — NATIVE | Real adapter and native executor, scripted server replies |
| Qwen through llama.cpp | Deployment model and runner | — | BLOCKED | No configured local inference server or model was available |

## Acceptance matrix

Environment abbreviations are **L** for Linux x64 with Node 24.22.3, **L26** for Linux x64 with Node 26.13.1, and **W** for Windows. Native status applies to the named component. Scripted model output in a runtime test proves DSH behavior on that input. The provider fixture proves wire compatibility with the scripted endpoint.

Raw command transcripts and coverage summaries are under [evidence](evidence/). The clean installs exercised `137d717`. The final combined suite exercised `e0cdf2cf5deb315129177ec8090bf9b5a4b12e15`, which adds the ignored-input check. See `evidence/qualified-coverage.txt`. The final native smoke reran the suite with both Knowledge modes and the receipt negative control. Its three .NET workflows were already exercised in the clean combined run. See `evidence/native-final-smoke.txt`.

### P0 · native runtime and verification

| ID | Priority | Status | Method / environment | Expected | Actual | Evidence | Remaining risk / action |
|---|---|---|---|---|---|---|---|
| DSH-01 | P0 | PASS — NATIVE | Loader / L | Discover and activate the plugin by path | Real loader installed the engineering tool | `native-engineering.test.ts` | Qualify shipped overlay on deployed profile |
| DSH-02 | P0 | PASS — NATIVE | Loader and observer / L | Initialization, unload, handler disposal | Tool removed. Passive observer emitted no events after disposal | `native.test.ts`, `native-engineering.test.ts` | Live-profile unload during a process remains open |
| DSH-03 | P0 | PASS — NATIVE | Session and tool pipeline / L | Correct event names, schemas and context | Native turn, step, call and result events matched. Actual child roles submitted structured output | `native.test.ts`, `native-engineering.test.ts` | Exercise installed preset as documented |
| DSH-04 | P0 | PASS — NATIVE | Native deterministic dispatch / L | Distinct producer and session identities | Sequential and concurrent sessions had separate evidence and verdicts | `native-evidence.test.ts` | Uses controlled tool results. One lifecycle per workspace |
| DSH-05 | P0 | PASS — NATIVE | Native abort and failure / L | Stop child and surface terminal failure | Cancelled verifier terminated and DSH emitted ABORTED. Real build/test failures reached Repair | `native-engineering.test.ts` | Check actual production sandbox path |
| DSH-06 | P0 | PASS — NATIVE | JSONL reopen / L | Interrupt and restart without accepting stale work | Fresh context reopened original session. New missing-file verification blocked | `native-engineering.test.ts` | Live UI recovery remains open |
| DSH-07 | P0 | NOT RUN | Additional DSH releases | Match deployed API and behavior | One exact upstream release qualified | Compatibility matrix | Repeat on every deployment version |
| VER-01 | P0 | PASS — NATIVE | Upstream library / L, L26 | Mint immutable, task-specific contracts | Separate IDs and frozen selectors. Only exact evidence bound | `library.test.ts`, `lifecycle.test.ts` | No root Goal service in composition |
| VER-02 | P0 | PASS — NATIVE | Native dispatch / L | Attribute and isolate evidence | Separate owner, task, producer and session identities | `native-evidence.test.ts` | Full deployed adapter owns workspace exclusivity |
| VER-03 | P0 | PASS — NATIVE | Binder, oracles and gate / L | Missing, superseded, interrupted and stale evidence deny completion | Fresh success passed. Missing, failed and interrupted cases denied | `library.test.ts` | See stale-green scope below |
| VER-04 | P0 | PASS — NATIVE | Native repair and review / L | Repair invalidates old evidence and reruns checks | Native review repair crossed a new evidence floor | `native-engineering.test.ts` | The deployed TDD sandbox still requires qualification |
| VER-05 | P0 | PASS — NATIVE | Two tasks in one native parent / L | Both tasks use separate contracts and checks | Both passed. Earlier task reverified after later edit | `native-engineering.test.ts` | Workspace-wide freshness may re-run unaffected checks |
| VER-06 | P0 | PASS — NATIVE | DSH result replacement negative control / L | Replacing a failed check result cannot satisfy the contract | Final result claiming success was rejected because it did not match its execution receipt | `evidence/native-receipt.txt` | Native post-execution policy exercised in the test composition |

### P0 · stale-green

| ID | Priority | Status | Method / environment | Expected | Actual | Evidence | Remaining risk / action |
|---|---|---|---|---|---|---|---|
| STALE-01 | P0 | PASS — NATIVE | Real Git C# edit / L | Changed source invalidates pass | Gate blocked until captured again | `library.test.ts` | Inputs must be in workspace scope |
| STALE-02 | P0 | PASS — NATIVE | Real Git test edit / L | Changed tests invalidate pass | Gate blocked until captured again | `library.test.ts` | Same scope |
| STALE-03 | P0 | PASS — NATIVE | Real csproj and props edits / L | Changed project or build config invalidates pass | Both edits blocked old evidence | `library.test.ts` | External build inputs require deployment review |
| STALE-04 | P0 | PASS — NATIVE | Actual contract remint / L | Changed contract rejects old refs | Previous refs could not bind against revised contract | `library.test.ts` | Contract changes require fresh evidence |
| STALE-05 | P0 | PASS — NATIVE | Native review repair and library negative control / L | Repair consumes fresh evidence | New attempt blocked before new capture, including a no-edit control | `library.test.ts`, `native-engineering.test.ts` | No evidence replay between attempts |
| STALE-06 | P0 | PASS — NATIVE | Real binder isolation / L | Another task’s evidence cannot satisfy criteria | Exact selector under another identity denied | `library.test.ts`, `native-evidence.test.ts` | Concurrent dispatcher tests use controlled tool responses |
| STALE-07 | P0 | PASS — NATIVE | Aborted check and native verifier abort / L | Interrupted evidence cannot authorize | Earlier green was superseded. Native verification returned ABORTED | `library.test.ts`, `native-engineering.test.ts` | Installed UI cancellation remains open |
| STALE-08 | P0 | PASS — NATIVE | Successful capture followed by failure / L | Latest failure controls | Gate failed despite older success | `library.test.ts` | Release archive behavior is pinned and regression tested |
| STALE-09 | P0 | PASS — NATIVE | Native JSONL restart and old-ref injection / L | Fresh run cannot reuse earlier state | New request verified again. Copied refs rejected | `native-engineering.test.ts`, `library.test.ts` | A hard kill of the deployed launcher remains to be exercised |
| STALE-10 | P0 | PASS — NATIVE | Edit source after actual VSTest host starts / L | A changed snapshot rejects the run | SDK run returned unverified after the test host resumed | `dotnet-acceptance.test.ts` | Linux executor exercised |
| STALE-11 | P0 | PASS — NATIVE | Real edit during upstream blob load / L | Change during gate denies completion | Second fingerprint blocked candidate | `library.test.ts` | No cross-process lock or external state attestation |
| STALE-12 | P0 | PASS — NATIVE | Real Git hidden index entry / L | Hidden worktree input causes unavailable fingerprint | Assume-unchanged and an ignored C# source both produced unavailable fingerprints and blocked the gate | `library.test.ts` | Scope requires tracked/nonignored, regular workspace inputs |

### P0 · lifecycle scenarios

| ID | Priority | Status | Method / environment | Expected | Actual | Evidence | Remaining risk / action |
|---|---|---|---|---|---|---|---|
| LIFE-01 | P0 | PASS — NATIVE | Real DSH and file tools / L | First attempt passes | Completed after native review | `native-engineering.test.ts` | Model scripted |
| LIFE-02 | P0 | PASS — NATIVE | Real DSH and SDK / L | Compile failure, then repair | Compilation failure caused attempt two. Workflow completed | `native-engineering.test.ts` | Repeat on Windows |
| LIFE-03 | P0 | PASS — NATIVE | Real DSH, SDK and TRX / L | Test failure, then repair | Failed assertion caused attempt two. Workflow completed | `native-engineering.test.ts` | Repeat on Windows |
| LIFE-04 | P0 | PASS — NATIVE | DSH Reviewing / L | Rejection prevents completion | Terminal blocked | `native-engineering.test.ts` | Reviewer output scripted |
| LIFE-05 | P0 | PASS — MOCKED | DSH with forced shell rejection / L | Verification infrastructure failure blocks | Explicit blocked with no Reviewing | `native-engineering.test.ts` | Forced shell exception. Verify deployed sandbox and installation failure |
| LIFE-06 | P0 | PASS — NATIVE | Binder plus absent on-disk artifact / L | Missing required evidence prevents success | Binder blocked. Native run exhausted repairs with missing file | `library.test.ts`, `native-engineering.test.ts` | None in tested scope |
| LIFE-07 | P0 | PASS — NATIVE | Cancel native verifier / L | Verification abort terminates run | ABORTED, roles released | `native-engineering.test.ts` | Actual deployed UI stop pending |
| LIFE-08 | P0 | PASS — NATIVE | Native failed file check / L | Stop at configured cap | Stopped after two attempts | `native-engineering.test.ts` | None in tested scope |
| LIFE-09 | P0 | PASS — NATIVE | Cancel, dispose, reopen JSONL / L | No resumed pass | New user request blocked on actual state | `native-engineering.test.ts` | Hard-kill launcher recovery still open |
| LIFE-10 | P0 | PASS — NATIVE | Two tasks, one parent / L | Independent sequential verification | Both accepted after final revalidation | `native-engineering.test.ts` | None in tested scope |
| LIFE-11 | P0 | PASS — NATIVE | Parallel native dispatcher calls / L | Evidence does not cross task/session boundaries | One pass and one fail stayed isolated | `native-evidence.test.ts` | Controlled check tool. Concurrent lifecycle in same workspace is intentionally denied |
| LIFE-12 | P0 | PASS — NATIVE | Native refusal and cap / L | Return explicit blocked | Both paths terminated with specific reason | `native-engineering.test.ts` | None in tested scope |
| LIFE-13 | P0 | PASS — NATIVE | Native review rework / L | Make changes and reverify before completion | New capture and review required | `native-engineering.test.ts` | None in tested scope |
| LIFE-14 | P0 | PASS — NATIVE | Loader unload and real test-host cancellation / L | Handlers removed and no live cancelled test process | Loader removed registration. SDK check verifies the live PID stopped | `native.test.ts`, `native-engineering.test.ts`, `dotnet-acceptance.test.ts` | Cloud PID 1 may retain a zombie record. Unload during active work in deployed profile remains open. |
| LIFE-15 | P0 | PASS — NATIVE | DSH and real SDK TDD / L | Observe expected RED, GREEN, refactor, repeat GREEN | The native TDD workflow completed with new GREEN evidence after refactor | `native-engineering.test.ts` | Deployed sandbox and local model remain open |

### P0 · .NET and installation

| ID | Priority | Status | Method / environment | Expected | Actual | Evidence | Remaining risk / action |
|---|---|---|---|---|---|---|---|
| NET-01 | P0 | PASS — NATIVE | Build/test fixture / L | Discover both test projects. Build and run both | Real solution build and both test runs passed | `dotnet-acceptance.test.ts` | Windows pending |
| NET-02 | P0 | PASS — NATIVE | Real compile and assertion failures / L | Preserve nonzero status and distinguish failure types | Compile failed, and later a passing build preceded a failing TRX | `dotnet-acceptance.test.ts` | Windows pending |
| NET-03 | P0 | PASS — NATIVE | Real VSTest TRX / L | Parse executed, failed and skipped tests | Counters matched emitted results. Skip was unverified | `dotnet-acceptance.test.ts` | Additional frameworks and TRX shapes unqualified |
| NET-04 | P0 | PASS — NATIVE | Real no-results run and invalid XML injection / L | Missing and malformed TRX fail closed | Empty SDK result dir and deliberately malformed XML both produced unverified | `dotnet-acceptance.test.ts` | Malformed XML injected into parser |
| NET-05 | P0 | PASS — NATIVE | Real DSH executor / L | Enforce timeout and cancel running test | Neither authorized verification. Cancellation probes actual test-host PID | `dotnet-acceptance.test.ts` | Windows process-tree behavior pending |
| NET-06 | P0 | PASS — NATIVE | Path uses spaces and non-ASCII / L | Native shell handles path correctly | All production shell commands used the Unicode temp root | `dotnet-acceptance.test.ts` | Windows pending |
| NET-07 | P0 | BLOCKED | Windows-native tests / W | Repeat build, test, TRX and cancellation | No Windows runner available | [Local guide](DSH_LOCAL_VALIDATION.md) | Run with actual PowerShell and deployment sandbox |
| INST-01 | P0 | PASS — NATIVE | Clean `npm install` and `npm ci` / L | Resolve immutable archives and locked packages | Clean installation succeeded after manifest fix | `evidence/clean-24.txt` | Requires npm and upstream archive host access |
| INST-02 | P0 | PASS — MOCKED | `npm test` / L, L26 | Retain original 26 scenario assertions | Committed smoke and bundled cases passed | `evidence/clean-24.txt`, `evidence/clean-26.txt` | DSH services and libraries are doubled in these tests |
| INST-03 | P0 | PASS — NATIVE | `npm run test:library`, `npm run test:native` / L, L26 | Actual packages load and existing commands pass | Real library and dispatcher suites passed | `evidence/clean-24.txt`, `evidence/clean-26.txt` | Optional SDK and MCP scenarios enabled in L run |
| INST-04 | P0 | PASS — NATIVE | `npm ci --omit=dev` and package listing / L | Real verification, XML and stalegreen imports resolve and source is packaged | Runtime imports resolved. Package listing included all plugin files | `evidence/production-install.txt` | Deployment loads source from a standalone checkout |
| INST-05 | P0 | PASS — NATIVE | npm failure and recovery / L | Identify unavailable or incompatible dependency without claiming success | Baseline E404 and missing peer failures identified and fixed | This report and [manifest](package.json) | Keep registry and GitHub raw access for install |

### P1 · coverage, diagnostics, MCP and provider

| ID | Priority | Status | Method / environment | Expected | Actual | Evidence | Remaining risk / action |
|---|---|---|---|---|---|---|---|
| QA-01 | P1 | PASS — NATIVE | V8/c8 implementation coverage / L | Report statement, branch and function totals | Coverage captured for production TS and gate/lifecycle | [Coverage report](DSH_COVERAGE.md) | Detailed gaps listed there |
| QA-02 | P1 | PASS — MOCKED | Unit and mocked suites / L | Retain original cases and separate validation categories | Separate unit, mocked integration, native and acceptance scripts | `package.json`, `evidence/test-categories.txt` | Keep native evidence attribution in its own suite |
| QA-03 | P1 | PASS — NATIVE | Gate negative controls / L | Deny missing, stale, cancelled, superseded and cross-task inputs | Negative cases and valid controls exercised. Two intentional regressions were detected | `evidence/mutation-controls.txt` | Targeted mutation checks |
| OBS-01 | P1 | PASS — NATIVE | Native lifecycle output / L | Task, staged progress, build/test, gate, repair, review, blocker and outcome visible | Structured compact progress logged. Passive tracer opt-in | `evidence/clean-24.txt` | Confirm accessibility and rendering in deployed UI |
| OBS-02 | P1 | NOT RUN | Actual desktop/web UI | Review trajectory, result cards, and bounded context in installed profile | Native console verified. UI unexercised | [Local guide](DSH_LOCAL_VALIDATION.md) | Manual deployed-profile qualification |
| MCP-01 | P1 | PASS — NATIVE | Actual Knowledge stdio in native DSH / L | Discover read-only tools and retrieve context | Context obtained. Lifecycle completed | `native-engineering.test.ts` | Verify deployed server configuration |
| MCP-02 | P1 | PASS — NATIVE | Real tool denied by Harness guard / L | Exact allowlist preserves read-only policy. Candidate capture absent | Unlisted read rejected. No candidate tools. DB status unchanged | `native-engineering.test.ts` | Repeat with production policy and access control |
| MCP-03 | P1 | PASS — MOCKED | Native client with a controlled stdio MCP timeout / L | Role receives bounded tool failure and gate remains independent | Timeout classified as a tool error. Required file evidence still passed independently. | `evidence/mcp-faults.txt` | Repeat with deployed Knowledge transport |
| MCP-04 | P1 | PASS — MOCKED | Native client with fixture server disconnect / L | Transport loss surfaces as a tool failure | Client reported the call failed. Harness continued with its own checks. | `evidence/mcp-faults.txt` | Repeat with deployed Knowledge server loss |
| MCP-05 | P1 | PASS — MOCKED | Native client with malformed fixture response / L | Show protocol error without creating evidence | Invalid result content was rejected by DSH | `evidence/mcp-faults.txt` | Repeat through deployed transport |
| MCP-06 | P1 | PASS — MOCKED | Native client with server-side fixture denial / L | Propagate server denial without using it as acceptance evidence | DSH surfaced access denied. The native Knowledge read-only test separately verified unchanged database status. | `evidence/mcp-faults.txt` | Exercise actual deployment permission policy |
| MODEL-01 | P1 | PASS — NATIVE | Actual adapter and loopback HTTP/SSE / L, L26 | Parse valid tool call, reject schema-invalid input, disable reasoning | One valid call executed. Malformed arguments denied. Wire reasoning disabled | `provider.test.ts` | Scripted responses establish protocol behavior |
| MODEL-02 | P1 | PASS — NATIVE | Native subagent model inheritance / L | Delegate across role sessions | Scripted adapter used for all native role sessions | `native-engineering.test.ts` | Real local model delegation still pending |
| MODEL-03 | P1 | PASS — NATIVE | Actual retry policy and local HTTP fault fixture / L, L26 | Bound timeouts and retry, stop interrupted POST, detect context error | Recovered from HTTP 503 in one retry, surfaced context error and timeout, closed cancelled request | `provider.test.ts` | Exercise on deployed inference endpoint |
| MODEL-04 | P1 | BLOCKED | Real Qwen/llama.cpp endpoint | Complete local inference acceptance | No configured local endpoint and no model downloaded | [Local guide](DSH_LOCAL_VALIDATION.md) | Run with deployed model and runner |

## Known limits

The gate asserts a fresh snapshot of supported Git working-tree inputs. Dependencies outside the workspace, ignored resources other than rejected .NET inputs, generated artifacts, and externally mutable tools or services remain outside that proof. The deployment profile owns filesystem isolation. The upstream process service terminated the running test host in Linux. A container init process can retain the zombie entry, which requires reaping by the host. Windows process behavior and the deployed sandbox still require qualification. See [the local acceptance guide](DSH_LOCAL_VALIDATION.md).
