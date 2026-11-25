# Native Confluence integration

Branch: `codex/knowledge-confluence-integration`, based on accepted main `6eb59254`.
Stages were committed separately: Stage 2 `608765b5`, Stage 3 `0a454a35`, Stage 4
`f37578c7`. Review refinements preserve provider authority (`63762cd5`) and avoid
changing a standalone Git inventory during first collection (`d6a1aafb`).

## Architecture and behavior

The baseline inspection confirmed local-only envelope/source checks, local
inventory validation during simulation/precommit, and descriptive external URLs.
Native Confluence now uses stable instance/page identity and independently bound
native revision + normalized snapshot hash. Snapshots retain immutable metadata,
quotes and shared content-addressed bodies. Hash/checksum/quote verification is
local and reproducible; it never attests authenticated live Confluence access.

No Confluence REST client, credential configuration, generic provider registry,
mandatory dependency or extra subagent was introduced. The agent discovers actual
configured Confluence MCP tools and supplies their results to the existing
Knowledge MCP. Normal context/retrieval stays offline and deterministic.

`confluence.py` validates native snapshots, evidence, version freshness and
retention. `confluence_sync.py` persists metadata observation, partial/completed
analysis, candidate outboxes, controlled source-specific proof updates, refreshes
and actual application receipts. `confluence_command.py` persists approved scope,
recursive/paginated work, search deduplication, bounded budgets and progress.
Store/lifecycle/discovery/deduplication/identity migration reuse existing validation,
revision history and exact atomic plan application. Source collection freezes its
multi-transaction work with the existing coordination gate. Canonical machine
application retains its execution lease, source revalidation and exact approval.

Page identity survives title/URL changes. Observed/analyzed/applied revisions are
separate, including zero-claim analysis. Completed unchanged native versions skip
content/model work where metadata-only MCP retrieval is available; identical new
bodies reuse completed analysis and refresh pending proof bindings without reusing
approval or provider authority. Changed/deleted pages affect only their own proofs;
independent Git and other-page proofs survive. Loss of all active proofs yields
NEEDS_HUMAN_CONFIRMATION and retained historical evidence. Timeout, access denial,
404 and incomplete search never confirm deletion. Same-scope contradictions retain
symmetric conflicts and clarification questions. Documentation-only implementation
is INFERRED/supporting, distinct from requirements, rationale, history and proposals.

`/knowledge-confluence` is installed globally in OpenCode 2.4.0 using the existing
plugin/installer and included in the wheel and kit. It asks for multiple roots,
optional spaces and autonomous permission once, then persists scope. Mandatory
recursive discovery precedes search. Unknown space membership is verified before
traversal/content. Pagination needs explicit exhaustion and non-repeating cursors;
access/capability/skipped/budget gaps remain visible and incomplete. Bounded page
chunks, offsets and outboxes resume across sessions. Status counters derive from
persisted discovery, analysis, submission and application state.

`/knowledge-update` aliases the supported exact-approval plan lifecycle. Collection
never applies candidates. Existing three commands and `/update-by-CR` remain.
Existing P1 projects do not rerun init, reset SQLite or rescan Git to add Confluence.
The Knowledge-only command does not transition a Harness runner. No IPM/UMUH
application source was edited. Additive migrations are transactional/idempotent;
old-root execution objects remain archived by explicit identity migration rather
than regaining authority.

## Verification

Final source and qualification details are recorded in `verification-summary.json`
and the final P4 run it references. The installable kit is under `distribution/`.
Earlier stage-focused tests and raw logs are retained alongside the source-bound
qualification, including the pre-fix first-enrollment experiment and provider drift
regression. Intermediate interrupted routes are not final PASS evidence.

See `docs/P4/CONFLUENCE.md` for MCP/normalization/storage semantics and
`docs/P4/CONFLUENCE-COMMAND-RU.md` for installation, incremental use and an explicit
verification guide for the existing UMUH store.

## Final verification and ready kit

Product source: `d6a1aafb3257eaadac67cbf5f93f2e58fca6e92a`. Source identity:
`832ef8851bfafe400d289f3048ff949f9946063b2c19b3d8d8fc791b304f87c8`. Local installed P4 qualification is **PASS_PORTABLE**:
28/28 commands; 539 tests, 526 PASS, 13 native-Windows-only skips,
zero failures/errors. This includes source transfer, legacy backup/upgrade/restore,
comparison, real .NET CLI/MCP/application routes, CR dialogue replay, independent
Knowledge-only installation, machine install/update and real OpenCode 2.4.0.
Raw ledger/tests/logs: `../P4/runs/caed5eb0fccc4ea28be2cd6d5194758e/`.
All source inputs were unchanged; every command-log and release-asset hash was
independently rechecked.

