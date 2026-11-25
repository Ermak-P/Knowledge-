# Knowledge — Plan Deduplication, Diagnostics and Scan Recovery

## 1. Objective

Fix Knowledge plan preparation so that duplicate statements do not unnecessarily block the entire knowledge update workflow.

Implement deterministic duplicate detection and safe reconciliation, improve diagnostics, and allow existing completed scan artifacts to be reused after upgrading Knowledge.

Repository: https://github.com/Ermak-P/Knowledge-

The solution must be project-independent and applicable to large repositories, including IPM and UMUH.

## 2. Observed production issue

A real Knowledge scan of the IPM repository produced the following results:

- Eligible files: 38,350.
- Successfully processed files: 38,257.
- Failed files: 78.
- Partially processed files: 15.
- Scan state: `COMPLETED_WITH_GAPS`.
- Processing complete: `true`.
- Writer is no longer active.
- Proposed add operations: 25,014.
- Plan state: `BLOCKED`.
- Blocker: `duplicate-statement`.
- Canonical knowledge remains unchanged.

Additional issues:

- `knowledge_scan_diagnostics` does not expose actionable duplicate-statement details.
- The `impact` diagnostics section returns `response-budget-exceeded` even with `limit=2`.
- Semantic preflight succeeds but does not resolve the plan validation blocker.
- The local agent attempts to inspect thousands of operations through paginated MCP requests.
- The existing workflow provides no efficient recovery path for this situation.

The exact source of duplicate statements has not yet been established. Do not assume that duplicates originate exclusively from canonical knowledge, scan extraction, or repeated file processing.

## 3. P0 — Root cause investigation

Locate and analyze the code responsible for:

- Scan extraction and aggregation.
- Candidate identity generation.
- Statement normalization.
- Claim identity generation.
- Canonical knowledge lookup.
- Plan construction.
- Plan validation.
- `duplicate-statement` blocker generation.
- Scan checkpoint persistence and recovery.

Determine whether duplicate statements can originate from:

- Multiple source files describing the same fact.
- Multiple extractors processing the same source.
- Scan retries or resumed scans.
- Candidate aggregation.
- Existing canonical claims.
- Repeated evidence references.
- Statement normalization collisions.
- Plan construction defects.
- Concurrent or interrupted operations.

Reproduce the issue using automated tests before implementing the fix.

Do not require access to the private IPM repository. Use synthetic fixtures that reproduce the observed conditions.

## 4. P0 — Deterministic duplicate detection

Implement or correct deterministic duplicate detection before final plan validation.

Duplicate detection must cover:

1. Duplicates within the same prepared plan.
2. Duplicates between proposed claims and canonical knowledge.
3. Repeated evidence references.
4. Repeated candidates resulting from scan retries or recovery.
5. Duplicate claims with different candidate IDs.

Reuse existing statement identity and normalization rules where appropriate.

If normalization rules are insufficient, introduce a documented, versioned normalization strategy.

Normalization must not accidentally change the meaning of statements, including:

- Case-sensitive identifiers.
- Negations.
- Numeric values.
- Configuration values.
- Code symbols.
- Scope and project boundaries.

Do not introduce mandatory LLM calls, embeddings, or semantic similarity checks for exact duplicate detection.

Use efficient indexing or hash-based grouping instead of quadratic pairwise comparisons.

## 5. P0 — Safe duplicate reconciliation

Implement the following behavior:

| Scenario | Expected behavior |
|---|---|
| Identical new claims with compatible metadata | Consolidate into one claim |
| Identical claims with different valid evidence | Preserve and combine compatible evidence |
| Repeated evidence | Deduplicate evidence references |
| Exact match with an existing canonical claim | Do not create another claim |
| Existing canonical claim with additional valid evidence | Prepare an evidence update where supported |
| Identical statement with incompatible metadata or scope | Report an explicit unresolved conflict |
| Semantically similar but non-identical statements | Do not automatically merge |
| Contradictory statements | Preserve conflict detection and review requirements |

Preserve:

- Claim identity.
- Source provenance.
- Evidence references.
- Source hashes.
- Confidence classification.
- Review status.
- Trust boundaries.
- Project and global knowledge boundaries.
- Existing approval requirements.

Never silently promote an inferred claim to `CONFIRMED`.

Never silently discard conflicting metadata or valid evidence.

Exact duplicates that can be safely reconciled must not block the entire plan.

Unresolved or unsafe duplicate groups must remain explicit blockers.

## 6. P0 — Reuse existing completed scans

The existing completed scan of approximately 38,350 IPM files must not need to be repeated solely because the plan preparation implementation has changed.

Implement or repair the recovery workflow so that Knowledge can:

