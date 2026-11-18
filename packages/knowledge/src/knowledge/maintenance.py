from contextlib import closing
"""Exact-approved lifecycle tooling for root-bound Knowledge/Harness state.

Execution lease -> exclusive maintenance gate -> SQLite backup/read snapshots.
No competing Knowledge writer and no canonical SQL mutation. Restore touches only
owned metadata; a durable fence prevents ordinary access to a partial restore.
"""
from contextlib import contextmanager
import hashlib,json,os,platform,sqlite3,stat,tempfile,uuid,zipfile
from pathlib import Path
from . import __version__
from .project import Project,safe_path,safe_tree
from .coordination import gate
from .execution_lock import ProjectExecutionLock
from .store import Store
from .util import loads,read_text,canonical_json,digest,fingerprint,require,KnowledgeError
MAX_BYTES=128*1024*1024
SUPPORTED_PRODUCTS=('0.3.0rc1','0.4.0rc1',__version__)

def valid_marker(value):
    if value is None:return True
    if not isinstance(value,dict) or type(value.get('version')) is not int or value['version']!=1 or value.get('product') not in SUPPORTED_PRODUCTS:return False
    formats=value.get('formats')
    return isinstance(formats,dict) and set(formats)=={'knowledge','extension','harness'} and formats['knowledge'] in (None,'knowledge-sqlite-v1') and formats['extension'] in (None,1) and formats['harness'] in (None,1) and type(value.get('database_rewrite')) is bool and value['database_rewrite'] is False and isinstance(value.get('transaction'),str) and len(value['transaction'])==32


def fault(phase):pass

def write(path,value):
    safe_path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    with tmp.open('wb') as out:out.write(canonical_json(value).encode());out.flush();os.fsync(out.fileno())
    os.replace(tmp,path)

def sha(data):return hashlib.sha256(data).hexdigest()
def profile():return 'windows' if os.name=='nt' else platform.system().lower()

@contextmanager
def frozen(root,recovery=False):
    project=Project(root);lock=None;project._maintenance_reservations=[]
    safe_tree(project.root/'.harness');lock=ProjectExecutionLock(project.root).acquire()
    project._maintenance_execution=lock
    try:
        with gate(project.root,exclusive=True,recovery=recovery):
            harness_db=project.root/'.harness/runs.sqlite3'
            if harness_db.exists():
                try:
                    with closing(sqlite3.connect(harness_db.as_uri()+'?mode=ro',uri=True)) as db:
                        rows=[(r,i,loads(p)) for r,i,p in db.execute('SELECT run,id,payload FROM actions')]
                except sqlite3.DatabaseError as e:raise KnowledgeError('maintenance-database-corrupt-or-unsupported') from e
                if any(a.get('process_spec') and not a.get('process_result') for _,_,a in rows):
                    try:from harness.platform import fence_pending
                    except ImportError as e:raise KnowledgeError('harness-required-to-verify-pending-processes') from e
                    class Pending:
                        def runs(self):return [{'id':r} for r in {r for r,_,_ in rows}]
                        def actions(self,run):return {i:a for r,i,a in rows if r==run}
                    fence_pending(Pending())
            for relative in ('.knowledge/store.sqlite3','.harness/runs.sqlite3'):
                path=project.root/relative
                if not path.exists():continue
                connection=sqlite3.connect(path.as_uri()+'?mode=rw',uri=True,timeout=.15)
                try:connection.execute('BEGIN IMMEDIATE')
                except sqlite3.OperationalError as error:
                    connection.close();raise KnowledgeError('maintenance-sqlite-busy') from error
                project._maintenance_reservations.append(connection)
            yield project
    finally:
        release_reservations(project)
        if lock:lock.close()

def release_reservations(project):
    for connection in getattr(project,'_maintenance_reservations',[]):
        connection.rollback();connection.close()
    project._maintenance_reservations=[]


def source_identity(root):
    files={};ignored={'.git','.knowledge','.harness','.maintenance','.venv','.local','.opencode','bin','obj','node_modules','__pycache__','TestResults'}
    for directory,dirs,names in os.walk(root,followlinks=False):
        dirs[:]=[n for n in dirs if n not in ignored and not n.startswith('.')]
        for name in names:
            p=Path(directory)/name
            if name.startswith('.') or p.suffix.lower() in ('.zip','.pyc','.dll','.pdb','.exe','.png','.jpg','.pdf'):continue
            safe_path(p);require(p.stat().st_size<=2*1024*1024,'maintenance-source-too-large')
            files[p.relative_to(root).as_posix()]=sha(p.read_bytes())
    return digest(files)

