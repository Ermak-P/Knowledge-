# P0 implementation report

Corrected P0 is submitted for second review, not marked externally accepted.
Run: ca4cda1b57b54a7fb29d0745ded39e0a; source identity: e058e6a9e504a624599a8bade58f34347cd03a4236ae0546edbf49e5d95c4110.
All 16 portable acceptance conditions have executable passing evidence.
This is not certification of the complete product or a production Windows release.

## Delivered source and checks

Source: product checkout `/workspace/Knowledge-`, working tree over `878ca2eb711405919f82fe57be0d798b42fa5066`.
Source content identity: `cd330a47fb8bcf9eaccdaaa5483bbeb9261c7e96b63dc14cd2a0a9dd70852891`; per-file hashes in SOURCE-REVISION.json.
No automatic Git commit, push, publication or production mutation was performed.

```sh
bash scripts/setup.sh
.venv/bin/python scripts/setup_benchmark.py
.venv/bin/python scripts/verify.py
.venv/bin/python scripts/make_review.py
```

This instance reused the verified SDK with
`.venv/bin/python scripts/setup_benchmark.py --sdk-dir /workspace/dotnet`.
The complete verification entry point ran successfully after final product fixes.
Python 3.12.14, SQLite from Python's standard library, MCP 1.30.0, .NET 10.0.404.

- 43 product tests passed, no skips in this Linux run; real MCP stdio sessions
  and controlled subprocess crashes/concurrent writers included.
- Both packages built as wheels; Knowledge installed and initialized/validated
  in a fresh venv without MCP or Harness.
- Synthetic legacy migration preserved exact records, candidate IDs/statuses,
  history and source bytes. Backup restore was byte-equal. Incomplete journal,
  dual-store, repeat and interruption scenarios passed.
- Pinned eShopOnWeb build and 49 existing unit tests passed with integration
  absent, then 49 passed after integration, zero failures/skips. Current-run TRX
  files and counters are retained. Tracked application source diff is empty.
- 15 curated source-anchored records traversed the real writer/import/ack
  pipeline. Nine CLI/MCP query expectations passed; Harness retained expected
  first-ranked support and the no-answer case. Full result lists are retained
  so lexical extras can be inspected; this is not a broad accuracy metric.

## Behavior and review decisions

Before: an incomplete project-local legacy installer, no delivered candidate
writer/Harness, and no independent package or supported recovery workflow.
After: reusable Knowledge/Harness packages with explicit project identity;
standalone CLI, optional read-only MCP, coordinated durable candidate queue,
exact-fingerprint approval, atomic canonical/journal commit, payload-bound
acknowledgment/recovery, bounded provenance-bearing retrieval and offline
lossless fixture migration. Project data contains no duplicated executable tools.

Legacy schema bytes and semantic validator/ranking were retained. SQLite
replaced multi-file application transactions to provide testable atomicity
across canonical data and import journal. Full source map/call graph is in
SOURCE-AUDIT.md; storage/permission/error guarantees in CONTRACTS.md.

Self-review traced submission through every shipped public entry point and
checked immutable payload binding, normalized duplicate races, root isolation,
missing-plan assessment, packaging and byte bounds. Review found and fixed a
publication crash gap by replacing a two-link step with atomic directory
publication, and tightened actual legacy journal layout/seal checks. Migrated
candidate IDs now remain stable in the operational queue as well as history.
All affected tests and the full required verification were rerun successfully.

## Limits and diagnosed initial failures

The original ZIP's installer expects missing operational docs. Its unmodified
baseline failed at that packaging prerequisite; the new package has its own
complete documented installation. No historical docs or results were fabricated.
The old transaction/writer interfaces are not blindly promised compatible.

.NET initially needed permission for OS mutexes. A multi-node build failed;
one node/no shared compilation succeeded. Optional LibMan browser downloads
were blocked by proxy HTTP 403. The supported `LibraryRestore=false` switch
omits those assets for the .NET build/unit baseline without modifying upstream
source or tests. Browser/UI behavior is not claimed. Upstream NuGet vulnerability
warnings are retained in raw logs; pinned dependencies were not silently upgraded.
No TLS, signature or checksum verification was disabled.

Native Windows/NTFS, Windows junction/locking behavior, real OpenCode/live model,
browser UI, SQL Server, full Aspire/containers and Azure checks are NOT RUN.
Windows reproduction commands are supplied; portable results do not certify
native behavior. Live executor/provider integration is outside delivered P0;
there is no code-changing runner to validate. No required portable check remains
failed or blocked. P1 lifecycle/discovery and P2/P3 work were not started.

## Review packet

`reports/P0/P0-review.zip` contains source, tests, reproducible setup/verification,
input archive, docs, acceptance results, source checksums, curated generated
artifacts and raw evidence. It excludes credentials, caches, SDK/package files,
private runtime settings and upstream application source. The MIT upstream
license is included. REVIEW-INVENTORY.json lists every archive member/hash;
packet-check.json verifies archive integrity and byte-level inventory equality.
