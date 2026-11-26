# Harness for DeepSeek Harness (DSH)

Status: proposed MVP scope; implementation requires owner agreement on the tasks below.

## Boundaries

- DSH is the only target runtime for the new Harness. Use its native LLM calls, subagents, contexts, MCP, sessions, permissions and trajectory wherever they satisfy the requirements.
- This directory is isolated from the legacy Harness and Knowledge source/test trees. Do not copy their test suites or import their private implementation modules.
- Knowledge remains a separate service, accessible through standard MCP. No Knowledge changes, database migrations, installers, packaging/distribution automation or OpenCode adapters in this directory.
- Keep production code and dependencies minimal. No speculative abstractions, custom agent runtime, custom dashboard or background service.
- Any additional behavior, dependency or feature outside the agreed scope requires explicit owner approval before implementation. Prefer deleting unnecessary code over adding another abstraction.
- Work in-place, without Git worktrees. Never modify main or legacy code as part of this initiative.
- Run only the new directory's tests for this work. Do not trigger legacy or Knowledge test suites deliberately. Use targeted commands from this directory; document the exact command once the test framework is selected.

## Proposed tasks (approval pending)

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
