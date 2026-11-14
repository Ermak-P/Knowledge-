# Knowledge + Harness — P0 execution task

Version: 1.2 · 2026-11-14 · Repository-ready P0

## 1. Mission and execution authority

Build the first working foundation of two reusable products, **Knowledge** and **Harness**, using `inputs/ai-source.zip` in `https://github.com/Ermak-P/Knowledge-` as implementation input and the pinned GitHub application in section 4A as the mandatory realistic test host. Keep the reusable product code separate from that application. The eventual user deployment target is another project, **UMUH**. You do not have to access the user's real IPM or UMUH repository to complete P0.

This is an implementation assignment, not a request for another plan or architecture-only report. Inspect, decide, implement, test, self-review, repair, and produce a reviewable result in one autonomous milestone. Make ordinary reversible implementation decisions yourself and record their rationale. Do not stop after discovery, after writing an RFC, or after generating a list of proposed patches.

The user authorizes changes and test transactions within the supplied development/test workspace. Do not ask for approval of individual files, test-fixture imports, refactorings, or internal steps. Fixture transactions may obtain and apply their exact prepared fingerprints automatically. Preserve the product's explicit transaction-approval contract for normal users.

Pause only for a genuinely missing requirement that changes the agreed outcome, an unavailable essential capability with no reasonable substitute, or an operation outside this test-workspace scope. Missing production IPM data, production credentials, UMUH sources, the broader original AL.zip, original Harness/writer source files, Serena, Roslyn, a local LLM, or native Windows are not by themselves P0 blockers. Use synthetic fixtures and deterministic provider doubles where appropriate; identify exactly what those tests establish.

Do not run the archived runtime configurations against real services, install system services, publish, push, or modify the user's production environments. If this development project is Git-backed, keep changes in that project and use its ordinary repository workflow. Execution is **in place**: do not create Git worktrees or retain worktree execution as a fallback.

## 2. Roadmap and milestone boundary

P0–P3 below are **delivery milestone identifiers**, not changes to the priority labels in any existing improvement register.

| Milestone | Final outcome | External review boundary |
| --- | --- | --- |
| P0 — Working foundation | Independently installable Knowledge, a safe end-to-end add/import/query workflow, lossless legacy-fixture migration, and a minimal read-only Harness consumer | Finish all P0 work, self-check it, then submit one complete review packet |
| P1 — Knowledge completeness | Resumable full-project discovery, incremental discovery, evidence freshness, update/retire/supersede lifecycle, conflict handling, and active/history retrieval | A separate assignment after P0 review |
| P2 — Harness completeness | Agent execution, role/tool permissions, build/test/review enforcement, reliable automatic capture, recovery, and full accounting of Main plus subagents | A separate assignment after P1 review |
| P3 — Portable release | Reproducible installation, Windows verification, upgrade/uninstall/rollback, complete release package, and a UMUH onboarding rehearsal on a separate fixture | A separate assignment after P2 review |

Complete **P0 only**. Design its public contracts with the later milestones in mind, but do not implement a speculative general agent platform, a GUI, a vector database, or every future lifecycle operation. The first milestone must already work; the later milestones must not be prerequisites for its demonstration.

## 3. Product invariants

1. The product names are **Knowledge** and **Harness**. Knowledge is independent; Harness is its first consumer.
2. The target per-project Knowledge directory is `.knowledge`. Harness project configuration/state belongs under `.harness`. Reusable implementation code belongs in packages, not duplicated inside every project's data directory.
3. Knowledge must install and run without Harness, OpenCode, Serena, Roslyn, a model server, or IPM-specific paths.
4. Harness owns agent orchestration, role/tool permissions, retry policy, and agent token budgets. Knowledge owns knowledge records, provenance, retrieval, validation, and its transaction contracts. Bounded retrieval response limits are valid Knowledge API controls.
5. Canonical knowledge, candidate queue, prepared proposals, history, and generated views have explicit owners and distinct semantics. Do not create a second independently writable canonical store.
6. Claims reference identifiable evidence. Confidence, evidence validity, and claim lifecycle are different concepts. Do not silently convert confidence into lifecycle or treat missing evidence as proof that a claim is false.
7. Knowledge is an index of supported statements. A schema-valid record is not proof of truth. Evidence from a source file proves only what that source actually supports; product rationale/business authority is separate.
8. All project-sensitive operations resolve an explicit project identity/root consistently across CLI, MCP, queue, migration, and Harness. Never fall back silently to `C:\Git\IPM` or to another checkout.
9. Preserve stable existing IDs, evidence, provenance, confidence, relationships, candidate statuses, and import history during supported legacy conversion. Do not regenerate IDs from rewritten wording.
10. No automatic Git commits of the user's project changes. Never use destructive reset/clean to simulate transaction rollback.

