"""Explicit SQLite identity migration; historical rows never carry live authority.

Only this module accepts a caller-supplied old identity. Ordinary Store access
keeps its identity checks. Publication replaces directories under the existing
maintenance fence, never source SQL rows. No model/provider or Harness dependency.
"""
from contextlib import closing
from base64 import b64encode
from copy import copy
import hashlib
import os
from pathlib import Path, PureWindowsPath
import shutil
import re
import sqlite3
import tempfile
from .project import Project, safe_path, safe_tree
from .store import Store, create_tables
from . import maintenance as m
from .util import require, loads, canonical_json, digest, fingerprint, KnowledgeError
from .sqlite_snapshot import view
from . import confluence as cf
from . import confluence_sync as cs
from . import confluence_command as cc
from . import discovery_history, discovery_checkpoint, discovery_cache

KEY = 'sqlite-identity-migration-v1'
RULE = 'canonical-and-revisions-active-control-objects-historical-v1'
CORE = {'metadata': ('key','value'), 'records': ('id','kind','payload'),
        'queue': ('id','payload','status','binding'), 'plans': ('id','payload','status'),
        'history': ('sequence','payload')}
P1 = {'revisions': ('id','revision','payload'), 'scans': ('id','payload'),
      'reviews': ('sequence','payload'), 'receipts': ('plan','payload')}
DISCOVERY = {
    'discovery_runs': ('id','initial','initial_hash','sequence','tail'),
    'discovery_chunks': ('scan','sequence','payload','checksum'),
    'discovery_file_cache': ('path','binding','payload','checksum'),
    discovery_history.TABLE: ('digest','payload'),
}
DISCOVERY_SQL = {**discovery_checkpoint.TABLE_SQL, 'discovery_file_cache': discovery_cache.TABLE_SQL,
                 discovery_history.TABLE: discovery_history.TABLE_SQL}
DISCOVERY_BLOBS = {'discovery_runs':1, 'discovery_chunks':2}
OPS = {'operational_current': ('id','revision','payload'),
       'operational_history': ('id','revision','payload'), 'operational_events': ('id','payload')}
PREFIXES = ('update-by-cr:', 'operational-transfer:', 'candidate-refresh-v1:',
            'capture-observation-v1:', 'semantic-provider-v1:')
LIMIT = 128*1024*1024
P1_SQL = {
    'revisions':'CREATE TABLE revisions(id TEXT, revision INTEGER, payload TEXT NOT NULL, PRIMARY KEY(id,revision))',
    'scans':'CREATE TABLE scans(id TEXT PRIMARY KEY,payload TEXT NOT NULL)',
    'reviews':'CREATE TABLE reviews(sequence INTEGER PRIMARY KEY,payload TEXT NOT NULL)',
    'receipts':'CREATE TABLE receipts(plan TEXT PRIMARY KEY,payload TEXT NOT NULL)'}
OPS_SQL = {
    'operational_current':'CREATE TABLE operational_current(id TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL)',
    'operational_history':'CREATE TABLE operational_history(id TEXT NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(id,revision))',
    'operational_events':'CREATE TABLE operational_events(id TEXT PRIMARY KEY, payload TEXT NOT NULL)'}


def fault(phase):
    """Internal future regression seam; no user/environment activation."""


def _validate_source(db, project, identity):
    # Only source validation has an identity exception; return no Store handle.
    store=Store(project.root)
    store.project=copy(project);store.project.identity=identity
    store._check_control(db);store._records(db)


def _validate_staged(project, base):
    store=Store(project.root);store.base=Path(base);store.path=store.base/'store.sqlite3'
    with store.connection() as db:
        require(db.execute('PRAGMA integrity_check').fetchall()==[('ok',)],'identity-destination-integrity-failed')
    store.validate()


