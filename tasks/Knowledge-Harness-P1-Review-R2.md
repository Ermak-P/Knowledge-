# Knowledge + Harness — P1 independent review, round 2

Date: 2026-11-15.

Repository: https://github.com/Ermak-P/Knowledge-

Reviewed branch: `p1`.

Reviewed commit: `a767c744cc771541e4b3727ff15b8cd526657ba6`.

Previous reviewed commit: `2a8664821d0f6512ecbce92280e25d6f19b3f32c`.

## Decision

**P1 is not accepted yet. Complete this narrow follow-up for A and B, then return fresh evidence. Keep P2 untouched.**

The original reproductions for R1–R5 now behave correctly. The source exclusions, historical-assertion ownership, qualified identity handling, reintroduction proposals and ignored-source provenance repairs are substantive. Do not undo them or restart the project. Two defects remain in the corrected implementation: the new reactivation path simulates a different state from the state it commits, and the new whole-scope ambiguity validation bypasses bounded discovery.

Implement the corrections autonomously, retain the shared transaction path, P0 compatibility, root isolation, immutable history, exact approval and conservative source semantics. Preserve legitimate later work. No store resets, deletion of history, automatic canonical changes during discovery, merge or deployment.

## Independently verified results

- All **93 product tests** passed, including the 75 earlier tests and 18 correction regressions; no skips.
- Both wheels built, and dependency-free standalone Knowledge passed packaging verification.
- The current source/run/artifact gate passed. All **86 ZIP members**, inventory hashes, external SHA-256 and corresponding current checkout bytes matched.
- Repeated original adversarial scenarios confirmed: excluded live `build/Independent.cs` remains an SDK Compile item and is no longer proposed for retirement; the reviewed historical assertion is preserved; distinct namespace types retain separate histories; a returned retired declaration generates a new proposal; ignored source is labeled working-tree/ignored rather than committed.
- Fresh discovery on an independent copy of pinned eShopOnWeb produced **529 observations**. All five source-backed natural-language questions found their expected answers with ordinary defaults: 10 claims, 16,000 bytes.
- Submitted before/after TRX files each contain 49 passed out of 49, zero failed/unexecuted. These are verified submitted artifacts; no independent application build/test pass is claimed in this round. The review environment's previously identified WebAssembly task-host limitation remains separate from product findings.

## A — High: `reactivate` preview and committed state disagree

Location at the reviewed commit: `packages/knowledge/src/knowledge/lifecycle.py`, `simulate()` lines 91–112, compared with `apply_item()` lines 119–124.

The target-state check recognizes `reactivate`, but the state/payload transition does not:

```python
if action in ('update','add'):
    current[i]=(change['kind'],change['payload']); states[i]={'lifecycle':'active'}
else:
    states[i]={'lifecycle':'superseded' if action=='supersede' else 'retired', ...}
```

Consequently simulation leaves a reactivated record retired and validates its old payload. Actual application writes the new payload and activates it. Validation/approval therefore concerns a different resulting model from the model committed.

### Reproduced invalid batch accepted

1. Discover/import the synthetic fixture and select its `Independent` declaration claim A.
2. Explicitly retire A through an approved version-2 batch. The source can remain present: manual retirement is supported and source reappearance is not required to demonstrate the transaction bug.
3. Add reviewed replacement claim B with A's same statement, a different ID, and its own correctly linked evidence. A is inactive, so the resulting current view has only B for that statement and the batch is accepted.
4. Run discovery again. It proposes reactivation of A from the still-present source.
5. Prepare, approve, apply and acknowledge.

Actual independently executed result:

```json
{
  "prepare_ok": true,
  "before": "retired",
  "apply_state": "COMMITTED",
  "active_identical_statement_ids": ["scan.…", "synthetic.replacement"],
  "validate_ok": true
}
```

There are now two active claims with the identical normalized statement. The duplicate invariant was bypassed because simulation excluded A from its active set. `validate()` also blesses this invalid state because the duplicate check is not part of the common canonical-model validator.

### Reproduced valid batch rejected

1. Start again with retired claim A and a distinct active claim B.
2. Submit one explicitly reviewed batch: reactivate A; update B's `depends_on` to include A; add the matching relationship B → A. Use current expected revisions and valid payloads.

The intended final graph has two active claims and a valid active dependency. Actual preparation returns:

```json
{"ok":false,"blocked":[{"code":"active-dependent-needs-reviewed-change","details":"B's ID"}]}
```

Simulation wrongly considers A retired, so it rejects the valid reviewed closure.

### Required result

