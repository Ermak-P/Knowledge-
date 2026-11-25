# Knowledge — Persistence Identity Fix, Duplicate Reconciliation and Scan Recovery

## 1. Objective

Fix the confirmed root cause of the `duplicate-statement` plan blocker, prevent similar defects in other extractor categories, and recover existing completed scan artifacts without requiring a full repository rescan.

Repository: https://github.com/Ermak-P/Knowledge-

Branch:

`codex/knowledge-plan-deduplication-recovery`

Knowledge must remain independent from Agent Harness.

This task supersedes the earlier speculative root-cause investigation. A local agent has now inspected the actual IPM scan artifacts and installed Knowledge implementation.

Verify the reported findings against the current repository implementation before making changes. Installed runtime line numbers may differ from the current branch.

## 2. Confirmed production findings

The local investigation reported:

| Metric | Value |
|---|---:|
| Eligible files | 38,350 |
| Successfully processed files | 38,257 |
| Failed files | 78 |
| Partially processed files | 15 |
| Canonical claims | 697 |
| Canonical duplicate statements | 0 |
| Pending v2 candidate batches | 12,507 |
| Total queue operations | 25,014 |
| Proposed claims | 12,507 |
| Proposed evidence operations | 12,507 |
| Unique proposed claim IDs | 12,507 |
| Duplicate statement groups | 10 |
| Claims belonging to duplicate groups | 26 |
| Redundant claim records | 16 |
| Persistence claims | 49 |
| Ambiguous observations | 451 |
| Coverage gaps | 460 |

All 10 duplicate groups belong to the persistence extractor category.

Duplicates exist within the proposed queue, not within canonical knowledge and not across canonical and proposed knowledge.

Scan state: `COMPLETED_WITH_GAPS`.

Plan state: `BLOCKED`.

Blocker: `duplicate-statement`.

Canonical knowledge has not been modified.

The completed scan and its persisted artifacts must be preserved.

## 3. P0 — Fix persistence claim identity

The reported implementation in `discovery.py` generates a claim identifier using:

```python
identifier = 'scan.' + digest(
    ['identity-v3', project, category, key]
)[:32]
```

The persistence extractor currently uses:

```python
emit(
    'persistence',
    Path(path).stem + ':' + m[1] + ':' + str(m[2]),
    f'{project_name} contains {m[1]}'
    + (f'<{m[2]}>' if m[2] else '')
    + ' persistence/configuration syntax.',
    index,
    m[2] or m[1]
)
```

The identity is file-scoped, while the statement is project-scoped.

Multiple files within the same project calling the same persistence method therefore generate different claim IDs with identical statement text.

The affected syntax includes:

- `AddDbContext`
- `UseSqlServer`
- `UseSqlite`
- `GetConnectionString`

The proposed minimal correction is to remove the file stem from the persistence identity key:

```python
emit(
    'persistence',
    m[1] + ':' + str(m[2]),
    f'{project_name} contains {m[1]}'
    + (f'<{m[2]}>' if m[2] else '')
    + ' persistence/configuration syntax.',
    index,
    m[2] or m[1]
)
```

Treat this as a proposed implementation, not an unconditional requirement.

Verify that:

- Project identity is stable and sufficiently scoped.
- Distinct projects with the same display name remain distinct.
- Different persistence methods remain distinct.
- Different generic arguments remain distinct.
- Equivalent observations from multiple files are safely aggregated.
- Source occurrences retain their individual provenance.
- Repeated occurrences do not become ambiguous observations solely because they originate from different files.

Inspect `equivalent_occurrence()`, `occurrence()` and `proposal()`.

Do not assume that combining occurrences automatically preserves all evidence in the final canonical representation.

Add end-to-end tests proving that every compatible source occurrence survives extraction, aggregation, candidate generation, prepare and apply.

## 4. P0 — Review claim identity invariants across all extractors

Review all deterministic extractor categories for inconsistencies between:

- Claim identity.
- Statement text.
- Semantic scope.
- Subject identity.
- Source location.
- Evidence granularity.

Identify other categories where multiple different claim IDs can produce identical statements.

Also identify categories where different facts can produce the same claim ID.