## 4. Repository inputs: inspect and verify

The implementation repository is <https://github.com/Ermak-P/Knowledge->. Work in its supplied development checkout. The task file is `tasks/Knowledge-Harness-P0-Codex-Task.md`; the legacy input is `inputs/ai-source.zip` with an adjacent `inputs/ai-source-manifest.json` and input README.

Expected input archive SHA-256: `734aa3f4b5231d96f82638c634d41eec445d61ae1eb47c91d076af9a13a81ee4`.

Verify that checksum and inspect the ZIP before extraction. Extract into a disposable source-input directory, preserving `.ai/` as the archive root. Do not extract it over the new product packages or a benchmark's canonical store.

The published package contains **22 source/metadata files**: legacy `.ai/tools` Python modules, four existing test modules, `.ai/schema`, manifest, deployment metadata and README. It contains no project claims/evidence, no durable candidate queue, no transaction journals/plans, no Harness implementation, no manual/automatic candidate writers, and no machine/OpenCode/MSSQL configurations. Some empty scaffold directories are retained. The broader original user archive is intentionally not needed to execute this assignment.

Treat the supplied source as input to audit, not an accepted product. Retain useful existing validator, context/retrieval, MCP and population/transaction code where appropriate; extract/refactor it into the standalone package. A replacement of supplied working mechanisms needs a concrete reason and equivalent or stronger acceptance evidence. Implement the missing coordinated candidate writer/import acknowledgment and minimal Harness consumer against the contracts in this task. Missing excluded source is not a reason to stop or to reduce the agreed P0 outcome.

Context from the earlier full-archive inspection, **not reproducible evidence from this narrow input**: the old automatic writer ignored queue locking; the manual writer deduplicated before taking a lock; global MCP configuration was tied to IPM; some old Harness descriptions still advertised worktrees. Use these as regression scenarios/requirements for the delivered product. Do not claim to have inspected, repaired in place, or proved parity with omitted files.

Facts to establish from the available input include the package's completeness, actual CLI/schema behavior, reusable dependency graph, path/root assumptions, add-only import limits and missing operational documentation. Empty validation does not establish content correctness. Replace missing documentation with accurate documentation of the delivered behavior; never invent historical acceptance reports or missing production records.

Create a concise source map and distinguish **provided/reused**, **provided/refactored**, **newly implemented**, **omitted/unverified legacy**, and **future milestone** capabilities. Map the complete delivered capture → queue → prepare → apply → acknowledgment → retrieval workflow. Compatibility claims must name the actual supplied interface and its executable regression evidence; do not promise compatibility with unobserved private integrations.

## 4A. Mandatory GitHub test host and test layers

Use **NimblePros/eShopOnWeb** as the primary existing-application benchmark:

- Repository: <https://github.com/NimblePros/eShopOnWeb>
- Pinned commit: `0c2c95d9d450d07fcd4e96e95e1cd48c20834e99`
- Immutable source: <https://github.com/NimblePros/eShopOnWeb/tree/0c2c95d9d450d07fcd4e96e95e1cd48c20834e99>
- At this commit, `global.json` specifies SDK `10.0.0` with `rollForward: latestFeature`; `Directory.Packages.props` targets `net10.0`. Resolve a compatible .NET 10 SDK from these actual files and record the exact SDK used. These file inspections are not a claim that the benchmark has already been built in your environment.
- License: MIT; retain upstream copyright/license notices when including upstream material.

