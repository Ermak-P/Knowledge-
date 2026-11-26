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
from .auto_init import run, write_json, read_json, read_checkpoint, ScanError, ScanCancelled
from .execution_lock import ExecutionLock, ProjectExecutionLock
from .project import safe_path
from .util import require, loads

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
    except ProcessLookupError: return False
    except PermissionError: return True


def status(folder):
    folder = Path(folder)
    state = read_json(safe_path(folder / 'job.json'))
    require(state.get('version') == 1 and type(state.get('pid')) is int and state['pid'] > 0 and state.get('state') in ('STARTING', 'RUNNING', 'COMPLETED', 'COMPLETED_WITH_GAPS', 'CANCELLED', 'BLOCKED'), 'invalid-scan-job-state')
    launcher = folder / 'launcher.json'
    launched = read_json(safe_path(launcher)) if launcher.exists() else {}
    launcher_pid = launched.get('pid') if launched.get('job') == state['job'] else None
    require(launcher_pid is None or (type(launcher_pid) is int and launcher_pid > 0), 'invalid-scan-launcher-state')
    child = _children.get(launcher_pid)
    if child is not None and child.poll() is not None:
        del _children[launcher_pid]
    living = alive(state['pid'],state.get('process_stamp')) or (launcher_pid is not None and alive(launcher_pid,launched.get('process_stamp')))
    if state['state'] in ('STARTING', 'RUNNING') and not living:
        return {**state, 'state': 'OUTCOME_UNKNOWN', 'next_action': 'Observe scan-status and diagnostics; explicitly resume only after determining the outcome.'}
    if state['state'] in ('COMPLETED', 'COMPLETED_WITH_GAPS', 'CANCELLED', 'BLOCKED') and living:
        # A Windows venv redirector can outlive its Python worker briefly and
        # still own stdout. Completion includes releasing both owned processes.
        state = {**state, 'state': 'RUNNING', 'phase': 'FINALIZING'}
    checkpoint = folder / 'checkpoint.json'
    if checkpoint.exists():
        try:state['scan_id']=read_checkpoint(safe_path(checkpoint))['scan_id']
        except (ScanError,ValueError,OSError) as error:
            state['checkpoint_error']=str(error)[:300]
            state['next_action']='Observe diagnostics section=scans; explicitly resume with verified observed_scan_id, or choose fresh. Corrupt checkpoint is never trusted.'
    last = folder / 'progress.json'
    if last.exists():
        value = read_json(last)
        if value.get('job')==state['job']:
            state.update(identity_verification=value.get('identity_verification'), coverage_complete=value.get('complete', False), work=value.get('work'), candidates=value.get('candidates',0),
                         counters=value.get('counters'), processing_complete=(value.get('work') or {}).get('remaining_files')==0,
                         gaps=value.get('gaps',0),source=value.get('source'), source_verified=value.get('source_verified',False), semantic_coverage_complete=False)
    cancellation=folder / 'cancel.json'
    if state['state'] in ('STARTING','RUNNING') and cancellation.exists() and read_json(cancellation).get('job')==state['job']:
        state['phase']='CANCELLING_AT_CHUNK_BOUNDARY'
    return state


def cancel(folder):
    folder=safe_path(Path(folder))
    lease=ExecutionLock(folder / 'launch.lock').acquire()
    try:
        state=status(folder)
        if state['state'] in ('STARTING','RUNNING'):
            write_json(folder / 'cancel.json', {'version':1,'job':state['job']})
        return {'ok':True,'state':state['state'],'job':state['job'],
                'cancellation':'requested at durable chunk boundary' if state['state'] in ('STARTING','RUNNING') else 'already terminal; no process terminated'}
    finally:lease.close()