def inventory_connection(db, project, old, knowledge_base=None):
    require(isinstance(old,str) and re.fullmatch('[a-f0-9]{64}',old),'invalid-old-project-identity')
    require(db.execute('PRAGMA integrity_check').fetchall()==[('ok',)],'identity-source-integrity-failed')
    require(set(CORE)<={r[0] for r in db.execute("SELECT name FROM sqlite_schema WHERE type='table'")},'identity-source-missing-core-tables')
    metadata=dict(db.execute('SELECT key,value FROM metadata'))
    require(metadata.get('project')==old,'identity-source-identity-mismatch',
            {'expected_old_identity':old,'stored_identity':metadata.get('project')})
    require(metadata.get('format')=='knowledge-sqlite-v1' and metadata.get('p1') in (None,'1')
            and metadata.get('operations') in (None,'1'),'identity-unsupported-format')
    require(metadata.get('confluence-schema') in (None,*cf.SUPPORTED_SCHEMAS),'identity-unsupported-confluence-version')
    require(metadata.get('confluence-sync-schema') in (None,cs.SCHEMA),'identity-unsupported-confluence-sync-version')
    require(metadata.get(cc.META) in (None,cc.SCHEMA),'identity-unsupported-confluence-command-version')
    require(all(k in ('format','project','p1','operations','migration','confluence-schema','confluence-sync-schema','confluence-gc-registrations',cc.META) or k.startswith((*PREFIXES,cs.REFRESH))
                for k in metadata),'identity-unknown-metadata-extension')
    schema=list(db.execute("SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name"))
    require(not any(t in ('trigger','view') for t,_,_,_ in schema),'identity-unknown-schema-object')
    require(all(t!='index' or sql is None or (metadata.get('confluence-schema') in cf.SUPPORTED_SCHEMAS and n in cf.INDEX_SQL) or (metadata.get('confluence-sync-schema')==cs.SCHEMA and n in cs.INDEX_SQL) or (metadata.get(cc.META)==cc.SCHEMA and n in cc.INDEX_SQL) for t,n,_,sql in schema),'identity-unknown-index')
    source_tables={n for t,n,_,_ in schema if t=='table'}
    checkpoints={'discovery_runs','discovery_chunks'}
    require(not (source_tables & checkpoints) or checkpoints <= source_tables, 'identity-incomplete-discovery-checkpoint-schema')
    extensions={t:columns for t,columns in DISCOVERY.items() if t in source_tables and metadata.get('p1')=='1'}
    expected={**CORE,**(P1 if metadata.get('p1')=='1' else {}),**extensions,
              **(OPS if metadata.get('operations')=='1' else {}),**(cf.schema_tables(metadata['confluence-schema']) if metadata.get('confluence-schema') else {}),**(cs.TABLES if metadata.get('confluence-sync-schema') else {}),**(cc.TABLES if metadata.get(cc.META) else {})}
    require({n for t,n,_,_ in schema if t=='table'}==set(expected),'identity-unknown-or-missing-table')
    # Recognize constraints/indexes as well as column names. Never execute DDL
    # from a supplied source while constructing the destination.
    with closing(sqlite3.connect(':memory:')) as known:
        create_tables(known,'schema-only')
        for table,sql in {**P1_SQL,**OPS_SQL,**DISCOVERY_SQL}.items():
            if table in expected:known.execute(sql)
        if metadata.get('confluence-schema'):
            for sql in cf.schema_sql(metadata['confluence-schema']):known.execute(sql)
        if metadata.get('confluence-sync-schema'):
            for sql in (*cs.TABLE_SQL.values(),*cs.INDEX_SQL.values()):known.execute(sql)
        if metadata.get(cc.META):
            for sql in (*cc.TABLE_SQL.values(),*cc.INDEX_SQL.values()):known.execute(sql)
        normalize=lambda sql:re.sub(r'\s+','',sql or '').casefold()
        recognized=[(t,n,parent,normalize(sql)) for t,n,parent,sql in known.execute('SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name')]
        require([(t,n,parent,normalize(sql)) for t,n,parent,sql in schema]==recognized,'identity-unrecognized-schema-definition')
    rows={};manifest={}
    for table,columns in expected.items():
        require(tuple(r[1] for r in db.execute('PRAGMA table_info("'+table+'")'))==columns,
                'identity-unsupported-table-columns',{'table':table})
        values=list(db.execute('SELECT * FROM "'+table+'" ORDER BY '+','.join(str(i+1) for i in range(len(columns)))))
        blob = DISCOVERY_BLOBS.get(table)
        require(all(all(v is None or type(v) in (str,int) or (i==blob and type(v) is bytes)
                        for i,v in enumerate(row)) for row in values),'identity-unsupported-sql-value')
        if blob is not None:
            require(all(type(row[blob]) is bytes for row in values),'identity-unsupported-sql-value')
            values=[(*row[:blob], {'base64':b64encode(row[blob]).decode('ascii')}, *row[blob+1:]) for row in values]
        rows[table]=values
        manifest[table]={'columns':list(columns),'count':len(values),
                         'rows':[digest(list(row)) for row in values],
                         'disposition':'active-identical-and-archived' if table in ('records','revisions','history') or table in cf.TABLES else 'historical-only'}
    require(len(canonical_json(rows).encode())<=LIMIT,'identity-source-too-large')
    _validate_source(db,project,old)
    # Check every historical revision, not only the latest projection.
    if 'revisions' in rows:
        from .store import shape, empty
        previous={}
        for identifier,revision,payload in rows['revisions']:
            v=loads(payload);require(v['id']==identifier and v['revision']==revision
                and revision==previous.get(identifier,0)+1 and v['lifecycle'] in ('active','retired','superseded'),
                'identity-corrupt-revision-history')
            records=empty();records[v['kind']]=[v['record']];shape(records);previous[identifier]=revision
        for identifier,payload in rows['scans']:
            state=discovery_history.decode(db,identifier,payload)
            require(isinstance(state,dict) and state.get('id')==identifier and re.fullmatch('[a-f0-9]{64}',identifier)
                    and state.get('extractor') in ('dotnet-lexical-v1','dotnet-lexical-v2','dotnet-lexical-v3')
                    and isinstance(state.get('snapshot'),dict) and isinstance(state.get('coverage'),dict)
                    and isinstance(state.get('observations'),list) and type(state.get('complete')) is bool,'identity-unsupported-scan')
    if 'discovery_runs' in rows:
        from .discovery import _load_checkpoint
        require(all(_load_checkpoint(db,row[0]) is not None for row in rows['discovery_runs']),
                'identity-corrupt-discovery-checkpoint')
    for k,payload in rows['metadata']:
        if k.startswith('operational-transfer:'):
            require(loads(payload)['phase']=='completed','identity-transfer-recovery-required',{'key':k})
        if k.startswith('update-by-cr:'):
            for item in loads(payload)['artifacts']:
                relative=Path(item['path']).relative_to('.knowledge')
                p=safe_path((knowledge_base or project.base)/relative)
                require(p.is_file() and p.stat().st_size<=LIMIT and 'sha256:'+m.sha(p.read_bytes())==item['hash'],'identity-missing-or-changed-cr-artifact',{'path':str(p)})
    counts={'record_kinds':{},'queue_dispositions':{},'plan_states':{}}
    for table,column,key in (('records',1,'record_kinds'),('queue',2,'queue_dispositions'),('plans',2,'plan_states')):
        for row in rows[table]:counts[key][row[column]]=counts[key].get(row[column],0)+1
    for table,key in (('operational_current','operational_statuses'),('operational_events','operational_event_versions')):
        if table in rows:
            grouped={}
            for row in rows[table]:
                item=loads(row[-1]);label=item.get('status','event-without-version' if 'version' not in item else str(item['version']))
                grouped[label]=grouped.get(label,0)+1
            counts[key]=grouped
    counts['cr_states']={};counts['transfer_states']={}
    for key,payload in rows['metadata']:
        for prefix,field,target in (('update-by-cr:','state','cr_states'),('operational-transfer:','phase','transfer_states')):
            if key.startswith(prefix):
                state=loads(payload)[field];counts[target][state]=counts[target].get(state,0)+1
    unresolved=[]
    for identifier,kind,payload in rows['records']:
        if kind!='evidence':continue
        for field in ('source','location'):
            ref=loads(payload).get(field)
            if isinstance(ref,dict):ref=ref.get('reference')
            if isinstance(ref,str) and (Path(ref).is_absolute() or PureWindowsPath(ref).is_absolute()):
                unresolved.append({'id':identifier,'field':field,'reference_hash':digest(ref),'disposition':'preserved unchanged; absolute binding unresolved'})
    return {'schema':[list(row) for row in schema],'tables':manifest,'counts':counts,'unresolved_evidence':unresolved,
            'old_identity':old,'logical_identity':digest(rows)},rows


