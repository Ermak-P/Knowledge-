# Integrated correction review response

Candidate **0.4.0rc4**, implementation `72c46b846086ef9a31275193934b1c25d70f5b6b`, base `4345352cb0fb8c20a19b51f9227fe91424c250de`.
Source identity: `975e841d9aa7cb1e6d394a5fbba358c773eaf7d980f4254f4c678831a14e5f99`.

| Outcome | Observed result | Raw evidence |
|---|---|---|
| 1. Delivery-only retry | Ineligible execution causes zero extra HTTP/patches/recipes; required and optional outboxes converge; accepted-before-receipt death and competing retries preserve one identity. | tests.json / regressions.log: CaptureIntegration |
| 2. Review after Git commit | Two completed tasks committed before one fresh approval; old approval rejected; unrelated pending kept; exact IDs active/trusted once; next plan empty. Prior rc3 pending and rejected/deferred/changed-meaning cases also pass. | supplemental/two-pending/result.json; installed KnowledgeIntegration tests |
| 3. LF/CRLF retirement | Both actual checkout byte policies clean; approved commit-range retirement preserves history; old raw CRLF proof works; dirty/partial/referenced cases still refuse. | Linux and native Windows tests.json / KnowledgeIntegration |
| 4. File-size policy | 1,100,000-byte file completes and delivers under 2,000,000; resume/retry use that bound; 2,000,001 refused. | CaptureIntegration installed CLI cases |
| 5. Public init budget | Entire-command extractor counts 1/1/418/0 against budgets 1/1/10000/1; final observations equal uninterrupted 420-file extraction. No hidden reconciliation calls; nonempty/ambiguous/stale cases covered. | public-init-budget/result.json; corresponding native result; installed public-init test |
| 6. ZIP first use | Both profiles installed outside checkout; shipped templates/provider and real C# build/test/review/capture work; rc3 interrupted work/delivery survive upgrade. | first-use/result.json; rc3-upgrade/result.json |
| 7. PR/main development qualification | Push Linux/native jobs succeed; PR/main triggers and read-only validation are implemented. Correction PR creation is blocked by the repository Actions setting, so no PR merge qualification is claimed. | pr-creation-block.json; workflow source; linked failed orchestration job |

Linux: **224 discovered, 214 PASS, 10 native-Windows-only SKIP, zero failures/errors**. Native Windows: **224/224 PASS, zero skips/failures/errors**, NTFS, PowerShell 5.1, Python 3.12. Both complete routes use the same committed source and preserve the pinned .NET application evidence: 49/49 baseline, an independent regression failing before repair, 50/50 afterward. Every recorded command-log SHA has been checked. Qualified jobs: https://github.com/Ermak-P/Knowledge-/actions/runs/44506706470/job/135500136213 and https://github.com/Ermak-P/Knowledge-/actions/runs/44506706470/job/135500136429 . The overall workflow fails only at PR creation, whose exact GitHub rejection is retained above.

Reviewed rc3 is installed from its exact checksum-pinned ZIP. Baseline actual effects include six extra HTTP requests, one patch and two recipe launches during capture retry, optional capture remaining degraded, clean CRLF misclassification, and 421 real extractor calls reported as one. Its focused regressions intentionally fail; REPRODUCED is not a claim that baseline tests pass. First installer-identity CI failures are retained separately under failed-ci/. Uncommitted local development history is outside this accepted run/archive and never used as a committed-source qualification.

| Distribution container | SHA-256 |
|---|---|
| Linux | `601b69dd90d7f274ce9c1eccdd6f2239d5c11364e33506d65640efe838cdd1fb` |
| Native Windows | `ca271278e5c1f4653c8a388e930cadf3cff05e92d2b2e1ce7c72cb75b23ad820` |

Platform container hashes differ; both wheel bytes, payload bytes and semantic RELEASE manifests match. The independent Linux rebuild matches byte for byte. See package-equivalence.json.

**Not ready for final integrated acceptance:** outcome 7 still needs an actual correction PR and its Linux/native qualification. The generated integrated verdict remains NO_GO until that evidence exists. This is an external repository permission block, not a passing PR claim. No merge, release publication or deployment. Private UMUH/IPM and live-model quality/benefit remain NOT_ESTABLISHED.