Do not introduce unrelated identity changes without documented justification and compatibility analysis.

Add regression tests enforcing the intended identity invariants.

## 5. P0 — Defensive duplicate reconciliation

The current discovery pipeline aggregates observations primarily by claim ID.

The reported logic is:

```python
existing = {o['id'] for o in state['observations']}

for o in observations:
    prior = next(
        (
            prior
            for prior in state['observations']
            if prior['id'] == o['id']
        ),
        None
    )

    if prior and equivalent_occurrence(prior, o):
        prior.setdefault(
            'occurrences',
            [occurrence(prior)]
        ).append(occurrence(o))
        continue
```

Implement a deterministic defensive reconciliation stage before final plan validation.

This stage must detect identical statements associated with different claim IDs.

Handle:

- Exact duplicates within proposed candidates.
- Exact matches against canonical claims.
- Compatible evidence belonging to equivalent claims.
- Repeated evidence references.
- Incompatible metadata.
- Identity collisions.
- Scope differences.
- Conflicting confidence or trust classifications.

Automatically reconcile only demonstrably compatible duplicates.

Do not merge claims solely because their normalized statements match.

Inspect the existing `normalized()` implementation, reportedly using NFKC, case folding and whitespace collapsing.

Ensure that normalization does not cause unsafe merging of case-sensitive symbols, configuration values or other semantically distinct statements.

Keep the existing lifecycle and store validation protections.

Do not disable `duplicate-statement` validation.

Do not introduce mandatory LLM calls for deterministic duplicate handling.

## 6. P0 — Recover the existing blocked IPM scan

This is a mandatory acceptance requirement.

The existing completed scan contains 12,507 proposed claims, including 16 redundant claim records across 10 duplicate groups.

Do not require the user to repeat the full repository scan merely to correct these duplicate records.

Implement a supported backend recovery mechanism capable of:

1. Loading existing completed scan artifacts and pending candidate batches.
2. Validating artifact integrity and compatibility.
3. Identifying compatible duplicate groups.
4. Reconciling redundant claim records.
5. Preserving and remapping all compatible evidence.
6. Updating dependent references where necessary.
7. Preserving unrelated candidate operations.
8. Preserving ambiguous observations and coverage gaps.
9. Rebuilding the prepared plan.
10. Generating a valid fingerprint for the corrected plan.
11. Requiring fresh approval before canonical apply.

Prefer rebuilding derived candidates from persisted scan observations where the required information is available.

If the candidate queue is the only recoverable representation, implement a supported, validated reconciliation mechanism for that representation.

Do not arbitrarily keep the lexicographically smallest claim ID and discard all remaining records.

The selected surviving identity must be compatible with future scans and existing canonical references.

Do not lose evidence associated with redundant claim IDs.

Do not require direct manual SQLite modifications.

Do not require the user to edit JSON or JSONL artifacts manually.

Do not silently discard candidate batches.

Provide a dry-run or preview of the proposed recovery.

Any persistent candidate or scan artifact modification must respect the existing authorization model.

Recovery must be transactional or otherwise safely recoverable after interruption.

Repeated recovery must be idempotent.

## 7. P0 — Existing claim ID compatibility

Changing the persistence key changes generated claim IDs.

Analyze compatibility with:

- Existing canonical persistence claims.
- Existing pending candidates.
- Completed scan artifacts.
- Future incremental scans.
- Evidence references.
- Claim relationships.
- Retirement and reconciliation logic.

A future scan must not recreate an equivalent claim solely because an older Knowledge version used a different identity key.

Implement a safe identity reconciliation or migration strategy if required.

Preserve existing canonical identities where necessary to avoid breaking references.

Do not silently retire legacy claims.

Do not silently rewrite canonical data during prepare or recovery.

Document the chosen identity compatibility strategy.

## 8. P0 — Actionable duplicate diagnostics

Expose bounded, structured duplicate diagnostics through existing MCP interfaces wherever possible.

The diagnostic summary must include:

- Total proposed claim operations.
- Unique claim identities.
- Duplicate statement groups.
- Claims affected by duplicate groups.
- Redundant claim records.
- Canonical matches.
- Automatically resolved groups.
- Unresolved groups.
- Evidence preserved or remapped.
- Resulting operation counts.

