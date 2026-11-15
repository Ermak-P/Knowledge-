# Knowledge + Harness — P1 execution task

Version: 1.0 · 2026-11-15

## 1. Mission, accepted baseline and autonomy

Implement **P1: complete the Knowledge discovery and lifecycle workflow** on top of the accepted P0 foundation. Deliver working code, meaningful tests, actual verification results and one complete review packet. This is an implementation assignment, not a request for a new plan or an architecture-only report.

- Repository: <https://github.com/Ermak-P/Knowledge->
- Accepted P0 branch: `codex/knowledge-harness-p0`
- Accepted P0 commit: `a3c7ac7afd7cff6137b916832cf40019ca8b8c87`
- P0 acceptance: portable foundation; independent review passed 43 product tests and closed R1–R4. Native Windows and live-provider integration were not certified.
- Existing inputs: `inputs/ai-source.zip`, the accepted packages/tests/scripts, and the pinned eShopOnWeb setup. The original AL.zip, production IPM, UMUH and private machine configuration are not required.

First verify your development checkout contains the accepted commit. `main` may still contain only the earlier task/input preparation; do not implement P1 on that older scaffold or discard P0. Preserve user changes and use an ordinary development branch/checkout. No Git worktrees, production changes, automatic merge, push or deployment. Temporary synthetic Git fixture repositories may create commits to test revision ranges; that does not authorize committing the user's application changes.

Work autonomously through design, implementation, tests, self-review and repairs. Make routine reversible decisions yourself and record important choices. Do not ask for approval at every internal step or stop after generating a plan. Approved fixture transactions may automatically approve their exact prepared fingerprints for tests; normal product use must retain explicit approval of the precise transaction.

Stop only for an essential missing capability with no reasonable substitute or a requirement ambiguity that changes the agreed final outcome. The absence of a live LLM, OpenCode, Serena, Roslyn MCP or native Windows does not block portable implementation. State precisely what deterministic tools and test doubles establish. Never describe a mock-backed check as live integration.

## 2. Final outcome and scope

At the end of P1, a user must be able to:

1. Initialize a project's Knowledge store and run a real full-project discovery pass.
2. Interrupt that pass and resume from durable progress without losing completed work or emitting duplicate candidates.
3. Discover incremental additions/changes from a verified revision range or working-tree delta.
4. Inspect evidence-backed additions and proposed changes to existing knowledge.
5. Review and approve one exact transaction containing supported add, update, retire, supersede and associated relationship changes.
6. Retrieve the current supported view by default and inspect earlier versions/history explicitly.
7. Run a full reconciliation against current source, including the removed-component case, without false retirement or physical deletion of history.

Knowledge remains independent; its per-project directory is `.knowledge`. Preserve the accepted common resolver, package boundaries, one coordinated writer/storage path, provenance, structured errors and approval/recovery guarantees. SQLite is an accepted foundation; no storage rewrite is requested.

**P1 does not include** the P2 code-changing agent runner, broad tool/role orchestration, live automatic session capture, a GUI, vector infrastructure, cloud deployment, production IPM migration or final Windows release certification. Harness changes are limited to consuming the correct active/history/freshness view and preserving its response budgets. Keep P0's `runner: not-implemented` behavior honest.

## 3. Inspect P0 and define the extension contract

Read the accepted implementation and contracts before editing. In particular inspect `store.py`, `migration.py`, `retrieval.py`, `project.py`, CLI/MCP/Harness adapters, `scripts/evidence.py`, `verify.py`, `make_review.py`, and the P0 correction tests.

Document a concise implementation contract and then implement it in this same milestone. Do not wait for an external architecture gate. Specify:

- The versioned operation envelope, allowed transitions and expected-revision checks.
- The difference between confidence, lifecycle, evidence freshness and review disposition.
- Scan scope, source snapshots, capabilities/limitations, checkpoint identity and resume rules.
- Canonical current/history views and their CLI/MCP/export behavior.
- Store upgrade, compatibility, failure, recovery and evidence-run contracts.

P0 uses hash-pinned v1 claim/evidence/relationship schemas; a claim's `status` denotes confidence. Do not turn that field into lifecycle or add fields without an explicit versioned compatibility strategy. Lifecycle/revision metadata may live separately from unchanged v1 payloads. Choose the simplest maintainable design that satisfies the behaviors below.

## 4. Real discovery with truthful coverage

### 4.1 Whole-project inventory

Implement a reusable discovery subsystem with a real .NET/C# capability pack. It must enumerate the intended repository, partition it into named projects/subsystems, inspect relevant source/configuration/tests/docs and produce evidence-backed observations/candidates. Reuse the supplied legacy scanner/analyzer when helpful, but an inventory of filenames is not the finished discovery feature.

