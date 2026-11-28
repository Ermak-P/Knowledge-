# Harness for DeepSeek Harness (DSH)

**Approved scope:** the owner approved the consolidated DSH-01–06 roadmap on 2026-11-26 and authorized mocked validation where the native environment is unavailable. See [the independent acceptance report](https://github.com/Ermak-P/Knowledge-/blob/9e3c58d4682aad81b01d16099e78a717281d0436/harness-dsh/DSH_ACCEPTANCE_REPORT.md) for current native evidence and deployment verdicts.

## Boundaries

DSH only, in-place, isolated under harness-dsh/. No changes to legacy Harness, Knowledge, main, installers, migrations, databases, custom model providers, agent loop, custom fingerprint engine or dashboard. Knowledge remains an independent MCP service. Do not execute legacy tests. Additional features require approval.

## Architecture

Alternative D: import the public verification library primitives, without activating the Goal-bound VerificationService or forking upstream. Task contracts are immutable, minted by the trusted host from Planning's structured output; the actual current user message is the basis. Origin is truthfully model-self-declared (Planning), not a claim of independent upstream intent capture. The host checks plan shape and file scope; final Reviewing checks original intent.

- `src/index.ts`: DSH-01 passive observer retained independently.
- `src/engineering.ts`: native tool entry points, direct native subagent activations, tool-result capture and monotonic execution guard. Native role presets are configurable; defaults use the installed standard preset, with role prompts and host guards. Native Workflow is not required for this sequential design.
- `src/lifecycle.ts`: task-scoped immutable contracts, run-local ordered in-memory evidence and capture failures, exact selectors, upstream oracles and CompletionGate, bounded repair and final review.
- `src/dotnet.ts`: Git-based project discovery, scoped paths, trusted native shell build/test, fresh TRX interpretation, real exit status, cancellation and timeout.
- `src/tdd.ts` and `src/reprolab/`: TDD controller and reused MIT pure RED/GREEN/regression functions. No worktrees.

Planning -> for each task (optional Testing/RED -> Coding -> Testing if applicable -> GREEN if TDD -> Verification/Task Gate) -> final revalidation -> independent Reviewing -> complete or targeted repair. Deterministic missing/stale checks run through the native shell service without extra model requests. Already-current canonical tool evidence is reused. Semantic ACs require a fresh independent verifier that actually read the cited target. Reviewing reads changed planned files and receives the original request, plan, and a bounded real Git diff. Only the host sets COMPLETED. Missing evidence, unavailable freshness, cancellation, infrastructure problems or exhausted repair attempts never become success. The default repair budget is three Coding attempts per task; at most one explicitly requested TDD refactor (followed by GREEN) per task.

The library contract identity uses the parent session as source basis; task/run identity and actual producer agent/session are recorded separately. Native tool results and direct trusted host checks are distinguished. The host assigns fresh reserved child ids before activation; model arguments cannot assign themselves a role or task. Capture uses the final immutable native tools/result event, not model summaries. No independent Goal lifecycle or permit replay is introduced. Evidence is intentionally in-memory for a live run; native sessions retain their own tool history, but interrupted Harness runs are not resumed automatically.

stalegreen supplies fingerprint computation/comparison, not its advisory claim-blocking plugin. Its unknown-fingerprint fallback is not accepted. The upstream verification library handles evidence binding and gates; compact host receipts preserve freshness and ordering without another receipt database. Ordinary acceptance covers tracked and nonignored paths. A bounded file-identity and timestamp check supplements the upstream Git-content snapshot and rejects hidden index entries. Checks are conservative: later changes invalidate earlier evidence until rechecked. This may cost time on large projects; the real IPM benchmark remains pending.

## Run the validation suites

Run these from `harness-dsh` with Git and a supported Node.js release. The .NET acceptance suite also needs .NET 10 and a native shell. Set `DSH_DOTNET_ACCEPTANCE=1` to include full native .NET repair workflows in `test:native`. Set `DSH_KNOWLEDGE_PYTHON` to the Python executable of an isolated Knowledge MCP installation to add the real MCP test.

```text
npm ci
npm test
npm run test:unit
npm run test:mocked
npm run test:library
npm run test:native
npm run test:acceptance
npm run test:provider
npm run test:coverage
```

From a checkout or ZIP download of the branch, run `npm ci --omit=dev --offline` in `harness-dsh` for production. All 28 production archives are included under `vendor/` with their integrity and redistribution records. Full development installation with `npm ci` uses the configured registry for development-only dependencies. See [Windows installation and upgrades](INSTALL-WINDOWS.md) for source ZIP installation, npm package installation, and release packaging. See [the hardened compatibility matrix](https://github.com/Ermak-P/Knowledge-/blob/9e3c58d4682aad81b01d16099e78a717281d0436/harness-dsh/DSH_ACCEPTANCE_REPORT.md#compatibility-matrix) for the previously qualified DSH releases.

### Native smoke (separate disposable profile/project first)

Use the standard native-tool executor preset, not PTC/code mode, unrestricted shell or a profile with third-party plugins that can bypass the host guard. Configure the plugin in a disposable DSH profile with [overlay.example.yml](overlay.example.yml), replacing both absolute paths. For a DSH source checkout use the normal upstream launcher, e.g.:

```powershell
pnpm dsh web --patch C:/Temp/harness-dsh-overlay.yml
```

Copy `fixtures/dotnet` to the disposable Git workspace and commit a baseline. No installer is provided. Open a native DSH session whose cwd is inside that repo, with the local llama.cpp model configured in DSH. Ask for a specific small behavior change and explicitly mention using harness_run. Verify:

1. Planning produces exact paths and acceptance criteria; no root writes outside harness_run.
2. Coding and Testing receive separate sessions with their role labels; forbidden shell/PTC/goal/nested delegation, out-of-scope paths, test/production cross-writes and unknown MCP tools are denied.
3. Native harness_run_check results and direct host checks yield actual evidence; task-level failures repair only the affected task; no missing or stale evidence passes.
4. Force a failing test, no discovered tests, a timeout and cancellation separately; inspect BLOCKED/CANCELLED and disposal; no success claim from the actual harness_run result.
5. Exercise a TDD task with an expected failing test, same test inputs GREEN, optional refactor and re-test.
6. Review actual native trajectory/child sessions and terminal logs; verify current task/phase and failure reason. Then explicitly test an existing Knowledge read-only MCP tool in the allowed list. Do not modify Knowledge.
7. Only after these pass, benchmark fingerprint budget and selected build/test commands in a disposable copy of the real .NET project (not the production checkout).

### Conservative restrictions and open items

- The plugin is deliberately restricted to the configured Git workspace and native standard tool execution. It does not claim an OS security boundary against arbitrary plugin code, external processes, or test/build code itself. PTC direct effects and Windows sandbox completeness need live qualification. Use native read/edit/write; apply_patch, arbitrary shell, dynamic subagents and mutating MCP tools are denied in scope. All role-specific writes must be listed by Planning and pass path/symlink and test-directory guards. Build-control and Git scope-control files require separate approval.
- The exact `mcp__knowledge__knowledge_capabilities` discovery tool is allowed for managed agents before and during a task, including when `readOnlyTools` is omitted or empty. This only permits an already-connected tool; it does not connect Knowledge, call it automatically, initialize a project or enable capture. Set `readOnlyTools` only to additional exact, reviewed native MCP public names (`mcp__server__tool`). Other Knowledge reads and all mutating MCP tools remain blocked unless explicitly allowed. The underlying DSH and Knowledge access policies still apply.
- .NET checks use installed dotnet, explicit existing solution/project and selected test projects; final gate revalidates all mandatory plan checks. No forced scan of ignored files or automatic full-repo suite beyond the agreed plan. Zero tests, skipped required tests, missing/invalid TRX, infrastructure/timeout/cancel are unverified. Older .NET Framework/MSBuild-only projects and unusual TRX formats need validation.
- Testing performs qualitative coverage and assertion review; measured coverage collection is not enabled automatically. TDD freezes planned test files and relevant test/build configuration, checks the expected failing name/message, and rejects changed frozen inputs. Existing baseline failures are not silently accepted as GREEN. No worktrees.
- Automatic acceptance only in this candidate; manual approval UI was optional and is not added. No automatic replay/recovery, aggregate token meter, external status service or dashboard. Main must report the actual harness_run status, not its own claim.
- Native shell checks write TRX to a temporary directory and use the native sandbox root grant when required. A missing grant or failed sandbox check blocks the task.
- Fingerprinting fails closed when a snapshot exceeds its budget (five seconds by default). Keep all build and test inputs in fingerprint scope and avoid external writers. There is no cross-process workspace lock. Semantic review is independent model judgement anchored to actual read calls, not a formal proof.
- Final review receives bounded HEAD diff and baseline-changed planned paths; a dirty pre-existing diff may include user edits. Full persistent audit/replay, measured coverage and a native Windows qualification are not claimed.

## Upstream references

- [DSH 4b399c39](https://github.com/deepseek-ai/deepseek-harness/tree/4b399c39a6d1479cd84ca591b4d7c88e24d38a96) — native subagent startActivation, tools.guard, tools/result, shell.execute(...).result(), sandbox policy.
- [dsh-verification f7828e9](https://github.com/bpc-oss/dsh-verification/tree/f7828e9b77095e570eefe221f7e48bfbf44a3944) — Apache-2.0 library exports and exact binder.
- [stalegreen 9e4cbca](https://github.com/pavangupta352/stalegreen/tree/9e4cbca4787558ea739c2e4ae9cc8314cdc9c173) — MIT public fingerprint library.
- [dsh-reprolab bdf332e](https://github.com/yuttfu/dsh-reprolab/tree/bdf332e37b19fbe50e2377ad8911e6d600d44d30) — MIT pure verifiers, retained notice.

## CI isolation

Existing workflows at the branch baseline do not match feature/deepseek-harness push. No workflows changed, no PR to main, no legacy test dispatch. Do not open a PR targeting main before reviewing its P4 workflow trigger.
