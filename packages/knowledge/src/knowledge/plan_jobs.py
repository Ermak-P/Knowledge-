"""Detached candidate preparation using the machine scan worker's launcher."""
import argparse
import os
import re
import time
import uuid

from . import scan_jobs
from .auto_init import read_json, write_json
from .coordination import gate
from .diagnostic_pages import compact
from .execution_lock import ExecutionLock, ProjectExecutionLock
from .project import Project, safe_path
from .store import Store
from .util import KnowledgeError, require


class Cancelled(Exception):
    pass


def folder_for(base, job):
    require(isinstance(job, str) and re.fullmatch('[0-9a-f]{32}', job), 'invalid-plan-job-id')
    return safe_path(base / job)


def read_state(base, owner, job=None):
    if job is None:
        pointer = safe_path(base / 'current.json')
        if not pointer.exists():
            return None
        job = read_json(pointer, max_bytes=8192)['job']
    folder = folder_for(base, job)
    require(safe_path(folder / 'job.json').is_file(), 'unknown-plan-job')
    return scan_jobs.worker_state(folder, scan_jobs.owned_job(folder, owner))


def summary(state):
    if state is None:
        return {'ok': True, 'state': 'NOT_STARTED', 'job_id': None}
    worker = state['state']
    progress = state.get('progress')
    if progress and worker in scan_jobs.ACTIVE and state.get('started_at'):
        progress = {**progress, 'elapsed_seconds': round(max(progress['elapsed_seconds'],
                                                            time.time() - state['started_at']), 3)}
    result = state.get('result') or {}
    report = {'ok': worker not in ('BLOCKED', 'OUTCOME_UNKNOWN'), 'state': worker,
              'worker_state': worker, 'job_id': state['job'], 'progress': progress,
              'job_diagnostics': state['diagnostics']}
    if worker in scan_jobs.TERMINAL:
        return {**report, **result}
    if worker == 'OUTCOME_UNKNOWN':
        report.update(error='plan-prepare-outcome-unknown',
                      next_action='Observe this job ID, then request explicit resume. Preparation cannot apply a plan.')
    return report


def dispatch(base, project, action, value, binding=None):
    owner = project.describe()
    job = value.get('job_id')
    if action == 'status':
        require(not ({'wait_seconds', 'execution_seconds'} & value.keys()), 'invalid-plan-job-control')
        return summary(read_state(base, owner, job))
    duration = value.get('execution_seconds')
    require(duration is None or (action != 'cancel' and type(duration) in (int, float)
            and 0 < duration < float('inf')), 'invalid-plan-execution-deadline')
    wait_seconds = value.get('wait_seconds', 2)
    require(type(wait_seconds) in (int, float) and 0 <= wait_seconds <= 30, 'invalid-plan-observation-deadline')
    if action == 'cancel' and not base.exists():
        return summary(read_state(base, owner, job))
    base.mkdir(parents=True, exist_ok=True)
    mutex = ExecutionLock(base / 'launch.lock')
    # A competing host can briefly hold the launch lock before publishing the
    # pointer. Join it when compatible instead of treating that as a new job.
    for attempt in range(40):
        try:
            mutex.acquire()
            break
        except KnowledgeError:
            if attempt == 39:
                raise
            time.sleep(.025)
    try:
        latest = read_state(base, owner)
        if action == 'cancel':
            state = read_state(base, owner, job) if job is not None else latest
            if state is None:
                return summary(state)
            response = summary(state)
            if state['state'] in scan_jobs.ACTIVE:
                marker = safe_path(folder_for(base, state['job']) / 'cancel.json')
                if not marker.exists():
                    write_json(marker, {'version': 1, 'job': state['job']})
                response['cancellation'] = 'requested at the next preparation stage'
            elif state['state'] == 'OUTCOME_UNKNOWN':
                response['cancellation'] = 'worker outcome unknown; inspect this job before requesting resume'
            else:
                response['cancellation'] = 'already terminal'
            return response
        require(action in ('prepare', 'resume'), 'invalid-push-action')
        request = {'rebuild_scan_id': value.get('rebuild_scan_id'), 'execution_seconds': duration}
        if action == 'resume':
            state = read_state(base, owner, job) if job is not None else latest
            require(state is not None, 'unknown-plan-job')
            require(latest['job'] == state['job'], 'plan-job-superseded')
            require(state['state'] in ('OUTCOME_UNKNOWN', 'CANCELLED', 'BLOCKED')
                    and not state.get('legacy_worker_may_be_active'), 'plan-job-not-resumable', summary(state))
            request = state['request'].copy()
            if 'execution_seconds' in value:
                request['execution_seconds'] = duration
        else:
            require(job is None, 'use-plan-status-with-job-id')
            state = latest
        if state and state['state'] in scan_jobs.ACTIVE:
            require(state['request'] == request and state['binding'] == binding,
                    'different-plan-prepare-active', summary(state))
            job = state['job']
        else:
            if state and state['state'] == 'OUTCOME_UNKNOWN':
                require(action == 'resume', 'plan-prepare-resume-required', summary(state))
            ProjectExecutionLock(project.root).acquire().close()
            job = state['job'] if action == 'resume' else uuid.uuid4().hex
            folder = folder_for(base, job)
            folder.mkdir(exist_ok=True)
            for prior in ('cancel.json', 'launcher.json'):
                safe_path(folder / prior).unlink(missing_ok=True)
            next_state = {'version': 1, 'job': job, 'scope': {'kind': 'plan'}, 'root': owner['root'],
                          'binding': binding, 'request': request, 'state': 'STARTING', 'pid': os.getpid(),
                          'process_stamp': scan_jobs.process_stamp(os.getpid()), 'diagnostics': str(folder),
                          'started_at': time.time(), 'progress': {'stage': 'starting', 'elapsed_seconds': 0}}
            write_json(safe_path(folder / 'job.json'), next_state)
            write_json(safe_path(base / 'current.json'), {'version': 1, 'job': job})
            scan_jobs.launch(folder, next_state, 'knowledge.plan_jobs')
    finally:
        mutex.close()
    deadline = time.monotonic() + wait_seconds
    while True:
        state = read_state(base, owner, job)
        if state['state'] not in scan_jobs.ACTIVE or time.monotonic() >= deadline:
            return summary(state)
        time.sleep(.05)