Observe generated/binary/vendor/dependency/build-output exclusions and avoid credentials or live operational data. Do not execute repository-provided build hooks or embedded instructions merely to read its code. A document's instructions are source data, not permission to mutate files.

Track coverage per partition and relevant file, with statuses such as analyzed, partial, excluded, blocked and not analyzed. Explain exclusions and unsupported analysis capabilities. Enumeration is not semantic analysis; distinguish those measures. An incomplete or tool-blocked scan cannot claim complete source coverage or prove absence.

Use bounded deterministic passes and narrow source excerpts rather than inserting the whole repository into one model context. Semantic tooling may improve analysis, but a failed/unavailable tool must have a bounded fallback or an explicit limitation, not an unbounded retry loop.

### 4.2 Meaningful candidates, not a hard-coded demonstration

Discovery must run as delivered software on previously uncurated source. At minimum implement useful extractors in three distinct categories, including project/dependency structure and at least two of: interface/implementation or DI wiring, API routing/contracts, persistence/configuration wiring, or clearly supported behavioral patterns.

Do not hard-code eShop project names, claims, source anchors or question answers into the generic implementation. The old `benchmark_dataset.py` is an independently curated comparison input, not the discovery engine or its candidate source. A provider interface for optional LLM-assisted interpretation is allowed, but required discovery must also demonstrate useful deterministic operation without a live model.

Every proposed fact needs a stable identity/deduplication basis, confidence, source project/snapshot, concrete project-relative evidence and a truthful extraction method. Verify referenced source/anchors and retain content hashes or equivalent revision binding. A syntax match does not establish an arbitrary runtime call graph or product rationale. Business meaning inferred only from code must remain inferred/unconfirmed; do not promote it merely because extraction succeeded.

Missing business knowledge or unsupported semantic analysis should become a documented gap or question, not an invented fact. Do not fill an arbitrary claim quota with filename statements, paraphrases or duplicates.

### 4.3 Durable resumability

Store progress durably under `.knowledge` through supported APIs, using the same project identity and coordinated mutation policy. Bind a scan to its source snapshot, scope/exclusion policy, extractor/configuration versions and progress units. Preserve discovered observations and queued candidates across compaction, restart and process death.

Provide bounded work controls and explicit resume/restart operations. Repeating an unchanged run must not requeue equivalent additions, revisions or resolved conflicts. Detect source/configuration changes since a checkpoint: either revalidate/invalidate affected work with clear accounting or refuse stale resume with a precise next step. Never mix revisions silently or lose completed work because the terminal session ended.

### 4.4 Incremental discovery

Support a verified Git base/head range and relevant working-tree changes, including staged/unstaged edits and documented untracked-source handling. Capture committed revision and dirty-file hashes separately; do not label uncommitted evidence as committed HEAD.

Account for renamed/deleted sources and dependency/consumer effects beyond the directly changed file. Compare against a known baseline; do not mark an unchanged unexamined partition freshly verified. A no-Git file snapshot mode is optional and must state its absence/history limitations.

Scans may write checkpoints, observations, candidate queue and reports. They must not mutate application source or silently apply canonical knowledge changes.

## 5. Versioned lifecycle operations

Implement supported operations equivalent to:

| Operation | Required behavior |
| --- | --- |
| Add | Import new evidence-backed facts without duplicate identities or equivalent unchanged candidates. |
| Update | Create a new revision of the same logical claim, preserving its ID and prior payload/provenance/evidence history. |
| Retire | Remove a claim from the current active view through a reviewed lifecycle transition; retain retrievable history. |
| Supersede | Link an old claim to an identified successor, transitioning the active view and preserving both histories. A successor may be added in the same transaction. |
| Relationship change | Update affected dependencies/conflicts/relations consistently, with history and expected-version checks. No disconnected silent side edits. |

The operation contract must bind target IDs, expected claim/store revisions or fingerprints, proposed payload/state, supporting evidence and reasons. Validate before writes. Unsupported fields/versions and ambiguous targets fail explicitly. Preserve existing P0 v1 add behavior or provide an explicit, tested compatibility facade; no divergent writer.

Add review dispositions needed to reject or defer a candidate so one unresolved proposal does not permanently poison every unrelated valid batch. Persist the exact reviewed payload/disposition and reason. A later full scan must not endlessly rediscover an unchanged rejected/deferred proposal as new. Changed evidence can justify a new clearly identified revision of that proposal.

### 5.1 History and idempotency

