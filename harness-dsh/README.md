# Harness for DeepSeek Harness (DSH)

**Approved scope:** the owner approved the consolidated DSH-01–06 roadmap on 2026-11-26 and authorized mocked validation where the native environment is unavailable. Implementation candidate, **not native-qualified**. See [VALIDATION.md](VALIDATION.md).

## Boundaries

DSH only, in-place, isolated under harness-dsh/. No changes to legacy Harness, Knowledge, main, installers, migrations, databases, custom model providers, agent loop, custom fingerprint engine or dashboard. Knowledge remains an independent MCP service. Do not execute legacy tests. Additional features require approval.

## Architecture

Alternative D: import the public verification library primitives, without activating the Goal-bound VerificationService or forking upstream. Task contracts are immutable, minted by the trusted host from Planning's structured output; the actual current user message is the basis. Origin is truthfully model-self-declared (Planning), not a claim of independent upstream intent capture. The host checks plan shape and file scope; final Reviewing checks original intent.

- `src/index.ts`: DSH-01 passive observer retained independently.
- `src/engineering.ts`: native tool entry points, direct native subagent activations, tool-result capture and monotonic execution guard. Native role presets are configurable; defaults use the installed standard preset, with role prompts and host guards. Native Workflow is not required for this sequential design.
- `src/lifecycle.ts`: task-scoped immutable contracts, globally ordered in-memory evidence and capture failures, exact selectors, upstream oracles and CompletionGate, bounded repair and final review.
- `src/dotnet.ts`: Git-based project discovery, scoped paths, trusted native shell build/test, fresh TRX interpretation, real exit status, cancellation and timeout.
- `src/tdd.ts` and `src/reprolab/`: TDD controller and reused MIT pure RED/GREEN/regression functions. No worktrees.

Planning -> for each task (optional Testing/RED -> Coding -> Testing if applicable -> GREEN if TDD -> Verification/Task Gate) -> final revalidation -> independent Reviewing -> complete or targeted repair. Deterministic missing/stale checks run through the native shell service without extra model requests. Already-current canonical tool evidence is reused. Semantic ACs require a fresh independent verifier that actually read the cited target. Reviewing reads changed planned files and receives the original request, plan, and a bounded real Git diff. Only the host sets COMPLETED. Missing evidence, unavailable freshness, cancellation, infrastructure problems or exhausted repair attempts never become success. The default repair budget is three Coding attempts per task; at most one explicitly requested TDD refactor (followed by GREEN) per task.

The library contract identity uses the parent session as source basis; task/run identity and actual producer agent/session are recorded separately. Native tool results and direct trusted host checks are distinguished. The host assigns fresh reserved child ids before activation; model arguments cannot assign themselves a role or task. Capture uses the final immutable native tools/result event, not model summaries. No independent Goal lifecycle or permit replay is introduced. Evidence is intentionally in-memory for a live run; native sessions retain their own tool history, but interrupted Harness runs are not resumed automatically.

stalegreen supplies fingerprint computation/comparison, not its advisory claim-blocking plugin. Its unknown-fingerprint fallback is not accepted. The upstream verification library handles evidence binding and gates; compact host receipts preserve freshness and ordering without another receipt database. All nonignored Git paths are included (no extra fingerprint ignore list for ordinary acceptance). Checks are conservative: later changes invalidate earlier evidence until rechecked. This may cost time on large projects; the real IPM benchmark remains pending.

## Approved roadmap and implementation status

| ID | Implementation | Acceptance |
|---|---|---|
| DSH-01 | Passive native plugin | Prior isolated observer test passed; native loading/disposal pending |
| DSH-02.1 | Library PoC, two task contracts, exact evidence, supersede and freshness | Mock scenarios passed; real imports and native dispatcher tests provided, NOT RUN |
| DSH-02.2 | Contracts, evidence, freshness, minimal guard | Implemented; host/core doubles exercised; native qualification pending |
| DSH-02.3 | Direct native subagents, sequential roles and bounded repair | Implemented; mocked native host scenario passed |
| DSH-02.4 | Merged into 02.2 | Freshness fail-closed in mock tests; real large Git fingerprint pending |
| DSH-02.5 | Final gate + independent Reviewing; targeted repair | Implemented, mocked scenarios passed |
| DSH-03.1 | Discover tracked/untracked nonignored *Tests.csproj, build, fresh TRX, classification | Implemented; pure TRX scenarios passed; real filesystem/shell/Windows tests pending |
| DSH-03.2 | Testing role, test-only write scope, coverage/test quality assessment | Implemented with structured agent results; actual quality/quantitative coverage pending |
| DSH-03.3 | RED/GREEN, optional refactor/retest, frozen test inputs, regression | Implemented using ReproLab pure functions; native .NET validation pending |
| DSH-04 | Monotonic native guard + per-task repair cap | Implemented for allowed native calls; actual sandbox/PTC boundary pending; no speculative extended detector |
| DSH-05 | Native child labels/trajectory and deterministic terminal phase logs | Implemented; inspect live UI, especially direct host checks |
| DSH-06 | Isolated native acceptance procedure | NOT RUN: Windows/local Qwen/Knowledge MCP inaccessible |

## Morning verification

From this directory only, on a machine with compatible Node (the reviewed DSH source requires Node ^24.22.3 or >=26.13.1), Git, and .NET SDK:

```powershell
git switch feature/deepseek-harness
git pull --ff-only
Set-Location harness-dsh
npm test
npm install
npm run test:library
npm run test:native
```