def database(path,project):
    db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=.15)
    try:
        require(db.execute('PRAGMA quick_check').fetchone()==('ok',),'maintenance-database-corrupt')
        if path.parent.name=='.knowledge':
            metadata=dict(db.execute('SELECT key,value FROM metadata'))
            require(metadata.get('project')==project.identity and metadata.get('format')=='knowledge-sqlite-v1' and metadata.get('p1') in (None,'1'),'backup-database-incompatible')
            legacy=project.root/'.ai'
            require(not (legacy.exists() and any(legacy.iterdir())) or 'migration' in metadata,'ambiguous-dual-stores')
            store=Store(project.root);store._check_control(db);store._records(db)
        else:
            require(dict(db.execute('SELECT key,value FROM meta'))=={'project':project.identity,'version':'1'},'unsupported-harness-state')
            for payload, in db.execute('SELECT payload FROM runs'):
                r=loads(payload);require(r.get('version') in (1,2) and r.get('project')==project.identity,'unsupported-harness-run')
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        require(all(t.replace('_','').isalnum() for t in tables),'unsafe-database-table')
        counts={t:db.execute('SELECT count(*) FROM "'+t+'"').fetchone()[0] for t in tables}
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'snapshot.sqlite3';target=sqlite3.connect(p)
            try:db.backup(target);target.commit()
            finally:target.close()
            return p.read_bytes(),counts
    except sqlite3.DatabaseError as e:raise KnowledgeError('maintenance-database-corrupt') from e
    finally:db.close()

def snapshot(project,allow_absent=False):
    files={};counts={};first=source_identity(project.root)
    for folder in ('.knowledge','.harness'):
        base=project.root/folder;safe_tree(base)
        if not base.exists():continue
        for path in sorted(base.rglob('*')):
            if not path.is_file():continue
            if path.name in ('writer.lock','init.lock') or path.name.endswith(('.sqlite3-journal','.sqlite3-wal','.sqlite3-shm')):continue
            require(not any(word in path.name.casefold() for word in ('credential','secret','privatekey')) and path.suffix.lower() not in ('.pem','.key','.pfx'),'backup-sensitive-file')
            rel=path.relative_to(project.root).as_posix()
            if rel in ('.knowledge/store.sqlite3','.harness/runs.sqlite3'):
                files[rel],counts[folder]=database(path,project)
            else:
                files[rel]=path.read_bytes()
                if rel in ('.harness/runner.json','.harness/companion.json'):require(loads(files[rel].decode('utf-8')).get('version')==1,'unsupported-state-configuration')
    require(files or allow_absent,'maintenance-state-absent')
    require(sum(map(len,files.values()))<=MAX_BYTES,'backup-too-large')
    require(first==source_identity(project.root),'source-changed-during-maintenance')
    marker=project.root/'.maintenance/product-state.json';safe_path(marker)
    product_state=loads(read_text(marker)) if marker.exists() else None
    require(valid_marker(product_state),'unsupported-maintenance-version')
    extension=None
    if '.knowledge' in counts:
        with closing(sqlite3.connect((project.root/'.knowledge/store.sqlite3').as_uri()+'?mode=ro',uri=True)) as db:extension=1 if dict(db.execute('SELECT key,value FROM metadata')).get('p1')=='1' else None
    formats={'knowledge':'knowledge-sqlite-v1' if '.knowledge' in counts else None,'extension':extension,'harness':1 if '.harness' in counts else None}
    return dict(version=1,project=project.identity,root=str(project.root),platform=profile(),product=__version__,formats=formats,source=first,files={p:sha(data) for p,data in files.items()},counts=counts,product_state=product_state),files

def absent_destination(path,root):
    path=Path(path).absolute();safe_path(path)
    require(not path.exists(),'destination-must-be-absent')
    require(not any(path.is_relative_to(root/p) for p in ('.knowledge','.harness')),'destination-inside-live-state')
    return path

