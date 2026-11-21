# Persistent Instructions R1: Review Fixes and Real-Host Validation

## Objective and baseline

Fix the two findings below in the existing Knowledge + Harness persistent-instructions implementation, add meaningful regression tests, and validate the supported real-host path when the required host/model is available. Implement the fixes; do not stop at a plan or simply rerun the existing passing tests.

Reviewed repository: https://github.com/Ermak-P/Knowledge-

Reviewed branch: `codex/persistent-instructions`.

Reviewed HEAD: `1cf9619f02bdaf68375ed438e1a0b61552a1ea21`. Product-source qualification is recorded against `5dfc4c523b1bc5cd5cf48b37f8366c6bb09cdb1d`; later reviewed commits retain evidence. Inspect actual current HEAD and any intervening changes rather than resetting or overwriting them.

Read applicable AGENTS.md, the reviewed parent assignment in `tasks/Knowledge-Harness-Persistent-Instructions-Codex-Task-1.md`, and:

- `reports/PersistentInstructions/ACCEPTANCE.md`
- `docs/P4/PERSISTENT-INSTRUCTIONS.md`
- `docs/P4/PERSISTENT-INSTRUCTIONS-LIVE-HOST.md`

The reviewer independently ran the 38 existing `test_persistent*.py` tests successfully. This establishes a baseline, not coverage of the findings. The real OpenCode/local-model trial was not available; no successful real-host acceptance was claimed.

Preserve the approved design: standalone Knowledge, shared root `~/.local/share/knowledge`, project `.knowledge`, existing lifecycle and provenance, bounded context, existing roles and permissions, Windows-native execution, and in-place Git work. No worktrees, unrelated refactors, broad permission changes, or remote model providers. Keep the existing branch; do not merge or publish a release merely to complete this assignment.

## R1-01 — CLI resume silently ignores current restrictions

### Evidence

At the reviewed revision, `packages/harness/src/harness/run_cli.py` declares global `--no-service-start` and `--format-input` arguments. The `run` branch passes them to `engine.start`, but the `resume` branch calls only `resume(args.root, args.run_id)`.

Source: https://github.com/Ermak-P/Knowledge-/blob/1cf9619f02bdaf68375ed438e1a0b61552a1ea21/packages/harness/src/harness/run_cli.py#L34-L35

A review probe invoked CLI `main()` with:

```text
harness-run resume --root <fixture> --run-id <saved-run> --no-service-start
```

With `run_cli.resume` replaced by a call recorder, the recorded call contained only `(root, run_id)` and no restriction. This is a CLI-handoff reproduction, not a claim that a real service was started by that probe. `--format-input` follows the same ignored-argument path.

### Required fix

1. Support the current no-start restriction when resuming a run. Persist/apply it under the normal execution lease before any resumed action, recovery attempt, or provider-driven continuation can perform an effect. Keep existing internal callers compatible.
2. Resume without a new option must preserve previously saved restrictions. An omitted flag is not permission to clear a prohibition. A current restriction takes precedence over a remembered startup grant.
3. Handle `--format-input` explicitly on resume. Apply supported overrides before the affected edit intent is created. For an edit already partially committed/journaled, preserve deterministic recovery: reject an incompatible new override with a clear error rather than silently ignoring it or re-encoding already committed bytes.
4. Reject options on command paths where they have no supported meaning, or document and implement their meaning. No silently accepted control flags.
5. Preserve run identity, source/config guards, host-session controls, action receipts, and durable recovery behavior. Do not bypass enrollment or reset the run merely to apply options.

### Regression evidence

- CLI-level test: the parsed no-start flag reaches resume handling; an incompatible or unsupported option fails explicitly.
- Resumable-run test: a saved applicable startup grant exists, a pending action needs an unavailable dependency, and resume is invoked with no-start. Observe zero startup calls and an explicit affected-action outcome.
- Resume without new options preserves an existing restriction.
- Supported format override on resume changes the intended output bytes while preserving the durable default. An incompatible override after edit-intent creation fails without additional writes.

Use existing fault/recovery fixtures where possible; exercise actual resume handling in addition to checking a mock's arguments.

## R1-02 — A misclassified negative statement can become a startup grant

### Evidence and its limits

At the reviewed revision, `knowledge/normalizer.py` verifies that `permission_quote` has a minimum length and occurs in the trusted user source. It does not independently reject a negative permission quote. `semantic_ingress.py` then uses the parsed authorization boolean to save the startup grant.

Sources:

- https://github.com/Ermak-P/Knowledge-/blob/1cf9619f02bdaf68375ed438e1a0b61552a1ea21/packages/knowledge/src/knowledge/normalizer.py#L145-L149
- https://github.com/Ermak-P/Knowledge-/blob/1cf9619f02bdaf68375ed438e1a0b61552a1ea21/packages/knowledge/src/knowledge/semantic_ingress.py#L134-L141

The reviewer supplied this genuine user text to real ingress and storage:

```text
Remember Kafka: you may not start the container. Only check readiness.
```

A **deliberately incorrect normalizer protocol double** returned `authorize_recovery=true`, `permission_quote="you may not start the container"`, and no unsupported conditions. The result was durably saved with `recovery_authorized=true`. The existing `DockerContract` double then recorded one startup call.

No real Docker effect occurred. This does not establish how frequently any actual model makes this mistake. It establishes that an erroneous but schema-valid model interpretation can promote an explicit denial into executable stored permission.

### Required fix