def inventory(root, old):
    project=Project(root);safe_tree(project.base)
    require(project.db.is_file(),'knowledge-absent')
    require(project.db.stat().st_size<=LIMIT,'identity-source-file-too-large')
    wal=safe_path(project.base/'store.sqlite3-wal')
    require(not wal.exists() or wal.stat().st_size<=LIMIT,'identity-source-wal-too-large')
    with closing(sqlite3.connect(project.db.as_uri()+'?mode=ro',uri=True,timeout=.15)) as db:
        db.execute('BEGIN');result,_=inventory_connection(db,project,old)
    return {'ok':True,'database':str(project.db),'root':str(project.root),
            'expected_identity':project.identity,**result,'read_only':True}


def files(folder):
    result={};safe_tree(folder)
    if folder.exists():
        for p in sorted(folder.rglob('*')):
            if not p.is_file():continue
            # SQLite SHM and lock files are volatile coordination, not artifacts.
            # Originals are still archived by directory rename, never deleted.
            if p.name in ('writer.lock','init.lock') or p.name.endswith('-shm'):continue
            primary='runs.sqlite3' if folder.name=='.harness' else 'store.sqlite3' if folder.name in ('.knowledge','staged') else None
            if primary and p.parent==folder and p.name in (primary,primary+'-wal',primary+'-journal'):continue
            require(p.stat().st_size<=LIMIT,'identity-artifact-too-large')
            result[p.relative_to(folder).as_posix()]=m.sha(p.read_bytes())
    return result


