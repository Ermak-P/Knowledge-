"""Exclusive inheritable execution ownership shared by Harness and maintenance."""
import os
from pathlib import Path
from .project import safe_path
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
