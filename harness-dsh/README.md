# Harness for DeepSeek Harness (DSH)

Status: DSH-01 approved and implemented; native integration validation pending. DSH-02 onward require separate owner agreement.

## Boundaries

- DSH is the only target runtime for the new Harness. Use its native LLM calls, subagents, contexts, MCP, sessions, permissions and trajectory wherever they satisfy the requirements.
- This directory is isolated from the legacy Harness and Knowledge source/test trees. Do not copy their test suites or import their private implementation modules.
- Knowledge remains a separate service, accessible through standard MCP. No Knowledge changes, database migrations, installers, packaging/distribution automation or OpenCode adapters in this directory.
- Keep production code and dependencies minimal. No speculative abstractions, custom agent runtime, custom dashboard or background service.
- Any additional behavior, dependency or feature outside the agreed scope requires explicit owner approval before implementation. Prefer deleting unnecessary code over adding another abstraction.
- Work in-place, without Git worktrees. Never modify main or legacy code as part of this initiative.
- Run only the new directory's tests for this work. Do not trigger legacy or Knowledge test suites deliberately. Use targeted commands from this directory; document the exact command once the test framework is selected.

## Tasks (DSH-01 approved; DSH-02 onward pending approval)

| ID | Task | Acceptance criteria |
|---|---|---|
| DSH-01 | Minimal native DSH plugin and isolated tests | Plugin loads and exposes one observable test event; use public APIs, a minimal test setup and no custom provider. Verify how branch CI can be restricted without changing existing workflows; do not claim isolation until verified. |
| DSH-02 | Minimal engineering workflow | A user request can progress through plan, implementation, verification and independent review. Use native agents and contexts. Read-only requests need no development workflow; no manual task enrollment prerequisite. Exact role division to be agreed. |
| DSH-03 | Build and test verification | Agree a minimal .NET verification contract; discover relevant *Tests.csproj without fixed project lists; report real exit status, failures and absence of tests. Do not claim success when mandatory verification fails. Agree TDD and coverage policy before implementation. |
| DSH-04 | Minimal guard and bounded retries | Establish required non-bypassable checks for write/execute and completion using DSH public hooks/permissions. Stop repeated unsuccessful repair attempts. Agree specific restrictions and retry limits before implementation. |
| DSH-05 | Live visibility | Show current phase, active agent and operation via native DSH trajectory/events, including blocked/waiting states as supported. No extra LLM requests for status and no hidden secondary LLM loop. |
| DSH-06 | End-to-end acceptance | Verify a small .NET change in an isolated project using native DSH and local llama-server/Qwen on Windows; exercise success, failed tests, denied operation and cancellation. Verify existing Knowledge MCP can be used without changes; no Knowledge tests. |

Each task should be discussed and explicitly approved before coding. Implement in small commits with focused tests. A proposed feature is not an approved feature.

## Not included in the MVP unless separately approved

Universal runtime support, migration of old task state, automatic Knowledge capture, custom Knowledge commands, custom token accounting/budget dashboard, new database, persistent workflow recovery beyond native DSH behavior, custom compaction, custom MCP discovery, additional agents or telemetry infrastructure. Existing required quality and security guarantees must be discussed before any reduction; do not silently assume DSH equivalents.

## Planned layout

```text
harness-dsh/
  README.md
  src/       # only approved DSH integration and engineering logic
  tests/     # only tests for this new Harness
```

Add source, tests and minimal tool configuration only when needed. No placeholder implementation.

## DSH-01: passive native plugin

The plugin exports the standard Cordis `name`, `inject`, and `apply` fields.
It subscribes to DSH's public `session/event`, logs turn/step boundaries and
tool call/result events (only session ID, event type and tool name), and relies
on Cordis to dispose the subscription. No prompts, tool arguments, results,
LLM calls, agent creation, or workflow policy are added.

Reviewed upstream: [DSH 4b399c39](https://github.com/deepseek-ai/deepseek-harness/tree/4b399c39a6d1479cd84ca591b4d7c88e24d38a96).
Public references: [plugin loading](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/docs/user/develop/basic/index.md),
[effect cleanup](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/docs/cordis-tutorial/02-lifecycle-and-effects.md),
[session events](https://github.com/deepseek-ai/deepseek-harness/blob/4b399c39a6d1479cd84ca591b4d7c88e24d38a96/packages/core/session/src/index.ts).

### Focused tests

From this directory, with Node 22.16 or a compatible newer Node:

```sh
npm test
```

This runs one dependency-free unit test using a small context double. It does
not prove actual Cordis/DSH loading or disposal. No install or legacy tests needed.

For native integration use the Node version required by the reviewed DSH
checkout (Node ^24.22.3 or >=26.13.1), and install the test-only dependencies:

```sh
npm install
npm run test:native
```

The native test drives the actual DSH agent loop and tool dispatcher with a
scripted model adapter. It checks the observed event sequence, tool execution,
exact number of model requests, and absence of observer output after unload.
The test package versions match the reviewed upstream source manifests; npm
availability and dependency resolution have not been verified. No runtime
version equality check is performed by the plugin. No runtime dependencies
are bundled.

Validation recorded: `npm test` passed (1 test, Node 22.16.0).
Native test syntax checked; native execution is **NOT RUN** because this
environment cannot resolve registry.npmjs.org and lacks the reviewed DSH Node
version. Native DSH loading, event delivery and unload acceptance remain open.

### Manual smoke check

For a DSH source checkout that already runs its web profile, use an overlay
outside this project with the absolute path to the plugin:

```yaml
- insert:
    - id: harness-dsh
      name: '/absolute/path/to/Knowledge-/harness-dsh/src/index.ts'
```

Start DSH as documented by its upstream guide, e.g.
`pnpm dsh web --patch /absolute/path/to/overlay.yml`.
Confirm a loaded line in its terminal, run one ordinary read-only task that
calls a tool, check turn/step/tool event lines, and unload the plugin via the
native configuration lifecycle. The installed desktop/web host has not been
validated by this task.

### CI boundary

The five existing workflows were inspected at the branch baseline. Their
push filters do not match `feature/deepseek-harness`; no workflow files are
changed and no legacy workflow is requested. The P4 workflow does match PRs
targeting main, so do not open such a PR or dispatch legacy workflows for this
isolated development phase. Separate CI automation, if needed, requires an
explicit follow-up decision.
