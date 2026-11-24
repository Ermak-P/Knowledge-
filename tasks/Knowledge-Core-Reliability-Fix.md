# Knowledge-Core-Reliability-Fix

## 1. Objective

Investigate and fix production-blocking reliability issues in the Knowledge project discovered during real-world usage on Windows with OpenCode and a large .NET repository.

Knowledge must provide:

- Reliable Windows MCP server startup.
- Compatibility with OpenCode Code Mode.
- Reliable scanning of large repositories.
- Recovery from individual file extraction failures.
- Accurate coverage accounting.
- Support for multiple source encodings.
- Bounded processing of large files.
- Configurable exclusion policies.
- Automatic chunk progression.
- Durable checkpoints and resumable execution.
- Safe semantic reconciliation and knowledge retirement.

Implement generic improvements in the Knowledge core.

Knowledge is an independent, reusable product. Do not introduce IPM-specific behavior or dependencies.

## 2. Scope and responsibility

This task is assigned to Codex working on the Knowledge source repository.

Your responsibilities include:

- Source code investigation.
- Root cause analysis.
- Implementation.
- Installer improvements.
- Automated regression testing.
- Compatibility verification.
- Documentation.
- Migration and rollback procedures.
- Preparation of a local integration validation checklist.

The following activities are outside the scope of this task and will be performed by a separate local agent:

- Updating the actual Knowledge installation on the user's Windows machine.
- Modifying local OpenCode configuration.
- Configuring the production inference provider.
- Inspecting individual IPM source files.
- Configuring IPM-specific exclusion policies.
- Running the complete production scan against IPM.
- Measuring production scan performance on the user's hardware.

Do not attempt to modify the user's local installation or IPM repository.

Do not block implementation merely because the production environment is unavailable.

## 3. Observed failures

### 3.1. Windows MCP server startup failure

Previously observed error:

```text
MCP server: knowledge_machine
Status: failed
Configuration: mcp.servers.knowledge_machine
Error: Connection closed: MCP server process exited with code 0
```

A likely root cause was identified in the generated Python bootstrap launcher.

The Windows launcher uses `os.execv()`, which may not preserve the process lifecycle expected by the MCP stdio client on Windows.

The recommended fix is described in Section 4.

### 3.2. OpenCode Code Mode incompatibility

Observed errors and capability gaps:

```text
Cannot import "fs": this runtime doesn't provide it.
```

Additional limitations:

- `child_process` is unavailable.
- Direct `fetch` is forbidden.
- Required Knowledge backend tools are missing from the available tool catalog.
- The agent cannot invoke supported scan recovery and candidate submission operations.
- The agent cannot access scan diagnostics through the required backend interfaces.

Do not assume that all these issues have the same root cause.

Investigate the Windows launcher first, then determine which integration problems remain.

### 3.3. Full repository scan failure

A production repository scan returned the following diagnostics:

| Property | Value |
|---|---|
| Scope | full |
| Total inventory | 38,318 files |
| First chunk | 100 files |
| Blocked files | 29 |
| Remaining files | 38,218 |
| Terminal state | BLOCKED |
| Semantic reconciliation | null |
| Queued candidates | 0 |

Error:

```text
Coverage is blocked. See coverage-errors.json
```

All blocked files were reported with the same ambiguous reason:

```text
unreadable, non-UTF8 or oversized source
```

Affected file categories included:

- XML configuration files.
- XML and JSON test fixtures.
- Toolchain evidence JSON files.
- Generated dependency graph artifacts.
- Kubernetes CRD YAML files.
- Agent session Markdown logs.

The entire repository scan stopped after encountering problematic files in the first chunk.

The remaining repository was not processed.

Use these observations to reproduce the failure using representative synthetic fixtures. The actual IPM files are not required for core implementation.

### 3.4. Provider configuration clarification

The observed `controlled-demo` test-double provider was caused by an acknowledged user configuration mistake.

This is not a confirmed Knowledge implementation defect.

Do not investigate hypothetical installer corruption or provider configuration replacement based on this observation.

Production provider configuration will be corrected separately by the user.

Only implement or verify preventive safeguards against accidental test-double usage.

## 4. P0 — Fix Windows bootstrap launcher

### 4.1. Implementation location

