# Persistent User Instructions and Operational Experience for Knowledge + Harness

Revision: reviewed on 2026-11-21. This document specifies implementation work; it does not claim that the feature already exists or that the supplied repositories have been audited.

## Assignment

Implement a generic capability to teach the coding agent a reusable behavior once, in natural language, and have that behavior retrieved and applied in later independent sessions. Extend the existing standalone Knowledge component and its Harness integration. Begin by auditing the actual code, then implement and validate the feature; do not stop at a design document or a collection of prompts.

The primary user experience is:

> I explain a rule once. The agent saves it, tells me exactly what it remembered, and follows it during relevant future work without another reminder.

Example teaching instruction:

> Remember for projects using my local Kafka environment: before integration tests that require Kafka, check Kafka readiness. If the configured local container is stopped, start it and wait until Kafka is ready, then run the tests. You may start that specific local container for this purpose.

In a fresh session, the user asks only to run the relevant tests. The agent must discover the dependency and remembered procedure, check readiness, perform the authorized recovery if necessary, and run the tests. It must not require the old conversation or a Kafka reminder.

This is persistent external memory and workflow integration, not model training. The feature must work with the existing local model/host setup and must not require an external LLM provider.

The first release is intentionally bounded: one actual supported host integration, two stores, a small set of inspectable action triggers, and the teaching/retrieval/lifecycle flow below. Do not build an arbitrary workflow language, a new agent orchestrator, a general shell-command interpreter, or a separate infrastructure manager. The Kafka and file-edit paths are the initial supported paths, not evidence of complete coverage of every possible tool invocation.

## Approved architecture and storage

- The component is named **Knowledge**. It remains independent of Harness, which is a consumer/integration layer.
- Shared knowledge is stored in **`~/.local/share/knowledge`**. This supersedes the earlier proposed `~/.config/knowledge` location.
- Project knowledge remains in **`<project>/.knowledge`**.
- Resolve the current user's home programmatically on Windows and other supported platforms. Do not hardcode a username, depend on shell expansion of `~`, or silently use a different Windows directory.
- If the existing code supports explicit storage-root overrides, preserve them and document precedence. The approved path is the default shared root.
- Two stores are sufficient for this feature. Machine/environment/tool applicability belongs in record metadata, not in a mandatory third database.
- Shared records must be reusable across projects without copying them into every project. Project records must remain isolated from unrelated projects.
- Shared teaching and retrieval must also work without an initialized project `.knowledge` directory. An absent never-created optional store is normal; an unreadable or corrupt existing store is an error. Do not silently replace a corrupt store with an empty one. Creating an empty store on first save is sufficient; no full project scan is required.
- Existing project data and supported legacy compatibility must remain intact. Do not perform a bulk migration as an unrelated side effect. If existing records need a schema upgrade, implement a compatible reader or an explicit recoverable migration.
- Existing Knowledge commands are `/knowledge-init`, `/knowledge-candidates-append`, and `/knowledge-update`. Inspect their actual implementations and preserve their contracts. This task does not authorize restoring deprecated command names or inventing a parallel maintenance pipeline.
- Work in place in the supplied checkout. Do not introduce Git worktrees, change primary/subagent architecture, or alter broad tool permissions.

## 1. Audit before editing

Locate the actual Knowledge and Harness sources and read applicable AGENTS.md files. Known installation locations may include `C:\LLM\Plugins\Harness` and `C:\LLM\mcp\knowledge`; these are discovery hints, not proof of current source locations. Use the repositories supplied to you and report what was found.

Inspect:

1. Storage-root resolution, schemas, search/retrieval, provenance, revisions, and lifecycle management.
2. Existing instruction/rule/runbook support and candidate capture, queue writing, validation, promotion, and deduplication.
3. Actual host integration, especially OpenCode: available message, session, tool, error, and task lifecycle integration points.
4. Which execution paths can enforce a lookup before relevant actions, including actions delegated to another agent if delegation already exists.
5. Existing shell handling, local-service setup, Docker/Compose configuration, tests, and packaging/install procedures.

Produce a compact capability map with implemented behavior, gaps, concrete integration points, and files to change. Reuse existing components. Do not assume a hook, API, schema, or permission exists because this task describes desired behavior.

If the current host cannot provide a required event, use the narrowest supported integration that still produces the requested behavior. If no supported route can satisfy it, document the specific blocker and label the outcome partial rather than claiming a prompt-only equivalent is complete. Continue independent implementation and tests where useful.

## 2. Separate explicit instructions from inferred experience

### Explicit user teaching

