# P1 extension contract

Baseline a3c7ac7afd7cff6137b916832cf40019ca8b8c87; ordinary branch
codex/knowledge-harness-p1. No P2 runner, automatic commit, merge or deployment.

## Storage and compatibility

The P0 `knowledge-sqlite-v1` metadata and hash-pinned v1 payload schemas are
unchanged. An explicit `p1=1` extension adds revisions, receipts, reviews and
scans in the same database. Unknown extension versions refuse. `upgrade-preview`
seals a nonempty P0 export, project identity and upgrade version. `upgrade-apply
--approve EXACT` first retains a SQLite backup under `.knowledge/backup-HASH.sqlite3`,
then installs tables and initial revisions in one FULL-sync SQLite transaction.
Repeated upgrade is idempotent after a fresh preview; interrupted transactions
roll back. Backup files retain old data, not permission to relocate root identity.
Stop participating processes before restoring the backup to `store.sqlite3`;
retain the interrupted directory separately and inspect journals, never delete a
hot journal. Opening the restored P0 database reuses the P0 path; extension
upgrade can be attempted again. Canonical values, IDs, confidence, original queue
identities/status/bindings and migration/import history are preserved, not rebuilt.
Prepared v1 approvals survive a metadata-only upgrade only when their exact
queue and canonical fingerprint still match. Legacy JSONL remains unsupported.

## Operations and transactions

v1 `{version:1,operation:"add",records:{claims:[],evidence:[],relationships:[]}}`
remains supported. `version` retains `operations:["add"]` for this facade and
advertises `v2_operations` separately. P1 batch envelope is exactly:

```json
{"version":2,"operation":"batch","reason":"review reason","source":null,
 "operations":[{"action":"update","kind":"claims","id":"logical.id",
 "expected":1,"payload":{},"successor":null}]}
```

Each operation has exactly those six keys. Payload must be the unchanged v1
record of the selected kind for add/update; it is null for retire/supersede.
`expected` is the current immutable revision (zero for add). IDs cannot repeat
within a batch or conflict across pending candidates. Retire supports claims
and relationships; supersede supports claims and requires an active successor
claim ID, possibly added by the same batch. Historical successor chains may
continue through later supersessions, but must resolve without cycles to an
active claim; evidence IDs and retired terminal successors refuse. Evidence is never physically removed.
Unsupported fields/versions/targets fail before writes. New claims require
supporting evidence. Evidence can be updated with history. Each lifecycle
change requires a reason; source can be null for explicitly reviewed/manual
facts, or a snapshot object with identity/revision/kind and optional delta.
Source-bound batches require a matching fresh inventory at prepare and apply.
The product does not equate an explicit manual retirement reason with proof.

One P0 resolver, BEGIN IMMEDIATE lock, queue, plan, canonical commit and
acknowledgment path owns all mutations. Prepare binds canonical payloads,
revision metadata, source bindings and exact pending candidate payloads.
Approval must equal the returned sha256 fingerprint. A wrong/stale approval
cannot authorize a new transaction. After a stale scan, explicitly defer/reject
its old candidates, rescan and prepare again; approval is never carried forward.
Canonical rows, revisions, receipts and COMMITTED state commit atomically;
acknowledgment changes queue bindings and plan state in a separate transaction.
SQLite rollback protects interruption during mixed writes. Recovery never
approves prepared work. A COMMITTED batch pending acknowledgment blocks new
preparation with pending-acknowledgment-recover-first; recover/acknowledge first. Immutable receipt equality and historical payload
ownership permit old apply/ack retries after later revisions without reverting
current state. No physical record/history deletion is used.

`review --id CID --disposition rejected|deferred|pending --reason TEXT` records
the exact payload and review event and removes refused/deferred proposals from
ordinary preparation. A committed unacknowledged proposal cannot be reviewed
away. Unchanged proposal operation content (excluding capture/verification
clock fields) is not requeued on a different scan snapshot. Changed evidence
hashes or an explicit review back to pending can initiate new review.

## Lifecycle, confidence, freshness and graphs

Claim `status` remains confidence. Revision lifecycle is active/retired/
superseded. Evidence active/retracted/superseded is distinct. Review disposition
belongs to the queue. Capture time, source revision/dirty hashes and approval
provenance are retained; upgrade never backdates a verification. Verification
dates on extracted claims describe the source observation, not external truth.
No promotion to CONFIRMED is made by freshness checks. Deterministic source
syntax assertions are CONFIRMED only as syntax, never as business/runtime facts.

Full latest records remain structurally validated against v1 with historical
references intact. Active relationships may not refer to inactive claims;
active dependents of a retired claim require explicit reviewed closure. Reject
cycles, orphans, conflicting targets and inactive successors. Closure is not
inferred by text matching: a caller must review affected dependent operations.
Retired relationships have revision history. Default trusted context filters
inactive claims and any claim with missing/changed/unverifiable/retracted support,
then filters dependent closure. Returned P1 claims expose lifecycle, revision and
freshness metadata inside the measured byte budget. Evidence hash equality is
current; a byte-identical lexical anchor surviving unrelated edits is explicitly
`anchor-valid-file-changed` only after syntax is re-extracted in its current
context. A commented/string-only anchor is not current, including evidence from
the legacy v1 extractor. Source reads reject linked ancestors and oversized files.
This does not certify method bodies or deployment.