Inspect the `BOOTSTRAP` generator in:

```text
installer/knowledge_install.py
```

Implement the permanent fix in the installer source.

Do not limit the fix to manually patching an already generated launcher.

Identify all launchers generated from this bootstrap and determine whether they share the same issue.

### 4.2. Recommended implementation

Use the following implementation as the baseline:

```python
command = args + sys.argv[2:]

if os.name == "nt":
    import subprocess

    raise SystemExit(
        subprocess.call(command, shell=False)
    )

os.execv(str(python), command)
```

Adapt this implementation to the existing bootstrap structure.

Validate executable selection, argument forwarding, and runtime resolution before applying the change.

Ensure that `args` and `sys.argv[2:]` preserve the intended arguments without losing or duplicating them.

### 4.3. Required Windows behavior

The generated launcher must:

- Start the actual Knowledge runtime as a child process.
- Inherit stdin, stdout, and stderr.
- Preserve MCP stdio transport.
- Remain alive until the child process terminates.
- Propagate the actual child process exit code.
- Avoid unnecessary shell invocation.
- Preserve paths and arguments containing spaces and Unicode characters.
- Report startup failures correctly.

Preserve existing non-Windows process replacement behavior unless a separate verified defect requires a change.

### 4.4. MCP protocol integrity

The launcher must not:

- Consume or modify MCP protocol messages.
- Introduce unnecessary buffering.
- Write diagnostic messages to protocol stdout.
- Return exit code zero when the child process has failed.
- Terminate prematurely while the MCP server remains active.

Diagnostic messages must be written to stderr.

### 4.5. Process lifecycle management

Investigate the behavior of:

- Normal child termination.
- Child startup failure.
- Nonzero child exit codes.
- MCP client disconnect.
- Parent launcher termination.
- Cancellation and interruption.
- Repeated server startup and shutdown.
- Potential orphaned child processes.
- Potential duplicate MCP processes.

The recommended `subprocess.call()` implementation provides synchronous waiting and exit-code propagation.

It does not automatically guarantee child cleanup when the parent launcher is forcibly terminated.

If additional lifecycle management is necessary, implement the smallest reliable solution supported by the existing architecture.

Do not terminate unrelated Python processes, other Knowledge instances, or shared inference servers.

Distinguish MCP server child processes from intentionally detached scan workers.

Do not accidentally terminate legitimate background scan workers when an MCP session closes.

### 4.6. Installer and upgrade compatibility

Ensure that:

- Fresh installations generate the corrected bootstrap.
- Existing installations receive the corrected bootstrap during upgrade.
- All affected launchers are updated.
- Existing runtime configuration is preserved.
- Existing provider configuration is preserved.
- Existing project databases are preserved.
- Existing knowledge stores and pending candidates are preserved.
- Linux and macOS behavior remains compatible.
- Users do not need to manually patch generated launchers.

### 4.7. Required tests

Add automated tests covering:

- Windows bootstrap generation.
- Non-Windows bootstrap generation.
- Runtime executable selection.
- Argument forwarding.
- Paths containing spaces.
- Unicode paths and arguments.
- stdin inheritance.
- stdout inheritance.
- stderr inheritance.
- Parent waiting for child termination.
- Successful exit-code propagation.
- Nonzero exit-code propagation.
- Child startup failure.
- MCP initialization handshake.
- MCP tool discovery.
- MCP shutdown.
- Repeated startup and shutdown.
- Process cleanup.
- Upgrade of an existing generated launcher.

Run actual Windows tests if a Windows execution environment is available.

Otherwise, provide automated Windows-specific tests that can be executed by the local agent and mark actual Windows runtime validation as `UNVERIFIED`.

Do not treat mocked Windows behavior as proof of production compatibility.

## 5. P0 — Fix OpenCode Code Mode integration

### 5.1. Root cause investigation

Inspect:

- MCP server registration.
- MCP tool discovery.
- Tool exposure.
- Knowledge command definitions.
- OpenCode integration mechanisms.
- Runtime compatibility.
- Backend invocation mechanisms.
- Permission requirements.
- Error propagation.

Determine whether the Windows bootstrap issue contributes to the missing MCP capabilities.

Do not assume that fixing the launcher resolves every integration problem.

