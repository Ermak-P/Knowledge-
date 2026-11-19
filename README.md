# Knowledge + Harness — P4 implementation candidate (0.5.0rc1)

New tasks use the task-v2 bounded pipeline in [P4 usage](docs/P4/USAGE.md) and [the P4 example](examples/p4/task.json). Main coordinates sequential Coding items, build/test run as trusted runtime recipes, and independent Reviewing remains mandatory. Task-v1 inputs retain the accepted legacy policy.

Build with Python 3.12: `python scripts/setup_p3.py`, then `.venv/bin/python scripts/build_p4.py --output .local/p4-release`. Verify the installed product with `.venv/bin/python scripts/verify_p4.py`. Read [P4 acceptance](reports/P4/ACCEPTANCE-MATRIX.md) before adoption; native qualification and live-model results remain separate.

Automatic .NET testing (runner v2): [contract](docs/P4/AUTOMATIC-TESTS.md), [machine installation (RU)](docs/P4/INSTALL-RU.md), [project setup (RU)](docs/P4/PROJECT-SETUP-RU.md). The runtime finds every case-insensitive `*Tests.csproj` and verifies the complete suite.

## Retained P3 and historical documentation

# Knowledge + Harness — P3 release candidate

Version 0.3.0rc1 provides independent Knowledge, controlled Harness execution, a portable offline core install kit, native Windows backend, exact-approved lifecycle tooling and a project-local OpenCode v2 companion. Start with [START-HERE](START-HERE.md), [operational docs](docs/P3/INSTALL.md) and current [qualification evidence](reports/P3/QUALIFICATION.json). Native Windows requires actual matched CI/NTFS/PowerShell evidence; a source workflow does not qualify it. Publication and production migration remain user-controlled.

## Historical P0–P2 documentation

# Knowledge + Harness — P2

Harness 0.2 executes controlled tasks through a configurable HTTP model provider, separate Main/role contexts, scoped edits, real build/test/review gates and recoverable Knowledge capture. Knowledge remains independently installable. See [START-HERE](START-HERE.md) and [P2 contracts](reports/P2/P2-CONTRACTS.md) for commands and precise boundaries. P2 is submitted for external review; live model/OpenCode/Windows integration remains unexecuted.

## Historical P0/P1 documentation

# Knowledge + Harness — P0

Knowledge is an independently installable Python 3.12+ evidence store. Harness
is its minimal read-only consumer. P0 supports approved factual additions,
transaction recovery and offline legacy migration. It does not implement an
agent runner, full-project discovery or P1 lifecycle changes.

## Install and verify

```sh
bash scripts/setup.sh
.venv/bin/python scripts/setup_benchmark.py
.venv/bin/python scripts/verify.py
```

Setup installs locked development/MCP dependencies and both local packages.
The benchmark script fetches the ordinary eShopOnWeb checkout at
`0c2c95d9d450d07fcd4e96e95e1cd48c20834e99` and installs a SHA-512-verified
Linux x64 .NET SDK 10.0.404 under `.local/dotnet`. An existing SDK can be reused:
`python scripts/setup_benchmark.py --sdk-dir /workspace/dotnet`.
Windows reproduction is in `scripts/verify-windows.ps1`; native Windows
verification is **NOT RUN**. Cloud execution may require permission to create
.NET OS synchronization objects. The single verification command fails if a
required product, packaging or benchmark check fails. Logs go to `reports/P0`.

CLI-only installation has no runtime dependencies:

```sh
python -m pip install ./packages/knowledge
knowledge version --root /absolute/existing/project
```

MCP is optional (`knowledge-p0[mcp]`); the development lock includes it for tests.
Harness installation is `pip install ./packages/knowledge ./packages/harness`.
No live model, OpenCode, SQL Server, browser or Azure account is needed for P0.

## Add and retrieve evidence-backed knowledge

All commands require an explicit existing project root. Initialization creates
only an empty `.knowledge/store.sqlite3`, not facts or discovery results.
The slash command `/knowledge-init` means full-project discovery/reconciliation
and is **not implemented**; it is distinct from `knowledge init`.

