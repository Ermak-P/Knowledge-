"""Durable external scan workers. A host request starts/observes, never owns it.

Unknown outcomes stop. Status is observation, not an automatic retry policy.
"""
import argparse
import re
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from .auto_init import run, write_json, read_json, read_checkpoint, ScanError, ScanCancelled
from .execution_lock import ExecutionLock, ProjectExecutionLock
from .project import safe_path
from .util import KnowledgeError, digest, require

_children = {}


def process_stamp(pid):
    if os.name!='nt':
        try:
            fields=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split()
            return Path('/proc/sys/kernel/random/boot_id').read_text().strip()+':'+fields[19]
        except (OSError,IndexError):return None
    import ctypes
    from ctypes import wintypes as w
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenProcess.restype=w.HANDLE
    k.GetProcessTimes.argtypes=[w.HANDLE,*[ctypes.POINTER(w.FILETIME)]*4];k.GetProcessTimes.restype=w.BOOL
    k.CloseHandle.argtypes=[w.HANDLE]
    handle=k.OpenProcess(0x1000,False,pid)
    if not handle:return None
    try:
        times=[w.FILETIME() for _ in range(4)]
        if not k.GetProcessTimes(handle,*[ctypes.byref(t) for t in times]):return None
        return str((times[0].dwHighDateTime<<32)|times[0].dwLowDateTime)
    finally:k.CloseHandle(handle)


def alive(pid,expected=None):
    if expected is not None and process_stamp(pid)!=expected:return False
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle: return False
        try:
            code = wintypes.DWORD()
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value == 259)
        finally: kernel.CloseHandle(handle)
    try:
        state = Path('/proc') / str(pid) / 'stat'
        if state.is_file() and state.read_text().rsplit(')', 1)[1].split()[0] == 'Z': return False
        os.kill(pid, 0); return True
    except (ProcessLookupError, FileNotFoundError): return False
    except PermissionError: return True


ACTIVE = {'STARTING', 'RUNNING'}
TERMINAL = {'COMPLETED', 'COMPLETED_WITH_GAPS', 'CANCELLED', 'BLOCKED'}
CHECKPOINT_SCOPE = {'base': None, 'head': None, 'incremental': False}

# These reasons come from the runtime's lexical compatibility checks.
INCOMPATIBLE = {
    'stale-extractor-restart-required': ('extractor', 'Use a runtime supporting the recorded extractor.'),
    'incompatible-scan-identity-policy': ('identity_policy', 'Use a runtime supporting the recorded identity policy.'),
    'incompatible-scan-resume-contract': ('runtime_capabilities', 'Use a runtime supporting the recorded lexical resume contract.'),
    'stale-discovery-policy': ('discovery_configuration', 'Restore the recorded discovery policy.'),
    'stale-scan-git-revision': ('git_revision', 'Return to the recorded Git revision and source snapshot.'),
    'checkout-requested-head-first': ('git_revision', 'Check out the recorded head commit before resuming this range.'),
    'stale-scan-git-branch': ('git_branch', 'Return to the recorded Git branch or detached HEAD.'),
    'stale-scan-restart-required': ('source_snapshot', 'Restore the recorded working tree and index.'),
    'scan-range-mismatch-restart-required': ('scope', 'Select the recorded base and head range.'),
    'scan-scope-mismatch-restart-required': ('scope', 'Select the recorded full or incremental scope and source.'),
    'unsupported-store-format': ('database_schema', 'Use a runtime supporting the project database format.'),
    'unsupported-extension-version': ('database_schema', 'Use a runtime supporting the project database extension.'),
    'incompatible-scan-database-schema': ('database_schema', 'Preserve the store and use a runtime supporting its discovery tables.'),
    'upgrade-required': ('database_schema', 'Inspect the database and use the separately approved upgrade workflow if appropriate.'),
    'unsupported-checkpoint-format': ('checkpoint_format', 'Use a runtime supporting the locator format or inspect the durable scan ID.'),
}
OBSERVE = 'Inspect knowledge_scan_diagnostics section=scans. Resume only a verified scan ID, or explicitly choose fresh.'
WAIT = 'Wait for the worker to finish or request cancellation at a durable chunk boundary.'
UNVERIFIED_WORKER = 'scan-worker-liveness-unverified'


