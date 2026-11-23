# Knowledge /update-by-CR — Independent Review R1

Date: November 23, 2026.

**Verdict: request changes for one P1 correctness issue. Three additional P2 workflow issues are reproduced below.** The feature is implemented end to end, and the ordinary merged-PR path works. This is not a rejection of the command/backend architecture or the earlier SQLite optimization.

Repository: [Ermak-P/Knowledge-](https://github.com/Ermak-P/Knowledge-). Reviewed branch: `codex/update-by-cr`; head: `3c9d1ed6aa43091866e1f4873e78d0e31e58b058`, rechecked at the end of the audit. Qualified implementation commit: `1a4999fa62a0d78a9d331d4f6f9396a0bef73995`. Original assignment: `Knowledge-Update-by-CR-Codex-Task.md`, November 22, 2026.

All four findings were reproduced against the **installed delivered wheel**, outside the source checkout, using temporary synthetic projects. No application repository, real IPM database, user OpenCode configuration, or GitHub branch was modified.

## Findings

| ID | Priority | Problem | Relevant acceptance scenarios |
|---|---|---|---|
| UCR-R1-01 | P1 | An unmerged successor PR can overwrite a confirmed target-state Knowledge record | UCR-09, UCR-10, UCR-11 |
| UCR-R1-02 | P2 | Refreshing sources after preparation loses ownership of the workflow's pending candidate | UCR-09, UCR-13, UCR-15 |
| UCR-R1-03 | P2 | An unchanged contract inside a modified file cannot be represented as a nonchange | UCR-03, UCR-04 |
| UCR-R1-04 | P2 | Two successive CR workflows in one native chat leave conflicting host bindings | UCR-01, UCR-10, UCR-13 |

### UCR-R1-01 — Preserve current target knowledge when saving an unmerged proposal

Location: [`cr_workflow.py`, line 242](https://github.com/Ermak-P/Knowledge-/blob/3c9d1ed6aa43091866e1f4873e78d0e31e58b058/packages/knowledge/src/knowledge/cr_workflow.py#L242), and the update operation at [line 272](https://github.com/Ermak-P/Knowledge-/blob/3c9d1ed6aa43091866e1f4873e78d0e31e58b058/packages/knowledge/src/knowledge/cr_workflow.py#L272).

Automatic claim identity uses project + CR + decision key. It does not distinguish an unmerged proposal from the active target decision. `_build()` finds the existing record under that identity and prepares an update regardless of PR merge status. Lowering the new record's confidence and adding a branch disclaimer does not preserve the previous active fact.

Reproduction:

1. Save merged PR 8 for CR 7. The target implements four attempts. Decision `retry-limit` becomes a confirmed claim at revision 1 and appears in normal context retrieval.
2. Create a distinct, open PR 9 for the same CR proposing six attempts. Keep the target checkout unchanged at four attempts.
3. Save the proposal through normal analyze/prepare/exact-plan apply/acknowledge, using the same decision key and no explicit existing ID.
4. The previous claim becomes revision 2, `NEEDS_HUMAN_CONFIRMATION`, with the six-attempt proposal. Normal context retrieval no longer returns the four-attempt claim. The target commit and source still implement four attempts.

The former revision remains in history; the defect is loss of the applicable fact from **current ordinary retrieval**, not irreversible deletion. A future agent loses the valid target constraint merely because a proposal was recorded. Explicit approval of saving a branch proposal does not make that proposal an implementation change on the target.

**Required correction:** preserve the current canonical target identity and store unmerged/closed proposals under a separate applicability/identity, or refuse the conflicting write with a precise non-destructive result. An explicit `existing_id` must not bypass this separation. Preserve stable target revision history when a later merged PR actually changes the target. Apply the same principle to retirement operations.

Acceptance additions: save merged PR A, then open and closed-without-merge PR B for the same CR/key; default retrieval must retain A while optional proposal retrieval exposes B with its scope. Test explicit existing IDs and retirement requests. After B merges and its implementation is present on the selected target, a supported approved update must retain canonical history.

Evidence: `probe_proposal_scope.py`; `evidence/proposal-scope-regression.json`, including before/after lookup, default retrieval, exact receipts, unchanged target commit/source, and installed import path.

### UCR-R1-02 — A source refresh strands the workflow's own queued candidate

Location: [`cr_workflow.py`, line 129](https://github.com/Ermak-P/Knowledge-/blob/3c9d1ed6aa43091866e1f4873e78d0e31e58b058/packages/knowledge/src/knowledge/cr_workflow.py#L129), and ownership-based cleanup at [line 288](https://github.com/Ermak-P/Knowledge-/blob/3c9d1ed6aa43091866e1f4873e78d0e31e58b058/packages/knowledge/src/knowledge/cr_workflow.py#L288).

`sources()` archives the old proposal and clears `state.proposal` when a source fingerprint changes. Its already queued candidate remains pending. Later `prepare()` can defer a superseded owned candidate only through the now-cleared current proposal reference, and therefore treats that candidate as unrelated work.

Reproduction: prepare a plan; add a PR discussion comment to the normalized source snapshot; refresh sources and reassess the same implementation; try preparing again. The only pending candidate is the old candidate from this workflow, yet the result is `ucr-unrelated-pending-candidates` containing that candidate ID. The new plan cannot proceed through the ordinary interview flow without a separate manual disposition.

Refusing truly unrelated candidates is correct and must remain. This finding concerns ownership lost during the workflow's **own required refresh**, including the documented pre-approval reobservation step.

**Correction:** durably retain the superseded proposal/candidate ownership and resolve it through supported lifecycle operations before preparing the replacement. Preserve stale-approval invalidation and make interruption/retry safe. Do not dispose or approve another workflow's candidates.

Acceptance additions: metadata/comment change and head/target change after preparation; refresh, reassess, prepare, and apply the replacement without manual queue repair. Verify old approval rejection, owned-candidate history, crash recovery, and preservation of genuinely unrelated candidates.

Evidence: `probe_workflow_edges.py`; `refresh_after_prepare` in `evidence/workflow-edge-probes.json`.

### UCR-R1-03 — Nonchange validation compares the entire file

Location: [`cr_workflow.py`, line 176](https://github.com/Ermak-P/Knowledge-/blob/3c9d1ed6aa43091866e1f4873e78d0e31e58b058/packages/knowledge/src/knowledge/cr_workflow.py#L176).

For a nonchange's neighbor/contract anchor, validation requires the complete file bytes at PR base and head to be equal. The contract itself may be untouched while another member in that file changes, a normal C# case.

Reproduction: change only `MaxAttempts` from four to six in `Retry.cs`, leaving `PublicName()` on its own line unchanged. Submit a `nonchange` decision anchored precisely to the unchanged public method. Analysis fails with `ucr-nonchange-not-established`, although the pinned contract excerpt is identical at both revisions.

This prevents the intended representation of a material compatibility boundary. Reclassifying the item as a generic decision can work around the validator, but should not be required to capture an intentional nonchange.

**Correction:** establish unchangedness for the referenced member/contract or explicitly mapped pinned ranges, with sufficient surrounding evidence, rather than requiring the entire containing file to be untouched. Keep rejection of an actually changed contract; do not remove source validation.

Acceptance additions: unchanged public member in a modified file succeeds; changed anchored contract fails; existing separate-file nonchange tests continue to pass.

Evidence: `unchanged_member_in_modified_file` in `evidence/workflow-edge-probes.json`, including complete before/after fixture text and the submitted line-3 anchor.

### UCR-R1-04 — Completed workflows retain a conflicting native chat binding

Location: [`cr_workflow.py`, line 103](https://github.com/Ermak-P/Knowledge-/blob/3c9d1ed6aa43091866e1f4873e78d0e31e58b058/packages/knowledge/src/knowledge/cr_workflow.py#L103), binding checks at [line 110](https://github.com/Ermak-P/Knowledge-/blob/3c9d1ed6aa43091866e1f4873e78d0e31e58b058/packages/knowledge/src/knowledge/cr_workflow.py#L110), and creation at line 119.

Reproduction: complete and save the first CR workflow with host session `same-native-chat`; start a second CR/PR pair in that chat; invoke the command again without arguments. Two stored workflows still match the host session, so `start()` returns `ucr-ambiguous-session`. Repeating the second pair's explicit links or its explicit resume ID with that same host session also fails: `ucr-host-already-has-active-workflow`, because the completed first workflow still has a source.

These are the actual backend calls made by the packaged native hook. This audit exercised those calls directly against the installed backend, rather than claiming a second real OpenCode UI run. Continuing from a different chat is a workaround, not a solution for sequential reviews in the same chat.

**Correction:** maintain an unambiguous active workflow binding for a host chat. Detach or otherwise exclude completed historical bindings when selecting/starting the next workflow, preserving receipts/history and explicit resume. Do not allow duplicate active bindings on the new-session branch.

Acceptance additions: save CR A, start CR B in the same chat, then invoke without arguments and explicitly resume B. Verify native-hook behavior, restart/resume, and independent historical access to A.

Evidence: `same_native_chat_two_workflows` in `evidence/workflow-edge-probes.json`.

## Verification and evidence scope

| Check | Result | Scope |
|---|---|---|
| Exact delivered kit installation outside checkout | PASS | Full and Knowledge-only profiles |
| Source identity | PASS | All 248 manifest assets match; computed identity `a09c9364beaa434d5ab35e3af97f396ad8b7fdfd9ba5c2c5167aff7747b0e0ab` |
| Installed byte identity | PASS | All 61 published installed package assets match |
| Focused update-by-CR tests | PASS | 27 tests, including normal fresh-process retrieval and two decision domains |
| Full local suite | PASS | 389 run, 378 passed, 11 platform-dependent skips; installed candidate packages |
| Independent Knowledge-only persistence | PASS | Harness and MCP absent; actual canonical save and normal retrieval |
| Independent additional probes | Four issues reproduced | Installed packages; synthetic Git repositories; no production mutations |
| Live GitHub Actions state | SUCCESS | [Run 45066137182](https://github.com/Ermak-P/Knowledge-/actions/runs/45066137182), implementation commit `1a4999f...`; both platform verification jobs succeeded |
| Retained Windows qualification | PASS as published | 389 passed, no skips; independently checked CI status, not rerun locally |
| Native OpenCode 1.19.6 | Retained controlled-provider profile PASS | Reviewed registration/dialogue/answer/save evidence; no independent native executable run in this audit |
| Actual model semantic replay | NOT_RUN | Controlled fixtures do not establish arbitrary-model decision equivalence |
| Live tracker acquisition / local .NET behavioral replay | NOT_RUN in this audit | Product tracker subprocess boundaries and retained .NET fixture evidence have narrower, explicitly labeled scope |

The kit ZIP SHA-256 is `b1b7eac4aa0d4d950f0613986ff223cb2de482ba708327f3813b3add617a34e0`. This audit verified that digest and the source/installed manifests, rather than relying on the unchanged `0.5.0rc1` version string.

The first local full-suite attempt had one missing historical `release/kit/install.py` fixture in the audit's partial source materialization. Its failure log is retained for transparency. The exact file was fetched and verified against Git blob `3988f4080028d17a0e906b43fe3d92ebec0f93ce`; the completed full run then passed. This was an audit setup omission, not a product defect. The additional historical P1 contract fixture also matches its Git blob. Product implementation bytes were not patched.

## What is working and should be retained

The foreground command has a real installed backend and host hook. It requests missing links, stores interview progress in the existing SQLite ownership model, captures immutable supporting evidence, and saves normal schema-valid claims through existing candidate/plan/apply/acknowledge APIs. Normal retrieval and fresh-process fixtures work. Unknown answers and new future preferences remain distinguishable from confirmed historical reasons. Exact-plan approval, source freshness, CAS, unrelated-candidate isolation, installed asset ownership, and Knowledge independence are exercised by substantive tests.

Keep the current small command/backend split and reuse of lifecycle APIs. No new knowledge database, inference service, mandatory Harness dependency, or general workflow framework is needed to fix these findings. The explicitly disclosed absence of a live-model semantic run is an allowed limitation of the assignment and is **not** an additional release blocker.

## Suggested agent handoff

Implement UCR-R1-01 first and treat it as the acceptance blocker. UCR-R1-02 through UCR-R1-04 are P2 follow-ups; they do not erase the demonstrated success of the basic path. Fix them in the same revision if completing the full workflow acceptance scope.

Add behavioral regression cases for the reproduced combinations, preserving normal exact-plan approval and lifecycle ownership. Run the focused tests and full affected suite, rebuild and install the official kit outside the checkout, and publish source/package hashes for the fixed revision. Retain platform distinctions and the honest live-model NOT_RUN status. No rollout into IPM, global OpenCode configuration change, or unrelated SQLite work is required.

The companion `Knowledge-Update-by-CR-Review-R1-Evidence.zip` contains independent probe programs, structured before/after evidence, byte verification, installation and test logs, provenance, and reproduction instructions.