### 5.2. Command compatibility audit

Audit all existing Knowledge commands.

Include the following commands where present in the current implementation:

- `/knowledge-init`
- `/knowledge-candidates-append`
- `/knowledge-candidates-update`
- `/knowledge-candidates-push`
- `/knowledge-update`
- `/update-by-CR`

Discover the actual current command inventory before making changes.

Do not recreate removed commands or introduce duplicate command definitions.

Ensure that every command references actual registered and supported backend capabilities.

### 5.3. Required backend capabilities

Verify that the supported integration exposes the capabilities required to:

- Start a full scan.
- Retrieve scan status.
- Retrieve scan diagnostics.
- Retrieve coverage information.
- Resume an interrupted scan.
- Start a fresh scan.
- Cancel a running scan.
- Retrieve semantic reconciliation status.
- Submit source-bound candidates.
- Review candidate application plans.
- Perform explicitly approved knowledge mutations.

Reuse existing tools and APIs wherever possible.

If a required capability is genuinely missing, implement it using the existing architecture.

Do not expose unnecessary low-level filesystem or database APIs.

### 5.4. Unsupported runtime capabilities

Knowledge commands must not require unsupported Code Mode capabilities such as:

- Node.js `fs`.
- Node.js `child_process`.
- Direct network requests using `fetch`.
- Direct SQLite access.
- Shell execution as a mandatory fallback.

Filesystem access, database operations, provider communication, and worker process management must remain inside the appropriate Knowledge backend.

Do not bypass OpenCode permissions or Knowledge approval mechanisms.

### 5.5. Capability preflight

Before starting an operation, verify that all required backend capabilities are available.

If a required capability is unavailable:

- Return a specific actionable diagnostic.
- Identify the missing capability.
- Distinguish registration failure from permission denial.
- Avoid starting an operation that cannot be safely completed.
- Avoid repeated attempts without a relevant environment change.

Do not silently degrade into an unsupported execution path.

## 6. P0 — Fix coverage failure handling

### 6.1. Required behavior

A recoverable file-level extraction failure must not terminate repository-wide scanning.

Distinguish between:

- Recoverable file-level failures.
- Explicit policy exclusions.
- Temporary infrastructure failures.
- Fatal infrastructure failures.
- Integrity violations.

Continue scanning remaining eligible files after recoverable file-level failures.

Fatal failures may terminate execution when continuing would compromise integrity or produce unreliable results.

Do not merely replace the `BLOCKED` status with `COMPLETED`.

Fix the underlying processing and coverage behavior.

### 6.2. Coverage accounting

Maintain accurate and internally consistent coverage counters for:

- Discovered files.
- Eligible files.
- Policy-excluded files.
- Successfully processed files.
- Partially processed files.
- Failed files.
- Remaining files.
- Pending retries.

Define the relationship between these counters.

Prevent double-counting across chunks, retries, and resumed executions.

A file must not be classified as fully processed if extraction was incomplete.

### 6.3. Final scan status

Review the existing scan state machine.

Ensure that it can distinguish:

- Scan in progress.
- Scan interrupted.
- Scan completed successfully.
- Scan completed with unresolved coverage failures.
- Scan blocked by fatal errors.
- Scan cancelled.

Reuse existing states where their semantics are sufficient.

Introduce new states only if required.

A scan that has processed all available eligible files but still contains unresolved required-file failures must accurately report incomplete coverage.

### 6.4. Reconciliation and retirement safety

Preserve all existing fail-closed safeguards.

In particular:

- Incomplete coverage is not evidence that existing knowledge is obsolete.
- An unreadable source is not evidence that a previously confirmed claim is false.
- A policy exclusion is not proof of source deletion.
- Partial extraction is not proof of complete source analysis.
- Lexical extraction is not proof of semantic understanding.
- A successful inventory is not proof of successful reconciliation.

Allow safe collection of evidence from successfully analyzed sources without weakening retirement safeguards.

Do not automatically mutate canonical knowledge.

## 7. P1 — Improve file-level diagnostics

Replace the ambiguous diagnostic:

```text
unreadable, non-UTF8 or oversized source
```

with specific machine-readable reasons.

Suggested reason codes:

