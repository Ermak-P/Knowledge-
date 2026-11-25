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
