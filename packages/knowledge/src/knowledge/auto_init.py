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
import time
from contextlib import contextmanager


class ScanError(Exception):
    pass


class ScanCancelled(ScanError):
    pass


@contextmanager
def lease_options(handles):
    """A committed chunk child retains writer ownership if its worker dies."""
    if not handles:yield {};return
    if os.name!='nt':yield {'pass_fds':tuple(handles)};return
    previous={handle:os.get_handle_inheritable(handle) for handle in handles}
    try:
        for handle in handles:os.set_handle_inheritable(handle,True)
        startup=subprocess.STARTUPINFO();startup.lpAttributeList={'handle_list':list(handles)}
        yield {'startupinfo':startup,'close_fds':True}
    finally:
        for handle,inherited in previous.items():os.set_handle_inheritable(handle,inherited)


def read_json(path):
    """Windows readers share delete so atomic writers can replace metadata."""
    if os.name != 'nt': return json.loads(Path(path).read_text(encoding='utf-8'))
    import ctypes
    import msvcrt
    from .windows_lock import k, INVALID
    for attempt in range(20):
        handle = k.CreateFileW(str(path), 0x80000000, 7, None, 3, 0x80, None)
        if handle != INVALID: break
        error = ctypes.WinError(ctypes.get_last_error())
        if error.winerror not in (5, 32, 33) or attempt == 19: raise error
        time.sleep(.01)
    try: fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException: k.CloseHandle(handle); raise
    with os.fdopen(fd, 'r', encoding='utf-8') as stream: return json.load(stream)


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
        for attempt in range(20):
            try: os.replace(temporary, path); break
            except PermissionError as error:
                if os.name != 'nt' or getattr(error,'winerror',None) not in (5,32,33) or attempt == 19: raise
                time.sleep(.01)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def inside(path, root):
    return path == root or root in path.parents


def read_checkpoint(path):
    saved=read_json(path)
    if not isinstance(saved,dict):raise ScanError('Invalid checkpoint object.')
    if saved.get('version')==2:
        body={k:v for k,v in saved.items() if k!='checksum'}
        if saved.get('checksum')!=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest():
            raise ScanError('Corrupt checkpoint checksum; observe diagnostics section=scans before explicit recovery.')
    elif saved.get('version')!=1:raise ScanError('Unsupported checkpoint version.')
    scan_id=saved.get('scan_id')
    if not isinstance(scan_id,str) or len(scan_id)!=64 or any(c not in '0123456789abcdef' for c in scan_id):
        raise ScanError('Invalid checkpoint scan_id; observe diagnostics section=scans.')
    return saved