- `UNREADABLE`
- `ACCESS_DENIED`
- `UNSUPPORTED_ENCODING`
- `INVALID_ENCODING`
- `FILE_TOO_LARGE`
- `EXTRACTION_FAILED`
- `FILE_CHANGED_DURING_SCAN`
- `PARTIAL_EXTRACTION`
- `EXCLUDED_BY_POLICY`
- `EXCLUDED_GENERATED`
- `EXCLUDED_BINARY`

Adapt these codes to the existing diagnostic architecture.

For each failed or excluded file, record relevant information:

- Repository-relative path.
- File size.
- Detected encoding, when available.
- Applicable size limit.
- Extraction stage.
- Failure or exclusion reason.
- Retry eligibility.
- Applicable exclusion rule.
- Original exception information, when appropriate.

Do not expose credentials, secrets, or unnecessary source content.

Ensure diagnostics are available through supported backend interfaces.

Preserve existing diagnostic compatibility where practical.

Avoid requiring the agent to manually inspect internal state directories to understand why an operation failed.

## 8. P1 — Improve encoding support

Review the current source-reading implementation.

Implement or verify support for:

- UTF-8 without BOM.
- UTF-8 with BOM.
- UTF-16 LE.
- UTF-16 BE.
- XML encoding declarations.
- Configurable legacy encodings, including Windows-1251.

Use deterministic encoding detection where possible.

Prefer a fast path for normal UTF-8 source files.

Requirements:

- Never silently discard undecodable bytes.
- Never silently replace invalid source content.
- Never silently reinterpret binary files as text.
- Preserve source-bound evidence and source locations.
- Preserve original source identity.
- Report unsupported or ambiguous encodings explicitly.
- Avoid expensive encoding detection for every file.

Legacy encoding fallback must be controlled by explicit policy or reliable format-specific metadata.

Do not indiscriminately attempt Windows-1251 decoding after every UTF-8 failure.

Do not modify repository source files to accommodate Knowledge.

Add regression fixtures representing mixed-encoding repositories.

## 9. P1 — Improve large-file processing

Inspect existing extraction limits and resource management.

Investigate whether large structured files can be processed safely without loading their entire contents into memory or submitting excessively large inference requests.

Consider:

- Streaming extraction.
- Structure-aware JSON processing.
- Structure-aware XML processing.
- Structure-aware YAML processing.
- Bounded chunking.
- Incremental hashing.
- Configurable per-file limits.
- Configurable per-format limits.
- Truncation detection.
- Source-bound evidence preservation.

Do not simply increase the global file size limit.

Implement an approach appropriate to the existing architecture and supported formats.

Ensure that:

- Memory consumption remains bounded.
- Inference requests remain within configured context budgets.
- Oversized files cannot destabilize the scan worker.
- Partial extraction is explicitly recorded.
- Unprocessed source regions are not treated as analyzed.
- Invalid structured files produce actionable diagnostics.

Use safe parsers and disable unnecessary external resource resolution.

Avoid introducing unnecessary dependencies.

## 10. P1 — Implement configurable exclusion policies

### 10.1. Existing mechanisms

Inspect existing inventory filters, ignore rules, source classification, and project configuration before implementing new mechanisms.

Reuse existing exclusion mechanisms where appropriate.

Do not introduce overlapping configuration systems.

### 10.2. Required behavior

Support explicit project-level exclusion policies and conservative defaults for non-source artifacts.

Potential exclusion categories include:

- Generated reports.
- Generated dependency graphs.
- Build outputs.
- Caches.
- Agent session logs.
- Temporary files.
- Tool-generated evidence artifacts.
- Vendored or generated large structured files.

These categories are examples, not mandatory unconditional exclusions.

Do not hardcode IPM-specific paths into Knowledge core.

Do not automatically exclude entire source categories such as:

- XML.
- JSON.
- YAML.
- Documentation.
- Test data.
- Infrastructure configuration.

These sources may contain important architectural and operational knowledge.

### 10.3. Exclusion safety

Ensure that:

- Every exclusion has an explicit reason.
- Applicable rules are visible in diagnostics.
- Excluded files are not classified as extraction failures.
- Exclusion policies are deterministic.
- Exclusion policies participate in snapshot compatibility checks.
- Project-specific exclusions can be configured without modifying Knowledge core.
- Previously analyzed but newly excluded files cannot silently trigger unsafe knowledge retirement.

