# Knowledge + Harness — P2 execution task

Version: 1.0 · 2026-11-15

## 1. Mission and accepted starting point

Implement **P2: a working Harness for controlled agent execution** on the accepted Knowledge foundation. Deliver functioning software, meaningful regression tests, executed evaluation and one complete review packet. This is an implementation assignment; do not stop at a design document or a collection of agent prompts.

Repository: <https://github.com/Ermak-P/Knowledge->.

Accepted P1 revision: `c62cad5aabbc47b43ef59fcf3ff975dd405eb42d`.

Accepted source identity: `f6fbbd3dc18cfe085c3694bd6ab529f23e5eb7ac7b0c54bb450083bb33069954`, as recorded in the accepted P1 verification/source inventory.

P1 independently passed 104 product tests, packaging, the source/run/archive gate, and five natural-language questions on pinned eShopOnWeb at ordinary retrieval defaults. All R1–R5 and round-2 A/B findings are closed. Its accepted scope is portable Knowledge and its read-only Harness consumer; it does not establish a working agent runner or live OpenCode/model integration. Submitted .NET TRX files were checked at 49/49 before and after; independent review did not claim its own successful .NET test execution.

The user will merge P1 into `main` and delete the `p1` branch. **Do not depend on that branch existing.** Start an ordinary `p2` development branch from the updated `main`. Confirm that the checkout contains the accepted implementation: use commit ancestry for an ordinary merge, or verify the accepted source inventory for a squash merge. If `main` has legitimate later changes, inspect and preserve them; record the relationship to the accepted baseline rather than reverting them. If the merge has not happened yet, identify the missing baseline precisely rather than implementing P2 on the old P0/P1 version.

Read the accepted source and contracts, P0/P1 task files and P1 correction tests before designing the extension. Include `packages/harness`, Knowledge's store/discovery/lifecycle/resolver, CLI/MCP adapters, packaging and verification scripts. The published narrow `inputs/ai-source.zip` intentionally has no original private Harness/writer implementation; implement against the explicit requirements here, not imagined legacy parity.

## 2. Autonomy and repository boundaries

Work through design, implementation, testing, self-review and repairs autonomously. Resolve routine reversible choices yourself and document material tradeoffs. Do not seek approval for every internal step. Test fixtures may approve their exact prepared Knowledge fingerprints automatically; ordinary product use retains explicit canonical-change approval.

Complete P2 and submit it for external review. Do not start P3 or claim external acceptance. Commit the completed product changes to the development branch and report the exact revision. The user controls merging into `main`, deleting branches and deployment. Do not perform those actions. Do not automatically commit the user's application edits. Synthetic Git fixture repositories may create commits for tests.

Use ordinary checkouts and **in-place execution only; no Git worktrees**. Preserve existing edits. Never use `reset --hard`, destructive clean, broad checkout/restore or history deletion as rollback. Use disposable ordinary application copies for controlled evaluation. Do not touch production IPM/UMUH, private machine configurations, credentials or external operational services.

Headless remote execution is sufficient. Inspect actual shell/process/network capabilities before diagnosing environment problems; a missing graphical desktop is not a runner prerequisite. Production projects, a local model, OpenCode, native Windows, Serena/Roslyn and private MCP services are not prerequisites for portable implementation. A genuinely missing essential execution capability must be reported accurately; do not invent verification or ask for unrelated GUI setup.

## 3. Finish line and scope

At the end of P2 a user must be able to configure a project and a supported provider, submit a coding task, and have Harness:

1. Resolve that explicit project and start a durable run.
2. Retrieve relevant current Knowledge with provenance and a measured context budget, or report explicit degraded availability.
3. Let Main delegate bounded assignments to Planning, Coding, Building, Testing and Reviewing, using separate contexts and enforced role/tool capabilities.
4. Execute actual source edits and actual configured build/test processes in the authorized project scope.
5. Require applicable build, test and review gates against the final source state before declaring the coding task successful.
6. Automatically derive eligible evidence-backed Knowledge candidates from the run and submit them through Knowledge's existing coordinated API, without silently applying canonical knowledge.
7. Resume/recover after interruption without repeating acknowledged edits, losing capture events or overwriting unrelated user changes.
8. Show honest status, failures and total accounting for Main, all subagents and every retry/attempt.