```sh
knowledge init --root /absolute/existing/project
knowledge submit --root /absolute/existing/project --input candidate.json
knowledge prepare --root /absolute/existing/project
knowledge apply --root /absolute/existing/project --plan sha256:EXACT_HASH --approve sha256:EXACT_HASH
knowledge acknowledge --root /absolute/existing/project --plan sha256:EXACT_HASH
knowledge context --root /absolute/existing/project --task 'basket checkout' --max-bytes 16000
knowledge lookup --root /absolute/existing/project --kind claims --id example.claim
knowledge status --root /absolute/existing/project
knowledge recover --root /absolute/existing/project
```

Use the fingerprint returned by `prepare`, not the placeholder above. Apply does
not implicitly acknowledge. `recover` completes proven committed acknowledgments;
it never auto-approves prepared plans. `validate` and `export` are also available.
Queries omit unconfirmed claims unless `--include-unconfirmed` is supplied.

A candidate is one JSON object with exactly `version: 1`, `operation: "add"` and
`records`, containing arrays `claims`, `evidence`, `relationships`. Record schemas
are the unchanged legacy v1 schemas shipped in `knowledge/schemas`. A complete
example and source anchors are generated by `scripts/benchmark_dataset.py` and
saved as `reports/P0/benchmark-candidates.json`. Candidates may form a coordinated
batch with cross-references; `prepare` validates the complete proposed graph and
blocks the whole plan on errors. Unsupported lifecycle operations/fields fail.

MCP: `knowledge-mcp --root /absolute/existing/project` runs a read-only stdio
server exposing `knowledge_context`, `knowledge_get_claim`,
`knowledge_get_evidence`. Harness: `harness --root /absolute/existing/project
--task 'basket checkout'`. Optional `.harness/config.json` accepts
`{"response_max_bytes":16000}`. Neither adapter grants shell/write execution.

## Safety and scope

One SQLite store owns canonical records, queue, sealed plans and import journal.
Every writer uses the same bounded SQLite write lock. Deduplication uses stable
identity and NFKC/case/whitespace-normalized statements, not semantic similarity.
Exact fingerprints bind root identity, canonical snapshot and candidate payloads.
Claim `status` retains legacy confidence semantics, not lifecycle semantics.
Evidence validity is its own field. Validation never proves truth or freshness.

Paths with spaces and non-ASCII characters are supported. Roots must exist;
`..`, symlinks/junctions in ancestors or store descendants, hardlinked control
files and copied stores with another root identity are rejected. Relative roots
are resolved relative to the invoking working directory; no Git-root search or
other project fallback occurs. Stores are bound to their normalized absolute
root; relocation requires explicit export/reconstruction, not copying a database.
Use a local filesystem with SQLite locking and atomic directory publication.
Native Windows junction/locking semantics remain unverified. See
[contracts](reports/P0/CONTRACTS.md) for crash and filesystem guarantees.

## Legacy migration and recovery

Run `knowledge migrate-preview --root ROOT`, review its manifest/semantic diff,
then `knowledge migrate-apply --root ROOT --approve EXACT_FINGERPRINT`.
Only offline, quiescent `.ai` snapshots with supported v1 records/schemas and
complete terminal transaction journals/plans are accepted. The queue format is
explicitly documented in the migration report; absent original writers are not
claimed compatible. The source remains unchanged and is thereafter an archived
input; `.knowledge` is the only writable canonical store.

Restore the captured source to a **new absent** absolute directory with
`knowledge restore-legacy --root ROOT --destination /absolute/new-backup`.
For ongoing store backup use SQLite's backup API while holding a read snapshot,
or copy a closed database after all participating processes stop. Preserve
`.knowledge` and any SQLite recovery journal together after an interrupted write;
open through `knowledge recover`. Never delete a journal or reset Git to recover.