`lookup` explicitly inspects latest record/lifecycle/freshness even if inactive;
`history --id ID` exposes immutable revisions and their source/reason/plan;
`export` exposes all latest payloads plus revisions, receipts and review events,
with an explicit all-latest view label. It is not the trusted-current view.

## Discovery and reconciliation

`scan --max-files N` starts a bounded scan; `--scan-id ID` resumes. `--restart`
creates/reuses an identity for the current snapshot instead of stale progress.
Progress units are atomic chunks of at most N files. A crash loses only the
uncommitted chunk; prior durable chunks/observations survive, with no requeue of
completed proposals. Snapshot identity binds project, full included-file hashes,
committed revision, separate relevant staged/unstaged/untracked status, exclusion
policy, staged index blob identities and extractor version. Unmerged Git paths
are blocked rather than analyzed as valid C#. Changed source/configuration
refuses stale resume.
Relevant untracked source is included, never labeled committed HEAD.

`scan --base COMMIT --head COMMIT` verifies ancestry and requires head to equal
the checked-out HEAD. It records the rename-aware committed delta and dirty
hashes separately. Incremental analysis conservatively re-examines the full
included scope, including consumers, rather than labeling untouched partitions
fresh without examining them. Without Git, hashes/resume work; no history-based
retirement proof or revision-range guarantee is available.

No hooks, source instructions or models execute. The version-2 lexical reader masks C# comments and normal/verbatim/raw strings
without treating slashes inside a route literal as comments. Interpolated string
expressions remain conservatively opaque. XML comments cannot create dependency
facts. Old extractor checkpoints require restart; old evidence is revalidated.
Re-observation preserves reviewed confidence, provenance, dependencies, conflicts
and independent supporting evidence instead of silently resetting those fields.

XML project/package references,
C# declarations/inheritance, simple generic DI, literal route attributes/minimal
routes and persistence calls are lexical observations. Stable IDs bind logical
project/category/key; evidence binds exact relative path, line/excerpt and hash.
Duplicate lexical identities are reported as gaps rather than guessed symbols.
Partition/file coverage distinguishes inventory, analyzed XML, partial lexical
analysis, unsupported semantic analysis, exclusions and blocked content.
`complete` means all bounded inventory units processed without blocked units;
`semantic_coverage_complete` is always false for this capability pack. Hidden,
credential-risk, binary, generated, dependency and oversized files are excluded
or blocked with reasons. Scope does not claim external deployment availability.
No arbitrary quota or curated benchmark facts are read by discovery.

`reconcile --scan-id ID` is read-only and classifies current claims, freshness,
dependent effects and proposed retirement. A changed file with valid anchor
retains its fact. Missing/changed source alone is suspected obsolete or not
verifiable. Retirement proposals require a complete unblocked, unambiguous
lexical inventory, a recorded complete base scan, exact base file hash from Git,
observed declaration/registration removal and no subject references anywhere
in included current source/docs/tests/config. This narrowly retires source-syntax
assertions, not external/business/historical facts. Retirements/relationship
closure are returned as a proposal, never applied. Submit that exact JSON via
`submit --input`, inspect `prepare`, explicitly approve, apply and acknowledge.
A dependent that remains current can block the plan until separately reviewed.

## Adapters and errors

`knowledge init` creates an empty P0 store only. `knowledge-init` initializes a
new store's empty extension and runs bounded discovery/reconciliation; an existing
P0 store requires explicit upgrade approval. `/knowledge-init`,
`/knowledge-candidates-update` and `/knowledge-candidates-push` map to CLI commands
with those names without slash. Update delegates to scan (range optional); push
without approval delegates to prepare, with `--plan --approve` to exact apply.
Explicit acknowledgment remains required. These are functional CLI adapters;
live OpenCode host registration and execution are not delivered.

Read-only MCP preserves its three tool names. `knowledge_get_claim` accepts
`history:true`; claim/evidence reads accept `max_bytes`. Application JSON is
TextContent only with no duplicate structuredContent. Oversized point/history
reads return budget-too-small, not an unbounded second channel. CLI/API history
is the full explicit view; context and Harness use the same bounded Store path.
Unicode byte counts are UTF-8. Context retains no-answer/partial/budget behavior;
there are no read-side reconciliation/writes or shell grants.

CLI returns one JSON object, exit 0 when ok, exit 1 for operational errors,
argparse usage errors on stderr/exit 2. Important stable error codes include
upgrade-required, unsupported-extension-version, stale-scan-restart-required,
source-changed-during-scan-restart, source-drift-rescan-required,
stale-expected-revision, stale-plan-prepare-again, exact-approval-required,
active-dependent-needs-reviewed-change, active-relationship-needs-reviewed-change,
dependency-cycle and store-busy-retry. There is no unbounded retry loop.

## Verification

`scripts/verify_p1.py` starts a non-success run, checks independent packaging,
all accepted and new tests (including real stdio and killed processes), and
pinned application build/unit/discovery evaluation. No P0 report is overwritten.
The P1 ledger binds exact source files and all required current-run artifacts;
`scripts/make_review_p1.py` refuses incomplete, failed, mixed, missing or stale
source/evidence. Archive inventory hashes every included member and an external
SHA-256 binds the ZIP. Generated evaluations are not broad accuracy claims;
raw returned extras, gaps and limits remain visible. Native Windows and live
OpenCode/model integration remain NOT_RUN. P2 is not started.
