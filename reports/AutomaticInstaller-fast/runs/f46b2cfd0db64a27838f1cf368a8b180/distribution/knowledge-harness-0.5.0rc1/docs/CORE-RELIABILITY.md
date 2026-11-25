# Core reliability: launcher, Code Mode and durable coverage

This delivery keeps the 0.5.0rc1 package version and identifies builds by source
identity and release hashes. Knowledge remains independent of Harness and IPM.
See [local Windows/IPM validation](Knowledge-IPM-Integration-Validation.md).

## Architecture and confirmed defects

The previous generated `launch.py` used `os.execv` on Windows as well as POSIX.
Windows does not provide POSIX process replacement semantics: a client observing
the outer launcher could lose ownership of the real interpreter and its stdio.
The corrected generator keeps POSIX exec and uses synchronous Windows child
execution. `windows-process.py` creates a private kill-on-close Job Object,
assigns the child atomically with `PROC_THREAD_ATTRIBUTE_JOB_LIST`, and inherits
only the three standard handles. It does not read or buffer protocol data.
It waits, returns the actual exit code and writes startup diagnostics to stderr.
It also observes the verified outer venv redirector's process handle. Closing
the launcher kills its MCP descendants, while deliberately detached scan workers
can break away. Other Python/model processes are never selected or terminated.
Windows 10+ is required; no claim of native macOS execution is made.

One stable bootstrap dispatches both `mcp` and `command`. Upgrade replaces its
owned files and helper transactionally. The activation probe exercises this
stable dispatcher before the journal is committed; failure restores the prior
generation. Retry the same installer after a failed first installation. Keep
the existing TEMP long-path expansion/identity and path safety checks.

Code Mode previously had no backend tools for scanning, reconciliation or plans;
command text required filesystem/child-process access unavailable in that sandbox.
The machine MCP now exposes those operations. A separate nested Git invocation
also inherited MCP stdin: it now uses the existing bounded Git subprocess helper
with DEVNULL stdin, avoiding Windows named-pipe startup deadlock.

The old automatic helper stopped whenever any coverage entry was blocked, even
if hundreds of independent files remained. It now continues committed chunks
until there is no remaining eligible work. File failures remain visible and
cannot turn into successful whole-project coverage.

## OpenCode 2.4.0 and capability discovery

The global native plugin sets `codemode: true` for `knowledge_machine`. It checks
connection and installed backend capabilities before starting a command and calls
the host's `ctx.permission.assert` for the actual session/agent/tool. The trusted
plugin may start the installed backend; agent Code Mode needs no Node imports,
filesystem API, fetch, shell, SQL or process launcher.

Inside the actual Code Mode `execute`, call
`search({namespace:"knowledge_machine",limit:30})`, inspect `items`, and use the
returned `path` and `signature`. Do not guess namespace aliases or import printed
tool names. `knowledge_capabilities` returns the actual backend contract
`knowledge-machine-v2`, provider identity and supported operations, without
contacting the model. Registration grants no permission. OpenCode can omit denied
tools from search: an advertised tool absent from search may be a host permission
or visibility problem. A disconnected MCP, old backend, wrong roots, denied tool,
and unsupported sandbox API are different failures. Do not bypass denial with a
shell. The native plugin's early `ctx.tool.list()` is not a reliable lazy MCP
catalog, and its MCP domain does not implement `ctx.mcp.resource`.

| Registered MCP tool | Purpose |
|---|---|
| knowledge_context | Existing bounded context retrieval |
| knowledge_get_claim | Existing claim and lifecycle history |
| knowledge_get_evidence | Existing evidence lookup |
| knowledge_instructions | Existing instruction lookup |
| knowledge_capabilities | Actual contract, provider identity, supported operations |
| knowledge_scan | start/status/resume/fresh/cancel; full or incremental scope |
| knowledge_scan_diagnostics | Paged failures/coverage/reconciliation/impact/policy/identity/scans |
| knowledge_source_read | Bounded included source, original hash and current source binding |
| knowledge_submit_candidates | Reviewed source-bound v2 proposals, no apply |
| knowledge_plan | Prepare, separately approved exact apply, observe recovery |
| knowledge_semantic_preflight | Explicit test mode safeguards, no network probe |
| knowledge_change_review | Existing CR workflow adapter; cannot forge host user turns |

The three global native commands are `/knowledge-init`,
`/knowledge-candidates-update`, `/knowledge-candidates-push`.
The existing project/legacy `/update-by-CR` contract is retained; its template
uses `knowledge_change_review` in Code Mode. Old append/update aliases are absent
and were not recreated. Candidate submission, plan preparation and explicit apply
remain separate. A prepared fingerprint is never itself user approval. CR
sessions bound to native user turns retain their original ingress requirements.

