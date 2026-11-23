# R1 validation checkpoint

Product implementation: `b57f5e8c26992c5bd95cf8d22b46f1a9f485187d`.
Qualification source identity:
`4ce84bd346cad8fa0bd3177617c7b718984372524556b37360ebf3fddb34a0b0`.

R1 fixes all four reviewed cases and protects pending plans created before the
proposal-identity correction. Final local installed qualification passes all
25 commands and 401 tests (390 PASS, 11 Windows-only SKIP). The 39 affected tests
and 12 Knowledge-only installed probes pass, as does the real OpenCode 1.19.6
controlled same-chat CR sequence.

CI run 45128239934 passes Linux. Its Windows regression run passes all 39 affected
tests and 400 of 401 total tests, with one error in the unchanged
`PersistentInstructions.test_default_roots_concurrent_acceptance_and_existing_claims`:
`unsafe-filesystem-object` during concurrent shared-root traversal.
The raw failed run remains in reports/UpdateByCR-R1/failures/ci-b57-first.

The GitHub REST rerun endpoint is inaccessible from this environment (Forbidden).
Publishing this validation note triggers the existing complete CI route through
the normal push event. It changes neither product/test bytes nor the declared
qualification source closure/identity. No checks, safety guards, synchronization
or timeouts are modified. The next CI receipt must be retained under its actual
Git commit and unchanged source identity, not relabelled as the earlier run.
