"""Windows 10+ stdio child, atomically assigned to a private kill-on-close job.

Uses the same Windows Job Object mechanism as the existing supervisor, without
any Harness dependency. JOB_LIST removes the create/assign orphan window.
Explicit durable scan workers can break away; unrelated processes are untouched.
"""
import ctypes as c
from ctypes import wintypes as w
import os
import subprocess
import sys


def run(command):
    k=c.WinDLL('kernel32',use_last_error=True)
    HANDLE=w.HANDLE
    class Basic(c.Structure):
        _fields_=[('PerProcessUserTimeLimit',c.c_int64),('PerJobUserTimeLimit',c.c_int64),('LimitFlags',w.DWORD),
                  ('MinimumWorkingSetSize',c.c_size_t),('MaximumWorkingSetSize',c.c_size_t),('ActiveProcessLimit',w.DWORD),
                  ('Affinity',c.c_size_t),('PriorityClass',w.DWORD),('SchedulingClass',w.DWORD)]
    class IO(c.Structure):
        _fields_=[(name,c.c_uint64) for name in ('ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount')]
    class Limits(c.Structure):
        _fields_=[('BasicLimitInformation',Basic),('IoInfo',IO),('ProcessMemoryLimit',c.c_size_t),
                  ('JobMemoryLimit',c.c_size_t),('PeakProcessMemoryUsed',c.c_size_t),('PeakJobMemoryUsed',c.c_size_t)]
    class Startup(c.Structure):
        _fields_=[('cb',w.DWORD),('lpReserved',w.LPWSTR),('lpDesktop',w.LPWSTR),('lpTitle',w.LPWSTR),
                  *[(name,w.DWORD) for name in ('dwX','dwY','dwXSize','dwYSize','dwXCountChars','dwYCountChars','dwFillAttribute','dwFlags')],
                  ('wShowWindow',w.WORD),('cbReserved2',w.WORD),('lpReserved2',c.c_void_p),
                  ('hStdInput',HANDLE),('hStdOutput',HANDLE),('hStdError',HANDLE)]
    class StartupEx(c.Structure):
        _fields_=[('StartupInfo',Startup),('lpAttributeList',c.c_void_p)]
    class Process(c.Structure):
        _fields_=[('hProcess',HANDLE),('hThread',HANDLE),('dwProcessId',w.DWORD),('dwThreadId',w.DWORD)]
    def api(name,args,result):
        fn=getattr(k,name);fn.argtypes=args;fn.restype=result;return fn
    def checked(value):
        if not value:raise c.WinError(c.get_last_error())
        return value
    api('CreateJobObjectW',[c.c_void_p,w.LPCWSTR],HANDLE)
    api('SetInformationJobObject',[HANDLE,c.c_int,c.c_void_p,w.DWORD],w.BOOL)
    api('CloseHandle',[HANDLE],w.BOOL)
    api('GetCurrentProcess',[],HANDLE)
    api('GetStdHandle',[w.DWORD],HANDLE)
    api('DuplicateHandle',[HANDLE,HANDLE,HANDLE,c.POINTER(HANDLE),w.DWORD,w.BOOL,w.DWORD],w.BOOL)
    api('InitializeProcThreadAttributeList',[c.c_void_p,w.DWORD,w.DWORD,c.POINTER(c.c_size_t)],w.BOOL)
    api('UpdateProcThreadAttribute',[c.c_void_p,w.DWORD,c.c_size_t,c.c_void_p,c.c_size_t,c.c_void_p,c.c_void_p],w.BOOL)
    api('DeleteProcThreadAttributeList',[c.c_void_p],None)
    api('CreateProcessW',[w.LPCWSTR,w.LPWSTR,c.c_void_p,c.c_void_p,w.BOOL,w.DWORD,c.c_void_p,w.LPCWSTR,c.c_void_p,c.POINTER(Process)],w.BOOL)
    api('WaitForSingleObject',[HANDLE,w.DWORD],w.DWORD)
    api('GetExitCodeProcess',[HANDLE,c.POINTER(w.DWORD)],w.BOOL)
    api('OpenProcess',[w.DWORD,w.BOOL,w.DWORD],HANDLE)
    api('QueryFullProcessImageNameW',[HANDLE,w.DWORD,w.LPWSTR,c.POINTER(w.DWORD)],w.BOOL)
    api('GetModuleFileNameW',[HANDLE,w.LPWSTR,w.DWORD],w.DWORD)
    job=checked(k.CreateJobObjectW(None,None));duplicates=[];attributes=None;initialized=False;child=Process();parent=None
    try:
        # Windows venv python.exe is itself a redirector. The host may terminate
        # that outer PID while this real interpreter is still alive. Hold a
        # verified handle to that Python parent and observe its termination.
        candidate=k.OpenProcess(0x100000|0x1000,False,os.getppid())
        if candidate:
            try:
                capacity=w.DWORD(32768);image=c.create_unicode_buffer(capacity.value)
                if k.QueryFullProcessImageNameW(candidate,0,image,c.byref(capacity)) and os.path.samefile(image.value,sys.executable):
                    parent=candidate;candidate=None
            finally:
                if candidate:k.CloseHandle(candidate)
        executable=c.create_unicode_buffer(32768)
        checked(k.GetModuleFileNameW(None,executable,len(executable)))
        if not os.path.samefile(executable.value,sys.executable) and parent is None:
            raise OSError('Cannot verify the outer Python launcher lifetime; no runtime child started')
        limits=Limits();limits.BasicLimitInformation.LimitFlags=0x2000|0x800  # KILL_ON_JOB_CLOSE | BREAKAWAY_OK
        checked(k.SetInformationJobObject(job,9,c.byref(limits),c.sizeof(limits)))
        # Duplicate only the three real standard handles. No reader/writer is
        # interposed on MCP, and the job handle is never inherited by the child.
        current=k.GetCurrentProcess()
        for selector in (-10,-11,-12):
            original=k.GetStdHandle(selector)
            if not original or original==c.c_void_p(-1).value:raise OSError('Knowledge launcher requires stdin/stdout/stderr handles')
            duplicate=HANDLE();checked(k.DuplicateHandle(current,original,current,c.byref(duplicate),0,True,2));duplicates.append(duplicate.value)
        size=c.c_size_t();k.InitializeProcThreadAttributeList(None,2,0,c.byref(size))
        attributes=c.create_string_buffer(size.value)
        checked(k.InitializeProcThreadAttributeList(attributes,2,0,c.byref(size)));initialized=True
        handles=(HANDLE*3)(*duplicates);jobs=(HANDLE*1)(job)
        checked(k.UpdateProcThreadAttribute(attributes,0,0x20002,handles,c.sizeof(handles),None,None))  # HANDLE_LIST
        checked(k.UpdateProcThreadAttribute(attributes,0,0x2000D,jobs,c.sizeof(jobs),None,None))  # JOB_LIST (Windows 10+)
        startup=StartupEx();startup.StartupInfo.cb=c.sizeof(startup);startup.StartupInfo.dwFlags=0x100
        startup.StartupInfo.hStdInput,startup.StartupInfo.hStdOutput,startup.StartupInfo.hStdError=duplicates
        startup.lpAttributeList=c.cast(attributes,c.c_void_p)
        environment={**os.environ,'KNOWLEDGE_OWNED_JOB':'1'}
        block=c.create_unicode_buffer('\0'.join(key+'='+value for key,value in sorted(environment.items(),key=lambda item:item[0].upper()))+'\0')
        argv=c.create_unicode_buffer(subprocess.list2cmdline([str(value) for value in command]))
        checked(k.CreateProcessW(str(command[0]),argv,None,None,True,0x80000|0x400,block,None,c.byref(startup),c.byref(child)))
        while True:
            if parent and k.WaitForSingleObject(parent,0)==0:return 1
            status=k.WaitForSingleObject(child.hProcess,100)
            if status==0:break
            if status!=258:raise c.WinError(c.get_last_error())
        code=w.DWORD();checked(k.GetExitCodeProcess(child.hProcess,c.byref(code)));return code.value
    except KeyboardInterrupt:return 130
    finally:
        # Closing the private job also handles forced launcher termination at
        # any point after CreateProcess; breakaway scan workers remain alive.
        k.CloseHandle(job)
        if child.hProcess:
            k.WaitForSingleObject(child.hProcess,10000);k.CloseHandle(child.hProcess)
        if child.hThread:k.CloseHandle(child.hThread)
        if parent:k.CloseHandle(parent)
        if initialized:k.DeleteProcThreadAttributeList(attributes)
        for handle in duplicates:k.CloseHandle(handle)