Simulation and actual application must derive the same resulting records, lifecycle states and successor/graph semantics for every supported action, including reactivation of claims and relationships. Validate the proposed reactivation payload, not the old payload. Preserve retired-only target restrictions, expected revisions, source bindings and new explicit approval.

Apply common canonical invariants consistently, including normalized uniqueness of active statements, so ordinary store validation cannot report success for the duplicate state above. Preserve allowed historical duplicates/inactive payloads and legitimate old receipts; do not weaken the invariant to make the test pass. An already-invalid store must be reported honestly and any repair must be explicit/audited, not silently destructive.

Required regressions:

1. Replacement B plus proposed reactivation of A cannot create duplicate active statements; preview rejects the conflict before writes and leaves history unchanged.
2. The valid mixed reactivation/dependency/relationship batch prepares and applies successfully, and preview/current/history agree.
3. Invalid proposed reactivation payloads, cycles/orphans and inactive successor/endpoint problems are rejected by the resulting-model checks; they are not accepted at preview and discovered only after mutation starts.
4. Reactivation of a retired relationship is evaluated as active against its final endpoints. Wrong/stale approval, interrupted apply, recovery and historical retries remain safe.
5. `validate()` rejects a deliberately constructed active duplicate while retaining supported historical/inactive records. This corruption fixture is test-only; do not reset real user data.

Original acceptance affected: P1-A06, A07, A09, A13 and reviewed graph closure in R4.

## B — Medium: bounded discovery re-extracts the whole tree on every chunk

Location: `packages/knowledge/src/knowledge/discovery.py`, the unconditional `analysis_scope(...)` call in `scan()` and `analysis_scope()`'s loop over all snapshot files.

Whole-scope ambiguity checking is valuable. Its current integration defeats the scan's bounded-work control: after processing the requested chunk, `scan()` extracts every included file again through `analysis_scope()`, including on a fresh empty store where there is no canonical evidence to revalidate.

### Independent reproduction

Use `test_p1.fixture` plus twenty small additional `.cs` files under `Tests`, for 28 inventory files. Wrap `discovery.extract` with an observer that records its path argument while delegating unchanged to the real extractor. Do not modify product source.

Call `scan(max_files=1)`, then resume that scan with `max_files=1`.

Observed:

| Call | Requested max files | Actual extract calls | Distinct files extracted | Durable processed files |
| --- | ---: | ---: | ---: | ---: |
| Initial | 1 | 29 | 28 | 1 |
| Resume | 1 | 29 | 28 | 2 |

The checkpoint advances one file, but both invocations redo extraction over all 28 files. On a large repository, repeated small chunks still repeatedly incur whole-repository analysis. This is a product resumability/work-bound regression, not a demand to avoid necessary snapshot enumeration or hashing.

### Required result

Keep extraction/ambiguity work genuinely bounded and durably reusable across scan/resume calls. Reuse snapshot-bound observations and ambiguity groups, or use another explicit bounded validation phase. Discovery must not hide a full extraction pass outside the work accounting on every call. Preserve global collision detection: a later file revealing a collision must withhold the entire ambiguous group, and stale source/extractor policy must still invalidate or revalidate safely. Read-side ambiguity/freshness must remain honest.

It is acceptable to distinguish snapshot hashing/enumeration from bounded extraction and to expose separate explicitly bounded phases. It is not acceptable to redefine `max_files` as a checkpoint counter while still re-extracting all source on each call, or to remove ambiguity validation and start trusting the first occurrence again.

Required regressions:

1. A fresh scan and resumed scan with a small extraction bound do not each call the real extractor over the whole included scope. Include a larger-than-chunk fixture and record the actual work performed.
2. Full completion over several chunks gives the same observations/proposals as a supported full run, without repeating already completed extraction unnecessarily or requeueing unchanged proposals.
3. A collision appearing in a later chunk is withheld correctly; no arbitrary first entity becomes trusted. Preserve source drift, killed-process checkpoints, P0 compatibility and immutable history tests.

Original acceptance affected: P1-A04 and section 4.3 bounded work controls.

## Handoff / definition of done

Keep the scope to A and B and their necessary invariants/compatibility. Add meaningful regressions for the concrete cases above. Retain all 93 existing tests and corrected R1–R5 behavior. Run fresh packaging, the full product suite, real-source discovery/questions at ordinary defaults, and the supported application verification in the implementation environment. Regenerate the source-bound run, reports, acceptance/correction mapping, ZIP inventory and SHA-256 after the final source changes.

Do not reuse the reviewed PASS packet as evidence for changed code. Report the exact committed revision and packet location. Mark P1 submitted for external review, leave P2 untouched, and return the completed result without seeking permission for each routine implementation step.
