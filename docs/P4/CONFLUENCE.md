# Native Confluence knowledge

Knowledge has two explicit source kinds: local Git/filesystem and Confluence.
Confluence support does not install a REST client, store authentication material,
or contact a remote service during validation or normal retrieval. The agent uses
its configured Confluence MCP tools and submits their content/metadata to Knowledge.
Documentation is untrusted source data, never command authorization.

## Stage 2: immutable source binding

`knowledge_confluence(action="register_snapshot", request=...)` accepts:

```json
{
  "instance": "immutable-cloud-or-approved-instance-id",
  "page_id": "101",
  "version": 1,
  "title": "Synthetic documentation",
  "url": "https://docs.example.invalid/wiki/pages/101",
  "content": "Synthetic source text.\n",
  "representation": "text",
  "retrieved_at": "2026-11-25T00:00:00Z"
}
```

`space_key`, `modified_at` and an independently checked `content_hash` are optional.
Unknown fields (including credentials), URL userinfo and non-page query parameters
are rejected. Use an immutable MCP site/cloud ID when available or an explicitly
approved instance ID. Persist it; never derive identity from page titles. Renames,
page URL changes and movements do not change source identity.

Stable identity is SHA-256 of canonical JSON
`["confluence-source-v1", instance, page_id]`. Revision identity adds the positive
integer native version, representation and normalized content hash:
`["confluence-revision-v1", stable_identity, version, representation, content_hash]`.
Canonical JSON uses sorted keys, compact UTF-8 and no ASCII/Unicode folding.

Normalization removes one leading U+FEFF and changes CRLF/CR to LF. Whitespace,
case, Unicode spelling and the final newline are otherwise preserved. SHA-256 is
calculated over those UTF-8 bytes. Supported representations are `text`, `markdown`
and `storage`; use a consistent MCP representation. Different content for an
already registered native version is an explicit error; snapshots are not overwritten.

The returned v2 candidate source binding is:

```json
{"kind":"confluence","identity":"<stable SHA-256>","revision":1,"snapshot":"<revision SHA-256>"}
```