Review results, limitations, source audit and the reproducible review ZIP are
under [reports/P0](reports/P0/P0-REPORT.md). Browser assets, SQL Server/Aspire,
native Windows and live-provider checks are separate from the portable P0 suite.

## P0 consolidated correction (R1–R4)

Migration preview explicitly discovers both `.ai/state/candidates.json` and
`.harness/knowledge/candidates/queue.jsonl`. The JSONL format is not adapted in P0:
any present external queue (even empty) refuses migration with discovery details
and conversion requirements. Coexistence refuses as ambiguous; neither is silently
preferred. Supported interchange bytes and discovery absence are approval-bound.
Persisted JSON is UTF-8. Invalid decoding/container types produce operational JSON
errors; argparse usage errors remain stderr/exit 2.

The MCP context limit includes the actual compact UTF-8 application TextContent.
Context has no duplicate structuredContent; only the fixed JSON-RPC envelope is
outside that limit. CLI and MCP JSON objects retain identical semantics.

Verification creates `reports/P0/runs/RUN_ID/run.json` and invalidates the current
success pointer and packet before checks. Logs, subprocess exit codes and generated
outputs are hashed and snapshotted within that run. In-progress, interrupted,
failed, missing-output, changed-source and mixed-artifact runs cannot generate a
success packet. Dependency caches may be reused; success evidence cannot.
`make_review.py` validates the completed current run against the exact source and
all current/snapshotted artifacts before generating acceptance or ZIP output.

## P1 discovery and lifecycle

P1 extends the accepted P0 payloads with durable source discovery, immutable
revisions and reviewed lifecycle changes. See
[the P1 contract](reports/P1/P1-CONTRACTS.md) for exact envelopes, policies and limits.

```sh
bash scripts/setup.sh
.venv/bin/python scripts/setup_benchmark.py
# Existing P0 project: inspect upgrade-preview, then use its exact fingerprint.
.venv/bin/knowledge upgrade-preview --root /absolute/project
.venv/bin/knowledge upgrade-apply --root /absolute/project --approve sha256:EXACT
# New project: functional whole-project discovery adapter; canonical facts remain unapplied.
.venv/bin/knowledge knowledge-init --root /absolute/new-project --max-files 100
.venv/bin/knowledge scan --root /absolute/project --scan-id SCAN_ID --max-files 100
.venv/bin/knowledge scan-status --root /absolute/project --scan-id SCAN_ID
.venv/bin/knowledge reconcile --root /absolute/project --scan-id SCAN_ID
.venv/bin/knowledge knowledge-candidates-update --root /absolute/project --base BASE --head HEAD
.venv/bin/knowledge review --root /absolute/project --id CANDIDATE --disposition deferred --reason 'Needs review'
.venv/bin/knowledge knowledge-candidates-push --root /absolute/project
.venv/bin/knowledge knowledge-candidates-push --root /absolute/project --plan sha256:EXACT --approve sha256:EXACT
.venv/bin/knowledge acknowledge --root /absolute/project --plan sha256:EXACT
.venv/bin/knowledge history --root /absolute/project --id CLAIM_ID
.venv/bin/python scripts/verify_p1.py
.venv/bin/python scripts/make_review_p1.py
```

The `/knowledge-*` interface maps to the same CLI commands without the slash;
live OpenCode installation remains outside P1. Complete bounded scans report
lexical coverage separately from semantic completeness. Retirement proposals
remain reviewable JSON, requiring submit/prepare/exact approval. A filename
inventory, missing evidence or failed semantic tooling never proves retirement.
The old P0 sections above describe the accepted historical scope; P1 capability
and verification claims are defined in the separate P1 contract and run packet.

Automatic .NET testing (runner v2): [contract](docs/P4/AUTOMATIC-TESTS.md), [machine installation (RU)](docs/P4/INSTALL-RU.md), [project setup (RU)](docs/P4/PROJECT-SETUP-RU.md). Normal .NET templates have only trusted build recipes; every case-insensitive `*Tests.csproj` is a mandatory automatic gate.
