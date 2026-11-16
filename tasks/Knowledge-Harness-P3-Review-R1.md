# Knowledge + Harness — P3 independent review, correction round 1

Date: 2026-11-16.

Repository: https://github.com/Ermak-P/Knowledge-

Reviewed branch/revision: `p3` / `453e5625ee939e338d4430927ca4f13e8c6938c8`.

Tested implementation revision named by the submitted evidence: `3c28581124a4b045f1339c09fa3fd6bcd06f2983`. Its product/source inputs match the delivery revision. Accepted P2 baseline: `91689475a283a2cdc654cfb6090074f0251f895d`.

## Decision and assignment

**P3 is not accepted yet. Complete a narrow consolidated correction for P3-R1 and P3-R2 below, then submit a fresh release candidate and review packet.**

The release/Windows work is substantial, and the native evidence is real. The remaining blockers are in the new companion's authorization and approved-removal boundaries, not absence of Windows implementation or CI.

Preserve the current architecture, independently verified release behavior and accepted P0–P2 invariants. Fix both cases autonomously, add meaningful regressions and regenerate evidence. No need to restart P3 or redesign the entire host integration. Keep merge, publication, production adoption and deployment user-controlled. Commit the finished correction and name its exact revision.

## Independently verified strengths

- Fresh install of the submitted packages and independent Linux suite: **171 discovered, 161 passed, 10 explicitly native-Windows-only skips**. No test failures. The submitted regression map retains the 138 accepted logical cases.
- Verified GitHub Actions run [43755985622](https://github.com/Ermak-P/Knowledge-/actions/runs/43755985622), head `3c28581124a4b045f1339c09fa3fd6bcd06f2983`: both Ubuntu 24.04 and Windows 2022 jobs completed successfully. The Windows job actually executed the native PowerShell step.
- Validated the collected native source/run/artifact ledger, package identities and raw test results: **171/171 passed, zero skips**, Windows Server 2022 / NTFS / Python 3.12.10 x64 / Windows PowerShell 5.1. The required native check groups are present and PASS. This is verified native CI evidence, not an independent local Windows execution by the reviewer.
- All **892 review ZIP members**, their hashes, current checkout bytes and the external checksum match. Current source identity: `8f7fbfb6ecd243e64b9bbcd927bee157a03df7bd28b37f880b48954617582ed2`; local verification run: `487b8e58b2c645db988705ff213f362c`.
- Independently rebuilt the distribution from current source. It is byte-identical to the submitted distribution: SHA-256 `aac287cb6e3092a6e39038123111dbedaf6f7404d8627bfa4d2e9e7011c907cc`. Both wheel hashes also match the native/local manifest.
- Independently ran transferred-release packaging checks: network-blocked core install on Linux, independent Knowledge, installed CLIs, full profile, product-only uninstall/reinstall, retained-store validation, launcher error propagation and tamper rejection all passed.
- Additional reviewer probes interrupted restore during the **second metadata directory's** old/new rename windows; recovery succeeded and preserved exact logical state. The existing suite's first-directory crash checks are not the sole evidence for this boundary.
- Fresh submitted application and UMUH-like rehearsal evidence is present and bound to the verified source. Its successful .NET results remain submitted/CI results; this review does not claim an independent successful local .NET application run.

The original/native test suites do not cover the following two failures. Both were reproduced against the actual final implementation. The first used actual HTTP provider calls, production runner tools and real process gates; only a scheduling seam triggered the concurrent file replacement.

## P3-R1 — High: an enrolled read-only task can become an unapproved coding task

Location: `packages/harness/src/harness/companion.py`, `doctor()` lines 56–64 and `run_task()` lines 66–70 at the reviewed revision.

### Reproduction

1. Initialize the ordinary synthetic project and runner configuration with the delivered HTTP fixture provider.
2. Write `task.json` using `task(kind='read-only')`: empty writable paths and recipes. Install the companion through exact preview/approval, enrolling that file under `approved_task`.
3. Trigger `run_task(root, 'approved_task')`.
4. Between the task read in `doctor` and its later use, replace `task.json` with the valid broader `task()` coding payload. The scheduling probe delegates the first read unchanged, then writes the replacement before returning those already-read bytes. It does not mock `engine.start`, role decisions, gates, source writes or execution success.

Current code checks the first payload's digest in `doctor`, then reads settings/task again and passes the **second payload** to `start` without checking it against the enrolled digest.

Observed result:

```text
enrolled kind: read-only
replacement kind: coding
run: completed / execution=passed
Feature.cs changed through the Coding tool: true
actual HTTP provider calls: 13
```

This directly contradicts the advertised property that the hidden enrollment digest prevents replacing a source task JSON with broader scope and silently running it. It is not an OS-sandbox claim or an attempt to make hostile build programs safe.

### Required result

Bind the execution input to the exact validated enrolled task, root/runtime/config and relevant enrollment state across the ownership boundary. Do not validate one filesystem read and execute another. Reuse an immutable validated payload, and/or perform the validation and handoff under appropriate ownership with an expected enrollment identity passed into the runner. Ordinary `doctor` output must not act as reusable authority for later different bytes.

Recheck authority where execution actually starts; a pre-lock validation or an extra unsynchronized check immediately before another read is not a sufficient concurrency fix. Preserve runtime role/tool/gate checks and all existing root/state controls.

If the file changes, an acceptable outcome is explicit stale/review-required refusal, or execution of only the immutable originally authorized read-only payload. An unauthorized coding scope must never reach the provider/tools. Do not simply trust the provider/reviewer to notice the scope change.

### Closure criteria

- A deterministic replacement-window regression proves an enrolled read-only payload cannot execute as coding and cannot modify the application, runner policy or canonical Knowledge. Count actual tool/process/provider effects, not just returned error text.
- Exercise the same production entry through the configured companion MCP tool, as well as the underlying API where useful.
- Cover changed writable paths/recipes and changed enrollment/configuration while waiting to acquire run ownership. A once-valid check is not permission to use a different task or enrollment.
- Retain successful unchanged enrolled execution, unknown-name rejection, source task digest checks, version/root/runtime checks, P2 verifier protection and final-source build/test/review gates.

Affected requirements: P3-A15, A18, A23–A24, plus retained P2 role/scope authority.

## P3-R2 — High: remove approval does not bind the bytes actually restored

Location: `packages/harness/src/harness/companion.py`, remove-preview construction lines 15–18/33 and `apply()` lines 36–47.

### Reproduction

1. Start with `opencode.json` containing `{"model":"original-approved"}`; install the companion normally.
2. Create an exact remove preview. Its approved desired configuration is `{"model":"original-approved"}`.
3. Leave the current live `opencode.json` untouched. Change only `.harness/companion.json`'s saved `original_bytes`/`original` to `{"model":"unreviewed-replacement"}`.
4. Apply the original remove preview with its correct fingerprint.

Observed result:

```text
approved desired: {model: original-approved}
apply: ok=true / operation=remove
actual restored: {model: unreviewed-replacement}
```

Apply checks current host bytes against the preview, but then reloads `installed['original_bytes']` from mutable companion metadata and uses those unapproved bytes. The preview/fingerprint does not bind that state. A normal source snapshot also excludes this hidden metadata.

### Required result

The exact removal preview/approval must bind the relevant companion state and the exact restoration bytes/absence. Validate that dependency under acquired ownership; restore only the approved snapshot. If enrollment/installation metadata or another relevant input changed, refuse as stale and preserve current configuration rather than reading a different restoration target after approval.

Preserve byte-for-byte restoration for an unchanged valid installation, including whitespace/Unicode and original absence. Do not weaken the existing live-host-config conflict check or silently canonicalize the user's original bytes to hide a mismatch. Unsupported metadata/operation versions must refuse safely.

### Closure criteria

- The metadata-change reproduction above is rejected before `opencode.json` changes, or can only restore the immutable exact approved bytes if that is the explicitly documented policy.
- Cover a changed original-absence value, changed enrolled tasks/installation identity and a live host edit. No stale approval may delete/overwrite a different configuration or remove a newer installation marker.
- A valid unchanged remove still restores the exact original file bytes/absence, retains the documented backup/history and leaves unrelated project/global configuration untouched.
- Include the new negative tests in installed-product verification; do not rely solely on development-tree function tests.

Affected requirements: P3-A15, A18, A23–A24 and the promised exact-preview/reversible bootstrap behavior.

## Definition of done and evidence refresh

1. Fix P3-R1/R2 in production code, with named executed regressions for the exact races/dependencies above. Preserve all 171 existing logical test cases and required per-platform coverage. Do not relabel a coding task as read-only after its writes or claim restoration success for unapproved bytes.
2. Exercise unchanged and adverse companion flows through the installed distribution, real configured MCP transport and guarded runner. Retain the offline core/install/uninstall and nonempty lifecycle/recovery guarantees.
3. Rebuild reproducibly and run the coherent verification against the final corrected source/package. Refresh Linux and native Windows evidence: the existing successful CI is genuine, but it qualifies the old package and must not be attached to changed wheels/source as fresh qualification.
4. Regenerate source/package/run/CI bindings, acceptance/qualification matrix, operational documents where the contract changes, distribution/review ZIP inventories and external checksums. Include P3-R1/R2 → implementation → named regression → actual result.
5. If current native evidence cannot be collected, finish the code/package/tests and mark that revised Windows profile NOT_RUN/NO_GO according to the P3 task; do not borrow the old native PASS. Keep optional live OpenCode/model checks distinct from the real MCP/runner verification.
6. Commit the completed correction, report exact revision/verification commands/artifact locations, and keep P3 submitted for independent review. Do not merge, publish or deploy.

This is a focused correction to two companion authority boundaries. The already verified Windows backend, release reproducibility, lifecycle tooling and onboarding work should remain intact.