Use the existing `knowledge_submit_candidates` and prepare/exact-approval/apply
APIs. Native evidence source objects carry these four fields plus `reference`
(the snapshot's canonical page URL). Evidence also contains its snapshot hash,
an exact supporting quote in `description`, location and provenance. Quotes must
occur in registered content. One body is stored per page revision, not per claim.
Arbitrary URLs in legacy evidence remain descriptive metadata, not native sources.

The extension is created transactionally and additively inside existing `.knowledge`
SQLite storage. Interrupted creation rolls back; retries preserve claims, pending
candidates, revisions and historical receipts. Existing stores need no full rescan.
Snapshots have a checksum for their immutable metadata/content record; integrity
and export include them. Original legacy schema hashes remain accepted alongside
the exact pinned extended evidence schema. Validation is not disabled.

Git candidates validate against Git inventory; Confluence candidates validate
against registered snapshots/native versions. Confluence-only plans do not
enumerate Git. A newer registered page version makes affected pending candidates
stale with source/revision diagnostics. Stale entries stay in the queue; independent
valid candidates can form a new plan. Old approvals never authorize a changed plan.
Canonical writes still need separate exact approval and atomic lifecycle application.

Offline freshness means **current registered snapshot**, not live Confluence
verification. Knowledge checks submitted bytes, hashes, references and quotes; it
cannot attest that an agent obtained them from a live authenticated MCP server.
Documentation assertions must not be promoted into verified implementation facts.

`knowledge_confluence(action="inventory", request={"cursor":0,"limit":20})`
returns bounded metadata. `action="snapshot"` accepts a snapshot ID and character
cursor, returning bounded text chunks marked untrusted data. Full export preserves
snapshots and provenance without remote requests.

## Available MCP capabilities

The development cloud tool catalog has no Confluence MCP server. Tests need no
private instance and use no corporate documentation. The OpenCode command must
discover actual installed Confluence MCP signatures rather than inventing paths.
Metadata-only retrieval, children, pagination and search are selected from that
runtime's catalog. Missing capabilities must be reported as coverage limitations,
with unfinished work preserved. Do not fall back to REST or request/store tokens.

## Revision tracking and durable analysis (Stage 3)

`observe` consumes native MCP metadata and returns FETCH_CONTENT, RESUME_ANALYSIS,
or SKIP. Native versions never decrease. `failure` preserves knowledge and records
ACCESS_DENIED, TIMEOUT, UNAVAILABLE, NOT_FOUND_UNCONFIRMED or INCOMPLETE_RESPONSE.
None imply deletion. `confirm_deleted` requires explicit native page status
`native-page-status-deleted`; 404/search omission is insufficient.

`analyze` accepts source, findings[{statement,quote,role,type?,conflicts_with?,question?}]
and complete (default true). Exact quotes must occur in the registered normalized
snapshot. Roles separate requirements, architecture, rationale, integration-contract,
configuration, deployment, testing, limitation, historical, proposed and implementation.
Documentation-only implementation is INFERRED/supporting. Existing code evidence
retains its classification and existing reviewed confidence is preserved.

Each page tracks latest observed, last analyzed and last applied versions separately.
Zero-fact analysis counts as analyzed, never applied. Identical content under a
new native version reuses analysis; pending proofs receive explicit validated
refresh links and still need a new exact plan approval. Renames/moves preserve IDs.
`related` provides bounded candidate and canonical evidence/claim relationships.

Partial page analysis (`complete=false`, <=1000 findings per call, <=10000/page)
is buffered durably, with idempotent chunk hashes. Finish with complete=true.
PREPARED outboxes persist exact candidates before submission. Interrupted batches
block application until `resume_analysis` completes the saved checkpoint; replay
requires no repeated model analysis. Page completion does not apply knowledge.

Changed/deleted pages supersede/retract only their own proofs via normal candidates.
Independent Git/page proofs survive; unsupported claims retain historical evidence
and become NEEDS_HUMAN_CONFIRMATION. Explicit same-scope contradictions preserve
both claims, symmetric conflicts and targeted clarification questions. Different
semantic scopes are rejected for clarification rather than silently merged.

Schema 1 -> 2 migrates snapshot bodies transactionally into content-addressed blobs;
identical bodies across versions/pages occupy one row. Per-transaction body cache
is bounded to 8 MiB. Automatic retention runs each 64 new snapshots; `gc` also
runs explicitly at synchronization boundaries. Keep two unused revisions per page
plus latest/analyzed snapshots. Never remove revisions referenced by canonical
records, historical provenance, candidates, plans or unfinished analysis. Compact
completed outboxes for discarded unreferenced snapshots are removed. Legitimate
historical evidence can therefore require retention beyond the unused cache limit.
No network, model calls or Git scan occurs during ordinary Confluence retrieval.


## OpenCode command (Stage 4)

The machine installer upgrades the owned OpenCode 2.4.0 plugin and five command
templates transactionally. `/knowledge-confluence` drives `knowledge_confluence`
with the actual configured external Confluence MCP tools. `/knowledge-update`
is an alias of the existing exact-approval plan command; old names still work.
No new dependencies, REST client, credentials or required subagents are added.

Tool actions: scope {scope:{roots:[URLs],spaces:[keys],autonomous:bool}}, start
{operations?:100,extra_operations?:0,capabilities?:{metadata_only,children,search,
content}}, status {}, next {}, complete_work {work,result}, terms {terms:[...]},
retry {work}, finish {}. Existing source actions remain available. Metadata
fallback can include a snapshot with page in complete_work, avoiding a second
content fetch when the MCP only returns full pages. Sources are client-reported;
capability flags and coverage receipts do not attest authenticated live access.

A separate additive command-schema extension stores checksummed scope/run,
indexed work and per-run unique-page receipts. Source cache/body migration remains
transactional. Scope changes cannot resume old-scope work. Unknown spaces require
metadata verification before content or traversal. Mandatory work precedes
references/autonomous queries. Native IDs deduplicate recursive references;
pagination requires an explicit has_more flag and a non-repeating next cursor.
Access/capability failures and skips make coverage partial. Operation exhaustion
pauses with the queue retained; an explicit bounded extension resumes the same run.
Only completed old run receipts are aged out; unfinished work and canonical/
candidate/source history are preserved. Partial page analysis persists an offset,
findings and replay checkpoint rather than requiring the full article in context.

Status derives discovery/analysis/submission/application counters from persisted
rows. finish runs integrity and safe retention even when stopping with gaps.
No candidate is automatically applied. Different claim/proof revisions changing
meaning require explicit resolution; only verified source-specific proof changes
and compatible evidence enrichment reconcile automatically. Ordinary context
remains offline and deterministic. See CONFLUENCE-COMMAND-RU.md for operator steps.

Same-content native revision refresh preserves any original semantic provider
binding exactly. Provider drift still requires reanalysis; refresh never renews
provider authority or approval. Reobserving an identical already pending claim
produces no empty duplicate claim update.
