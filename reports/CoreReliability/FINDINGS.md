# Core reliability implementation and review record

Task: [exact supplied request](../../tasks/Knowledge-Core-Reliability-Fix.md).
Implementation branch: `codex/core-reliability-fix`, based on `f1fc690735`.
Final verdicts and source-bound test evidence are in ACCEPTANCE.md.

## Root causes and scope of proof

1. **Windows launcher ownership:** the shared generator used os.execv on both
   Windows and POSIX. Windows process creation does not provide the client-facing
   POSIX replacement/lifetime contract. Direct module self-test also skipped the
   activated stable bootstrap. Fixed in installer source, delivered helper,
   upgrade ownership transaction and postactivation rollback-aware probe. The
   generator affects mcp, command and auto modes. Existing core-only kit launchers
   remain separate. Native Windows tests exercise the actual generated process,
   stdio handshake and lifecycle, not an os.name mock. This identifies the source
   defect; it does not claim to have reproduced the owner's precise host failure.
2. **Code Mode:** the previous MCP exposed only four retrieval/instruction tools,
   while templates required scan/semantic/queue operations and implicitly relied
   on external filesystem/process access. Added eight actual backend capabilities
   and explicitly enabled Code Mode. Audited the real pinned 2.4.0 API: lazy MCP
   tools are absent from early plugin tool.list; plugin mcp.resource does not
   exist; denied MCP tools can be omitted from Code Mode search. The solution
   uses installed backend preflight plus actual per-agent search/capabilities
   and native host permission assertions. Tests exercise official OpenCode's
   actual execute/search and MCP transport with a controlled inference fixture.
3. **Windows nested Git:** project resolution used subprocess.run with inherited
   named-pipe stdin. Switched to the existing bounded git_process helper with
   DEVNULL stdin; source/Git integrity checks remain mandatory.
4. **Early global scan stop:** old auto_init stopped on any blocked coverage row
   even when remaining_files was positive. Raw 307-file baseline confirms one
   chunk, four failed files, 203 remaining, no queued candidates. New helper
   continues all independent chunks and reports terminal gaps with nonzero exit.
5. **Generic source reading:** old inventory decoded every file as UTF-8 and
   rejected a prefix over the single size limit with a combined generic error.
   It offered no explicit legacy decoding policy or bounded structured preview.
   Source_reader now preserves complete original hashes, strict supported
   encoding decisions, per-path errors, explicit policy and partial byte regions.
6. **Queue cost:** full scan candidate insertion repeatedly read/decoded the
   entire queue. A transaction-local semantic index removes that repeated scan;
   it preserves human dispositions, owned plans, refresh links and semantic
   receipts. No persistent schema/index migration or weaker source cache.

The previous TEMP 8.3/provider path fix is preserved, including identity checks,
path rejection details and full installer log location. No source path validation
was disabled. Owner provider misconfiguration was acknowledged as user error;
this task adds safeguards and does not claim hidden corruption.

## Implementation map and state compatibility

| Area | Files / behavior |
|---|---|
| Install/launch | installer/knowledge_install.py, installer/windows_process.py; scripts/build_p4.py delivers helper and wheel; transaction probes actual bootstrap before discarding rollback journal |
| Source | source_reader.py; discovery.py inventory, strict bounded read, physical coverage, negative-proof gaps and candidate batching |
| Durable worker | auto_init.py and scan_jobs.py: automatic progression, versioned checksummed checkpoint, compact progress, sharing-safe Windows metadata, explicit recovery/cancel, inherited writer lease |
| Backend | project_commands.py and machine_mcp.py: actual scan/diagnostics/source/semantic/queue/plan/CR APIs, active root, finite pages/budgets |
| Provider authority | providers.py and store.py: explicit test opt-in, no synthetic CONFIRMED semantic claims, atomic provider receipt, current provider validation at prepare/apply/precommit |
| Host/templates | host/machine_opencode.mjs and four command templates: 2.4.0 Code Mode, actual catalog paths, permission checks, bounded status observations |
| Verification | new core_wire.py, test_core_bootstrap.py, test_core_reliability.py; existing machine tests and installer/native trials; source-bound Linux/native Windows workflows |
| Documentation | CORE-RELIABILITY.md, local Knowledge-IPM-Integration-Validation.md, installation RU and README links |

See changed-files.json for exact Git paths and change types. Knowledge remains
standalone: the owned Windows helper uses only stdlib and imports no Harness.
Product package version stays 0.5.0rc1; source identity/hash distinguishes this
delivery, including same-version updates. SQLite format knowledge-sqlite-v1,
extension, pending queue, plans, decisions, canonical IDs/revisions/history, CR
sessions and existing APIs are retained. No destructive or automatic migration.
Semantic provider and partial capture ownership receipts are additive metadata
within existing transactions. Ordinary retrieval validates receipt shape without
contacting the provider. Applying source/provider drifted plans fails closed.

