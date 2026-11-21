"""Opt-in project-local OpenCode v2 MCP companion; Harness retains runtime authority."""
import argparse,copy,hashlib,importlib.util,os,sys,tempfile,uuid
from pathlib import Path
from knowledge.project import Project,safe_path
from knowledge.util import require,digest,fingerprint,emit_json,canonical_json,loads,read_text,KnowledgeError
from knowledge.maintenance import write
from .runtime import Journal,Lease,config,validate_config

def _read(path):
    safe_path(path)
    return path.read_bytes()

def _hash(raw):return hashlib.sha256(raw).hexdigest()

def _json(raw):
    try:return loads(raw.decode('utf-8'))
    except UnicodeError as error:raise KnowledgeError('invalid-utf8') from error

def _task_path(project,path):
    require(isinstance(path,str) and path and len(path)<=2000,'invalid-host-task-path')
    relative=Path(path)
    require(not relative.is_absolute() and not relative.drive and '..' not in relative.parts,'invalid-host-task-path')
    target=project.root/relative
    require(target.is_relative_to(project.root),'invalid-host-task-path')
    safe_path(target)
    return target

def _installed(project):
    path=project.root/'.harness/companion.json';safe_path(path)
    require(path.exists(),'companion-not-installed');raw=_read(path);value=_json(raw)
    require(isinstance(value,dict) and type(value.get('version')) is int and value['version']==1 and value.get('project')==project.identity,'companion-project-or-version-mismatch')
    require(value.get('python')==sys.executable,'companion-runtime-changed')
    require(isinstance(value.get('tasks'),dict) and isinstance(value.get('installed_digest'),str),'invalid-companion-state')
    require('original' in value and 'original_bytes' in value,'invalid-companion-state')
    old=value['original_bytes']
    require((old is None and value['original'] is None) or (isinstance(old,str) and isinstance(value['original'],dict) and _json(old.encode('utf-8'))==value['original']),'invalid-companion-state')
    if 'installation_id' in value:require(isinstance(value['installation_id'],str) and bool(value['installation_id']),'invalid-companion-state')
    for name,item in value['tasks'].items():
        require(isinstance(name,str) and isinstance(item,dict) and set(item)=={'path','digest'} and isinstance(item['digest'],str),'invalid-companion-state')
        _task_path(project,item['path'])
    return raw,value

def _snapshot(root):
    """One-read values; callers never reread a task to obtain execution input."""
    project=Project(root);raw,installed=_installed(project)
    require(not (project.root/'opencode.jsonc').exists(),'jsonc-config-requires-explicit-manual-merge')
    host=_read(project.root/'opencode.json');require(digest(_json(host))==installed['installed_digest'],'host-config-changed-review-required')
    runner=_read(project.root/'.harness/runner.json');configuration=validate_config(_json(runner))
    tasks={};payloads={}
    from .engine import task_shape
    for name,item in installed['tasks'].items():
        task_raw=_read(_task_path(project,item['path']));payload=_json(task_raw)
        require(digest(payload)==item['digest'],'host-task-changed-review-required');task_shape(payload,configuration)
        tasks[name]={'path':item['path'],'digest':item['digest'],'bytes':_hash(task_raw)};payloads[name]=payload
    return dict(version=1,project=project.identity,root=str(project.root),python=sys.executable,installed_code=digest({p.name:_hash(p.read_bytes()) for p in Path(__file__).parent.glob('*.py')}),installation=_hash(raw),host=_hash(host),runner=_hash(runner),configuration=digest(configuration),tasks=tasks),payloads

def validate_entry(root,authority,task,configuration):
    require(isinstance(authority,dict) and authority.get('version')==1,'unsupported-companion-authority')
    expected=copy.deepcopy(authority);name=expected.pop('task_name',None)
    current,payloads=_snapshot(root)
    require(current==expected and current['configuration']==digest(configuration),'host-enrollment-changed-review-required')
    require(name in payloads and task==payloads[name],'host-task-changed-review-required')

def _restore(target,raw):
    if raw is None:target.unlink();return
    fd,temporary=tempfile.mkstemp(prefix='.companion-',dir=target.parent)
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(raw.encode('utf-8'));stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,target)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)

def _remove(journal,target,companion,value):
    # Claim the actual marker before touching the host. Revalidate the renamed
    # bytes, not an earlier read which a scheduler could replace before rename.
    archived=journal.base/('companion-removed-'+uuid.uuid4().hex+'.json')
    companion.rename(archived)
    try:
        require(_hash(_read(archived))==value['installation'] and not companion.exists(),'stale-companion-preview')
        current=_read(target) if target.exists() else None
        require(current==(value['original_bytes'].encode('utf-8') if value['original_bytes'] is not None else None),'stale-host-preview')
        _restore(target,value['restore_bytes'])
    except BaseException:
        # Atomic no-clobber return: never overwrite a newer active marker. The
        # temporary internal link is removed immediately; final link count is 1.
        try:os.link(archived,companion)
        except FileExistsError:pass  # Keep both active newer state and archive.
        else:archived.unlink()
        raise