1. Make resource-specific startup authorization independently validated, rather than accepting a model boolean plus arbitrary source substring as sufficient evidence.
2. Define a bounded, inspectable recognition contract for positive startup grants and negative startup statements in the supported teaching languages (at least English and Russian). The model can propose a parse; it must not manufacture an affirmative grant from a denial, a quotation/example, or an observation about prior execution.
3. When authorization is negative, contradictory, ambiguous, or outside the validated recognition contract, preserve the user's instruction/intent but do not issue an executable startup grant. Ask a focused clarification only if a startup grant is needed and cannot be established. Do not require confirmation for every ordinary teaching message.
4. Preserve action-specific meaning: `start if stopped; never restart a running container` can authorize the start while forbidding restart. Do not solve the problem by rejecting every sentence containing `not`, `only`, or `не`.
5. Keep grants tied to the selected resource and current independent procedure/template allowlist. A different resource, old revoked grant, or broader quoted text must not restore permission implicitly.
6. Current no-start restrictions remain stronger than persistent grants. A malformed classification must not clear a current prohibition. Save and acknowledge the effective authorization truthfully.
7. Keep harmless readiness checks available where permitted; denying startup must not require deleting the user's rule or disabling all memory.

The implementation should state what is mechanically validated and what still depends on model interpretation. Do not claim perfect understanding of unrestricted natural language. A second prompt asking the same model to reconsider is not an independent authorization boundary.

### Required negative and positive tests

Inject intentionally wrong, schema-valid normalizer responses, not only correct responses:

- The exact negative example above returns `authorize_recovery=true`: no executable grant and zero startup calls.
- An English direct denial and Russian `не запускай контейнер` / `запуск контейнера запрещён` cannot become grants.
- A current prohibition cannot be classified into clearing itself.
- A quoted/example permission or a statement that an earlier start succeeded cannot authorize future startup.
- Explicit positive permission for the configured stopped container is accepted once and persists across a fresh process.
- `You may start it if stopped; never restart a running container` retains the allowed start and prohibited restart.
- Correcting the resource or revoking permission does not revive an earlier grant through an original-source quote.

Use actual ingress, transactions, persisted records, and the existing command/broker contract for focused regressions. Label all model/Docker doubles accurately.

## R1-03 — Close the remaining real-host validation boundary

The delivered status is `IMPLEMENTED / HOST VALIDATION PENDING`. Keep this status unless real evidence changes it. CI, Node hook-contract tests, separate Python processes, and Docker fixtures do not alone prove that a new OpenCode/local-model session captures and follows the taught instruction.

After fixing R1-01 and R1-02:

1. Identify the actual installed host/version and its supported plugin/MCP contract. The published `@opencode-ai/plugin` hook adapter and the documented OpenCode v2 MCP layout are distinct compatibility assumptions; verify the actual combination instead of assuming compatibility.
2. Check the installation order. If the plugin is configured in the enrolled project's `opencode.json`, include it before preview/apply enrollment; later edits otherwise invalidate the enrolled host-config digest. Make the guide and driver agree. Do not weaken that digest guard.
3. Use the existing isolated encoding driver and Kafka live guide. Execute the live trials if the host and local model are available. If they are absent, complete code fixes, tests, and runnable validation instructions without repeatedly reinstalling unrelated tools or pretending mocks prove the host path.
4. Use temporary memory roots and explicitly owned fixtures. Do not stop the user's real Kafka or alter real memory to manufacture a test condition. Do not start Docker Desktop/daemon under permission to start one container.

The central live Kafka trial:

1. In one real session, teach the applicable rule once and supply missing binding details once if needed.
2. Verify a durable receipt and terminate the teaching session.
3. In a new independent session, request only normal project tests. Do not paste Kafka, memory-tool, rule-ID, or retrieval reminders.
4. Observe the declared suite/dependency/procedure relationship, the matched record revision, one permitted start of the stopped owned container, Kafka protocol readiness, and the result of the original tests.
5. Repeat with ready Kafka, an unrelated suite, current no-start, and a running-but-unhealthy resource. Verify no unnecessary startup/restart or inappropriate remedy.

Recheck the encoding case in a new real session as well. Maintain the documented coverage boundary: native host shell/edit tools outside the Harness broker are not automatically covered. Do not expand host tool permissions to hide that limitation.

## Validation and delivery

First add focused regressions that fail against the reviewed behavior, then fix the implementation. Run:

```text
python -m unittest discover -s tests -p "test_persistent*.py" -v
```

Use the supported installed/runtime testing route for subprocess tests, and run the existing broader qualification appropriate to changed CLI, recovery, policy, packaging, and host paths. Record source SHA and the actual source being tested; old receipts do not qualify changed code. If Windows execution is available, include native Windows regression results. Otherwise mark it NOT RUN and retain the reproducible command/CI route.

Deliver source changes, regression tests, corrected docs/driver where needed, a commit/diff reference, and a concise Russian completion report with:

| Item | Required reporting |
|---|---|
| R1-01 | Reproduction before fix; persisted resume restrictions; effect/byte-level regression result. |
| R1-02 | Wrong-normalizer regressions; effective grants; zero forbidden effects; supported authorization-language boundaries. |
| R1-03 | Host/model versions, independent sessions, record IDs/revisions, and actual live results or the precise unavailable prerequisite. |
| Regression | Commands, test counts, failures/skips, source SHA, and distinction between real execution and doubles. |
| Coverage | Supported Harness paths, native-tool bypasses, and remaining limitations. |

Update the existing acceptance report/evidence in the repository without rewriting older failures as successes. Do not update unrelated improvement registers.

Use separate implementation and host-validation statuses: code fixes may be complete while host validation remains pending. Do not label the whole feature ACCEPTED until real A01/A02/A05/A17 and applicable negative checks are evidenced. The user should be able to tell exactly what is fixed and what still needs to run on their machine.
