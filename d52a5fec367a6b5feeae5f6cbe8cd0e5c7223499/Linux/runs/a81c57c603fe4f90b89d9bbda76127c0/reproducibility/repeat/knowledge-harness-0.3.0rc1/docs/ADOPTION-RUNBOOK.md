# Production adoption rehearsal runbook

This is guidance, not authorization for IPM/UMUH cutover. Prerequisites: a qualified OS/Python/filesystem profile, verified distribution checksum, trusted recipe programs, explicit project root, optional separately configured model/MCP and a tested recovery operator.

1. Inspect doctor/version and current git/source/user edits. Preserve compatible prior wheels. Quiesce execution and canonical transactions; do not kill unrelated processes.
2. Create/verify a consistent complete backup. Save upgrade/restore/host merge previews and inspect exact root, source/state identities, formats, changes and destination. Approve only the exact fingerprint.
3. Install in an isolated environment or explicitly adopted product-only venv. Perform independent Knowledge read/history/no-answer smoke and a narrow guarded task with real gates. Inspect capture delivery separately; canonical changes require explicit prepare/apply/ack review.
4. Stop on source conflict, unknown process outcome, unexpected counts, unsupported OS/state version or missing required qualification. Preserve bytes/receipts; use status/recover rather than reset/clean.
5. If rollback is warranted, use the tested exact restore with a separate replaced-state recovery location, then reinstall the compatible prior wheels. Verify records/history/dispositions/outbox/accounting and user source before resuming. Old source-stale approvals remain review work.

Windows NO_GO cannot be waived by Linux results, a workflow file, WSL or mocked APIs. Optional live-model/OpenCode evidence is distinct from standalone product qualification. Real production deployment requires the user's separate decision.