Keep immutable revisions/receipts sufficient to explain what was known, changed, approved and applied. Store capture time, verification time, source snapshot and reviewer/import provenance distinctly where relevant. Do not backdate a new observation as an old verification.

P0 `_verify_committed` compares imported payloads against the current canonical rows. A legitimate later update would invalidate that simple comparison. Extend the transaction/receipt model deliberately: historical apply/ack retries must remain safe after later authorized revisions, without reverting current state or treating old approval as permission for a new change. Define whether a pending old acknowledgment blocks later edits or how revision ownership proves it. Test the complete sequence, not just a one-operation fixture.

History is not a second writable canonical store. No physical record deletion or blind overwrite is an acceptable scan/retirement side effect.

### 5.2 Graph and dependent knowledge

Compute affected dependent claims and relationships when a claim/evidence source changes or is retired. Preserve graph integrity, detect cycles/orphans/conflicting successors and explain proposed dependent changes. Mentioning a removed component does not automatically make every related claim obsolete.

Keep appropriate historical references valid while excluding retired/superseded current-state assertions from ordinary active retrieval. Validate the full revision/relationship model and the resulting current view. Do not satisfy the old validator by deleting historical evidence or leaking historical rules back into the active view.

## 6. Evidence freshness and full reconciliation

Implement a full reconciliation/Full Update preview across existing Knowledge and the intended current source snapshot. Classify each relevant current claim with an explicit supported outcome such as unchanged, changed, contradicted, suspected obsolete, proposed retirement/supersession or not verifiable.

Evaluate evidence existence, source/content identity and anchor validity. A changed file is a reason to recheck; it is not automatically a false claim. An unrelated edit with still-valid evidence must not cause spurious retirement. A missing file, failed search or unavailable language server alone is insufficient proof of deletion.

Use positive corroboration and adequate scope for retirement: before/after changes, consumers/references, registrations, interfaces/API/config/deployment contracts, replacements and relevant tests/docs as available. If the source cannot prove external/runtime availability, mark that limit. Preserve historical statements that remain true as history.

Freshness/review state must influence retrieval honestly without silently rewriting confidence. Known stale/contradicted/unverified-current evidence must be flagged and excluded from a trusted-current default where appropriate; exact policy must be documented and tested. Re-verification can retain a still-true claim with new evidence/revision history instead of replacing its ID.

### Required removed-component regression

Create a realistic synthetic .NET fixture containing an `ExternalManagement`/EM-like component, registrations, an API or consumer, configuration and dependent claims. Capture a before state, then completely remove/replace the component in a controlled after state.

The expected pipeline is: discover/reconcile → propose exact revisions and dependent effects → inspect preview → approve fingerprint → apply/acknowledge → query current/history. A new sentence “EM is removed” beside still-active “EM exists” assertions is not a successful resolution.

Also test a historical removal statement, a still-valid independent claim mentioning EM, incomplete scan/tool failure, stale evidence without proved removal, and an external deployment fact not verifiable from the checkout. No mass retirement by text matching.

## 7. Safe preview, approval, apply, recovery and store upgrade

All discovery/lifecycle/import entry points must use the accepted shared resolver and coordinated writer/transaction path. Keep bounded lock contention and idempotent retries. Preparation is a reproducible preview; approval binds the exact source/canonical/queue state and proposed operation payloads. Concurrent changes require an actionable stale-plan result, not a blind retry with old approval.

Commit each approved operation batch, revision history, graph/lifecycle changes and transaction receipt consistently. Test interruptions before commit, during a mixed-operation batch, after canonical commit and during acknowledgment. Recovery must leave either the previous complete state or the new complete committed state; preserve unrelated edits and ambiguous ownership for review. An explicit approved reversal is a new audited change, not deletion of historical receipts.

Upgrade a nonempty accepted P0 store using a documented versioned preview/apply/backup/recovery procedure. Preserve P0 canonical values/IDs, confidence, evidence, relationships, queue identities/statuses/bindings, import/migration history and supported old approvals. Do not reconstruct an empty database and call it an upgrade. Reject unknown versions and incomplete upgrades safely. Existing unsupported external legacy JSONL must still refuse explicitly unless a separate lossless adapter is actually implemented and tested.

## 8. User-facing commands and retrieval

Deliver actual supported CLI/API operations for full scan/start/resume, incremental scan, reconciliation preview, candidate review/disposition, approved lifecycle apply, active/history lookup and status/coverage inspection. Choose clear exact CLI names and document JSON schemas, stable error codes and exit behavior.

For the OpenCode-style command interface, preserve these intended roles with thin documented adapters/examples:

- `/knowledge-init`: whole-project initial discovery plus reconciliation. It may initialize a new empty store when appropriate; it never silently migrates an existing legacy store or applies canonical changes.
- `/knowledge-candidates-update`: incremental discovery/candidate submission from current work or a supplied revision range.
- `/knowledge-candidates-push`: review/prepare and exact-fingerprint approved application.

Retain older aliases only as documented delegation to one implementation if needed; do not create competing semantics. Store initialization (`knowledge init`) remains distinct from full source discovery. Real OpenCode host installation/live execution remains P2/P3 work; functional CLI adapters and their tests must be real in P1, not markdown pretending to implement the backend.

Update CLI/MCP/Harness reads so ordinary context uses the supported current view and explicit history access exposes prior revisions/lifecycle/provenance safely. Maintain bounded actual serialized application payloads, including Unicode and errors; no duplicate structured output that defeats the response budget. Preserve no-answer/partial/budget results and project isolation. Read tools must not silently perform reconciliation/apply or grant new shell/write permissions.

## 9. Real application and controlled source-change evaluation

Continue using the accepted immutable eShopOnWeb baseline:

- <https://github.com/NimblePros/eShopOnWeb>
- Commit `0c2c95d9d450d07fcd4e96e95e1cd48c20834e99`
- Resolve the SDK from the existing pinned setup; do not follow moving `main`, retarget the app or weaken upstream tests.

Run real discovery on that source. Demonstrate useful generated facts across at least three application areas/projects and three extractor categories, with concrete anchors and no reads of the curated dataset as discovery input. Independently inspect a representative generated subset against source. Record coverage, candidate counts, duplicates/conflicts/gaps and quality limitations; a count alone is not accuracy.

Evaluate at least five ordinary source-grounded questions from the automatically generated/imported dataset, plus no-answer and unconfirmed/history cases. Expectations must be checked independently of the output being scored, and queries must not simply embed generated claim IDs. Report incorrect/unsupported results and abstentions explicitly. The old curated P0 regression remains useful but cannot substitute for this new discovery evaluation.

Use a separate disposable source copy or generated .NET fixture for controlled changes: addition, behavior/wiring change, rename, deletion and a dependency impact. Keep the immutable benchmark source unchanged. Show baseline discovery, incremental detection, lifecycle preview/application and current/history query behavior. Do not create Git worktrees. Synthetic snapshot/patch provenance must be explicit.

Retain the 43-test accepted P0 regression behavior and add meaningful P1 checks. Repeat dependency-free packaging and relevant real stdio tests. Reproduce pinned application build/unit results before/after integration in the available prepared environment. Preserve supported single-node build/restore settings and diagnostics. An unavailable SDK/network/task host is reported as an actual blocked check, not replaced with old PASS logs or weakened application tests.

## 10. Acceptance conditions

Every condition needs executable evidence and an actual outcome. Tests should exercise observable contracts and meaningful failure boundaries, not mirror implementation details.

