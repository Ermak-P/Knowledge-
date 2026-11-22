# /update-by-CR review

The installed native `/update-by-CR` command now runs a durable foreground
interview and prepares ordinary Knowledge changes. Its backend inspects pinned
Git code and existing Knowledge, validates a sourced decision map, asks anchored
questions about missing reasons and intentional nonchanges, and uses the existing
candidate → exact plan → apply → acknowledge lifecycle. The receipt includes
normal retrieval, canonical IDs/revisions, source revisions and unresolved limits.

Code/qualification revision: `1a4999fa62a0d78a9d331d4f6f9396a0bef73995`.
Qualification source identity:
`a09c9364beaa434d5ab35e3af97f396ad8b7fdfd9ba5c2c5167aff7747b0e0ab`.
Started clean at `90cf0623e`; fetched current main `b1e88a848` had the same tree
and includes the separately reviewed SQLite optimization. The feature branch is
`codex/update-by-cr`, based on that main. No worktree, application PR merge,
deployment, user IPM write, or global model/configuration change was performed.

## Architecture and compatibility

* `knowledge.cr_sources` owns the bounded normalized source contract, optional
  existing-authentication `gh` adapter, repository/revision checks and actual Git
  blob inspection. GitHub pagination includes issue comments, PR comments,
  inline comments, formal reviews and files. Attachments/check-runs are explicitly
  incomplete. Azure DevOps/TFS uses available connectors or labelled user exports;
  there is no mandatory tracker SDK or built-in authenticated Azure client.
* `knowledge.cr_workflow` owns versioned sealed progress in existing SQLite
  metadata and immutable supporting artifacts under `.knowledge/update-cr`.
  Claims/evidence retain the existing strict schemas, confidence enums and
  `{actor,method}` provenance. Focused claims contain the reason, condition,
  preserved boundary and reassessment condition; evidence contains exact source
  references, pinned anchors and actual user quotes. This is retrievable Knowledge,
  not a separate interview database or operational-memory permission.
* `knowledge.cr_cli` is a JSON/stdin local operator interface. The project-owned
  native command/plugin supplies actual user-message binding, missing-link
  handling and resume while retaining the configured agent/model. Untrusted
  arguments never enter a command-template shell block or interpolated argv.
  Installation/removal verifies ownership and preserves unrelated/user-edited
  command definitions. The Knowledge wheel works independently of Harness/MCP.

The only Store integration validates optional workflow metadata on existing
connections and includes workflow/artifacts in export. There is no table/schema
migration or migration on read. New stores use the existing P1 initialization;
an existing P0 store requires the normal explicit upgrade preview/apply. Supporting
artifacts participate in existing backup/restore. Corruption refuses explicitly.
See the packaged [protocol and source contract](../../docs/P4/UPDATE-BY-CR.md).

Preparation records its intent before submitting the candidate, so a restart can
recover that candidate/plan. Approval records the exact plan before normal apply;
commit/acknowledgment recovery is idempotent. Source/Knowledge CAS rejects stale
analysis; earlier answers retain their original source binding. Unrelated pending
candidates are refused with the supported independent review/disposition route.
Closed/unmerged PR material remains visibly branch-scoped and unconfirmed.
Committed code that becomes stale during receipt recovery yields a partial result
with withheld IDs, rather than a false fully usable saved result.

## Executed evidence

* [Focused tests](local/focused.log): **27 PASS**, including hard process exits,
  actual candidate/apply/ack, answer corrections, new-chat rebinding, source drift,
  Unicode, installation preservation and strict evidence freshness.
* [Installed byte chain](installed-bytes.json): all **61** packaged Python/schema/
  host assets equal the specified Git tree and the installed files outside the
  checkout. The Knowledge-only environment has neither Harness nor MCP.
* [Worked dialogues and .NET replay](trial/result.json): retry and Russian cache
  scenarios both save canonical claims, retrieve through a fresh isolated process,
  satisfy the separate decision/nonchange oracle, and build/run .NET 10 behavior
  checks. Raw questions, exact answers, plans, IDs and exports are retained.