def run(root, output, scan_id=None, max_files=100, max_calls=10000,
        command_timeout=600, fresh=False, base=None, head=None, incremental=False, retry_blocked=False,
        cancel_path=None, cancel_job=None, refresh=False, lease_fds=(), persistent=False):
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
    if not scan_id and not fresh and not refresh and checkpoint.exists():
        saved = read_checkpoint(checkpoint)
        if os.path.normcase(saved.get('root', '')) != os.path.normcase(str(root)) or saved.get('scope', {'base': None, 'head': None, 'incremental': False}) != {'base': base, 'head': head, 'incremental': incremental}:
            raise ScanError('Checkpoint belongs to a different root; choose another --output.')
        scan_id = saved.get('scan_id')
        if not isinstance(scan_id, str) or not scan_id.strip():
            raise ScanError('Invalid checkpoint scan_id; inspect checkpoint.json.')
    if retry_blocked and (not scan_id or fresh):
        raise ScanError('--retry-blocked requires the observed scan ID/checkpoint and cannot be combined with --fresh.')
    print('Knowledge scan helper 2', flush=True)
    print('Project: ' + str(root), flush=True)
    print('Diagnostics: ' + str(output), flush=True)
    if scan_id:
        print('Scan ID: ' + short_message(scan_id), flush=True)
    previous = None
    session = None
    if persistent:
        from .discovery import ScanSession
        from .store import Store
        from . import lifecycle
        from .util import KnowledgeError

        store = Store(root)
        if not store.path.exists():
            store.init()
            lifecycle.upgrade(store, lifecycle.upgrade_preview(store)['fingerprint'])
        session = ScanSession(store)
    environment = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}
    for number in range(1, max_calls + 1):
        if cancel_path and Path(cancel_path).exists() and read_json(cancel_path).get('job') == cancel_job:
            raise ScanCancelled('Scan cancelled at a durable chunk boundary; checkpoint and candidates preserved.')
        returncode = 0
        if session is not None:
            started = time.monotonic()
            try:
                result = session.scan(scan_id, max_files, base, head, fresh and number == 1,
                                      incremental, retry_blocked and number == 1, reconcile_result=True)
            except KnowledgeError as error:
                result = {'ok': False, 'error': error.code, 'details': error.details}
            if time.monotonic() - started > command_timeout:
                write_json(output / 'last-error.json', {'error': 'command-timeout-outcome-unknown',
                           'scan_id': scan_id, 'timeout_seconds': command_timeout})
                raise ScanError('Chunk exceeded the command timeout. Inspect Knowledge scan-status before resuming.')
            if result.get('ok') and not result['processing_complete']:
                # Complete per-file diagnostics are available through scan-status.
                result = {**{k: result[k] for k in ('ok','id','complete','work','counters','candidates')},
                          'source_verified': False, 'snapshot': {k: result['snapshot'].get(k) for k in ('identity','revision','snapshot_kind','coverage_errors')},
                          'coverage': {p: result['coverage'][p] for p in result['work']['paths_this_call']
                                       if result['coverage'][p]['status'] == 'blocked'}}
        else:
            command = [sys.executable, '-I', '-B', '-X', 'utf8', '-m', 'knowledge.cli', 'knowledge-init',
                       '--root', str(root), '--max-files', str(max_files)]
            if number == 1 and retry_blocked:
                command.append('--retry-blocked')
            if number == 1 and fresh:
                command.append('--restart')
            if incremental:
                command.append('--incremental')
            if base is not None:
                command.extend(['--base', base, '--head', head])
            if scan_id:
                command.extend(['--scan-id', scan_id])
            try:
                with lease_options(lease_fds) as ownership:
                    process = subprocess.run(command, stdin=subprocess.DEVNULL,stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                             encoding='utf-8', errors='strict', env=environment,
                                             timeout=command_timeout, check=False,**ownership)
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
            returncode = process.returncode
        write_json(output / 'last-result.json', result)
        if not isinstance(result, dict):
            raise ScanError('Unexpected CLI JSON shape; expected an object.')
        if returncode != 0 or result.get('ok') is not True:
            raise ScanError('Knowledge failed: ' + short_message(result.get('error', 'exit ' + str(returncode))))
        returned_id = result.get('id')
        if not isinstance(returned_id, str) or not returned_id.strip():
            raise ScanError('Successful response has no scan id; unsupported CLI response.')
        if scan_id and returned_id != scan_id:
            raise ScanError('CLI changed the scan id unexpectedly; stopped.')
        first_id = scan_id is None
        scan_id = returned_id
        saved = {'version': 2, 'root': str(root), 'scan_id': scan_id, 'scope': {'base': base, 'head': head, 'incremental': incremental}}
        saved['checksum'] = hashlib.sha256(json.dumps(saved,sort_keys=True).encode()).hexdigest()
        write_json(checkpoint, saved)
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
        write_json(output / 'progress.json', {'version':1,'job':cancel_job,'scan_id':scan_id,
                   'source':{'identity':snapshot['identity'],'revision':snapshot['revision'],'kind':snapshot['snapshot_kind']},
                   'complete':result.get('complete',False),'source_verified':result.get('source_verified',False),'counters':result.get('counters'),
                   'work':{k:v for k,v in result.get('work',{}).items() if k!='paths_this_call'},
                   'candidates':len(result.get('candidates',[])), 'gaps':len(result.get('gaps',[])),
                   'identity_verification':({k:v for k,v in result['identity_verification'].items() if k not in ('missing_files','ambiguous_ids')} |
                        {'missing_file_count':len(result['identity_verification'].get('missing_files',[])),
                         'ambiguous_id_count':len(result['identity_verification'].get('ambiguous_ids',[]))}) if result.get('identity_verification') else None})
        blocked = {path: item for path, item in coverage.items() if item.get('status') == 'blocked'}
        coverage_errors = snapshot.get('coverage_errors')
        # Keep redirected/non-interactive output small as well as terminal output.
        if number == 1 or number % 25 == 0 or complete or remaining == 0:
            print('Chunk {0}: processed={1}, remaining={2}, extracted={3}, blocked={4}'.format(
                number, processed, remaining, extracted, len(blocked)), flush=True)
        if blocked or coverage_errors:
            write_json(output / 'coverage-errors.json', {
                'scan_id': scan_id, 'coverage_errors': coverage_errors, 'blocked': blocked})
        if complete or remaining == 0:
            if remaining or any(item.get('status') == 'not-analyzed' for item in coverage.values()):
                raise ScanError('Inconsistent complete=true response; files are still pending.')
            reconciliation = result.get('reconciliation')
            if not isinstance(reconciliation, dict) or reconciliation.get('ok') is not True or reconciliation.get('complete') is not complete or reconciliation.get('scan') != scan_id:
                raise ScanError('Scan finished but reconciliation was not confirmed; inspect last-result.json.')
            gaps = result.get('gaps', [])
            print(('Completed scan: ' if complete else 'COMPLETED_WITH_GAPS: ') + short_message(scan_id), flush=True)
            if gaps:
                print('Review required: {0} lexical ambiguity/gap entries in last-result.json.'.format(len(gaps)), flush=True)
            print('Coverage completion is not semantic completeness. Candidates were not approved/applied.', flush=True)
            return 0 if complete else 2
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
    parser.add_argument('--base')
    parser.add_argument('--head')
    parser.add_argument('--retry-blocked', action='store_true', help='Explicitly retry eligible transient read failures of the observed scan once; never bypass snapshot errors')
    parser.add_argument('--incremental', action='store_true')
    parser.add_argument('--scan-id', help='Continue an already started scan')
    parser.add_argument('--max-files', type=positive, default=100)
    parser.add_argument('--max-calls', type=positive, default=10000)
    parser.add_argument('--command-timeout', type=positive, default=600, help='Seconds per CLI call')
    parser.add_argument('--output', help='Diagnostic directory outside the project')
    parser.add_argument('--fresh', action='store_true', help='Create a new execution for the current snapshot; preserve canonical knowledge, candidates and prior scans')
    args = parser.parse_args()
    if args.max_files > 10000:
        parser.error('--max-files cannot exceed 10000')
    if args.fresh and args.scan_id:
        parser.error('--fresh and --scan-id cannot be used together')
    root_key = os.path.normcase(str(Path(args.root).resolve()))
    key = hashlib.sha256(root_key.encode('utf-8')).hexdigest()[:20]
    base = Path(os.environ.get('LOCALAPPDATA') or tempfile.gettempdir())
    output = args.output or str(base / 'Knowledge' / 'scan-helper' / key)
    from .util import KnowledgeError
    try:
        return run(args.root, output, args.scan_id, args.max_files, args.max_calls,
                   args.command_timeout, args.fresh, args.base, args.head, args.incremental,
                   args.retry_blocked, persistent=True)
    except KeyboardInterrupt:
        print('\nInterrupted. Inspect diagnostics/scan-status before resuming; '
              'a completed chunk remains durable.', file=sys.stderr)
        return 130
    except (ScanError, KnowledgeError, OSError, ValueError, UnicodeError) as error:
        print('STOP: ' + short_message(error), file=sys.stderr)
        print('Full diagnostics: ' + str(Path(output).resolve()), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
