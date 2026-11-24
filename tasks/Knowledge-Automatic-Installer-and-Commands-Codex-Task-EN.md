# Agent Task: Automatic Installation and Updates for Knowledge MCP

Repository: https://github.com/Ermak-P/Knowledge-

Implement installation and updates for standalone Knowledge MCP with a single user-supplied parameter: the installation directory. Individual projects must be configured later through `/knowledge-init`, invoked from that project's workspace. Provider configuration must be stored and resolved centrally for all connected projects.

Deliver a working implementation with verification and documentation, rather than only a plan or new Markdown instructions. Preserve Knowledge's independence and compatibility with the installed Harness. Work against the current checkout and its AGENTS.md; access to the owner's computer or `C:\Git\IPM` must not be assumed.

## 1. Supplied Materials

Use the attached files as source material:

| File | Purpose |
|---|---|
| `knowledge-init-auto(1).py` | Automatic scanning loop, helper version 1.1; include it in the product as `knowledge-init-auto.py` |
| `knowledge-init(1).md` | Requirements for comprehensive project inspection and knowledge reconciliation |
| `knowledge-candidates-update(2).md` | Requirements for collecting and queuing candidates |
| `knowledge-candidates-push(1).md` | Separation between plan preparation and application after exact approval |

The Markdown sections referring to `.ai`, `.harness/knowledge/candidates/queue.jsonl`, `append_candidates.py`, and a fixed IPM checkout describe a historical implementation. Adapt the intent of those requirements to the actual APIs of standalone Knowledge. Do not restore the obsolete architecture or blindly copy historical invocations. Handle an existing project with legacy `.ai` separately through the supported migration contract, without a hidden migration or a second competing database.

## 2. Required User Workflow

### 2.1. Machine Installation

After obtaining the source, the user runs a single command from `Knowledge-Source`, for example:

```powershell
Set-Location 'C:\Temp\Knowledge-Source'
.\install.ps1 -McpDir 'C:\LLM\mcp\knowledge'
```

This is the target interface to implement. The current `install.py --env` interface may remain as an internal mechanism and a compatible low-level interface.

The only required parameter of the new user interface is `McpDir`. Prompting for that same path when launched without an argument is acceptable. For normal first-time installation and updates, do not ask for a project root, provider, Python, profile, wheel, source path, scan ID, SDK, or template paths. Additional diagnostic or recovery parameters may be optional.

The file source is the root of the local `Knowledge-Source` distribution or checkout. The directory name is arbitrary, including `Knowledge--main` or `Konwledge-Source`; do not locate it by its literal name. Anchor the source root to the launcher's location (`$PSScriptRoot` or equivalent), validate its structure, and do not substitute an unrelated current working directory. Invoking the launcher by absolute path from another directory must also work.

The installer determines whether a first installation, update, or verifiable no-op is needed. It obtains everything from that source: packages, locks, scripts, default configuration, command templates, and documentation. The user must not have to run setup/build or build wheels manually beforehand.

### 2.2. Connecting a Project

After installation, the user opens their project in a supported agent host and invokes:

```text
/knowledge-init
```

The command automatically resolves and validates the active project root, locates the installed runtime, creates the necessary project configuration, initializes `.knowledge`, and runs a complete resumable scan to completion. An ordinary, unambiguous configuration must not require additional questions. Ambiguity between multiple roots must not be resolved by silently selecting another project.

No project is needed during installation. Do not use `Knowledge-Source` as a dummy project root to pass checks or scan it during installation.

## 3. Installation and Automatic Updates