def outside(raw,project):
    path=Path(raw).absolute();require('..' not in path.parts,'parent-traversal-not-allowed');safe_tree(path)
    require(not path.is_relative_to(project.root) and not project.root.is_relative_to(path),'identity-workspace-must-be-outside-project')
    require(not path.exists(),'identity-workspace-must-be-absent')
    safe_path(path.parent);require(path.parent.is_dir(),'identity-workspace-parent-must-exist')
    require(path.parent.stat().st_dev==project.root.stat().st_dev,'identity-cutover-requires-same-volume')
    return path


def preview(root,old,workspace):
    no_hot_journal(Project(root))
    with m.frozen(root) as project:
        return _preview(project,old,workspace)


def _preview(project,old,workspace):
    require(old!=project.identity,'identity-already-matches')
    require(not (project.root/'.ai').exists(),'identity-legacy-state-requires-separate-resolution')
    work=outside(workspace,project)
    result=inventory(project.root,old)
    existing=m.status(project.root)
    require(all(j.get('status')=='COMPLETED' for j in existing['transactions']),'identity-existing-maintenance-recovery-required')
    identity_journals=list((project.root/'.maintenance').glob('identity-*.json'))
    require(all(loads(p.read_text(encoding='utf-8')).get('state') in ('COMPLETED','ROLLED_BACK') for p in identity_journals),'identity-existing-migration-recovery-required')
    harness,_=harness_snapshot(project,old)
    artifacts={'knowledge':files(project.base),'harness':files(project.root/'.harness'),
               'maintenance':files(project.root/'.maintenance')}
    value={'version':1,'operation':'sqlite-identity-migration','rule':RULE,'root':str(project.root),
           'new_identity':project.identity,'old_identity':old,'workspace':str(work),
           'source':result,'harness':harness,'artifacts':artifacts,
           'mapping':{'records':'active byte-identical payloads','revisions':'active identical lifecycle history',
                      'history':'active immutable audit events',
                      'other_rows':'identity_archive; read with identity-history; never execution authority',
                      '.knowledge/*':str(work/'knowledge-original'),'.harness/*':str(work/'harness-original'),
                      'absolute_evidence':'unchanged and unresolved; no old root inferred, no freshness asserted'},
           'collision_policy':'in-place only; exact approved source, no unrelated destination merge'}
    return {'ok':True,'preview':value,'fingerprint':fingerprint(value),
            'warning':'Old queue/plans/sessions and all operational memory become accessible history only. Revalidation/re-enrollment is explicit; no automatic apply or grant.'}

def no_hot_journal(project):
    for relative in ('.knowledge/store.sqlite3-journal','.harness/runs.sqlite3-journal'):
        path=safe_path(project.root/relative)
        require(not path.exists() or path.stat().st_size==0,'identity-unresolved-rollback-journal',
                {'path':str(path),'next_action':'Use the original runtime recovery procedure first; this migration does not delete recovery journals.'})


