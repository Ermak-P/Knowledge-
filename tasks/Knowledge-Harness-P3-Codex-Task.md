# Knowledge + Harness — P3 execution task

Version: 1.0 · 2026-11-15

## 1. Mission and accepted baseline

Implement **P3: a reproducible portable release candidate, native Windows execution/verification, safe lifecycle tooling and a UMUH onboarding rehearsal**. Deliver working code and release artifacts, executed verification and one complete review packet. This is implementation work, not a request for another roadmap or documentation-only Windows support.

Repository: <https://github.com/Ermak-P/Knowledge->.

Accepted P2 revision: `91689475a283a2cdc654cfb6090074f0251f895d`.

Accepted P2 source identity: `4bb5fdfc0dabe64fee7087a29565549b40da6f2a8f32e203ed46f58883110416`.

Independent P2 review passed 138 tests, packaging, original defect reproductions and source/run/archive integrity. P2-R1–R3 are closed: repeated capture uses verified positive ownership, verifier input protection is path-spelling independent, and resume reads mutable state/configuration under ownership. Submitted .NET artifacts showed baseline 49/49, the new regression failing before repair, then final 50/50. Independent review did not claim its own successful .NET application run. Live model/OpenCode/native Windows were not certified.

Start a normal `p3` development branch from updated `main` after the user merges P2. Do not depend on the `p2` branch existing. Verify accepted ancestry, or the accepted source inventory for a squash merge; preserve legitimate later changes. Do not develop on the earlier uncorrected P2. Record the exact starting revision and inspect differences if main has moved.

Read the accepted code/contracts and P0–P2 tasks/correction tests before changing them. Known starting limitations include `fcntl`/POSIX leases, `/proc` process identities, process groups and inherited descriptors; POSIX absolute-executable checks; Linux SDK/bootstrap paths; and the historical `verify-windows.ps1` invoking old P0 verification. Replace these active limitations with supported behavior rather than renaming reports.

The original product archive/private IPM, real UMUH, personal configs, local models and credentials are not required inputs. The narrow public input intentionally omits the old private Harness. Do not invent compatibility with unseen integrations.

## 2. Autonomy, authorization and deliverable verdicts

Work autonomously through design, implementation, tests, self-review and repairs. Make routine reversible decisions and record important tradeoffs. Complete the coherent result before returning; do not ask permission for every substep or stop after writing scripts that were never exercised.

Use ordinary checkouts and **in-place execution only; no Git worktrees**. Preserve user edits and existing stores. Never use destructive reset/clean, blanket restore or history deletion as recovery. Temporary fixture repositories may create commits. Do not automatically commit application edits, merge branches, deploy, publish a GitHub release, upload packages to a registry or modify production IPM/UMUH. Commit the completed product/task-branch work and report its exact revision. The user controls merge, branch deletion and publication.

Implementing standard Linux/native Windows CI workflows and running them through the repository's available ordinary task-branch CI is in scope. Do not alter repository administration, secrets, protected-branch settings or billing, provision paid infrastructure or seek production access. No graphical desktop is required for implementation or headless CI.

Two verdicts must remain separate:

- **Implementation review readiness:** whether the complete source/package/scripts/rehearsal and available verification are ready for external review.
- **Release qualification:** which explicit OS/runtime/integration profiles actually passed their required checks.

Native Windows execution and NTFS verification are **required for a Windows release GO**. Prefer an available native Windows CI runner; a local Windows host is not required if CI provides equivalent evidence. Linux, WSL, Wine, mocked `os.name`, static PowerShell inspection or a workflow YAML file do not prove native Windows behavior.

If no authorized native Windows runner can actually execute, finish all implementation, runnable Windows tests/workflow, portable checks and review artifacts. Mark the native conditions `NOT_RUN/BLOCKED`, provide the exact executable handoff and keep Windows release `NO_GO`. Do not stop early, replace those checks with mocks or silently downgrade the release criterion. Explain the precise missing capability. Missing optional live model/OpenCode infrastructure is separately recorded and does not prevent qualification of the tested standalone software profile.