Document rule precedence, matching behavior, defaults, and project-level overrides.

Provide configuration examples that the local agent can adapt to IPM.

## 11. P1 — Automatic chunk progression and resumable scanning

### 11.1. Chunk processing

Determine whether `max_files: 100` currently represents:

- A per-chunk processing limit.
- A per-invocation limit.
- An unintended total scan limit.

A full scan must automatically progress through all eligible chunks.

The agent must not manually initiate processing of every chunk.

Ensure that recoverable failures in one chunk do not prevent subsequent chunks from being processed.

### 11.2. Durable checkpoints

Ensure that:

- Scan progress is persisted durably.
- Worker interruption does not lose committed progress.
- OpenCode restarts do not invalidate compatible checkpoints.
- Resume does not duplicate committed extraction results.
- Resume does not duplicate candidates.
- Recoverable failures can be retried independently.
- Unaffected files are not unnecessarily rescanned.
- Checkpoint updates are atomic or recoverable.
- Corrupt checkpoints are detected and reported.

Preserve transaction integrity.

### 11.3. Snapshot compatibility

Review compatibility checks for:

- Repository identity.
- Source inventory.
- Source fingerprints.
- Extraction configuration.
- Exclusion policies.
- Extraction implementation version.
- Semantic provider configuration.
- Semantic model identity.
- Relevant prompt or schema versions.

Do not reuse incompatible semantic results.

If an implementation or configuration change invalidates only a particular processing stage, reuse earlier results only when compatibility is explicitly established.

Do not silently combine incompatible snapshots.

### 11.4. Resume and fresh semantics

Document the exact semantics of:

```json
{"resume": true}
```

and:

```json
{"fresh": true}
```

Ensure that:

- Resume continues compatible interrupted work.
- Fresh creates a new scan execution.
- Fresh does not delete canonical knowledge.
- Fresh does not delete unrelated pending candidates.
- Incompatible resume requests return actionable diagnostics.

### 11.5. Worker lifecycle

Investigate:

- Stale worker detection.
- Launcher termination.
- Worker termination.
- Lock ownership.
- Lock recovery.
- Cancellation.
- Concurrent scan attempts.
- Recovery after interrupted checkpoint writes.

Distinguish between the MCP launcher lifecycle and the background scan worker lifecycle.

Prevent duplicate workers from processing the same scan concurrently.

Do not introduce unbounded retries or busy polling.

### 11.6. Agent context efficiency

Scanning large repositories must not require the controlling agent to accumulate thousands of repetitive status messages.

Provide compact status responses containing relevant progress information.

Avoid:

- Unbounded status polling.
- Repeated full diagnostic payloads.
- Returning complete file inventories for routine progress checks.
- Repeatedly transmitting already acknowledged information.

Do not introduce a new orchestration layer unless necessary.

## 12. P1 — Test-double provider safeguards

The observed provider configuration was a user mistake.

Implement or verify lightweight preventive validation only.

Requirements:

- Identify test-double providers before production semantic processing begins.
- Clearly report the active provider, model, and evidence type.
- Require explicit authorization for test-mode execution.
- Prevent synthetic semantic results from being classified as production-verified knowledge.
- Return actionable diagnostics for inappropriate provider configuration.
- Prevent incompatible test-double semantic results from being reused during production resume.

Do not automatically modify provider configuration.

Do not hardcode provider endpoints, model names, or credentials.

Do not break legitimate automated tests that explicitly authorize test-double execution.

Do not require external model availability for deterministic unit tests.

## 13. Preserve existing Knowledge guarantees

All changes must preserve:

- Existing canonical knowledge.
- Existing pending candidates.
- Source-bound evidence.
- Candidate deduplication.
- Conflict detection.
- Claim lifecycle semantics.
- Transaction integrity.
- Explicit approval requirements.
- Reconciliation safeguards.
- Retirement safeguards.
- Database compatibility.
- Existing infrastructure and project knowledge separation.
- Existing valid provider configuration.

Review recent changes in the repository before modifying shared components.

Pay particular attention to existing candidate update workflows, database optimizations, and infrastructure knowledge support.

