# Knowledge + Harness: audit stages 1–2, independent review R1

Date: 2026-11-22. Repository: https://github.com/Ermak-P/Knowledge-

Reviewed branch: `codex/audit-stages-1-2`.
Reviewed HEAD: `7eb3c8089ddf4a7f6f1434a95d9e307f8e8e6c9b`.
Product code commit: `74b2dee16aaf8fd0dfe25854fae47d8bf8bcf016`.
Assignment baseline/main: `152e372eafac74c39236a3f6b0e55808769d910e`.

## Decision

**Changes requested. Keep the implementation, but do not accept stages 1–2 as complete yet.** Three reproducible gaps remain: an unknown denial/condition can still become a startup grant; conditional language can clear a current denial; P4's optional Knowledge tool bypasses the new legacy freshness protection.

The positive work is substantial and independently observable: source gaps are explicit; transfer phases recover; normalizer outages have durable envelopes; fresh architectural knowledge is automatically delivered; dependencies and filtered evidence have bounded diagnostics. A rewrite or broader redesign is unnecessary. One focused correction round should address the findings below and repeat the relevant qualification.

No repository code, GitHub branch, user database, IPM configuration, or real Docker resource was changed by this review. All execution fixtures were temporary and owned by the review.

## Findings

### R1 — P1: unrecognized denial/condition still becomes an executable startup grant