The first command suite is dependency-free: Node test runner, Git and filesystem only, with explicit test-only doubles. It never imports external packages through production apply(). The second suite imports actual upstream packages; native suite uses actual DSH agent loop/dispatcher with scripted model and a controlled tool result. If npm reports incompatible peers or missing packages, STOP and investigate; do not silently downgrade DSH, activate the upstream Goal plugin, or substitute mocks in production. Package versions are taken from the inspected manifests; registry resolution has not been verified. No runtime version-equality gate is implemented. No lockfile could be generated in the offline environment.

### Native smoke (separate disposable profile/project first)

Use the standard native-tool executor preset, not PTC/code mode, unrestricted shell or a profile with third-party plugins that can bypass the host guard. Configure the plugin in a disposable DSH profile with [overlay.example.yml](overlay.example.yml), replacing both absolute paths. For a DSH source checkout use the normal upstream launcher, e.g.:

```powershell
pnpm dsh web --patch C:/Temp/harness-dsh-overlay.yml
```

In the disposable Git workspace create a small .NET solution and an existing test project ending in Tests.csproj, add appropriate project references, ignore bin/obj, and commit a baseline. No installer is provided. Open a native DSH session whose cwd is inside that repo, with the local llama.cpp model configured in DSH. Ask for a specific small behavior change and explicitly mention using harness_run. Verify:

1. Planning produces exact paths and acceptance criteria; no root writes outside harness_run.
2. Coding and Testing receive separate sessions with their role labels; forbidden shell/PTC/goal/nested delegation, out-of-scope paths, test/production cross-writes and unknown MCP tools are denied.
3. Native harness_run_check results and direct host checks yield actual evidence; task-level failures repair only the affected task; no missing or stale evidence passes.
4. Force a failing test, no discovered tests, a timeout and cancellation separately; inspect BLOCKED/CANCELLED and disposal; no success claim from the actual harness_run result.
5. Exercise a TDD task with an expected failing test, same test inputs GREEN, optional refactor and re-test.
6. Review actual native trajectory/child sessions and terminal logs; verify current task/phase and failure reason. Then explicitly test an existing Knowledge read-only MCP tool in the allowed list. Do not modify Knowledge.
7. Only after these pass, benchmark fingerprint budget and selected build/test commands in a disposable copy of the real .NET project (not the production checkout).

### Conservative restrictions and open items

- The plugin is deliberately restricted to the configured Git workspace and native standard tool execution. It does not claim an OS security boundary against arbitrary plugin code, external processes, or test/build code itself. PTC direct effects and Windows sandbox completeness need live qualification. Use native read/edit/write; apply_patch, arbitrary shell, dynamic subagents and mutating MCP tools are denied in scope. All role-specific writes must be listed by Planning and pass path/symlink and test-directory guards. Build-control files require separate approval.
- Set readOnlyTools only to exact, reviewed native MCP public names (mcp__server__tool). No automatic Knowledge capture.
- .NET checks use installed dotnet, explicit existing solution/project and selected test projects; final gate revalidates all mandatory plan checks. No forced scan of ignored files or automatic full-repo suite beyond the agreed plan. Zero tests, skipped required tests, missing/invalid TRX, infrastructure/timeout/cancel are unverified. Older .NET Framework/MSBuild-only projects and unusual TRX formats need validation.
- Testing performs qualitative coverage and assertion review; measured coverage collection is not enabled automatically. TDD freezes planned test files and relevant test/build configuration, checks the expected failing name/message, and rejects changed frozen inputs. Existing baseline failures are not silently accepted as GREEN. No worktrees.
- Automatic acceptance only in this candidate; manual approval UI was optional and is not added. No automatic replay/recovery, aggregate token meter, external status service or dashboard. Main must report the actual harness_run status, not its own claim.
- Native shell checks write TRX to a temporary directory, using the existing native sandbox root grant if required, never a wider permission mode. Windows may not honor extra roots; failure blocks the task.
- Fingerprint is bounded (default 5 seconds, configurable), unavailable is fail-closed. Git-ignored inputs and concurrent external changes require environmental discipline; there is no cross-process workspace lock. Semantic review is independent model judgement anchored to actual read calls, not a formal proof.
- Final review receives bounded HEAD diff and baseline-changed planned paths; a dirty pre-existing diff may include user edits. Full persistent audit/replay, measured coverage and a native Windows qualification are not claimed.

## Upstream references

- [DSH 4b399c39](https://github.com/deepseek-ai/deepseek-harness/tree/4b399c39a6d1479cd84ca591b4d7c88e24d38a96) — native subagent startActivation, tools.guard, tools/result, shell.execute(...).result(), sandbox policy.
- [dsh-verification f7828e9](https://github.com/bpc-oss/dsh-verification/tree/f7828e9b77095e570eefe221f7e48bfbf44a3944) — Apache-2.0 library exports and exact binder.
- [stalegreen 9e4cbca](https://github.com/pavangupta352/stalegreen/tree/9e4cbca4787558ea739c2e4ae9cc8314cdc9c173) — MIT public fingerprint library.
- [dsh-reprolab bdf332e](https://github.com/yuttfu/dsh-reprolab/tree/bdf332e37b19fbe50e2377ad8911e6d600d44d30) — MIT pure verifiers, retained notice.

## CI isolation

Existing workflows at the branch baseline do not match feature/deepseek-harness push. No workflows changed, no PR to main, no legacy test dispatch. Do not open a PR targeting main before reviewing its P4 workflow trigger.