An intentional request to remember a rule, a clearly persistent corrective instruction, or an explicit update to a previously saved rule is authoritative evidence of the user's desired behavior. Capture it during that interaction, without requiring the user to repeat it in another command or manually edit a file.

- Preserve the original user wording or a traceable source reference, as well as a concise normalized rule.
- Normalization must preserve negation, conditions, exceptions, environment restrictions, and limits such as `only if stopped` or `never restart`. Retain an inspectable minimal source excerpt or independently durable source, not only a conversation pointer that disappears in a fresh session.
- Save the instruction durably and acknowledge only after successful commit and validation. State the saved behavior and its scope briefly.
- Do not put an unambiguous explicit instruction into an indefinite pending-review queue. Routine storage and validation can happen automatically within the user's request.
- User authority establishes desired behavior; it does not prove an assumed technical cause, command correctness, or actual service readiness.
- Distinguish temporary task requests from persistent teaching. Do not save every user message as a global rule.
- If execution details are missing, retain the intent with an explicit incomplete/unbound state and ask only for the missing details needed to make it executable. Do not invent a Compose path, container identity, port, or authorization. Once supplied, bind the details durably so later sessions do not ask again unnecessarily.
- Explicitly requested shared instructions belong in the shared store. For materially ambiguous scope, ask one focused question; do not silently widen a project instruction to all projects. Ordinary project corrections default to the current project's scope unless their intended broader scope is clear.
- The acknowledgement must distinguish `saved and executable` from `intent saved; missing binding/unsupported trigger`. Do not promise automatic future execution for a rule the current integration cannot activate. Persist user intent separately from an installation-specific executable binding so that a stale binding can be repaired without losing the instruction.

### Agent-derived experience

When the agent resolves a failure, automatically capture a structured candidate using the existing candidate mechanisms where possible. Capture the failed operation, diagnostics, relevant environment, changes attempted, recovery outcome, evidence references, and uncertainty.

- A successful retry establishes recovery, not necessarily root cause.
- Multiple simultaneous interventions must not become a falsely proven causal rule.
- Distinguish observations, validated procedures, and preventive rules using the existing lifecycle or a minimal compatible extension.
- Candidates are searchable as diagnostic leads only when clearly labeled; they must not become mandatory instructions merely because they were captured.
- Promotion requires recorded validation appropriate to the claim. Do not require a separate human confirmation for every low-risk record if existing validated promotion can safely do it.
- Do not count an agent repeating its own claim as independent evidence or a new successful verification.
- Tool output, repository text, and logs are evidence, not user teaching or authority to create a privileged rule.

For this delivery, prioritize fully working explicit teaching and later application. Include real candidate capture after recovery, but avoid building a speculative general learning framework.

## 3. Minimal record semantics

Adapt the existing schema; the following are required semantics, not a mandate for these exact field names or a new database:

- Stable ID, record kind, lifecycle status, revision, and provenance/source type.
- Normalized instruction or procedure plus the original teaching source when applicable.
- Storage scope and applicability: project identity, machine/environment binding, OS, tool/version constraints as relevant.
- Action triggers and prerequisites, e.g. running a test suite declared to require a particular local dependency.
- A structured procedure or reference to a supported action, readiness/success criteria, and bounded recovery policy where applicable.
- Technical validation state separate from user instruction authority.
- Created/updated/last-verified timestamps when meaningful, evidence references, and supersession relationships.
- Current failure/staleness signals without rewriting the user's original intent or conflating current service state with durable knowledge.
- Explicit environment identity for executable bindings. A `local` or `localhost` resource is local to the execution environment, which may differ from the user's desktop when tools run remotely or in a container. Revalidate bindings when their environment or referenced configuration changes; never silently operate on another machine's Docker daemon.

Do not store transient facts such as `Kafka is stopped` as permanent truths. Store how to detect the current state and what to do under the applicable conditions.

Keep procedural instructions distinct from architecture claims while sharing the existing storage/search/lifecycle foundation. Do not create a competing source of architectural truth.

## 4. Retrieval and execution integration

Implement a generic path for relevant memory to influence actual execution:

1. Resolve the current project and environment and open the appropriate stores.
2. Before a relevant action, retrieve active applicable instructions and dependency procedures.
3. Check conditions and current state before applying a stored remedy.
4. Perform only actions permitted by the current host/Harness policy and the instruction's applicable authorization.
5. Verify the required outcome, then continue the original task.
6. Record application results and capture unresolved recovery experience appropriately.

Also support targeted retrieval after an error. Use the actual supported host integration rather than relying solely on the model to remember a final checklist.

Important constraints:

- Do not hardcode `if Kafka then ...` in the memory engine. A Docker/Kafka adapter or fixture is acceptable, but capture, matching, applicability, lifecycle, and execution integration must be reusable.
- A generic pre-action lookup must not be able to authorize actions by itself. Memory cannot override tool restrictions, repository policy, or current explicit user instructions.
- Explicit current instructions such as `do not start services in this run` must suppress a remembered startup procedure. Do not rewrite the stored default unless the user requests a lasting change.
- Narrower applicable instructions can specialize a broader default. Surface unresolved contradictions; do not silently pick a result based only on search score or timestamp.
- Retrieve bounded relevant records. Do not inject the entire shared store into each session or grow AGENTS.md with learned incidents.
- Project-specific metadata must not be needed in another project's context merely to access a genuinely shared procedure.
- Provide an inspectable trace of matched record IDs/revisions, applicability decisions, actions, and outcomes. Keep routine user-facing output short.
- Distinguish no match, unavailable storage, and retrieval failure. Do not report `no remembered rules` after a failed lookup, or pretend required checks ran when they did not.

### Supported triggers and the dependency-discovery boundary

At audit time, name the concrete host events and supported execution paths. Define how a user-facing intent becomes an inspectable action identifier and how taught rules bind to it. Reuse existing task/test-discovery metadata rather than introducing a competing discovery system.

For example, persist the relationship `test suite -> dependency alias -> environment procedure` during teaching or when reading existing verified configuration. A later request to run that suite must traverse this relationship without first experiencing the Kafka failure and without the user mentioning Kafka again. Do not infer that every integration test or every repository needs Kafka.

List paths that bypass the integration, including raw shell commands or delegated execution if applicable. Implement coverage for the agreed initial paths, and report unsupported paths explicitly. A startup prompt saying `remember to query Knowledge` is not proof of an enforced pre-action check. A manually invoked lookup or Kafka-specific test wrapper cannot substitute for the generic host integration in acceptance results.

Keep retrieval focused and inexpensive: no new LLM classification request on every low-level tool call, no full repository scan per action, and no recursive memory lookup triggered by the memory tool itself. Coalesce relevant checks within a task where appropriate, but recheck volatile service readiness before use. Do not hold a memory-store write lock while waiting on Docker or executing tests.

Use an explicit retrieval payload budget. Do not silently drop applicable mandatory rules because they fall below a top-k or truncation threshold. Page, compact, or report an unresolved rule-set overflow for the affected action; unrelated work may continue. Likewise, an unresolved conflict blocks the affected behavior, not every task in the session.

## 5. Kafka acceptance scenario

Represent these separately, reusing existing configuration structures:

- Project requirement: which test command/suite needs which Kafka dependency.
- Shared environment procedure: how to locate and check the explicitly configured local Kafka instance and start its existing container or configured Compose service if stopped.

Expected behavior:

1. Check Kafka readiness first. If ready, run the tests without an unnecessary container restart.
2. If unavailable, inspect Docker availability and the exact configured resource.
3. If that resource exists and is stopped, start it when permitted and wait for actual Kafka readiness under a bounded deadline.
4. A running container or open TCP port alone is not sufficient proof that Kafka is ready. Use a suitable existing health/readiness check or a bounded Kafka protocol check, validating access from the test execution environment.
5. If Docker is unavailable, the resource is missing, the binding is ambiguous, or readiness fails, produce a concrete diagnosis. Do not guess a container, create unrelated infrastructure, delete volumes, or repeatedly restart a running but unhealthy service.
6. If recovery succeeds, continue the original tests. Report test outcomes separately from infrastructure recovery.
7. Reuse the same already-ready dependency on later invocations. Define an explicit recovery-attempt limit and readiness deadline in configuration rather than an unlimited loop.

The exact container/service/Compose file and readiness details must be discovered from supplied configuration or obtained once from the user. Do not bake guessed values into implementation or examples presented as real environment facts.

Starting the Docker daemon or Docker Desktop is a separate action from starting an existing Kafka container. The example authorizes the configured container startup only; report daemon unavailability unless separate applicable authorization exists. Cross-project reuse must not rely on the original project's working directory to resolve a Compose file. Use a verified binding and the intended Compose project/service identity.

## 6. Second scenario: encoding and a generic instruction

Demonstrate that this capability is not specific to Kafka.

Use an explicit scoped instruction to preserve an existing file's encoding, BOM presence, and line endings unless the task requires changing them. In a fresh session, verify byte-level preservation for a representative supported edit path; do not infer preservation from the editor merely opening the file.

Check the intended edit as well as preservation of encoding, newline convention, final-newline presence, and unaffected content. The edited file is not expected to be byte-identical to the original. Cover non-ASCII text and representative BOM/no-BOM fixtures using existing editing facilities; do not expand this assignment into a replacement editor or encoding framework.