1. Inspect the current `release/p4-kit/install.py`, `install.ps1`, `scripts/build_p4.py`, manifests, ownership marker, and MCP/host integration points. Choose the smallest extension to the existing mechanism that preserves its verified guarantees.
2. The new launcher must automatically discover a compatible Python and prepare the runtime. Reuse an existing Python 3.12 installation when suitable; do not damage other environments. If automatic provisioning of a missing runtime is supported, use an official pinned source and integrity verification. If provisioning is impossible in the current environment, return a precise prerequisite error with one corrective action rather than requesting a set of paths. Do not claim fully unattended bootstrapping where it has not been implemented.
3. Install a ready, verifiable release kit when available; when only source is available, automatically build the current product. Do not reuse stale cached wheels merely because the version matches. Compare source/release identity and actual hashes.
4. Install the required MCP dependencies from the pinned lock without a separate mandatory `--mcp-online` question: the user is explicitly installing an MCP product. Distinguish offline core installation, offline MCP installation with a complete wheelhouse, and online bootstrapping; do not describe a network-dependent scenario as offline. Do not report a successful installation after a network failure.
5. Deliver the runtime, `knowledge-init-auto.py`, the three commands, default provider configuration, and instructions. They must continue to work after the source directory is deleted or renamed. Do not leave references, imports, or script execution dependent on the temporary `Knowledge-Source` directory.
6. Make the runtime/MCP available on the machine and the three commands globally available through the host's actual supported mechanism. Do not require opening a project. Preserve unrelated existing MCP/config entries; verify the host version and configuration format. MCP registration by itself does not install slash commands.
7. Re-running against the same product-owned `McpDir` automatically updates the installation from the current source; do not require manual uninstallation/reinstallation or re-entering the provider. The same source artifact may produce a verified no-op; different bytes with the same version must be updated.
8. Preserve user settings, shared memory, registrations, and installation metadata. Prepare and verify the replacement before switching; on failure, retain or restore the previous working installation through the supported transactional/rollback mechanism. Do not mark an incomplete update as successful.
9. For an older installation without the new marker, automatically recognize only files/packages whose ownership by the product can be established. Do not require `--adopt` in the normal, verifiable case. Do not take over an unrelated venv or a directory containing unrelated files: fail precisely while preserving its contents. Do not report such a conflict as a successful no-op.
10. Do not bulk-upgrade project databases during machine installation. Do not enumerate or modify projects solely to update the product. Check format compatibility and required upgrade steps when a specific project is accessed; do not bypass existing exact-approval contracts.
11. If MCP is already running, provide a documented way to update the product's own processes and files. Do not terminate unrelated Python/OpenCode/MCP processes. If the host requires a restart to reload registration, state this in the brief result; do not claim the new process is active without verification.
12. Keep installation output short: `INSTALLED`, `UPDATED`, `UNCHANGED`, or a precise failure; include the path, version/source identity, shared configuration, MCP/command status, and log location. Save full pip/build logs and JSON separately, without secrets.

Do not install Visual Studio, SDKs, Kafka, or a model as a side effect of installing Knowledge MCP. A model must not be required for installation or local product diagnostics; check model availability only for operations that actually need it.

## 4. One Provider Configuration for All Projects

Base configuration object:

```json
{
  "provider": {
    "endpoint": "http://127.0.0.1:9000/v1/chat/completions",
    "model": "controlled-demo",
    "evidence": "test-double"
  }
}
```

Implement a single shared source of truth, for example `<McpDir>\config\provider.json`, accessible to all projects using this installation. Document the chosen location, format, resolution order, and how to change it later. Do not duplicate the provider in every project runner or template.

- On first installation, obtain the initial default from `Knowledge-Source`. Changes to the installed shared file must be picked up by every project on its next operation, without reinitializing each project.
- If Harness requires a project-local runner, retain project-specific build/test/scope settings and a reference to the shared provider configuration; update the resolver/validator and authority checks consistently. After the effective provider changes, an old run/approval must not silently authorize new effects; use the existing drift/re-enrollment checks.
- Preserve compatible reading of older runners with an inline provider. Do not perform hidden bulk rewrites. A specific project's transition to the global provider must occur through an explicit `/knowledge-init` invocation and be shown in the result. If inline and global values conflict, do not introduce unpredictable precedence.
- During updates, do not overwrite user-edited shared configuration with factory defaults. If the previous default was unchanged, a verifiable update from the new source default is acceptable; document and test how user edits are distinguished.
- `controlled-demo` and `test-double` are demonstration settings, not a discovered real model belonging to the owner. Do not automatically change `evidence` to `live` or describe fixture execution as verification of a real model. Installation must neither start a fake provider on port 9000 nor assume that one exists.
- Handle credentials through the existing `key_env` or supported secret mechanism; do not write credential values into project JSON, templates, reports, or logs.

## 5. Integrating knowledge-init-auto.py

“Use the script in the installer” means include it in the distribution, install it, and connect it to `/knowledge-init`. **The installer must not run it against a project:** the user explicitly requires project setup to remain separate.

Move helper 1.1 into version-controlled source and the built kit under the standard name `knowledge-init-auto.py`. After installation, run it using the installed Python. Shared logic may be moved into an installed module/entry point while retaining the script as a compatible wrapper; do not create two diverging loop implementations.

