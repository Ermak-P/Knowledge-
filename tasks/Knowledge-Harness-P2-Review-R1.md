# Knowledge + Harness — P2 independent review, correction round 1

Date: 2026-11-15.

Repository: https://github.com/Ermak-P/Knowledge-

Reviewed branch/revision: `p2` / `413bb196d58ca050e9be0bd05bd92cda129da70b`.

Accepted P1 baseline: `c62cad5aabbc47b43ef59fcf3ff975dd405eb42d`; merged `main` base: `5e6f33da5758c30418df490840c76c1946c84545`.

## Decision and assignment

**P2 is not accepted yet. Complete one consolidated correction round for P2-R1–R3 below, then submit a fresh review packet. Do not start P3.**

The delivered runner, role dispatch, HTTP transport, process execution, capture outbox and tests are substantive. Preserve them and the accepted P0/P1 behavior. Repair these product defects autonomously, including meaningful reproducing regressions, relevant compatibility/recovery behavior and fresh evidence. Choose the implementation details; do not stop for approval at each routine step.

Work from the reviewed branch, preserve legitimate later changes and keep the user in control of merge/deployment. Commit the completed correction and report the exact revision. No destructive reset/clean, worktrees, deletion of historical receipts, direct Harness writes to Knowledge SQL or automatic canonical approval.

## Independent verification already completed

- Installed the submitted packages and ran **129 product tests: PASS, no skips**, including all 104 accepted regressions. Accepted test bodies were unchanged.
- Fresh packaging passed: both wheels and installed execution CLI/legacy read facade; standalone Knowledge remained usable without Harness/provider services.
- Independently reran the five eligible automatic capture sessions: each completed and submitted one candidate, with no canonical auto-apply. The absence/no-change case also passed. These tests cover first capture, not the subsequent approved-record update in P2-R1.
- The current source/run/artifact gate passed. All **133 review ZIP members**, member hashes, corresponding checkout bytes and external SHA-256 matched.
- Submitted actual application artifacts show baseline 49/49, the newly added regression failing 1 of 50 before repair, and final 50/50 after repair. Source/fixture code implements the expected checked-overflow behavior and a new xUnit assertion; the existing tests are retained. These are verified submitted artifacts, not a claimed independent successful .NET application run in the review environment.
- Live model/llama-server/OpenCode/Windows/private MCP remain explicitly unexecuted. The review does not convert synthetic HTTP provider decisions into live quality/performance evidence.

The passing suite and generated acceptance mapping do not cover the three failures below. All three were reproduced through production code, with real local HTTP provider requests, runner state and actual tool/store/process behavior. Deterministic provider decisions only make the scenarios repeatable.

## P2-R1 — High: automatically captured knowledge cannot subsequently update

Relevant source at this revision:

- `packages/knowledge/src/knowledge/discovery.py`: `proposal()` lines 197–204, `discovery_owned()` lines 493–503, `candidate_preview()` lines 516–540.
- `packages/harness/src/harness/capture.py`: preview/outbox/submission flow.

### Reproduction

Use the delivered `p2_fixtures` project/configuration/task/HTTP provider helpers and the normal Harness API:

1. On a new initialized Knowledge store, run the normal coding session that changes `Feature.cs` to `public class ImprovedFeature {}`. Actual build/test/review pass and automatic capture queues its source declaration.
2. Explicitly prepare, approve, apply and acknowledge that candidate through the supported Knowledge API. This approval is deliberate test setup; Harness must not begin doing it automatically.
3. Set the next independent fixture expectation to `public class ImprovedFeature : System.Object {}`. Update the fixture's test expectation as user-owned setup **before** starting the next run.
4. Run a second normal coding session against the same project/Knowledge store. The source change and all gates pass.

Observed result:

```text
first run: completed
Knowledge scans: 0
second run: completed / execution=passed / capture=no-candidate
queue statuses: [imported]
pending update operations: []
canonical: Project [Project.csproj] declares class ImprovedFeature.
actual: public class ImprovedFeature : System.Object {}
```

The new observation has the same logical identity and a changed, supported statement. It should be actionable update work, not silently discarded.