- Open existing persisted scan artifacts.
- Validate their integrity and compatibility.
- Rebuild a prepared plan using the corrected deduplication logic.
- Preserve completed extraction results.
- Preserve scan failures and coverage gaps.
- Generate a new plan fingerprint.
- Request fresh approval before applying the corrected plan.

Support both `COMPLETED` and `COMPLETED_WITH_GAPS` scan states, subject to existing safety and coverage policies.

If persisted artifacts require migration, implement a safe and versioned migration.

Do not silently invalidate existing completed scans.

Do not automatically start a fresh scan.

If recovery is impossible for a particular artifact version, report the precise incompatibility and available recovery options.

## 7. P0 — Actionable duplicate diagnostics

Extend existing plan or scan diagnostics to expose structured duplicate information.

Prefer extending existing MCP tools over introducing unnecessary new tools.

The diagnostics must provide:

- Total proposed operations.
- Total unique statements.
- Number of duplicate groups.
- Number of affected operations.
- Duplicates within the prepared plan.
- Matches against canonical knowledge.
- Duplicate evidence references.
- Automatically reconciled groups.
- Unresolved duplicate groups.
- Number of resulting add operations.
- Number of resulting evidence updates.
- Number of skipped duplicate operations.

For individual duplicate groups, provide bounded details:

- Group identifier.
- Statement or bounded statement preview.
- Statement hash.
- Candidate IDs.
- Claim IDs.
- Source file paths.
- Evidence references.
- Duplicate classification.
- Resolution status.
- Blocking reason, if applicable.

The local agent must be able to understand the cause of a blocked plan without reading thousands of unrelated operations.

## 8. P1 — Fix diagnostics response budgeting

Investigate and fix the following observed behavior:

`knowledge_scan_diagnostics(section=impact, limit=2)`

Result:

`response-budget-exceeded`

Implement:

- Compact diagnostic projections.
- Byte-aware response budgeting.
- Bounded statement and evidence previews.
- Stable pagination.
- Explicit truncation indicators.
- References for retrieving individual detailed records.
- Aggregate summaries that do not require full record serialization.

A single oversized record must not make the entire diagnostic section inaccessible.

Do not silently truncate information required for review or approval.

Do not solve the problem merely by increasing the maximum MCP response size.

## 9. P1 — Plan preparation progress and observability

Large plan preparation operations should expose useful progress information.

Provide structured progress events or status fields for:

- Loading scan artifacts.
- Loading canonical knowledge.
- Normalizing statements.
- Detecting duplicate groups.
- Reconciling duplicate claims.
- Reconciling evidence.
- Validating operations.
- Building the final plan.
- Generating the fingerprint.

Where applicable, include:

- Processed operations.
- Total operations.
- Duplicate groups detected.
- Duplicate groups resolved.
- Remaining operations.
- Elapsed time.
- Current processing stage.

Reuse the existing progress reporting infrastructure.

Do not introduce artificial progress percentages or excessive logging.

## 10. P1 — Knowledge extraction quality assessment

Investigate why the IPM scan generated approximately 25,014 add operations.

Determine whether the current extraction pipeline can produce excessive amounts of low-value knowledge, including:

- Mechanical descriptions of classes and methods.
- Repeated configuration descriptions.
- Boilerplate.
- Generated code descriptions.
- Facts already available through structural code analysis.
- Repeated descriptions of the same architectural behavior.

Provide aggregate extraction statistics and representative examples.

Distinguish between:

- Architecture knowledge.
- Business rules.
- Behavioral constraints.
- Integration contracts.
- Configuration knowledge.
- Infrastructure knowledge.
- Structural source-code facts.
- Duplicate or low-value extracted statements.

Do not introduce arbitrary claim limits.

Do not automatically delete existing canonical knowledge.

Any changes to extraction or admission policies must be separately documented, justified, and tested.

Knowledge should complement structural analysis tools rather than become an unnecessary duplicate source-code index.

## 11. P1 — Structured syntax extraction failures

Investigate the reported extraction failures affecting JSON and configuration files.

The observed failure classification is:

- Error: `EXTRACTION_FAILED`.
- Stage: `structured-syntax`.
- Retry eligible: `false`.

Determine whether failures can originate from:

- JSON with comments.
- Trailing commas.
- UTF-8 BOM.
- Unsupported encodings.
- Invalid or incomplete syntax.
- JSON configuration dialects.
- Extractor implementation defects.
- File size restrictions.

Add regression tests for supported input formats.

Do not silently treat invalid or unreadable files as successfully processed.

Preserve accurate coverage reporting.

Where safe, allow targeted reprocessing of failed files without requiring a complete repository rescan.

## 12. Approval and safety requirements

Maintain the existing approval model.

