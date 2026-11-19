# Knowledge + Harness - P4 execution task

Version: 1.0 | 2026-11-16

## 1. Mission

Implement **P4: bounded agent work, durable coordination, deterministic verification and controlled repair** in the existing Knowledge + Harness product.

This is an implementation assignment. Deliver working installed software, backward compatibility, executed tests and a complete review packet. Do not finish with an architecture proposal, prompt collection or unexecuted scripts.

The primary objective is **preserving correctness over long tasks without allowing Main or Coding to accumulate an unbounded conversation**. Reduce unnecessary model calls where the work is deterministic. Treat lower latency and lower total token use as hypotheses to measure, not guaranteed consequences of adding agents.

The intended default architecture for new P4 runs is:

- Main is the only primary coordinator. It delegates bounded work and maintains a durable work ledger.
- Coding is the source writer for an authorized work item, including its necessary tests.
- Build and test execution are trusted runtime operations with real receipts, not mandatory LLM conversations on the successful path.
- Reviewing is a separate read-only model context and remains a mandatory final gate for coding work.
- Planning and read-only diagnosis are invoked when needed; a simple task does not require ceremonial model calls to every role.
- Fresh contexts, concise handoffs, finite repair budgets and actual source-bound verification replace indefinite conversation growth.

Do not add a permanent TestAuthor role, mandate universal TDD, add parallel source writers or expand the optional MCP/service inventory as part of this task.

## 2. Repository, accepted baseline and working authority

Repository: <https://github.com/Ermak-P/Knowledge->.

Accepted P3 delivery revision: `3dbaa8806e30c083761c9ac8a07a233a03e2866b`.

Accepted P3 source identity: `041f1ee4e1c533be7addd41c88a3b314609b13733a67f33f970bee2a8e02e808`.

Accepted P3 distribution:

`reports/P3/runs/c72e6b4fcb41419cb5ff40a61a506466/distribution/knowledge-harness-0.3.0rc1.zip`

Distribution SHA-256: `cf108d6ba7b49b42c8a81831abd9f72cdc999552cbd500cbef07ada9b0349338`.

Start an ordinary `p4` branch from updated `main`. Verify accepted P3 ancestry, or equivalent accepted source content after a squash merge. Record the exact starting commit and preserve legitimate later changes. Do not require the old `p3` branch to exist and do not start from an earlier uncorrected 0.3.0rc1 package with the same version string.

Read the existing contracts, P0-P3 tasks, correction regressions and active code before designing the change. Relevant starting points include:

- `packages/harness/src/harness/engine.py`: frames, provider requests, role completion, context assembly and recovery.
- `packages/harness/src/harness/runtime.py`: role/tool policy, configurations, source snapshots, durable state and limits.
- `packages/harness/src/harness/tools.py`: broker authority, patch intents, protected paths, processes, artifacts and review receipts.
- `packages/harness/src/harness/provider.py`: actual HTTP protocol, request limits and uncertain outcomes.
- `packages/harness/src/harness/capture.py`, `comparison.py`, `companion.py` and platform backends.
- Knowledge lifecycle, source freshness, coordination and maintenance implementation.
- `scripts/verify_p3.py`, installed-product rehearsal, packaging/evidence scripts and native Windows CI.

Known starting behavior: separate contexts per delegation already exist; the current engine nevertheless requires completed Planning, Coding, Building, Testing and Reviewing agents for every coding task. Context assembly trims old history chunks, Main receives child summaries, and the engine already records actions/requests/gates. Reuse these mechanisms where sound. Merely renaming roles, lowering byte caps or documenting existing isolation is not P4.

Work autonomously through design, implementation, meaningful tests, self-review and repairs. Make routine reversible decisions without requesting step-by-step approval. Use the whole assignment as one coherent delivery; the user expects an external review followed by at most one or two focused correction rounds.

Use ordinary checkouts and **in-place execution only; no Git worktrees**. Preserve user edits. Do not reset/clean away changes or discard stores/journals to recover. Use controlled temporary projects for destructive/interruption tests.

Commit the completed product work on the task branch and report its exact revision. Do not merge into main, delete branches, deploy to IPM/UMUH, publish a release/package, change global OpenCode settings, alter repository administration/secrets/billing or provision paid infrastructure. The user controls merge and production adoption. No desktop UI or access to private projects/models is required.

## 3. Concrete finish line

From a clean P4 package installed outside the implementation checkout, a user must be able to:

1. Submit a bounded coding task or a larger task that Main decomposes into a small ordered plan of authorized work items.
2. Execute work items sequentially, using fresh Coding contexts and durable handoffs rather than inherited transcripts.
3. Have the runtime execute configured build/test recipes automatically and evaluate their real structured results without requiring Building/Testing provider calls on a normal successful path.
4. Require an independent final Reviewing context before reporting successful coding completion.
5. Continue a long task across context rotations or an interruption without losing requirements, weakening scope, replaying an edit/process or resetting aggregate budgets.
6. Stop a repeated ineffective repair loop, perform bounded diagnosis/replanning if appropriate, and return an actionable non-success state if unresolved.
7. Inspect the plan, work ledger, changes, evidence, context sizes and complete cost/attempt accounting using documented CLI/status/metrics commands.
8. Reopen accepted P3 data and run compatible legacy operations without a silent policy or authority change.

A fresh P4 example/default must exercise the new behavior. An experimental switch that leaves every ordinary new run on the unchanged five-agent path is insufficient. Compatibility can preserve the old path for old inputs/runs; it must not silently reinterpret them as broader P4 authority.

## 4. Scope and design decisions

Before implementation, write `docs/P4/DESIGN.md` with the selected state machine, schemas, authority model, compatibility choices, context policy, repair policy and short examples. Then implement it in the same assignment; do not pause for design approval.

Use the smallest coherent design. A small ordered work plan with explicit dependencies is sufficient; do not build a general distributed workflow platform. Keep default execution sequential for a local provider with one inference slot. A single model can serve all model roles.

P4 changes orchestration, not the Knowledge product's purpose. Keep Knowledge independently installable. Do not implement automatic canonical approval, semantic contradiction resolution, root relocation or production migration under this task.

## 5. Bounded work items and durable coordination

Implement versioned, validated records for the work plan, work items, context epochs and handoffs. You may choose their exact API/storage shape, but their semantics must be explicit and inspectable.

Each work item must bind at least:

- Stable identity, parent task and dependencies/order.
- A concrete objective and acceptance criteria derived from the authorized task.
- An authorized write scope that is a subset of the outer task scope, plus relevant existing-test exceptions.
- Configured verification requirements, source/config identity and evidence references.
- Status, attempts, context epochs and unresolved issues.
- A bounded handoff describing changes, checks, remaining work and relevant artifact identifiers.

Main may propose decomposition, but the runtime validates it. Main/model output cannot expand writable paths, test-edit authority, recipes, credentials, resource budgets or accepted completion criteria. Do not require a user to author a large work-plan document for every simple task; provide a narrow validated one-item route.

Maintain the coordinator's work ledger durably. It must be sufficient to rebuild a correct bounded Main context without concatenating child conversations. Source changes and verification results come from broker receipts, not assertions in a model summary.

Only one work item may mutate project source at a time. Moving between work items retains the project execution/ownership guarantees. An intermediate completed work item is historical progress, not proof that the final project still passes all checks.

Plan changes retain history and invalidate affected evidence. They must not bypass aggregate limits by renaming a failed item or creating a new plan. Cyclic/oversized plans, unauthorized paths and invalid dependencies refuse before effects.

## 6. Context lifetime, checkpoints and bounded retrieval

### 6.1 Fresh contexts

Give every new Coding work item a fresh frame/context identity. A repair or continuation may start a new epoch of that item with a new context identity and a concise validated handoff. Never inherit another item's full transcript by default.

Main's ordinary requests must use the authorized task, bounded ledger, pending decision and selected evidence. Child transcripts and complete logs are not automatically fed back into Main. Planning/diagnosis/review contexts have the same explicit isolation rules.

### 6.2 Rotation before exhaustion

Provide explicit hard request/input limits and a documented rotation/continuation policy. Count the actual serialized provider request, including tool schemas and runtime policy; do not measure only the visible message text. Keep bytes, estimated tokens and provider-reported tokens distinct.

When a context reaches the continuation threshold, checkpoint at a safe action boundary and create a fresh epoch from durable facts. Runtime authority, original requirements, unresolved findings and required checks must survive. Do not treat silently dropping old messages as successful context preservation.

If the irreducible task/policy/checkpoint cannot fit, stop before the HTTP call with an actionable split/replan result. Do not remove security instructions, silently drop acceptance criteria, send an oversized request or claim successful completion.