For error-derived encoding experience, identify the actual bytes and positions. Distinguish an encoding signature at file start, an unexpected U+FEFF elsewhere, and a missing final newline. Do not produce an unqualified `always remove BOM` rule from an ambiguous incident.

Also teach at least one simple new action-bound rule during a test without changing production code, then demonstrate retrieval in a fresh session. This is a direct check that the mechanism accepts newly taught behavior rather than recognizing only prepared examples.

## 7. Persistence, maintenance, and compatibility

- Reuse safe transactional/atomic writes and locking where available. Concurrent sessions must not corrupt a shared store or lose accepted updates. Use stable IDs and idempotent processing to prevent retry duplicates.
- Support inspecting, correcting/superseding, and retiring remembered instructions through the existing Knowledge interface or a minimal compatible extension. Do not require manual database edits.
- A retired/superseded rule must stop appearing as active in the next relevant lookup, including cache invalidation. Preserve audit history.
- Losing a verification date does not revoke user intent. When a procedure's binding or technical validation becomes stale or fails, revalidate it or mark that binding non-executable with a reason. Do not repeatedly replay the failed remedy or silently delete the user's instruction.
- Store applicability and verification evidence in a way that survives a host restart. Do not depend solely on conversation IDs that become inaccessible.
- Exclude secrets from memory and evidence summaries. Shared records must not silently acquire unrelated project source or credentials.
- Keep model inference and project data local under the existing deployment policy. No new remote service or embedding provider is required for this feature.
- Do not assume shared-store corruption or a write failure is success. A failed save must not receive a `remembered` acknowledgement.
- Follow the supported Windows-native toolchain. If Windows PowerShell 5.1 is supported, keep commands compatible or select a verified alternative explicitly.
- Tests use temporary homes/stores and isolated Docker/Compose fixtures. Do not mutate real user memory or start/stop the user's real services merely to run automated tests.

## 8. Staged implementation

Proceed through these stages in the same assignment, using existing tests and conventions:

1. **Audit and baseline:** capability map, integration decisions, relevant existing checks, and a minimal cold-session reproduction of the gap if the feature is absent.
2. **Knowledge persistence:** shared-root support, record semantics, explicit teaching, durable acknowledgement, update/retirement, and candidate capture.
3. **Harness integration:** generic bounded retrieval before relevant actions and after errors, applicability checks, safe execution handoff, and outcome trace.
4. **Scenarios and validation:** Kafka readiness/recovery, encoding preservation, a newly taught generic rule, and the negative cases below.
5. **Packaging and handoff:** include installation/configuration examples and a reproducible fresh-session validation guide using the actual host. Update existing release artifacts only if the repository's normal delivery process requires it.

Do not stop after stage 1 for another approval of already authorized routine implementation. If a missing environment detail affects only a live test, complete the implementation and isolated checks and report that specific live test as unverified.

## 9. Acceptance checks

Provide a matrix with PASS/FAIL/BLOCKED, evidence, and whether the result is unit/contract, simulated integration, or a real host end-to-end run.