This must be a reusable product path, not a benchmark-specific script. Required portable behavior must work without a live model by exercising the same production provider protocol with deterministic test providers. A real provider adapter must still be implemented. Distinguish those kinds of evidence clearly.

**Out of scope:** GUI, production IPM cutover, final Windows/NTFS certification, universal model/host support, full external MCP installation, autonomous deployment, database/Kafka writes, cloud infrastructure, vector-store rewrites and P3 release/onboarding certification. Do not build a general enterprise agent platform to satisfy this milestone.

## 4. Ownership, compatibility and configuration

Knowledge remains independently installable and owns records, evidence, lifecycle, retrieval, validation, candidate identity and approved transactions under `.knowledge`. Harness owns execution, roles, tool capability enforcement, task/gate state, retries, budgets, capture delivery coordination and accounting under `.harness`. Reusable implementation stays in packages, not copied into each project.

Retain one Knowledge resolver and coordinated writer. Harness must not directly insert Knowledge SQL rows, append a competing queue, rewrite Knowledge journals, bypass validation or invent alternate lifecycle semantics. A Harness capture outbox is delivery state, not a second canonical knowledge store.

Document and implement versioned configuration, request/result/error schemas and durable-state compatibility. Existing `.harness/config.json` containing only `response_max_bytes` must remain supported or have an explicit tested migration. Preserve the existing read-only `harness --root ... --task ...` consumer behavior or provide a tested compatibility facade; adding a runner must not turn that old read command into a source-mutating operation. Update package/version capability descriptions honestly.

Use explicit roots everywhere; bind runs, role contexts, tool requests, artifacts, capture and metrics to one project identity. Accept spaces/non-ASCII paths; reject escaping paths, linked ancestors and accidental root fallback. Similar project names are not identities. Configuration and permission-policy changes mid-run require deliberate revalidation; they must not silently grant new capabilities to an existing approval.

Write a concise contract/architecture document and implement it in this milestone without waiting for an intermediate architecture approval. It must make the following behavior inspectable and testable.

## 5. Real execution and provider boundary

Implement a durable task/run coordinator and a versioned provider interface. Requests identify the run, immutable runtime role, attempt, bounded input/context, available tool schemas and limits. Responses have validated message/tool-call/completion/error forms. Malformed data, unsupported versions, unknown tools, oversized responses and provider failures produce explicit bounded errors.

Deliver at least one **real configurable model provider adapter**, suitable for use with a local OpenAI-compatible HTTP model endpoint such as the user's eventual llama-server environment. Consult current authoritative protocol documentation when implementing it. Support configurable endpoint/model, optional credentials supplied through a documented environment mechanism, actual requests/responses, structured tool requests, timeouts/cancellation and usage where the provider supplies it. Do not embed keys or private endpoints. Clearly report unsupported provider features; a server's text claiming that tools ran is not a tool execution receipt.

Exercise that adapter's real serialization/transport/parser with a controllable local HTTP test server and adverse responses. Deterministic providers may choose scripted actions to make tests reproducible, but those actions must traverse the same runner, authorization, tool execution, durable state, gate and capture code used in normal operation. A fixture that directly edits files or prepopulates success receipts outside the runner does not demonstrate agent execution.

If an authorized configured live model/host is actually available, run a small live smoke and report the actual model/endpoint class and outcome without exposing credentials. If not, mark live model/host integration `NOT_RUN`; finish portable implementation and transport-backed tests. Do not count stub usage as real inference measurements or claim that model quality, OpenCode interoperability or performance has been established.

Do not bypass native OpenCode permissions by invoking an external unrestricted agent executable. Any optional host adapter must describe the real permission boundary it can enforce. Core portable verification must not depend on an undocumented host hook.

## 6. Roles, contexts and enforced tools

