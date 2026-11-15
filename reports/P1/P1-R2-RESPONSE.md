# P1 independent review round 2 — A/B correction

Run `fe11fd6fd62e4372b5d6e830889775be`; source `f6fbbd3dc18cfe085c3694bd6ab529f23e5eb7ac7b0c54bb450083bb33069954`. Raw evidence: `runs/fe11fd6fd62e4372b5d6e830889775be/`.

Reviewed commit: a767c744cc771541e4b3727ff15b8cd526657ba6. Branch: p1.
Submitted for external review; not accepted. P2 untouched.

| Finding | Implementation | Fresh executable evidence | Result |
| --- | --- | --- | --- |
| A | One resulting_record transition for simulation/commit; common active-statement uniqueness in validate_model | 8 tests in test_p1_r2.py; current product-tests.log and round2.json | PASS |
| B | Reuse durable snapshot-bound observations/ambiguities; no hidden analysis_scope extraction in scan | 3 tests in test_p1_r2.py; actual extractor call measurements in round2.json | PASS |

All 93 existing tests are retained; 104 total tests passed without skips.
Before repair the new focused suite reproduced the duplicate acceptance, valid
closure rejection, common-validation omission and whole-tree extraction defects.
The final tests run real extraction/tools/persistence, not success substitutes.

A: preview and apply use the same payload/state/successor transition, including
claim and relationship reactivation. Retired-only target, expected revisions,
source bindings and exact new approval remain. Duplicate normalized active
statements now fail ordinary canonical validation too; inactive/historical
duplicates remain valid. Tests reject new-payload orphans/cycles, inactive
successors/endpoints and mixed v1/v2 aliases; accept reviewed mixed closure; and
exercise actual process death during write, after commit and during acknowledgment.
Old approved receipts remain retryable without reverting later revisions.
A deliberately corrupt duplicate fixture is diagnosed and preserved. No real
store reset or silent repair is performed; invalid existing data requires a
separately reviewed/audited repair or consistent backup restoration.

B: on a 28-file fixture, each initial/resumed
max_files=1 call performs exactly one real extract call. Total completed extraction
calls: 28; each path once; unchanged
completed rerun: 0 calls. The observer
delegates unchanged to the real extractor. Snapshot enumeration, hashing and scope
metadata policy checks remain whole-snapshot and are explicitly outside this
extraction budget. No canonical candidate is emitted until the complete bounded
scope is known; a late collision removes all ambiguous observations, including
those from earlier chunks. Partial evidence is not labeled freshly verified.
Read-side context/reconciliation still performs honest whole-scope validation;
it does not grant writes or claim to be a bounded discovery chunk. Existing v3
observation checkpoints remain reusable; work accounting is additive version 1.

Fresh packaging, real stdio/budgets/isolation, process/race, P0 upgrade and R1–R5
regressions passed. Pinned application build and 49 tests before/49 after passed;
five source questions passed with ordinary defaults (10 claims / 16,000 bytes).
The ZIP, inventory and source/run gate are regenerated from final source.
Native Windows, live OpenCode/model, browser/SQL Server/Aspire remain NOT_RUN.