def start(folder, root, scope, binding, max_files=100, resume=False, fresh=False, observed_scan_id=None):
    folder = safe_path(Path(folder))
    folder.mkdir(parents=True, exist_ok=True)
    lease = ExecutionLock(folder / 'launch.lock').acquire()
    try:
        if observed_scan_id is not None:
            from . import discovery
            from .store import Store
            require(resume and not fresh and isinstance(observed_scan_id,str) and len(observed_scan_id)==64 and all(c in '0123456789abcdef' for c in observed_scan_id),'invalid-observed-scan-resume')
            found=discovery.status(Store(root),observed_scan_id)['scans'];require(len(found)==1,'unknown-observed-scan')
            observed=found[0];current=discovery.inventory(root,scope.get('base'),scope.get('head'))
            require(observed['snapshot']['identity']==current['identity'] and bool(observed.get('incremental'))==(scope['kind']=='incremental')
                    and observed['snapshot'].get('delta')==current.get('delta'),'observed-scan-incompatible')
        metadata = folder / 'job.json'
        if metadata.exists():
            old = status(folder)
            if resume and not fresh:require(old['binding']==binding and old['scope']==scope,'resume-scan-configuration-drift')
            if old['state'] in ('STARTING', 'RUNNING'):
                require(not fresh,'scan-active-cancel-before-fresh')
                require(old['binding'] == binding and old['scope'] == scope, 'active-scan-configuration-drift')
                return old
            # A terminal error/unknown outcome requires explicit observation and
            # resume. Normal repeated successful calls can verify current source.
            require(old['state'] == 'COMPLETED' or resume or fresh, 'scan-recovery-required', old)
            if old['state'] != 'COMPLETED' and old.get('chunk_started', True) and not (folder / 'checkpoint.json').exists():
                require(fresh or observed_scan_id is not None, 'scan-outcome-observation-required', {'root': str(root), 'next_action': 'Use MCP diagnostics section=scans to observe this root before explicit observed_scan_id resume or fresh; no automatic new scan.'})
        previous_success = metadata.exists() and old['state'] == 'COMPLETED'
        require(type(max_files) is int and 1 <= max_files <= 10000, 'invalid-scan-bound')
        state = {'version': 1, 'job': uuid.uuid4().hex, 'root': str(root), 'scope': scope, 'binding': binding,
                 'max_files': max_files, 'resume': resume, 'fresh':fresh,'observed_scan_id':observed_scan_id,'chunk_started': False, 'previous_success': previous_success, 'state': 'STARTING', 'pid': os.getpid(), 'process_stamp':process_stamp(os.getpid()), 'diagnostics': str(folder)}
        write_json(metadata, state)
        log = (folder / 'progress.log').open('ab')
        try:
            flags=(subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS) if os.name=='nt' else 0
            if os.name=='nt' and os.environ.get('KNOWLEDGE_OWNED_JOB')=='1':flags |= subprocess.CREATE_BREAKAWAY_FROM_JOB
            options = {'creationflags': flags} if os.name == 'nt' else {'start_new_session': True}
            # Isolated mode ignores PYTHONUTF8/PYTHONIOENCODING. Set the
            # interpreter flag explicitly for Unicode paths in redirected logs.
            process = subprocess.Popen([sys.executable, '-I', '-B', '-X', 'utf8', '-m', 'knowledge.scan_jobs', '--worker', str(folder)],
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, close_fds=True, **options)
        finally: log.close()
        _children[process.pid] = process
        write_json(folder / 'launcher.json', {'version': 1, 'job': state['job'], 'pid': process.pid,'process_stamp':process_stamp(process.pid)})
        # The worker writes its own PID before doing anything. Parent waits only
        # for that durable handshake; no scan is tied to this request's deadline.
        import time
        for _ in range(100):
            current = read_json(metadata)
            if current['job'] == state['job'] and current['pid'] != state['pid']: return current
            if process.poll() is not None: break
            time.sleep(.02)
        return {**state, 'state': 'STARTING', 'next_action': 'Check status; do not start a second worker.'}
    finally: lease.close()


def worker(folder):
    folder = Path(folder)
    state = read_json(folder / 'job.json')
    state.update(state='RUNNING', pid=os.getpid(),process_stamp=process_stamp(os.getpid()))
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
        fresh = state.get('fresh', False)
        from .store import Store
        store = Store(state['root'])
        before = {row['id'] for row in store.status()['queue']}
        state['chunk_started'] = True
        write_json(folder / 'job.json', state)
        observed_id=state.get('observed_scan_id')
        run(state['root'], folder,scan_id=observed_id, max_files=state['max_files'], fresh=fresh,
            base=scope.get('base'), head=scope.get('head'), incremental=scope['kind'] == 'incremental', retry_blocked=bool(state.get('resume') and (checkpoint.exists() or observed_id) and not fresh),
            cancel_path=folder / 'cancel.json',cancel_job=state['job'],refresh=state.get('previous_success',False),persistent=True)
        after = {row['id'] for row in store.status()['queue']}
        observed = read_json(folder / 'last-result.json')
        reconciliation = observed['reconciliation']
        state.update(state='COMPLETED' if observed['complete'] else 'COMPLETED_WITH_GAPS', queued_added=len(after - before),
                     skipped_existing=max(0, len(observed.get('candidates', [])) - len(after - before)),
                     reconciliation={'claims': len(reconciliation['claims']), 'classifications': {name: sum(row['classification'] == name for row in reconciliation['claims']) for name in sorted({row['classification'] for row in reconciliation['claims']})},
                                     'negative_evidence_gaps': len(reconciliation.get('negative_evidence_gaps', [])), 'retirement_proposal_available': reconciliation.get('proposal') is not None})
    except ScanCancelled as error:
        state.update(state='CANCELLED',chunk_started=(folder/'checkpoint.json').exists(),error=str(error),next_action='Resume the compatible checkpoint explicitly, or choose fresh for a new execution.')
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