## 3. Concrete finish line and scope

The delivered release candidate must let a user:

1. Transfer the product package to another machine/path and install Knowledge alone, or Knowledge plus Harness, into an isolated supported environment without editing product source or private machine configuration.
2. Initialize a new project; run source discovery and current/history retrieval; execute a controlled Harness task; receive reviewable candidates; and approve canonical changes through the existing explicit transaction flow.
3. Use the same supported product contracts on Linux and native Windows, including safe source paths, writer ownership, process cleanup, interruption and resume.
4. Preview and perform supported upgrade, consistent backup, restore/rollback and uninstall without losing claims, evidence, queue/dispositions, receipts, positive capture ownership, run/outbox state or unrelated application files.
5. Follow a tested project-local OpenCode/companion integration path with honest capability boundaries, rather than overwriting global user agent policy.
6. Rehearse connecting an independent UMUH-like project from a clean release package and a new root, with no IPM-specific changes to the core.
7. Inspect a release manifest, checksums, compatibility/qualification matrix and current evidence sufficient for independent review.

Out of scope: actual production IPM migration/cutover, real UMUH deployment, universal hosts/models/filesystems, an MSI or GUI, OS sandboxing of arbitrary hostile build programs, installing every private MCP service, business/domain facts not supported by source, performance marketing claims and automatic publication. Retain Knowledge's independence and Harness's separate execution/permission/accounting ownership.

## 4. Release artifacts, installation and versioning

Produce independently installable wheels for Knowledge and Harness, declared reproducible dependencies, optional MCP/host extras and a small bootstrap/install kit. Installation must work from the release bundle in an absent isolated environment, outside the implementation checkout and without `PYTHONPATH` or editable-install dependence. Knowledge-only core must not install/import Harness or require an agent/model service.

At minimum provide an offline install of the core Knowledge + Harness wheels from local artifacts on the declared profiles, given an already installed supported Python. If optional profiles need network installation, use pinned/verifiable dependencies and declare that explicitly. Do not claim a complete offline MCP/Windows wheelhouse unless all platform/Python-specific transitive artifacts are present and a network-disabled fresh install actually passes. Do not bundle SDK/model/dependency caches or arbitrary machine environments as the product distribution.

Choose a release version and align package metadata, runtime version/capability commands, manifests and compatibility documentation. State supported Python/OS/architecture and SDK profiles; avoid promising versions never exercised. Distribution-name changes, if any, require tested upgrade/uninstall/dependency handling from the existing `knowledge-p0`/`harness-p0` packages. Do not install two competing copies of the same import package or silently break existing CLI names.

Keep product version, record/envelope schema, database extension, Harness config/run state and platform receipt versions distinct. Unknown or incompatible versions must fail before mutation with an actionable result. Existing v1/v2 Knowledge payloads and approved histories retain their meaning; no speculative schema/storage rewrite is requested.

Ship separate POSIX and PowerShell entry scripts or a small portable launcher. Windows PowerShell 5.1 launcher support is required for the Windows profile; PowerShell 7 support must also be tested if claimed. Handle UTF-8/non-ASCII paths and quoted arguments, and propagate child nonzero exit status. Do not rely on PS7-only operators in PS5.1. Discover real Python/venv executable locations and native `dotnet`; do not retain `.venv/bin`, `/...` executable assumptions or a Linux SDK URL on Windows. Runtime/SDK installation must be local or user-selected, checksum-verified when downloaded, and must preserve incompatible existing installations rather than silently replacing them.

## 5. Native Windows execution and path semantics

Implement a real platform boundary for leases, process ownership/supervision/cancellation, path policy and native launch behavior. Keep the accepted Linux guarantees. Choosing a suitable OS mechanism is your responsibility; inspect authoritative docs and verify the actual implementation. Do not merely catch `ImportError`/skip cleanup or replace a held lease with an unlocked marker file.

On native Windows demonstrate:

- One source-mutating owner per project; bounded competing-writer behavior; correct ownership across parent/supervisor death and cleanup; no unsafe release while owned children are still active.
- Actual child/grandchild timeout/cancellation and worker-death recovery. Act only on verifiably owned processes; PID reuse, stale receipts and another run's process must not authorize termination. `taskkill` by image name, killing all dotnet/Python processes or assuming parent death kills descendants is unacceptable.
- Handle/process identity and abandoned-owner semantics that do not replay an acknowledged edit or trust a stale tool/gate result. Persist platform provenance; a historical Linux PID/descriptor receipt is not Windows process authority.
- Native absolute executable/drive paths, case normalization and the same project through alternate supported spellings; two genuinely different roots remain isolated. Cover spaces, non-ASCII, path traversal, symlinks/junctions, hardlinks, UNC policy, reparse/path alias policy and unsupported/reserved forms. Either support a path class safely or reject it before effects; do not silently normalize an escape into an allowed path.
- Consistent source hashing/provenance, atomic file replacement and bounded file-sharing/permission errors. An access-denied/locked-file failure must not be reported as a successful edit, gate, backup or restore.

Use ordinary-user privileges where possible. Record actual Windows version, Python, architecture, shell, filesystem and capability availability. If a particular link operation is unavailable, distinguish that from an exercised junction policy; do not certify an untested path class. An unsupported environment/profile must refuse honestly rather than drop the guard.

Retain P2's separate role contexts, runtime capability checks, absolute/relative recipe-input protection, explicit test-edit exceptions, final-source build/test/review gates, budget/accounting and monotonic under-lease resume. Port all required runtime behavior, not only the read-only Knowledge CLI. An all-green Windows Knowledge test job cannot certify Harness if its execution cases were skipped.

## 6. State compatibility and safe upgrade

Deliver usable versioned upgrade preview/apply/status/recovery operations for the supported prior package/store versions. Test real nonempty accepted-format fixtures and isolated installed prior/current binaries, not an empty reconstructed database labeled an upgrade.

Fixtures must include canonical records/relationships, immutable revisions/receipts, pending/imported/rejected/deferred queue entries, prepared and committed-but-unacknowledged transactions, positive capture observation metadata, completed/interrupted Harness runs, request/usage history and accepted-but-undelivered capture outbox state. Preserve exact identities, values, dispositions, bindings and historical authority.

Preview must be observational and explain planned format/config changes, compatibility, semantic differences, backup destination and required quiescence. It must not initialize/reset an absent or corrupt store as a side effect. Apply requires approval of that exact current preview/fingerprint; intervening relevant edits, queue/state/config changes or a different project invalidate it.

Coordinate participating writers and readers according to a documented lock/freeze order. Busy/unknown ownership yields bounded refusal; do not forcibly remove locks or stop unrelated processes. Upgrade and canonical mutation must not run concurrently through independent writers. Test interruptions before/during/after the relevant commit boundary, repeat/idempotent application and recovery without losing unrelated source edits.

Compatible old approvals remain valid only where the accepted contract permits; incompatible or source-stale ones become explicit review work. Preserve original receipt payloads/ownership. Do not rewrite historical approvals into permission for new changes or silently acknowledge uncertain old transactions.

## 7. Backup, restore, rollback and relocation policy

Implement consistent, integrity-checked backup and restore tooling and a documented rollback path. Live SQLite files must be copied with an appropriate consistency/freeze mechanism, not raw-copied with ignored journals. A Knowledge + Harness backup must describe its cross-store consistency boundary and include all required metadata, configuration, run/action/outbox state and referenced artifacts. A fixed old five-table export is not a complete P2 backup.

Backups have manifests with project/root binding, schema/product/platform versions, file checksums and semantic counts/identity checks. Keep secrets outside by design or explicitly redact them without pretending redacted state can transparently resume. Treat restored archive paths and manifests as untrusted input: reject traversal, links, collisions and tampering before unsafe writes.