Required behavior:

- The first call starts or finds a scan for the current snapshot; subsequent chunks use the same ID. After interruption, continuation uses a durable checkpoint bound to the actual root.
- Display the scan ID immediately after the first successful chunk, rather than only after the entire project finishes. Keep progress brief; full JSON/coverage/evidence belongs only in diagnostics. Large `details` must not flood the terminal or model context again.
- Checkpoints and logs must not change the source snapshot. Keep them outside the project or use a service path that is demonstrably excluded; the original helper uses an external directory. Preserve root boundaries and separation between checkouts.
- Stop on `blocked`/`coverage_errors`, invalid JSON, CLI failure, a stale scan/source drift, an unexpected ID change, no progress, or an explicit limit being reached. Do not fix problems by deleting files, ignoring sources, or changing the root.
- A timeout or unknown outcome does not prove that no commit occurred. Do not automatically enter an endless retry loop or start a new scan; use observation/recovery and show the exact next step.
- For large projects, a host-tool deadline must not destroy work that has just started. Use supported durable execution/continuation and status; do not report `complete` before the scan and reconciliation actually finish.
- Do not portray a per-chunk extraction-count bound as a time limit or constant-cost full inventory/hashing.
- A normal successful scan produces candidates and a report. It must not call prepare/apply/acknowledge as a hidden stage or approve knowledge.

Explicitly check for recursion: the helper currently invokes `python -I -m knowledge.cli knowledge-init` for one chunk. If the public `knowledge-init` CLI starts invoking this helper itself, execution becomes recursive. Preserve a separate low-level chunk operation or introduce an explicit internal separation. The slash-command wrapper, automatic loop, and chunk backend must form a finite call chain, verified with a real subprocess test.

## 6. Create Three Commands

The user-facing command names must be exactly:

```text
/knowledge-init
/knowledge-candidates-update
/knowledge-candidates-push
```

Implement their executable backend, host templates, and template installation. Merely placing three `.md` files in the source is insufficient: demonstrate that the supported host discovers the commands after installation. Preserve compatibility with existing CLI names and protocols, or provide a documented adapter.

### 6.1. /knowledge-init

1. Resolve the root from the active workspace; verify its identity and the installation. Do not default to IPM paths. For a normal Git project, do not require the user to supply `--root` manually; explicit CLI use of `--root` remains valid.
2. Create or consistently update the necessary project configuration, access to the installed MCP/runtime, and the global provider reference. Preserve unrelated settings. Build/test settings belong to the project; do not invent them or make machine installation depend on their presence.
3. Create a new `.knowledge` or preserve existing data, the queue, and lifecycle/history. Perform required upgrades/migrations only through supported mechanisms; do not bypass previous approvals or root binding.
4. Run the installed automatic loop for full inventory and reconciliation. Do not require manual copying of IDs or repeated invocations for every 100 files.
5. Preserve the intent of the attached `knowledge-init.md`: new/changed assertions, verification of existing assertions, dependencies, conflicts, possible obsolescence, and unverifiable facts. Incomplete coverage, lexical matches, and failed semantic tooling do not establish complete understanding or prove a component's removal.
6. Propose only supported lifecycle operations, preserving IDs/provenance/history. Do not substitute a “component removed” assertion for retirement while treating a contradictory active claim as resolved. If analysis or operation support is insufficient, show the coverage gap and report `PARTIAL`/`BLOCKED_CAPABILITY`.
7. Re-running against an unchanged project must not create duplicate candidates. After a blocker is fixed, use correct resume/restart behavior rather than endlessly continuing a scan that remains irreversibly blocked.
8. Report the root, version, provider reference, scan ID, coverage, candidates actually queued, conflicts/limitations, and the next step, `/knowledge-candidates-push`. Save full data locally; do not dump the entire database into chat.

### 6.2. /knowledge-candidates-update

Collect new and changed knowledge from the current work, a supplied Git range, or relevant working-tree changes. Use the same root/runtime/global configuration and the supported durable queue. Deduplicate by identity/meaning and evidence; preserve rejected/deferred decisions under the existing contract. Do not silently run a full scan instead of the stated incremental scope, or claim unsupported semantics have been implemented.

Check evidence and support for `add/update/retire/supersede` operations before submission. Report actual added/skipped/blocked results and scope. Do not directly edit SQLite/JSONL/lock files, apply canonical changes, or retry busy locks indefinitely.