Rotation must not reset run/work-item request limits, repair counts, token accounting, elapsed budgets or uncertain-outcome state. Never rotate around an in-flight provider/tool operation as an excuse to retry it.

### 6.3 Handoff integrity and artifacts

Store model-authored narrative as untrusted bounded data. Validate any referenced action IDs, file hashes, source/config bindings and verification statuses against the journal. A handoff that says 'tests passed' is not a gate receipt.

Preserve complete available bounded logs/receipts as artifacts. Return concise structured diagnostics plus owned artifact references to model contexts. Support bounded excerpt/range retrieval for deeper investigation, with path/identity/size checks. Do not solve overflow by discarding the only useful failure evidence or truncating tool-call protocol pairs into an invalid conversation.

Do not introduce uncounted background summarization calls. If any model call is used for a checkpoint, count it and retain deterministic reconstruction of authority. Prefer deterministic ledger rendering over another mandatory summarizer role.

## 7. Deterministic build/test execution

Replace the **mandatory model conversations** for successful build/test stages in the new policy with runtime-scheduled execution of existing trusted recipes.

Requirements:

- Use the accepted broker/platform/process ownership path, durable intents, cancellation, timeouts, artifacts and result parsers. Do not create a second unsafe subprocess path.
- The runtime invokes only recipe IDs already authorized for the task/work item. Models cannot provide argv/env/output paths or raw shell commands through a new verification tool.
- Main may request verification through a narrow runtime operation, or the engine may schedule it after a Coding item; this does not give Main direct shell, arbitrary recipe or patch authority.
- Record that the invocation was a deterministic verifier event, including its authorizing task/item and source/config inputs. Do not invent a Building/Testing model session to satisfy old counters.
- Parse real test results. Missing/malformed reports, zero executed tests where a nonempty suite is required, failed/skipped mandatory checks and stale artifacts must not count as passing.
- Preserve protection of executable/recipe input paths and explicitly authorized existing tests across alternate native path spellings.
- If the source or relevant configuration changes after verification, invalidate affected gates. Intermediate checks may guide progress, but successful overall completion requires the final required checks on the final source/config state.
- Cache/reuse a verification result only when its complete supported authority/input identity still matches. When unsure, invalidate it. Do not broaden legacy cache claims.

A small successful new-policy coding task must not require separate Planning, Building or Testing HTTP model calls solely to complete role attendance. Coding may write implementation and authorized tests in one bounded item. Test-design specialists and TDD remain optional future/pilot choices, not new mandatory infrastructure.

## 8. Independent review and honest completion

Keep a separate read-only Reviewing context for coding completion. Supply the original acceptance criteria, final changes/diff, current source/config identity and actual verifier evidence. Do not automatically preload the author's full reasoning or conversation; the reviewer can request bounded additional evidence.

The review tool must still be runtime-authorized and source-bound. Main/Coding cannot fabricate or reuse an approval from another item/run/source. Findings remain explicit unresolved ledger entries until the relevant change is independently rechecked.

Read-only tasks remain read-only and do not acquire coding authority because a plan or handoff suggests a patch. They also must not require irrelevant build/test work merely to complete the new state machine.

For a coding task, success requires all authorized work completed, no unresolved blocking findings, fresh mandatory build/test evidence, a final independent approval and the existing capture policy outcome. A concise final narrative cannot override failed gates.

Capture remains after eligible successful execution and generates candidates only. Context rotation/subtask completion must not repeatedly deliver the same logical candidate, create fabricated full scans or auto-approve canonical Knowledge. Preserve existing delivery-only recovery and ownership semantics.

## 9. Finite repair, diagnosis and replanning

Implement explicit persisted repair/no-progress limits. Suggested initial policy: two unsuccessful repair cycles for the same diagnostic family, then at most one bounded read-only diagnosis/replan stage. Select and document sensible configurable limits; tests must exercise the actual limit rather than loop for an arbitrary long time.

A repair cycle must record the failure evidence, attempted change, resulting source/config identity and subsequent verifier outcome. Normalize failure signatures enough that timestamps, attempt IDs, log noise or cosmetic edits cannot trivially evade repeated-failure detection. Different genuinely new failures must remain distinguishable.

Diagnosis should classify code/test/environment/requirement uncertainty and produce a narrower actionable hypothesis. Use an ephemeral read-only Planning/diagnosis capability or another minimal existing role arrangement. It must not gain patch/shell authority.