Individual diagnostic records should include:

- Duplicate group identifier.
- Bounded statement preview.
- Claim IDs.
- Candidate IDs.
- Source files.
- Evidence references.
- Resolution classification.
- Blocking reason.

A local agent must be able to identify the exact reason for a `duplicate-statement` blocker without reading thousands of unrelated operations or inspecting installed Python source code manually.

## 9. P1 — Fix impact diagnostics response budgeting

The local investigation found that the `impact` section is approximately 82,482 serialized JSON bytes.

It contains:

- 697 changed or unverifiable evidence IDs.
- 697 direct claim IDs.
- Zero dependent claims.
- Zero relationships.
- Policy information.

The MCP response budget is approximately 16 KB.

The current endpoint serializes the entire impact object as one aggregate record.

Consequently:

```text
knowledge_scan_diagnostics(section=impact, limit=2)
```

returns:

```text
response-budget-exceeded
```

Implement:

- A compact impact summary.
- Separately paginated impact collections.
- Stable pagination.
- Byte-aware response budgeting.
- Bounded individual records.
- Explicit truncation and continuation information.
- Retrieval of detailed records when necessary.

Preserve backward compatibility where practical.

Do not solve the problem merely by increasing the global MCP response budget.

Investigate why all 697 canonical evidence records were classified as changed or unverifiable.

Verify whether this classification is correct or caused by an overly broad freshness or impact calculation.

Do not weaken source verification requirements to reduce the reported impact.

## 10. P1 — Optimize observation aggregation

The current observation lookup appears to perform a linear search through accumulated observations for each incoming observation.

This may cause quadratic behavior on large scans.

Inspect the actual execution path and profile the implementation before changing it.

If confirmed, replace repeated linear searches with an indexed lookup, such as:

```python
observations_by_id = {
    observation['id']: observation
    for observation in state['observations']
}
```

Maintain the index consistently during:

- Observation insertion.
- Occurrence aggregation.
- Ambiguous observation handling.
- Observation removal.
- Scan checkpoint restoration.
- Scan recovery.
- Incremental processing.

Preserve deterministic output ordering.

Do not introduce stale indexes or change extraction semantics.

Benchmark the existing and optimized implementations.

Report the measured improvement rather than claiming a theoretical speedup as an observed result.

## 11. P1 — Knowledge quality assessment

The local investigation classified most extracted claims as good quality because they have stable identifiers and source-bound evidence.

However, factual correctness and knowledge usefulness are separate properties.

Representative extracted claim:

```text
FrontendSP declares class NewContentTemplateButton
with declared bases BaseNewButton.
```

This is structural source-code information.

It may duplicate information already available through structural analysis tools such as Serena and Roslyn.

Analyze the current extraction pipeline and classify representative claims into:

- Structural code facts.
- Architecture knowledge.
- Business rules.
- Behavioral constraints.
- Integration contracts.
- Configuration knowledge.
- Infrastructure knowledge.
- Duplicate or low-information statements.

Investigate whether generic claims such as:

```text
Project contains GetConnectionString
persistence/configuration syntax.
```

provide sufficient practical value to a coding agent.

Report available aggregate statistics and representative examples.

Do not classify every nonduplicate claim as high-value knowledge.

Do not automatically remove existing knowledge.

Do not introduce arbitrary claim limits.

Propose a separate configurable admission or knowledge-quality policy if the investigation demonstrates a need for it.

Do not make this investigation a prerequisite for recovering the blocked plan.

## 12. P1 — Structured syntax extraction failures

Investigate the separate issue involving 78 failed files and 15 partially processed files.

Reported error:

```text
EXTRACTION_FAILED
stage: structured-syntax
retry_eligible: false
```

Review support for:

- JSON with comments.
- Trailing commas.
- UTF-8 BOM.
- Unsupported encodings.
- Invalid JSON.
- Configuration-specific JSON dialects.

Distinguish unsupported inputs from extractor defects.

Where safe, support targeted reprocessing without repeating the complete scan.