def preview(root,task_path=None,remove=False):
    project=Project(root);target=project.root/'opencode.json';safe_path(target)
    require(not (project.root/'opencode.jsonc').exists(),'jsonc-config-requires-explicit-manual-merge')
    original=_read(target) if target.exists() else None
    current=_json(original) if original is not None else {};require(isinstance(current,dict),'invalid-host-config')
    companion=project.root/'.harness/companion.json';safe_path(companion)
    if remove:
        installed_raw,installed=_installed(project)
        require(digest(current)==installed['installed_digest'],'host-config-changed-review-required')
        desired=installed['original'];tasks=installed['tasks']
    else:
        require(not companion.exists(),'companion-already-installed-remove-or-review-first')
        desired=copy.deepcopy(current);mcp=desired.setdefault('mcp',{});require(isinstance(mcp,dict),'invalid-host-mcp-config')
        # V2 namespaces; refuse a v1 server layout rather than silently replacing it.
        require(set(mcp)<={'servers'},'host-v1-config-requires-explicit-migration')
        servers=mcp.setdefault('servers',{});require(isinstance(servers,dict) and not {'knowledge_local','harness_companion'}&set(servers),'host-server-name-conflict')
        servers['knowledge_local']={'type':'local','command':[sys.executable,'-I','-m','knowledge.mcp','--root',str(project.root)]}
        shared=config(root).get('memory',{}).get('shared_root')
        if shared:servers['knowledge_local']['command']+=['--shared-root',shared]
        memory=config(root).get('memory',{})
        if memory.get('shared_root'):servers['knowledge_local']['command']+=['--shared-root',memory['shared_root']]
        servers['harness_companion']={'type':'local','command':[sys.executable,'-I','-m','harness.host_mcp','--root',str(project.root)]}
        tasks={}
        if task_path:
            path=Path(task_path);require(not path.is_absolute() and '..' not in path.parts,'invalid-host-task-path')
            value=_json(_read(_task_path(project,path.as_posix())))
            from .engine import task_shape
            task_shape(value,config(root));tasks['approved_task']={'path':path.as_posix(),'digest':digest(value)}
    value=dict(version=2,project=project.identity,root=str(project.root),operation='remove' if remove else 'install',original=current if original is not None else None,original_bytes=original.decode('utf-8') if original is not None else None,desired=desired,tasks=tasks,python=sys.executable,configuration=digest(config(root)),installation=_hash(installed_raw) if remove else None,installation_id=installed.get('installation_id') if remove else None,restore_bytes=installed['original_bytes'] if remove else None)
    return {'ok':True,'preview':value,'fingerprint':fingerprint(value),'mode':'OpenCode v2 project-local MCP companion; no native subagent enforcement claim'}

def apply(root,value,approval):
    value=copy.deepcopy(value);project=Project(root)
    require(type(value.get('version')) is int and value['version']==2 and value.get('operation') in ('install','remove') and value['project']==project.identity and approval==fingerprint(value),'companion-exact-approval-required')
    require(os.path.normcase(value['root'])==os.path.normcase(str(project.root)) and value['python']==sys.executable,'companion-runtime-or-root-changed')
    journal=Journal(root)
    with Lease(journal):
        require(value['configuration']==digest(config(root)),'stale-host-configuration')
        target=project.root/'opencode.json';safe_path(target);current=_read(target) if target.exists() else None
        require(current==(value['original_bytes'].encode() if value['original_bytes'] is not None else None),'stale-host-preview')
        companion=journal.base/'companion.json'
        if value['operation']=='remove':
            installed_raw,installed=_installed(project)
            require(_hash(installed_raw)==value['installation'],'stale-companion-preview')
            require(installed.get('installation_id')==value['installation_id'] and installed['original_bytes']==value['restore_bytes'] and installed['original']==value['desired'],'stale-companion-preview')
            _remove(journal,target,companion,value)
        else:
            safe_path(companion);require(not companion.exists(),'companion-already-installed-remove-or-review-first')
            for item in value['tasks'].values():require(digest(_json(_read(_task_path(project,item['path']))))==item['digest'],'host-task-changed-review-required')
            if current is not None:
                backup=journal.base/'host-backups'/uuid.uuid4().hex/'opencode.json';backup.parent.mkdir(parents=True);backup.write_bytes(current)
            write(target,value['desired'])
            write(companion,dict(version=1,project=project.identity,original=value['original'],original_bytes=value['original_bytes'],installed_digest=digest(value['desired']),tasks=value['tasks'],python=sys.executable,installation_id=uuid.uuid4().hex))
    return {'ok':True,'operation':value['operation'],'mode':'companion'}

def doctor(root):
    snapshot,_=_snapshot(root)
    return {'ok':True,'project':Project(root).describe(),'mode':'OpenCode v2 companion','mcp_available':importlib.util.find_spec('mcp') is not None,'native_host':'NOT_RUN','tasks':list(snapshot['tasks'])}

def run_task(root,name,host_session_id=None):
    authority,payloads=_snapshot(root);require(name in payloads,'host-task-not-enrolled');authority['task_name']=name
    from .engine import start
    return start(root,payloads[name],entry_authority=authority,host_session=host_session_id)

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