The pin deliberately avoids using a moving `main`. The live branch had already changed its SDK requirement to 11.0.100 when this assignment was prepared, despite a .NET 10 README still appearing in web results. Do not follow the README version label without checking build metadata. Do not retarget or mass-upgrade the benchmark merely to make it fit your installed SDK.

Clone it into a dedicated ordinary checkout, for example `benchmarks/eShopOnWeb`, and verify the full commit SHA before any measurement. This is a test application, not the repository in which to bury the reusable Knowledge/Harness implementation. Record the remote, full SHA, actual SDK, baseline Git state, and precise restore/build/test commands in `BENCHMARK-BASELINE.md`. If it is already supplied, verify the same identity and preserve existing user changes; never reset them to obtain a clean baseline.

Use three complementary test layers:

| Layer | Purpose | Required P0 evidence |
| --- | --- | --- |
| Small generated fixtures | Queue races, crashes, malformed input, stale approvals, root isolation and legacy migration | Deterministic automated tests; deliberately constructed records remain clearly synthetic |
| Pinned eShopOnWeb | Real C# dependencies, implementation facts, tests and evidence-backed retrieval in an existing application | Actual build/unit-test baseline, a modest source-verified Knowledge dataset and end-to-end CLI/MCP/Harness queries |
| A distinct later application | Generalization beyond the primary host | Deferred to a later assignment; `dotnet/eShop` is a candidate for service/event coverage, not a P0 dependency |

For P0, do the following on eShopOnWeb:

1. Inventory its actual projects and test projects. Trace representative source in `ApplicationCore`, `Infrastructure`, `Web` and, where present at the pin, `PublicApi`. Do not assume an architecture from folder names alone.
2. Establish restore/build and existing unit-test results before adding Knowledge/Harness integration. `tests/UnitTests/UnitTests.csproj` exists at the pinned revision; discover the exact supported invocation, project references and test runner from its files. Prefer project-scoped commands over launching every UI/container workload. A local, workspace-scoped SDK setup is allowed if needed and feasible.
3. Create a modest dataset of roughly 12–20 useful, independently supportable statements spanning several areas, such as basket behavior, order creation, dependency direction, persistence and API wiring. This is a curated P0 end-to-end dataset, not the P1 full-project discovery implementation. Verify each statement against pinned source and attach precise project-relative paths/symbols/lines and revision identity. Do not pad the dataset to meet a count, and do not import IPM-specific statements as eShop facts.
4. Submit these records through the actual candidate writer → prepare → exact-fingerprint apply → acknowledgment workflow. Do not bypass the implementation by writing canonical demonstration records directly.
5. Define at least eight representative questions with expected supporting claim/evidence IDs, including a no-answer case and an unconfirmed/inferred case. Cover different subsystems, record results across CLI/MCP and the minimal Harness consumer, and use independently checked source expectations. Report wrong, missing, irrelevant and unsupported answers instead of equating nonempty output with retrieval quality. This small regression set does not establish a broad accuracy percentage.
6. Demonstrate isolation from a separate synthetic project and retention of the original application source behavior. In P0, new `.knowledge`/`.harness` integration artifacts are allowed, but application source/test behavior should remain unchanged. Capture before/after tracked-source differences and rerun the required baseline checks.
7. Document external-service requirements separately. Full browser, SQL Server and Aspire/container scenarios are not mandatory for this P0 dataset. Tests using an in-memory database do not prove real SQL Server behavior. Do not deploy Azure resources or configure real identity accounts to complete this benchmark.

If network, SDK or package restoration genuinely prevents execution, finish the independent product work and report the benchmark condition as `BLOCKED`/`NOT_RUN` with an exact cause. Do not replace the mandatory application silently with a hand-written toy or report the realistic-host check as passed. P0 review may assess completed product work, but full benchmark acceptance remains outstanding until executed.

## 5. Required P0 implementation

### A. Repository, packages, and reproducible setup