Main is the only primary coordinator. Implement the five core subagent roles Planning, Coding, Building, Testing and Reviewing as separate role executions/contexts. They may use the same configured model; separate contexts do not imply independent models or simultaneous execution. Sequential scheduling is acceptable and is the safe default for a single-slot local model server.

Minimum capability policy:

| Role | Required capabilities | Boundary |
| --- | --- | --- |
| Main | Task decomposition, delegation, bounded source/Knowledge reads, status/accounting | No unrestricted shell or direct source/canonical Knowledge mutation |
| Planning | Bounded source/Knowledge inspection and structured plan | Read-only; no privileged delegation by impersonation |
| Coding | Read and constrained source patch operations in declared task scope | No arbitrary shell, policy/state edits, canonical Knowledge apply, Git reset/commit or access outside project scope |
| Building | Execute selected configured build recipe and inspect its receipts | No model-supplied arbitrary command string |
| Testing | Execute selected configured test recipe and inspect real results | No fabricated pass, arbitrary shell or disabling tests to pass a gate |
| Reviewing | Inspect final diff/source/evidence and return structured findings/verdict | Read-only; cannot manufacture build/test receipts or widen permissions |

Enforce this in the dispatcher/executor using the actual runtime role and validated typed requests. Prompts and provider-supplied `role` fields are not access control. A denied request must fail before side effects and be observable. An allowlisted tool name must not turn into an arbitrary command/argument/path escape. Use explicit recipes/argv rather than shell-evaluated strings where possible. Model-editable source must not become authority to change Harness policy or approve Knowledge transactions.

Document the practical boundary: Harness-level role checks are not an operating-system sandbox for arbitrary provider processes or build hooks. Do not advertise guarantees you have not implemented. Keep fixtures/build recipes within the authorized test environment.

The future specialist roles (Serena/Roslyn, external knowledge/services and other MCP tools) need a clear extension/capability interface, not fake implementations. Missing optional tools have explicit availability/fallback results and cannot silently acquire broader capabilities. Do not install or require every private MCP service for this milestone.

Give each role a fresh bounded context assembled from its assignment, relevant source/diff slices, selected Knowledge with provenance, necessary previous decisions and concise role results. Do not copy Main's full conversation into every subagent or dump the full Knowledge store. Persist task progress and artifact references outside model context so a new role invocation can continue after a long session. Test context separation with distinguishable markers and an oversized/long prior transcript; measure actual inputs and truncation/selection behavior, not just the existence of separate Python objects.

## 7. Tools, in-place changes and durable run state

Expose actual inspectable tools for bounded reads, scoped patch application, build/test recipe execution, review artifacts and role delegation. Application task intent must lead to real tool execution, not only generated instructions.

Each run needs a durable validated state machine with a unique identity, monotonic events or equivalent transactional ordering, role/attempt/tool identities, pending actions, artifacts, gate decisions and a terminal outcome. Choose the implementation, but define permitted transitions and recovery semantics. Keep externally unverified states distinct from completed success.

Coordinate source-mutating runs per project. Competing writers must refuse or wait within a bounded documented policy; two runs must not interleave source edits and then attribute each other's outputs to themselves. Read-only concurrency may be supported if it remains honest. Do not require parallel subagents or create extra checkouts/worktrees to solve coordination.

Bind edit intent to the authorized paths and actual before/after content identities. On recovery:

- If the edit is known not to have occurred, retry according to policy.
- If exact after-state and ownership show it already occurred, reconcile the receipt without applying the patch twice.
- If a user/other process changed the file, stop with an actionable conflict and preserve their bytes.

Do not promise one atomic transaction across filesystem edits, remote inference and SQLite. Demonstrate how durable intent, receipts, reconciliation and idempotency handle the gaps. An unknown provider/tool outcome remains unknown until resolved, not automatically retried as harmless.

Use real process execution for recipes: capture exit code and bounded logs, deadlines, cancellation and child cleanup. A cancelled/timed-out build/test must not later report success or keep modifying the project unnoticed. Release mutation ownership only under the documented safe process state. Test actual interrupted processes and competing runs, not only exceptions in one Python stack.