* [Native OpenCode](native/result.json): actual **1.19.6 Linux x64** registration,
  no/one/two-link command API calls, later foreground link messages and new-chat
  `--resume` all PASS. The expanded real-host interview also verifies actual
  foreground user-message IDs, Russian answers, exact-plan fixture approval and
  normal apply/acknowledgment/retrieval (`native/interview-messages.json`).
  This is the real host with an isolated controlled SSE
  responder; the transcript/logs and published plugin types are retained.
* [Independent profile](independent/result.json): real persistence and normal
  retrieval with **Knowledge only**, no Harness/MCP imports or dependencies.
* [Provider process boundaries](provider/result.json): real subprocess pagination
  output, oversized response and a killed 25-second provider timeout. The executable
  is controlled; this does not claim live tracker access.
* [Existing Knowledge reuse](existing/result.json): explanations cited from
  actual saved IDs/revisions produce no redundant questions. An independently
  applied canonical correction makes the previous analysis stale.

The earlier full installed Linux route is **PASS_PORTABLE**, all **25 commands PASS**,
with **389 tests: 378 PASS, 11 native-Windows-only SKIP**. All inputs remained
unchanged. The entire raw run is retained in [qualification/](qualification/run.json),
including logs, comparison results, application outputs and installed replay.
The separate local full regression also passes (`local/full-result.json`).
That local route ran at `cb8b3d725`, before the replay-pipe encoding correction;
its source descriptor is retained alongside it. All product wheel bytes are
identical to the final delivery. Final-source CI Linux/native Windows results
are recorded in `ci/validation.json` when their receipts become available.
The expanded native OpenCode profile uses the final installed wheel.

## Worked outcome

The retry dialogue explains why four total operation attempts fit the bounded
budget, why the independent packet retry owner stays at two, and why the public
caller deadline remains 120ms. Its three revision-1 records are
`ucr.5917a2eacdf368ff.retry-limit`, `.transport-owner`, and `.deadline`.
The Russian cache dialogue captures capacity 32, bounded memory/miss behavior and
compatibility of `ILookup.Find`; its revision-1 records are
`ucr.7ba1e88c78b8d81b.capacity` and `.contract`. These fixture-specific IDs derive
from the project identity; reruns in other temporary roots have different prefixes.
Both worked results are actually `saved`, not just queued or awaiting approval.

The fresh controlled planner receives only the paraphrased task and normal
Knowledge context, with the expected choices kept in a separate oracle. Removing
the critical nonchange from its context fails the regression. The resulting
fresh .NET files exercise retry/deadline/owner and cache/interface boundaries.
This establishes the executed controlled persistence/retrieval/behavior profile.

## Limits and retained failures

**Live model semantic replay: NOT_RUN.** No approved live model was configured for
this task. The command itself does not introduce a model or inference service.
Neither scripted planning nor the controlled native responder establishes how an
arbitrary model will choose or implement a solution.

**Live provider acquisition: BLOCKED/NOT_RUN.** Git transport works, but this
environment's GitHub REST access returns Forbidden. No live Azure/TFS connector
access was available. Provider exports/controlled responses are labelled honestly.
Remote changes require a new source observation through the host/provider tools;
the backend checks local/Knowledge freshness on each continuation but does not
pretend that an offline export proves current remote state.

The first source-bound Windows attempt (`failures/ci-cb8b3d725/`) passed
388 tests and failed one replay test method in two subcases. Its fresh worker
printed Unicode JSON through cp1252. The fix uses ASCII JSON transport, which
restores the exact original Unicode through json.loads. The regression now forces
cp1252 on every OS and compares the complete decoded task/context/plan. The fix
and guard are in the final qualification revision; the failed receipt is retained.

The initial full regression attempt is retained in
`failures/pre-freeze-full-regressions.log`: one FileNotFoundError occurred while
the agent incorrectly reinstalled the same environment during the run, briefly
removing an installed schema. It is a failed attempt, not qualification evidence.
Subsequent final runs use stable installations. Native attempts 1–4 are also
retained: task-local npm cache was required, a missing synthetic-part messageID
was fixed, and the report's controlled provider needed to decode content parts.
Final native execution uses the actual installed final wheel.

No unrelated SQLite reporting P2 fixes are included. The product keeps the
existing `0.5.0rc1` candidate version; source, wheel and ZIP hashes identify these
specific bytes. [Reproduction commands](REPRODUCE.md) and
[UCR-01–20 acceptance map](ACCEPTANCE.md) distinguish the executed profiles.
