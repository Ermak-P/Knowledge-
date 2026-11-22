# Audit stages 1–2 contracts (0.5.0rc1)

This additive correction covers AUD-01/02/03/04/05/07/09. The product version and
SQLite formats remain unchanged. Qualification binds the exact source map and
wheel/kit hashes; a version string alone does not identify this correction.

## Source coverage

Discovery snapshots carry `coverage_errors` when included enumeration fails.
Read/extraction failures and disappeared paths are blocked, not intentional
exclusions. Errors participate in snapshot identity and survive chunk/resume.
Unknown directory scope conservatively prevents negative proof for every related
project partition. Accessible positive observations remain reviewable. Reconcile
returns `negative_evidence_gaps` and no retirement based on that unknown scope.
A new scan after restoring access can establish complete coverage. Healthy
snapshot identities retain their earlier representation (no empty errors field).
Harness execution snapshots and maintenance identities fail with a structured
coverage error rather than accepting an incomplete source tree. Link/private path
protections and proven retirement remain in force.

## Natural-language startup grants

Catalog, semantic normalization, CLI and host use the independent
`startup-en-ru-v1` full-source decision. A positive model quote alone is insufficient.
Contradictory denial wins, including `starting containers is forbidden` and
`запуск контейнера не разрешен`. Unknown limiting clauses do not disappear into a
new grant. The supported grammar is deliberately narrow: current explicit startup
permission for the bound resource, optionally stopped-only and never-restart.
Quoted/log/past permissions do not authorize. Ordinary same-binding clarification
can retain an existing grant; changing resource/binding cannot inherit it.
Replay may revoke a weaker historical grant but never manufactures a new one.
Readiness is distinct from startup: a ready resource needs no start; a running
unready resource is never restarted; an authorized stopped existing resource may
start once within current operator allowlists. Structured local `memory-teach`
remains a separate trusted operator contract, never a model write tool.

## Project/shared transfer recovery

The existing project SQLite metadata stores a sealed
`operational-transfer:<id>` intent. It binds source ID/revision/hash, target
scope-specific ID, source message/hash, approved binding and shared-root identity.
Gate order is project → shared → short individual SQLite transactions. No new
coordinator database, model under the gates, or two-database atomicity is claimed.

| Durable phase | State and next recovery action |
|---|---|
| prepared | Authorized intent exists; create/check deterministic target |
| target-saved | Target committed; CAS-retire source with successor link |
| source-retired | Source retired; verify both sides and mark completed |
| completed | Receipt can acknowledge the verified target without inference |
| conflict | Source/target changed independently; preserve both histories and block affected lookup |

While pending/conflicting, related lookup returns `instruction-transfer-pending`.
Unrelated actions continue. A repeated authentic source message or local CLI
`knowledge memory-transfer-recover --root ROOT --shared-root SHARED` completes
already authorized work without a model. `memory-inspect` exposes transfer state.
A fault before intent creation leaves nothing authorized to recover. Concurrent
correction fails CAS; it is never overwritten. Resolve the competing records with
normal explicit operator corrections/retirements and inspect history before a new
transfer. Both records explicitly retired remove the old conflict's applicability.
Original wording, predecessor/successor and source/target histories remain.

## Degraded host sessions

Host session format 2 adds bounded message envelopes: source ID/hash, monotonically
ordered sequence, pending/resolved/sensitive/overflow state, config/memory binding,
and only the permitted pending payload. Limits: 128 message envelopes, 128000 UTF-8
pending payload bytes, 512000 serialized session bytes. Resolved envelopes discard
text. Sensitive inputs retain only their hash/order, never raw text.

| Operation | Normalizer available | Unavailable / timeout / malformed |
|---|---|---|
| Chat and read-only analysis | Normal receipt | `ok=true`, explicit degraded reason/notice; available |
| Existing guard / no-start / format controls | Enforced independently | Retained; no clearing on missing inference |
| Service startup | Existing binding, grant, current controls and allowlist required | Unresolved session blocks covered effect |
| Patch / recipe | Existing authorization and controls required | `host-controls-unresolved`, no patch/process |
| New teaching | Validated supported binding or explicit unbound intent | At most unbound intent; no new grant |
| Recovery | Exact source binding, ordered controls | One explicit retry per envelope after service recovery, or local operator resolution |

`python -m harness.host_ingress --root ROOT --recover-session SESSION` retries
pending stored sources once in order; optional `--source-id ID` selects one.
Config/memory changes produce a precise conflict requiring inspection, not silent
reinterpretation. Sensitive/overflow payload cannot be retried automatically.
The local operator can submit JSON containing exactly `source_id`, `source_hash`,
`decision: "no-new-controls"` to `--resolve-session SESSION`. This resolves that
source's uncertainty while retaining existing controls and grants no permission.
Envelope-count overflow requires a new independent session. Legacy sessions with
an existing sequence but no ordered ledger are fenced on new ingress; old controls
remain, with an explicit instruction to use a new session.

