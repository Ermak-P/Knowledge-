"""Durable external scan workers. A host request starts/observes, never owns it.

Unknown outcomes stop. Status is observation, not an automatic retry policy.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
from .auto_init import run, write_json, ScanError
from .execution_lock import ExecutionLock, ProjectExecutionLock
from .project import safe_path
from .util import require, loads

_children = {}


def alive(pid):
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
    try: os.kill(pid, 0); return True
    except ProcessLookupError: return False
    except PermissionError: return True


def status(folder):
    folder = Path(folder)
    state = loads(safe_path(folder / 'job.json').read_text(encoding='utf-8'))
    require(state.get('version') == 1 and type(state.get('pid')) is int and state['pid'] > 0 and state.get('state') in ('STARTING', 'RUNNING', 'COMPLETED', 'BLOCKED'), 'invalid-scan-job-state')
    child = _children.get(state['pid'])
    if child is not None and child.poll() is not None:
        del _children[state['pid']]
    if state['state'] in ('STARTING', 'RUNNING') and not alive(state['pid']):
        return {**state, 'state': 'OUTCOME_UNKNOWN', 'next_action': 'Observe scan-status and diagnostics; explicitly resume only after determining the outcome.'}
    checkpoint = folder / 'checkpoint.json'
    if checkpoint.exists(): state['scan_id'] = loads(checkpoint.read_text(encoding='utf-8'))['scan_id']
    last = folder / 'last-result.json'
    if last.exists():
        value = loads(last.read_text(encoding='utf-8'))
        state.update(identity_verification=value.get('identity_verification'), coverage_complete=value.get('complete', False), work=value.get('work'), candidates=len(value.get('candidates', [])),
                     gaps=len(value.get('gaps', [])), semantic_coverage_complete=False)
    return state


def start(folder, root, scope, binding, max_files=100, resume=False, fresh=False):
    folder = safe_path(Path(folder))
    folder.mkdir(parents=True, exist_ok=True)
    lease = ExecutionLock(folder / 'launch.lock').acquire()
    try:
        metadata = folder / 'job.json'
        if metadata.exists():
            old = status(folder)
            if old['state'] in ('STARTING', 'RUNNING'):
                require(old['binding'] == binding and old['scope'] == scope, 'active-scan-configuration-drift')
                return old
            # A terminal error/unknown outcome requires explicit observation and
            # resume. Normal repeated successful calls can verify current source.
            require(old['state'] == 'COMPLETED' or resume or fresh, 'scan-recovery-required', old)
            if old['state'] != 'COMPLETED' and old.get('chunk_started', True) and not (folder / 'checkpoint.json').exists():
                require(fresh, 'scan-outcome-observation-required', {'root': str(root), 'next_action': 'Use knowledge.cli scan-status for this root and inspect diagnostics before choosing explicit fresh; no automatic new scan.'})
        previous_success = metadata.exists() and old['state'] == 'COMPLETED'
        require(type(max_files) is int and 1 <= max_files <= 10000, 'invalid-scan-bound')
        state = {'version': 1, 'job': uuid.uuid4().hex, 'root': str(root), 'scope': scope, 'binding': binding,
                 'max_files': max_files, 'resume': resume, 'chunk_started': False, 'previous_success': previous_success or fresh, 'state': 'STARTING', 'pid': os.getpid(), 'diagnostics': str(folder)}
        write_json(metadata, state)
        log = (folder / 'progress.log').open('ab')
        try:
            options = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS} if os.name == 'nt' else {'start_new_session': True}
            process = subprocess.Popen([sys.executable, '-I', '-B', '-m', 'knowledge.scan_jobs', '--worker', str(folder)],
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, close_fds=True, **options)
        finally: log.close()
        _children[process.pid] = process
        # The worker writes its own PID before doing anything. Parent waits only
        # for that durable handshake; no scan is tied to this request's deadline.
        import time
        for _ in range(100):
            current = loads(metadata.read_text(encoding='utf-8'))
            if current['pid'] == process.pid: return current
            if process.poll() is not None: break
            time.sleep(.02)
        return {**state, 'state': 'STARTING', 'next_action': 'Check status; do not start a second worker.'}
    finally: lease.close()


def worker(folder):
    folder = Path(folder)
    state = loads((folder / 'job.json').read_text(encoding='utf-8'))
    state.update(state='RUNNING', pid=os.getpid())
    write_json(folder / 'job.json', state)
    lease = None
    try:
        from .project import Project
        require(Project(state['root']).describe() == state['binding']['root'], 'scan-job-root-binding-mismatch')
        lease = ProjectExecutionLock(state['root']).acquire()
        scope = state['scope']
        # Fresh asks for the current snapshot, preserving durable chunks when
        # unchanged. Explicit resume uses the existing checkpoint ID.
        checkpoint = folder / 'checkpoint.json'
        fresh = checkpoint.exists() and state.get('previous_success', False)
        from .store import Store
        store = Store(state['root'])
        before = {row['id'] for row in store.status()['queue']}
        state['chunk_started'] = True
        write_json(folder / 'job.json', state)
        run(state['root'], folder, max_files=state['max_files'], fresh=fresh,
            base=scope.get('base'), head=scope.get('head'), incremental=scope['kind'] == 'incremental', retry_blocked=bool(state.get('resume') and checkpoint.exists() and not fresh))
        after = {row['id'] for row in store.status()['queue']}
        observed = loads((folder / 'last-result.json').read_text(encoding='utf-8'))
        reconciliation = observed['reconciliation']
        state.update(state='COMPLETED', queued_added=len(after - before),
                     skipped_existing=max(0, len(observed.get('candidates', [])) - len(after - before)),
                     reconciliation={'claims': len(reconciliation['claims']), 'classifications': {name: sum(row['classification'] == name for row in reconciliation['claims']) for name in sorted({row['classification'] for row in reconciliation['claims']})},
                                     'negative_evidence_gaps': len(reconciliation.get('negative_evidence_gaps', [])), 'retirement_proposal_available': reconciliation.get('proposal') is not None})
    except (ScanError, OSError, ValueError, RuntimeError) as error:
        state.update(state='BLOCKED', error=str(error)[:500], next_action='Run knowledge.cli scan-status --root <reported-root>; inspect diagnostics. After observing the outcome/fixing the cause, invoke the original command with {"resume":true} or {"fresh":true} for a changed snapshot. Never delete source to bypass coverage.')
    except Exception as error:
        state.update(state='BLOCKED', error=getattr(error, 'code', type(error).__name__), next_action='Inspect diagnostics; outcome may be unknown. No automatic retry.')
    finally:
        if lease: lease.close()
        write_json(folder / 'job.json', state)
    return 0 if state['state'] == 'COMPLETED' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', required=True)
    raise SystemExit(worker(parser.parse_args().worker))