Inspect the supplied product workspace and the pinned eShopOnWeb test host first. Reuse an appropriate existing product structure or create separate Knowledge and Harness packages. Generate small disposable .NET-style fixtures for controlled safety/migration tests; they supplement the required GitHub benchmark in section 4A and do not replace it.

Create maintainable Knowledge and Harness package boundaries with explicit dependencies and supported runtime versions. Python is a natural default for Knowledge given the existing code; a different choice requires a concrete benefit. Supply locked or otherwise reproducible dependency installation. CLI-only Knowledge usage must not require optional MCP/agent integrations.

Provide one documented verification entry point, usable from a fresh checkout, that returns nonzero on a required failure. Automated tests use disposable roots and do not mutate archived source inputs or a real canonical store. Track implementation progress in a small durable P0 status file so execution can resume after context compaction.

### B. Explicit project resolver

Implement a shared project-root/identity resolver. All integrations must use its result rather than implementing their own unrelated root guesses. Support explicit roots, paths containing spaces and non-ASCII characters, and distinct repositories/checkouts with similar names.

Reject ambiguous or unsafe destinations before mutation. Define symlink/junction, case normalization, relative-path, and path-escape behavior. Test native semantics where available; do not claim Linux tests prove Windows junction or locking behavior.

### C. Standalone Knowledge store and CLI

Expose working equivalents of the following capabilities with documented CLI arguments and machine-readable results:

- Initialize a clean `.knowledge` store without scanning or guessing facts.
- Report version/capabilities and validate the store.
- Submit evidence-backed factual additions to the durable candidate queue through the canonical writer API.
- Prepare a stable preview with a transaction fingerprint and explicit included/skipped/blocked results.
- Apply that exact approved transaction; reject approval for a different or stale plan.
- Acknowledge only candidates proven to belong to the committed import.
- Query/search/context with claim and evidence lookup, provenance, confidence, bounded output, and clear empty/no-match results.
- Inspect transaction state and perform documented recovery.

Separate store initialization from source discovery in the public API. The slash command `/knowledge-init` means full-project discovery/reconciliation; it must not be confused with a CLI operation that only creates directories.

Use a versioned candidate-operation contract. P0 may support only `add`; explicitly reject unsupported `update/retire/supersede` operations. Do not accept and silently ignore lifecycle fields. Reserve a documented evolution path without changing legacy meaning or hash-pinned schemas casually.

### D. One coordinated mutation path

Implement one coordinated writer implementation for both manual submission and the future automatic capture integration. The original manual/automatic writer files are not included in this package; build the shared API and any delivered facades from the explicit contracts here. Every shipped entry point must delegate to the same implementation and protocol.

The read/deduplicate/validate/write decision must be protected as one critical operation. Ensure every participating writer, acknowledgment operation, and queue replacement obeys the same protocol. Handle both concurrency and interrupted writes. Define and test lock ownership/release, contention behavior, and abandoned-operation recovery. Do not implement a retry loop that waits indefinitely.

Prepare/apply/acknowledgment must form a recoverable workflow: an interruption between canonical commit and queue acknowledgment must not lose records or cause a second import. Verify the acknowledged payload or another immutable binding to the prepared candidate, not merely an arbitrary current record sharing its claim ID.

Validate untrusted candidate input before using IDs as paths or accepting records. Return structured failures for malformed records and corrupted queue input; do not silently skip unreadable canonical data or report full success after partial input rejection. Preserve existing valid records on failure.

Retain or implement journaled recovery with accurately documented guarantees. Do not claim cross-file atomicity unless the actual storage mechanism provides it. Recovery must preserve unrelated edits and refuse ambiguous ownership rather than deleting files blindly.

P0 deterministic duplicate prevention must work for stable identity and normalized identical statements, including competing writers. Document that semantic/paraphrase duplicate detection is not established by text hashing alone; broader discovery reconciliation belongs to P1.

### E. Legacy compatibility and fixture migration

Construct a representative nonempty legacy fixture containing confirmed and inferred claims, evidence, relationships/dependencies, a conflict, pending and already-imported candidates, and relevant transaction/history state. Clearly label every synthetic record. Existing proposal samples may inform shapes, but their statements are not verified production facts.

