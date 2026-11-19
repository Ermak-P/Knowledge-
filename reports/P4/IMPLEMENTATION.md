# P4 R1 implementation

Candidate 0.4.0rc2; final installed run 718e79cb0dd24bc4a1f240047953dcb5; source identity 9ba88b5fad87cd723a57e4aac114b7f5337465e6b427779047b67890865181aa.

R1: known predecessor maintenance markers remain readable without mutation; exact-approved upgrades retain old state/markers in backup and transaction history, and recovery completes the originally approved version. Real accepted P3 fixtures cover marked and unmarked nonempty/pending states and actual code/data rollback.

R2: safe rotations publish version-2 continuation contracts with owned read/search/action receipts, bounded observations, explicit untrusted decision notes, unresolved issues and next step. Fresh contexts receive this contract and range retrieval, rather than an inherited transcript. A fact learned from Notes.md drives a real patch after process death and rotation.

R3: final findings map to their affected immutable item scopes; structured affected item/path references are validated. Earlier items can reopen without broadening authority, losing attempts, replaying unrelated source edits or reusing final gates. Ambiguous findings stop for an explicit target.

R4: native checkout restores process-local core.longpaths. CI emits exact-source/package qualification receipts through the dedicated p4-ci-evidence branch as well as Actions artifacts.

R5: all fifteen acceptance IDs are derived from actual tests/checks; .NET application, comparison manifests, independent install, concurrency, workflow and lockfile inventories are part of the single verification route. No manual PASS promotion.

Tests: 206 discovered, 196 PASS, 10 SKIP, 0 failures/errors. Native status and remaining gaps: ACCEPTANCE-MATRIX.md. No merge, deployment or release publication.
