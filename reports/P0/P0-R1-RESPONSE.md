# P0 consolidated correction response — R1–R4

Reviewed base: 878ca2eb711405919f82fe57be0d798b42fa5066.
Branch: codex/knowledge-harness-p0, local correction working tree; no push/merge/deploy.
Submitted for second review; external acceptance is not asserted. P1/P2 were not started.

| Request | Implementation | Executable regression |
|---|---|---|
| R1 | Explicit discovery of interchange/external JSONL; any external presence safely refuses with details, coexistence ambiguous; selected bytes/absence approval-bound | test_corrections.MigrationDiscovery: absent, supported empty/nonempty, unsupported empty/nonempty/malformed, coexistence and changed/appeared source |
| R2 | SDK CallToolResult with exact canonical TextContent and no structuredContent | test_corrections.WireBudget: actual stdio text bytes at 256/512/1000/4000/16000, Unicode, provenance, conflicts, no-answer; semantic agreement/evidence associations |
| R3 | UTF-8 reader with domain error; explicit manifest/schema/record/journal/plan/queue/config containers | test_corrections.ErrorContract: subprocess exit/stdout/no traceback and preserved store/source for invalid UTF-8 and JSON array/null/number/string |
| R4 | Run-scoped UUID ledger, initial success invalidation, statuses/return codes, current-output removal, artifact hashes/snapshots and exact source binding; generator validates ledger first | test_corrections.EvidenceGate: successful attempt then real controlled rc9 subprocess; incomplete/interrupted, changed-source and mixed-artifact refusal through generator subprocess |

Commands: `bash scripts/setup.sh`, `.venv/bin/python scripts/verify.py`,
`.venv/bin/python scripts/make_review.py`. Current authoritative outcomes, run ID,
source identity, commands, return codes and artifact hashes are in
`verification-summary.json` and the matching `runs/RUN_ID/run.json`.
The final report and acceptance matrix are generated only after all required checks
complete successfully against that source; they provide actual test counts/results.

Self-review retained the package/resolver/SQLite/validator/Harness boundaries.
Review checked queue discovery before publication, JSON decoding before field access,
MCP wire serialization and provenance/association retention, old-success invalidation,
missing-output refusal, mixed-artifact/source checks and failed-process diagnostics.
Single-node restore now explicitly uses `-m:1` as supported by the reviewer diagnosis.
No network access or verification was weakened to address the task-host limitation.
Fresh .NET results must come from the current ledger, never submitted old TRX files.
Native Windows/NTFS, live providers, UI/SQL Server/Aspire remain NOT_RUN.

Execution result in this prepared Linux environment: the first corrected full run
completed successfully with 42 tests and fresh build/49 before-and-after unit-test
results. Final verification additionally starts a new benchmark store (preserving
the previous generated store under `.local`) so all 15 submissions/imports/acks
are executed anew, and exercises actual Unicode claim/evidence provenance at the
MCP wire boundary. The final run ledger supersedes earlier attempts; acceptance
and packet provenance refer exclusively to it. No reviewer task-host diagnosis
is inferred from success in this separate environment.
