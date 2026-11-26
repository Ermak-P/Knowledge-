# Knowledge MCP, consumer, and runtime validation

The implementation is based on `15d2a2b`, the main-branch merge of scan lifecycle
recovery. It adds a diagnostics section and a scan action to existing tools.
The maintainer MCP catalog still has 13 tools. The consumer catalog has five.
There are no new runtime dependencies.

## Replay of the reported failures

| Workflow | Baseline | Updated |
| --- | --- | --- |
| Candidate discovery and inspection | 2 calls, 2 invalid calls, 1 corrective retry, incomplete | 2 calls, 0 invalid calls, 0 retries, complete |
| Submission instructions | 2 calls, both valid lookups, 1 alternate-name retry, no match | 1 call, 0 retries, matched |
| .NET configuration source read | 1 call, `unsupported-json-comments`, scan completed with gaps | 1 call, source read succeeded, scan completed |
| Reported invalid candidate call replay | Discovery path unavailable | 1 invalid call, 1 corrected discovery call, and 1 inspection |

The candidate section required a candidate ID. A scan ID in that section was
an invocation error, and the misleading scan-ID message plus the absence of a
dedicated discovery section prevented correction. The backend now identifies the
unexpected argument and supplies the discovery invocation. The two submission
instruction names were accepted as project knowledge lookups. Packaged
instructions and tool-name discovery were missing from the implementation.
The JavaScript `preflight.map` error was in the caller. Destructuring the result
of `Promise.allSettled` yields one settled object per variable. The published
example exercises both a rejected promise and a structured tool error.

Serialized input schemas increased from 6,022 to 6,361 bytes. The complete tool
catalog increased from 7,795 to 8,232 bytes. The successful candidate workflow
returned 451 bytes for discovery and 1,910 bytes for a candidate page. Packaged
submission help returned 858 bytes. These are application JSON payload sizes.
Baseline calls returned shorter responses because they returned errors or
empty matches. [Per-call application and MCP result sizes](MEASUREMENTS.json)

A baseline-created synthetic store contained 1,605 eligible files, including
1,604 successful files and one failed BOM-encoded `appsettings.json`. After
the offline runtime-path migration, the linked recovery analyzed that one file
and published 1,605 successful files. It preserved the original terminal scan.
It refreshed one historical candidate's source binding and retained one active
candidate and zero duplicate groups. Repeating the recovery extracted zero files.
Canonical claims remained empty. Source identity re-enumeration and hashing
still ran, so this fixture does not establish a wall-clock speedup. [Measurements](MEASUREMENTS.json)

## SQLite results

| Synthetic storage operation | Result |
| --- | --- |
| Initial database, 25,000 pending candidates | 22,634,496 bytes |
| First preparation | 41,922,560 bytes, 6.259 seconds |
| Second preparation, 25,001 pending candidates | 61,218,816 bytes, 10.592 seconds |
| Preview | 14.001 seconds |
| Approved cleanup and vacuum | 41,730,048 bytes, 39.761 seconds |
| Retained after cleanup | 25,001 pending candidates and the active plan |

The obsolete prepared payload was 19,272,455 bytes. The file shrank by
19,488,768 bytes. The fixture uses product preparation and validation, then
performs cleanup with the exact approval fingerprint. The receipt test converts
a legacy full payload, compares the exported receipt and knowledge before and
after, and recovers a committed plan awaiting acknowledgment. [Measurements](MEASUREMENTS.json)

## Acceptance

The installed Linux suite ran 686 tests in 473.098 seconds, with 673 passes,
13 platform skips, and no failures or errors. A fresh installation of the
final code passed all 46 focused contract, consumer, storage, capture, scan,
push, and change-review tests.