MCP selects the active workspace with standard roots discovery and Git top-level;
multiple roots fail explicitly. Source reads use relative included paths, byte
and line/column pagination, original raw hashes and snapshot bindings. They are
not arbitrary file reads. Tool replies enforce byte budgets before mutations.
Observe an outcome after a truncated mutation response before retrying.

## Physical coverage, semantic coverage and diagnostics

Core scans use `IN_PROGRESS`, `COMPLETED`, `COMPLETED_WITH_GAPS`. Jobs additionally
use `STARTING`, `RUNNING`, `BLOCKED`, `OUTCOME_UNKNOWN`, `CANCELLED` and a brief
`FINALIZING` phase while owned processes release their handles. The command
projection reports a fully extracted repository as `PARTIAL` because lexical
coverage is not semantic understanding; check `coverage_complete` independently.
`processing_complete` means no pending files, including a run ending with gaps.

Counters are recomputed from durable per-path states; retries/resume do not add
the same file twice:

```
eligible_files = processed_files + partially_processed_files + failed_files + remaining_files
discovered_files = eligible_files + policy_excluded_files + classified_excluded_files + out_of_scope_files
```

`pending_retries` is a subset of failed files eligible for explicit retry, not
extra work counted in the equation. `pruned_directories` counts observed excluded
directory entries, not an invented count of files below them. `discovered_files`
counts observed included/excluded files; unenumerated descendants cannot be
claimed as discovered. Legacy extraction `status: partial` can describe limited
C# lexical semantics despite full physical read; physical
`processing_status: partial` specifically means unread/unprocessed bytes.

Per-file diagnostic pages show relative path, stage, reason_code, byte counts,
encoding, bounds and retry eligibility where known. Reasons include
`INVALID_ENCODING`, `UNSUPPORTED_ENCODING`, `EXTRACTION_FAILED`,
`FILE_TOO_LARGE`, `PARTIAL_EXTRACTION`, `EXCLUDED_BINARY`, `EXCLUDED_GENERATED`,
`EXCLUDED_BY_POLICY`, `ACCESS_DENIED`, `UNREADABLE`, `UNSAFE_PATH` and
`FILE_CHANGED_DURING_SCAN`. Encoding/parse errors never print source contents.
Known unsafe filesystem objects are refused before reading and leave explicit
gaps. Source identity changes and integrity violations still stop the operation.

Safe positive lexical proposals from unaffected identity partitions may be
queued despite unrelated document failures. Failed/partial code, ambiguous
identity, enumeration gaps and exclusions restrict reconciliation and negative
proof. Excluding a source is not deletion, missing lexical syntax is not
obsolescence, and no scan automatically retires or applies canonical knowledge.
Reviewed retire/supersede still require existing supported operations, current
source evidence, expected revisions, preview and exact approval.

## Encodings and bounded files

UTF-8 has a fast path. UTF-8 BOM, UTF-16 LE/BE BOM, XML UTF-16 signatures and
reliable XML encoding declarations are recognized. BOM takes precedence; a
conflicting declaration is not an encoding-guessing mechanism. Plain BOM-less
UTF-16 requires explicit policy unless identified as XML. Legacy encodings are
allowed only by a declared XML encoding or explicit relative-glob policy.
Allowed canonical names: utf-8, utf-8-sig, utf-16, utf-16-le, utf-16-be, cp1251,
cp1252, iso8859-1. There is no blanket CP1251 fallback, error replacement or
discarding undecodable bytes. Raw original bytes determine evidence hashes;
decoding does not rewrite source or rebind old evidence.

Inventory streams complete hashes in 64 KiB blocks; default maximum hashing is
128 MiB/file. Above it, hash is absent and the file is failed, never represented
by a prefix hash. Default extraction budget remains 512000 bytes. Oversized
JSON/XML/config/YAML/Markdown yields a bounded preview with explicit analyzed
bytes and unread-region coverage gaps. Oversized code fails unless an explicit
bounded per-format policy permits it. Extraction budgets are capped at 8 MiB,
hash budgets at 1 GiB. A growing/changing file fails source identity validation.

Small JSON is strictly parsed, including duplicate-key and nonfinite-number
rejection. Small XML uses ElementTree with DOCTYPE/entities rejected and no
external resolution. Oversized previews are not complete structure validation.
YAML remains strict-decoded content inventory/preview: **no YAML grammar or
semantic validation is claimed**. No new parser dependency was added.
Git CRLF normalization remains supported for bounded small files; inability to
prove normalized identity for a large file conservatively marks dirty state.

