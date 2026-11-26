"""Offline relocation of legacy project coordination and maintenance paths."""
from contextlib import contextmanager
import os

from .access import require_maintainer
from .coordination import gate
from .execution_lock import ExecutionLock, ProjectExecutionLock
from .project import Project, safe_path, safe_tree
from .runtime_paths import CONTROL_LOCK, WRITER_LOCK, ignore_runtime
from .util import KnowledgeError, require


@contextmanager
def legacy_control(path):
    if path.exists():
        if os.name == 'nt':
            from .windows_lock import RangeLock

            lock = RangeLock(path, exclusive=True)
            lock.acquire()
            try:
                yield
            finally:
                lock.close()
        else:
            import fcntl

            with path.open('r+b') as stream:
                try:
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as error:
                    raise KnowledgeError('maintenance-busy') from error
                yield
    else:
        yield


def fault(phase):
    pass


def migrate(root, offline=False):
    require_maintainer()
    require(offline, 'runtime-migration-requires-offline',
            {'next_action': 'Stop all versions of Knowledge and Harness, including detached workers, then rerun with --offline.'})
    project = Project(root)
    runtime = project.runtime
    writer, control = (safe_path(project.root / name) for name in (WRITER_LOCK, CONTROL_LOCK))
    previous = project.root / '.maintenance'
    safe_tree(previous)
    safe_tree(runtime.maintenance)
    require(not previous.exists() or previous.is_dir(), 'invalid-legacy-maintenance-directory')
    lease = ProjectExecutionLock(project.root, migration=True)
    legacy = ExecutionLock(writer)
    migrated = []
    try:
        lease.acquire()
        with gate(project.root, exclusive=True, recovery=True, migration=True):
            try:
                if writer.exists():
                    legacy.acquire()
                with legacy_control(control):
                    for path in (writer, control):
                        require(not path.exists() or (path.is_file() and path.stat().st_size == 0),
                                'legacy-runtime-lock-has-data', {'path': path.name})
                    if previous.exists():
                        require(not runtime.maintenance.exists(), 'runtime-migration-destination-conflict',
                                {'source': str(previous), 'destination': str(runtime.maintenance)})
                        previous.rename(runtime.maintenance)
                        migrated.append(previous.name)
                        fault('maintenance-moved')
                    if os.name != 'nt':
                        for path in (control, writer):
                            if path.exists():
                                path.unlink()
                                migrated.append(path.name)
                                fault('legacy-lock-removed')
            finally:
                legacy.close()
            if os.name == 'nt':
                # A different open handle prevents deletion on Windows.
                # The new control lock remains held through this interval.
                for path in (control, writer):
                    if path.exists():
                        path.unlink()
                        migrated.append(path.name)
                        fault('legacy-lock-removed')
            ignore_runtime(runtime)
            runtime.check_legacy()
    except KnowledgeError as error:
        if error.code in ('maintenance-busy', 'project-writer-busy', 'maintenance-lock-open-failed'):
            raise KnowledgeError('runtime-migration-active-lock', {
                'next_action': 'Stop all Knowledge and Harness processes and retry the offline migration.'}) from error
        raise
    finally:
        lease.close()
    return {'ok': True, 'state': 'migrated' if migrated else 'already-migrated', 'artifacts': migrated,
            'maintenance_recovery_required': runtime.fence.exists()}