def harness_snapshot(project,old):
    path=project.root/'.harness/runs.sqlite3'
    if not path.exists():return None,None
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
        db.execute('BEGIN')
        expected={'meta','runs','events','actions','outbox','cancels'}
        schema=list(db.execute('SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name'))
        require({n for t,n,_,_ in schema if t=='table'}==expected and all(t not in ('trigger','view') for t,_,_,_ in schema)
                and all(t!='index' or sql is None or n=='ix_outbox_run' for t,n,_,sql in schema),'identity-unknown-harness-schema')
        from .sqlite_indexes import check
        check(db)  # Only the supported optional outbox index.
        identity=dict(db.execute('SELECT key,value FROM meta')).get('project')
        require(identity in (old,project.identity),'identity-unrelated-harness-store')
        tables={}
        for table in sorted(expected):
            columns=[r[1] for r in db.execute('PRAGMA table_info('+table+')')]
            expected_columns={'meta':['key','value'],'runs':['id','payload'],'events':['run','sequence','payload'],
                              'actions':['run','id','payload'],'outbox':['id','run','payload'],'cancels':['run','at']}
            require(columns==expected_columns[table],'identity-unknown-harness-columns',{'table':table})
            rows=list(db.execute('SELECT * FROM '+table+' ORDER BY '+','.join(str(n+1) for n in range(len(columns)))))
            tables[table]={'columns':columns,'count':len(rows),'rows':[digest(list(row)) for row in rows]}
    prior=copy(project);prior.identity=identity
    data,_=m.database(path,prior)
    return {'identity':identity,'schema':[list(r) for r in schema],'tables':tables},data


def physical_copy(source,target):
    """Preserve pre-release physical bytes including WAL/journal, plus API snapshot."""
    if not source.exists():return {}
    safe_tree(source);target.mkdir(mode=0o700);manifest={}
    for p in sorted(source.rglob('*')):
        relative=p.relative_to(source);dest=target/relative
        if p.is_dir():dest.mkdir(mode=0o700);continue
        if p.name in ('writer.lock','init.lock'):continue
        require(p.stat().st_size<=LIMIT,'identity-physical-file-too-large')
        before=m.sha(p.read_bytes());shutil.copyfile(p,dest)
        with dest.open('r+b') as stream:os.fsync(stream.fileno())
        require(before==m.sha(dest.read_bytes())==m.sha(p.read_bytes()),'identity-physical-source-changing')
        manifest[relative.as_posix()]=before
    return manifest


def rows_digest(db):
    values={}
    for table in ('records','revisions','history'):
        if db.execute('SELECT 1 FROM sqlite_schema WHERE type=\'table\' AND name=?',(table,)).fetchone():
            values[table]=list(db.execute('SELECT * FROM '+table+' ORDER BY '+('id,revision' if table=='revisions' else 'id' if table=='records' else 'sequence')))
    return digest(values)


def validate_archive(db):
    return view(db,'identity-archive',lambda:_validate_archive(db))


def _validate_archive(db):
    row=db.execute('SELECT value FROM metadata WHERE key=?',(KEY,)).fetchone()
    has=db.execute("SELECT 1 FROM sqlite_schema WHERE type='table' AND name='identity_archive'").fetchone()
    require(bool(row)==bool(has),'identity-archive-marker-mismatch')
    if not row:return None
    value=loads(row[0]);require(isinstance(value,dict) and value.get('version')==1 and value.get('rule')==RULE
        and value.get('new_identity')==dict(db.execute('SELECT key,value FROM metadata'))['project']
        and isinstance(value.get('tables'),dict) and set(CORE)<=set(value['tables'])<=set(CORE)|set(P1)|set(DISCOVERY)|set(OPS)|set(cf.TABLES)|set(cs.TABLES)|set(cc.TABLES), 'identity-corrupt-archive-marker')
    for table,entry in value['tables'].items():
        require(isinstance(entry,dict) and entry.get('columns')==list({**CORE,**P1,**DISCOVERY,**OPS,**cf.TABLES,**cs.TABLES,**cc.TABLES}[table])
                and type(entry.get('count')) is int and entry['count']>=0 and isinstance(entry.get('rows'),list)
                and len(entry['rows'])==entry['count']
                and all(isinstance(h,str) and re.fullmatch('[a-f0-9]{64}',h) for h in entry['rows']), 'identity-corrupt-archive-table')
    actual={}
    for table,ordinal,payload in db.execute('SELECT source_table,ordinal,payload FROM identity_archive ORDER BY source_table,ordinal'):
        require(table in value['tables'],'identity-unknown-archived-table');items=actual.setdefault(table,[])
        require(ordinal==len(items),'identity-archive-order-mismatch');items.append(digest(loads(payload)))
    require(all(actual.get(t,[])==entry['rows'] for t,entry in value['tables'].items()),'identity-archive-content-mismatch')
    return value


