# Knowledge + Harness — P1 independent review, correction round 1

Review date: 2026-11-15.

Repository: https://github.com/Ermak-P/Knowledge-

Reviewed commit: `2a8664821d0f6512ecbce92280e25d6f19b3f32c` on `main`.

Accepted P0 baseline: `a3c7ac7afd7cff6137b916832cf40019ca8b8c87`.

## Decision and assignment

**P1 is not accepted yet. Complete one consolidated correction round for R1–R5 below, then return a fresh review packet. Do not start P2.**

Continue from the reviewed implementation and preserve legitimate later work. Implement the repairs autonomously, including regression tests, compatibility handling, documentation and fresh evidence. Choose the implementation details yourself. Ask only if an essential ambiguity changes the required outcome. These are corrections to P1 correctness and its agreed acceptance conditions, not a request to add a compiler, a live model or a new runner.

Keep Knowledge independent from Harness, the shared coordinated writer, exact approval, immutable history, supported P0 behavior, root isolation and actual UTF-8 response budgets. Scanning may propose changes; it must not apply canonical changes silently. No deletion/reset of existing stores, history or queues as a repair. Do not merge or deploy. Commit the finished corrections to the working branch and report its exact commit so the result can be reviewed again.

## Independently verified strengths and limits

- All **75 product tests passed independently**, including the accepted P0 regressions, real stdio and process interruption tests.
- Both wheels built; standalone Knowledge passed the dependency-free packaging check.
- The current P1 run/source/artifact gate validated. All **80 ZIP members**, member hashes, current checkout bytes and external archive checksum matched.
- Fresh discovery on a separate copy of pinned eShopOnWeb produced **536 observations**. All five submitted natural-language questions found their expected answer using the **ordinary defaults: 10 claims, 16,000 bytes**. This independently confirms usefulness beyond the submitted evaluation's larger retrieval allowance.
- Submitted TRX files contain 49/49 passed before and 49/49 after, with zero failed or unexecuted tests. These are verified submitted artifacts. An independent application build in the review environment still failed at the WebAssembly `ComputeWasmBuildAssets` task-host boundary, MSB4216/MSB4027; therefore the reviewer does **not** claim an independent .NET test pass. This environment limitation is not one of R1–R5.
- The submitted eShop scan reports 11 duplicate-identity gaps. Reporting them is useful, but it does not resolve R3: the first matching identity still becomes trusted canonical knowledge.

The existing passing suite does not cover the five reproduced cases below. Do not treat its PASS or the generated 20-row acceptance ledger as external acceptance.

## R1 — High: excluded live source can produce a false retirement

Relevant implementation: `packages/knowledge/src/knowledge/discovery.py`, `inventory()` lines 25–37 and `reconcile()` lines 258–276 at the reviewed commit.

### Reproduced behavior

1. Use the synthetic `test_p1.fixture`, but set `Tests/Independent.cs` to `public class UniqueDeclared {}`. Commit this before taking the initial scan, so the base source/hash proof is genuinely committed. The unique name avoids the fixture's unrelated `Independent` configuration key.
2. Scan completely, approve/apply/acknowledge the generated knowledge, and record the Git base.
3. Move that file to `Tests/build/Independent.cs`, retaining its exact contents. Commit the move. Do not modify `Tests.csproj`, which uses the ordinary `Microsoft.NET.Sdk` defaults.
4. Scan the base/head range completely and call reconciliation.

Actual result: `complete=true`; `Tests/build` is excluded; reconciliation proposes `retire` for `UniqueDeclared`, explaining that the current inventory/consumers no longer contain its subject.

Independent MSBuild evaluation, `dotnet msbuild Tests/Tests.csproj -getItem:Compile`, exited 0 and **included `build/Independent.cs`**. The type remains a real compile item. Exclusion from the reader's inventory is not proof of removal from the project.

### Required outcome

Retirement must require adequate coverage for that specific assertion and its relevant source/consumers. Distinguish successful processing of the chosen inventory from sufficient negative-evidence coverage. A source relocation into an excluded or unsupported scope must produce an explicit gap/not-verifiable/manual-review result, or be inspected safely by a supported method; it must not be described as proven removal.

Do not solve this by loading credentials, following arbitrary links or pretending all excluded directories are analyzed. Genuine generated/dependency exclusions remain useful. Define a conservative, explainable policy for relevant excluded source and use it consistently in the retirement decision and reports.

