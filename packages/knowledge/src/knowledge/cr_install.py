"""Project-only native command activation. Never overwrites unrelated host files."""
import hashlib,os,sys,uuid
from pathlib import Path
from .project import Project,safe_path,safe_tree
from .coordination import gate
from .util import canonical_json,loads,read_text,require

BASE=Path(__file__).parent/'host'
MANIFEST='.opencode/.knowledge-update-cr-install.json'


def sha(data):return hashlib.sha256(data).hexdigest()
def _paths(root):
    p=Project(root);safe_tree(p.root/'.opencode');safe_path(p.root/'.knowledge-cr-host.json');return p
def _previous(project):
    path=project.root/MANIFEST
    if not path.exists():return None
    value=loads(read_text(path));require(isinstance(value,dict) and set(value)=={'version','project','files'} and value['version']==1 and value['project']==project.identity and set(value['files'])=={'.opencode/commands/update-by-CR.md','.opencode/plugins/knowledge-update-cr.js','.knowledge-cr-host.json'},'ucr-invalid-installation-marker')
    return value
def _write(path,data):
    safe_path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with tmp.open('xb') as out:out.write(data);out.flush();os.fsync(out.fileno())
        os.replace(tmp,path)
    finally:
        if tmp.exists():tmp.unlink()


def install(root,python=None,language='auto'):
    project=_paths(root);python=Path(python or sys.executable)
    require(python.is_absolute() and python.is_file(),'ucr-absolute-installed-python-required');require(language in ('auto','en','ru'),'ucr-invalid-language')
    files={'.opencode/commands/update-by-CR.md':(BASE/'commands/update-by-CR.md').read_bytes(),'.opencode/plugins/knowledge-update-cr.js':(BASE/'cr_opencode.mjs').read_bytes(),'.knowledge-cr-host.json':(canonical_json(dict(version=1,python=str(python),language=language))+'\n').encode()}
    with gate(project.root):
        previous=_previous(project)
        for rel,data in files.items():
            path=project.root/rel;safe_path(path)
            if path.exists():require(path.is_file() and ((previous and sha(path.read_bytes())==previous['files'][rel]) or path.read_bytes()==data),'ucr-command-installation-conflict',{'path':rel,'resolution':'Preserve/rename your existing definition or explicitly remove the owned installation first.'})
        for rel,data in files.items():_write(project.root/rel,data)
        _write(project.root/MANIFEST,(canonical_json(dict(version=1,project=project.identity,files={k:sha(v) for k,v in files.items()}))+'\n').encode())
    return dict(ok=True,command='/update-by-CR',scope='project',host='OpenCode 1.19.6 native command/plugin discovery',files=list(files),restart='Restart the host to load project commands/plugins; current agent/model is retained.')


def uninstall(root):
    project=_paths(root)
    with gate(project.root):
        previous=_previous(project)
        if previous is None:return dict(ok=True,state='not-installed')
        for rel,wanted in previous['files'].items():
            path=project.root/rel;safe_path(path)
            require(not path.exists() or sha(path.read_bytes())==wanted,'ucr-command-user-edits-preserved',rel)
        for rel in previous['files']:
            path=project.root/rel
            if path.exists():path.unlink()
        (project.root/MANIFEST).unlink()
    return dict(ok=True,state='removed-owned-files',other_commands='preserved')


def status(root):
    project=_paths(root);previous=_previous(project)
    if previous is None:return dict(ok=True,state='not-installed')
    return dict(ok=True,state='installed',files={rel:dict(present=(project.root/rel).is_file(),matches=(project.root/rel).is_file() and sha((project.root/rel).read_bytes())==wanted) for rel,wanted in previous['files'].items()})