After the permitted diagnosis/replan allowance, either proceed with a bounded justified new attempt or stop with a clear actionable non-success state. The total attempts remain bounded across renamed items, context epochs, resume and restart. Do not auto-expand scope or weaken tests to escape failure.

Unknown provider outcomes, uncertain process ownership and conflicting user edits are not ordinary repair failures to retry automatically. Retain the accepted stop/recovery requirements. No repeated charge/process replay may be justified by a new context ID.

## 10. Compatibility, authorization and lifecycle

Choose a **new product release version**; do not ship changed P4 wheels as another 0.3.0rc1. Align manifests, dependencies, runtime version/capability commands and example documentation.

Keep these dimensions separate: product version, runner config, task/plan schema, run state, handoff/checkpoint format, Knowledge schema and platform receipts. Unknown versions refuse before effects.

Define explicit legacy and P4 policy selection. Preserve accepted meanings of v1 config/task inputs and recorded P3 runs. Do not overload the existing `single`/`multi` context mode as an undocumented execution-policy switch.

Acceptable compatibility designs include a legacy driver plus a versioned new policy, or explicit previewed migration with tested recovery. Do not silently resume an old pending run under different semantics or require deletion of stores to make it work. Terminal old results remain historical results, not fresh validation.

Update companion authority as needed: exact task/config/policy, installed identity and entry runtime must remain bound under the real execution lease, including after rotations/replans/resume. Keep P3-R1/P3-R2 fixed. Enrollment/removal previews must not gain hidden default-policy changes, stale task substitution or mutable restoration bytes.

Preserve Knowledge independence, records/revisions/receipts/dispositions, positive capture ownership, pending outbox, unknown usage/process history and normal backup/restore/recover/uninstall behavior. Any new authoritative state must be included in maintenance snapshots and restored with compatible identities.

Exercise actual **accepted P3 package -> P4 install/upgrade -> preserved nonempty state -> supported rollback** in the same supported root/platform. Stop old processes before code replacement, and restart installed MCP/runtime processes afterward. Verify actual installed versions and code, not filenames. Do not expand unsupported cross-root/cross-OS relocation or POSIX-only P2 Windows migration claims.

Support the accepted Python 3.12/Linux and native Windows/NTFS/PowerShell 5.1 profiles. Keep ordinary-user operation and existing platform/path/process guarantees. Do not reinterpret OpenCode v1 as v2 support; a live host integration is a separate qualification.

## 11. Observability and complete metrics

Extend inspectable status/metrics without removing accepted accounting. Include:

- Execution policy/version, work plan/item IDs, dependencies, statuses and unresolved findings.
- Context identity/epoch, role, item, rotation reason and checkpoint/artifact references.
- Per-request serialized input bytes/hash and maximum input bytes per role/context/item/run.
- Request count and input-byte totals across all Main/Coding/Planning/Reviewing/diagnosis/checkpoint calls, including retries, failures and unknown outcomes.
- Provider-reported input/output/total usage where present, separate unknown-usage counts, and cache/reasoning subsets without double counting.
- Deterministic verifier invocations, real process attempts, results, source/config binding, durations and reuse/invalidation decisions.
- Repair cycles, repeated-failure families, replan counts, bounded-stop reasons and rejected authority changes.
- Wall time, provider time and process time with a sequential-execution explanation. Do not present their sum as wall time.

Context bytes are not measured model tokens; response `max_tokens` is not a context-window measurement. A missing token report is unknown, not zero. Quality/speed/token-benefit verdicts must distinguish software fixtures from live-model results.

## 12. Required verification

Retain the accepted P0-P3 behavior and correction regressions. Add meaningful tests at the authority and recovery boundaries; do not merely assert that a new JSON field exists or use success mocks for the effects being verified.

At minimum execute these scenarios against the new installed product:

| ID | Scenario and required result |
| --- | --- |
| P4-01 | A simple coding task uses the new pipeline, makes a real scoped edit, runs real build/test programs, obtains independent review and completes without mandatory Planning/Building/Testing model sessions. |
| P4-02 | A multi-item task gives each Coding item a fresh context; later items receive validated handoffs and dependencies, not previous transcripts. Final gates cover the final source. |
| P4-03 | A long continuation rotates before exhaustion, preserves an early requirement and unresolved issue, stays within actual serialized request limits and eventually produces the independently checked expected result. |
| P4-04 | An oversized irreducible assignment/checkpoint refuses before any oversized provider call; no criteria/policy silently disappear. |
| P4-05 | After several large child outputs/logs, Main still receives a bounded ledger and owned artifact references. Bounded retrieval can recover the real diagnostic; transcripts are not secretly concatenated. |
| P4-06 | A source or recipe-input change invalidates prior build/test/review evidence; stale success cannot finish the task. Cover final review rejection and malformed/empty test evidence. |
| P4-07 | Repeated failure with noisy logs/cosmetic edits reaches the finite diagnosis/replan policy and then stops honestly if unresolved. Epoch changes, item renaming and resume do not reset the allowance. |
| P4-08 | Interruption after a real edit, around checkpoint/rotation and after a verifier receipt resumes without replaying acknowledged source/process effects or losing authority. Exercise every introduced side-effect window. |
| P4-09 | A provider request with unknown outcome remains unknown/blocked across rotation/resume. All attempted calls/usage are counted and it is not silently resent. |
| P4-10 | Forged summaries, injected source/log instructions, invalid artifact references, expanded subtask paths/recipes and fake reviewer/verifier receipts cannot grant authority or completion. |
| P4-11 | Changing companion task/config/policy/enrollment/installation while crossing an ownership/continuation boundary rejects before new effects. Old removal approvals remain unable to remove a new installation. |
| P4-12 | Real accepted P3 nonempty Knowledge/Harness state survives supported P4 upgrade, backup/restore and rollback. Pending work is handled by documented version-aware semantics; unrelated user bytes survive. |
| P4-13 | Required execution/checkpoint/repair/process/lock/recovery behavior executes on native Windows and Linux. Windows evidence cannot be replaced by WSL, mocks or a workflow file. |
| P4-14 | Knowledge-only clean install still works without importing/installing Harness or requiring a provider/MCP service. P4 full install is exercised outside the source tree. |
| P4-15 | Cancellation/competing resume during automatic verification or rotation retains single-writer ownership and affects only verifiably owned processes. |

Use deterministic HTTP provider fixtures where necessary to control scheduling, long-context behavior and failures. They must exercise real installed tools, edits, process supervision, parsers, stores and journals. Their scripted decisions/usage do not prove live reasoning quality or model efficiency.

Rehearse at least one real .NET behavioral change using the existing pinned public application/rehearsal infrastructure or a justified equivalent independent project. Show an independent regression failing before repair and passing after implementation, real build/test artifacts, final review inputs and capture. Do not rewrite an application/test oracle to match a faulty result. A tiny synthetic fixture alone is insufficient application evidence; the private UMUH/IPM is not required.

Use native Windows CI on the task branch when available; updating the old branch-filtered workflow for P4 is in scope. Do not modify repository administration/secrets. If an authorized native runner cannot execute, finish all portable work, provide the exact native handoff and mark Windows `NOT_RUN/NO_GO`. Do not claim complete cross-platform acceptance or stop after merely writing YAML.

## 13. Evaluation against the accepted baseline

Produce a reproducible comparison against the **actual accepted P3 package**, not a pretend legacy label routed through the P4 engine. Run baseline and candidate in separate ordinary disposable source copies/environments. Do not patch P3 to make it lose.

Predeclare the scenario manifests, expected outputs/checks, policy settings and comparison procedure before collecting final results. Include at least:

1. A small behavioral fix with a regression test.
2. A multi-file/test-related change of bounded scope.
3. A multi-item/context-pressure scenario with an early requirement that must survive.
4. An intentionally persistent failure that must stop rather than claim completion.

Use equivalent application starting bytes, task objectives, verification oracles, review requirements, model/provider configuration and overall resource limits where supported. Document unavoidable differences introduced by the new policy. No weakening tests/review/capture, pre-solving P4 work, hiding failed runs or excluding coordinator calls from totals.

For deterministic scenarios repeat positive cases at least three times and retain every result. Demonstrate:

- The simple success path removes the previously mandatory role-attendance model calls while retaining actual checks/review.
- The long-task path preserves required information with bounded contexts and actual rotations, rather than falsely succeeding after truncation.
- The persistent failure path has finite observable attempts.
- The designated context-pressure comparison shows a lower maximum Coding request size through a generic item/continuation policy; report total input bytes/calls as well, including any tradeoff.

If a particular optimization does not reduce aggregate calls/bytes, show that result honestly. Correctness and boundedness are release requirements; universal speed/token improvement is not. If the designated Coding-context reduction is not achieved, do not describe that objective as completed: repair the implementation or identify it explicitly as an unmet acceptance condition.