### Cause and required result

`candidate_preview` creates valid source-backed proposals without persisting a scan. After their approval, `discovery_owned` recognizes an existing generated assertion only if a matching completed scan exists. Therefore a record created through automatic capture lacks the ownership proof required for its own future update, and `proposal` returns `None`. `candidate_preview` then reports no eligible new fact rather than exposing the unsupported ownership state.

Make the supported capture/proposal/import ownership model coherent. Preserve enough verifiable provenance/observation ownership through a supported Knowledge path that future changes to that same generated assertion can produce reviewed updates. Do not require the user to run a separate full scan after every accepted automatic capture. Do not fake full-scope coverage to create a scan receipt or let Harness insert internal Knowledge state directly.

Keep P1's protection of manually reviewed/historical meanings: matching an old generated ID or provenance label alone must not authorize automatic overwrite or retirement. Where ownership really cannot be established, return explicit actionable manual review instead of a misleading no-candidate success.

### Closure criteria

- Run the full automatic add → explicit canonical approval → same-entity source change → automatic update candidate flow. The update keeps the logical ID, current expected revision and fresh source evidence; canonical history changes only after a new exact approval/apply/ack.
- Cover a second subsequent source revision and the supported retired-then-returned case for capture-origin records, or clearly expose a genuine conflict/manual-review requirement rather than silently ignoring it.
- Keep rejected/deferred deduplication, capture crash/retry ownership, all P1 reviewed-meaning/false-retirement regressions, confidence semantics and no-auto-apply behavior.

Affected requirements: P2-A11–A14 and compatibility with the accepted Knowledge lifecycle.

## P2-R2 — High: absolute recipe inputs bypass Coding's protection

Relevant source: `packages/harness/src/harness/engine.py`, `start()` lines 38–48; `tools.py`, recipe-input enforcement in `patch()`.

### Reproduction

1. In the synthetic project, create a trusted test recipe script named `verify.py` containing `raise RuntimeError("real verifier rejects this task")`. The neutral filename is intentional: trusted recipe protection must not depend on whether the name contains the word “test”.
2. Configure the test recipe as `[absolute_python, absolute_project_path/verify.py]`, result format `unittest`. This is accepted configuration. A relative path to the same script would currently be protected.
3. Declare a broad coding source scope, such as `writable=["*"]`, without any `existing_test_edits` exception. Directly configured verifier inputs must remain protected even inside that scope.
4. Through the real Coding read/patch tools, replace `verify.py` with:

```python
print("Ran 1 test in 0.001s\n\nOK")
```

5. Execute the configured recipes and separate Reviewing role through the normal runner.

Observed: `protected_paths` contains only `build.py`; the verifier patch is accepted. The replacement script executes and the test gate records `ok=true`, `executed=1`, `returncode=0`, output ending `OK`. The overall run reports `completed` despite the trusted check being replaced by a print statement. This is a concrete role/gate bypass, not a demand for an OS sandbox around hostile unrelated host processes.

### Cause and required result

`start()` adds argv file inputs to `protected_paths` only when `not Path(arg).is_absolute()`. The same project-owned trusted script loses protection solely because configuration names it absolutely.

Resolve configured recipe inputs canonically and protect project-owned inputs consistently regardless of absolute/relative spelling. Include relevant configured executable/script/module entry points; preserve resolver/link/hardlink/path protections. An ordinary coding scope must not authorize rewriting its own verifier or policy. Define any explicit user-approved test-edit exception narrowly and keep it observable. Do not solve this by changing the fixture script's filename or trusting the provider/reviewer to notice the replacement.

### Closure criteria

- Absolute and relative argv paths to the same verifier both deny the Coding patch before bytes change. Cover a neutral filename, broad task scope, spaces/non-ASCII paths and a configured project-owned entry point.
- The original failing verifier still fails; this scenario cannot obtain a successful gate/run by writing synthetic pass output.
- Preserve legitimate application source/test additions, explicit supported test-edit exceptions, configured recipe execution, process recovery and the real .NET fail → repair → pass flow.
- Extend the permission evidence to execute this attempted bypass; a static list or prompt-only assertion is insufficient.

