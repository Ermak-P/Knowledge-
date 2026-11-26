"""Cross-store maintenance gate. Knowledge owns this dependency-free boundary.

Lock order: execution lease (maintenance only), gate, SQLite. Ordinary Knowledge
transactions share the gate; maintenance holds it exclusively. Reentrance is
thread local, permitting validation/backup under an exclusive maintenance freeze.
"""
from contextlib import contextmanager
from pathlib import Path
import os,threading
from .project import safe_path
from .runtime_paths import CONTROL_LOCK, RuntimePaths
from .util import require,KnowledgeError
_local=threading.local()

@contextmanager
def gate(root,exclusive=False,recovery=False,readonly=False,global_store=False,migration=False):
    root=Path(root);key=os.path.normcase(str(root.absolute()))
    if exclusive and not migration:
        from .access import require_maintainer
        require_maintainer()
    held=getattr(_local,'held',{});old=held.get(key)
    if old:
        require(not exclusive or old=='exclusive','maintenance-busy','active transaction cannot become an exclusive freeze')
        yield;return
    runtime = RuntimePaths(root)
    path, fence = runtime.control, runtime.fence
    if global_store:
        path, fence = root / CONTROL_LOCK, root / '.maintenance/active.json'
    elif readonly and (root / CONTROL_LOCK).exists():
        # Older stores can be consumed without an offline upgrade.
        path = root / CONTROL_LOCK
    elif not (readonly or migration):
        runtime.check_legacy()
    safe_path(path)
    safe_path(fence)
    legacy_fence = safe_path(root / '.maintenance/active.json')
    if readonly and not path.exists():
        require(not (fence.exists() or legacy_fence.exists()), 'maintenance-recovery-required')
        yield
        require(not (fence.exists() or legacy_fence.exists()), 'maintenance-recovery-required')
        return
    if not readonly:
        if not global_store and not runtime.base.exists():
            from .runtime_paths import ignore_runtime
            ignore_runtime(runtime)
        path.parent.mkdir(parents=True, exist_ok=True)
    if os.name=='nt':
        from .windows_lock import RangeLock
        lock=RangeLock(path,exclusive,readonly)
        lock.acquire()
    else:
        import fcntl
        fd=os.open(path,os.O_RDONLY if readonly else os.O_RDWR|os.O_CREAT,0o600)
        try:fcntl.flock(fd,(fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)|fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd);raise KnowledgeError('maintenance-busy')
    _local.held={**held,key:'exclusive' if exclusive else 'shared'}
    try:
        require(recovery or not (fence.exists() or legacy_fence.exists()), 'maintenance-recovery-required')
        if not (readonly or migration or global_store):
            runtime.check_legacy()
        yield
    finally:
        _local.held=held
        if os.name=='nt':lock.close()
        else:os.close(fd)