def owned_job(folder, owner=None):
    state = read_json(safe_path(Path(folder) / 'job.json'), max_bytes=65536)
    require(isinstance(state, dict) and state.get('version') == 1 and type(state.get('pid')) is int
            and state['pid'] > 0 and state.get('state') in ACTIVE | TERMINAL
            and isinstance(state.get('job'), str) and 0 < len(state['job']) <= 128
            and isinstance(state.get('scope'), dict) and state['scope'].get('kind') in ('full', 'incremental', 'plan'),
            'invalid-scan-job-state')
    if owner is not None:
        binding = state.get('binding')
        require(isinstance(binding, dict) and binding.get('root') == owner and state.get('root') == owner['root'],
                'scan-job-root-binding-mismatch')
        scope = state['scope']
        if scope['kind'] == 'incremental' or 'base' in scope or 'head' in scope:
            require(set(scope) == {'kind', 'base', 'head'}
                    and all(isinstance(scope[key], str) and re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}', scope[key])
                            for key in ('base', 'head')), 'invalid-scan-job-scope')
        else:
            require(set(scope) == {'kind'}, 'invalid-scan-job-scope')
        expected = 'incremental-' + digest(scope) if scope['kind'] == 'incremental' else scope['kind']
        if scope['kind'] == 'plan':
            require(Path(folder).parent.name == 'plan' and Path(folder).name == state['job'],
                    'plan-job-scope-binding-mismatch')
        else:
            require(Path(folder).name == expected, 'scan-job-scope-binding-mismatch')
    return state


def checkpoint_scope(scope):
    return {'base': scope.get('base'), 'head': scope.get('head'), 'incremental': scope['kind'] == 'incremental'}


def checkpoint_status(folder, state):
    path = safe_path(folder / 'checkpoint.json')
    if not path.exists():
        return {}
    try:
        saved = read_checkpoint(path)
    except (ScanError, ValueError, TypeError, OSError) as error:
        return {'checkpoint_error': getattr(error, 'code', 'invalid-scan-checkpoint')}
    # After fresh starts, the previous locator can survive until the first
    # committed chunk. It cannot prove the outcome of the new worker.
    if ((state.get('fresh') or state.get('recovery_of') or (state.get('previous_success') and not state.get('resume')))
            and saved.get('job') != state['job']
            and not (saved.get('job') is None and state.get('progress_scan_id') == saved['scan_id'])):
        return {'checkpoint_error': 'scan-checkpoint-precedes-fresh-worker'}
    root = saved.get('root')
    if (not isinstance(root, str) or os.path.normcase(root) != os.path.normcase(state['root'])
            or saved.get('scope', CHECKPOINT_SCOPE) != checkpoint_scope(state['scope'])):
        return {'checkpoint_error': 'scan-checkpoint-ownership-mismatch'}
    return {'scan_id': saved['scan_id'], 'checkpoint_format': saved['version']}


def worker_state(folder, state):
    launcher = safe_path(folder / 'launcher.json')
    launched = read_json(launcher, max_bytes=8192) if launcher.exists() else {}
    launcher_pid = launched.get('pid') if launched.get('job') == state['job'] else None
    require(launcher_pid is None or (type(launcher_pid) is int and launcher_pid > 0), 'invalid-scan-launcher-state')
    child = _children.get(launcher_pid)
    if child is not None and child.poll() is not None:
        _children.pop(launcher_pid, None)
    worker_stamp = state.get('process_stamp')
    launcher_stamp = launched.get('process_stamp')
    # Old jobs without a creation stamp cannot establish PID ownership.
    living = bool(worker_stamp and alive(state['pid'], worker_stamp))
    if state['state'] == 'STARTING' and launcher_pid is not None:
        # Once published, the launcher is authoritative until the worker
        # handshake. The host PID may stay alive after a failed launch.
        living = False
    living = living or (launcher_pid is not None and bool(launcher_stamp) and alive(launcher_pid, launcher_stamp))
    if state['state'] in ACTIVE and not living:
        state['legacy_worker_may_be_active'] = ((not worker_stamp and alive(state['pid']))
                                               or (launcher_pid is not None and not launcher_stamp and alive(launcher_pid)))
        state.update(state='OUTCOME_UNKNOWN', next_action=OBSERVE)
    elif state['state'] in TERMINAL and living:
        # A Windows venv redirector can outlive its Python worker briefly.
        state.update(state='RUNNING', phase='FINALIZING')
    return state


