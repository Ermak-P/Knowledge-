# P3 independent review correction: R1 and R2

Review baseline: p3 / 453e5625ee939e338d4430927ca4f13e8c6938c8 (tested implementation 3c28581124a4b045f1339c09fa3fd6bcd06f2983). This is a focused companion correction. The Windows backend, release/install/lifecycle architecture and all 171 existing tests are retained.

P3-R1: companion._snapshot captures one-read immutable payloads plus exact enrollment/host/runner bindings. engine.start validates the snapshot under the actual Lease and drives companion runs without an intervening unlock. Stored authority is rechecked at resume before provider/tools/capture. A changed file cannot supply a second, broader task after validation. A once-valid doctor result is not execution authority.

Named regressions in test_p3_companion_review.CompanionReviewTests:

- test_task_replacement_after_validated_read_cannot_gain_coding_authority
- test_changed_scope_enrollment_or_policy_at_ownership_is_rejected
- test_configured_mcp_rejects_read_replacement_before_provider_or_tools
- test_configured_mcp_rechecks_installation_and_config_at_ownership
- test_interrupted_companion_run_rechecks_authority_before_resume

P3-R2: version 2 previews include the exact marker hash and restoration bytes/absence. Under Lease, apply rejects stale marker/host/configuration, unknown versions/operations and a newer installation, restores only the approved snapshot and retains the marker/history. New installation UUIDs distinguish otherwise identical reenrollment. Legacy version 1 markers can be removed with a fresh version 2 preview; old previews require renewed approval.

Named regressions in the same class:

- test_remove_approval_rejects_changed_restore_bytes_or_absence
- test_remove_approval_rejects_changed_installation_tasks_host_and_versions
- test_remove_rechecks_marker_after_waiting_for_real_ownership
- test_valid_remove_preserves_exact_unicode_bytes_absence_history_and_global
- test_unknown_preview_version_or_operation_refuses_before_mutation
- test_install_preview_rechecks_task_config_and_existing_marker

Both groups execute again through tests/p3_companion_review_driver.py using -I in a fresh non-editable release installation, including real configured companion MCP transport. Only the filesystem scheduling seam is instrumented; start/drive, HTTP provider, tools, process gates and Knowledge are production implementations. Rejected entry cases require zero actual provider/tool/process effects and unchanged application, policy and canonical/queue state. Removal cases require exact host/marker retention or exact approved bytes/absence and preserved history/global sentinel.

Release delivery also tests a real original P3 0.3.0rc1 installation refreshed by the corrected same-version kit. The installer force-reinstalls only the declared local core wheels with no dependency/index access, preventing pip's same-version skip from retaining the vulnerable old implementation under a new marker hash. The test imports actual new authority code, retains nonempty canonical/pending state and removes the legacy marker through preview v2. Restart existing MCP/runner processes after updating code. This check is packaging/same-version-upgrade.json; it does not replace the fresh installed API/MCP regressions.

Current raw results are runs/RUN/rehearsal/companion-review.json and companion-review.log, with per-case effect counts. CORRECTIONS.json and P3-REPORT.md bind actual current local/native results to the tested source and package hashes. Prior successful native evidence qualifies its old source only. Missing revised native evidence keeps the revised Windows profile NOT_RUN/NO_GO. Optional live OpenCode/model/private MCP remain separate.