Preserve accurate coverage reporting.

This is a separate issue and must not delay the P0 duplicate recovery.

## 13. Regression tests

Add automated regression tests covering:

1. Multiple files calling `GetConnectionString` within one project.
2. Multiple files calling `UseSqlServer` within one project.
3. Different persistence methods.
4. Different generic arguments.
5. Different projects with identical display names.
6. Preservation of all compatible source occurrences.
7. Preservation of evidence through candidate generation and apply.
8. Existing legacy persistence claim IDs.
9. Duplicate statements with different claim IDs.
10. Compatible and incompatible duplicate metadata.
11. Canonical matches.
12. Duplicate evidence references.
13. Case-sensitive identifiers.
14. Recovery of completed scans.
15. Recovery of scans completed with gaps.
16. Recovery of legacy candidate artifacts.
17. Recovery idempotency.
18. Interrupted recovery.
19. Preservation of unrelated candidates.
20. Stale approval rejection.
21. Canonical state remaining unchanged during prepare.
22. Canonical apply idempotency.
23. Oversized impact diagnostic records.
24. Stable diagnostics pagination.
25. Observation aggregation and index consistency.
26. Large-scale scan and plan preparation performance.
27. Existing Knowledge database compatibility.
28. Windows upgrade compatibility.

Create a synthetic production-scale regression fixture containing:

- Approximately 40,000 file records.
- 12,507 proposed claims.
- 697 canonical claims.
- 10 duplicate statement groups containing 26 claim records.
- 16 redundant claims.
- Compatible evidence from multiple source files.
- Partial processing failures.
- Persisted completed scan artifacts.

Verify that recovery preserves evidence and removes the 16 redundant proposed claim records without changing unrelated candidates.

Do not assume that the private IPM repository is available in the Codex environment.

## 14. Performance benchmarks

Measure before and after implementation:

- Observation aggregation time.
- Duplicate detection time.
- Plan preparation time.
- Recovery time.
- Peak memory usage.
- Diagnostics response size.
- SQLite query count where measurable.

Avoid quadratic duplicate detection and repeated full repository inventory during recovery.

Use reproducible benchmark fixtures.

## 15. Safety requirements

- Never bypass lifecycle validation.
- Never apply a blocked plan.
- Never silently discard valid evidence.
- Never silently promote claim confidence.
- Never merge incompatible claims automatically.
- Never modify canonical knowledge during prepare.
- Never allow stale approval to authorize a changed plan.
- Never restart a full scan automatically.
- Preserve project and global knowledge boundaries.
- Preserve existing source verification requirements.
- Preserve accurate scan coverage.
- Keep Knowledge independent from Harness.

## 16. Deliverables

Deliver:

1. Verified root cause analysis.
2. Persistence extractor identity fix.
3. Extractor identity invariant review.
4. Defensive duplicate reconciliation.
5. Supported recovery of existing blocked scan artifacts.
6. Legacy claim identity compatibility strategy.
7. Actionable duplicate diagnostics.
8. Automated regression tests.
9. Performance benchmark results.
10. Updated documentation.
11. Windows installation and upgrade instructions.
12. Exact recovery commands or MCP calls for the existing IPM scan.
13. Remaining limitations and risks.

Report P0 and P1 completion separately.

If any issue remains unresolved, state it explicitly.

Do not report tests against synthetic fixtures as validation against the actual private IPM repository.

## 17. Acceptance criteria

P0 is complete only when:

- The reported persistence identity defect is reproduced and fixed.
- Compatible duplicate claims are safely reconciled.
- All valid evidence is preserved.
- Legacy claim identities remain compatible.
- Existing completed scan artifacts can be recovered without full rescanning when the required data is available.
- Recovery does not modify canonical knowledge.
- The recovered plan has a valid fingerprint.
- Old approvals cannot authorize the recovered plan.
- Unresolved conflicts remain explicit blockers.
- Duplicate diagnostics identify the actual affected claims.
- Required regression tests pass.
- A supported recovery procedure is documented.

Complete P0 before starting optional P1 improvements.

Do not consider the task complete merely because the persistence extractor has been changed. The existing blocked scan must have a safe recovery path.