## 8. Build, test and review enforcement

Coding tasks must have explicit completion criteria and applicable mandatory gates. Read-only tasks can have a different declared gate policy, but a coding run cannot silently relabel itself read-only to skip validation.

Execute build/test recipes through the restricted tool boundary. Store actual invocation/recipe identity, timestamps, exit codes, logs/results, project, source/config identity and attempt. A provider's “tests passed” sentence or copied old TRX is not evidence.

Gates must concern the **final relevant source state**. Any subsequent source change invalidates earlier affected build/test/review receipts; rerun the applicable checks. Also detect a concurrent edit during a gate. Bind the review verdict to the reviewed diff/source and include structured blocking/nonblocking findings and reasons. It must be a separate Reviewing invocation/context, not Coding's self-reported approval.

Do not declare success when a required build/test failed, review is missing/rejecting, or required evidence is stale/ambiguous. Permit repair cycles, but bound retries, repeated identical failures, role delegation and elapsed/token budgets. Exhaustion produces a precise terminal/paused result with completed work preserved, not a misleading success or an endless loop. Test an attempted bypass and an actual failing-check → repair → fresh checks → success sequence.

Do not weaken/delete existing application tests or alter recipes merely to obtain a pass. Explicitly scoped new tests and legitimate source changes for a benchmark task are allowed and must be part of its reviewed diff.

## 9. Automatic Knowledge capture

Implement capture as a normal part of the delivered runner, triggered by real run/tool milestones or completion according to a documented policy. The user must not separately paste observations into a queue for the demonstration. Capture delivery is not equivalent to canonical acceptance.

Derive candidates only from identifiable eligible source observations or concrete recorded evidence. Reuse the accepted Knowledge discovery/submission APIs where appropriate. If model interpretation is used, retain uncertainty and source/provenance, and do not upgrade business meaning or unsupported explanations to CONFIRMED. Deterministically verified source syntax may keep the narrow accepted P1 confidence policy. A successful task, generated summary or passing test alone does not prove a reusable architecture/business assertion.

Persist a capture decision for each relevant event: candidates submitted/deduplicated; no eligible new supported fact, with a reason; pending delivery; or failed/manual-review required. A candidate quota is not a correctness target. Preserve human reject/defer dispositions and same-payload deduplication; a retry must not resubmit unchanged refused work as new by altering timestamps or wording.

Use a durable outbox or equivalent protocol. Persist exact payload/event identity before submission. Submit through Knowledge's single supported writer. Record the returned candidate identity/disposition and event/run linkage. If Knowledge commits but Harness dies before recording delivery, recovery must reconcile/deduplicate without losing or multiplying candidates. Preserve the original payload/capture time and event ownership on retry. Retain accepted Knowledge envelope/schema validation; keep additional delivery bookkeeping in supported provenance fields or the Harness event mapping rather than inventing silently ignored record fields.

Handle store absence, bounded lock contention, corruption, invalid candidates and interrupted delivery explicitly. Do not convert corruption into an empty successful knowledge result. If execution succeeded but capture remains pending, show those dimensions separately; do not claim that knowledge was delivered. Recovery must not replay code changes just because capture delivery is incomplete.

**Never automatically prepare-and-approve/apply canonical knowledge as a side effect of an ordinary task.** Reuse the explicit Knowledge preview/review/approval/apply/ack workflow. Keep canonical values/history unchanged until that explicit authorized transaction, including retire/supersede/reactivation operations. A scanner's observation is not approval to remove a claim.

Required capture evaluation: five independent eligible source-change sessions through the real runner, each automatically producing the expected supported candidate(s) exactly once; plus ineligible/no-new-fact sessions that honestly produce none. Include duplicate event delivery, unchanged rejected/deferred candidates, Knowledge-busy recovery, concurrent producers and process death after Knowledge accepted a candidate but before Harness acknowledged delivery. Five scripted direct calls to `Store.submit` are not five automatic sessions.

## 10. Recovery, cancellation and failure accounting