def stage(project,snapshot,source,rows,work,txn):
    staged=work/'staged';staged.mkdir()
    with closing(sqlite3.connect(staged/'store.sqlite3')) as db:
        db.execute('PRAGMA synchronous=FULL');create_tables(db,project.identity)
        for table in ('records','history'):
            db.executemany('INSERT INTO '+table+' VALUES ('+','.join('?' for _ in CORE[table])+')',rows[table])
        if 'revisions' in rows:
            for table in P1:
                db.execute(P1_SQL[table])
            db.executemany('INSERT INTO revisions VALUES (?,?,?)',rows['revisions'])
            db.execute("INSERT INTO metadata VALUES ('p1','1')")
        if 'confluence_pages' in rows:
            version='2' if 'confluence_blobs' in rows else '1'
            for sql in cf.schema_sql(version):db.execute(sql)
            for table,columns in cf.schema_tables(version).items():
                values=rows[table]
                if table=='confluence_pages':
                    values=[]
                    for row in rows[table]:
                        value=loads(row[-1])
                        if value.get('analysis_checkpoint'):
                            value.update(archived_analysis_checkpoint=value['analysis_checkpoint'],analysis_checkpoint=None,analysis_offset=0,processing_status='ANALYSIS_REQUIRED')
                        values.append((*row[:-1],canonical_json(value)))
                db.executemany('INSERT INTO '+table+' VALUES ('+','.join('?' for _ in columns)+')',values)
            db.execute("INSERT INTO metadata VALUES ('confluence-schema',?)",(version,))
        db.execute('CREATE TABLE identity_archive(source_table TEXT NOT NULL,ordinal INTEGER NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(source_table,ordinal))')
        for table,items in rows.items():
            db.executemany('INSERT INTO identity_archive VALUES (?,?,?)',[(table,n,canonical_json(list(row))) for n,row in enumerate(items)])
        manifest={'version':1,'rule':RULE,'transaction':txn,'old_identity':source['old_identity'],
                  'new_identity':project.identity,'tables':source['tables'],'original_database':str(work/'source.sqlite3'),
                  'artifacts':snapshot['artifacts'],'workspace':str(work)}
        db.execute('INSERT INTO metadata VALUES (?,?)',(KEY,canonical_json(manifest)));db.commit()
        require(rows_digest(db)==digest({t:sorted(rows[t],key=lambda r:(r[0],r[1]) if t=='revisions' else r[0]) for t in ('records','revisions','history') if t in rows}),'identity-active-preservation-failed')
    # Preserve the explicit discovery policy, not old machine/provider enrollment.
    config=project.base/'discovery.json'
    if config.exists():(staged/'discovery.json').write_bytes(config.read_bytes())
    _validate_staged(project,staged)
    return staged


def journal_path(project,tid):
    require(isinstance(tid,str) and re.fullmatch('[a-f0-9]{32}',tid),'invalid-identity-transaction')
    return safe_path(project.root/'.maintenance'/('identity-'+tid+'.json'))


def read_journal(project,tid):
    journal=loads(journal_path(project,tid).read_text(encoding='utf-8'))
    value=journal['preview']
    require(journal.get('version')==1 and journal.get('kind')==KEY and journal.get('id')==tid
            and value.get('version')==1 and value.get('operation')=='sqlite-identity-migration' and value.get('rule')==RULE
            and journal.get('approval')==fingerprint(value) and digest(value)[:32]==tid
            and value.get('root')==str(project.root) and value.get('new_identity')==project.identity,'identity-invalid-recovery-journal')
    work=Path(value['workspace'])
    require(work.is_absolute() and '..' not in work.parts and not work.is_relative_to(project.root)
            and not project.root.is_relative_to(work),'identity-invalid-recovery-workspace')
    safe_tree(work)
    return journal


