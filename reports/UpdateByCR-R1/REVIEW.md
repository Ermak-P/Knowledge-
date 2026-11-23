# /update-by-CR — R1 corrections

All four findings in the independent R1 review are addressed. The correction
keeps the existing command/backend split, record schemas and normal
candidate/plan/apply/acknowledge APIs. No new database, inference dependency or
application rollout is introduced.

Implementation revision: `b57f5e8c26992c5bd95cf8d22b46f1a9f485187d`.
Source identity: `4ce84bd346cad8fa0bd3177617c7b718984372524556b37360ebf3fddb34a0b0`.
Started clean at reviewed head `3c9d1ed6aa`; current main was checked at
`b1e88a848`. Work remains on `codex/update-by-cr`, in place, without worktrees,
merges, user IPM writes or global OpenCode/model changes.

## Corrections

| Finding | Result and implementation |
| --- | --- |
| UCR-R1-01 (P1) | Unmerged/closed proposals use stable `ucr.proposal.*` IDs scoped to project/CR/PR/key. Their statement also names the PR and head. The current target ID, confidence, revision and default retrieval remain unchanged. Explicit existing-ID updates and retirement from unmerged PRs refuse before queue/canonical writes. After merge on the selected target, the original target ID updates normally, preserving history; supported merged retirement remains available. |
| UCR-R1-02 | Refresh/reanalysis retains the complete superseded proposal ownership in sealed workflow history. Replacement preparation records its intent before deferring owned pending candidates through `lifecycle.dispose`. Resume survives a hard process exit after disposition. Unrelated candidates are checked before any disposition and remain unchanged. Interview revision in the batch reason prevents reuse of an already-deferred candidate after sources change and then return to earlier content. |
| UCR-R1-03 | Nonchange validation compares the actual pinned excerpt/range at base and head with the selected anchor. Other members may change. Optional explicit base/head range mappings support moved members. Both pins, paths, range lengths and excerpts are validated; the containing files retain full hashes and normal freshness guards. Changed anchored contracts still refuse. |
| UCR-R1-04 | Both new and resumed native workflows use one transactional chat-binding path. Completed historical bindings detach while receipts/history survive. Completed receipts marked stale remain historical; genuinely unfinished sourced workflows still block rebinding. A pre-R1 completed+active duplicate resolves to its one active workflow on the next command. No read-time migration is introduced. |

The optional anchor mapping and revised ownership/identity behavior are documented
in the packaged [UPDATE-BY-CR contract](../../docs/P4/UPDATE-BY-CR.md).
Existing workflow metadata remains version 1 with the same fields. The additional
history events reuse the bounded existing history list. Core claim/evidence
schemas, current denials, approval/CAS, project isolation and FULL synchronization
are preserved.

## Executed checks

* **39 focused tests PASS**: the existing 27 and 12 R1 regression methods.
  [Focused log](local/focused.log).
* **401 final-source full installed Linux regressions PASS**: 390 PASS,
  11 Windows-only SKIP, no failures/errors
  ([raw results](local/full-tests.json), [log](local/full-regressions.log)).
* **400 intermediate installed Linux regressions PASS** at `e60b7e48d4`:
  389 PASS, 11 Windows-only SKIP, no failures/errors
  ([raw test results](qualification/tests.json), [log](qualification/regressions.log)).
* **12 installed Knowledge-only R1 probes PASS**, with neither Harness nor MCP
  available. [Result](fixed-probes/result.json). The captured JSON per method
  contains actual before/after records, canonical receipts, default/optional
  context, queue dispositions, revision history and retained workflow state.
  These execute normal installed APIs in synthetic Git projects outside checkout.
* [Installed byte proof](installed-bytes.json) verifies all **61** packaged assets
  against the exact Git revision and two installations outside checkout.
  ZIP SHA-256: `7cb633e1823e36e3436dd43a19529ca36002717a922850d4e657ba4fbd121090`.
* The sequential-native test invokes the **published plugin hooks and installed
  CLI through Node**, starts the next pair in the same chat, repeats without
  arguments, recreates the plugin, and explicitly resumes B. A's receipt remains
  independently accessible. The separate [real OpenCode 1.19.6 R1 run](native/result.json) also passes
  the complete controlled interview/save, starts B in the same native session,
  repeats without arguments, explicitly resumes B and preserves A's receipt.
  Raw native messages and logs are retained; the responder is controlled.