### 6.3. /knowledge-candidates-push

Prepare and validate a plan for pending candidates; display a compact summary and its exact fingerprint. Canonical knowledge must not change until that fingerprint receives separate explicit approval. Invoking `/knowledge-candidates-push`, installing the product, or approving an earlier plan does not approve a new plan.

After approval, recheck the root, evidence/source, queue, and plan binding; perform the supported apply and acknowledge steps, then validation/status. On drift, prepare a new reviewable plan; do not automatically substitute a new approval value. Handle partial failure through supported recovery without direct database repairs. History and retired/superseded knowledge must remain accessible.

## 7. Acceptance Checks

Provide reproducible checks and their actual results. Static checks do not replace an executable scenario.

| Scenario | Acceptance criterion |
|---|---|
| Clean installation from source | One `McpDir`, no manual build/setup and no project; runtime, MCP, helper, and commands are ready |
| Paths with spaces/Cyrillic characters | Installation and commands work in Windows PowerShell 5.1 without `&&`/`||` or broken quoting/UTF-8 |
| Launcher invoked from another directory | The source adjacent to the launcher is used; an unrelated CWD is not scanned |
| Source removed after installation | MCP and all three commands continue working; the product's sources are installed independently |
| Re-running the same kit | A successful verified no-op or safe reinstallation, without duplicate registrations/commands |
| Changed source with the same version | New bytes are actually delivered; hashes and imports from the installed runtime are verified |
| Updating an existing installation | Product ownership is automatically recognized; settings and memory are preserved; no mandatory manual uninstall/adopt |
| Unrelated directory/incompatible environment | Failure occurs before destructive changes; unrelated files are preserved |
| Update failure/interruption | The previous installation remains usable or a verified rollback is available; no false success |
| Machine installation | Does not create `.knowledge` in the source/CWD or modify existing project stores |
| Global provider | Two independent projects read one shared configuration; changes are picked up without copying settings into each project |
| Provider and upgrades | User values are preserved; the demo remains `test-double`; drift checks for an old run are not bypassed |
| Real MCP transport | The installed stdio server passes handshake/list-tools checks; no diagnostic logs enter JSON-RPC stdout |
| Host commands | All three are available from a new project without manually copying templates or retaining the old source |
| Large project | Multiple chunks, unchanged ID, automatic resume, bounded terminal output, and completed reconciliation |
| Recursion | A finite number of subprocesses; no helper → public automatic CLI → helper loop |
| Coverage/CLI/timeout | Clear failure, diagnostics, and recoverable state; no busy/restart loop |
| Unchanged rerun | No duplicate candidates; history and dispositions are preserved |
| Command separation | Init/update only prepare candidates; push does not change canonical knowledge before exact-plan approval |
| Stale approval | Source/queue/provider changes follow the existing binding contract; an old approval is not transferred to a new plan |
| Legacy project | No hidden `.ai` migration, history loss, or relocation of root-bound SQLite by copying |

A correct protocol client is sufficient for transport tests; live OpenCode and a real local model require separate checks. If Windows/the host/the model is unavailable, explicitly report `NOT_RUN` and the remaining scenario; do not describe fixtures or a test double as live E2E.

## 8. Implementation Sequence and Delivery

1. Briefly document the current entry points, installation source, host/version contract, and chosen shared-configuration location. Resolve discrepancies between the attached legacy instructions and the current product.
2. Implement the shared provider resolver, runtime/MCP installation and updates, and delivery of commands/helper. Then connect project bootstrapping and the three commands.
3. Run acceptance checks against the installed product outside the source checkout; retain the minimal fixtures and logs needed for reproduction.
4. Update the README and Russian instructions: one installation/update command with `McpDir`, followed by `/knowledge-init` inside a project, changing the shared provider, and approved push. Do not require manual configuration of every runner with repeated provider settings.
5. In the final report, list changed files, the global-configuration and host-registration decisions, test results/limitations, and exact verification commands. Confirm preservation of existing data and the absence of project setup during installation.

Do not expand the task into a redesign of Knowledge/Harness, a model change, introduction of new agents, or optimization of every database. Perform normal supported operations automatically within this task; additional user decisions are needed only for a genuine data/identity conflict that cannot be resolved by preserving existing settings. Merging, publishing a release, and modifying the owner's actual working installation are outside this task's scope.

## Appendix A. Original knowledge-init-auto.py Version 1.1

