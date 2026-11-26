# Validation — 2026-11-26

The results below describe the feature-branch baseline. See [DSH_ACCEPTANCE_REPORT.md](DSH_ACCEPTANCE_REPORT.md) for independent validation of the hardened branch.

This is an implementation candidate, not a native-qualified release. The owner explicitly allowed mocks for inaccessible environments. Production code has no fallback to test doubles.

## Executed in this session

- **19/19 lifecycle scenarios passed.** The exact committed lifecycle.ts source was evaluated in an isolated V8 engine; the test functions are committed in tests/lifecycle.test.ts. External libraries and native host were explicit doubles, with JSON clone substituted for the missing V8 host structuredClone. This validates local policy/state transitions, not real library behavior.
- **6/6 TRX scenarios passed.** The exact pure summarizeTrx/classifyTest functions were evaluated against parsed fixture objects, not a real XML parser or dotnet process.
- **1/1 native host composition scenario passed.** Exact engineering.ts and lifecycle.ts source evaluated in V8 with mocked native context, filesystem, Git, process check, abort and upstream library dependencies. Verified role restrictions, reserved child identity, actual capture listener path, disposal and final acceptance. The committed Node host test additionally exercises real temporary Git/filesystem when run locally.
- Prior DSH-01 dependency-free observer unit test passed in Node 22.16.0 during its original commit; not rerun here.

Executed total for this session: 26 mocked/pure scenarios, 26 passed. These are scenario counts, **not** an npm test or native test-run count.

## Pending on the owner's machine

| Command / scenario | Status | Why |
|---|---|---|
| npm test | NOT RUN as a complete Node suite | Remote private branch files were exercised through connector/V8; local Node filesystem suite not materialized here |
| npm install | NOT RUN | Registry DNS failed; package peer compatibility not verified |
| npm run test:library | NOT RUN | Actual third-party packages unavailable |
| npm run test:native | NOT RUN | Actual DSH runtime/test dependencies unavailable; current container Node 22.16 differs from reviewed DSH Node requirement |
| Native plugin load and actual subagent manager | NOT RUN | DSH host unavailable |
| Windows dotnet/TRX/XML parser, baseline RED/GREEN, cancellation, sandbox | NOT RUN | No dotnet/Windows; host and parsed-result tests provided |
| Actual stalegreen Git fingerprint on IPM | NOT RUN | Private workspace inaccessible |
| Native web/desktop trajectory and local Qwen | NOT RUN | Actual host/model inaccessible |
| Existing Knowledge MCP | NOT RUN | No production MCP connection |

The full native acceptance is blocked until these checks pass. The branch does not claim production readiness, and no existing production project or legacy/Knowledge tests were touched. Use README.md's isolated procedure.
