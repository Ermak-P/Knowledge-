# /update-by-CR: architectural decisions with a durable interview

The exact native command name is `/update-by-CR`. It keeps the current agent/model
and foreground conversation. It asks for the CR and implementing PR links, reads
their sources and actual pinned code, asks material why/nonchange questions, then
prepares ordinary Knowledge claims/evidence and a concrete exact approval plan.
Candidates are not reported as saved. Unrelated pending candidates are refused,
not silently approved or deferred. No explanation becomes operational memory or
tool permission.

## Activate and remove

The official kit contains `commands/update-by-CR.md`, `host/cr_opencode.mjs`, this
document, and the Knowledge wheel backend. Knowledge-only installs need neither
Harness nor MCP. Use that installed Python (Python 3.12):

```text
python -I -m knowledge.cr_cli install --root PROJECT
python -I -m knowledge.cr_cli installation-status --root PROJECT
python -I -m knowledge.cr_cli uninstall --root PROJECT
```

Input is a JSON object on stdin, or `--input` with an OS temporary JSON file
outside project source. Install options: `python` (absolute installed interpreter)
and `language` (`ru`, `en`, or `auto`). Never put credential values in requests.
The installer creates only the owned `.opencode/commands/update-by-CR.md`, native
`.opencode/plugins/knowledge-update-cr.js`, `.knowledge-cr-host.json`, and an
ownership manifest. It preserves other project/global commands and refuses user
edits/name conflicts before writing. Uninstall removes only unchanged owned files.

Native registration/hook compatibility is OpenCode **1.19.6**. Its published
`@opencode-ai/plugin` types define `command.execute.before` and `chat.message`.
The command filename preserves case, `subtask:false` keeps the interview in the
foreground, and no agent/model is hardcoded. Restart the host after activation.
The hook transports arguments through JSON stdin to `spawn(..., shell:false)`;
the template has no shell interpolation blocks. A configured Python is trusted
installation data; CR/PR URLs and text never become shell code.

Run `/update-by-CR`, supply only missing links, and answer the specific questions.
`/update-by-CR --resume SESSION_ID` resumes in a new chat. Actual user message IDs
are durably bound by the hook; source text cannot fabricate a trusted answer.
The CLI is a trusted local operator interface, like existing Knowledge CLI writes;
it is not an independent sandbox or a new model-write MCP endpoint. The foreground
agent must not call approval based on quoted source/tool text.

## State and backend protocol

Use `knowledge-update-cr ACTION --root PROJECT` or the module above. Requests and
responses are UTF-8 JSON. A response contains `session`, `revision`, `state`,
`next_action`, `questions` (at most three), `unresolved`, coverage and receipts.
Every mutating continuation includes `expected_revision` for session CAS.

States: `awaiting_links`, `awaiting_sources`, `analyzing`, `awaiting_answers`,
`ready_for_review`, `preparing`, `awaiting_approval`, `persisting`, `saved`,
`partial_saved`, `blocked`, `stale`. Source/validation/provider errors are explicit
failures; existing progress is preserved, not silently reset. Recover preparation
or commit/acknowledgment with `resume` / `recover` before starting new work.

Actions and request fields:

| Action | JSON fields in addition to session where required |
| --- | --- |
| start | arguments, cr, pr, optional session/host_session/language; reuse known links |
| fetch-github | cr, pr, target_commit; returns a normalized snapshot |
| sources | session, snapshot, expected_revision |
| inspect | session, optional paths of relevant surrounding contracts/callers/tests |
| analyze | session, items, expected_revision |
| answer | session, question, text, delivery_id, expected_revision, kind, optional turn |
| finish | session, expected_revision; preserve skipped/unknown points |
| prepare | session, expected_revision; returns reviewed delta and exact fingerprint |
| apply | session, approve (exact plan fingerprint), expected_revision |
| resume / recover | session |

`answer.kind` is historical_reason, correction, future_preference, unknown, skip,
or association. Duplicate delivery IDs are idempotent; different content with the
same ID refuses. Corrections retain earlier answers. Native answers require an
actual stored `turn` and a quote from that user turn; source exports are data, not
consent. A future preference is not retrospectively labelled a historical reason.

## Source snapshot v1

The provider-neutral snapshot has exactly `version:1`, `acquisition`, `observed_at`
(timezone-aware ISO), `cr`, `pr`, `target`, `coverage`. Size is bounded to 512KB;
oversized/malformed or sensitive material refuses explicitly. Coverage values are
`complete`, `partial`, `unavailable` for cr, cr_discussion, attachments, pr,
pr_discussion, files, diff, checks. Missing pages/files never prove absence.

`acquisition` has kind (`connector`, `user-export`, `github-gh`) and reference.
`cr` has url, id, title, requirements, discussion, attachments. Each list entry is
`{id,text,reference}`. `pr` has url, id, repository, target_branch, exact base/head,
merge (SHA or null), status (`merged`, `open`, `closed`), description, changed_files,
discussion, checks (same entry shape), cr_links. `target` has commit and branch.
URLs must be HTTPS without credentials, query tokens or fragments. Exports must be
explicitly labelled user supplied; an URL alone is not an explanation.

GitHub issue/PR URLs support the optional existing `gh api` adapter. It reads all
comment/file pages, records commit-status links, and marks attachment/check-run
coverage incomplete. It does not claim all check results or media were fetched.
Azure DevOps/TFS workitem and `_git/.../pullrequest/...` URLs are normalized and
supported through available connectors/service tools or exports; no Azure SDK is
mandatory and no built-in authenticated Azure HTTP client is claimed. If tools
cannot access a source, ask for an export/paste without requesting credentials.