Regression acceptance: the move above must not produce a retirement proposal; an actually removed, adequately covered component must still pass the existing EM removal pipeline. Cover at least one unsupported/excluded-source boundary in addition to the ordinary missing-file case.

Original acceptance affected: P1-A03, A10, A11.

## R2 — High: source reconciliation retires a reviewed historical fact

Relevant implementation: `discovery.py`, `reconcile()` lines 247–276. The retirement loop uses the earlier observation's ID and subject without establishing that the **current revision** is still the source-existence assertion owned by that observation.

### Reproduced behavior

1. Start with the committed `UniqueDeclared` fixture above; scan and import it.
2. Through the supported version-2 update/approval path, update that same logical claim to:

   `UniqueDeclared was declared in Tests in the recorded earlier source snapshot.`

   Set its reviewed provenance to actor `human-reviewer`, method `reviewed-historical-statement`. Preserve the retained source evidence/history. Apply and acknowledge this exact approved revision.
3. Remove the declaration, commit the removal and reconcile a full base/head scan.

Actual result: reconciliation proposes retirement of this reviewed historical statement. The statement remains true about the recorded past; it is no longer an assertion that the component currently exists.

### Required outcome

Automatically generated retirement proposals must be bound to the currently applicable assertion/revision and its semantics/ownership. A former discovery ID is not permanent permission to retire every future reviewed meaning of that record. Use an explicit supported policy to preserve or abstain on changed/manual/historical assertions. It is acceptable to mark their current-checkout evidence not verifiable according to the documented retrieval policy. It is not acceptable to assert their obsolescence solely because the earlier component disappeared.

Do not solve this with an English/Russian keyword list for “historical”. Preserve the distinction structurally or conservatively validate that the latest record still matches the assertion the deterministic removal proof establishes.

Regression acceptance: the exact same-ID historical revision above is not proposed for retirement. Original source-existence assertions and reviewed dependency closure still retire correctly when removal is actually proved. The prior revision and the human-reviewed historical payload remain retrievable.

Original acceptance affected: P1-A06, A09, A11, A13.

## R3 — High: ambiguous identities are reported, then imported and reassigned

Relevant implementation: `discovery.py`, `extract()` lines 84–92, duplicate handling lines 195–203 and enqueueing lines 220–232.

### Reproduced behavior

Create two legitimate distinct namespace types in the same project, for example:

```csharp
// Tests/Independent.cs
namespace A { public class Independent : System.Exception {} }
// Tests/Other.cs
namespace B { public class Independent : System.Object {} }
```

The current identity uses only `[project_name, category, key]`, where the declaration key is the short type name. Both types receive one `scan.*` ID. A gap is recorded for the second observation, but the first observation is still proposed, imported and reported as trusted.

In the executed probe, the bases were named `ABase` and `BBase`; the observed behavior was:

```text
gap: duplicate lexical identity
canonical statement: Tests declares class Independent with declared bases ABase.
freshness.trusted: true
```

After deleting the first source and scanning/importing again, the **same logical ID** acquired a new revision saying it has base `BBase`. This represents a different namespace type, not an update to the original entity. Filename/traversal order selected the identity.

### Required outcome

Either distinguish entities with sufficiently stable project/type identity or abstain on the ambiguous group until it can be resolved. Merely logging a gap while retaining an arbitrary first candidate is insufficient. Account for different project paths sharing a project filename, namespaces, nested/partial declarations and other collisions within the advertised capability. A lexical implementation may explicitly decline unsupported cases.

Revalidation must not continue trusting a formerly unambiguous identity when the current scope makes its ownership ambiguous. Removing one colliding entity must not silently transfer the other entity's history, reviewed edges, confidence or identity to it. Preserve rename stability where identity is actually established.

If the identity/extractor format changes, provide an explicit compatibility strategy for already generated P1 data/checkpoints; never silently rewrite IDs or discard old knowledge. Preserve P0 payload schemas and legitimate manually reviewed state.

Regression acceptance: two distinct namespace types and two same-named projects cannot collapse into one arbitrary trusted entity; a collision introduced after an initial import is handled honestly; deletion of one collision cannot reassign the other's history. Run these through scan → proposal/abstention → exact approved apply where applicable → current/history reads, including resumed scans.

Original acceptance affected: P1-A02, A04, A06, A12, A13.