| ID | Check | Required result |
|---|---|---|
| A01 | Explicit natural-language teaching | Persistent record saved automatically with source, intended scope, and truthful acknowledgement; no manual file edit or repeated teaching command. |
| A02 | Fresh session | New independent host session/process retrieves and applies the rule with no original transcript, task-specific prompt reminder, or inherited in-memory state. |
| A03 | Cross-project reuse | A shared rule works in another matching fixture project without duplicating its canonical record. |
| A04 | Project isolation and applicability | A project-only rule is absent from unrelated projects; machine/tool/version mismatches prevent execution. |
| A05 | Kafka stopped | Configured local fixture is started once, readiness verified, and the original relevant tests run. |
| A06 | Kafka already ready | Tests run with no unnecessary start/restart. |
| A07 | Kafka unavailable/unhealthy | Bounded diagnosis for unavailable Docker, missing resource, and running-but-not-ready Kafka; no blind restart loop or unrelated mutation. |
| A08 | Similar symptom, different cause | A Kafka-ready test failure caused by application code does not trigger inappropriate infrastructure recovery. An unrelated test suite does not trigger Kafka startup. |
| A09 | Explicit current restriction | `Do not start services in this run` suppresses startup despite the saved default. Tool-denied startup is not bypassed. |
| A10 | Update, deduplication, retirement | Repeated teaching does not duplicate the rule; a deliberate correction supersedes it; retirement prevents later active application. |
| A11 | Inferred experience | Recovery emits a candidate with evidence and uncertainty; unvalidated causal guesses are not promoted into mandatory rules. |
| A12 | Non-Kafka generality | Encoding instruction and a newly taught action-bound rule work without adding a special branch for each rule to the memory engine. |
| A13 | Storage and concurrent access | Approved default roots resolve correctly; project data remains intact; concurrent writes and retried capture preserve all committed records. |
| A14 | Failure truthfulness | Write/retrieval failure is explicit; no false saved/no-match/success acknowledgement. |
| A15 | Bounded context | Unrelated shared records are not injected; retrieval traces show selected IDs/revisions and measured payload size. An applicable mandatory rule cannot be silently lost to top-k or truncation; overflow is resolved or surfaced for the affected action. |
| A16 | Incomplete teaching | Missing resource binding is retained and surfaced; binding supplied once is reused in a later session without guessing or repeated setup questions. |
| A17 | Trigger and dependency discovery | A normal fresh-session test request resolves the stored suite/dependency/procedure relationship before failure, without a Kafka keyword, explicit memory lookup, or custom reminder in the request. An unrelated suite does not match. |
| A18 | Teaching fidelity and conflicts | Conditions, negation, exceptions, and `never restart` survive normalization; a temporary current override leaves the saved default intact. Unresolved incompatible active rules are reported for the affected behavior. |
| A19 | Environment changes and store absence | Shared memory works without project initialization. A machine/context mismatch or changed resource binding prevents applying the wrong procedure. A never-created optional store differs from corruption of an existing one. |
| A20 | Stale remedy and integration bounds | A failed/stale binding is not retried indefinitely, and user intent is preserved. Supported paths show actual pre-action integration; unsupported paths are documented. Memory-tool calls do not recursively trigger themselves. |

For A02, actually terminate the teaching session and start a new host session when host execution is available. A unit test that reloads a store is useful but does not prove end-to-end host behavior. If actual OpenCode/local-model access is absent, supply a runnable validation script/guide and mark the real-host result BLOCKED or NOT RUN. Do not report full acceptance from mocks alone.

Use ordinary user requests in the fresh-session scenarios. A normal persistent host integration may bootstrap retrieval, but the evaluator must not paste remembered content, a rule ID, or an instruction to search Knowledge into the new session. For Kafka, missing binding may be supplied during teaching, then must persist. Verify both recovery behavior and the continued execution/result of the original requested task.

At minimum, validate the implemented store/matching behavior in isolated tests and the host adapter's supported event contract. The final verdict must be **IMPLEMENTED / HOST VALIDATION PENDING** if real-host A01, A02, A05, or A17 is unverified, even when all isolated tests pass. Use **ACCEPTED** only when those end-to-end results and the applicable negative acceptance checks are evidenced. The encoding/generic-rule scenario must also have fresh-session evidence; report its integration level explicitly.

## 10. Evaluation and completion report

Compare controlled baseline and memory-enabled runs from reset fixture state. For the primary scenarios, record:

- Task correctness and final result.
- Failed attempts before successful execution and inappropriate remedies attempted.
- Time spent on diagnosis/recovery and lookup overhead, where measurable.
- Retrieved record count and context payload size.
- Model token usage when exposed by the host, including participating agents when present; mark unavailable metrics rather than estimating them as facts.

Do not claim a speed or quality improvement without measured evidence. Correct cross-session application and avoidance of wrong remedies are the first acceptance goals.

Deliver:

1. Implemented source changes in the supplied repositories, including install/package changes required for them to be usable.
2. A concise architecture/capability map and a list of concrete host integration points.
3. User instructions for teaching, inspecting, updating, and forgetting a rule, with shared/project examples.
4. The acceptance matrix, test commands/results, and fresh-session trace with record revisions, readiness evidence, and test result.
5. Exact limitations, outstanding live-environment checks, compatibility notes, and a reversible rollback procedure that preserves knowledge data.

Include a short coverage table mapping supported host action paths to lookup/enforcement points and known bypasses. This is required to distinguish working bounded integration from a claim that arbitrary future instructions or shell commands are automatically handled.

The user-facing explanation should be in Russian. Code, technical documentation, and task/report artifacts may follow repository conventions. Do not update unrelated improvement registers or unrelated agent architecture as part of this assignment.

## Definition of done

The user teaches an applicable rule once in natural language. Knowledge commits it to the correct durable store. In a later independent session, Harness retrieves it at the relevant action, verifies conditions, performs the permitted behavior, and continues the task. Changed conditions, conflicting instructions, unavailable tools, and failed recovery produce an explicit bounded outcome rather than blind application. The evidence clearly distinguishes implemented mechanisms, isolated tests, and real host validation.