def preview(root,operation,destination=None,archive=None,recovery=None):
    require(operation in ('backup','upgrade','restore'),'unsupported-maintenance-operation')
    with frozen(root) as project:
        state,_=snapshot(project,operation=='restore')
        value=dict(version=1,operation=operation,project=project.identity,root=str(project.root),state=state,product=__version__)
        if operation in ('backup','upgrade'):value['destination']=str(absent_destination(destination,project.root))
        else:
            manifest,_=read_backup(archive,project)
            value.update(archive=str(Path(archive).absolute()),archive_sha256=sha(Path(archive).read_bytes()),manifest=manifest,recovery=str(absent_destination(recovery,project.root)))
        if operation=='upgrade':value['transition']={'from':state['product_state'].get('product') if state['product_state'] else None,'to':__version__,'formats_unchanged':True}
        return {'ok':True,'preview':value,'fingerprint':fingerprint(value),'quiescence':'execution lease, exclusive gate; ordinary writers/readers refused during apply','relocation':'root-bound state; package transfer and fresh-project initialization supported'}

def create_backup(project,path,state,files):
    path=absent_destination(path,project.root);path.parent.mkdir(parents=True,exist_ok=True);safe_path(path.parent)
    manifest={**state,'archive_version':1,'file_count':len(files),'cross_store':'exclusive participating-writer freeze; SQLite backup API; same-root/same-OS restore'}
    tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('MANIFEST.json',canonical_json(manifest))
            for rel,data in files.items():z.writestr(rel,data)
        read_backup(tmp,project);os.replace(tmp,path)
    finally:
        if tmp.exists():tmp.unlink()
    return dict(path=str(path),sha256=sha(path.read_bytes()),manifest=manifest)

def read_backup(archive,project):
    path=Path(archive).absolute();safe_path(path);require(path.is_file() and path.stat().st_size<=MAX_BYTES,'backup-unavailable-or-too-large')
    try:
        with zipfile.ZipFile(path) as z:
            infos=z.infolist();require(len(infos)<=10000 and sum(i.file_size for i in infos)<=MAX_BYTES,'backup-too-large')
            names=[i.filename for i in infos];require(len(names)==len(set(n.casefold() for n in names)),'backup-member-collision')
            require('MANIFEST.json' in names,'backup-manifest-missing')
            for info in infos:
                p=Path(info.filename)
                require(not p.is_absolute() and '..' not in p.parts and '\\' not in info.filename and ':' not in info.filename and not info.is_dir(),'unsafe-backup-path')
                require(stat.S_IFMT(info.external_attr>>16) in (0,stat.S_IFREG),'backup-links-denied')
                require(info.filename=='MANIFEST.json' or p.parts[0] in ('.knowledge','.harness'),'unsafe-backup-path')
                safe_path(project.root/p)
            manifest=loads(z.read('MANIFEST.json').decode('utf-8'))
            require(isinstance(manifest,dict) and isinstance(manifest.get('files'),dict) and isinstance(manifest.get('counts'),dict),'invalid-backup-manifest')
            require(type(manifest.get('archive_version')) is int and type(manifest.get('version')) is int,'unsupported-backup-version')
            require(manifest.get('archive_version')==1 and manifest.get('version')==1 and isinstance(manifest.get('formats'),dict) and set(manifest['formats'])=={'knowledge','extension','harness'} and manifest['formats']['knowledge'] in (None,'knowledge-sqlite-v1') and manifest['formats']['extension'] in (None,1) and manifest['formats']['harness'] in (None,1),'unsupported-backup-version')
            require(manifest['project']==project.identity and manifest['root']==str(project.root),'backup-project-mismatch-no-relocation')
            require(manifest.get('product') in SUPPORTED_PRODUCTS and valid_marker(manifest.get('product_state')),'unsupported-backup-product')
            require(manifest['platform']==profile(),'cross-platform-state-restore-unsupported')
            require(set(names)=={'MANIFEST.json',*manifest['files']},'backup-inventory-mismatch')
            files={name:z.read(name) for name in manifest['files']}
            require(all(sha(data)==manifest['files'][name] for name,data in files.items()),'backup-checksum-mismatch')
            require(len(files)==manifest['file_count'],'backup-count-mismatch')
            for name,data in files.items():
                if name in ('.knowledge/store.sqlite3','.harness/runs.sqlite3'):
                    actual=validate_database_bytes(data,name,project)
                    require(actual==manifest['counts'].get(name.split('/')[0]),'backup-semantic-count-mismatch')
            return manifest,files
    except (zipfile.BadZipFile,KeyError,UnicodeError) as e:raise KnowledgeError('invalid-backup') from e