The intermediate installed Linux route at `e60b7e48d4` is **PASS_PORTABLE**, all **25 commands PASS**,
with unchanged inputs ([complete raw run](qualification/run.json)). It includes
upgrade/recovery, .NET behavior, Knowledge-only, uninstall/reinstall and the full
400-test suite. Its source-bound CI also passes both platforms (Linux 389 PASS/11 SKIP,
Windows 400 PASS), retained in `qualification/ci-intermediate`.

The [final-source full local qualification](qualification-final/run.json) is
**PASS_PORTABLE**, all **25 commands PASS**, unchanged inputs. Its 401 tests
include the additional legacy-plan guard: **390 PASS, 11 Windows-only SKIP**.
Final-source CI receipts remain pending; intermediate results are not relabelled
as final.

The additional regression constructs a valid pre-R1 pending plan through normal
Store APIs. Before the final guard it reproduced the unsafe write
(`failures/legacy-plan-before-guard.log`). Apply now refuses it, interrupted
prepared recovery clears stale approval without a canonical write, and explicit
source reobservation replaces its owned candidate safely. Already committed
history is never rewritten automatically.

## Raw proof by finding

* [Target/proposal/merge trace](fixed-probes/test_open_closed_successors_preserve_target_then_merge_updates_same_history.json): A stays at confirmed revision 1 while distinct open and closed proposals are saved. After B actually merges, the same A ID advances to confirmed revision 2; proposal revisions remain separate.
* [Explicit-ID and retirement refusal](fixed-probes/test_explicit_existing_id_and_retirement_cannot_bypass_proposal_scope.json) and [merged retirement](fixed-probes/test_merged_retirement_still_uses_supported_revision_history.json).
* [Refresh/crash recovery](fixed-probes/test_refresh_owns_old_candidate_and_recovers_hard_crash_during_disposition.json), [head/target refresh](fixed-probes/test_head_target_refresh_prepares_and_applies_without_manual_queue_repair.json), [unrelated queue preservation](fixed-probes/test_refresh_never_disposes_unrelated_pending_candidate.json), and [source roundtrip](fixed-probes/test_refresh_roundtrip_does_not_reuse_already_deferred_candidate.json).
* [Same-file unchanged member](fixed-probes/test_unchanged_member_in_modified_file_is_saved_and_changed_member_refused.json) and [mapped moved member](fixed-probes/test_explicit_base_head_ranges_support_shifted_contract_and_reject_wrong_pin.json).
* [Chat binding/history](fixed-probes/test_same_chat_binding_is_unique_with_history_resume_and_active_conflict.json) and [native-hook restart/resume](fixed-probes/test_native_hook_sequential_reviews_survive_plugin_restart.json).

The unchanged audit archive is retained with its original before-fix probes and
evidence. [Audit input verification](audit-input.json) checks all 18 SHA256SUMS
entries; archive programs were read, not executed. The new probes test corrected
behavior rather than expecting the old defects. Development failures and a
report-capture helper name collision are retained under `failures/`; final
installed probes pass after those corrections.

The first full installed Linux attempt ran all 400 tests but hit one
`harness-busy` error while the existing supervisor-death test polled SQLite during
startup (`failures/qualification-first/`). Harness and that platform test were
unchanged by R1. Its isolated repeat passed in 1.286 seconds
(`local/platform-retry.log`); the complete official route then passed unchanged.
The failed full ledger remains retained
and is not labelled PASS.

Live-model semantic replay is **NOT_RUN**. R1 includes both installed hook/CLI
checks and a real native OpenCode 1.19.6 run with a controlled responder. These
verify protocol and persistence behavior, not arbitrary-model decision equivalence. No live tracker
or production data mutation is claimed. There is no unrelated SQLite work.

[Reproduction](REPRODUCE.md) includes the official installed qualification routes
and hash-verified CI transport. The candidate version remains `0.5.0rc1`; use
the source/package hashes to identify this correction's bytes.
