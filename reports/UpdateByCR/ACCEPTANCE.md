# Acceptance evidence

Code/source binding is in [source.json](source.json). `F` below means an actual
test from `test_update_by_cr.UpdateByCR` in [27 passing focused tests](local/focused.log);
the replay test is `test_update_cr_replay.UpdateCRReplay`. Tests use real temporary
Git repositories, SQLite and normal APIs; subprocess cases are identified.

| ID | Executed result and evidence |
| --- | --- |
| UCR-01 | PASS: real native command with no/one/two links, later foreground links and resume (`native/result.json`, `*-messages.json`); F `missing_links_reused_inputs_and_russian`, `published_host_hook_uses_stdin_and_real_user_turn`. |
| UCR-02 | PASS for supported exports/controlled GitHub adapter: F `azure_and_tfs_provider_exports_resolve_without_sdk`, `github_paginated_sources_and_postmerge_base_resolution`, URL/repository mismatch and unavailable tool tests. Live tracker access is BLOCKED/NOT_RUN, not claimed. |
| UCR-03 | PASS: F `real_code_inspection_and_anchored_nonchange_questions`; `trial/*-dialogue.json` inspection contains actual base/head/target files and neighbors; checked in decision map and references. |
| UCR-04 | PASS: anchored Transport/Caller and ILookup questions, actual answers and saved reasons in both worked dialogues and fresh retrieval. |
| UCR-05 | PASS: F `existing_explanation_avoids_redundant_question`, incremental answer/unknown/correction tests; `existing/result.json` reuses actual saved Knowledge IDs/revisions and returns no redundant questions. |
| UCR-06 | PASS: F `apply_acknowledge_and_fresh_process_retrieval`; both installed dialogues reach `saved` through exact-plan apply/ack, with canonical revision-1 IDs and fresh process retrieval. |
| UCR-07 | PASS: F `answer_dedup_and_correction_history`, `unknown_and_future_preference_are_not_historical_certainty`; unresolved remains UNKNOWN, future preference unconfirmed, no executable instruction. |
| UCR-08 | PASS: real plan/schema validation in save tests, immutable source/user explanation artifacts and pinned target-file evidence in `trial/*-export.json`; corrupt artifact refuses; source paths do not treat URLs as files. |
| UCR-09 | PASS: F `unmerged_and_closed_are_scoped_not_target_facts`, `changed_head_invalidates_analysis_keeps_bound_answers`, `exact_approval_and_canonical_cas`, `recovery_after_commit_reports_newly_stale_code`; merged worked results verified against actual target. Remote reobservation is required. |
| UCR-10 | PASS: F `repeated_completed_command_is_deduplicated`, answer delivery dedup and hard-exit recovery; native later-link completion reuses the known pair and new-chat resume preserves its identity. |
| UCR-11 | PASS: F `canonical_update_uses_existing_identity_and_history` advances the same ID to revision 2 and retains history; session/source CAS rejects stale continuation. Existing full suite also covers competing canonical revisions. |
| UCR-12 | PASS: F `partial_coverage_truthfully_saves_independent_facts`, unknown/finish tests, explicit GitHub attachment/check limitations and inspection mismatch refusal. Incomplete material does not establish absence/nonchange. |
| UCR-13 | PASS: F `restart_before_apply_and_after_commit_no_duplicate_revision`, `process_crash_frontiers_recover_without_duplicate_application` use new processes/os._exit and durable preparation/approval/commit/ack recovery. Native new-chat resume also passes. |
| UCR-14 | PASS: malformed map/unavailable tool preserves progress; corrupt session/artifact refuses; `provider/result.json` executes a real process timeout and oversized response. No automatic reset. |
| UCR-15 | PASS: F `unrelated_candidates_are_not_approved_or_disposed` preserves the queue exactly; wrong plan/session/source fingerprint refuses. Preparation does not approve unrelated work. |
| UCR-16 | PASS: F `url_credentials_mismatch_and_source_prompt_injection` and native hook malicious argument marker test; source cannot approve a plan or execute arguments. User-turn matching is an ingress boundary; the trusted local CLI is not an OS sandbox. |
| UCR-17 | PASS: F `two_roots_and_code_freshness_no_cross_project_authority`, existing-nonempty correction and backup/export tests; full baseline suite exercises shared isolation/current denials/read-only integrity. No schema migration on read. |
| UCR-18 | PASS: `installed-bytes.json` proves final installed assets; `independent/result.json` demonstrates actual Knowledge-only persistence; actual native host discovery plus installer conflict/removal preservation tests. |
| UCR-19 | PASS controlled profile: `trial/result.json`, separate fresh process replay JSON and real .NET logs for retry and Russian cache/interface domains. Critical nonchange removal fails the separate oracle. Live-model semantic replay NOT_RUN. |
| UCR-20 | PASS_PORTABLE: final installed Linux route (`qualification/run.json`) passes all 25 commands and 389 tests (378 PASS, 11 Windows-only SKIP), unchanged source. Separate full local regression also passes. Source-bound CI/native Windows status is in `ci/validation.json`, never inferred from the Linux host test. |

No row asserts that an arbitrary model will recover the same source diff or that
fixture CRs were independently fetched. [Review limits and failures](REVIEW.md)
are part of these results, alongside their raw logs, not hidden skips.
