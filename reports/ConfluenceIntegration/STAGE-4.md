# Stage 4 — installed OpenCode command and durable discovery

`/knowledge-confluence` is installed by the existing machine installer/plugin and
included in the wheel and kit. It uses the existing Knowledge MCP plus the user's
configured Confluence MCP. `/knowledge-update` is a supported alias of the existing
exact-approval candidate push lifecycle; the original three commands remain.

The command asks for roots/sections, optional spaces and autonomous search once,
persists the approved scope, and supports subsequent scope changes. A separate
additive command-schema extension stores checksummed scope/run/work/page receipts.
Mandatory recursive traversal precedes search. Cursor exhaustion is explicit;
missing or repeating cursors cannot yield complete coverage. Unknown space
membership requires metadata before content/traversal. Native IDs and normalized
literal queries deduplicate pages and searches. All MCP responses are untrusted
source data; they do not grant execution or scope authority.

The agent discovers actual MCP signatures, executes bounded work, supplies native
metadata/content and atomic findings, and reports persisted checkpoints. No REST
client, token storage, provider framework, new dependency or required subagent is
introduced. Metadata-only is preferred; full-page fallback can cache its snapshot
without a second fetch. Context is bounded to one page/chunk, with persisted offsets
and partial findings. Unchanged versions/bodies skip model work. Budgets pause
rather than truncate the work queue. Access/capability failures/skips stay partial.
Finished old receipts are bounded; unfinished work and source/evidence/plan history
are retained. finish validates integrity and runs safe source-cache retention.

New stores can use the Confluence command without a full Git scan. Existing P1
stores do not rerun init; legacy/P0 migrations retain exact approval. Connecting
this Knowledge-only command does not transition a Harness runner. Identity
migration recognizes the exact command schema, archives old-root execution
controls and clears active old-root analysis handles while preserving canonical
records and source snapshots. No application source code was changed.

Automated synthetic evidence: stage4-focused.log (13 initial command cases),
stage4-installed.log (72 command/source/sync/existing machine cases),
stage4-final-installed.log (129 focused installed cases including dedup and all
39 CR cases), stage4-command-installed.log (21 final command cases). The final
installed stdio test covers import -> candidates -> plan/approved apply -> offline
retrieval -> native version change -> incremental MCP synchronization -> approved
apply; it asserts old proof superseded and new native version active. Other cases
cover multiple roots, recursive pagination/cycles, scope persistence/changes,
autonomous-only/authorized search, budgets, access failures, restart/receipt replay,
partial offsets, metadata fallback, space checks and explicit identity migration.
Python AST, JavaScript syntax and git diff whitespace checks pass.

Native OpenCode qualification now explicitly checks all five command registrations,
actual Code Mode discovery/call of knowledge_confluence, native command scope/work
persistence and the knowledge-update alias, with existing permission-denial checks
retained. Exact-source installed full/native results and the final kit are collected
in the final report after this source commit. No live/private Confluence or UMUH
access is claimed. Operator guide: docs/P4/CONFLUENCE-COMMAND-RU.md.

Earlier Windows CI failure is retained, not hidden: Stage 3 fast Windows run
fcbcc445d4b2478f9507fa1efd10f8e1 passed all 17 Confluence sync cases but failed
existing test_core_reliability cancellation/resume and concurrent atomic metadata
checks with unsafe-filesystem-object / Access is denied. Stage 3 Linux fast passed.
Raw source/log/asset hashes are verified in ci/stage3-machine/validation.json.
No filesystem protections or these existing assertions were weakened for Confluence.