Support inspecting runs, resuming/recovering an interrupted run and explicit cancellation. A restart must load durable project-bound state, not regenerate an entire task from a conversational summary or silently start a new successful run.

Exercise interruption before/after edit intent and source write, during an actual recipe process, after tool completion but before its run receipt, during capture delivery and around terminal state. Establish whether a recipe can safely be rerun and what evidence it invalidates. Provider response timeouts and external effects with unknown outcome need explicit handling. Do not reuse stale approval or hidden success flags as recovery authority.

Retain failed/cancelled attempts and their charged/unknown usage. Preserve unrelated user edits and the original Knowledge data/queue/history. Recovery/cleanup must be idempotent; malformed/unknown durable-state versions must refuse safely rather than reset the run.

## 11. Budgets, metrics and comparison

Produce per-run, per-role and per-attempt accounting including Main, every subagent, failed requests, retries and delegated calls. Include wall elapsed time, provider duration, tool/build/test duration, queue/wait time where measurable, retry/guard outcomes and completion/gate status. Distinguish summed concurrent durations from elapsed wall time.

For model usage retain provider-reported input/output, reasoning and cache information when available, plus raw usage semantics/source. Avoid double-counting totals and subsets such as cached input or reasoning already included in another total. Aggregate all calls consistently; Main-only usage is not total cost. Missing usage is `unknown`/partial with explained coverage, not zero. Mark estimates and synthetic test-provider usage explicitly; do not compare them as measured live-model efficiency.

Enforce configured context/output/attempt/time/tool-result/log limits at actual boundaries and prevent unbounded growth or delegation loops. Explain what can be capped before a request and what is only observed afterward; do not claim exact provider-token enforcement from a character estimate. If accounting or a mandatory limit cannot be enforced, surface that state and follow a documented conservative policy. Test Unicode byte limits, oversized tool/provider output, cancellation and exhausted budgets.

Provide a comparison runner/report for single-agent and Main-plus-subagent execution on the same tasks and provider configuration. The comparison baseline may use one reasoning context with the same guarded executor and externally enforced completion checks; it must not become a permission bypass in the ordinary multi-role runner. State which checks/review contexts are shared or separate and include their cost consistently. Record task success first, total tokens across all roles, wall time, retries and relevant cache/warm/cold conditions. If no live model is available, execute the orchestration/accounting comparison with deterministic transport providers to validate the measurement mechanism, and mark real quality/speed/token-benefit conclusions `NOT_ESTABLISHED`. Do not make a positive performance claim merely because contexts are separate. Negative or neutral measured benefit is acceptable; missing or misleading accounting is not.

## 12. Executable interfaces and documentation

Deliver real CLI/API commands for at least configure/validate configuration, run/start, inspect/status, resume/recover, cancel, capture delivery status/retry and metrics export. You may choose exact names, but document examples, versioned JSON, exit codes, stable errors and side effects. Retain the existing read-only facade and Knowledge's three accepted command adapters; do not create markdown-only commands with no backend.

Ship one minimal usable project configuration and one provider example with no secrets. Explain how to run with the supported live adapter, what deterministic tests prove, how role/tool policy is enforced, how capture becomes a reviewable candidate, and how recovery works. Update README/START-HERE/package descriptions to describe the delivered P2 behavior while retaining historical task/report files as history.

Document the later OpenCode/Windows integration boundary precisely. Do not certify an untested live host. Keep Knowledge installation usable without Harness/provider services. New Harness dependencies must be explicit, reproducible and appropriately optional rather than forced into standalone Knowledge.

## 13. Realistic evaluation and independent expectations

Use the existing pinned eShopOnWeb commit `0c2c95d9d450d07fcd4e96e95e1cd48c20834e99` as the realistic .NET test application. Preserve the original pinned checkout and evaluate changes in disposable ordinary copies, never Git worktrees. Record remote/pin, actual SDK and initial source/dirty state. Preserve the application's license.

Establish a fresh real restore/build/unit baseline. Reuse the known project-scoped/single-node setup where appropriate; do not require UI/container deployment. Independently define an expected code change and executable check before running the agent, rather than accepting whatever change it happens to emit.