def validate_database_bytes(data,name,project):
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'state.sqlite3';path.write_bytes(data)
        db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
        try:
            require(db.execute('PRAGMA quick_check').fetchone()==('ok',),'backup-database-corrupt')
            if name.startswith('.knowledge/'):
                metadata=dict(db.execute('SELECT key,value FROM metadata'))
                require(metadata.get('project')==project.identity and metadata.get('format')=='knowledge-sqlite-v1' and metadata.get('p1') in (None,'1'),'backup-database-incompatible')
                store=Store(project.root);store._check_control(db);store._records(db)
            else:require(dict(db.execute('SELECT key,value FROM meta'))=={'project':project.identity,'version':'1'},'backup-database-incompatible')
            tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            require(all(t.replace('_','').isalnum() for t in tables),'unsafe-database-table')
            return {t:db.execute('SELECT count(*) FROM "'+t+'"').fetchone()[0] for t in tables}
        except sqlite3.DatabaseError as e:raise KnowledgeError('backup-database-corrupt') from e
        finally:db.close()


def apply(root,value,approval):
    require(isinstance(value,dict) and type(value.get('version')) is int and value.get('version')==1,'unsupported-maintenance-preview')
    require(approval==fingerprint(value),'maintenance-approval-required')
    with frozen(root) as project:
        require(value['project']==project.identity and value['root']==str(project.root) and value['product']==__version__,'maintenance-project-or-version-mismatch')
        op=value['operation'];require(op in ('backup','upgrade','restore'),'unsupported-maintenance-operation')
        state,files=snapshot(project,op=='restore')
        for path in (project.root/'.maintenance/transactions').glob('*/journal.json'):
            prior=loads(read_text(path))
            if prior.get('status')=='COMPLETED' and prior.get('preview')==value and prior.get('approval')==approval:
                expected=prior.get('desired_files',value['state']['files'])
                require(state['files']==expected and state['source']==value['state']['source'],'stale-maintenance-preview')
                return dict(ok=True,status='COMPLETED',result='already-completed',transaction=prior['id'])
        require(state==value['state'],'stale-maintenance-preview')
        if op=='backup':return dict(ok=True,operation=op,backup=create_backup(project,value['destination'],state,files))
        txn=uuid.uuid4().hex;base=project.root/'.maintenance/transactions'/txn;base.mkdir(parents=True);safe_path(base)
        journal=dict(version=1,id=txn,operation=op,project=project.identity,status='PREPARED',preview=value,approval=approval)
        if op=='upgrade':
            journal['backup']=create_backup(project,value['destination'],state,files)
        else:
            require(sha(Path(value['archive']).read_bytes())==value['archive_sha256'],'backup-changed-after-preview')
            manifest,restored=read_backup(value['archive'],project);require(manifest==value['manifest'],'backup-changed-after-preview')
            saved=absent_destination(value['recovery'],project.root);saved.mkdir(parents=True);journal['saved']=str(saved)
            for rel,data in restored.items():
                path=base/'staged'/rel;safe_path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            journal['desired_files']=manifest['files']
        write(base/'journal.json',journal);write(project.root/'.maintenance/active.json',{'version':1,'transaction':txn,'project':project.identity})
        fault('maintenance-prepared')
        return _finish(project,journal,base)