Exact-source machine CI is **PASS_PORTABLE on Linux** and **PASS_NATIVE on Windows**
([Actions](https://github.com/Ermak-P/Knowledge-/actions/runs/45662404178)). Installed focused suite:
138 tests on each OS (Linux skips two Windows checks; Windows skips none).
Both execute the real pinned OpenCode 2.4.0 registry/Code Mode/plugin, including
Confluence scope/work persistence and knowledge-update alias. Downloaded artifacts
were not executed locally; their Git source, every log and every kit asset hash
were verified. All manifested asset bytes and release-manifest semantics match the local
final distributable. Windows has a different ZIP hash due to manifest JSON
serialization/container metadata; no byte-for-byte ZIP identity is claimed.
Final full CI is PASS_PORTABLE on Linux. Windows full CI is FAILED during
unchanged bootstrap fixture cleanup (WinError 5), followed by the inherited
class-teardown recorder KeyError. Raw evidence: ci/final-full. Full Windows P4
qualification is not claimed; see [the separate defect note](EXISTING-VERIFICATION-DEFECTS.md).

Ready kit: [ZIP](distribution/knowledge-harness-0.5.0rc1.zip),
[manifest](distribution/RELEASE.json). SHA-256:
`d7895bc2078ef40eda33a90226ee3cebb5bd698e11b73710b52e976774de262f`.
Source checkout or extracted kit, Windows PowerShell 5.1:

```powershell
.\install.ps1 -McpDir 'C:\LLM\mcp\knowledge'
```

Restart OpenCode 2.4.0, open the existing project, then /knowledge-confluence.
No new /knowledge-init is required for an existing P1 store. Review/apply through
/knowledge-update with separate exact approval. [Summary](verification-summary.json).

## Boundaries and known limitations

* Confluence responses and semantic findings are synthetic fixtures. Actual
  installed stdio MCP and OpenCode 2.4.0 transport use a controlled local model.
  No real/private Confluence, live-model quality or private UMUH/IPM validation is
  claimed. This cloud catalog has no Confluence MCP; deployment uses the user's
  configured MCP and its actual capabilities.
* Coverage is client-reported traversal, not independent remote attestation. Missing
  metadata-only support may require fetching content just to read its native
  version; a supplied full-page fallback snapshot avoids a second content fetch.
* Analysis reuse is for completed pages. If the native source advances during a
  partial page analysis, obsolete partial findings are discarded and only that
  page restarts. Same-version checkpoints resume without redoing saved chunks.
* Semantic comparison is performed by the agent. Deterministic reconciliation
  uses exact UTF-8 statements and matching roles; when another page supports an
  existing meaning, reuse its exact statement/scope and supply the new page quote
  separately. Natural-language paraphrases are not automatically equated by a
  hidden model or embedding service.
* The existing core still validates its queue/plans on each transaction. Indexed
  native lookups and an 8 MiB body cache avoid redundant Git scans and unbounded
  text caches, but do not remove that global validation cost. Concurrent reviewed
  meaning/graph changes require explicit resolution; only compatible enrichment
  and verified source-specific proof changes reconcile automatically.
* Retention keeps unused cache revisions bounded, while snapshots referenced by
  active/historical evidence, queued candidates, plans or unfinished work remain
  pinned. Legitimate audit history is retained. Old runtimes without native source
  support cannot interpret post-import Confluence stores; rollback uses an
  approved pre-import backup.
* Stage 3 Windows machine CI failed in two pre-existing filesystem reliability
  tests (`unsafe-filesystem-object`, concurrent JSON `Access is denied`), while
  all Confluence cases in that run passed. Raw source/log/asset hashes were checked
  and retained under `ci/stage3-machine`. These races were not hidden by weakening
  filesystem checks. Final-platform receipts, if available, are separately listed
  in the verification summary. GitHub Actions REST access is Forbidden in this
  cloud; receipt branches are the available verified evidence transport.


Additional CI receipts for refinement 63762cd5: machine qualification PASS on
Linux and native Windows, including real OpenCode and all Confluence cases.
Full Linux CI ran 537 tests but failed in pre-existing Harness concurrency tests
(harness-busy/database locked and competing resume). Full Windows CI failed in
bootstrap fixture cleanup (WinError 5 on the runtime Python), then the existing
qualification driver's class-teardown error accounting raised KeyError before
writing tests.json. Both failed routes are retained under ci/provider-full;
passing machine routes under ci/provider-machine. Harness product code and these
unrelated tests/receipt validation were not changed to suppress the failures.
These receipts certify that older source only; the final d6a1aafb result is
reported independently in verification-summary.json.


The final Windows full-CI failure was reproduced in unchanged inherited fixture
cleanup/recorder paths, not suppressed or retried into a PASS. The bootstrap
fixture file is byte-identical to accepted main, and the recorder line is unchanged.
The lifetime of the file handle causing WinError 5 was not fully investigated in
this Confluence task. See the separate defect note and exact-source raw logs.