Implement a legacy `.ai` → `.knowledge` migration preview and apply workflow on disposable copies. Produce a machine-readable semantic diff and manifest. Preserve meaningful values and relationships, not merely file counts. An incomplete snapshot with journals but missing plans must receive an explicit incomplete/recovery-required assessment; never synthesize missing historical approvals.

Demonstrate no-op or explicit safe refusal on repeated migration, detection of ambiguous dual stores, source immutability, and restoration from the documented backup/recovery procedure. The supplied empty canonical scaffold must not be treated as a complete production migration fixture. Construct incomplete-journal/missing-plan scenarios explicitly as synthetic fixtures; the actual historical journals were excluded.

Legacy facades must be thin delegations to the common implementation. Document which old interfaces are supported, read-only, or explicitly unsupported. No dual-write compatibility mode.

### F. Retrieval integration and minimal Harness consumer

Provide a read-only MCP adapter using the same resolver and Knowledge implementation as the CLI. Preserve compatible claim/evidence/context concepts where practical. It must not embed one user's username or IPM checkout path. Verify CLI/MCP agreement for two separate project roots.

Implement a minimal Harness read-only Knowledge consumer: resolve the active project, request relevant context with provenance, respect a configured response budget, and return a structured result. Demonstrate that an ordinary read-only Harness operation can continue with a clear degraded result when Knowledge is absent or unavailable. Do not suppress corruption as an apparently successful empty knowledge result.

Document the intended executor/permission boundary for discovery, queue submission, and approved import. Do not solve a missing writer capability by granting Main unrestricted shell/write permissions. P0 does not have to deliver the complete code-changing agent runner; that is P2.

Ship no active executable path that creates Git worktrees. Legacy references may remain only in clearly historical documentation; active descriptions must match in-place behavior. An unimplemented runner must report that capability honestly.

## 6. Required acceptance evidence

Every row must have an executable check, an actual result, and an artifact reference. A statement such as "implemented" or a checklist with unchecked assumptions is insufficient.

| ID | Observable acceptance condition |
| --- | --- |
| P0-A01 | A documented fresh setup installs the delivered packages; Knowledge CLI works without Harness/OpenCode/model services. |
| P0-A02 | A new `.knowledge` store initializes and validates; all shipped/documented files needed for installation are present. Empty validation is not presented as content-quality evidence. |
| P0-A03 | A real fixture source supports a candidate; submit → prepare → approved apply → acknowledgment → query returns the same claim/evidence identity and provenance. |
| P0-A04 | Repeating candidate submission and applying/acknowledging an already committed plan is safe and produces no duplicate knowledge. |
| P0-A05 | A held coordination lock prevents every supported competing queue mutation path, including every delivered manual/automatic-compatible facade. Concurrent equivalent submissions cannot both append duplicates; omitted original writers are not reported as tested. |
| P0-A06 | Malformed records, unsafe IDs/paths, queue corruption, unsupported operations, and stale/wrong fingerprints fail explicitly without corrupting valid data. |
| P0-A07 | Injected interruption during mutation and between commit/acknowledgment is recoverable; retry does not lose candidates or import them twice. Ownership ambiguity and unrelated edits are preserved. |
| P0-A08 | Nonempty legacy-fixture migration preserves IDs, values, evidence, relationships, candidate states and history; semantic comparison passes. Repeat and interrupted migration behavior are demonstrated. |
| P0-A09 | Incomplete legacy snapshots and conflicting dual stores are diagnosed; missing plans/approvals are not fabricated. |
| P0-A10 | Two project roots with similar names remain isolated across CLI, MCP and Harness. Invalid/escaping paths fail before writes. Spaces and non-ASCII paths work. |
| P0-A11 | CLI/MCP lookup agrees; confidence and conflicts/provenance are preserved, unconfirmed facts are not silently promoted, and output bounds are enforced. |
| P0-A12 | The minimal Harness consumer works with Knowledge and degrades explicitly when it is missing; it never reads another project's store as a fallback. |
| P0-A13 | Active shipped configuration/code/descriptions contain no IPM-specific runtime default and no Git-worktree execution path. Project-specific examples are clearly examples. |
| P0-A14 | The full documented P0 check suite passes in the actual available environment; unexecuted platform/real-provider checks are listed separately with exact reproduction commands. |
| P0-A15 | A complete source-and-review packet is generated, excluding credentials, dependency caches, model files, private runtime configs and fabricated benchmark results. |
| P0-A16 | The pinned eShopOnWeb host has a recorded build/unit-test baseline; source-verified records traverse the real import pipeline and answer the eight-question regression set through CLI/MCP/Harness; project isolation and unchanged application source behavior are checked. |

