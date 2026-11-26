"""Exclusive inheritable execution ownership shared by Harness and maintenance."""
import os
from pathlib import Path
from .project import safe_path
from .runtime_paths import RuntimePaths
from .util import KnowledgeError,require

class ExecutionLock:
    def __init__(self,path):self.path=Path(path);self.fd=None
    def acquire(self):
        safe_path(self.path)
        if os.name=='nt':
            from .windows_lock import k,INVALID
            self.fd=k.CreateFileW(str(self.path),0xC0000000,4,None,4,0x80,None)
            if self.fd==INVALID:self.fd=None;raise KnowledgeError('project-writer-busy')
        else:
            import fcntl
            require(Path('/proc/self/stat').is_file(),'execution-host-unsupported')
            self.fd=os.open(self.path,os.O_RDWR|os.O_CREAT,0o600)
            try:fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                os.close(self.fd);self.fd=None;raise KnowledgeError('project-writer-busy')
        return self
    def close(self):
        if self.fd is not None:
            if os.name=='nt':
                from .windows_lock import k
                k.CloseHandle(self.fd)
            else:os.close(self.fd)
            self.fd=None

class ProjectExecutionLock:
    """Stable root ownership plus the prior executor's metadata-file lease."""
    def __init__(self,root,migration=False):
        root=Path(root)
        self.runtime = RuntimePaths(root)
        self.migration = migration
        self.stable=ExecutionLock(self.runtime.writer)
        self.legacy=ExecutionLock(root/'.harness/writer.lock') if (root/'.harness').is_dir() else None
    @property
    def fd(self):return self.legacy.fd if self.legacy else self.stable.fd
    @property
    def fds(self):return tuple(lock.fd for lock in (self.stable,self.legacy) if lock and lock.fd is not None)
    def acquire(self):
        if not self.migration:
            self.runtime.check_legacy()
        if not self.runtime.base.exists():
            from .runtime_paths import ignore_runtime
            ignore_runtime(self.runtime)
        safe_path(self.runtime.locks).mkdir(parents=True, exist_ok=True)
        self.stable.acquire()
        try:
            if self.legacy:self.legacy.acquire()
        except BaseException:self.stable.close();raise
        return self
    def release_metadata_handle(self):
        if self.legacy:self.legacy.close()
    def close(self):
        self.release_metadata_handle();self.stable.close()
