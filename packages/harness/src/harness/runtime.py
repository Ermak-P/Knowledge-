"""P2 operational state. Knowledge remains an independent writer/API."""
from contextlib import contextmanager
import fnmatch
import hashlib
import os
from pathlib import Path
import sqlite3
import time
import uuid
from knowledge.project import Project,safe_path,safe_tree
from knowledge.util import require,KnowledgeError,canonical_json,loads,digest,read_text

ROLES=('Main','Planning','Coding','Building','Testing','Reviewing')
TOOLS={'Main':('read','search','knowledge','delegate','status','capability'),
       'Planning':('read','search','knowledge','capability'),
       'Coding':('read','search','knowledge','patch','capability'),
       'Building':('read','recipe','artifact','capability'),
       'Testing':('read','recipe','artifact','capability'),
       'Reviewing':('read','search','knowledge','artifact','review','capability')}
IGNORED={'.git','.harness','.knowledge','.ai','.venv','.local','node_modules','bin','obj','__pycache__','.vs','TestResults'}
BINARY={'.png','.jpg','.jpeg','.gif','.ico','.zip','.dll','.exe','.pdb','.woff','.woff2','.ttf','.pdf','.sqlite3','.pyc'}
DEFAULT_LIMITS=dict(context_bytes=24000,response_bytes=64000,tool_bytes=6000,log_bytes=20000,file_bytes=1048576,
                    output_tokens=2048,requests=64,turns_per_agent=16,delegations=16,elapsed_seconds=600,
                    provider_seconds=15,recipe_seconds=60,reported_tokens=None)


def fault(phase):
    """Test-only crash seam. No activation by config, model or environment."""


def stamp():return time.time()

def blob(data):return hashlib.sha256(data).hexdigest()


def source_snapshot(project,limit=1048576):
    result={}
    for directory,dirs,files in os.walk(project.root,followlinks=False):
        parent=Path(directory)
        for name in list(dirs):
            p=parent/name
            if name in IGNORED or name.startswith('.'):dirs.remove(name)
            elif p.is_symlink():result[p.relative_to(project.root).as_posix()]={'linked':True};dirs.remove(name)
        for name in files:
            path=parent/name;relative=path.relative_to(project.root).as_posix()
            if path.suffix.lower() in BINARY or (name.startswith('.') and name not in ('.gitignore','.gitattributes','.editorconfig')) or any(part in name.casefold() for part in ('secret','credential','privatekey')):continue
            if path.is_symlink():result[relative]={'linked':True};continue
            safe_path(path)
            require(path.stat().st_size<=limit,'source-file-too-large',relative)
            result[relative]=blob(path.read_bytes())
    return dict(sorted(result.items()))


def policy_path(relative):return relative.casefold() if os.name=='nt' else relative


def local_path(project,relative,write=False):
    require(isinstance(relative,str) and relative and len(relative)<=1024,'invalid-relative-path')
    p=Path(relative)
    require(not p.is_absolute() and '..' not in p.parts and not any(x.startswith('.') or x.casefold() in {i.casefold() for i in IGNORED} for x in p.parts),'path-denied')
    require(not any(x in relative.casefold() for x in ('secret','credential','.env','privatekey','appsettings')) and p.suffix.casefold() not in ('.pem','.key','.pfx','.p12'),'private-path-denied')
    path=project.root/p;safe_path(path)
    if write:require(path.suffix.lower() not in ('.csproj','.props','.targets','.sln','.lock') and path.name.casefold() not in ('pyproject.toml','package.json','package-lock.json','requirements.txt','global.json','nuget.config','opencode.json','opencode.jsonc'),'protected-build-policy')
    return path


