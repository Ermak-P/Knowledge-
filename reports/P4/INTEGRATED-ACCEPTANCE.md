# Integrated correction acceptance

Candidate 0.4.0rc4; base `4345352cb0fb8c20a19b51f9227fe91424c250de`; installed implementation `72c46b846086ef9a31275193934b1c25d70f5b6b`; source identity `975e841d9aa7cb1e6d394a5fbba358c773eaf7d980f4254f4c678831a14e5f99`. Verdict: **NO_GO**.

| Outcome | Result | Command/test and evidence |
|---|---|---|
| 1. Delivery-only capture retry | PASS | test_capture_retry_refuses_execution_without_http_edits_or_processes, test_required_and_optional_delivery_retry_preserve_original_candidate, test_delivery_after_acceptance_death_and_competing_cli_retries_converges, test_delivery_retry_obeys_lease_and_bound_source_configuration |
| 2. Candidate review after commit | PASS | test_two_harness_tasks_commit_refresh_exact_approval_and_dispositions, test_prior_candidate_refresh_preserves_manual_dispositions_and_changed_meaning, test_refresh_links_cannot_hide_unrelated_meaning_or_form_cycles |
| 3. LF/CRLF retirement | PASS | test_lf_and_crlf_clean_checkout_retirement_with_real_commit_ranges, test_crlf_prior_release_raw_evidence_can_prove_retirement, test_partial_or_referenced_removal_still_refuses_retirement |
| 4. Bound file-size policy | PASS | test_configured_file_limit_applies_through_capture_finalization_and_retry, test_resume_uses_configured_file_limit_after_saved_response |
| 5. Public initialization budget | PASS | test_public_init_bounds_real_extraction_first_partial_and_completion, public-init-budget |
| 6. Transferred kit first use | PASS | transferred-kit-first-use, accepted-rc3-upgrade |
| 7. Development/PR/main qualification | NOT_RUN | PR merge-revision qualification pending; .github/workflows/p4.yml |

The seven rows are derived from passing installed tests and complete qualification checks. Real extraction counts and final/uninterrupted equality: runs/df1cbbc388e4417da464fc74fb5ed925/public-init-budget/result.json. ZIP-only setup, real C# build/test/review/capture and independent profile: first-use/result.json. Actual rc3 interruption/upgrade recovery: rc3-upgrade/result.json. Reviewed baseline effect counts and expected failures: reviewed-baseline/result.json. Existing P3 recovery, all fifteen P4 IDs and the pinned 49/49 -> 49/50 -> 50/50 application scenario remain qualified.

PR merge revision: PENDING; PR: PENDING. The matrix jobs execute with read permissions. Token-created PRs use explicit trusted dispatch to qualify their merge revision; ordinary PRs to main trigger automatically. Publication is a separate trusted job and ignores reports-only pushes. Raw successful and failed runs remain in Actions artifacts/evidence history.

Native and Linux ZIP container hashes are recorded separately; use the distribution sidecars and package comparison evidence. Live UMUH/IPM and model-quality benefits remain NOT_ESTABLISHED. No merge/deployment/release publication.
