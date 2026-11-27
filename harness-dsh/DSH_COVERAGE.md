# DSH implementation coverage

Measured with c8 10.1.3 and Node 24.22.3 on Linux x64. The clean run at `e0cdf2cf5deb315129177ec8090bf9b5a4b12e15` ran all 25 Node test cases with the .NET and Knowledge integrations enabled. Individual cases in the original mocked suite retain multiple scenario assertions.

| Production source | Statements | Branches | Functions | Lines |
|---|---:|---:|---:|---:|
| **Total** | 96.74% | 81.25% | 97.80% | 96.74% |
| `src/dotnet.ts` | 97.83% | 76.75% | 100.00% | 97.83% |
| `src/engineering.ts` | 100.00% | 83.33% | 100.00% | 100.00% |
| `src/index.ts` | 100.00% | 100.00% | 100.00% | 100.00% |
| `src/lifecycle.ts` | 100.00% | 84.17% | 95.83% | 100.00% |
| `src/tdd.ts` | 100.00% | 69.44% | 100.00% | 100.00% |
| `src/reprolab/green-verifier.ts` | 100.00% | 85.71% | 100.00% | 100.00% |
| `src/reprolab/red-verifier.ts` | 100.00% | 100.00% | 100.00% | 100.00% |
| `src/reprolab/regression-verifier.ts` | 97.82% | 87.50% | 100.00% | 97.82% |
| `src/reprolab/types.ts` | 0.00% | 0.00% | 0.00% | 0.00% |

The aggregate includes the vendored, type-only `reprolab/types.ts`. Node strips those declarations before execution. V8 coverage records statement and line coverage at the same granularity for this run. Review the branch results and scenario outcomes before drawing conclusions from the aggregate.

## Coverage of critical behavior

- **Evidence and gate.** Real verification libraries and Git snapshots exercise success, missing evidence, wrong selector, copied evidence, revised contracts, new repair attempts, unavailable freshness, missing blobs, capture failures, the latest failing result, ignored .NET sources, and changes during gate evaluation.
- **Lifecycle and recovery.** Native DSH runs exercise Planning through completion, both .NET repair paths, Reviewing refusal and rework, retry exhaustion, cancellation and restart, evidence isolation, and native unload. Real SDK TDD includes RED, GREEN, refactor and the second GREEN.
- **Failure controls.** Removing the final gate snapshot check and reverting capture-failure typing each produced a failing stale-green regression in an isolated source copy. The additional native receipt test rejected a post-execution result replacement. See [mutation output](evidence/mutation-controls.txt) and [native receipt output](evidence/native-receipt.txt).

Remaining branch gaps include unusual filesystem failures during snapshots, alternate TDD rejection outcomes, and teardown error branches. The production Windows sandbox, deployed UI, and model remain qualification gaps. See [DSH acceptance](DSH_ACCEPTANCE_REPORT.md).

[Raw coverage log](evidence/qualified-coverage.txt) · [Machine-readable coverage](evidence/coverage-summary.json)