def status(folder, owner=None):
    folder = Path(folder)
    state = worker_state(folder, owned_job(folder, owner))
    last = safe_path(folder / 'progress.json')
    if last.exists():
        value = read_json(last, max_bytes=65536)
        if value.get('job') == state['job']:
            state.update(identity_verification=value.get('identity_verification'), coverage_complete=value.get('complete', False), work=value.get('work'), candidates=value.get('candidates', 0),
                         counters=value.get('counters'), processing_complete=(value.get('work') or {}).get('remaining_files')==0,
                         gaps=value.get('gaps', 0), source=value.get('source'), source_verified=value.get('source_verified', False), semantic_coverage_complete=False)
            state['progress_scan_id'] = value.get('scan_id')
    state.update(checkpoint_status(folder, state))
    cancellation = safe_path(folder / 'cancel.json')
    if state['state'] in ACTIVE and cancellation.exists() and read_json(cancellation, max_bytes=8192).get('job') == state['job']:
        state['phase'] = 'CANCELLING_AT_CHUNK_BOUNDARY'
    return state


def compatibility(state, binding):
    saved = state['binding']
    changed = []
    if 'runtime_release' in saved and saved['runtime_release'] != binding['runtime_release']:
        changed.append('runtime_release')
    reference = saved.get('provider_reference') or {}
    current = binding.get('provider_reference') or {}
    available = bool(current)
    if available and reference:
        if reference.get('path') != current.get('path'):
            changed.append('provider_reference.path')
        if reference.get('hash') != current.get('hash'):
            old_fields, new_fields = saved.get('provider_fields'), binding.get('provider_fields')
            observed = [f'provider.{key}' for key in new_fields if old_fields.get(key) != new_fields[key]] if old_fields and new_fields else []
            changed.extend(observed or ['provider_reference.hash'])
    elif available != bool(reference) or saved.get('provider_state') != binding.get('provider_state'):
        changed.append('provider_configuration')
    nonblocking = changed.copy()
    reason = state.get('checkpoint_error')
    action = OBSERVE
    execution = source = 'unverified'
    allowed = None
    if state.get('resume_verified'):
        execution = source = 'verified-at-resume'
    if state['state'] in ACTIVE:
        allowed, reason, action = False, 'scan-worker-active', WAIT
    elif state.get('legacy_worker_may_be_active'):
        allowed, reason, action = False, UNVERIFIED_WORKER, WAIT
    elif reason:
        allowed = False
    elif not state.get('scan_id'):
        allowed, reason = False, 'scan-outcome-observation-required'
    else:
        reason = 'checkpoint-present-verification-required'
        action = 'Request explicit resume to verify the source and checkpoint.'
    failure = state.get('resume_failure')
    if failure:
        allowed, reason, action = False, failure['reason'], failure['next_action']
        execution, source = failure['execution_compatibility'], failure['source_compatibility']
        changed = list(dict.fromkeys(failure['changed_fields'] + changed))
        nonblocking = list(dict.fromkeys(failure['nonblocking_fields'] + nonblocking))
    checkpoint_format = state.get('checkpoint_format')
    return {'configuration': 'drift' if changed else 'unchanged' if available else 'unavailable',
            'changed_fields': changed, 'nonblocking_fields': nonblocking,
            'provider_configuration': 'available' if available else binding.get('provider_state', 'unavailable'),
            'checkpoint_available': bool(state.get('scan_id')), 'checkpoint_format': checkpoint_format,
            'checkpoint_integrity': {1: 'legacy-locator', 2: 'locator-checksum-verified'}.get(
                checkpoint_format, 'invalid-locator' if state.get('checkpoint_error') else 'locator-missing'),
            'execution_compatibility': execution, 'source_compatibility': source,
            'resume_allowed': allowed, 'reason': reason, 'next_action': action}