class Journal:
    def __init__(self,root):
        self.project=Project(root);self.base=self.project.root/'.harness';safe_tree(self.base)
        self.path=self.base/'runs.sqlite3'
        from knowledge.coordination import gate
        with gate(self.project.root):self._initialize()
    def _initialize(self):
        from knowledge.execution_lock import ExecutionLock
        self.base.mkdir(exist_ok=True);safe_path(self.path);lock=ExecutionLock(self.base/'init.lock');until=time.monotonic()+3
        while True:
            try:lock.acquire();break
            except KnowledgeError as error:
                if error.code!='project-writer-busy' or time.monotonic()>=until:raise KnowledgeError('harness-busy') from error
                time.sleep(.01)
        try:self._initialize_owned(not self.path.exists())
        finally:lock.close()
    def _initialize_owned(self,new):
        with self.db() as db:
            if not new:
                tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                require({'meta','runs','events','actions','outbox','cancels'}<=tables,'harness-state-incomplete-preserve-and-restore')
            db.execute('CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT)')
            old=dict(db.execute('SELECT key,value FROM meta'))
            if old:require(old=={'version':'1','project':self.project.identity},'harness-state-version-or-project-mismatch')
            else:
                require(new,'harness-state-incomplete-preserve-and-restore')
                db.executemany('INSERT INTO meta VALUES (?,?)',[('version','1'),('project',self.project.identity)])
            db.execute('CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS events(run TEXT,sequence INTEGER,payload TEXT,PRIMARY KEY(run,sequence))')
            db.execute('CREATE TABLE IF NOT EXISTS actions(run TEXT,id TEXT,payload TEXT,PRIMARY KEY(run,id))')
            db.execute('CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY,run TEXT,payload TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS cancels(run TEXT PRIMARY KEY,at REAL)')
    @contextmanager
    def db(self):
        from knowledge.coordination import gate
        with gate(self.project.root):
            with self._db() as db:yield db

    @contextmanager
    def _db(self):
        safe_path(self.path)
        db=sqlite3.connect(self.path,timeout=.15)
        try:
            db.execute('PRAGMA synchronous=FULL');db.execute('BEGIN IMMEDIATE')
            require(db.execute('PRAGMA quick_check').fetchone()==('ok',),'harness-state-corrupt')
            yield db;db.commit()
        except sqlite3.OperationalError as e:
            raise KnowledgeError('harness-busy' if 'locked' in str(e) else 'harness-database-error') from e
        except sqlite3.DatabaseError as e:raise KnowledgeError('harness-state-corrupt') from e
        finally:db.close()
    def save(self,run):
        require(type(run.get('version')) is int and run.get('version') in (1,2,3) and run['project']==self.project.identity,'harness-run-version-or-project-mismatch')
        with self.db() as db:db.execute('INSERT OR REPLACE INTO runs VALUES (?,?)',(run['id'],canonical_json(run)))
    def load(self,run_id):
        with self.db() as db:r=db.execute('SELECT payload FROM runs WHERE id=?',(run_id,)).fetchone()
        require(r is not None,'unknown-run');value=loads(r[0])
        require(isinstance(value,dict) and type(value.get('version')) is int and value.get('version') in (1,2,3) and value.get('project')==self.project.identity,'harness-run-version-or-project-mismatch')
        require(value.get('id')==run_id and value.get('status') in ('running','completed','completed-degraded','failed','cancelled','blocked','awaiting-capture'),'invalid-harness-run-state')
        require(all(isinstance(value.get(k),list) for k in ('agents','frames','requests')) and all(isinstance(value.get(k),dict) for k in ('source','task','gates','capture')) and isinstance(value.get('config_hash'),str),'invalid-harness-run-state')
        if value['version'] in (2,3):
            require(value.get('p4',{}).get('version')==1 and value['p4'].get('policy')=='bounded-v1' and value['task'].get('version')==2,'unsupported-p4-state')
        else:require('p4' not in value and value['task'].get('version')==1,'unsupported-p4-state')
        require(('automatic_tests' in value)==(value['version']==3),'unsupported-automatic-test-state')
        if value['version']==3:require(isinstance(value['automatic_tests'],dict) and type(value['automatic_tests'].get('version')) is int and value['automatic_tests'].get('version')==1 and value['automatic_tests'].get('policy')=='dotnet-tests-suffix-v1' and value['task']['kind']=='coding','unsupported-automatic-test-state')
        for frame in value['frames']:
            require(isinstance(frame,dict) and frame.get('role') in ROLES and any(isinstance(a,dict) and a.get('id')==frame.get('id') and a.get('role')==frame['role'] for a in value['agents']),'invalid-harness-role-frame')
        return value
    def event(self,run,kind,**data):
        with self.db() as db:
            sequence=db.execute('SELECT COALESCE(MAX(sequence),0)+1 FROM events WHERE run=?',(run,)).fetchone()[0]
            value=dict(version=1,sequence=sequence,at=stamp(),kind=kind,**data)
            db.execute('INSERT INTO events VALUES (?,?,?)',(run,sequence,canonical_json(value)))
        return value
    def runs(self):
        with self.db() as db:return [loads(p) for p, in db.execute('SELECT payload FROM runs')]
    def events(self,run):
        with self.db() as db:return [loads(p) for p, in db.execute('SELECT payload FROM events WHERE run=? ORDER BY sequence',(run,))]
    def action(self,run,identifier,value=None):
        with self.db() as db:
            if value is not None:
                previous=db.execute('SELECT payload FROM actions WHERE run=? AND id=?',(run,identifier)).fetchone()
                previous=loads(previous[0]) if previous else {}
                if previous.get('recovery_stop') and previous.get('process_attempt',0)==value.get('process_attempt',0):value={**value,'recovery_stop':True}
                db.execute('INSERT OR REPLACE INTO actions VALUES (?,?,?)',(run,identifier,canonical_json(value)))
            row=db.execute('SELECT payload FROM actions WHERE run=? AND id=?',(run,identifier)).fetchone()
        return loads(row[0]) if row else None
    def request_recipe_stop(self,run,identifier):
        with self.db() as db:
            row=db.execute('SELECT payload FROM actions WHERE run=? AND id=?',(run,identifier)).fetchone();require(row is not None,'unknown-action')
            value=loads(row[0]);value['recovery_stop']=True
            db.execute('UPDATE actions SET payload=? WHERE run=? AND id=?',(canonical_json(value),run,identifier))
        return value
    def actions(self,run):
        with self.db() as db:return {i:loads(p) for i,p in db.execute('SELECT id,payload FROM actions WHERE run=?',(run,))}
    def cancelled(self,run):
        with self.db() as db:return db.execute('SELECT 1 FROM cancels WHERE run=?',(run,)).fetchone() is not None
    def cancel(self,run):
        self.load(run)
        with self.db() as db:db.execute('INSERT OR IGNORE INTO cancels VALUES (?,?)',(run,stamp()))
        self.event(run,'cancellation-requested')
    def put_outbox(self,identifier,run,value):
        with self.db() as db:db.execute('INSERT INTO outbox VALUES (?,?,?)',(identifier,run,canonical_json(value)))
    def outbox(self,run):
        with self.db() as db:return {i:loads(p) for i,p in db.execute('SELECT id,payload FROM outbox WHERE run=?',(run,))}
    def update_outbox(self,identifier,value):
        with self.db() as db:db.execute('UPDATE outbox SET payload=? WHERE id=?',(canonical_json(value),identifier))