Location: [startup_authorization.py, lines 79–103](https://github.com/Ermak-P/Knowledge-/blob/7eb3c8089ddf4a7f6f1434a95d9e307f8e8e6c9b/packages/knowledge/src/knowledge/startup_authorization.py#L79). Related ingress paths: `operations.ingest()` and `semantic_ingress.ingest()`.

`startup()` rejects known `DENIAL` expressions and a finite `LIMITING` vocabulary, then accepts one recognized positive clause. Other clauses can disappear without being represented or marked uncertain. Sharing this helper removes the earlier catalog/semantic divergence, but does not establish the promised full-message boundary.

Independent public host/CLI ingress reproductions:

```text
Remember Kafka: Do not automatically start the container. You may start container fixture.
Запомни Kafka: запрещено запускать контейнер. Разрешаю запуск контейнера fixture.
Remember Kafka: You may start container fixture. Approval is required before startup.
```

Each message was tested through both `catalog` and `local-model`. The semantic profile used a deliberately wrong but schema-valid local HTTP normalizer response proposing the positive quote. The catalog profile does not depend on that model response.

**Observed in all six cases:** ingress `ok=true`; the actual SQLite record has `recovery_authorized=true`; the current restriction is absent; the stopped-resource `DockerContract` receives exactly one start. The original text is retained, so the failure is in authorization, not loss of input.

**Expected:** no new executable grant when a denial conflicts with permission or an authorization-related condition is not represented. Safe readiness remains available. This is specifically required by AUD-02; it is not a demand to understand arbitrary natural language.

Correction expectations:

- Apply a conservative, documented whole-message contract before granting. Merely adding these three strings to another blacklist will leave the same failure mode.
- Unrepresented authorization-related clauses must prevent a new grant and must not weaken an existing restriction. Preserve supported ordinary clarification and positive stopped-container cases.
- Cover semantic/catalog, CLI/host, historical replay and intentionally incorrect schema-valid model proposals. Keep all allowlist/resource/binding checks.

Evidence: `kit-authorization.json`, rows 1–6; `probe_authorization.py`; the six subtest failures in `review-regressions.log`.

### R2 — P1: a conditional clear removes current no-start before approval

Location: [startup_authorization.py, lines 63–68](https://github.com/Ermak-P/Knowledge-/blob/7eb3c8089ddf4a7f6f1434a95d9e307f8e8e6c9b/packages/knowledge/src/knowledge/startup_authorization.py#L63).

`restriction()` validates a proposed `clear-denial` using `any(CLEAR.fullmatch(...))`. It does not apply the limiting-condition checks used by `startup()`. Thus this remains a separate bypass even if startup's vocabulary is expanded.

Public host-session reproduction:

1. Store an existing operator-approved startup grant for the independently allowed fixture binding.
2. Submit `Do not start services in this run.` The durable session correctly contains `no-service-start`.
3. Submit `You may start services again. Only after approval.` A schema-valid normalizer proposes `intent=none`, `current_start=clear-denial` with the positive sentence as its source quote.
4. Execute the same bound dependency with this actual host session attached.

**Observed:** `restriction=clear-service-start-denial`, session restrictions change from `["no-service-start"]` to `[]`, all source envelopes are resolved, and the Docker boundary double receives one start. No approval event occurs.

**Expected:** the current prohibition remains effective until the condition is represented and satisfied through a supported mechanism. A positive quote from part of the message cannot cancel the rest. An unknown condition can instead yield explicit unresolved/blocked state.

Correction expectations:

- Give grant creation and current-denial clearing the same independent full-source scrutiny.
- Reject or fence conditional clear requests that the supported grammar cannot faithfully enforce, including when the model returns `intent=none`.
- Test an existing grant plus a current denial, conditional clear, replay/restart, and a later genuinely unconditional authorized clear. The positive clear path must remain usable.

Evidence: final row of `kit-authorization.json`; `probe_authorization.py`; `test_conditional_clear_keeps_current_denial_and_blocks_start` in the independent regression driver.

### R3 — P1: P4 Knowledge tool reintroduces withheld legacy facts as complete matches

Locations: [tools.py, line 125](https://github.com/Ermak-P/Knowledge-/blob/7eb3c8089ddf4a7f6f1434a95d9e307f8e8e6c9b/packages/harness/src/harness/tools.py#L125), [tools.py, lines 297–302](https://github.com/Ermak-P/Knowledge-/blob/7eb3c8089ddf4a7f6f1434a95d9e307f8e8e6c9b/packages/harness/src/harness/tools.py#L297), and [delivery.py, lines 57–65](https://github.com/Ermak-P/Knowledge-/blob/7eb3c8089ddf4a7f6f1434a95d9e307f8e8e6c9b/packages/harness/src/harness/delivery.py#L57).

The automatic delivery path uses `delivery.retrieve()` to withhold P0 records that have no lifecycle revision/current evidence proof. However, P4's broker still dispatches the optional `knowledge` tool directly to the legacy-compatible `tools.knowledge()` path. This bypasses the new P4 validation.

Independent installed-provider reproduction:

1. Create a genuine supported P0 store using `Store.init()`, submit/approve a `CONFIRMED` legacy claim with the statement `ImprovedFeature requires an unverified historical threshold.` Its evidence is not currently verified.
2. Start a fresh read-only P4 task. Its first request correctly has `available=false`, `partial=true`, reason `knowledge-lifecycle-upgrade-required`, and no statement.
3. The controlled provider makes one ordinary allowed `knowledge` tool call for `ImprovedFeature`.
4. Inspect the next actual provider request, not just a direct helper call.

**Observed:** the tool delivers the withheld statement with `available=true`, `result=matches`, `partial=false`, `confirmed=true`, `revision=null`, no current freshness, and no filtered diagnostic. The P4 run completes successfully. The provider never accesses SQLite directly.

**Expected:** P4 must apply its current-fact policy consistently to both automatic and optional retrieval. An explicit historical view would need a separate documented contract and unmistakable labels; the ordinary tool must not silently reverse the initial refusal.

Correction expectations:

- Apply a shared P4-facing validation at broker dispatch/response assembly, including Main, Coding, Planning and Reviewing. Avoid a circular helper dependency when consolidating the two paths.
- Preserve the standalone Knowledge and task-v1 legacy read contracts. Do not implicitly migrate or rewrite existing stores to make this test pass.
- Add a public P4 HTTP-provider regression that first observes the withheld initial slice, then calls `knowledge`, and verifies the following real provider request still excludes unverified text and reports the upgrade/review reason.
- Preserve successful P1 fresh retrieval, graph diagnostics, byte caps, tool pairing and saved-response recovery.

Evidence: `kit-legacy-tool.json`, `probe_legacy_tool.py`, independent regression driver.

## Verification performed

| Check | Independent result |
|---|---|
| Assignment and external audit | Read current saved task and audit; compared all seven assigned AUD IDs with implementation and evidence |
| Branch/source identity | Exact reviewed HEAD; source map equals `reports/AuditStages12/source.json`; identity `49e8be70d9398daea601520d5f8e7dfcced4c7e64c9f2cd48938e30ffd8a3e27` |
| Clean independent setup | `scripts/setup_p3.py` installs current packages; no editable import substitution |
| Full local stock suite | **333 total: 322 PASS, 0 FAIL, 0 ERROR, 11 native-Windows-only SKIP**, 222.374 seconds |
| Real permission refusal | Stock AUD-01 test passed as ordinary Linux uid 1000; no permission mock substituted for its real refusal |
| Other new stock cases | Both audit test modules passed, including transfer fault/CAS matrices, degraded recovery/order/sensitivity, graph budgets and delivery counting/resume |
| Current kit integrity | Archive SHA-256 and all 31 release file hashes verified; extracted and installed outside checkout |
| Retained CI evidence | Recomputed all **47** retained command-log hashes across Linux/Windows; source identity matches current product code |
| GitHub CI | Independently fetched run/job statuses for [44984028401](https://github.com/Ermak-P/Knowledge-/actions/runs/44984028401): Linux and Windows verification both successful |
| Fresh-process installed delivery trial | Repeated with both the newly installed source package and the external kit runtime; enabled case PASS, disabled-delivery negative control behaves as expected |
| Adversarial authorization | All seven unsafe outcomes reproduced with the external kit runtime: six grant cases and one conditional clear |
| P4 legacy optional-tool path | Unverified text reaches the next actual provider request despite initial withholding; reproduced with external kit runtime |

Kit SHA-256: `80ad248a15c8850616deca4b562b0ff08cf6fae22251c021b27ffba1c47f4cb5`.

The installed delivery trial obtained the necessary threshold **37** from an approved claim automatically, made the real source change, ran real checking subprocesses, and passed an independent oracle. It did not call the Knowledge tool. The disabled control retained 0 and failed its oracle as expected. Final Reviewing used an independent canonical slice rather than accepting Coding's deliberately false narrative. This validates mechanical delivery, not live-model reasoning quality.

The full 23/24-command `verify_p4` route was **not independently rerun in this review**. Its successful Linux/Windows results are CI evidence whose statuses and retained hashes were checked. Native Windows execution and a real OpenCode/local-model trial were not performed by this reviewer. The submitted report correctly leaves real-host qualification blocked/separate.

The independent adversarial regression driver intentionally fails on this branch: **3 test methods, 8 failed assertions/subtests**, 4.637 seconds, exit code 1. Its expected outcomes represent the requested safe behavior. These are additional review cases, not failures in the 333-test stock suite.

## Acceptance by assigned area

| Assignment item | Review result |
|---|---|
| AUD-01: coverage/snapshots/negative proof | Supported by code inspection and passing real-refusal/fault/recovery tests; no additional blocker found |
| AUD-02: unified grants and restrictions | **Not accepted: R1 and R2** |
| AUD-03: project/shared transfer | Durable phases, CAS, lineage and replay present; relevant stock fault matrix passed; no additional blocker found |
| AUD-04: normalizer outage | Degraded envelopes, effect fence and ordered recovery present; relevant stock tests passed; retain separate real-host qualification |
| AUD-05: P4 delivery | Automatic delivery behavior verified, but **not accepted as a consistent current-knowledge boundary: R3** |
| AUD-07: dependency closure | IDs, bounded closure and incomplete reasons present; graph/item/depth/byte tests passed |
| AUD-09: missing/stale/truncated | New P1 diagnostics and byte-cap tests pass; **R3 leaves one P4 path falsely reporting complete/current availability** |

## Reproduction package and next review

The accompanying `Knowledge-Audit-Stages-1-2-Review-R1-Evidence.zip` contains the two diagnostic probes, an executable three-test regression driver, their observed outputs, stock suite log, installed-trial result, install log and a SHA-256 manifest. It contains no product installation, database or external dependency bundle.

From the reviewed repository root, after installing the current packages, run:

```text
<installed-python> -I -B <evidence-directory>/review_regressions.py
```

The probes load existing repository test fixtures from `cwd/tests` and import the product from the selected installed Python. Docker and local HTTP normalizer/provider responses are explicit doubles. Real SQLite, host CLI/session state, P4 HTTP requests and subprocess checks are used.

For the next round, fix R1–R3 in this branch, retain these reproductions as behavior regressions, repeat the stock suite and relevant installed qualification, and update the acceptance matrix/kit hashes to the corrected source. Keep existing failed/interim evidence as historical results. No merge, deployment, new database, permission expansion or real-user IPM trial is necessary for this correction.
