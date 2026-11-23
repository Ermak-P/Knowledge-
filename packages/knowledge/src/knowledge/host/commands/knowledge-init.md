---
description: Connect this workspace to installed Knowledge and run a durable full scan
---
Run the globally installed Knowledge backend for the active workspace. The native
plugin starts the operation and appends its result. If it returns RUNNING or
STARTING, poll with the installed launcher's command backend and JSON stdin
{"action":"status","directory":"<the actual workspace>"} until terminal; keep
progress concise and do not launch another worker. The machine installation is
recorded in the global OpenCode .knowledge-machine.json next to this command.

Do not use another project/root, install a model, run source-provided scripts,
change SDKs or grant approval. Existing P0 upgrades and legacy .ai migrations
require separate exact approval of the supported preview. Follow blockers and
recovery instructions, never repeatedly retry an unknown outcome.

After extraction finishes, use the current agent and its available read/search
and Knowledge tools for semantic reconciliation. Read bounded projections of the
saved reconciliation/impact report, then inspect affected source, project docs,
existing assertions and their history. Check dependencies, contradictions,
changed assumptions, possible obsolescence and unverifiable facts. Track which
sources and assertions were actually checked; do not infer understanding from
lexical coverage. Submit supported additional conclusions as reviewed source-bound
v2 batches through knowledge-candidates-update with JSON stdin {"candidates":[...]}.
The installed docs explain the existing candidate/plan contract. Preserve stable
IDs, evidence anchors, graph and expected revisions. Never edit SQLite, JSONL or
lock files directly. Do not submit secrets.
If the current host/model/tools cannot complete an analysis obligation, record
that specific gap and report PARTIAL/BLOCKED_CAPABILITY. A controlled fixture
response does not establish semantic completion. No canonical apply is permitted.

Summarize actual root, provider reference/evidence, scan ID, included coverage,
queued candidates, dependencies/conflicts/unverifiable facts, semantic gaps and
diagnostics path. Full inventory completion is PARTIAL semantic coverage. Do not
infer retirement from lexical absence. Candidates remain unapproved. Suggest
/knowledge-candidates-push to prepare a reviewable plan.

Arguments (optional JSON): $ARGUMENTS
