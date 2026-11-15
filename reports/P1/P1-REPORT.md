# P1 implementation submitted for independent review

Run `fe11fd6fd62e4372b5d6e830889775be`; source `f6fbbd3dc18cfe085c3694bd6ab529f23e5eb7ac7b0c54bb450083bb33069954`. Raw evidence: `runs/fe11fd6fd62e4372b5d6e830889775be/`.

Branch `p1`; baseline/HEAD `a767c744cc771541e4b3727ff15b8cd526657ba6`, with uncommitted P1 changes identified
by SOURCE-REVISION.json. Not externally accepted. P2 was not started.

## Actual verification

`bash scripts/setup.sh`, then `.venv/bin/python scripts/setup_benchmark.py`,
`.venv/bin/python scripts/verify_p1.py`, `.venv/bin/python scripts/make_review_p1.py`.
Python 3.12.14, pinned SDK 10.0.404, SQLite, MCP 1.30.0 on Linux x64.
104 product tests passed, including all 43 accepted P0 regressions;
no skips. Both wheels built and Knowledge ran in a dependency-free environment.
Pinned application build and 49 unit tests passed before and 49 after P1
integration, with zero failed or skipped tests. Real stdio sessions, killed
processes and competing writers executed; no live model was used.

## Concrete result

A full scan now persists inventory/coverage/observations, generates source-backed
proposals, resumes bounded work, and refuses stale source. Versioned batches
update the same logical claim, retire/supersede assertions and change graph edges
through exact approved transactions. Old payloads/receipts remain readable and
retries do not revert later revisions. Retired or stale facts disappear from
trusted context while explicit lookup/history/export retains their explanation.

A synthetic ExternalManagement removal produced retirement proposals after
verified before/after source and consumer checks; approved application removed
old active assertions. Independent claims remained. Missing evidence without
corroboration, blocked/incomplete scans and external/historical statements did
not cause automatic retirement. Reviewed dependency closure can retain a still
valid dependent while retiring its old relationship, without deleting history.

## Review choices, repairs and limits

Source schemas retain confidence semantics; lifecycle/freshness/review are separate.
Self-review repaired a real history/current graph interaction: retired edges must
not force a newly independent current payload to retain an obsolete dependency.
It also tightened historical receipt ownership, upgrade backup binding, P0
prepared-approval compatibility and scan identity exclusion of store journals.
The final run was executed after these changes. The independent R1–R5 corrections are in P1-R1-RESPONSE.md; the shared
reactivation model, canonical uniqueness and bounded-work repairs are in P1-R2-RESPONSE.md.

Discovery is deliberately lexical. It proves source syntax, not business rationale,
runtime dispatch, deployment availability or complete semantic analysis. Unsupported
files, ambiguous identities, gaps, returned lexical extras and partial coverage
are exposed in raw evidence. Retirement is narrow and conservative; unresolved
consumer changes can block a proposal until reviewed. Old unacknowledged commits
must be recovered/acknowledged before preparing later canonical changes.
NuGet emits upstream vulnerability warnings; pinned dependencies/tests were not
changed or weakened. .NET requires host synchronization-object access and uses
single-node builds, no shared compilation and LibraryRestore=false for unit
baseline (no browser assets). Native Windows, live OpenCode/model/provider host,
browser/database/Aspire deployment are NOT_RUN. No portable required check remains
failed or blocked in this run.

## Delivery

P1-CONTRACTS.md defines exact operations, commands, policies and recovery.
ACCEPTANCE.json maps all 20 rows to executed tests/evidence. Discovery, lifecycle
and upgrade reports link to raw generated results. The ZIP contains source,
tests, task, setup/verification, licenses and the current run, excluding SDKs,
caches, credentials, synthetic databases and old verification artifacts.