Restore/rollback must have a precise target and preview, verify compatibility/integrity, preserve the replaced state in a separate recovery location and require exact approval before overwrite. Refuse a stale preview, hot/owned process, mismatched project or unsupported version. Never delete hot journals or broad project directories to force a restore. Test interrupted restore and a practical rollback to supported previous code/data together; downgrade of code does not automatically make newer data compatible.

Separate three portability cases:

1. Moving the product package: supported through fresh installation at another path/machine.
2. Onboarding a different project: supported through a fresh identity/configuration/store and source-backed initialization.
3. Moving an existing root-bound store/run: either implement an explicit approved, audited relocation/rebind with retained original histories and tested semantics, or refuse it clearly and provide a safe documented preservation/reinitialization workflow. Do not promise that raw `.knowledge`/`.harness` directory copying is portable.

The minimum mandatory rehearsal uses cases 1 and 2; a general cross-machine active-run migration engine is not required. If relocation is supported, original approvals/process receipts must not become new-root/other-OS authority. Never silently rewrite root hashes, source paths or old transaction fingerprints to make a copied store pass validation.

## 8. Uninstall and reinstall

Provide an actual tested uninstall/reinstall path for the isolated installed product. Remove only artifacts owned by that installation. Preserve application source, `.knowledge`, `.harness` history/configuration and backups by default. Do not delete a shared/user venv, global config or unrelated packages. Any purge is a separate explicitly scoped action, never the default uninstall or test cleanup strategy for real projects.

Record install ownership/version/environment markers without making them a second knowledge store. Test uninstall followed by reinstall/current upgrade against the retained nonempty data and demonstrate expected retrieval, history, pending candidates and safe run inspection/recovery. Verify no competing old import package or stale CLI launcher shadows the installed version.

## 9. Project-local OpenCode/companion integration

Deliver a concrete optional project-local integration kit that can configure the existing Knowledge MCP/CLI commands and invoke the guarded Harness entry path. Inspect current supported host interfaces/version behavior when implementing it. Installation is opt-in/project-scoped, uses explicit paths/runtime discovery and preserves existing config via preview/merge/backup rather than replacing it. Do not touch the user's global agent configuration or actual IPM tool permissions.

Be precise about the execution mode. A standalone Harness calling a model endpoint is not proof that native OpenCode subagents enforce the same permissions. If the supported mode is a companion runner with Knowledge MCP and explicit CLI invocation, label it that way and retain Harness as the authoritative tool/gate boundary. Do not create an unrestricted shell escape through a host wrapper, conceal an unsupported native host capability or advertise unimplemented specialist MCPs.

Provide doctor/configuration validation, reversible bootstrap, examples without credentials and protocol tests exercising the real configured MCP/command entry points. Test that the active root, independent installation paths and current/explicit history semantics agree. The accepted three Knowledge command adapters remain supported; aliases delegate to one implementation rather than creating different writers.

If an authorized real OpenCode executable is available, execute a version/configuration/entry-point smoke with recorded provenance; a live model-driven session remains separately qualified. If unavailable, finish the actual kit and reproducible protocol/config tests, mark the live host check `NOT_RUN` and do not certify that host profile. Optional private MCP installation is not part of this milestone.

## 10. Independent UMUH onboarding rehearsal

Build a new disposable **UMUH-like rehearsal project**, separate from the product source, pinned eShop and prior P2 fixture. It must have a different directory/project naming layout, at least a small domain/application boundary and a real executable test/check project. This is a synthetic test host, not a representation that unseen production UMUH was inspected.

Run the rehearsal from the built release package in a fresh environment/new root, including a path with spaces/non-ASCII. Do not import product code from the development tree or edit core code to accommodate that project. Use declared public configuration only.

Execute and retain evidence for:

1. Install/doctor and independent Knowledge-only operation; add Harness using the supported install path.
2. Empty-store initialization distinct from full discovery; bounded discovery/resume, coverage/gaps and source-backed candidates across the fixture's projects.
3. Exact explicit prepare/approve/apply/ack; ordinary context versus explicit history, no-answer and inferred/unverifiable source cases.
4. One meaningful source behavior change made through the installed Harness/provider/tool path, actual build/test/review and automatic capture. Define the expected behavior/check before execution. Canonical knowledge remains unchanged until deliberate fixture approval.
5. Approved first capture followed by another same-entity source revision, automatic update and explicit approval, preserving ID/history/positive ownership. Include no-new-fact and rejected/deferred behavior without artificial candidate quotas.
6. A real interruption/recovery and restore/reinstall round trip, with state/usage/outbox checks and an intervening user-edit conflict preserved.
7. Isolation from two other project roots: no wrong-store fallback, source mutation, reused identity, provider/session leakage or arbitrary absolute machine paths. A case variant of the same Windows root is handled by the declared identity policy.

Use the same rehearsal generator/package on Linux and native Windows for qualification. Synthetic provider decisions are allowed through actual HTTP; process, filesystem, installed import, Knowledge and recovery behavior must be real. No real model/credentials are needed to complete this reproducible fixture. Do not call this a successful production UMUH deployment.

## 11. Regression, native CI and realistic application checks

Retain all **138 accepted logical product regressions** and the P2-R1–R3 fixes. Existing Linux behavior must remain exercised. Platform-assuming test setup may be refactored with a clear old-case → new-test mapping; version-specific assertions may change deliberately for the new release version. Do not remove behavioral assertions, convert failures to success or blanket-skip the runner suite to make Windows green.

Windows must run the portable behavior suite plus native equivalents for required lease/process/path/state behaviors. A POSIX-only descriptor/group test may be skipped there only with a named, actually executed Windows counterpart. Record per-platform PASS/FAIL/SKIP/NOT_RUN and explain capability-limited cases. Missing coverage for a required Windows guarantee prevents Windows GO even if test totals are green.

Add standard Linux and native Windows CI jobs for fresh isolated installation, standalone Knowledge, optional MCP stdio, Harness execution, platform safety/recovery, lifecycle tooling and onboarding. Select supported Python/runtime/runner profiles explicitly and record resolved versions. Test supported PowerShell launchers under their claimed shells, not merely `pwsh` while claiming PS5.1. Upload current raw logs/manifests/results even on failure without exposing secrets.

Bind CI evidence to the exact commit/source/package artifacts tested. Jobs triggered on different revisions, stale artifacts or unexecuted workflow files are not evidence. Ordinary available task-branch CI execution is authorized; if credentials/runner access prevent it, provide the ready workflow and concrete blocker while finishing other work. Do not enable paid runners or alter repository settings to bypass this boundary.

Keep the pinned eShopOnWeb application `0c2c95d9d450d07fcd4e96e95e1cd48c20834e99` and its license. Run a fresh supported native SDK restore/build/test baseline and the installed-product source-change workflow, preserving existing tests and the original checkout. Use ordinary disposable copies; final counts may grow with legitimate new tests. Record actual SDK/OS/source identities. Do not use the prior P2 TRX files as fresh P3 evidence or weaken tests/dependencies to bypass an environment failure.

## 12. Release validation, accounting and practical limits

Revalidate installation/upgrade/recovery and repeated capture under realistic nonempty state and bounded multi-chunk source scans. Include stale approval/configuration/source, unknown schema, tampered backup/package, duplicate delivery, concurrent resume/writers and a failed mandatory gate. Verify ordinary validation cannot bless invalid active duplicates or an unexecuted build/test.

Retain full per-role/per-attempt accounting, unknown-outcome usage, bounded contexts/logs and explicit capture delivery/canonical approval dimensions. Compare single/shared and isolated-role modes on equivalent installed-product task definitions. Report success, wall time and complete usage coverage; synthetic provider counters do not establish live model token/speed/quality improvements. Record neutral/negative results honestly.

Run a modest larger source/state fixture sufficient to expose accidental whole-tree re-extraction on every bounded chunk and repeated candidate/history duplication. Measure work actually performed and output sizes. No arbitrary architecture-fact quota, global vector infrastructure or invented production benchmark is required.