def resume_details(state, binding, reason, scan_id=None):
    report = compatibility(state, binding)
    field, action = INCOMPATIBLE.get(reason, (None, OBSERVE))
    if reason in ('scan-worker-active', UNVERIFIED_WORKER):
        action = WAIT
    elif reason == 'project-writer-busy':
        action = 'Wait for the project writer to release its execution lock, then retry explicit resume.'
    elif reason == 'scan-git-branch-unverified':
        action = 'Preserve the legacy checkpoint and history. Use an earlier compatible runtime for recovery or explicitly choose fresh.'
    elif reason == 'scan-checkpoint-ownership-mismatch':
        action = 'Verify the selected project and scope. Inspect the project scan history before attempting recovery.'
    changed = list(dict.fromkeys(report['changed_fields'] + ([field] if field else [])))
    return {**report, 'job_id': state.get('job'), 'scan_id': scan_id or state.get('scan_id'), 'worker_state': state['state'],
            'changed_fields': changed, 'resume_allowed': False, 'reason': reason, 'next_action': action,
            'execution_compatibility': 'incompatible' if field else 'unverified',
            'source_compatibility': 'incompatible' if field in ('source_snapshot', 'git_branch', 'git_revision', 'scope', 'discovery_configuration') else 'unverified'}


def cancel(folder, owner, scope):
    folder = safe_path(Path(folder))
    lease = ExecutionLock(folder / 'launch.lock').acquire()
    try:
        state = status(folder, owner)
        require(state['scope'] == scope, 'scan-job-scope-binding-mismatch')
        active = state['state'] in ACTIVE or state.get('legacy_worker_may_be_active')
        marker = safe_path(folder / 'cancel.json')
        if active and (not marker.exists() or read_json(marker, max_bytes=8192).get('job') != state['job']):
            write_json(marker, {'version': 1, 'job': state['job']})
        message = 'requested at durable chunk boundary' if active else 'already terminal'
        if state['state'] == 'OUTCOME_UNKNOWN' and not active:
            message = 'worker liveness unverified; inspect status and durable history'
        return {'ok': True, 'state': state['state'], 'job': state['job'], 'scan_id': state.get('scan_id'), 'cancellation': message}
    finally:
        lease.close()


def launch(folder, state, module):
    metadata = safe_path(folder / 'job.json')
    with safe_path(folder / 'progress.log').open('ab') as log:
        flags = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS) if os.name == 'nt' else 0
        if os.name == 'nt' and os.environ.get('KNOWLEDGE_OWNED_JOB') == '1':
            flags |= subprocess.CREATE_BREAKAWAY_FROM_JOB
        options = {'creationflags': flags} if os.name == 'nt' else {'start_new_session': True}
        write_json(metadata, state)
        try:
            process = subprocess.Popen([sys.executable, '-I', '-B', '-X', 'utf8', '-m', module, '--worker', str(folder)],
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, close_fds=True, **options)
        except OSError:
            state.update(state='BLOCKED', pid=os.getpid(), process_stamp=None, error='scan-worker-launch-failed', next_action=OBSERVE)
            write_json(metadata, state)
            raise
    _children[process.pid] = process
    write_json(safe_path(folder / 'launcher.json'), {'version': 1, 'job': state['job'], 'pid': process.pid,
               'process_stamp': process_stamp(process.pid)})
    return process


