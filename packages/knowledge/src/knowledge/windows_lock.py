"""Native Windows byte-range maintenance lock; never an unlocked marker file."""
import ctypes as c
from ctypes import wintypes as w
from .util import KnowledgeError
k=c.WinDLL('kernel32',use_last_error=True)
HANDLE=w.HANDLE
class OVERLAPPED(c.Structure):
    _fields_=[('Internal',c.c_size_t),('InternalHigh',c.c_size_t),('Offset',w.DWORD),('OffsetHigh',w.DWORD),('hEvent',HANDLE)]
k.CreateFileW.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD,c.c_void_p,w.DWORD,w.DWORD,HANDLE];k.CreateFileW.restype=HANDLE
k.CloseHandle.argtypes=[HANDLE];k.CloseHandle.restype=w.BOOL
k.LockFileEx.argtypes=[HANDLE,w.DWORD,w.DWORD,w.DWORD,w.DWORD,c.POINTER(OVERLAPPED)];k.LockFileEx.restype=w.BOOL
k.UnlockFileEx.argtypes=[HANDLE,w.DWORD,w.DWORD,w.DWORD,c.POINTER(OVERLAPPED)];k.UnlockFileEx.restype=w.BOOL
INVALID=c.c_void_p(-1).value
class RangeLock:
    def __init__(self,path,exclusive,readonly=False):self.path=path;self.exclusive=exclusive;self.readonly=readonly;self.handle=None;self.overlap=OVERLAPPED()
    def acquire(self):
        self.handle=k.CreateFileW(str(self.path),0x80000000 if self.readonly else 0xC0000000,3,None,3 if self.readonly else 4,0x80,None)
        if self.handle==INVALID:raise KnowledgeError('maintenance-lock-open-failed',c.get_last_error())
        if not k.LockFileEx(self.handle,1|(2 if self.exclusive else 0),0,1,0,c.byref(self.overlap)):
            self.close();raise KnowledgeError('maintenance-busy')
    def close(self):
        if self.handle not in (None,INVALID):
            k.UnlockFileEx(self.handle,0,1,0,c.byref(self.overlap));k.CloseHandle(self.handle);self.handle=None