Document remaining lexical/coverage limits, trusted build-program boundary, supported filesystems/runtime profiles and unsupported cross-platform active-state migration. “Ready for independent review”, “qualified standalone Windows release candidate”, “live host/model validated” and “safe production migration” are different claims and require different evidence.

## 13. Qualification and acceptance matrix

Map every row to concrete current tests/commands/artifacts and per-profile status. Native Windows conditions cannot become PASS from Linux/doubles. Optional host/model checks are separate. External acceptance and publication remain the user's/reviewer's decisions.

| ID | Required result |
| --- | --- |
| P3-A01 | Accepted P2 ancestry/inventory verified; 138 logical regressions mapped/preserved and all previous blocking fixes retained. |
| P3-A02 | Versioned wheels/install kit/dependency manifests install from clean isolated artifacts outside the source tree; standalone Knowledge stays independent. |
| P3-A03 | Actual offline core installation and declared optional dependency paths work; package/import/CLI versions and upgrade names do not conflict. |
| P3-A04 | Linux and PowerShell launchers discover native runtimes, quote paths/Unicode correctly and propagate failures under claimed shells. |
| P3-A05 | Real Windows process/lease/path backend is implemented; no skipped/unlocked stub substitutes for execution guarantees. |
| P3-A06 | Native Windows competing writers, parent/supervisor death, descendant cancellation/cleanup and owner identity protection pass. |
| P3-A07 | Native Windows/NTFS identity, case/path, junction/link/hardlink/escape and locked-file policies are executed and honest about unsupported forms. |
| P3-A08 | Linux's accepted ownership/process/recovery guarantees still pass; platform receipts cannot become another OS/process's authority. |
| P3-A09 | Nonempty accepted-format Knowledge/Harness upgrade preview/apply preserves records, queues, receipts, ownership metadata, runs and outbox/history. |
| P3-A10 | Wrong/stale approvals, active owners, interrupted/repeated upgrade and unsupported versions refuse/recover without resetting data. |
| P3-A11 | Consistent complete backup manifest/checksums and cross-store freeze policy are implemented and tested with real nonempty state. |
| P3-A12 | Restore/rollback verifies integrity/target/compatibility, survives interruption and preserves replaced state/unrelated user bytes. |
| P3-A13 | Package transfer and fresh-root onboarding work; existing root-bound state relocation is supported explicitly or refused with a safe actionable preservation policy. |
| P3-A14 | Uninstall/reinstall removes only installation-owned artifacts and retains project data/history/configuration by default; retained state remains usable. |
| P3-A15 | Project-local OpenCode/companion bootstrap/doctor is real, reversible and root-correct; no global policy overwrite or false native-subagent claim. |
| P3-A16 | Clean installed-product UMUH-like rehearsal works across a distinct layout with no core changes or IPM-specific path assumptions. |
| P3-A17 | Rehearsal performs actual controlled source change/build/test/review/capture, repeated approved learning and explicit canonical approval/history checks. |
| P3-A18 | Rehearsal interruption/recovery/restore/reinstall and multi-project isolation preserve edits, request accounting, candidates and ownership. |
| P3-A19 | Native Windows rehearsal and installed-product execution pass on the declared profile, with real transport/process/filesystem evidence. |
| P3-A20 | Fresh pinned eShop baseline/behavior workflow preserves prior tests/original source and binds actual SDK/build/TRX evidence to this release candidate. |
| P3-A21 | Linux/native Windows CI and per-platform regression mapping execute the actual release artifacts; required skipped/unrun controls block that profile's GO. |
| P3-A22 | Bounded work, full accounting/uncertainty, stale/tampered/duplicate/concurrent failure cases and comparison remain correct after packaging/porting. |
| P3-A23 | Release verdicts distinguish implementation readiness, OS/integration qualification and external acceptance; missing native evidence cannot yield Windows GO. |
| P3-A24 | Current run/source/package/CI evidence gate rejects stale, mixed, failed, incomplete or modified evidence, including externally collected native artifacts. |
| P3-A25 | Complete distribution/review bundles, compatibility/runbooks/licenses/inventories/checksums are reproducible and contain no credentials/private caches. |