## One project discovery policy

Optional `<project>/.knowledge/discovery.json`:

```json
{
  "version": 1,
  "exclude": [
    {"glob": "reports/generated/**", "reason": "Regenerable reports; not application contracts"},
    {"glob": "assets/vendor/**", "reason": "Third-party generated assets"}
  ],
  "include": ["reports/generated/Contract.json"],
  "legacy_encodings": {"legacy/manuals/*.md": "windows-1251"},
  "max_file_bytes": 512000,
  "format_limits": {".json": 1048576},
  "max_hash_bytes": 134217728
}
```

Globs are case-sensitive POSIX relative paths with `/`; no absolute paths,
backslashes, drives or `..`. Include takes precedence over explicit exclusions
and may open a soft generated/hidden directory. Administrative state directories,
links, unsafe objects, credential-risk names and unsupported suffixes remain
protected. It cannot turn every binary/generated file into source. No blanket
exclusion of JSON, XML, YAML, deployment or documentation formats is introduced.
Excluded paths retain the applicable rule and reason in diagnostics. Changing
policy or reader implementation invalidates incompatible resume/cache evidence.

## Durable progression, recovery and provider bindings

The external helper loops committed core chunks, printing first/every 25/final
progress. It returns 0 for physical completion, 2 for completed-with-gaps, and
fails for fatal/no-progress/timeout conditions. It never approves candidates.
Native commands return promptly; a detached worker holds project writer ownership
and passes the lease into each child, so killing a worker cannot permit a second
writer while its existing chunk child is still running. A second compatible
start observes the same job. Status is compact; detail uses paged diagnostics.
The templates allow at most four observations per turn, then a compact handoff.

Resume uses committed state and skips completed paths. Source snapshot, base/head,
project, scope, policy/reader, installed release and provider bindings must match.
Normal rerun verifies the current snapshot and can retain its ID if unchanged;
explicit fresh creates a new execution ID while preserving semantic queue dedup.
Cancel is cooperative at a durable boundary; it does not kill a half-committed
chunk. Fresh during an active scan is refused until cancel/observation completes.

Version 2 checkpoint JSON has a checksum and atomic replacement; old version 1
is accepted with root/scope/ID validation. A checksum is corruption detection,
not an authorization signature. Windows metadata readers share-delete so status
does not prevent replacement. Corrupt checkpoints are never trusted. If SQLite
committed before a checkpoint write failed, inspect diagnostics `section=scans`,
verify the exact scan ID/current source, then explicitly use `observed_scan_id`
with resume. It is validated against durable source/scope/bindings and does not
start an unobserved retry. Unknown outcomes require observation, never automatic
replay. Process receipts include creation stamps to avoid PID-reuse confusion.

Deterministic scanning does not call a model. Semantic preflight reports actual
endpoint/model/evidence, excluding keys, and refuses `test-double` without
`allow_test_double: true`. Synthetic semantic claims cannot be submitted as
CONFIRMED. Reviewed semantic candidates atomically retain shared provider hash,
model, evidence mode and contract; provider drift blocks normal Store prepare
and apply as well as machine commands. Reanalyze under the corrected live
provider; changing configuration never promotes old synthetic output. Preflight
does not verify endpoint availability or model quality.

## Deployment, backup and rollback

Run the same `install.ps1 -McpDir ...` from the new source/verified kit. It
delivers the corrected bootstrap, helper, wheel, plugin, templates and these docs;
no site-packages patch is needed. Provider edits, shared memory and project DBs
are preserved. Restart OpenCode to adopt the new runtime. There is no SQLite
schema migration in this change: knowledge-sqlite-v1 and existing extension,
queue, lifecycle, CR sessions and decision history remain valid. New scan reader
identity requires fresh execution for incompatible old scans; old checkpoints
are not converted into fabricated compatible evidence.

Use the existing approved `knowledge.maintain_cli backup-preview/apply` before
upgrade and `restore-preview/apply` for same-root/same-OS restore. The local
handoff gives exact PowerShell commands. Back up external machine/provider/host
configuration separately while quiescent. Restoring an old complete machine
directory and configuration snapshot rolls back code; do not edit current.json
or runtime files manually. Never let old and new workers write concurrently.
Retain the new runtime to read new scan metadata if reverting code; source-bound
plans must be regenerated after any source/provider/release change.
