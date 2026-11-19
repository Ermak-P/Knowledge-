"""Windows native Job Objects, suspended assignment and verifiable process handles.

No taskkill/image-name termination. The supervisor is outside the child job and
holds the exclusive inherited read/write file handle. KILL_ON_JOB_CLOSE covers supervisor
failure; the durable named-job fence covers abandoned ownership before reuse.
"""
import argparse,ctypes as c,os,subprocess,threading,time
from ctypes import wintypes as w
from pathlib import Path
from knowledge.util import require,KnowledgeError,digest
from knowledge.windows_lock import k,INVALID
HANDLE=w.HANDLE;INHERIT=1;NOT_FOUND=2
class SECURITY(c.Structure):_fields_=[('nLength',w.DWORD),('lpSecurityDescriptor',c.c_void_p),('bInheritHandle',w.BOOL)]
class STARTUP(c.Structure):
    _fields_=[('cb',w.DWORD),('lpReserved',w.LPWSTR),('lpDesktop',w.LPWSTR),('lpTitle',w.LPWSTR),('dwX',w.DWORD),('dwY',w.DWORD),('dwXSize',w.DWORD),('dwYSize',w.DWORD),('dwXCountChars',w.DWORD),('dwYCountChars',w.DWORD),('dwFillAttribute',w.DWORD),('dwFlags',w.DWORD),('wShowWindow',w.WORD),('cbReserved2',w.WORD),('lpReserved2',c.c_void_p),('hStdInput',HANDLE),('hStdOutput',HANDLE),('hStdError',HANDLE)]
class PROCESS(c.Structure):_fields_=[('hProcess',HANDLE),('hThread',HANDLE),('dwProcessId',w.DWORD),('dwThreadId',w.DWORD)]
class BASIC_LIMIT(c.Structure):
    _fields_=[('PerProcessUserTimeLimit',c.c_int64),('PerJobUserTimeLimit',c.c_int64),('LimitFlags',w.DWORD),('MinimumWorkingSetSize',c.c_size_t),('MaximumWorkingSetSize',c.c_size_t),('ActiveProcessLimit',w.DWORD),('Affinity',c.c_size_t),('PriorityClass',w.DWORD),('SchedulingClass',w.DWORD)]
class IO(c.Structure):_fields_=[(name,c.c_uint64) for name in ('ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount')]
class LIMIT(c.Structure):_fields_=[('BasicLimitInformation',BASIC_LIMIT),('IoInfo',IO),('ProcessMemoryLimit',c.c_size_t),('JobMemoryLimit',c.c_size_t),('PeakProcessMemoryUsed',c.c_size_t),('PeakJobMemoryUsed',c.c_size_t)]
class ACCOUNT(c.Structure):_fields_=[(n,c.c_int64) for n in ('TotalUserTime','TotalKernelTime','ThisPeriodTotalUserTime','ThisPeriodTotalKernelTime')]+[(n,w.DWORD) for n in ('TotalPageFaultCount','TotalProcesses','ActiveProcesses','TotalTerminatedProcesses')]

def api(name,args,result):
    fn=getattr(k,name);fn.argtypes=args;fn.restype=result;return fn
api('SetHandleInformation',[HANDLE,w.DWORD,w.DWORD],w.BOOL)
api('OpenProcess',[w.DWORD,w.BOOL,w.DWORD],HANDLE)
api('GetProcessTimes',[HANDLE,c.POINTER(w.FILETIME),c.POINTER(w.FILETIME),c.POINTER(w.FILETIME),c.POINTER(w.FILETIME)],w.BOOL)
api('WaitForSingleObject',[HANDLE,w.DWORD],w.DWORD)
api('GetExitCodeProcess',[HANDLE,c.POINTER(w.DWORD)],w.BOOL)
api('GetTickCount64',[],c.c_uint64)
api('CreateJobObjectW',[c.c_void_p,w.LPCWSTR],HANDLE)
api('OpenJobObjectW',[w.DWORD,w.BOOL,w.LPCWSTR],HANDLE)
api('SetInformationJobObject',[HANDLE,c.c_int,c.c_void_p,w.DWORD],w.BOOL)
api('QueryInformationJobObject',[HANDLE,c.c_int,c.c_void_p,w.DWORD,c.c_void_p],w.BOOL)
api('AssignProcessToJobObject',[HANDLE,HANDLE],w.BOOL)
api('TerminateJobObject',[HANDLE,w.UINT],w.BOOL)
api('IsProcessInJob',[HANDLE,HANDLE,c.POINTER(w.BOOL)],w.BOOL)
api('CreatePipe',[c.POINTER(HANDLE),c.POINTER(HANDLE),c.POINTER(SECURITY),w.DWORD],w.BOOL)
api('CreateProcessW',[w.LPCWSTR,w.LPWSTR,c.c_void_p,c.c_void_p,w.BOOL,w.DWORD,c.c_void_p,w.LPCWSTR,c.POINTER(STARTUP),c.POINTER(PROCESS)],w.BOOL)
api('ResumeThread',[HANDLE],w.DWORD)
api('ReadFile',[HANDLE,c.c_void_p,w.DWORD,c.POINTER(w.DWORD),c.c_void_p],w.BOOL)

