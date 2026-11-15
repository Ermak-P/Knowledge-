"""Opt-in project-local OpenCode v2 MCP companion; Harness retains runtime authority."""
import argparse,copy,importlib.util,os,sys,uuid
from pathlib import Path
from knowledge.project import Project,safe_path
from knowledge.util import require,digest,fingerprint,emit_json,canonical_json,loads,read_text,KnowledgeError
from knowledge.maintenance import write
from .runtime import Journal,Lease,config

def preview(root,task_path=None,remove=False):
    project=Project(root);target=project.root/'opencode.json';safe_path(target)
    require(not (project.root/'opencode.jsonc').exists(),'jsonc-config-requires-explicit-manual-merge')
    original=target.read_bytes() if target.exists() else None
    current=loads(original.decode('utf-8')) if original is not None else {};require(isinstance(current,dict),'invalid-host-config')
    companion=project.root/'.harness/companion.json';safe_path(companion)
    if remove:
        require(companion.exists(),'companion-not-installed');installed=loads(read_text(companion))
        require(digest(current)==installed['installed_digest'],'host-config-changed-review-required')
        desired=installed['original'];tasks=installed['tasks']
    else:
        require(not companion.exists(),'companion-already-installed-remove-or-review-first')
        desired=copy.deepcopy(current);mcp=desired.setdefault('mcp',{});require(isinstance(mcp,dict),'invalid-host-mcp-config')
        # V2 namespaces; refuse a v1 server layout rather than silently replacing it.
        require(set(mcp)<={'servers'},'host-v1-config-requires-explicit-migration')
        servers=mcp.setdefault('servers',{});require(isinstance(servers,dict) and not {'knowledge_local','harness_companion'}&set(servers),'host-server-name-conflict')
        servers['knowledge_local']={'type':'local','command':[sys.executable,'-I','-m','knowledge.mcp','--root',str(project.root)]}
        servers['harness_companion']={'type':'local','command':[sys.executable,'-I','-m','harness.host_mcp','--root',str(project.root)]}
        tasks={}
        if task_path:
            path=Path(task_path);require(not path.is_absolute() and '..' not in path.parts,'invalid-host-task-path')
            safe_path(project.root/path);value=loads(read_text(project.root/path))
            from .engine import task_shape
            task_shape(value,config(root));tasks['approved_task']={'path':path.as_posix(),'digest':digest(value)}
    value=dict(version=1,project=project.identity,root=str(project.root),operation='remove' if remove else 'install',original=current if original is not None else None,original_bytes=original.decode('utf-8') if original is not None else None,desired=desired,tasks=tasks,python=sys.executable)
    return {'ok':True,'preview':value,'fingerprint':fingerprint(value),'mode':'OpenCode v2 project-local MCP companion; no native subagent enforcement claim'}

def apply(root,value,approval):
    project=Project(root);require(value.get('version')==1 and value['project']==project.identity and approval==fingerprint(value),'companion-exact-approval-required')
    journal=Journal(root)
    with Lease(journal):
        target=project.root/'opencode.json';safe_path(target);current=target.read_bytes() if target.exists() else None
        require(current==(value['original_bytes'].encode() if value['original_bytes'] is not None else None),'stale-host-preview')
        companion=journal.base/'companion.json'
        if value['operation']=='remove':
            installed=loads(read_text(companion));old=installed['original_bytes']
            if old is None:target.unlink()
            else:target.write_text(old,encoding='utf-8',newline='')
            companion.rename(journal.base/('companion-removed-'+uuid.uuid4().hex+'.json'))
        else:
            require(value['python']==sys.executable,'companion-runtime-changed')
            if current is not None:
                backup=journal.base/'host-backups'/uuid.uuid4().hex/'opencode.json';backup.parent.mkdir(parents=True);backup.write_bytes(current)
            write(target,value['desired'])
            write(companion,dict(version=1,project=project.identity,original=value['original'],original_bytes=value['original_bytes'],installed_digest=digest(value['desired']),tasks=value['tasks'],python=sys.executable))
    return {'ok':True,'operation':value['operation'],'mode':'companion'}

def doctor(root):
    project=Project(root);path=project.root/'.harness/companion.json';safe_path(path)
    require(path.exists(),'companion-not-installed');value=loads(read_text(path));require(value.get('version')==1 and value['project']==project.identity,'companion-project-or-version-mismatch')
    require(value['python']==sys.executable,'companion-runtime-changed')
    safe_path(project.root/'opencode.json')
    require(digest(loads(read_text(project.root/'opencode.json')))==value['installed_digest'],'host-config-changed-review-required')
    for t in value['tasks'].values():
        safe_path(project.root/t['path']);require(digest(loads(read_text(project.root/t['path'])))==t['digest'],'host-task-changed-review-required')
    return {'ok':True,'project':project.describe(),'mode':'OpenCode v2 companion','mcp_available':importlib.util.find_spec('mcp') is not None,'native_host':'NOT_RUN','tasks':list(value['tasks'])}

def run_task(root,name):
    doctor(root);project=Project(root);settings=loads(read_text(project.root/'.harness/companion.json'))
    require(name in settings['tasks'],'host-task-not-enrolled');t=settings['tasks'][name]
    from .engine import start
    return start(root,loads(read_text(project.root/t['path'])))

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['preview','apply','remove-preview','doctor','run']);p.add_argument('--root',required=True);p.add_argument('--task');p.add_argument('--input',type=Path);p.add_argument('--approve');a=p.parse_args()
    try:
        if a.command in ('preview','remove-preview'):value=preview(a.root,a.task,a.command=='remove-preview')
        elif a.command=='apply':value=apply(a.root,loads(read_text(a.input)),a.approve)
        elif a.command=='doctor':value=doctor(a.root)
        else:value=run_task(a.root,a.task)
    except (KnowledgeError,OSError,ValueError,TypeError,KeyError) as e:value={'ok':False,'error':getattr(e,'code','host-input-or-filesystem-error')}
    emit_json(value);return 0 if value['ok'] else 1
if __name__=='__main__':raise SystemExit(main())
