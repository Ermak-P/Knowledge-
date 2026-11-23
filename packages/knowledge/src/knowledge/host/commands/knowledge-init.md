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

Summarize actual root, provider reference/evidence, scan ID, included coverage,
queued candidates, dependencies/conflicts/unverifiable facts, semantic gaps and
diagnostics path. Full inventory completion is PARTIAL semantic coverage. Do not
infer retirement from lexical absence. Candidates remain unapproved. Suggest
/knowledge-candidates-push to prepare a reviewable plan.

Arguments (optional JSON): $ARGUMENTS