def _finish(project,journal,base):
    safe_tree(base)
    value=journal['preview']
    require(journal['id']==base.name and journal['operation']==value['operation'] and value['project']==project.identity and value['root']==str(project.root),'invalid-maintenance-journal')
    if journal['operation']=='restore':
        require(journal['saved']==value['recovery'] and journal['desired_files']==value['manifest']['files'],'invalid-restore-journal')
        safe_tree(Path(journal['saved']))
    require(value.get('product') in SUPPORTED_PRODUCTS,'unsupported-maintenance-journal-product')
    require(journal['version']==1 and journal['project']==project.identity and journal['approval']==fingerprint(value),'invalid-maintenance-journal')
    if journal['operation']=='restore':
        for folder in ('.knowledge','.harness'):
            staged=base/'staged'/folder;saved=Path(journal['saved'])/folder
            expected={p:h for p,h in journal['desired_files'].items() if p.startswith(folder+'/')}
            old={p:h for p,h in value['state']['files'].items() if p.startswith(folder+'/')}
            if staged.exists():require(_folder_files(staged,project)==expected,'restore-staged-state-conflict')
            if saved.exists():require(_folder_files(saved,project)==old,'restore-preserved-state-conflict')
        # Participating clients remain fenced. Legacy programs must be quiescent;
        # initial SQLite reservations reject active legacy transactions. Close our
        # own DB handles before native directory replacement (Windows sharing).
        release_reservations(project)
        # Stable root ownership and the exclusive gate remain held throughout.
        project._maintenance_execution.release_metadata_handle()
        for folder in ('.knowledge','.harness'):
            target=project.root/folder;staged=base/'staged'/folder;saved=Path(journal['saved'])/folder
            expected={p:h for p,h in journal['desired_files'].items() if p.startswith(folder+'/')}
            old={p:h for p,h in value['state']['files'].items() if p.startswith(folder+'/')}
            if saved.exists():require(_folder_files(saved,project)==old,'restore-preserved-state-conflict')
            if staged.exists():require(_folder_files(staged,project)==expected,'restore-staged-state-conflict')
            if not saved.exists() and target.exists() and folder not in journal.get('installed',[]):
                # Validate the replaced state; do not move unrelated intervening bytes.
                got=_folder_files(target,project)
                require(got==old,'restore-intervening-state-conflict')
                os.replace(target,saved);fault('restore-old-moved')
            if staged.exists():
                require(not target.exists(),'restore-target-conflict');os.replace(staged,target);fault('restore-new-moved')
            require(_folder_files(target,project)==expected,'restore-target-integrity-failed')
            if folder not in journal.setdefault('installed',[]):journal['installed'].append(folder)
            write(base/'journal.json',journal)
    else:
        current=snapshot(project)[0];marker=current['product_state']
        current['product']=value['state']['product'] # Finish an already-approved supported predecessor operation without changing its meaning.
        if marker and marker.get('transaction')==journal['id']:current['product_state']=value['state']['product_state']
        require(current==value['state'],'upgrade-intervening-state-conflict')
    marker_path=project.root/'.maintenance/product-state.json'
    if journal['operation']=='restore':
        saved_marker=Path(journal['saved'])/'product-state-before-restore.json'
        if not saved_marker.exists():write(saved_marker,value['state']['product_state'])
        marker=value['manifest']['product_state']
        if marker is None:
            if marker_path.exists():marker_path.unlink()
        else:write(marker_path,marker)
    else:
        marker={'version':1,'product':value['product'],'formats':value['state']['formats'],'transaction':journal['id'],'database_rewrite':False}
        write(marker_path,marker)
    fault('maintenance-committed')
    journal['status']='COMPLETED';write(base/'journal.json',journal)
    (project.root/'.maintenance/active.json').unlink()
    return dict(ok=True,operation=journal['operation'],transaction=journal['id'],status='COMPLETED',backup=journal.get('backup'),replaced_state=journal.get('saved'),canonical_approval='unchanged; no auto-acknowledgment',source_files='preserved')

def _folder_files(base,project):
    if not base.exists():return {}
    result={};safe_tree(base)
    for p in sorted(base.rglob('*')):
        if not p.is_file() or p.name in ('writer.lock','init.lock') or p.name.endswith(('.sqlite3-journal','.sqlite3-wal','.sqlite3-shm')):continue
        rel=base.name+'/'+p.relative_to(base).as_posix()
        # Backup-API copies are deterministic snapshots, including live DB control pages.
        data=database(p,project)[0] if p.name in ('store.sqlite3','runs.sqlite3') else p.read_bytes()
        result[rel]=sha(data)
    return result

def status(root):
    project=Project(root);base=project.root/'.maintenance';safe_tree(base)
    active=base/'active.json'
    return dict(ok=True,version=1,active=loads(read_text(active)) if active.exists() else None,transactions=[loads(read_text(p)) for p in sorted((base/'transactions').glob('*/journal.json'))])

def recover(root):
    with frozen(root,recovery=True) as project:
        fence=project.root/'.maintenance/active.json';require(fence.exists(),'no-maintenance-to-recover')
        value=loads(read_text(fence));require(isinstance(value,dict) and type(value.get('version')) is int and value.get('version')==1 and value.get('project')==project.identity,'unsupported-maintenance-fence')
        txn=value['transaction'];require(isinstance(txn,str) and len(txn)==32 and all(c in '0123456789abcdef' for c in txn),'invalid-maintenance-transaction')
        base=project.root/'.maintenance/transactions'/txn;safe_tree(base);journal=loads(read_text(base/'journal.json'))
        if journal['status']=='COMPLETED':fence.unlink();return dict(ok=True,status='COMPLETED',transaction=txn)
        return _finish(project,journal,base)