Use synchronization barriers or controlled scheduling for race tests instead of relying on flaky timing alone. Crash tests must exercise meaningful failure boundaries. Do not weaken tests to match defective behavior. Add tests where they establish these contracts; avoid large volumes of tests that only repeat implementation details.

If Windows is unavailable, complete all portable work, provide native Windows test commands/scripts, and record Windows validation as **NOT RUN**, with its consequence for deployment. This permits review of P0 implementation; it does not certify a Windows production release. Likewise, distinguish deterministic adapter/provider tests from actual OpenCode or live-model integration.

## 7. Required deliverables for independent review

Put review artifacts under a stable path such as `reports/P0/` and document the exact path:

1. `P0-REPORT.md`: delivered behavior, before/after examples, key decisions, commands actually run, environment, results, limitations, and remaining milestone scope.
2. `ACCEPTANCE.json`: one record per P0-A01…P0-A16 with `id`, `status` (`PASS|FAIL|BLOCKED|NOT_RUN`), `command`, `evidence`, and explanation. No `PASS` for a check that was not executed. Platform subchecks must retain their own actual statuses.
3. `SOURCE-AUDIT.md`: archive checksum, actual source inventory, capture/import/retrieval call graph, reused/replaced pieces, confirmed defects and resolutions.
4. `CONTRACTS.md`: package boundaries, root identity, CLI/JSON/error/exit behavior, schema versions, confidence/lifecycle distinction, locking, transaction state machine, and legacy compatibility limits.
5. `MIGRATION-REPORT.md`: synthetic-fixture provenance, before/after semantic comparison, incomplete-snapshot assessment, repeat/recovery results, and restore instructions.
6. Raw test results and reproducible fixtures/scripts, plus a concise meaningful change summary or Git diff and source revision when available.
7. A review ZIP containing the changed/new source, tests, fixture generators and documentation needed to reproduce P0 from a fresh checkout. Include an inventory/checksums and required runtime/dependency information. Do not submit logs without implementation source. Reference the checked-in `inputs/ai-source.zip` and its checksum as the original input. No private machine configuration is required.
8. `BENCHMARK-BASELINE.md` and `BENCHMARK-RESULTS.json`: exact eShopOnWeb identity, SDK and baseline commands/results; curated candidates and their provenance; eight-query expectations/results; the application source diff and repeat checks. Include a pinned fetch/setup script and generated Knowledge artifacts so a reviewer can reconstruct the benchmark without relying on your local checkout. If upstream source is included, retain its license.

The final response must identify the delivered source revision/path, exact verification command, actual test summary, review ZIP location, and any failed or unexecuted acceptance conditions. State whether P0 implementation is ready for external review. Do not label the entire Knowledge/Harness product production-ready at this milestone.

## 8. Self-review and stopping rule

Before handing off, review the final diff and trace one addition through every public entry point. Inspect coordination scope, root isolation, migration fidelity, stale approval rejection, interrupted commit/acknowledgment, packaging completeness, and documentation accuracy. Fix defects found within P0 and rerun the affected checks plus the required milestone verification.

Aim to hand over a complete result that can be accepted after one external review and, if needed, one consolidated correction round. Do not require the user to supervise each internal step. Do not claim that this review budget excuses unresolved correctness defects.

Stop after P0 and deliver the complete packet. Do not start P1 without its follow-up assignment. Record actual work accomplished even if an essential acceptance condition remains blocked, with precise evidence and the smallest concrete unblocker.