Required scenarios:

1. At least one meaningful, narrowly scoped source behavior change in the real pinned application, made by the delivered Coding tool path, followed by actual build/tests and a separate review. Its effect must be shown by an independently specified regression/behavior check. Existing baseline tests remain intact; counts may increase with legitimate added tests.
2. At least two further distinct coding scenarios across that application and a realistic synthetic multi-project .NET fixture: one fails a mandatory check and is repaired before success; one demonstrates a real denied capability or isolation attempt with no forbidden side effect. Across the suite also cover read-only operation and optional Knowledge absence/degradation.
3. The five eligible automatic-capture sessions and adverse recovery cases from section 9, plus honest no-candidate cases.
4. The same task definitions exercised by the single-agent/multi-agent comparison path with clear provider/test-double attribution.

These evaluations may share task/session fixtures where the required assertions are independently checked; five capture sessions do not require five additional full eShop clones/build baselines. Keep each session/event and its actual outcome identifiable.

Deterministic model decisions are allowed for repeatable integration tests. They must drive the production runner/provider/tool paths; actual file/process/store behavior and gate decisions must be real. Do not hard-code benchmark paths or answers into generic Harness logic. Fixture generators may contain scenario-specific expected edits/actions and must identify them as synthetic test inputs.

If infrastructure blocks an application check, report the exact failure and attempted reasonable remedy. Do not remove the gate, relabel an old run fresh or silently substitute a toy test. Missing optional live-model/Windows/MCP capabilities are separate `NOT_RUN` items, not fabricated integration successes.

## 14. Acceptance matrix

Map every row to named executed tests/commands and current-run evidence; mark failures/blocked/NOT_RUN honestly. The implementation's table is a submission for review, not self-issued external acceptance.

| ID | Required result |
| --- | --- |
| P2-A01 | Verified accepted P1 baseline, reproducible package installation and all 104 accepted product regressions preserved; Knowledge remains independently usable. |
| P2-A02 | Real versioned runner/provider protocol and configurable live adapter implemented; actual transport/parsing/error behavior tested, live versus deterministic evidence distinguished. |
| P2-A03 | Main and five core role executions have separate bounded contexts; required state survives context/session replacement without full-history duplication. |
| P2-A04 | Runtime role/tool/recipe permissions deny unauthorized actions before effects; provider role spoofing and path/argument/policy escapes fail. |
| P2-A05 | Actual in-place scoped source edits and recipe processes run through production tools; project identity and competing-run ownership are enforced. |
| P2-A06 | Durable state transitions/status/cancel/recover are implemented; malformed versions and ambiguous outcomes refuse safely. |
| P2-A07 | Mandatory build/test/review gates bind actual final source/config state; stale/missing/failed checks and fake provider receipts cannot produce success. |
| P2-A08 | Real fail → repair → fresh gates → success flow passes; retries, repeated failures and delegation/budget exhaustion terminate honestly. |
| P2-A09 | Source-edit crash reconciliation avoids double edits and preserves conflicting user bytes; completed work is not reset to obtain recovery. |
| P2-A10 | Actual recipe timeout/cancellation/process death and child cleanup cannot leave a false success or unsafe released writer ownership. |
| P2-A11 | Automatic capture derives supported candidates during real runner sessions, uses the existing Knowledge writer, preserves confidence/provenance and never auto-applies canonical changes. |
| P2-A12 | Five eligible capture sessions succeed exactly once; no-new-fact sessions abstain; rejected/deferred unchanged candidates are not revived endlessly. |
| P2-A13 | Capture outbox/event identity handles busy/corrupt stores, concurrent producers and the accepted-but-unacknowledged crash window without candidate loss/duplication. |
| P2-A14 | Execution outcome, capture delivery and canonical approval are distinct; recovery can deliver pending capture without rerunning source edits. |
| P2-A15 | Complete per-role/per-attempt usage and timing includes Main/subagents/retries; unknown/estimated/synthetic usage is explicit and totals do not double-count. |
| P2-A16 | Actual context/output/time/attempt/log limits are enforced with documented uncertainty, Unicode/oversize tests and no unbounded retry loops. |
| P2-A17 | Single-agent/multi-agent comparison is executable on equivalent tasks; correctness and total cost are reported, with no unsupported speed/quality claim. |
| P2-A18 | Functional CLI/API/configuration and compatible old read facade execute the backend; missing optional tools and Knowledge degradation are explicit and project-isolated. |
| P2-A19 | Pinned real-application source change passes independently specified behavior/build/tests/review; existing tests are not weakened; original checkout stays intact. |
| P2-A20 | Additional fixture, isolation/denial, five capture and crash/race scenarios exercise real tools/stores/processes and document exactly which provider decisions were synthetic. |
| P2-A21 | Fresh current-run verification binds source/config/tasks, provider fixtures and artifacts; failed/mixed/stale/incomplete runs cannot generate an all-PASS packet. |
| P2-A22 | Complete source/test/setup/contracts/recovery/metrics/evaluation packet is reproducible, checksum-verified and contains no credentials, caches, SDKs or private machine data. |