def start(folder, root, scope, binding, max_files=100, resume=False, fresh=False, observed_scan_id=None, recovery_of=None):
    require(sum(map(bool, (resume, fresh, recovery_of))) <= 1, 'invalid-recovery-controls')
    require(type(max_files) is int and 1 <= max_files <= 10000, 'invalid-scan-bound')
    require(observed_scan_id is None or (resume and isinstance(observed_scan_id, str)
            and re.fullmatch('[0-9a-f]{64}', observed_scan_id)), 'invalid-observed-scan-resume')
    folder = safe_path(Path(folder))
    folder.mkdir(parents=True, exist_ok=True)
    lease = ExecutionLock(folder / 'launch.lock').acquire()
    try:
        metadata = safe_path(folder / 'job.json')
        old = status(folder, binding['root']) if metadata.exists() else None
        context = old or {'binding': binding, 'state': 'NOT_STARTED'}
        if old and old.get('legacy_worker_may_be_active'):
            raise KnowledgeError(UNVERIFIED_WORKER, resume_details(old, binding, UNVERIFIED_WORKER))
        if old and old['state'] in ACTIVE:
            require(not (resume or recovery_of), 'scan-worker-active', resume_details(old, binding, 'scan-worker-active'))
            require(not fresh, 'scan-active-cancel-before-fresh')
            require(old['scope'] == scope, 'active-scan-scope-mismatch')
            return old
        if old and not (resume or fresh or recovery_of):
            require(old['state'] == 'COMPLETED', 'scan-recovery-required',
                    resume_details(old, binding, 'scan-recovery-required'))
        if resume and old:
            require(old['scope'] == scope, 'resume-scan-configuration-drift',
                    resume_details(old, binding, 'scan-scope-mismatch-restart-required'))

        continuation = resume or (old is not None and not (fresh or recovery_of))
        resume_id = None
        if continuation:
            recorded = context.get('scan_id')
            require(not (recorded and observed_scan_id and recorded != observed_scan_id),
                    'resume-scan-configuration-drift', resume_details(context, binding, 'observed-scan-checkpoint-mismatch'))
            resume_id = recorded or observed_scan_id
            require(resume_id is not None, 'resume-scan-configuration-drift',
                    resume_details(context, binding, context.get('checkpoint_error', 'scan-outcome-observation-required')))
            require(context.get('checkpoint_error') != 'scan-checkpoint-ownership-mismatch',
                    'resume-scan-configuration-drift', resume_details(context, binding, 'scan-checkpoint-ownership-mismatch'))
        elif old is None and not (fresh or recovery_of):
            require(not safe_path(folder / 'checkpoint.json').exists(), 'scan-recovery-required',
                    resume_details(context, binding, 'scan-outcome-observation-required'))

        # Verify project ownership is available before publishing a new job.
        # The child acquires the same lock before checking compatibility or
        # extracting, including when another scope races this launch.
        try:
            ProjectExecutionLock(root).acquire().close()
        except KnowledgeError as error:
            if continuation:
                raise KnowledgeError(error.code, resume_details(context, binding, error.code, resume_id)) from error
            raise
        state = {'version': 1, 'job': uuid.uuid4().hex, 'root': str(root), 'scope': scope, 'binding': binding,
                 'max_files': max_files, 'fresh': fresh, 'resume': resume, 'resume_scan_id': resume_id,
                 'chunk_started': False, 'state': 'STARTING', 'pid': os.getpid(),
                 'process_stamp': process_stamp(os.getpid()), 'diagnostics': str(folder)}
        if continuation:
            state['resume_context'] = resume_details(context, binding, 'checkpoint-verification-pending', resume_id)
        if recovery_of:
            state['recovery_of'] = recovery_of
        process = launch(folder, state, 'knowledge.scan_jobs')
    finally:
        lease.close()

    # Bound the handshake. Large checkpoints can finish verification after the
    # request returns. Status reports the same structured result in that case.
    for _ in range(100):
        current = owned_job(folder, binding['root'])
        if current['job'] != state['job']:
            return state
        if current['state'] in TERMINAL or current.get('chunk_started') or current.get('resume_verified'):
            return current
        if process.poll() is not None:
            break
        time.sleep(.02)
    return owned_job(folder, binding['root'])


