# Integrated rc4 implementation (preserved P4 corrections)

Candidate 0.4.0rc4; tested commit 72c46b846086ef9a31275193934b1c25d70f5b6b; final installed run df1cbbc388e4417da464fc74fb5ed925; source identity 975e841d9aa7cb1e6d394a5fbba358c773eaf7d980f4254f4c678831a14e5f99.

Integrated changes: capture-retry is a delivery-only leased operation, including completed-degraded recovery and source/config preflight. Equivalent stale pending candidates get fresh source-bound payloads and validated audit links; old approvals and human dispositions remain intact. Raw evidence and normalized Git blobs are compared in separate domains for LF/CRLF retirement. All run snapshots use the bound file-size limit. Public initialization reuses durable bounded extraction for reconciliation. The ZIP contains complete first-use templates, a C# compiled-behavior demo and controlled provider. PR jobs use read permissions; trusted jobs separately retain evidence and open/qualify the correction PR. See INTEGRATED-ACCEPTANCE.md and docs/P4/DESIGN.md for exact observed boundaries.

R1: known predecessor maintenance markers remain readable without mutation; exact-approved upgrades retain old state/markers in backup and transaction history, and recovery completes the originally approved version. Real accepted P3 fixtures cover marked and unmarked nonempty/pending states and actual code/data rollback.

R2: safe rotations publish version-2 continuation contracts with owned read/search/action receipts, bounded observations, explicit untrusted decision notes, unresolved issues and next step. Fresh contexts receive this contract and range retrieval, rather than an inherited transcript. A fact learned from Notes.md drives a real patch after process death and rotation.

R2 follow-up: absent but already authorized source/test targets resolve through the shared real-patch path guard under both original outer and immutable item authority. Compatible strings resolve literal absent paths only with one owner; ambiguous, pattern-only and outside-authority findings stop. Installed HTTP regressions observe file-not-found, one real scoped creation, preserved unrelated bytes/attempts/budgets, new test execution, final source/config-bound gates, independent approval and candidate-only capture. Negative guards match real broker refusals for scope, traversal, absolute/private/protected and linked-parent paths.

R3: final findings map to their affected immutable item scopes; structured affected item/path references are validated. Earlier items can reopen without broadening authority, losing attempts, replaying unrelated source edits or reusing final gates. Ambiguous findings stop for an explicit target.

R4: native checkout restores process-local core.longpaths. CI emits exact-source/package qualification receipts through the dedicated p4-ci-evidence branch as well as Actions artifacts.

R5: all fifteen acceptance IDs are derived from actual tests/checks; .NET application, comparison manifests, independent install, concurrency, workflow and lockfile inventories are part of the single verification route. No manual PASS promotion.

Tests: 224 discovered, 214 PASS, 10 SKIP, 0 failures/errors. Native status and remaining gaps: ACCEPTANCE-MATRIX.md. No merge, deployment or release publication.
