"""Cross-store maintenance gate. Knowledge owns this dependency-free boundary.

Lock order: execution lease (maintenance only), gate, SQLite. Ordinary Knowledge
transactions share the gate; maintenance holds it exclusively. Reentrance is
thread local, permitting validation/backup under an exclusive maintenance freeze.
"""
from contextlib import contextmanager
from pathlib import Path
import os,threading
from .project import safe_path
from .util import require,KnowledgeError
_local=threading.local()

@contextmanager
def gate(root,exclusive=False,recovery=False):
    root=Path(root);key=os.path.normcase(str(root.absolute()))
    held=getattr(_local,'held',{});old=held.get(key)
    if old:
        require(not exclusive or old=='exclusive','maintenance-busy','active transaction cannot become an exclusive freeze')
        yield;return
    path=root/'.knowledge-control.lock';safe_path(path)
    if os.name=='nt':
        from .windows_lock import RangeLock
        lock=RangeLock(path,exclusive)
        lock.acquire()
    else:
        import fcntl
        fd=os.open(path,os.O_RDWR|os.O_CREAT,0o600)
        try:fcntl.flock(fd,(fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)|fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd);raise KnowledgeError('maintenance-busy')
    _local.held={**held,key:'exclusive' if exclusive else 'shared'}
    try:
        fence=root/'.maintenance/active.json';safe_path(fence)
        require(recovery or not fence.exists(),'maintenance-recovery-required')
        yield
    finally:
        _local.held=held
        if os.name=='nt':lock.close()
        else:os.close(fd)
