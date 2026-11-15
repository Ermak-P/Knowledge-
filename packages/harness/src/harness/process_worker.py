"""Recipe supervisor: owns the inherited writer lease until descendants are stopped."""
import argparse
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time
from .runtime import Journal,stamp,canonical_json


def process_info(pid):
    try:
        fields=Path(f'/proc/{pid}/stat').read_text().rpartition(') ')[2].split()
        return {'pid':pid,'group':int(fields[2]),'start':fields[19],'state':fields[0]}
    except (OSError,ValueError,IndexError):return None


def group_members(group,exclude=None):
    members=[]
    for p in Path('/proc').iterdir():
        if p.name.isdigit():
            info=process_info(int(p.name))
            if info and info['group']==group and info['pid']!=exclude and info['state']!='Z':members.append(info['pid'])
    return members


def stop_members(group):
    for _ in range(40):
        members=group_members(group,os.getpid())
        if not members:return True
        for pid in members:
            try:os.kill(pid,signal.SIGKILL)
            except ProcessLookupError:pass
        time.sleep(.025)
    return False


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--run',required=True);p.add_argument('--action',required=True);p.add_argument('--lease-fd',type=int,required=True);a=p.parse_args()
    journal=Journal(a.root);action=journal.action(a.run,a.action)
    if not action or action['status']!='INTENT':return 2
    terminating=[False]
    signal.signal(signal.SIGTERM,lambda *_:terminating.__setitem__(0,True))
    action['process']=process_info(os.getpid());action['process_started']=stamp();journal.action(a.run,a.action,action)
    spec=action['process_spec'];log=Path(spec['log']);log.parent.mkdir(parents=True,exist_ok=True)
    started=time.monotonic();seen=0;stored=0;reason=None
    process=subprocess.Popen(spec['argv'],cwd=spec['cwd'],env=os.environ.copy(),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,pass_fds=(a.lease_fd,))
    selector=selectors.DefaultSelector();selector.register(process.stdout,selectors.EVENT_READ)
    with log.open('wb') as output:
        while True:
            if terminating[0] or journal.cancelled(a.run):reason='cancelled'
            if time.monotonic()-started>=spec['timeout']:reason=reason or 'recipe-timeout'
            if reason:
                stop_members(os.getpgrp());break
            for key,_ in selector.select(.05):
                data=os.read(key.fd,8192)
                if data:
                    seen+=len(data);chunk=data[:max(0,spec['log_bytes']-stored)];output.write(chunk);stored+=len(chunk);output.flush()
                else:selector.unregister(key.fileobj)
            if process.poll() is not None and not selector.get_map():break
    process.wait();selector.close()
    if not stop_members(os.getpgrp()):
        action['cleanup']='unconfirmed';journal.action(a.run,a.action,action)
        # Keep the lease; an unkillable child must never release writer ownership.
        while not stop_members(os.getpgrp()):time.sleep(.25)
    action['process_result']=dict(returncode=process.returncode,reason=reason,duration=time.monotonic()-started,log_bytes=stored,observed_log_bytes=seen,truncated=seen>stored,descendants_stopped=True)
    action['process_finished']=stamp();journal.action(a.run,a.action,action)
    return 0


if __name__=='__main__':raise SystemExit(main())