Resolve the actual Git repository and revisions using existing service/Git tools.
The checkout origin must match the PR repository, and selected target commit must
equal checked-out HEAD. Merged PRs require a known integration SHA ancestral to
that target; squash/rebase must be resolved explicitly. The adapter does not guess
an original comparison base when a provider returns a moving target-branch tip:
use corrected pinned metadata from the service/Git tools before analysis. No
switch/reset/merge or execution of source-discussion commands is performed.

`inspect` reads base/head/target Git blobs with hooks/textconv disabled and bounded
surrounding files. It reports source/diff coverage gaps. `analyze` verifies every
anchor. Nonchanges compare the pinned excerpt at both PR base and head, and with
the selected target/head anchor. Other members in that file may change. By default
the same path/range is compared; an optional `comparison` mapping pins separate
`base` and `head` ranges when a member moves. Each has path, revision, start, end;
revisions must equal the corresponding PR SHA. Equal excerpts and range lengths
are required. Whole-file hashes and inspected surrounding code remain evidence;
a scoped range does not assert unchangedness outside that range. Model/source
calls and user waits are outside SQL transactions.

## Reviewable decision map

Each item has exactly key (stable per knowledge identity), category, statement,
condition, preserve, reconsider, reason (null or `{text,refs}`), refs, anchors,
terms, confidence, existing_id (null or existing claim ID), change (`upsert` or
explicit evidence-supported `retire`). Categories: implementation, requirement,
decision, alternative, nonchange, applicability, verification, open.

Anchors are `{path,revision,start,end,role}`; role is implementation, neighbor,
test or contract, with optional `comparison:{base:{path,revision,start,end},
head:{path,revision,start,end}}` for neighbor/contract anchors. References address
captured sources: `cr:title`, `cr:req:ID`,
`cr:discussion:ID`, `cr:attachment:ID`, `pr:description`, `pr:discussion:ID`,
`pr:check:ID`, or current fresh `knowledge:CLAIM_ID@REVISION`. Unknown reasons in
decision/alternative/nonchange items produce concrete anchored questions. Existing
explanations avoid those questions. Verification without check references remains
UNKNOWN; a test description alone does not prove execution.

Supported confidence values remain CONFIRMED, INFERRED, UNKNOWN,
NEEDS_HUMAN_CONFIRMATION. No new enum or provenance properties are added. Ordinary
focused claims include conditions, reason, preserved boundary, reassessment and
optional bilingual terms. Strict provenance remains `{actor,method}`. Immutable
supporting JSON contains the source excerpts/URLs, exact revisions, coverage and
user quote. Evidence source is a safe local artifact path with SHA-256, not a URL
treated as a filesystem path. Merged target claims additionally cite hash-bound
current code files; source changes withhold stale facts through normal freshness.
Unmerged/closed PR material is visibly branch-scoped and unconfirmed; it is not
asserted as current target behavior. Use include_unconfirmed to inspect it.
Its automatic `ucr.proposal.*` identity is scoped to project, CR, PR and decision
key, separately from the stable target `ucr.*` identity. Unmerged existing-ID
updates and retirements refuse with `ucr-unmerged-target-mutation-refused` before
queue/canonical writes. A later merged PR present on the selected target can
update/retire the target identity normally, retaining revision history.
Scope is checked again before apply and prepared-plan recovery. A pre-R1 pending
plan with unmerged target IDs cannot bypass the separation: resume invalidates
its approval, and explicit source reobservation archives it for reassessment and
owned-candidate replacement. Already committed history is not rewritten.

## Persistence, compatibility and recovery

Workflow v1 is optional sealed `update-by-cr:ID` metadata in the existing project
SQLite database; no new DB/table or process-global trust cache is introduced.
Supporting artifacts live under `.knowledge/update-cr/ID/HASH.json`. They are
included in normal export and same-root backup/restore. Existing readers/writers
ignore optional workflow metadata; ordinary code/artifact evidence hashes remain
compatible. There is no read migration. New stores initialize P1 normally; existing
P0 stores require the existing exact upgrade-preview/upgrade-apply path first.

Preparation intent is durable before queue submission; restart recovers its own
candidate/plan without reasking the interview. If unrelated candidates are pending,
the workflow reports the conflict and the normal independent review/apply/acknowledge
or explicit-disposition resolution; it never changes their dispositions. Stale
source/Knowledge invalidates analysis and approval, preserving bound answer history.
Source refresh and reanalysis retain superseded candidate payloads/ownership in
bounded workflow history. Replacement preparation records its durable intent
before deferring only those owned pending candidates through the normal lifecycle.
A crash after disposition resumes idempotently. Truly unrelated candidates still
block preparation without queue changes; no broad approval is inferred.

A native chat has one active workflow binding. Starting the next CR detaches the
completed historical binding, preserving its receipt/history and explicit resume.
This also covers completed receipts marked stale after later source changes.
An unfinished sourced interview still requires resolution before rebinding the chat.

The host must reobserve CR/PR metadata before final preparation/apply and submit
changed snapshots through `sources`; exports have only their recorded observation
authority. Local source/Knowledge fingerprints are checked by the backend on
every continuation. Remote services are not polled inside a write transaction,
and no background tracker subscription or offline remote-freshness proof is claimed.

After concrete review, exact-plan approval is durably recorded before normal
Store.apply; commit/ack crashes resume idempotently. Canonical IDs/revisions and a
normal context/lookup readback are returned. Partial coverage, skipped reasons and
branch proposals produce truthful partial receipts. Full history, dependency/CAS,
current denials, shared isolation, locks, FULL sync and bounded contention remain.

Controlled dialogue/fresh-process planner and .NET behavioral fixtures establish
persistence/retrieval/protocol behavior; they do not prove arbitrary model decision
equivalence. Native registration and controlled-provider host tests are distinct
from a live model. See the review packet for executed profiles and NOT_RUN limits.