| ID | Observable acceptance condition |
| --- | --- |
| P1-A01 | Work derives from the accepted P0 commit; installation/package independence and accepted regression behavior are preserved. |
| P1-A02 | Delivered generic .NET discovery produces independently verified useful candidates in three extractor categories across at least three application areas/projects, without consuming hard-coded curated facts. |
| P1-A03 | Full inventory reports truthful per-partition/file analysis coverage, exclusions and tool/capability limits; incomplete analysis cannot report full success or prove absence. |
| P1-A04 | Bounded scans survive actual process interruption/restart, resume completed work and observations, and detect changed source/configuration at resume. |
| P1-A05 | Incremental revision/working-tree scans detect additions, changes, renames, deletions and dependent effects with correct snapshot provenance; unchanged reruns add no duplicate operations. |
| P1-A06 | Add/update/retire/supersede/relationship operations are versioned, validated and usable through the real shared pipeline; unsupported or conflicting input fails explicitly. |
| P1-A07 | Preview/dry-run leaves canonical state and source unchanged; wrong/stale approval and concurrent modifications cannot apply a different transaction. |
| P1-A08 | Nonempty P0 store upgrade preserves IDs/values/evidence/queue/history and is safe on repeat, interruption, unknown version and recovery; no empty-store substitution. |
| P1-A09 | Claim revisions and evidence history remain retrievable; old apply/ack retries remain safe after legitimate later updates and never revert current state. |
| P1-A10 | The complete removed-component fixture resolves active old assertions and affected dependencies after approval; appending a removal sentence alone fails the check. |
| P1-A11 | False-retirement regressions preserve historical/independent/external facts and refuse conclusions based only on missing search results, tool failure or partial coverage. |
| P1-A12 | Evidence freshness handles unchanged anchors, unrelated edits, changed behavior, renamed/missing sources and re-verification without automatic confidence promotion. |
| P1-A13 | Current/history graph views remain consistent across dependent changes; default context excludes retired/superseded assertions and exposes confidence/freshness/conflicts/provenance accurately. |
| P1-A14 | Reject/defer/review dispositions persist with payload/reason identity; valid work remains processable and unchanged refused/resolved proposals are not emitted endlessly. |
| P1-A15 | Competing writers and real interrupted mixed-operation apply/ack tests prove transaction/recovery safety, idempotency and preservation of unrelated edits. |
| P1-A16 | Functional CLI and documented command adapters execute the backend; CLI/MCP/Harness agree semantically and actual wire byte budgets/errors/Unicode/project isolation remain correct. |
| P1-A17 | The pinned real-source discovery evaluation, independent question expectations, controlled source-change scenario and source-immutability checks are reproducible; curated P0 facts are not passed off as discovered facts. |
| P1-A18 | Current P1 verification is bound to one completed run and exact source/evidence identities; failed, interrupted, stale-source, mixed-run and missing-artifact attempts cannot generate a success packet. |
| P1-A19 | Required portable regression/packaging, real stdio and pinned build/unit checks have actual fresh outcomes. Optional native/live checks remain separately classified, never silently passed. |
| P1-A20 | Complete source, tests, fixtures, contracts, run evidence and a checksum-verified review ZIP are delivered; every claim of completion is traceable to executed acceptance evidence. |

No arbitrary claim count, static PASS template or old report satisfies these conditions. A blocked required check remains blocked even if most implementation is complete. Do not interpret the goal of one review plus one correction round as permission to conceal a defect.

## 11. Verification provenance and review delivery

Use a durable P1 status/checkpoint file to survive your own context compaction. Keep implementation progress distinct from product scan checkpoints and from verified acceptance.

Place new milestone results under `reports/P1/`. Preserve P0 evidence as historical evidence for the accepted source; do not overwrite it to imply it verified changed P1 code. Reuse/refactor the corrected run ledger with explicit milestone/check definitions. Start every attempt in a non-success state and bind commands, return codes, outputs and expected artifacts to that attempt/source. A packet must refuse failed/incomplete/mixed evidence and source changes after verification.

Deliver:

1. `P1-REPORT.md`: concrete behavior, important decisions, before/after examples, environment, actual results and remaining limits.
2. `P1-CONTRACTS.md`: operation/schema/store versions, lifecycle vs confidence/freshness, graph/history semantics, scan/resume/source identity, API/errors and approval/recovery/upgrade guarantees.
3. `ACCEPTANCE.json`: P1-A01…P1-A20 with PASS/FAIL/BLOCKED/NOT_RUN, exact executable command, evidence reference and explanation, tied to one real run. Platform/live subchecks remain separate.
4. `DISCOVERY-REPORT.md` and machine-readable results: scope, capabilities, partition/file coverage, source manifest, automatically generated candidates, checkpoint/resume and delta results, verified representative facts and independent question evaluation.
5. `LIFECYCLE-REPORT.md`: removed-component and false-retirement fixtures, mixed-operation previews/applies, expected/current/history results and dependency effects.
6. `UPGRADE-RECOVERY-REPORT.md`: nonempty P0 upgrade semantic comparison, preserved data/history/queue, interrupted upgrade/apply/ack results and restoration instructions.
7. Reproducible verification entry point, raw run-scoped results, source inventory/revision/identity, meaningful change summary, and `P1-review.zip` with verified member checksums.

The packet must contain enough implementation source, tests, fixture generators and setup instructions to reproduce P1 from a fresh checkout. Include pinned benchmark fetch details and required licenses; exclude credentials, private machine settings, dependency caches, SDKs/models and fabricated data. Mark synthetic fixtures and generated observations explicitly.

Before handoff, self-review the full diff and trace one discovered fact through scan/checkpoint → candidate → exact approval → update/retire/supersede → acknowledgment → current/history retrieval. Inspect false absence, source drift, pending old acknowledgments, dependency closure, upgrade recovery, actual adapter serialization and current-run evidence refusal. Fix defects found within P1 and run affected checks plus the required milestone verification.

Your final response must identify the delivered source revision/branch, exact verification command, actual test results, P1 report/acceptance/ZIP paths and every outstanding failed/blocked/not-run condition. Submit P1 for independent review; do not mark it externally accepted or start P2.