def apply(root,value,approval):
    require(isinstance(value,dict) and value.get('operation')=='sqlite-identity-migration' and value.get('rule')==RULE
            and value.get('version')==1 and approval==fingerprint(value),'exact-identity-preview-approval-required')
    no_hot_journal(Project(root))
    with m.frozen(root) as project:
        require(value['root']==str(project.root) and value['new_identity']==project.identity,'identity-destination-mismatch')
        tid=digest(value)[:32];jp=journal_path(project,tid)
        if jp.exists():
            prior=read_journal(project,tid)
            require(prior['preview']==value and prior['approval']==approval and prior['state']=='COMPLETED','identity-existing-transaction-requires-recovery')
            with Store(root).connection() as db:require(validate_archive(db)['transaction']==tid,'identity-completed-destination-conflict')
            return {'ok':True,'state':'COMPLETED','result':'already-completed','transaction':tid}
        current=_preview(project,value['old_identity'],value['workspace'])['preview']
        require(current==value,'identity-stale-preview')
        work=Path(value['workspace'])
        journal={'version':1,'kind':KEY,'id':tid,'preview':value,'approval':approval,'state':'BUILDING'}
        m.write(jp,journal);work.mkdir(mode=0o700);fault('identity-building')
        with closing(sqlite3.connect(project.db.as_uri()+'?mode=ro',uri=True)) as db:
            db.execute('BEGIN');source,rows=inventory_connection(db,project,value['old_identity'])
            with closing(sqlite3.connect(work/'source.sqlite3')) as saved:db.backup(saved)
        # The backup is validated under its original identity, never rewritten.
        with closing(sqlite3.connect((work/'source.sqlite3').as_uri()+'?mode=ro',uri=True)) as db:
            backed,_=inventory_connection(db,project,value['old_identity']);require(backed==source,'identity-backup-mismatch')
        staged=stage(project,value,source,rows,work,tid)
        harness,data=harness_snapshot(project,value['old_identity'])
        require(harness==value['harness'],'identity-harness-changed')
        if data is not None:
            with (work/'harness-source.sqlite3').open('xb') as out:out.write(data);out.flush();os.fsync(out.fileno())
        physical={'knowledge':physical_copy(project.base,work/'physical-knowledge'),
                  'harness':physical_copy(project.root/'.harness',work/'physical-harness')}
        m.write(work/'physical-manifest.json',physical)
        expected={'store.sqlite3':m.sha((staged/'store.sqlite3').read_bytes()),**files(staged)}
        require(inventory(root,value['old_identity'])==value['source'] and files(project.base)==value['artifacts']['knowledge']
                and files(project.root/'.harness')==value['artifacts']['harness'],'identity-source-changed-before-publication')
        journal.update(state='PREPARED',published_files=expected)
        m.write(jp,journal)
        fence=project.root/'.maintenance/active.json';m.write(fence,{'version':1,'kind':KEY,'project':project.identity,'transaction':tid})
        fault('identity-fenced')
        m.release_reservations(project);project._maintenance_execution.release_metadata_handle()
        os.rename(project.base,work/'knowledge-original');fault('identity-old-knowledge-archived')
        if (project.root/'.harness').exists():os.rename(project.root/'.harness',work/'harness-original')
        fault('identity-old-harness-archived')
        os.rename(staged,project.base);fault('identity-published')
        _validate_staged(project,project.base)
        journal['state']='COMPLETED';m.write(jp,journal);fault('identity-committed');fence.unlink()
        return {'ok':True,'state':'COMPLETED','transaction':tid,'backup':str(work/'source.sqlite3'),
                'original_state':str(work),'validation':'integrity, full product and row-preservation checks passed',
                'next_action':'Inspect identity-history; re-enroll operational instructions explicitly. knowledge-init reconciles retained canonical data; no candidate approval was transferred.'}


def rollback_value(project,journal):
    return {'version':1,'operation':'sqlite-identity-rollback','root':str(project.root),
            'transaction':journal['id'],'published_files':journal['published_files']}


def rollback_preview(root,tid):
    with m.frozen(root) as project:
        journal=read_journal(project,tid)
        require(journal['state']=='COMPLETED' and journal['preview']['new_identity']==project.identity,'identity-rollback-not-completed')
        actual={'store.sqlite3':m.sha(project.db.read_bytes()),**files(project.base)}
        require(actual==journal['published_files'],'identity-rollback-new-state-changed')
        value=rollback_value(project,journal)
        return {'ok':True,'preview':value,'fingerprint':fingerprint(value),
                'warning':'Restores old identity and original state. Do not use after new project writes; preserve/backup those writes first.'}