Live local-model comparison is optional when an authorized compatible service already exists. Never fabricate its presence or install/alter the user's llama-server/OpenCode environment. Clearly label deterministic provider usage as synthetic, unavailable live usage as unknown/NOT_RUN and unproven performance benefit as NOT_ESTABLISHED.

The existing shared-history `single` versus isolated `multi` comparison is a different experiment. Preserve/document it; it is not by itself the P3-versus-P4 evidence required here.

## 14. Deliverables and reproducible review packet

Deliver a coherent implementation with:

- Versioned runtime plan/item/epoch/handoff/repair behavior and compatible CLI entry points.
- Updated schemas, permission checks, provider tools/policy, automatic verifier dispatch, independent final gates and durable recovery.
- Fresh P4 examples for one-item, multi-item, context continuation and failed repair. Include commands, expected statuses and artifact inspection, not just JSON fragments.
- A newly versioned transferable distribution and exact checksums, tested core installation, optional MCP declaration, uninstall/reinstall and lifecycle evidence.
- Runnable portable verification and ordinary task-branch native Windows CI.
- A complete final-source-bound external review packet.

Provide at least these documents or clearly indexed equivalents:

```text
docs/P4/DESIGN.md
docs/P4/USAGE.md
docs/P4/COMPATIBILITY-AND-RECOVERY.md
reports/P4/IMPLEMENTATION.md
reports/P4/ACCEPTANCE-MATRIX.md
reports/P4/EVALUATION.md
reports/P4/REVIEW-INDEX.md
reports/P4/runs/<run-id>/run.json
reports/P4/P4-review.zip
reports/P4/P4-review.zip.sha256
```

Include a top-level executable verification route, for example `scripts/verify_p4.py`, plus a review-packet generator. Document actual setup, execution and validation commands on Linux and PowerShell 5.1. Update version-specific package paths in active scripts rather than accidentally certifying the old P3 kit.

The packet must bind the exact implementation source inventory/hash, release/wheel hashes, run IDs, OS/runtime profiles, command argv/exit codes, tests, benchmark inputs/results, native CI links and artifact inventories. Preserve useful raw evidence while keeping dependency/model caches and private data out of the deliverable.

Use one coherent final verification run for the delivered implementation. Earlier runs remain historical; do not mix old successful traces with changed executable inputs. If a later evidence-only commit is used, prove that its executable/source/package inputs match the tested implementation exactly. Review archive inventory and external checksum must match the actual final bytes.

## 15. Acceptance and final response

P4 is ready for external review only when the new workflow actually runs from an installed package, all implemented authority/recovery boundaries have executed evidence, the declared finish line is met and regressions are resolved.

Acceptance requires:

1. Bounded work and fresh contexts are real runtime behavior, including Main's ledger and long-task continuation.
2. Successful deterministic build/test execution no longer needs role-attendance model calls in the new policy; final verification and independent review remain mandatory.
3. Repair is finite, persisted and cannot be bypassed through context/item changes.
4. Runtime permissions, final-source evidence, companion authority, unknown-outcome handling and capture are preserved.
5. Accepted P3 compatibility and nonempty-state lifecycle are demonstrated, not assumed.
6. Context/call/usage accounting covers the whole system, and the declared comparative results are reproducible and honestly qualified.
7. Installed-product and required native profile evidence is available, or the exact unexecuted profile is explicitly NO_GO with a reproducible handoff.

Do not report 'done' because new role prompts exist, context limits are lower, the examples are scripted to say success, or the old tests were skipped. Do not claim a real UMUH/IPM deployment or live-model benefit from deterministic fixtures.

Finish with:

- Exact branch and delivery commit; tested implementation commit/source identity if different.
- New product version, distribution path and SHA-256.
- A short description of observable before/after behavior.
- Acceptance matrix with PASS/FAIL/NOT_RUN, test totals and native CI run links.
- Benchmark table including correctness, largest Coding/Main inputs, total calls/input bytes/reported tokens, unknown usage, retries/rotations and elapsed time.
- Actual user commands for a new P4 task and inspection/recovery of its work items.
- Review archive/index locations and any remaining unsupported condition.

Complete your own review and necessary repairs before returning. The user will provide this packet for independent review, then send focused findings back if needed. Main merge, branch deletion and production adoption remain with the user.