Do not regress previously implemented functionality.

If a database or state migration is necessary:

- Make it backward-compatible where practical.
- Use supported migration mechanisms.
- Provide a backup procedure.
- Provide a rollback procedure.
- Test migration using representative existing databases.
- Preserve canonical knowledge and pending candidates.

Do not require users to delete existing databases or rebuild all knowledge as a normal upgrade procedure.

## 14. Automated regression testing

Add or extend automated tests for the following areas.

### 14.1. Installer and launcher

- Windows bootstrap generation.
- POSIX bootstrap behavior.
- Argument forwarding.
- Standard stream inheritance.
- Parent and child lifecycle.
- Exit-code propagation.
- MCP initialization.
- MCP tool discovery.
- Installer upgrade compatibility.

### 14.2. OpenCode integration

- Command compatibility.
- Supported backend invocation.
- MCP tool discovery.
- Missing capabilities.
- Permission-denied diagnostics.
- Scan startup.
- Status retrieval.
- Diagnostic retrieval.
- Resume.
- Cancellation.
- Candidate submission.
- Approval enforcement.

### 14.3. Source extraction

- UTF-8 with and without BOM.
- UTF-16 LE and BE.
- Windows-1251.
- XML encoding declarations.
- Invalid encodings.
- Binary files.
- Unreadable files.
- Oversized files.
- Large JSON, XML, and YAML files.
- Partial extraction.
- Generated artifact exclusions.
- Files changed during scanning.

### 14.4. Scan lifecycle

- Multiple chunks.
- Recoverable failures in the first chunk.
- Continued processing of subsequent chunks.
- Worker interruption.
- Checkpoint recovery.
- Resume without duplicate processing.
- Resume without duplicate candidates.
- Corrupt checkpoint detection.
- Snapshot changes.
- Exclusion policy changes.
- Provider compatibility changes.
- Concurrent scan attempts.
- Cancellation.

### 14.5. Knowledge integrity

- Incomplete coverage.
- Unsafe retirement prevention.
- Excluded source safety.
- Partial extraction safety.
- Unauthorized canonical mutations.
- Unauthorized test-double execution.
- Preservation of existing canonical knowledge.
- Preservation of pending candidates.
- Transaction recovery.

### 14.6. Large-repository regression fixture

Create a reproducible synthetic workload representing a large repository.

Include:

- Multiple file formats.
- Mixed encodings.
- Generated artifacts.
- Oversized files.
- Recoverable extraction failures.
- Multiple scan chunks.

Reproduce the original failure pattern:

- A scan contains problematic files in its first chunk.
- The first chunk reports specific failures.
- Remaining eligible files continue to be processed.
- Final coverage accurately identifies unresolved failures.
- Unsafe reconciliation and retirement remain blocked.

The test must demonstrate actual processing of subsequent chunks, not merely a changed terminal status.

Use deterministic fixtures without requiring access to IPM or a production inference provider.

## 15. Performance and resource validation

Knowledge must remain suitable for large repositories.

Measure applicable metrics using equivalent before-and-after synthetic workloads:

- MCP startup duration.
- Bootstrap overhead.
- Inventory duration.
- Extraction throughput.
- Processing time per chunk.
- Peak memory consumption.
- Encoding detection overhead.
- Large-file processing overhead.
- Checkpoint overhead.
- Resume overhead.
- Database operation duration.
- MCP call count.
- Total scan duration.

Use reproducible benchmark procedures.

Document the environment and workload.

Investigate significant regressions.

Do not sacrifice evidence integrity, correctness, or recovery guarantees merely to improve throughput.

Do not claim production performance improvements based exclusively on synthetic measurements.

Actual IPM performance validation will be performed by the local agent.

## 16. Documentation and local validation handoff

Update relevant Knowledge documentation.

Document:

- Windows launcher behavior.
- OpenCode integration requirements.
- Supported MCP capabilities.
- Scan state semantics.
- Coverage counters.
- Diagnostic reason codes.
- Supported source encodings.
- Legacy encoding configuration.
- Large-file processing limits.
- Exclusion policy configuration.
- Resume and fresh behavior.
- Checkpoint compatibility.
- Test-double safeguards.
- Installation and upgrade procedures.
- Migration procedures.
- Rollback procedures.