Affected requirements: P2-A04, A05, A07 and A20.

## P2-R3 — High: a stale resume snapshot overwrites completed state and usage

Relevant source: `packages/harness/src/harness/engine.py`, `resume()` lines 77–101 and subsequent `Journal.save` calls. The ordinary acquisition path loads mutable run state before obtaining the project lease; only its contention retry path reloads under the lease.

### Reproduction

Use a read-only task so source changes do not obscure the state race:

1. Persist a newly started run before its first execution. The review fixture intercepted only `start`'s immediate call to `resume` to expose this normal durable starting state; actual subsequent resumes use production execution/transport.
2. Resume caller A loads that run, then is delayed **before acquiring the lease**.
3. Caller B resumes the same run and completes it normally, including Planning and Main requests and durable accounting.
4. Release A. It obtains the now-free lease but continues using its pre-B in-memory snapshot.

Observed:

```text
B outcome: completed
recorded requests after B: 3
A outcome: completed
actual provider HTTP calls overall: 4
recorded requests after A: 1
remaining recorded roles: Main only
```

Caller A makes an extra provider call and overwrites the completed run's role/request state. The provider observed four requests but final accounting retains one. The successful run's prior role history and usage are lost. This is not safe idempotent recovery or full Main/subagent accounting.

The scheduling delay in the reviewer probe wrapped `Journal.load` with events while delegating its actual read unchanged; it did not replace provider, execution, tool, database or accounting success behavior.

### Required result

Every mutable execution/recovery decision must use state/configuration reloaded or version-validated under the acquired ownership boundary. Recheck terminal/execution/capture state after acquiring that boundary. An older in-memory run must never overwrite newer frames, requests, attempts, gate/capture state or terminal results. Use under-lease reads, revision/CAS checks or an equivalent explicit consistency mechanism.

An already completed run must return its durable historical result without issuing another model request or dropping prior usage. Keep unknown-outcome attempts as unknown and retain charged usage; do not repair accounting by inventing totals after deleting attempts. Preserve the documented safe cleanup of actually owned recipe processes and project-level writer isolation.

### Closure criteria

- A deterministic overlapping-resume regression at the pre-lease scheduling boundary proves that completion/role/request history and aggregate usage never regress. Match retained request identities/counts to actual transport requests; no duplicate request occurs after terminal completion.
- Cover terminal/read-only completion and interrupted coding or capture delivery; retain all attempts, receipts and outbox events across contention and retries.
- Revalidate relevant configuration against the current persisted run after ownership acquisition; stale pre-lock configuration must not grant authority or bypass the existing configuration-change guard.
- Retain existing concurrent accepted-before-ack capture, killed-worker/lease cleanup, cancellation, uncertain provider outcome and no-double-edit regressions.

Affected requirements: P2-A05, A06, A09, A13, A15 and A20.

## Definition of done for this correction round

1. Fix P2-R1–R3 as production behavior, with named regressions covering the exact transitions and bypass/race above. Preserve all 129 existing tests and all accepted P0/P1 invariants.
2. Repeat first-capture and subsequent-update sessions through the actual HTTP/runner/tool/store paths. Verify queue IDs, review dispositions and canonical approval/history boundaries.
3. Repeat the permission bypass and overlapping-resume tests with real file/state/transport behavior. No fake success receipts or direct fixture writes during the tested Coding operation.
4. Run fresh packaging, the full suite, provider/permission/context/process/capture/recovery/accounting checks and the supported pinned .NET evaluation in the implementation environment. Preserve honest live/NOT_RUN distinctions. Do not reuse the submitted passing application artifacts as evidence for changed source.
5. Regenerate the coherent P2 run/source/artifact gate, acceptance mapping, reports, ZIP inventory and external SHA-256 after final fixes. Add a concise P2-R1–R3 → implementation → named test → executed result table.
6. Commit and report the exact corrected branch/revision and verification command/packet. Keep P2 marked submitted for external review; leave P3, merge and deployment untouched.

The finish line is the existing P2 runner with reliable repeated learning, enforced verifier ownership and monotonic recovery/accounting—not a storage rewrite or a new architecture milestone.