def recover(root,tid,rollback=False,approval=None):
    with m.frozen(root,recovery=True) as project:
        jp=journal_path(project,tid);journal=read_journal(project,tid)
        value=journal['preview']
        work=Path(value['workspace']);safe_tree(work)
        require(not work.is_relative_to(project.root),'identity-invalid-recovery-workspace')
        fence=project.root/'.maintenance/active.json'
        if fence.exists():
            active=loads(fence.read_text(encoding='utf-8'))
            require(active.get('kind')==KEY and active.get('project')==project.identity and active.get('transaction')==tid,'identity-unrelated-recovery-fence')
        if rollback:require(approval==fingerprint(rollback_value(project,journal)),'exact-identity-rollback-approval-required')
        if journal['state']=='COMPLETED' and not rollback:
            with Store(root).connection() as db:require(validate_archive(db)['transaction']==tid,'identity-completed-destination-conflict')
            _validate_staged(project,project.base);fence.unlink(missing_ok=True);return {'ok':True,'state':'COMPLETED','transaction':tid}
        require(journal['state'] in ('BUILDING','PREPARED','ROLLED_BACK') or rollback,'identity-unsupported-recovery-state')
        m.write(fence,{'version':1,'kind':KEY,'project':project.identity,'transaction':tid})
        m.release_reservations(project);project._maintenance_execution.release_metadata_handle()
        original=work/'knowledge-original'
        if original.exists():
            with closing(sqlite3.connect((original/'store.sqlite3').as_uri()+'?mode=ro',uri=True)) as db:
                old,_=inventory_connection(db,project,value['old_identity'],original)
                require(old['logical_identity']==value['source']['logical_identity'],'identity-original-changed')
            if project.base.exists():
                actual={'store.sqlite3':m.sha(project.db.read_bytes()),**files(project.base)}
                require(actual==journal['published_files'],'identity-rollback-new-state-changed')
                os.rename(project.base,work/'rolled-back-new')
            os.rename(original,project.base)
        else:require(inventory(root,value['old_identity'])==value['source'],'identity-original-unavailable')
        original_harness=work/'harness-original'
        if original_harness.exists():
            require(not (project.root/'.harness').exists(),'identity-rollback-harness-conflict')
            os.rename(original_harness,project.root/'.harness')
        require(inventory(root,value['old_identity'])==value['source'] and files(project.base)==value['artifacts']['knowledge']
                and files(project.root/'.harness')==value['artifacts']['harness'],'identity-rollback-validation-failed')
        harness,_=harness_snapshot(project,value['old_identity'])
        require(harness==value['harness'],'identity-rollback-harness-validation-failed')
        journal['state']='ROLLED_BACK';m.write(jp,journal);fence.unlink()
        return {'ok':True,'state':'ROLLED_BACK','transaction':tid,'warning':'Original identity mismatch is restored intentionally; no data was initialized or rescanned.'}


def history(root,table=None,cursor=0,limit=20,contents=False):
    require(type(cursor) is int and cursor>=0 and type(limit) is int and 1<=limit<=100,'invalid-history-page')
    with Store(root).connection() as db:
        manifest=validate_archive(db);require(manifest is not None,'identity-history-absent')
        if table is None:return {'ok':True,'manifest':manifest,'authority':'historical-only; no approvals/grants/process ownership'}
        require(table in manifest['tables'],'unknown-identity-history-table')
        rows=list(db.execute('SELECT ordinal,payload FROM identity_archive WHERE source_table=? ORDER BY ordinal LIMIT ? OFFSET ?',(table,limit,cursor)))
        return {'ok':True,'table':table,'columns':manifest['tables'][table]['columns'],
                'rows':[{'ordinal':n,'hash':digest(loads(p)),**({'values':loads(p)} if contents else {})} for n,p in rows],
                'next_cursor':cursor+limit if cursor+limit<manifest['tables'][table]['count'] else None,
                'total':manifest['tables'][table]['count'],'authority':'historical-only'}


def summary(db):
    value=validate_archive(db)
    if value is None:return None
    return {'transaction':value['transaction'],'old_identity':value['old_identity'],'new_identity':value['new_identity'],
            'tables':{t:{'count':entry['count'],'disposition':entry['disposition']} for t,entry in value['tables'].items()},
            'read_command':'knowledge.maintain_cli identity-history','authority':'historical-only'}