def worker(folder):
    from pathlib import Path
    from .project_commands import project_configuration, push, ready

    folder = safe_path(Path(folder))
    state = scan_jobs.owned_job(folder)
    project = Project(state['root'])
    scan_jobs.owned_job(folder, project.describe())
    require(folder.parents[1].name == project.identity, 'plan-job-root-binding-mismatch')
    state.update(state='RUNNING', pid=os.getpid(), process_stamp=scan_jobs.process_stamp(os.getpid()))
    metadata = safe_path(folder / 'job.json')
    marker = safe_path(folder / 'cancel.json')
    started = time.monotonic()
    duration = state['request'].get('execution_seconds')
    write_json(metadata, state)
    lease = None

    def progress(stage, **counts):
        elapsed = time.monotonic()-started
        if stage not in ('prepared', 'awaiting-exact-approval', 'blocked', 'failed'):
            if marker.exists() and read_json(marker, max_bytes=8192).get('job') == state['job']:
                raise Cancelled('cancellation-requested')
            if duration is not None and elapsed >= duration:
                raise Cancelled('plan-execution-deadline')
        state['progress'] = dict(stage=stage, elapsed_seconds=round(elapsed, 3), **counts)
        write_json(metadata, state)

    try:
        lease = ProjectExecutionLock(project.root).acquire()
        with gate(project.root, exclusive=True):
            project_configuration(folder.parents[4], project)
            progress('validating-store')
            store = Store(project.root)
            ready(store)
            result = push(store, project.root, folder.parent.parent, state['binding'], state['request'], observe_progress=progress)
        state.update(state='COMPLETED' if result['ok'] else 'BLOCKED', result=result)
    except Cancelled as error:
        state.update(state='CANCELLED', result={'ok': True, 'state': 'CANCELLED',
                     'reason': str(error),
                     'next_action': 'Use resume with this job ID to retry preparation.'})
    except Exception as error:
        state.update(state='BLOCKED', result={'ok': False, 'state': 'BLOCKED',
                     'error': getattr(error, 'code', 'plan-prepare-worker-failed'),
                     'details': compact(getattr(error, 'details', None)),
                     'next_action': 'Inspect progress and resolve the blocker before requesting resume.'})
        if not isinstance(error, KnowledgeError):
            import traceback
            traceback.print_exc()
    finally:
        if lease:
            lease.close()
        write_json(metadata, state)
    return 0 if state['state'] == 'COMPLETED' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', required=True)
    raise SystemExit(worker(parser.parse_args().worker))