## R4 — Medium: reintroduced retired knowledge is permanently suppressed

Relevant implementation: `discovery.py`, `proposal()` lines 159–164, and `lifecycle.py`, `simulate()` lines 91–96.

### Reproduced behavior

1. Import the committed `UniqueDeclared` declaration.
2. Delete it, perform a corroborated base/head reconciliation and explicitly approve/apply/acknowledge its retirement.
3. Restore the same source declaration and scan again.

Actual result: the declaration is present in new observations, **zero candidates are added**, and the existing record remains `retired`. A normal supported update cannot reactivate it either, because `simulate()` rejects non-active targets. The source exists again, but repeated initialization/update scans never offer a supported way to make that fact current.

### Required outcome

Define and implement an explicit reviewed reintroduction/reversal path. Fresh discovery must expose the returned entity as actionable review work rather than silently ignoring it forever. The resulting operation must create new audited lifecycle/evidence history with expected-version checks and exact approval, or use another documented identity model that preserves the old entity and clearly links the new one. Do not reset/delete history, silently reactivate on scan, or reinterpret old approval as permission to reactivate.

Handle or explicitly flag dependent relationships and supersession conflicts. Do not blindly reactivate every retired/superseded record simply because one source anchor reappears.

Regression acceptance: present → approved retirement → source reintroduction → actionable proposal → new explicit approval → correct current/history views. Include safe retry and stale-approval behavior and unchanged rejected/deferred reintroduction deduplication.

Original acceptance affected: P1-A05, A06, A09, A12; this also closes the agreed audited-reversal requirement in section 7 of the task.

## R5 — Medium: ignored uncommitted source is labeled committed

Relevant implementation: `discovery.py`, `inventory()` lines 49–81.

### Reproduced behavior

1. In the synthetic Git repository, commit `.gitignore` containing `Tests/Ignored.cs`.
2. Create that file with `public class IgnoredYetCompiled {}` without tracking it.
3. Run discovery.

Actual result:

```json
{"snapshot_kind":"committed","dirty":[],"observation":"Tests/Ignored.cs","head_has_file":false}
```

Inventory reads the ignored file and creates an observation from it. `git status --porcelain --untracked-files=all` omits ignored files, so the snapshot and generated proposal incorrectly call its source committed. Hash binding exists, but it does not make these bytes part of HEAD.

### Required outcome

Classify every included source against the actual Git HEAD/index/working tree state. Either explicitly include permitted ignored source with honest working-tree/ignored provenance and hashes, or exclude it with a documented reason. Never label a snapshot/proposal committed while it contains evidence absent from or different from the named commit. Keep staged, unstaged, untracked and ignored-source states distinct where relevant; do not weaken source fingerprints or resume/apply drift checks.

Regression acceptance: the ignored-file example is honestly excluded or labeled uncommitted, including when other tracked files are clean. Continue passing existing staged/unstaged/untracked, rename, source-drift and project-isolation cases.

Original acceptance affected: P1-A05, A07, A17.

## Definition of done for this correction round

1. All R1–R5 are fixed as product behavior, with meaningful reproducing regressions and the compatibility policies above. Do not change the expected results to bless the reproduced failures.
2. All 75 existing product tests remain passing, plus the new regressions. Keep fresh packaging, stdio/budget/isolation, crash/race, P0 upgrade, immutable-history and genuine EM-removal checks.
3. Run fresh real-source discovery and question evaluation on the pinned eShop checkout. Inspect ambiguous groups/current records under the corrected policy; explain count changes. Retain the five independent source expectations and report retrieval at ordinary defaults as well as any larger diagnostic budget.
4. Run the supported fresh verification pipeline and application before/after checks in a capable environment. Preserve the run/source/artifact gate and honest failure/NOT_RUN distinctions. Do not substitute the reviewer's task-host limitation for fresh evidence in the implementation environment.
5. Regenerate the P1 reports, acceptance mapping, source identity, review ZIP, inventory and SHA-256 from the final corrected source. Previous PASS artifacts are historical only. Include a concise `R1–R5 → implementation → regression → result` table and any remaining limits.
6. Report the exact committed revision and review packet location. Keep P1 labeled submitted for review until external acceptance. Leave P2 untouched.

The expected finish is a coherent corrected P1 that can safely maintain knowledge as a project changes, with one reviewable commit state and fresh evidence. Return the completed result without requesting approval for each routine implementation step.
