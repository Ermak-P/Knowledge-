# Workspace hardening (0.2.1 candidate)

The GitHub-independent distribution is retained. No dependency version or integrity is changed.

## Safety and cost
- A worktree-local atomic mkdir in the canonical Git directory excludes cooperating Harness processes. Evidence stays in memory; abandoned locks are not automatically stolen. If a process is forcibly terminated or teardown fails, stop every DSH/Harness process and its child processes, inspect owner.json, and only then remove the harness-dsh-run.lock directory under the Git directory. Never remove a live lock.
- The lock does not prevent external editors, other tools, or a non-cooperating older plugin from writing. External or ignored build inputs remain outside the qualified verification boundary. The existing pre/post content and metadata seals and final Gate checks are retained; no cache is introduced.
- Combine tracked status and untracked enumeration in each metadata seal, retaining ignored .NET input checks and hidden-index rejection. This reduces wrapper Git subprocesses from six to four per successful fingerprint; stalegreen's internal subprocesses are additional.
- Scope validation for a single criterion uses a literal Git pathspec rather than enumerating every file.
- Avoid unused role-boundary snapshots for mutating Coding/Testing roles; their actual verification and TDD snapshots are retained. An already-unverified result cannot be made usable by another snapshot, so return an explicitly unavailable fingerprint instead.
- Enable fingerprintMetrics: true in the user-managed overlay for per-call timings. The run prints a compact fingerprint-summary even when detailed metrics are off. These timings measure the wrapper and its stalegreen call, not individual internal stalegreen subprocesses.

## Read-only performance measurement on Windows
From the installed source directory with production dependencies installed:

    npm run benchmark:fingerprint -- C:/Git/IPM2 30 60000

The script outputs first invocation, warm min/median/P95/max, unavailable count, phase timings, CPU and sampled RSS. Run again with budget 5000 to test the deployed default. First invocation is not a guaranteed cold filesystem cache. Do not increase the default budget until measurements support it.

## Qualification
This candidate needs the complete regression suite, Windows-native lock/teardown tests, and actual IPM2 performance measurement. Do not claim measured speedup from fewer subprocesses alone. No production readiness is asserted.