The complete source of the supplied helper follows. Use it for inclusion in the distribution and for necessary changes while preserving the specified contract. This appendix is implementation source material, not a ready-to-run installation command.

```python
#!/usr/bin/env python3
r"""Continue Knowledge 0.5 knowledge-init chunks; never approve/apply candidates.

PowerShell:
  & $Runtime -I .\knowledge-init-auto.py --root 'C:\Git\MyProject'
  & $Runtime -I .\knowledge-init-auto.py --root 'C:\Git\MyProject' --scan-id 'ID'

Requires the Python environment containing knowledge-p0. Output/checkpoints stay
outside the project so they do not change the source snapshot being scanned.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


class ScanError(Exception):
    pass


def short_message(value, limit=240):
    text = ' '.join(str(value).split())
    return text if len(text) <= limit else text[:limit] + '...'


def write_json(path, value):
    fd, temporary = tempfile.mkstemp(prefix='.scan-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def inside(path, root):
    return path == root or root in path.parents


def run(root, output, scan_id=None, max_files=100, max_calls=10000,
        command_timeout=600, fresh=False):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ScanError('--root must be an existing project directory.')
    output = Path(output).resolve()
    if inside(output, root):
        raise ScanError('Output must be outside --root to avoid changing the scan snapshot.')
    # The driver itself must also stay outside the scanned project.
    if inside(Path(__file__).resolve(), root):
        raise ScanError('Move this helper outside the project, for example C:\\Temp.')
    output.mkdir(parents=True, exist_ok=True)
    checkpoint = output / 'checkpoint.json'
    if not scan_id and not fresh and checkpoint.exists():
        saved = json.loads(checkpoint.read_text(encoding='utf-8'))
        if saved.get('root') != str(root):
            raise ScanError('Checkpoint belongs to a different root; choose another --output.')
        scan_id = saved.get('scan_id')
        if not isinstance(scan_id, str) or not scan_id.strip():
            raise ScanError('Invalid checkpoint scan_id; inspect checkpoint.json.')
    print('Knowledge scan helper 1.1', flush=True)
    print('Project: ' + str(root), flush=True)
    print('Diagnostics: ' + str(output), flush=True)
    if scan_id:
        print('Scan ID: ' + short_message(scan_id), flush=True)
    previous = None
    environment = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}
    for number in range(1, max_calls + 1):
        command = [sys.executable, '-I', '-m', 'knowledge.cli', 'knowledge-init',
                   '--root', str(root), '--max-files', str(max_files)]
        if scan_id:
            command.extend(['--scan-id', scan_id])
        try:
            process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     encoding='utf-8', errors='strict', env=environment,
                                     timeout=command_timeout, check=False)
        except subprocess.TimeoutExpired as error:
            # No automatic retry: the child may have committed before timeout.
            write_json(output / 'last-error.json', {
                'error': 'command-timeout-outcome-unknown', 'scan_id': scan_id,
                'timeout_seconds': command_timeout})
            raise ScanError('Command timed out; no automatic retry. Inspect Knowledge scan-status '
                            'and the diagnostics before resuming.') from error
        (output / 'last-stdout.txt').write_text(process.stdout, encoding='utf-8')
        (output / 'last-stderr.txt').write_text(process.stderr, encoding='utf-8')
        try:
            result = json.loads(process.stdout)
        except (ValueError, TypeError) as error:
            raise ScanError('CLI did not return valid JSON; inspect last-stdout.txt and '
                            'last-stderr.txt. No automatic retry.') from error
        write_json(output / 'last-result.json', result)
        if not isinstance(result, dict):
            raise ScanError('Unexpected CLI JSON shape; expected an object.')
        if process.returncode != 0 or result.get('ok') is not True:
            raise ScanError('Knowledge failed: ' + short_message(result.get('error', 'exit ' + str(process.returncode))))
        returned_id = result.get('id')
        if not isinstance(returned_id, str) or not returned_id.strip():
            raise ScanError('Successful response has no scan id; unsupported CLI response.')
        if scan_id and returned_id != scan_id:
            raise ScanError('CLI changed the scan id unexpectedly; stopped.')
        first_id = scan_id is None
        scan_id = returned_id
        write_json(checkpoint, {'version': 1, 'root': str(root), 'scan_id': scan_id})
        if first_id:
            print('Scan ID: ' + short_message(scan_id), flush=True)
        complete = result.get('complete')
        work = result.get('work')
        coverage = result.get('coverage')
        snapshot = result.get('snapshot')
        if type(complete) is not bool or not isinstance(work, dict) or not isinstance(coverage, dict) or not isinstance(snapshot, dict):
            raise ScanError('Missing completion/work/coverage fields; unsupported CLI response.')
        remaining = work.get('remaining_files')
        processed = work.get('durable_extracted_files')
        extracted = work.get('extracted_this_call')
        if any(type(value) is not int or value < 0 for value in (remaining, processed, extracted)):
            raise ScanError('Invalid progress counters; unsupported CLI response.')
        if any(not isinstance(item, dict) for item in coverage.values()):
            raise ScanError('Invalid coverage entries; unsupported CLI response.')
        blocked = {path: item for path, item in coverage.items() if item.get('status') == 'blocked'}
        coverage_errors = snapshot.get('coverage_errors')
        # Keep redirected/non-interactive output small as well as terminal output.
        if number == 1 or number % 25 == 0 or complete or blocked or coverage_errors:
            print('Chunk {0}: processed={1}, remaining={2}, extracted={3}, blocked={4}'.format(
                number, processed, remaining, extracted, len(blocked)), flush=True)
        if blocked or coverage_errors:
            write_json(output / 'coverage-errors.json', {
                'scan_id': scan_id, 'coverage_errors': coverage_errors, 'blocked': blocked})
            raise ScanError('Coverage is blocked. See coverage-errors.json; fix the cause '
                            'before choosing whether to resume or start a fresh scan.')
        if complete:
            if remaining or any(item.get('status') == 'not-analyzed' for item in coverage.values()):
                raise ScanError('Inconsistent complete=true response; files are still pending.')
            reconciliation = result.get('reconciliation')
            if not isinstance(reconciliation, dict) or reconciliation.get('ok') is not True or reconciliation.get('complete') is not True or reconciliation.get('scan') != scan_id:
                raise ScanError('Scan finished but reconciliation was not confirmed; inspect last-result.json.')
            gaps = result.get('gaps', [])
            print('Completed scan: ' + short_message(scan_id), flush=True)
            if gaps:
                print('Review required: {0} lexical ambiguity/gap entries in last-result.json.'.format(len(gaps)), flush=True)
            print('Coverage completion is not semantic completeness. Candidates were not approved/applied.', flush=True)
            return 0
        current = (processed, remaining)
        if extracted == 0 or (previous is not None and processed <= previous[0] and remaining >= previous[1]):
            raise ScanError('No extraction progress; stopped to avoid an endless loop. Inspect last-result.json.')
        previous = current
    raise ScanError('Reached --max-calls. Scan id is saved; rerun this command to continue.')


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError('must be greater than zero')
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', required=True, help='Existing project directory')
    parser.add_argument('--scan-id', help='Continue an already started scan')
    parser.add_argument('--max-files', type=positive, default=100)
    parser.add_argument('--max-calls', type=positive, default=10000)
    parser.add_argument('--command-timeout', type=positive, default=600, help='Seconds per CLI call')
    parser.add_argument('--output', help='Diagnostic directory outside the project')
    parser.add_argument('--fresh', action='store_true', help='Ignore saved checkpoint; ask Knowledge for the current snapshot scan (does not reset existing scan state)')
    args = parser.parse_args()
    if args.max_files > 10000:
        parser.error('--max-files cannot exceed 10000')
    if args.fresh and args.scan_id:
        parser.error('--fresh and --scan-id cannot be used together')
    root_key = os.path.normcase(str(Path(args.root).resolve()))
    key = hashlib.sha256(root_key.encode('utf-8')).hexdigest()[:20]
    base = Path(os.environ.get('LOCALAPPDATA') or tempfile.gettempdir())
    output = args.output or str(base / 'Knowledge' / 'scan-helper' / key)
    try:
        return run(args.root, output, args.scan_id, args.max_files, args.max_calls,
                   args.command_timeout, args.fresh)
    except KeyboardInterrupt:
        print('\nInterrupted. Inspect diagnostics/scan-status before resuming; '
              'a completed chunk remains durable.', file=sys.stderr)
        return 130
    except (ScanError, OSError, ValueError, UnicodeError) as error:
        print('STOP: ' + short_message(error), file=sys.stderr)
        print('Full diagnostics: ' + str(Path(output).resolve()), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
```