New reader/policy identity deliberately invalidates incompatible old scan reuse.
Resume requires current project/source/scope/base/head/provider/release bindings.
Fresh starts a new execution; unchanged normal rerun can retain its scan ID.
Version 1 helper checkpoints remain readable with old root/scope checks; version
2 adds checksum. Corruption is never silently converted into compatible state.
Explicit observed_scan_id recovery is available only after durable scan
observation and current snapshot/scope validation. No SQLite repair instructions.

## Verification history, including failures

* Baseline full unit suite: 424 tests, 413 passed, 11 native-Windows skips on
  Linux. Raw baseline/regressions.log; original code f1fc690735.
* Initial local editable-package full run failed two installed-prefix assertions;
  another test observed changing code while subprocesses imported it. These are
  retained in regressions-attempt-1.log and do not establish a passing installed
  product. Later qualification installs an immutable wheel outside the checkout.
* Source 1f5649139a: Linux full 445 tests passed (13 native-Windows skips), all
  28 qualification commands passed. Windows 444/445 passed, one error: unsafe
  hardlink was refused before access but the new inventory did not turn that
  refusal into a durable file gap. Fixed without allowing the hardlink read.
* Same source: actual Windows machine tests 44/44 passed, including forced outer
  launcher termination/owned child cleanup, unrelated process survival and scan
  breakaway. Installer trial then failed a raw-CRLF vs normalized-wheel test
  expectation; the actual source byte update was installed. Corrected expected
  LF hash to match the existing reproducible wheel builder.
* Source 6900383fb0 local full attempt initially lacked a discoverable .NET SDK in
  its isolated worktree. Failed before full regressions with
  recipe-executable-must-be-absolute. Existing SDK and cached packages were then
  made available; no recipe safety check was weakened.
* Its local fast native trial exposed a test observation race: global commands
  appeared before the async MCP catalog populated. Initial empty catalog caused
  StopIteration. Source 00e4368ef2 observes catalog connection within the same
  existing finite deadline; no simulated pass or registration shortcut.
* Early native API/fixture investigation attempts are retained under attempt-*.
  They include unsupported plugin APIs, asynchronous fixture ordering and the
  verified behavior that denied tools are absent from search. These attempts
  are not promoted to final-source acceptance.

Subsequent native Windows testing confirmed an additional product defect:
isolated detached scan workers ignored PYTHONUTF8/PYTHONIOENCODING and could
fail logging Unicode paths under the Windows locale. f8a665bf adds explicit
`-X utf8` and a real worker regression. Windows then passed all 450 tests.
Its upgrade trial stopped while preparing the archived old installer, itself
invoked with `-I` without UTF-8; 9eef0842 corrects only that fixture invocation.
All delivered product asset hashes remain identical (product-equivalence.json).

The f8 full Linux CI route passed its unit regressions but failed a legacy
audit-stage trial's broad `'999' not in canonical_json(knowledge)` assertion.
This trial passed in the complete local installed route. A transient/collision
explanation is not proven by the retained traceback; the CI route remains
reported as failed, without relabelling it an environmental failure or silently
weakening the assertion. Source-bound raw evidence is retained in ci/f8-full.

CI data is copied and checked by collect_ci.py: source blobs vs requested Git
tree, manifest identity, every command log hash, every release asset hash,
unchanged inputs and zero return codes for passing runs. Artifact code is not
executed while collecting evidence. Git evidence refs are transport because
GitHub's API is unavailable in this workspace; receipts retain actual Actions
URLs and workflow revisions. Final status never rests on branch-name similarity.

## Performance interpretation and remaining limits

Raw equivalent before/after workloads and microtimings are in benchmarks/.
PERFORMANCE.md separates equal completed work from the intentionally failing
baseline. The original measured data is committed, including ignored benchmark
paths explicitly. Parent tracemalloc excludes child memory; Linux child RSS is
reported separately. Timings are synthetic on a shared Linux host and cannot
establish IPM production latency or semantic quality.

Limits remain explicit: lexical C# extraction, content inventory for other
formats, no YAML grammar validation, bounded oversized previews rather than full
structure understanding, no model/network validation by preflight. Full raw
hashing has bounded memory but I/O proportional to eligible source bytes and is
repeated to preserve identity. The repository inventory is still whole-snapshot
per chunk; extraction is bounded per chunk. No claim of constant-time snapshots,
complete business understanding, production provider quality, native macOS or
owner Windows acceptance is made. Local IPM installation, policy selection,
provider validation, semantic reconciliation and real performance are delegated
only in the separate local handoff; core implementation work is not delegated.

Installation/upgrade/backup/rollback and all actual schemas/commands are in
the delivered docs. Neither source implementation nor this report changed the
owner's Windows runtime, real provider/OpenCode configuration, IPM source or DB.

Final source 9eef0842 native machine CI passed on Windows and Linux. The archived-installer UTF-8 fixture correction was verified by the actual upgrade trial, and real OpenCode 2.4.0 Code Mode/permissions passed on both platforms. See ci/final-machine.
