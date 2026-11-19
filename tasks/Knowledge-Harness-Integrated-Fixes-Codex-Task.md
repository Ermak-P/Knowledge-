# Codex assignment — fix the Knowledge + Harness integration before the UMUH pilot

**Deliver one reviewable correction to the existing product.** An operator must be able to run a scoped C# task, commit its changes, refresh candidates, approve an observed fact, and recover interrupted candidate delivery without restarting application work. The same workflow must handle a normal Windows checkout, respect configured limits and work from the transferred kit.

**Repository:** [Ermak-P/Knowledge-](https://github.com/Ermak-P/Knowledge-). The integrated review reproduced the defects on merged P4, version `0.4.0rc3`, at `4345352cb0fb8c20a19b51f9227fe91424c250de`. Start from current `main` in an ordinary checkout and record the base SHA. If a later commit has fixed a case, demonstrate it with the regression and keep that fix. Use one topic branch, suggested name `codex/integrated-fixes`. The owner handles merge and branch cleanup.

Own implementation, tests, CI and delivery as a single assignment. Choose the internal design. Use installed packages, disposable projects and the existing deterministic HTTP fixture for repeatable verification. All seven outcomes below are in scope. Private UMUH/IPM data and a live model are reserved for the subsequent pilot.

## 1. Give capture retry delivery-only semantics

The reviewed CLI routes `harness-run capture-retry` and `resume` to the same driver. An interrupted task made eight more HTTP requests and edited `Feature.cs` when the operator retried delivery. Conversely, a completed run with optional capture and a pending outbox row returned success without retrying submission.

Implement a delivery-only operation under the existing ownership/lease mechanism. Load and validate durable eligibility under the lease. Ordinary execution recovery belongs to `resume`. Preserve the original capture event, payload, timestamp and candidate identity across retries.

Verify through the installed CLI:

- Interrupt a task after a saved provider response and before its first edit. Invoke `capture-retry`. Assert zero additional provider requests, edits and recipe launches, unchanged source bytes and an explicit ineligible outcome. Then use `resume` to demonstrate ordinary recovery.
- Exercise both required and optional capture. Inject a transient Knowledge submission failure after outbox creation, clear it, then retry. Assert one delivered candidate with the original identity and an accurate final capture status, including the previously `completed-degraded` case.
- Cover repeated and competing retries, including interruption after Knowledge has accepted the payload but before Harness saves the receipt. The pending delivery must converge to one receipt for one logical candidate.

Suggested entry points are `harness/run_cli.py`, `engine.py` and `capture.py` under `packages/harness/src`.

## 2. Make post-commit candidate review recoverable

Use a real Git checkout. Harness changes a C# declaration and captures a pending candidate. Prepare a plan, then commit exactly those source bytes. On the reviewed revision, a rescan suppresses the replacement because its operations look equivalent. The old candidate blocks preparation with `source-drift-rescan-required`. Deferring it can make the declaration disappear from the eligible batch.

Provide a documented recovery path through the normal candidate commands. Allow a freshly observed fact to become eligible against the current snapshot. Keep the original record and human decisions auditable. An approval issued for the old snapshot must remain invalid. A previously rejected or deliberately deferred observation must retain its disposition across equivalent rescans.

**Acceptance scenario.** Run two Harness tasks, commit their changes, refresh candidates, inspect a fresh plan, apply it with its exact fingerprint, acknowledge it and query the affected declaration. Assert the exact claim ID is present and active once, unrelated pending candidates remain reviewable, the next plan omits acknowledged work, and rejected/deferred observations retain their decisions. Verify that an observation whose meaning actually changed goes through fresh review. Include a pending candidate created by the prior release or an equivalent persisted fixture. Everything before explicit approval must leave canonical facts untouched.

Inspect scan and capture deduplication in `packages/knowledge/src/knowledge/discovery.py` together with plan validation and queue dispositions.

## 3. Make Git-backed retirement work on LF and CRLF checkouts

Create two ordinary repositories with `*.cs text eol=lf` and `*.cs text eol=crlf`. Force an actual checkout conversion and verify bytes on disk. In each, commit a file declaring `EM`, scan, approve and acknowledge the fact, delete the file in a second commit, then scan and reconcile that exact commit range.

**Acceptance.** Both clean worktrees are classified as clean and both produce a reviewable retirement proposal when coverage is complete and references are absent. The original fact retains its history. Retirement takes effect through approved lifecycle operations. Assert that genuine staged/unstaged changes are still detected and incomplete evidence still prevents retirement. Exercise both policies in native Windows CI. Keep raw working-file evidence and Git blob identity comparable in their respective domains, including for existing stored evidence where proof is available.

## 4. Apply one file-size policy through run completion

Configure `file_bytes=2000000`, add an unrelated 1,100,000-byte text file and run a task-v2 change. On the reviewed version, build, test and review passed but finalization returned `source-file-too-large` because capture and finalization fell back to 1 MiB.

**Acceptance.** The run completes and delivers its candidate with the configured limit. Repeat with a recoverable capture failure and delivery retry. A file above the explicit limit must still be refused. Preserve the source/configuration drift checks and honor the policy bound to the run at each snapshot comparison. Check start, resume, capture and finalization for inconsistent defaults.

## 5. Honor the extraction budget across the public initialization command

On the pinned eShopOnWeb checkout, a fresh `knowledge-init --max-files 1` reported one extraction while a counting wrapper forwarding to the real extractor saw 421 calls across scan and reconciliation. Inventory enumeration and content hashing were excluded from this measurement.

**Acceptance.** Count real extraction work over the entire public command. The first chunk, subsequent partial chunks and the chunk completing the scan must each respect their declared budget. Final results must match an uninterrupted scan of the same snapshot. Exercise a nonempty store and an ambiguous declaration split across chunks. Preserve stale-snapshot handling and prevent negative conclusions from partial coverage. Document which inventory/hash work remains proportional to repository size. A changed counter alone does not satisfy the regression.

## 6. Make the ZIP sufficient for first use

The reviewed ZIP installs correctly, but its usage guide points to a task example and provider/recipe documentation absent from the archive. Ship a working runner template, a compatible task-v2 example, and the instructions needed to adapt the project root, endpoint/model and trusted build/test executables. Include usable commands for Windows PowerShell 5.1 and Linux. Keep credentials out of examples. State the requirements for optional MCP separately.

**Acceptance.** Extract the final ZIP outside the source checkout. From its contents, install the Knowledge-only and full profiles in fresh environments. Show that Knowledge works independently. Using the full profile, follow the shipped instructions to configure a disposable project and run the sample through real build/test recipes, review and capture with a controlled provider. Record any fixture prerequisites explicitly. Verify that the files and relative references needed by this procedure resolve inside the kit.

## 7. Run qualification on the branches used for development

The reviewed workflow automatically verifies pushes only to the former `p4` branch. Enable automatic Linux and native Windows verification for pull requests targeting `main` and relevant pushes to `main`. Keep manual dispatch. Ordinary pull request validation must work with read permissions. Restrict any write-capable evidence publication to trusted events. Avoid recursive qualification triggered solely by evidence publication.

**Acceptance.** Show the actual Linux and Windows jobs for the correction PR, with run URLs and tested revisions. Verify the `main` trigger in the workflow; the owner will perform the merge. Use the existing qualification path and retain raw results for failed as well as successful runs.

## Delivery and review

- Add focused regressions for the failures above. Where practical, demonstrate the failing observation on the reviewed baseline and the passing result on the correction. Count actual effects: HTTP requests, process launches, source hashes, candidate IDs/dispositions and extractor invocations. Status strings alone cannot establish those outcomes.
- Run the existing installed-product suite and pinned eShopOnWeb .NET application scenario. The public fixture is `0c2c95d9d450d07fcd4e96e95e1cd48c20834e99`, SDK `10.0.404`. Preserve the existing 49-test baseline, the new regression failing before the repair, and 50 passing afterward. If the remote session blocks MSBuild named pipes, use the qualification CI runners and link their results.
- Preserve Knowledge's independent installation, task-v1 compatibility, P4 bounded execution, current project ownership rules and the exact-approval workflow. Give the corrected kit a distinguishable release identity following repository conventions. Verify the upgrade path from `0.4.0rc3` with pending data and the existing supported recovery scenarios.
- Return the branch and PR link, implementation and tested SHAs, kit location and SHA-256. Include a compact seven-row acceptance table with the command or test, observed result, and evidence link for each outcome. Give test totals per OS, explain skips or blocked runs, and identify any remaining limitation. Keep the PR open for independent review.
