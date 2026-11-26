# Inherited verification failures — separate from native source implementation

Final source d6a1aafb3257eaadac67cbf5f93f2e58fca6e92a:
https://github.com/Ermak-P/Knowledge-/actions/runs/45662404184

Linux full qualification: PASS_PORTABLE. Windows full qualification: FAILED.
During tearDownClass of test_core_bootstrap.NativeWindowsSafety, deletion of
`runtime Ω with spaces/runtimes/generation/Scripts/python.exe` raises WinError 5
(Access is denied). Both native tests themselves reported OK. The full regression
driver then calls its existing addError implementation with a unittest class-error
holder, whose ID was never added by startTest; rows[t.id()] raises KeyError.
The suite aborts before tests.json is written. Source/log/asset hash verification
and failing commands are retained under ci/final-full/Windows.

`tests/test_core_bootstrap.py` is byte-identical to accepted main 6eb59254. The
addError recorder line is also unchanged from that revision. No suppression,
filesystem-validation relaxation or unrelated Harness change was made. The root
cause of the lingering file handle/cleanup failure is not fully established here;
it requires a separate Windows process/fixture investigation. The recorder defect
is observable directly in the traceback. Reproduce with scripts/verify_p4.py on
native Windows; a passing machine suite does not certify the full suite.

For the same final source, the machine suite executes all 138 tests on native
Windows with no skips/failures, plus real installer/update/OpenCode 2.4.0 checks:
https://github.com/Ermak-P/Knowledge-/actions/runs/45662404178
All manifested product asset bytes and release semantics match the local ready
kit. This validates that route, not the failed full P4 route.

Earlier failures are retained as well: Stage 3 machine Windows reported
unsafe-filesystem-object / concurrent JSON Access is denied; full refinement
63762cd5 Linux reported harness-busy/database locked in unchanged concurrency
fixtures and competing resume; its Windows suite hit the same teardown/recorder
path. ci/stage3-machine and ci/provider-full preserve these attempts. They are
never used as final PASS evidence. Local final full qualification executes all
539 tests successfully (13 native-only skips) and all 28 portable checks.
