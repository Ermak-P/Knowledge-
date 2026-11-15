"""Native execution backend selection. Process receipts are platform/boot bound."""
import hashlib,os,platform as system,subprocess
from pathlib import Path
from knowledge.util import require

KIND='windows-job-v1' if os.name=='nt' else 'linux-pgroup-v1'
def host_identity():
    if os.name=='nt':
        from .windows import boot_marker
        value=system.node()+':'+str(boot_marker())
    else:
        value=system.node()+':'+Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    return hashlib.sha256(value.encode()).hexdigest()
def compatible(info):return bool(info and info.get('platform')==KIND and info.get('host')==host_identity())
def process_info(pid):
    if os.name=='nt':
        from .windows import process_info as info
        return info(pid)
    from .process_posix import process_info as info
    result=info(pid)
    if result:result.update(platform=KIND,host=host_identity())
    return result

def launch_worker(argv,env,lease):
    descriptors=lease.lock.fds
    if os.name!='nt':return subprocess.Popen(argv,env=env,pass_fds=descriptors,start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    import ctypes
    from .windows import k,INHERIT
    try:
        for fd in descriptors:require(bool(k.SetHandleInformation(fd,INHERIT,INHERIT)),'lease-handle-inherit-failed')
        startup=subprocess.STARTUPINFO();startup.lpAttributeList={'handle_list':list(descriptors)}
        return subprocess.Popen(argv,env=env,startupinfo=startup,close_fds=True,creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    finally:
        for fd in descriptors:k.SetHandleInformation(fd,INHERIT,0)

def stop_owned(journal,run):
    for action_id,action in journal.actions(run).items():
        info=action.get('process')
        if info and not action.get('process_result'):
            require(compatible(info),'unverifiable-process-ownership')
            if os.name=='nt':
                from .windows import stop_job
                action['recovery_stop']=True;journal.action(run,action_id,action)
                stop_job(action,info)
            else:
                import signal
                current=process_info(info['pid'])
                if current and current['start']==info['start'] and current['group']==info['group']:
                    try:os.kill(info['pid'],signal.SIGTERM)
                    except ProcessLookupError:pass
                elif current is None:
                    from .process_posix import stop_members
                    require(stop_members(info['group']),'child-cleanup-unconfirmed')

def fence_pending(journal):
    """After an abandoned Windows handle, jobs must be gone before ownership passes."""
    for run in journal.runs():
        for action in journal.actions(run['id']).values():
            if not action.get('process_spec') or action.get('process_result'):continue
            info=action.get('process')
            if info:require(compatible(info),'unverifiable-process-ownership')
            if os.name=='nt':
                require(action.get('process_platform')==KIND and bool(action.get('job_name')),'unverifiable-process-ownership')
                from .windows import active_job
                require(active_job(action['job_name'])==0,'project-writer-busy')
            elif info:
                from .process_posix import group_members
                leader=process_info(info['group'])
                require(not leader or leader['start']==info['start'],'process-identity-conflict')
                require(not group_members(info['group']),'project-writer-busy')