| Requirement | Result | Evidence or limit |
| --- | --- | --- |
| K01 Dialect selection, BOM and comments, trailing commas per dialect, escaped strings, syntax positions, overrides, limits, full and incremental read consistency | PASS | Structured source contract, source reliability tests, .NET consumer source audit |
| K02 Targeted source and reader-policy recovery, checkpoint preservation, historical diagnostics, compatible incremental caching, idempotency, duplicate reconciliation, canonical protection | PASS | Linked recovery tests and a baseline-created fixture with 1,605 eligible files |
| K03 Every diagnostic section, candidate discovery, identifier validation, argument combinations | PASS | Real stdio contract tests and published section matrix |
| K04 Actionable structured errors, byte budgets, unknown resource and durable state handling | PASS | Real stdio transport tests and scan and push recovery regressions |
| K05 Built-in help, schema-valid examples, packaging, absent stores | PASS | Installed stdio tool discovery and validated examples |
| K06 Parallel read example, error replies, sequential mutation guidance | PASS | Executed Node.js fixture and MCP guidance |
| K07 Automated replay, measurements, independent review, duplicate regression | PASS | Recorded replay and regression tests. Independent review findings addressed |
| OpenCode version detection, compatible newer APIs, capability errors, rollback of partial registration | PASS | 11/11 native Linux checks on each of 2.4.0 and 2.4.2, plus incompatible API and collision fixtures |
| Fresh read-only default, no provider or Harness, explicit maintainer selection, upgrade mode preservation | PASS | Isolated installs in both modes. A real upgrade from the baseline retained maintainer access and the edited provider bytes |
| Backend catalog and direct-call enforcement, no caller elevation, filesystem permissions, concurrent consumers | PASS | Three independent stdio sessions with read-only files and unchanged database bytes |
| Capture defaults off, automatic extraction and delivery bypassed, readonly overrides required capture, pending outbox and explicit existing policies preserved | PASS | Harness task completion and delivery retry tests |
| One project-local Knowledge runtime directory, local Git ignore rule, runtime data excluded from discovery | PASS | Root-cleanliness assertion and scan and maintenance tests |
| Offline layout migration, active locks, conflict refusal, interrupted rerun, canonical store and durable history preservation | PASS | Legacy store fixture, interrupted migration, independent lock contention |
| Current and approved plan protection, retention, dry run, approval guard, cleanup recovery, concurrent consumers, receipt integrity, existing store compatibility | PASS | SQLite maintenance and crash tests, plus the 25,000-candidate benchmark |
| Native Windows filesystem, locking, PowerShell, and OpenCode qualification | NOT VERIFIED | Linux runtime and Linux OpenCode executed |
| Live production repository, Confluence, and model qualification | NOT VERIFIED | Synthetic files and controlled host and provider fixtures |

## Compatibility boundary

Existing databases retain their path, project identity, canonical records,
history, queue, and approval fingerprints. The offline layout move preserves
database bytes. The upgraded runtime reads legacy receipt formats. Older
runtimes cannot read the new reference receipts. Keep participating writers on
the upgraded runtime. Retention tracks supersession for preparations made by
this runtime. Historical same-base plans without tracking remain eligible only
after their canonical base becomes obsolete.

Knowledge core owns the project database, its sidecars, and the control lock.
The project writer lock is shared by scan and plan workers, maintenance, and
Harness. The maintenance directory holds transaction and identity journals.
CR receipt artifacts already lived under the store directory. The machine
installer's worker diagnostics stay in installation-local state.

The independent review raised the Git index and incremental cache checks during
recovery, installer mode preservation after interrupted adoption, case-insensitive
runtime exclusions, public history links, partial host registration, and retention
across repeated preparations. Tests and synthetic workloads cover the resulting
changes. [Operations](../../docs/P4/KNOWLEDGE-OPERATIONS.md)
[MCP contracts](../../docs/P4/KNOWLEDGE-MCP-CONTRACT.md)

## Reproduce the measurements

```sh
/path/to/baseline/bin/python scripts/replay_knowledge_contract.py --baseline
/path/to/current/bin/python scripts/replay_knowledge_contract.py
/path/to/current/bin/python scripts/knowledge_storage_benchmark.py --output /tmp/knowledge-storage.json
```

Use a baseline interpreter with the Knowledge and Harness packages installed
from `15d2a2b`. The current interpreter should use the implementation under
test. The replay creates isolated working directories and runs real stdio MCP.
