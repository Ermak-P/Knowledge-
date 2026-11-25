# Persistence identity and completed scan recovery

The v3 persistence extractor previously hashed the source file stem while its
statement described project presence. Two files could therefore produce two IDs
for the same statement. New scans use `project-presence-v1`: relative project
path + persistence method + literal generic argument. Display names alone are
never project identity. Individual source locations remain separate evidence.

## Compatibility and approval

The database schema, extractor snapshot version and source-reader policy remain
compatible. Resuming an older scan retains its original extraction identity
policy. Recovery projects its persisted observations into a new derived plan;
original scan rows, candidate IDs, payloads, decisions, gaps and ambiguity records
remain audit data. Existing canonical IDs win over generated replacements.
Verified legacy file IDs are related to the new project ID using the recorded
project, method, generic argument and source path, rather than choosing a sorted
claim ID. Future incremental observations use the same compatibility rule.

Only exact statement matches with compatible metadata, source/provider scope and
lifecycle are reconciled. Case, whitespace, quoted values and Unicode spelling
are significant. Operational-memory normalization is unchanged. Unresolved
ownership, metadata, lifecycle or identity conflicts remain blockers.

Plan format 2 retains original candidates and separately records effective
operations and typed reference aliases. Supporting evidence is unioned, including
occurrences omitted by an older candidate generator when persisted observations
still contain them. Historical evidence remains stored. Confidence and canonical
verification dates are not promoted. Prepare/rebuild never changes canonical
records; apply revalidates original source/provider bindings and the exact plan.

When scan observations are unavailable, queue-only recovery requires the exact
scoped persistence statement, producer provenance, a source binding, typed
evidence locations/raw hashes and a matching old/new producer ID formula. It
keeps every available proof but cannot recreate occurrences absent from both the
queue and persisted observations. Missing/incompatible identity proof remains a
blocker. It does not fabricate completed-scan ownership or negative coverage.

## Extractor identity review

| Category | Identity and statement scope | Collision policy / compatibility |
|---|---|---|
| project | Relative csproj path; statement includes SDK | SDK changes are explicit updates at the same project ID. |
| declaration | Project + namespace/nested qualified name; statement includes kind/bases | Duplicate declarations, partial/unsupported syntax and kind/base collisions are withheld as ambiguous. No new declaration IDs. |
| dependency | Project + reference tag + literal include | Equal literals have equal statements. Repeated occurrences preserve separate locations. No new IDs. |
| wiring | Project + first service generic argument; statement also includes lifetime/implementation | Distinct registrations can share an ID. Existing fail-closed ambiguity is retained, rather than guessing semantics or migrating unrelated IDs. |
| routing | Project + source stem + method + literal; statement contains all three | Same stems in different directories can collide. Existing cross-file ambiguity stays explicit; this fix does not assert controller equivalence. |
| persistence | Project + method + generic argument; statement asserts project presence | File stems removed from new IDs; equivalent files aggregate, with legacy compatibility as above. |

These are lexical syntax facts: generic/literal spelling is intentionally exact.
The extractor does not resolve aliases, expressions, generic type symbols or
runtime equivalence. Regression cases retain fail-closed wiring/declaration
collisions and distinguish equal display names in separate project directories.

## Windows upgrade

Use the kit built from this branch, not an earlier installed wheel. From its
extracted directory, with OpenCode stopped:

```powershell
.\install.ps1 -McpDir 'C:\LLM\mcp\knowledge'
```

The existing machine installer performs an upgrade and preserves project stores
and machine configuration. Do not delete `.knowledge`, queue data, or `McpDir`.
Restart OpenCode 2.4.0 and rediscover MCP tools. `knowledge_capabilities` must
advertise plan formats `[1,2]`, `rebuild`, and diagnostics `duplicates`/`candidate`.
An old MCP runtime must be upgraded before interpreting format 2 plans.

## Recover the existing IPM scan

Use the actual scan ID observed from the existing machine scan job. No private
IPM scan ID or database is included in this repository. These are MCP calls:

```javascript
knowledge_capabilities({})
knowledge_scan({action:"status"})
knowledge_scan_diagnostics({section:"scans", limit:20})
knowledge_scan_diagnostics({section:"duplicates", limit:2, max_bytes:16000})
knowledge_plan({action:"rebuild", scan_id:"<observed completed scan ID>"})
```

Rebuild is a preview: it validates completed artifacts and unchanged source/policy
bindings, reuses saved extraction, and returns counts, blockers and a new approval
fingerprint. It does not start a worker or a fresh scan. Full current source hashes
are still checked before and after prepare to detect concurrent edits; this is
inventory verification, not lexical re-extraction. Source/policy drift produces
an explicit blocker instead of silently starting again.

Inspect an affected group or complete candidate text in bounded pages:

```javascript
knowledge_scan_diagnostics({section:"duplicates", group:"<group>", limit:20})
knowledge_scan_diagnostics({section:"candidate", candidate:"<candidate ID>", cursor:0, max_bytes:16000})
```

Follow `next_cursor`; candidate text chunks carry a full record hash. Optional
`operation` selects one original typed operation; optional `plan` selects the
effective operation in a prepared canonical plan (its canonical plan ID, not the
machine approval seal). Review all blockers and coverage gaps. Only after explicit
approval of the newly returned **machine fingerprint**, call:

```javascript
knowledge_plan({action:"apply", approve:"<exact new machine fingerprint>"})
```

If apply was interrupted after durable intent, observe state and use the existing
`knowledge_plan({action:"recover", approve:"<same fingerprint>"})` protocol.
Do not reuse the old blocked-plan approval. Repeated rebuild is idempotent while
source, queue, provider and canonical state remain unchanged. Rebuild interruption
rolls back its plan write; repeat the preview. Failed files, ambiguity and partial
coverage remain gaps; successful reconciliation does not certify business meaning
or complete semantic coverage.

## Bounded diagnostics and progress

`impact` is returned as individual collection members, with compact counts in
`impact_summary`. Filter and paginate collections independently:

```javascript
knowledge_scan_diagnostics({section:"impact", collection:"direct_claims", limit:2})
knowledge_scan_diagnostics({section:"impact", collection:"changed_or_unverifiable_evidence", cursor:0, limit:20})
knowledge_scan_diagnostics({section:"plan-progress"})
```

Follow `next_cursor`. Response projections explicitly report truncation; full
claim/evidence records remain available through their registered lookup tools.
The default 16 KB response budget is unchanged. Plan preparation reports real
stages, available operation/group counts and elapsed time in machine state outside
the project. Progress is excluded from approval fingerprints. The MCP event loop
can serve progress reads while prepare executes in its worker thread.

A global `scope.complete == false` used to mark every deterministic proof
unverified, including healthy code when only an unrelated JSON file failed.
Positive proof now requires complete physical code analysis in its project,
nonambiguous identity and exact source/anchor verification. Unexamined or failed
code, partial source reads and enumeration errors still fail closed. Negative
coverage and retirement continue to require the existing complete-scope proof.

## Structured input failures

`.json` is strict JSON: comments and trailing commas are rejected with a dialect
hint and line/column, without dumping content. UTF-8 BOM and supported BOM-marked
UTF-16 inputs are decoded strictly, with hashes of original bytes. Invalid JSON,
duplicate keys, nonfinite values, unsupported encodings and truncated physical
reads remain distinct coverage failures/gaps. `.jsonc` is not silently treated as
JSON or enabled as a new semantic format. This patch changes diagnostics, not the
persisted source-policy version.

Unchanged deterministic syntax failures have `retry_eligible:false`. Transient
eligible access/read failures can use the existing explicit observed-scan resume
and retry protocol, which reprocesses only eligible failed files and verifies the
unchanged snapshot. Correcting syntax or changing an encoding/dialect policy
changes source identity: preserve the old scan and use an explicit source-bound
update/review. Do not remove pending candidates to hide a stale-source blocker.
There is no automatic retry loop or automatic full scan.