def checked(value,code):
    if not value:raise KnowledgeError(code,c.get_last_error())
    return value

def boot_marker():
    # Quantized boot UTC is stable for one boot despite wall-clock millisecond jitter.
    # Process creation FILETIME and named job nonce are the primary identity checks.
    return int((time.time()-k.GetTickCount64()/1000)//60)

def process_info(pid):
    from .platform import KIND,host_identity
    handle=k.OpenProcess(0x1000|0x100000,False,pid)
    if not handle:
        if c.get_last_error() in (87,1168):return None
        raise KnowledgeError('process-identity-unavailable',c.get_last_error())
    try:
        if k.WaitForSingleObject(handle,0)==0:return None
        created=w.FILETIME();exit_time=w.FILETIME();kernel=w.FILETIME();user=w.FILETIME()
        checked(k.GetProcessTimes(handle,c.byref(created),c.byref(exit_time),c.byref(kernel),c.byref(user)),'process-identity-unavailable')
        return dict(pid=pid,group=pid,start=str((created.dwHighDateTime<<32)|created.dwLowDateTime),state='R',platform=KIND,host=host_identity())
    finally:k.CloseHandle(handle)

def open_job(name):
    require(isinstance(name,str) and name.startswith('Local\\Knowledge-') and len(name)==len('Local\\Knowledge-')+32,'invalid-job-identity')
    job=k.OpenJobObjectW(0x4|0x8,False,name) # QUERY | TERMINATE
    if not job and c.get_last_error()!=NOT_FOUND:raise KnowledgeError('job-identity-unavailable',c.get_last_error())
    return job

def active(job):
    info=ACCOUNT();checked(k.QueryInformationJobObject(job,1,c.byref(info),c.sizeof(info),None),'job-query-failed');return info.ActiveProcesses

def active_job(name):
    job=open_job(name)
    if not job:return 0
    try:return active(job)
    finally:k.CloseHandle(job)

def stop_job(action,supervisor):
    from .platform import compatible
    require(compatible(supervisor) and action.get('process_platform')=='windows-job-v1','unverifiable-process-ownership')
    current=process_info(supervisor['pid'])
    if current:require(current['start']==supervisor['start'],'process-identity-conflict')
    job=open_job(action['job_name'])
    if not job:return
    try:
        child=action.get('child_process')
        # A live supervisor can be between publishing its own identity and the
        # suspended child's receipt. recovery_stop is durable; it must finish
        # that bounded startup/cleanup itself without guessing child authority.
        if not child:return
        require(compatible(child),'unverifiable-child-ownership')
        handle=k.OpenProcess(0x1000|0x100000,False,child['pid'])
        if handle:
            try:
                info=process_info(child['pid'])
                if info:
                    require(info['start']==child['start'],'process-identity-conflict')
                    member=w.BOOL();checked(k.IsProcessInJob(handle,job,c.byref(member)),'job-identity-unavailable');require(member.value,'job-membership-conflict')
            finally:k.CloseHandle(handle)
        checked(k.TerminateJobObject(job,1),'job-terminate-failed')
    finally:k.CloseHandle(job)

def worker_main():
    from .runtime import Journal,stamp
    from .platform import process_info as owned_info
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--run',required=True);p.add_argument('--action',required=True);p.add_argument('--lease-fd',type=int,required=True);a=p.parse_args()
    journal=Journal(a.root);action=journal.action(a.run,a.action);require(action and action['status']=='INTENT','invalid-supervisor-action')
    action['process']=owned_info(os.getpid());action['process_started']=stamp();journal.action(a.run,a.action,action)
    spec=action['process_spec'];log=Path(spec['log']);log.parent.mkdir(parents=True,exist_ok=True)
    c.set_last_error(0)
    job=checked(k.CreateJobObjectW(None,action['job_name']),'job-create-failed')
    # Never reuse a pre-existing named job, even under the same user.
    require(c.get_last_error()!=183,'job-name-conflict')
    limits=LIMIT();limits.BasicLimitInformation.LimitFlags=0x2000
    checked(k.SetInformationJobObject(job,9,c.byref(limits),c.sizeof(limits)),'job-limit-failed')
    read=HANDLE();write=HANDLE();security=SECURITY(c.sizeof(SECURITY),None,True)
    checked(k.CreatePipe(c.byref(read),c.byref(write),c.byref(security),0),'pipe-create-failed')
    checked(k.SetHandleInformation(read,INHERIT,0),'pipe-inheritance-failed')
    checked(k.SetHandleInformation(a.lease_fd,INHERIT,INHERIT),'lease-inheritance-failed')
    startup=STARTUP();startup.cb=c.sizeof(startup);startup.dwFlags=0x100;startup.hStdOutput=write;startup.hStdError=write
    null=k.CreateFileW('NUL',0x80000000,3,c.byref(security),3,0x80,None);startup.hStdInput=null
    child=PROCESS();argv=c.create_unicode_buffer(subprocess.list2cmdline(spec['argv']));started=time.monotonic();reader=None
    try:
        action=journal.action(a.run,a.action)
        if action.get('recovery_stop') or journal.cancelled(a.run):
            log.write_bytes(b'');action['process_result']=dict(returncode=1,reason='cancelled',duration=time.monotonic()-started,log_bytes=0,observed_log_bytes=0,truncated=False,descendants_stopped=True,platform='windows-job-v1');action['process_finished']=stamp();journal.action(a.run,a.action,action);return 0
        checked(k.CreateProcessW(spec['argv'][0],argv,None,None,True,0x4|0x400,None,spec['cwd'],c.byref(startup),c.byref(child)),'recipe-create-failed')
        try:checked(k.AssignProcessToJobObject(job,child.hProcess),'job-assignment-failed')
        except BaseException:
            api('TerminateProcess',[HANDLE,w.UINT],w.BOOL)(child.hProcess,1);raise
        action=journal.action(a.run,a.action);action['child_process']=owned_info(child.dwProcessId);action=journal.action(a.run,a.action,action)
        reason='cancelled' if action.get('recovery_stop') or journal.cancelled(a.run) else None
        if reason:checked(k.TerminateJobObject(job,1),'job-terminate-failed')
        elif k.ResumeThread(child.hThread)==0xFFFFFFFF:
            require(journal.action(a.run,a.action).get('recovery_stop') or journal.cancelled(a.run),'recipe-resume-failed')
            reason='cancelled';checked(k.TerminateJobObject(job,1),'job-terminate-failed')
        k.CloseHandle(child.hThread);child.hThread=None;k.CloseHandle(write);write=None
        stats={'seen':0,'stored':0,'error':None};done=threading.Event()
        def drain():
            try:
                with log.open('wb') as stream:
                    buffer=c.create_string_buffer(8192);count=w.DWORD()
                    while k.ReadFile(read,buffer,8192,c.byref(count),None) and count.value:
                        data=buffer.raw[:count.value];stats['seen']+=len(data);part=data[:max(0,spec['log_bytes']-stats['stored'])];stream.write(part);stream.flush();stats['stored']+=len(part)
                    if c.get_last_error() not in (0,109):stats['error']='pipe-read-failed'
            except OSError:stats['error']='recipe-log-failure'
            finally:done.set()
        reader=threading.Thread(target=drain,daemon=True);reader.start()
        while k.WaitForSingleObject(child.hProcess,50)!=0:
            if stats['error']:reason=stats['error']
            if journal.cancelled(a.run) or journal.action(a.run,a.action).get('recovery_stop'):reason='cancelled'
            if time.monotonic()-started>=spec['timeout']:reason=reason or 'recipe-timeout'
            if reason:checked(k.TerminateJobObject(job,1),'job-terminate-failed');break
        checked(k.WaitForSingleObject(child.hProcess,10000)==0,'child-cleanup-unconfirmed')
        returncode=w.DWORD();checked(k.GetExitCodeProcess(child.hProcess,c.byref(returncode)),'process-exit-unavailable')
        if active(job):checked(k.TerminateJobObject(job,1),'job-terminate-failed')
        while active(job):time.sleep(.025) # Hold exclusive handle until verified empty.
        require(done.wait(5),'pipe-cleanup-unconfirmed');require(not stats['error'],stats['error'] or 'pipe-error')
        action=journal.action(a.run,a.action)
        if action.get('recovery_stop') or journal.cancelled(a.run):reason=reason or 'cancelled'
        action['process_result']=dict(returncode=returncode.value,reason=reason,duration=time.monotonic()-started,log_bytes=stats['stored'],observed_log_bytes=stats['seen'],truncated=stats['seen']>stats['stored'],descendants_stopped=True,platform='windows-job-v1')
        action['process_finished']=stamp();journal.action(a.run,a.action,action)
    finally:
        # Closing the last job handle kills all associated descendants on every error.
        if job:
            k.TerminateJobObject(job,1)
            while active(job):time.sleep(.025)
            k.CloseHandle(job)
        for handle in (child.hThread,child.hProcess,read,write,null):
            if handle not in (None,INVALID):k.CloseHandle(handle)
    return 0


def system_environment():
    # MCP stdio clients intentionally omit ProgramFiles variables. NuGet uses
    # them for machine-wide configuration even with an explicit packages path.
    # Ask Windows for known folders; never inherit the entire parent environment.
    shell=c.WinDLL('shell32',use_last_error=True)
    folder=shell.SHGetFolderPathW;folder.argtypes=[w.HWND,c.c_int,HANDLE,w.DWORD,w.LPWSTR];folder.restype=c.c_long
    values={}
    for name,identifier in (('PROGRAMFILES',0x26),('PROGRAMFILES(X86)',0x2A),('PROGRAMDATA',0x23)):
        buffer=c.create_unicode_buffer(32768)
        require(folder(None,identifier,None,0,buffer)==0 and Path(buffer.value).is_absolute() and Path(buffer.value).is_dir(),'windows-system-directory-unavailable',name)
        values[name]=buffer.value
    values['PROGRAMW6432']=values['PROGRAMFILES']
    return values