def worker(folder):
    from .discovery import ScanSession
    from .project import Project
    from .store import Store

    folder = safe_path(Path(folder))
    state = owned_job(folder)
    state.update(state='RUNNING', pid=os.getpid(),process_stamp=process_stamp(os.getpid()))
    write_json(folder / 'job.json', state)
    lease = None
    resume_id = state.get('resume_scan_id')
    try:
        owned_job(folder, Project(state['root']).describe())
        lease = ProjectExecutionLock(state['root']).acquire()
        scope = state['scope']
        base, head = scope.get('base'), scope.get('head')
        incremental = scope['kind'] == 'incremental'
        if incremental:
            write_json(safe_path(folder.parent / 'last-incremental.json'), {'folder': folder.name})
        store = Store(state['root'])
        session = None
        if resume_id or state.get('recovery_of'):
            state['phase'] = 'VERIFYING_RESUME'
            write_json(folder / 'job.json', state)
            session = ScanSession(store)
            if resume_id:
                session.prepare_resume(resume_id, base, head, incremental)
            else:
                resume_id = session.prepare_recovery(state['recovery_of'], base, head, incremental)
            state['resume_verified'] = True
            state.pop('phase')
            write_json(folder / 'job.json', state)
        before = {row['id'] for row in store.status()['queue']}
        state['chunk_started'] = True
        write_json(folder / 'job.json', state)
        run(state['root'], folder, scan_id=resume_id, max_files=state['max_files'], fresh=state['fresh'],
            base=base, head=head, incremental=incremental, retry_blocked=state['resume'],
            cancel_path=safe_path(folder / 'cancel.json'), cancel_job=state['job'], session=session)
        after = {row['id'] for row in store.status()['queue']}
        observed = read_json(folder / 'last-result.json')
        reconciliation = observed['reconciliation']
        state.update(state='COMPLETED' if observed['complete'] else 'COMPLETED_WITH_GAPS', queued_added=len(after - before),
                     skipped_existing=max(0, len(observed.get('candidates', [])) - len(after - before)),
                     reconciliation={'claims': len(reconciliation['claims']), 'classifications': {name: sum(row['classification'] == name for row in reconciliation['claims']) for name in sorted({row['classification'] for row in reconciliation['claims']})},
                                     'negative_evidence_gaps': len(reconciliation.get('negative_evidence_gaps', [])), 'retirement_proposal_available': reconciliation.get('proposal') is not None})
    except ScanCancelled as error:
        state.update(state='CANCELLED',chunk_started=(folder/'checkpoint.json').exists(),error=str(error),next_action='Resume the compatible checkpoint explicitly, or choose fresh for a new execution.')
    except Exception as error:
        if state.get('recovery_of') and not state.get('resume_verified'):
            reason = getattr(error, 'code', 'scan-checkpoint-verification-failed')
            details = getattr(error, 'details', None) or {}
            state.update(state='BLOCKED', error=reason, recovery_failure=details, next_action=details.get('next_action', OBSERVE))
        elif resume_id and not state.get('resume_verified'):
            reason = getattr(error, 'code', 'scan-checkpoint-verification-failed')
            failure = resume_details(state, state['binding'], reason, resume_id)
            context = state['resume_context']
            failure.update(job_id=context['job_id'], worker_state=context['worker_state'],
                           changed_fields=list(dict.fromkeys(context['changed_fields'] + failure['changed_fields'])),
                           nonblocking_fields=context['nonblocking_fields'],
                           configuration=context['configuration'], checkpoint_available=context['checkpoint_available'],
                           checkpoint_format=context['checkpoint_format'], checkpoint_integrity=context['checkpoint_integrity'])
            state.update(state='BLOCKED', error='resume-scan-configuration-drift', resume_failure=failure,
                         next_action=failure['next_action'])
        else:
            message = str(error)[:500] if isinstance(error, (ScanError, OSError, ValueError, RuntimeError)) else type(error).__name__
            state.update(state='BLOCKED', error=message, next_action=OBSERVE)
    finally:
        state.pop('phase', None)
        state.pop('resume_context', None)
        if lease: lease.close()
        write_json(folder / 'job.json', state)
    return 0 if state['state'] == 'COMPLETED' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', required=True)
    raise SystemExit(worker(parser.parse_args().worker))