Late results cannot replace newer session restrictions/formats. Completed-binding replay
returns the saved record receipt without inference or reapplying old controls. An
authentic replay of an unbound intent may finish its original binding, including
a lost host pending pointer; ordering still prevents replacing newer controls.
Source-ID reuse, corrupt envelopes and corrupt stores remain errors. The OpenCode
hook consumes normal degraded notices without throwing. Enforcement covers
connected Harness broker/startup/patch/recipe paths, not arbitrary native shell or
editing outside those paths.

## Architectural retrieval and P4 delivery

`Store.context` keeps its arguments and returns `delivery_version=2` /
`context-engine-v2`. Compact claims now include `revision`, `depends_on`, current
lifecycle/freshness, confidence status and provenance. Closure has depth 4, at most
128 dependency references and the same caller item/byte limits as ranked facts.
A child can remain with undelivered parent IDs; `dependencies.complete=false`
and item/depth/status/freshness/missing/byte reasons make that partiality explicit.
Dependencies are knowledge relationships, never executable guards or grants.

Diagnostics distinguish absent store, lexical no-match, status/lifecycle policy,
changed/missing/unverifiable evidence, blocked source scope, dependency filtering
and budgets. At most 8 query-related filtered entries contain IDs/revisions/source
refs and next steps, without filtered statements. Corruption remains an error.
Matches plus exclusions/overflow become `matches-with-gaps`. Counters count the
union of ranked candidates and considered dependencies; `returned` is the final
claim count, `dropped=candidates-returned`, after trimming. Omitted diagnostics and
dependency references are explicit. Very small responses say `budget-too-small`.
Actual compact UTF-8 bytes obey the cap, including CLI's newline; MCP uses one
TextContent with no duplicate structuredContent (JSON-RPC envelope separate).
Review/approval and supported evidence remain necessary to establish facts.

P4 automatically retrieves a bounded deterministic goal/acceptance/item/scope slice
for first Main, Coding items/repair attempts, diagnosis Planning and final Reviewing.
Building/Testing use deterministic gates without model frames. Reviewer retrieval
uses canonical knowledge independently of Coding's narrative. Operational guards
remain on broker preflight, not duplicated into architectural slices.

The journal records delivery ID, role/phase/attempt, query/scope/source/config/store
binding, selected IDs/revisions, evidence watch, payload hash/bytes and duration.
Provider request receipts record the actual projected delivery hash/bytes/IDs.
Cache reuse survives JSON reload and context rotation. Source/config/store generation
and watched evidence changes invalidate it. No extractor or model runs per ordinary
tool round; evidence watch hashes only bounded known paths. The whole serialized
provider body includes tools and diagnostics in its existing hard cap: optional
knowledge yields explicit `provider-byte-budget` first, irreducible authority and
acceptance produce `split-required` before HTTP. No token savings claim is made.
Persisted response/inflight is consumed or refused under existing rules without
rewriting its request or repeating unknown effects. Older P4 journals acquire new
slices at the next safe request boundary; task-v1 retains its earlier delivery path.

## Reproduction, rollout and rollback

Run `python scripts/setup_p3.py`, `.venv/bin/python -B -m unittest discover -s tests -v`,
then `.venv/bin/python -B scripts/verify_p4.py`. Windows uses the existing
`scripts/verify-p4-windows.ps1`. The full route builds/transfers/installs the kit,
runs regressions, the fresh-process delivery/control trial, standalone Knowledge,
legacy upgrades and actual .NET/TRX qualification. The isolated delivery trial is
also runnable with installed Python:
`python -I scripts/audit_stages12_trial.py --output NEW_EMPTY_OUTPUT_DIRECTORY`.
It uses a controlled HTTP provider and real SQLite/files/process gates; it is not
a live-model test. See the current source-bound `reports/AuditStages12/REVIEW.md`.

Before a user rollout, finish/fence pending effects, back up both Knowledge stores
and the separate Harness journal/session state, install the hash-verified kit and
run doctor. Rollback installs the previous verified kit against the matching backup;
do not resume newly pending transfer/degraded/P4 delivery state with old code that
cannot enforce it. Do not delete pending state or replay unknown process outcomes.
A real host/model trial remains a separate acceptance step; use
[PERSISTENT-INSTRUCTIONS-LIVE-HOST.md](PERSISTENT-INSTRUCTIONS-LIVE-HOST.md) and its
installed driver with isolated owned fixtures. No user services or databases were
used by these tests.

Legacy P0 stores remain readable through the core and task-v1 contracts. Their
confidence flag alone has no lifecycle revision/current freshness proof; P4
withholds such text with `knowledge-lifecycle-upgrade-required` and a supported
upgrade/review next step. It never upgrades or rewrites the old store implicitly.