The corrected implementation must guarantee:

- `prepare` does not modify canonical knowledge.
- A blocked plan cannot be applied.
- Rebuilding a plan generates a fingerprint corresponding to the corrected plan.
- Approval of an old plan cannot authorize a changed plan.
- Applying a plan requires valid approval.
- Canonical state changes invalidate stale approvals where required.
- Failed apply operations do not leave partially updated canonical knowledge.
- Repeated apply requests cannot create duplicate claims or evidence.
- Existing source verification and coverage safeguards remain intact.

Do not bypass validation to make the reported problem disappear.

## 13. Performance requirements

The solution must work efficiently for large repositories.

Create a synthetic benchmark containing at least:

- 40,000 source file records.
- 25,000 proposed claim operations.
- Existing canonical claims.
- Exact duplicate groups.
- Duplicate evidence.
- Conflicting metadata.
- Partial scan failures.
- Recovered scan checkpoints.

Measure and report:

- Plan preparation wall-clock time.
- Duplicate detection time.
- Reconciliation time.
- Peak memory consumption.
- SQLite query count where measurable.
- Diagnostics response size.
- Performance before and after the fix.

Avoid:

- Quadratic duplicate detection.
- One database query per proposed statement where batching is possible.
- Repeated full repository inventory during plan preparation.
- Mandatory LLM-based duplicate detection.
- Thousands of MCP pagination requests for root cause analysis.
- Unnecessary repeated filesystem traversal.

Do not claim a performance improvement without benchmark evidence.

## 14. Required regression tests

At minimum, implement tests covering:

1. Duplicate statements within a single plan.
2. Duplicate statements with different candidate IDs.
3. Duplicate statements across multiple source files.
4. Matches against canonical claims.
5. Additional evidence for an existing claim.
6. Duplicate evidence references.
7. Conflicting metadata.
8. Different statements that must not be merged.
9. Negated statements that must remain distinct.
10. Case-sensitive identifiers.
11. Repeated scan checkpoints.
12. Interrupted and resumed scans.
13. Recovery of existing completed scan artifacts.
14. Recovery of `COMPLETED_WITH_GAPS` scans.
15. Plan fingerprint changes after reconciliation.
16. Rejection of stale approvals.
17. Canonical state remaining unchanged during prepare.
18. Apply idempotency.
19. Oversized diagnostic records.
20. Stable diagnostics pagination.
21. Large-scale plan preparation.
22. Existing Knowledge database compatibility.
23. Windows installation compatibility.
24. Structured syntax extraction edge cases.
25. Targeted retry of failed extraction where supported.

Run the existing test suite and report all failures.

Do not hide unrelated regressions.

## 15. Implementation constraints

- Keep Knowledge independent from Agent Harness.
- Do not introduce IPM-specific paths or assumptions.
- Maintain compatibility with existing MCP consumers.
- Preserve compatibility with existing Knowledge databases and supported scan artifacts.
- Prefer Python standard library and existing dependencies.
- Avoid unnecessary new dependencies.
- Preserve Windows compatibility.
- Do not modify unrelated Harness functionality.
- Do not redesign unrelated components.
- Do not introduce a mandatory semantic model dependency.

## 16. Deliverables

Create a dedicated Git branch:

`codex/knowledge-plan-deduplication-recovery`

Deliver:

1. Root cause analysis.
2. Backend implementation.
3. Automated regression tests.
4. Large-scale benchmark results.
5. Database and scan artifact compatibility assessment.
6. Updated MCP diagnostics documentation.
7. Recovery instructions for existing installations.
8. Windows installation and upgrade verification.
9. List of modified files.
10. Remaining limitations and risks.

Include exact commands or MCP calls required to recover an existing blocked plan after installing the corrected Knowledge version.

The recovery procedure must not require a fresh full scan unless artifact incompatibility is explicitly demonstrated.

## 17. Acceptance criteria

The task is complete when:

- The root cause of `duplicate-statement` is established and documented.
- Exact duplicates are deterministically detected.
- Safely reconcilable duplicates no longer block plan preparation.
- Valid evidence and provenance are preserved.
- Unsafe conflicts remain explicit blockers.
- Existing completed scan artifacts can be reused when compatible.
- Canonical knowledge remains unchanged until an approved apply operation.
- A corrected plan receives a valid fingerprint.
- Duplicate diagnostics are actionable and bounded.
- Oversized impact records no longer make diagnostics inaccessible.
- Large-scale benchmark results are available.
- All required regression tests pass.
- Existing installations have a documented upgrade and recovery path.

Complete P0 requirements before starting P1 improvements.

Report P0 and P1 results separately.

Do not mark the task as complete if any P0 acceptance criterion remains unresolved.