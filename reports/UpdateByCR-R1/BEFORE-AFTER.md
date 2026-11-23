# Captured target/proposal behavior

Values are read from the final installed API trace. The target identity is `ucr.b425dc801d9e79e2.retry-limit`.

| Step | Target code attempts | Target revision | Target confidence | Target in default context | Saved identity |
| --- | --- | --- | --- | --- | --- |
| Merged A | 4 | 1 | CONFIRMED | True | `ucr.b425dc801d9e79e2.retry-limit` |
| Open proposal B | 4 | 1 | CONFIRMED | True | `ucr.proposal.e14494b1e2777d03.retry-limit` |
| Closed proposal C | 4 | 1 | CONFIRMED | True | `ucr.proposal.bc99f09b3db49ea5.retry-limit` |
| Merged B present on target | 6 | 2 | CONFIRMED | True | `ucr.b425dc801d9e79e2.retry-limit` |

Full source revisions, receipts and contexts: [raw trace](fixed-probes/test_open_closed_successors_preserve_target_then_merge_updates_same_history.json).

A separate [legacy-plan trace](fixed-probes/test_legacy_unmerged_plan_is_refused_and_recovers_without_target_mutation.json) verifies apply refusal, stale approval on interrupted prepared recovery, preserved target lookup, and replacement of the owned candidate through normal lifecycle APIs.