## 15. Verification and review packet

Add a separate P2 verification pipeline and `reports/P2`; retain P0/P1 historical evidence. Run fresh setup/packaging, the full accepted-plus-new suite, actual stdio/API compatibility, provider transport, permission/context tests, process interruption/contention, capture, metrics and pinned application evaluation. Do not replace test bodies with scaffolding or rely solely on static configuration inspection.

Use one current run identity, source fingerprint and artifact manifest. Cover Harness configuration/recipes, task definitions, provider fixtures, expected results and gate-relevant inputs, not just Python modules. A failed/interrupted verification must invalidate current success. Test stale-source, modified artifacts, mixed-run evidence, missing checks and provider/gate spoofing against the evidence gate. Do not overwrite accepted P1 reports to make P2 look fresh.

Deliver a self-contained review ZIP and external SHA-256 containing allowlisted source, tests/fixture generators, reproducible setup, this task, current contracts and the current verification evidence. Verify every archived member against an inventory. Exclude credentials, personal settings, private source, dependency/SDK/model caches and unrelated old runs.

Required reports, with equivalent clear names allowed:

1. `P2-REPORT.md`: actual delivered behavior, accepted starting revision, final source/branch identity, commands/results and remaining limits.
2. `ACCEPTANCE.json`: all P2-A01–A22 with run/source identity and concrete evidence; optional/live conditions separately.
3. `P2-CONTRACTS.md`: configuration, provider/tool/role protocols, state machine, gates, capture, budgets, errors and compatibility.
4. `EXECUTION-AND-PERMISSIONS.md`: core roles, enforced capability matrix, context measurements and denied-action evidence.
5. `CAPTURE-REPORT.md`: five sessions, supported source expectations, candidate/disposition mapping, no-fact cases and recovery/dedup results.
6. `RECOVERY-REPORT.md`: interrupted edits/processes/outbox windows, conflicting user changes, writer races and documented reconciliation limits.
7. `ACCOUNTING-AND-COMPARISON.md` plus machine-readable metrics: every role/attempt, aggregation rules, measurement coverage and single/multi-agent results.
8. `APPLICATION-EVALUATION.md`: pin/source identities, independent expected behavior, actual changes/diffs, baseline/final build/test/review and original-checkout immutability.
9. Run ledger, raw logs/results, source/artifact inventory, verified ZIP and SHA-256.

Finish with self-review of the concrete failure boundaries, repair discovered issues, rerun the checks affected by source changes, then run the final coherent verification. Return one complete reviewable result; do not stop for every internal design choice.

The final response must name the committed revision/branch, exact verification command, actual test/evaluation summary, review packet path and every failed/blocked/unexecuted condition. Label P2 **submitted for external review**. The finish line is a functioning, inspectable Harness that executes controlled work and safely feeds reviewable Knowledge candidates—not a claim that production IPM/UMUH migration or live-provider effectiveness has already been certified.