Prepare a separate handoff document:

```text
Knowledge-IPM-Integration-Validation.md
```

This document will be executed by the local agent in the actual Windows environment.

It must contain:

1. Exact instructions for updating the installed Knowledge version.
2. Backup and rollback instructions.
3. Instructions for verifying that the generated Windows bootstrap contains the corrected behavior.
4. Instructions for verifying MCP startup and tool discovery in OpenCode.
5. Instructions for verifying available Code Mode capabilities.
6. Instructions for collecting precise diagnostics for the previously blocked files.
7. Examples of project-specific exclusion configuration.
8. Instructions for validating the corrected production provider.
9. Instructions for starting a fresh production scan.
10. Instructions for monitoring automatic chunk progression.
11. Instructions for verifying checkpoint and resume behavior.
12. Instructions for validating semantic reconciliation.
13. Instructions for validating source-bound candidate generation.
14. Instructions for verifying preservation of existing canonical knowledge and pending candidates.
15. Instructions for measuring real production performance.
16. Explicit acceptance criteria.
17. Instructions for reporting newly discovered core defects back to Codex.

Use the actual implemented commands, configuration schemas, and diagnostic interfaces in the handoff document.

Do not invent commands that are not supported by the implementation.

The handoff must not require the local agent to patch Knowledge core or directly edit SQLite databases.

## 17. Acceptance criteria

### Windows launcher

- [ ] Permanent fix implemented in `installer/knowledge_install.py`.
- [ ] Windows launchers preserve stdin, stdout, and stderr.
- [ ] Windows parent launcher waits for child termination.
- [ ] Actual child exit codes are propagated.
- [ ] MCP protocol stdout remains clean.
- [ ] Argument forwarding is correct.
- [ ] Process lifecycle risks are addressed.
- [ ] Existing installations receive corrected launchers through supported upgrade procedures.
- [ ] Non-Windows behavior remains compatible.

### OpenCode integration

- [ ] Existing commands reference supported backend interfaces.
- [ ] Required MCP capabilities are implemented and exposed.
- [ ] Unsupported Code Mode APIs are not mandatory.
- [ ] Missing capabilities produce actionable diagnostics.
- [ ] Existing permission and approval mechanisms are preserved.

### Coverage and extraction

- [ ] Recoverable file failures do not terminate repository-wide scanning.
- [ ] Subsequent chunks are actually processed after failures.
- [ ] Coverage counters are accurate and consistent.
- [ ] Failed, partial, and excluded files are distinguished.
- [ ] File-level diagnostics identify specific reasons.
- [ ] Supported encodings are processed correctly.
- [ ] Large-file processing uses bounded resources.
- [ ] Configurable exclusion policies are supported.

### Scan lifecycle

- [ ] Full scans automatically advance through eligible chunks.
- [ ] Compatible checkpoints survive interruption.
- [ ] Resume avoids duplicate processing and candidates.
- [ ] Snapshot compatibility is enforced.
- [ ] Provider compatibility is enforced.
- [ ] Concurrent execution and stale locks are handled safely.
- [ ] Status polling remains bounded and context-efficient.

### Knowledge integrity

- [ ] Incomplete coverage cannot cause unsafe knowledge retirement.
- [ ] Partial extraction cannot be misrepresented as complete.
- [ ] Test-double results cannot silently become production-verified knowledge.
- [ ] Existing canonical knowledge is preserved.
- [ ] Existing pending candidates are preserved.
- [ ] Approval safeguards are preserved.
- [ ] Existing database compatibility is preserved.
- [ ] Previously implemented Knowledge functionality is not regressed.

### Deliverables and validation

- [ ] Automated regression tests pass.
- [ ] Large-repository regression fixture passes.
- [ ] Performance measurements are documented.
- [ ] Upgrade and rollback procedures are documented.
- [ ] Local integration validation handoff is complete.
- [ ] Actual Windows validation status is explicitly reported.
- [ ] Production IPM validation is explicitly delegated to the local agent.

## 18. Required deliverables

Provide:

1. Root cause analysis.
2. Implemented source code changes.
3. Changed-file inventory.
4. Windows bootstrap implementation report.
5. Windows lifecycle and MCP stdio verification report.
6. OpenCode command and capability audit.
7. Automated regression tests and results.
8. Before-and-after synthetic coverage diagnostics.
9. Encoding support documentation.
10. Large-file processing documentation.
11. Exclusion policy configuration examples.
12. Checkpoint and resume verification report.
13. Performance comparison.
14. Database and state compatibility report.
15. Upgrade and migration instructions.
16. Rollback instructions.
17. `Knowledge-IPM-Integration-Validation.md`.
18. Remaining limitations and unresolved issues.
19. Final implementation and validation verdicts.

## 19. Execution phases

### Phase 0 — Baseline and architecture audit

- Inspect the current repository.
- Review recent implementation changes.
- Discover existing commands and backend capabilities.
- Establish regression test baseline.
- Identify reusable mechanisms.
- Confirm root causes where possible.

### Phase 1 — Windows launcher reliability

- Fix the bootstrap generator.
- Verify argument forwarding and stdio behavior.
- Address process lifecycle issues.
- Verify installer and upgrade compatibility.
- Add regression tests.

### Phase 2 — OpenCode integration

- Audit MCP registration and tool exposure.
- Verify command compatibility.
- Remove mandatory dependencies on unsupported Code Mode APIs.
- Implement missing capabilities only where necessary.
- Add capability preflight diagnostics.

### Phase 3 — Coverage and diagnostics

- Fix recoverable file-level failure handling.
- Introduce specific diagnostic reasons.
- Verify coverage accounting.
- Preserve reconciliation and retirement safety.

### Phase 4 — Source extraction and exclusion policies

- Improve encoding support.
- Improve bounded large-file processing.
- Implement or extend configurable exclusion policies.
- Add regression fixtures.

### Phase 5 — Scan lifecycle and provider safeguards

- Verify automatic chunk progression.
- Improve checkpoint durability where necessary.
- Verify resume and fresh semantics.
- Verify snapshot and provider compatibility.
- Implement test-double safeguards.

### Phase 6 — Regression and performance validation

- Run the complete regression test suite.
- Run large-repository synthetic workloads.
- Compare performance and resource consumption.
- Verify upgrade and migration safety.
- Investigate regressions.

### Phase 7 — Documentation and handoff

- Update documentation.
- Prepare local validation instructions.
- Document remaining limitations.
- Produce final implementation and validation verdicts.

## 20. Verdict rules

Report separate verdicts for:

| Validation area | Allowed verdicts |
|---|---|
| Core implementation | GO / PARTIAL / NO-GO |
| Automated regression tests | PASS / FAIL / NOT_RUN |
| Windows runtime integration | PASS / FAIL / UNVERIFIED |
| OpenCode runtime integration | PASS / FAIL / UNVERIFIED |
| Installer upgrade compatibility | PASS / FAIL / UNVERIFIED |
| Production IPM validation | DELEGATED / UNVERIFIED |

A successful core implementation does not require access to the user's production environment.

If all core implementation acceptance criteria are satisfied and automated tests pass, the implementation may receive `GO` for local deployment validation.

Do not declare production readiness until the required local integration checks have been completed.

Clearly distinguish:

- Implementation completeness.
- Automated verification.
- Platform-specific runtime verification.
- Production environment verification.

## 21. Execution rules

- Inspect the existing implementation before making changes.
- Reuse existing mechanisms wherever appropriate.
- Implement actual fixes, not merely a diagnostic report.
- Avoid unrelated refactoring.
- Avoid unnecessary dependencies.
- Keep Knowledge independent of IPM and Agent Harness.
- Do not introduce IPM-specific paths into Knowledge core.
- Do not modify the user's local installation.
- Do not modify IPM source files.
- Do not weaken existing safety guarantees.
- Do not bypass existing approvals.
- Do not silently suppress coverage failures.
- Do not indiscriminately exclude problematic files.
- Do not treat synthetic provider output as production evidence.
- Do not fabricate test results or performance measurements.
- Do not consider mocked Windows behavior sufficient for production Windows acceptance.
- Report environmental blockers separately from implementation defects.
- Do not leave required core implementation work to the local agent.
- Complete all feasible phases within this task.

Proceed with source investigation, implementation, regression testing, performance validation, documentation, and preparation of the local integration handoff.