class Lease:
    def __init__(self,journal):self.journal=journal;self.fd=None;self.lock=None
    def __enter__(self):
        from knowledge.execution_lock import ProjectExecutionLock
        self.lock=ProjectExecutionLock(self.journal.project.root).acquire();self.fd=self.lock.fd
        try:
            from .platform import fence_pending
            fence_pending(self.journal)
        except BaseException:self.lock.close();self.fd=None;raise
        return self
    def __exit__(self,*args):
        if self.lock:self.lock.close();self.fd=None


def config(root):
    project=Project(root);p=project.root/'.harness/runner.json';safe_path(p);value=loads(read_text(p))
    return validate_config(value)


def validate_config(value):
    require(isinstance(value,dict) and {'version','provider','recipes','limits','capture'}<=set(value)<=({'version','provider','recipes','limits','capture','dotnet','memory'} if value.get('version')==2 else {'version','provider','recipes','limits','capture','memory'}),'invalid-runner-config')
    if 'memory' in value:
        from .instructions import validate_policy
        validate_policy(value['memory'])
    require(type(value['version']) is int and value['version'] in (1,2),'unsupported-runner-config')
    if 'dotnet' in value:require(isinstance(value['dotnet'],str),'invalid-shared-dotnet-executable')
    provider=value['provider']
    require(isinstance(provider,dict) and set(provider)<= {'endpoint','model','key_env','evidence'} and {'endpoint','model'}<=set(provider),'invalid-provider-config')
    from urllib.parse import urlsplit
    require(isinstance(provider['endpoint'],str) and 0<len(provider['endpoint'])<=2000,'invalid-provider-endpoint')
    try:endpoint=urlsplit(provider['endpoint'])
    except ValueError as e:raise KnowledgeError('invalid-provider-endpoint') from e
    require(endpoint.scheme in ('http','https') and endpoint.hostname and not endpoint.username and not endpoint.password and not endpoint.query and not endpoint.fragment,'invalid-provider-endpoint')
    require(endpoint.path.endswith('/chat/completions'),'unsupported-provider-endpoint')
    require(isinstance(provider['model'],str) and 0<len(provider['model'])<=200,'invalid-model')
    require(provider.get('evidence','live') in ('live','test-double'),'invalid-provider-evidence')
    if provider.get('key_env'):
        import re
        require(re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',provider['key_env']),'invalid-key-binding')
        require(endpoint.scheme=='https' or endpoint.hostname in ('localhost','127.0.0.1','::1'),'credentials-require-tls')
    limits=value['limits'];require(isinstance(limits,dict) and set(limits)<=set(DEFAULT_LIMITS),'invalid-limits')
    merged={**DEFAULT_LIMITS,**limits}
    for k,v in merged.items():
        if k=='reported_tokens' and v is None:continue
        require(type(v) is int and 0<v<=10000000,'invalid-limit',k)
    require(4096<=merged['context_bytes']<=1000000 and merged['response_bytes']<=2000000,'invalid-context-or-response-limit')
    require(value['capture'] in ('required','optional','off'),'invalid-capture-policy')
    require(isinstance(value['recipes'],dict) and len(value['recipes'])<=20,'invalid-recipes')
    for name,recipe in value['recipes'].items():
        require(isinstance(name,str) and name.isidentifier(),'invalid-recipe-name')
        require(isinstance(recipe,dict) and set(recipe)=={'kind','argv','result','rerun_safe','env'},'invalid-recipe')
        require(recipe['kind'] in ('build','test') and isinstance(recipe['argv'],list) and 0<len(recipe['argv'])<=40 and all(isinstance(a,str) and len(a)<=2000 and '\0' not in a for a in recipe['argv']),'invalid-recipe-argv')
        if os.name=='nt':require(not recipe['argv'][0].startswith(('\\\\','//')) and len(Path(recipe['argv'][0]).drive)==2,'unsupported-windows-executable-path')
        require(Path(recipe['argv'][0]).is_absolute() and Path(recipe['argv'][0]).is_file(),'recipe-executable-must-be-absolute')
        require(type(recipe['rerun_safe']) is bool and isinstance(recipe['env'],dict),'invalid-recipe-options')
        require(all(isinstance(k,str) and isinstance(v,str) and not any(word in k.upper() for word in ('TOKEN','KEY','SECRET','PASSWORD')) for k,v in recipe['env'].items()),'recipe-secret-environment-denied')
        result=recipe['result'];require(isinstance(result,dict) and set(result)=={'format','path'},'invalid-recipe-result')
        require(result['format'] in (('exit',) if recipe['kind']=='build' else ('unittest','trx','json')),'test-result-parser-required')
        require(isinstance(result['path'],str) and (not result['path'] or result['path'].startswith('{artifacts}/')),'result-path-must-be-owned-artifact')
        if result['path']:
            require(not any(x in result['path'] for x in ('//','\\',':')),'result-path-must-be-owned-artifact')
            tail=Path(result['path'][len('{artifacts}/'):]);require(bool(tail.parts) and not tail.is_absolute() and '..' not in tail.parts and '{' not in str(tail) and '}' not in str(tail),'result-path-must-be-owned-artifact')
        if result['format'] in ('trx','json'):require(bool(result['path']),'test-artifact-path-required')
    if value['version']==2:
        require(all(r['kind']=='build' for r in value['recipes'].values()),'automatic-runner-rejects-manual-test-recipes')
        from .testing import dotnet
        dotnet(value)
    return value


def configure(root,value,initialize_knowledge=False):
    journal=Journal(root);validate_config(value)
    with Lease(journal):
        path=journal.base/'runner.json';safe_path(path)
        temporary=journal.base/('config-'+uuid.uuid4().hex+'.tmp');temporary.write_text(canonical_json(value),encoding='utf-8');os.replace(temporary,path)
        if initialize_knowledge:
            from knowledge.store import Store
            from knowledge import lifecycle
            s=Store(root)
            if not s.path.exists():s.init();lifecycle.upgrade(s,lifecycle.upgrade_preview(s)['fingerprint'])
    return {'ok':True,'configuration':digest(value)}


def recipe_inputs(project,configuration,task):
    """Canonical project-owned argv files, executable and Python module entries.

    Check lexical ancestors before normalizing ..; resolving a symlink must never
    erase evidence that a project input escaped through a linked ancestor.
    External trusted tools are not project source and retain their host policy.
    """
    paths=set();executables=set()
    def include(argument,executable=False):
        p=Path(argument)
        if not p.is_absolute():p=project.root/p
        if os.name=='nt' and p.is_file():
            from knowledge.project import windows_spelling,linked
            windows_spelling(p)
            require(not any(linked(part) for part in (p,*p.parents)),'linked-path')
        canonical=Path(os.path.abspath(p))
        if not canonical.is_relative_to(project.root):return
        if not p.is_file():return
        safe_path(p);safe_path(canonical)
        relative=policy_path(canonical.relative_to(project.root).as_posix());paths.add(relative)
        if executable:executables.add(relative)
    if configuration['version']==2:
        from .testing import dotnet,native_msbuild
        include(dotnet(configuration)[0],True)
        native=native_msbuild(configuration,task['recipes'])
        if native:include(native[0],True)
    for name in task['recipes']:
        argv=configuration['recipes'][name]['argv']
        for index,arg in enumerate(argv):include(arg,index==0)
        if '-m' in argv:
            index=argv.index('-m')
            if index+1<len(argv):
                parts=argv[index+1].split('.')
                if all(part.isidentifier() for part in parts):
                    module='/'.join(parts)
                    include(module+'.py');include(module+'/__main__.py')
                    for i in range(1,len(parts)+1):include('/'.join(parts[:i])+'/__init__.py')
    for procedure in configuration.get('memory',{}).get('allowed_procedures',[]):
        argv=procedure['check']['argv']
        for index,arg in enumerate(argv):include(arg,index==0)
        if '-m' in argv:
            index=argv.index('-m')
            if index+1<len(argv):
                parts=argv[index+1].split('.')
                if all(part.isidentifier() for part in parts):
                    module='/'.join(parts);include(module+'.py');include(module+'/__main__.py')
                    for i in range(1,len(parts)+1):include('/'.join(parts[:i])+'/__init__.py')
        if 'docker' in procedure:
            include(procedure['docker']['executable'],True)
            if 'compose_file' in procedure['docker']:include(procedure['docker']['compose_file'])
    for template in configuration.get('memory',{}).get('procedure_templates',[]):
        include(template['python'],True);include(template['docker'],True)
    return sorted(paths),sorted(executables)