## 14. Verification evidence and review package

Add a separate P3 verification/packaging pipeline and `reports/P3`; retain P0/P1/P2 historical evidence. Provide a single documented verification entry per OS and an aggregator for exact current local/CI qualification results. External native evidence may arrive later, but must match the tested source/package identity, platform and declared checks. Updating a verdict must never attach old PASS evidence to new code.

Separate distributable artifacts from the review archive. The distribution contains installable products, dependency manifests, bootstrap/config templates, operational docs and required licenses—not SDKs, model weights, caches, full test databases, personal paths or provider credentials. The review archive additionally includes allowlisted source, tests/generators/tasks, current raw verification/CI evidence, manifest and external SHA-256. Verify every archive member and reject unsafe paths/tampering.

Required documents, with equivalent clear filenames allowed:

1. `P3-REPORT.md`: actual final outcome, starting/final revisions, commands/results and exact unresolved items.
2. `ACCEPTANCE.json` and `QUALIFICATION.json`: P3-A01–A25, per-OS/runtime/integration results, implementation-review state and mechanically derived release GO/NO_GO with reasons.
3. Release manifest/inventory/checksums and installed version/capability/compatibility matrix.
4. `INSTALL.md`, `UPGRADE.md`, `BACKUP-RESTORE-ROLLBACK.md`, `UNINSTALL.md`, each with tested command examples and actual side effects.
5. `WINDOWS-VALIDATION.md`: architecture/lock/process/path design, native host/filesystem/shell details, coverage mapping, CI IDs/source/package bindings and executed/raw results.
6. `OPENCODE-INTEGRATION.md`: tested project-local bootstrap/doctor, companion/native boundary, permissions/config preservation, exact host evidence and NOT_RUN limits.
7. `UMUH-ONBOARDING-REHEARSAL.md`: fixture definition, independent expected behavior, clean-package workflow, changes/gates/capture/approval/history, interruption/restore and isolation evidence.
8. `RELEASE-VALIDATION.md`: eShop/native fixture results, nonempty lifecycle tests, bounded-work/accounting comparison and limitations.
9. A concise production adoption runbook: prerequisites, backup/preflight, preview/approval, smoke, failure/rollback decision and verification. It is a rehearsal/runbook, not authorization to perform real IPM/UMUH cutover.
10. Current run ledger, source/package/CI/artifact manifests, logs/results, verified review ZIP and external SHA-256.

Self-review the operational failure windows, especially Windows child ownership, stale preview/receipt reuse, incomplete backups, absolute verifier paths, repeated capture ownership and pre-lease concurrency. Repair discovered issues and execute a final coherent verification after source changes. Do not use a positive narrative to override failed/missing evidence.

## 15. Final handoff and reference material

Commit the completed P3 work and report exact branch/revision, distribution paths/checksums, verification commands, actual result summary, review packet and every failed/blocked/NOT_RUN condition. If native Windows evidence is unavailable, include the implemented ready-to-run native suite/workflow and retain the explicit Windows NO_GO; finish all other authorized work. Do not ask the user to approve a vague plan in place of implementing the deliverable.

Label the result **P3 submitted for external review**. Do not merge, publish, deploy or certify real IPM/UMUH migration. The user should receive a concrete release candidate that can be transferred and exercised, with precisely stated qualified profiles and no hidden dependency on the development checkout or a deleted P2 branch.

Useful authoritative references; verify the details relevant to the chosen implementation:

- [Microsoft: Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).
- [Microsoft: JOBOBJECT_BASIC_LIMIT_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information).
- [Microsoft: Terminating a Process](https://learn.microsoft.com/en-us/windows/win32/procthread/terminating-a-process).
- [Python 3.12 subprocess](https://docs.python.org/3.12/library/subprocess.html).
- [GitHub Actions workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax).
- [GitHub Actions workflow commands / PowerShell encoding](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands).
