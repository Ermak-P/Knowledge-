"""Native Confluence snapshots. No HTTP client, credentials or Git inventory.

MCP results are submitted source data. Hash verification attests local snapshot
integrity, never independent live access to Confluence or implementation truth.
"""
from copy import deepcopy
from collections import OrderedDict
from datetime import datetime
import hashlib
import re
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
from .util import require,KnowledgeError,canonical_json,digest,loads
from .sqlite_snapshot import view

SCHEMA='2'
SUPPORTED_SCHEMAS=('1','2')
TABLES={'confluence_pages':('identity','instance','page_id','latest_version','payload'),
        'confluence_snapshots':('snapshot','source_id','version','content_hash','payload','checksum'),
        'confluence_blobs':('content_hash','content')}
TABLE_SQL={
 'confluence_pages':'CREATE TABLE confluence_pages(identity TEXT PRIMARY KEY,instance TEXT NOT NULL,page_id TEXT NOT NULL,latest_version INTEGER NOT NULL,payload TEXT NOT NULL,UNIQUE(instance,page_id))',
 'confluence_snapshots':'CREATE TABLE confluence_snapshots(snapshot TEXT PRIMARY KEY,source_id TEXT NOT NULL,version INTEGER NOT NULL,content_hash TEXT NOT NULL,payload TEXT NOT NULL,checksum TEXT NOT NULL,UNIQUE(source_id,version))',
 'confluence_blobs':'CREATE TABLE confluence_blobs(content_hash TEXT PRIMARY KEY,content TEXT NOT NULL)'}
INDEX_SQL={'confluence_snapshot_source':'CREATE INDEX confluence_snapshot_source ON confluence_snapshots(source_id,version)'}
ROLES=('requirement','architecture','rationale','integration-contract','configuration','deployment','testing','limitation','historical','proposed','implementation')


def schema_tables(version):return {k:v for k,v in TABLES.items() if version=='2' or k!='confluence_blobs'}
def schema_sql(version):return [TABLE_SQL[k] for k in schema_tables(version)]+list(INDEX_SQL.values())


def is_binding(source):return isinstance(source,dict) and source.get('kind')=='confluence'


def timestamp(value):
    require(isinstance(value,str),'invalid-confluence-timestamp')
    try:
        parsed=datetime.fromisoformat(value.replace('Z','+00:00'));require(parsed.tzinfo is not None,'confluence-timestamp-timezone-required')
        return parsed.isoformat()
    except ValueError as error:raise KnowledgeError('invalid-confluence-timestamp') from error


def url(value):
    require(isinstance(value,str) and len(value)<=4096 and not any(ord(c)<32 for c in value),'invalid-confluence-url')
    try:
        parsed=urlsplit(value);port=parsed.port
        require(parsed.scheme in ('https','http') and parsed.hostname and parsed.username is None and parsed.password is None,'invalid-confluence-url')
        query=parse_qsl(parsed.query,keep_blank_values=True)
        require(all(k in ('pageId','spaceKey','title') for k,_ in query),'confluence-url-query-not-permitted')
        host=parsed.hostname.lower();host=('['+host+']') if ':' in host else host
        if port is not None and port!=(443 if parsed.scheme=='https' else 80):host+=':'+str(port)
        return urlunsplit((parsed.scheme,host,parsed.path or '/',urlencode(query),''))
    except ValueError as error:raise KnowledgeError('invalid-confluence-url') from error


def instance_id(value):
    require(isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}',value),'invalid-confluence-instance')
    return url(value).rstrip('/') if value.startswith(('https://','http://')) else value


def page_id(value):
    require(isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}',value),'invalid-confluence-page-id')
    return value


def identity(instance,page):return digest(['confluence-source-v1',instance_id(instance),page_id(page)])


def normalize(content):
    require(isinstance(content,str),'invalid-confluence-content')
    content=content.removeprefix('\ufeff').replace('\r\n','\n').replace('\r','\n')
    try:raw=content.encode('utf-8')
    except UnicodeError as error:raise KnowledgeError('invalid-confluence-content') from error
    require(len(raw)<=16*1024*1024 and '\x00' not in content,'confluence-content-limit-or-binary')
    return content,'sha256:'+hashlib.sha256(raw).hexdigest()


def binding_shape(source):
    require(isinstance(source,dict) and set(source) in ({'kind','identity','revision','snapshot'},{'kind','identity','revision','snapshot','deletion'},{'kind','identity','revision','snapshot','revalidation'}) and source['kind']=='confluence',
            'invalid-confluence-binding',{'expected_kind':'confluence','required':['identity','revision','snapshot']})
    require(all(isinstance(source[k],str) and re.fullmatch('[a-f0-9]{64}',source[k]) for k in ('identity','snapshot')),
            'invalid-confluence-binding-identity',{'expected_kind':'confluence'})
    require(type(source['revision']) is int and source['revision']>0,'invalid-confluence-page-version',{'identity':source['identity']})
    if 'deletion' in source:require(isinstance(source['deletion'],str) and re.fullmatch('[a-f0-9]{64}',source['deletion']),'invalid-confluence-deletion-binding')
    if 'revalidation' in source:require(isinstance(source['revalidation'],str) and re.fullmatch('[a-f0-9]{64}',source['revalidation']),'invalid-confluence-revalidation-binding')
    return source


def _validate_control(db):
    marker=db.execute("SELECT value FROM metadata WHERE key='confluence-schema'").fetchone()
    found={n for n, in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'confluence_%'")}
    if marker is None:
        require(not found,'incomplete-confluence-extension');return False
    require(marker[0] in SUPPORTED_SCHEMAS and set(schema_tables(marker[0]))<=found,'unsupported-confluence-extension')
    for table,columns in schema_tables(marker[0]).items():
        require(tuple(r[1] for r in db.execute('PRAGMA table_info('+table+')'))==columns,'corrupt-confluence-schema',{'table':table})
    from .confluence_sync import validate_control as validate_sync
    validate_sync(db)
    from .confluence_command import validate_control as validate_command
    validate_command(db)
    return True


def validate_control(db):return view(db,'confluence-schema',lambda:_validate_control(db))


def enable(db):
    if validate_control(db):
        version=db.execute("SELECT value FROM metadata WHERE key='confluence-schema'").fetchone()[0]
        if version=='1':
            db.execute(TABLE_SQL['confluence_blobs'])
            identifiers=[r[0] for r in db.execute('SELECT snapshot FROM confluence_snapshots')]
            for identifier in identifiers:
                payload,checksum=db.execute('SELECT payload,checksum FROM confluence_snapshots WHERE snapshot=?',(identifier,)).fetchone()
                data=loads(payload);require(digest(data)==checksum,'corrupt-confluence-snapshot-checksum')
                text,hashed=normalize(data.pop('content'));require(hashed==data['content_hash'],'corrupt-confluence-snapshot')
                db.execute('INSERT OR IGNORE INTO confluence_blobs VALUES (?,?)',(hashed,text));data['body_ref']=hashed
                db.execute('UPDATE confluence_snapshots SET payload=?,checksum=? WHERE snapshot=?',(canonical_json(data),digest(data),identifier))
            db.execute("UPDATE metadata SET value=? WHERE key='confluence-schema'",(SCHEMA,))
        return
    from .lifecycle import enabled
    require(enabled(db),'upgrade-required')
    for sql in (*TABLE_SQL.values(),*INDEX_SQL.values()):db.execute(sql)
    db.execute("INSERT INTO metadata VALUES ('confluence-schema',?)",(SCHEMA,))


def page(db,source_id):
    def read():
        row=db.execute('SELECT instance,page_id,latest_version,payload FROM confluence_pages WHERE identity=?',(source_id,)).fetchone()
        require(row is not None,'unknown-confluence-page',{'identity':source_id,'next_action':'Register a snapshot retrieved through Confluence MCP.'})
        data=loads(row[3]);require(data['identity']==source_id==identity(row[0],row[1]) and data['instance']==row[0] and data['page_id']==row[1] and data['latest_version']==row[2],'corrupt-confluence-page',{'identity':source_id})
        return data
    return view(db,('confluence-page',source_id),read)


def snapshot_info(db,identifier):
    def read():
        row=db.execute('SELECT source_id,version,content_hash,payload,checksum FROM confluence_snapshots WHERE snapshot=?',(identifier,)).fetchone()
        require(row is not None,'unknown-confluence-snapshot',{'snapshot':identifier,'next_action':'Submit the exact MCP page revision before its candidates.'})
        data=loads(row[3]);require(digest(data)==row[4],'corrupt-confluence-snapshot-checksum',{'snapshot':identifier})
        require(data['content_hash']==row[2] and data['identity']==row[0] and data['version']==row[1]
                and identifier==digest(['confluence-revision-v1',row[0],row[1],data['representation'],row[2]]),'corrupt-confluence-snapshot',{'snapshot':identifier})
        require(identity(data['instance'],data['page_id'])==data['identity'] and url(data['url'])==data['url'],'corrupt-confluence-snapshot-metadata',{'snapshot':identifier})
        timestamp(data['retrieved_at']);return data
    return view(db,('confluence-snapshot-info',identifier),read)


def snapshot(db,identifier):
    data=snapshot_info(db,identifier)
    if 'content' in data:
        text,hashed=normalize(data['content']);require(text==data['content'] and hashed==data['content_hash'],'corrupt-confluence-snapshot')
        return data
    require(data.get('body_ref')==data['content_hash'],'corrupt-confluence-body-reference')
    cache=view(db,'confluence-body-lru',lambda:dict(rows=OrderedDict(),bytes=0));rows=cache['rows'];hashed=data['body_ref']
    if hashed in rows:
        text,size=rows.pop(hashed);rows[hashed]=(text,size)
    else:
        row=db.execute('SELECT content FROM confluence_blobs WHERE content_hash=?',(hashed,)).fetchone()
        require(row is not None,'missing-confluence-snapshot-body',{'snapshot':identifier})
        text,actual=normalize(row[0]);require(text==row[0] and actual==hashed,'corrupt-confluence-snapshot-body',{'snapshot':identifier})
        size=len(text.encode('utf-8'))
        while rows and cache['bytes']+size>8*1024*1024:
            _,(_,removed)=rows.popitem(last=False);cache['bytes']-=removed
        if size<=8*1024*1024:rows[hashed]=(text,size);cache['bytes']+=size
    return {**data,'content':text}


def register(store,value):
    required={'instance','page_id','version','title','url','content','retrieved_at','representation'}
    require(isinstance(value,dict) and required<=set(value)<=required|{'content_hash','space_key','modified_at'},'invalid-confluence-snapshot-fields')
    instance=instance_id(value['instance']);pid=page_id(value['page_id']);version=value['version']
    require(type(version) is int and version>0,'invalid-confluence-page-version')
    require(isinstance(value['title'],str) and 0<len(value['title'])<=4096,'invalid-confluence-title')
    require(value['representation'] in ('text','markdown','storage'),'unsupported-confluence-representation')
    text,hashed=normalize(value['content']);source_id=identity(instance,pid)
    require(value.get('content_hash',hashed)==hashed,'confluence-content-hash-mismatch',{'identity':source_id,'version':version,'calculated_hash':hashed})
    identifier=digest(['confluence-revision-v1',source_id,version,value['representation'],hashed])
    data=dict(identity=source_id,instance=instance,page_id=pid,version=version,title=value['title'],url=url(value['url']),content=text,
              representation=value['representation'],content_hash=hashed,retrieved_at=timestamp(value['retrieved_at']),integrity='locally-verified-mcp-snapshot; live verification not independently attested')
    for key in ('space_key','modified_at'):
        if key in value:
            require(isinstance(value[key],str) and len(value[key])<=512,'invalid-confluence-metadata')
            data[key]=timestamp(value[key]) if key=='modified_at' else value[key]
    with store.connection(True) as db:
        enable(db)
        old=db.execute('SELECT snapshot FROM confluence_snapshots WHERE source_id=? AND version=?',(source_id,version)).fetchone()
        require(old is None or old[0]==identifier,'confluence-version-content-conflict',{'identity':source_id,'revision':version,'next_action':'Check native version and content representation; do not overwrite the registered revision.'})
        if old:snapshot(db,old[0])
        else:
            db.execute('INSERT OR IGNORE INTO confluence_blobs VALUES (?,?)',(hashed,text))
            persisted={k:v for k,v in data.items() if k!='content'};persisted['body_ref']=hashed
            db.execute('INSERT INTO confluence_snapshots VALUES (?,?,?,?,?,?)',(identifier,source_id,version,hashed,canonical_json(persisted),digest(persisted)))
        row=db.execute('SELECT payload FROM confluence_pages WHERE identity=?',(source_id,)).fetchone()
        current=loads(row[0]) if row else dict(identity=source_id,instance=instance,page_id=pid,latest_version=version,last_analyzed_version=None,last_applied_version=None)
        if version>=current['latest_version']:
            current.update(latest_version=version,latest_snapshot=identifier,title=data['title'],url=data['url'],content_hash=hashed,last_checked=data['retrieved_at'],processing_status='SNAPSHOT_REGISTERED')
            for key in ('space_key','modified_at'):
                if key in data:current[key]=data[key]
        db.execute('INSERT OR REPLACE INTO confluence_pages VALUES (?,?,?,?,?)',(source_id,instance,pid,current['latest_version'],canonical_json(current)))
    source=dict(kind='confluence',identity=source_id,revision=version,snapshot=identifier)
    from .confluence_sync import on_snapshot
    work=on_snapshot(store,source)
    if old is None:
        with store.connection(True) as db:
            row=db.execute("SELECT value FROM metadata WHERE key='confluence-gc-registrations'").fetchone()
            count=int(row[0])+1 if row else 1
            db.execute("INSERT OR REPLACE INTO metadata VALUES ('confluence-gc-registrations',?)",(str(count),))
        if count%64==0:
            from .confluence_sync import collect
            work['retention']=collect(store)
    return {'ok':True,'result':'existing' if old else 'registered','source':source,'sync':work,
            'content_hash':hashed,'integrity':data['integrity'],'canonical_unchanged':True}


def verify_binding(db,source,fresh=True):
    binding_shape(source);require(validate_control(db),'confluence-not-registered',{'identity':source['identity'],'expected_kind':'confluence'})
    data=snapshot(db,source['snapshot']);current=page(db,source['identity'])
    require(data['identity']==source['identity'] and data['version']==source['revision'],'confluence-snapshot-binding-mismatch',{'identity':source['identity'],'revision':source['revision'],'snapshot':source['snapshot']})
    if fresh:
        if source.get('deletion'):
            from .confluence_sync import event
            proof=event(db,source['deletion'])
            require(proof['kind']=='deleted' and proof['identity']==source['identity'] and current.get('availability')=='deleted' and current.get('deletion_event')==source['deletion'],'stale-confluence-deletion-binding')
        else:
            require(current.get('availability')!='deleted' and current.get('processing_status')!='DELETED','confluence-page-confirmed-deleted',{'identity':source['identity'],'revision':source['revision']})
        require(source.get('deletion') is not None or current['latest_version']==source['revision'],'stale-confluence-revision',{'identity':source['identity'],'candidate_revision':source['revision'],'observed_revision':current['latest_version'],'next_action':'Analyze the observed page revision and prepare a new exact approval; Git rescan is unnecessary.'})
    return data


def verify_evidence(db,evidence,fresh=True):
    source=evidence['source'];binding={k:source[k] for k in ('kind','identity','revision','snapshot')};data=verify_binding(db,binding,fresh)
    require(source['reference']==data['url'] and evidence.get('content_hash')==data['content_hash'],'confluence-evidence-snapshot-mismatch',{'evidence':evidence['id'],'identity':binding['identity']})
    require(isinstance(evidence['description'],str) and 0<len(evidence['description'])<=8192 and evidence['description'] in data['content'],'confluence-evidence-quote-not-found',{'evidence':evidence['id'],'snapshot':binding['snapshot']})
    return data


def validate_candidate(db,item,fresh=True):
    source=item.get('source')
    if is_binding(source):verify_binding(db,source,fresh)
    for op in item.get('operations',[]):
        if fresh and is_binding(source) and source.get('deletion') and op['kind']!='evidence':
            row=db.execute('SELECT payload FROM revisions WHERE id=? AND revision=?',(op['id'],op['expected'])).fetchone()
            require(op['kind']=='claims' and op['action']=='update' and row is not None,'confluence-deletion-only-reevaluates-existing-claims')
            original=loads(row[0])['record'];updated=op['payload'];mutable={'status','last_verified','evidence'}
            require({k:v for k,v in original.items() if k not in mutable}=={k:v for k,v in updated.items() if k not in mutable}
                    and set(updated['evidence'])<=set(original['evidence']) and updated['status'] in (original['status'],'NEEDS_HUMAN_CONFIRMATION')
                    and updated['last_verified'] in (None,original['last_verified']),'confluence-deletion-cannot-authorize-new-meaning')
        evidence=op['payload'] if op['kind']=='evidence' else None
        if evidence and is_binding(source):require(is_binding(evidence.get('source')),'confluence-candidate-needs-native-evidence',{'evidence':evidence['id']})
        if evidence and is_binding(evidence.get('source')):
            historical=op['action']=='update' and evidence['status'] in ('retracted','superseded')
            if historical:
                row=db.execute('SELECT payload FROM records WHERE id=?',(evidence['id'],)).fetchone()
                require(row is not None,'unknown-confluence-evidence-correction')
                original=loads(row[0]);require({**original,'status':evidence['status']}==evidence,'confluence-evidence-correction-must-preserve-payload')
                if fresh and not (source or {}).get('deletion'):
                    from .confluence_sync import verify_revalidation
                    verify_revalidation(db,source,op)
            verify_evidence(db,evidence,fresh and not historical)
            if is_binding(source):
                require(evidence['source']['identity']==source['identity'] and (historical or all(evidence['source'][k]==source[k] for k in ('kind','identity','revision','snapshot'))),'confluence-candidate-evidence-binding-mismatch',{'evidence':evidence['id']})
            if source and source.get('deletion'):require(historical,'confluence-deletion-cannot-add-positive-evidence')


def pending_partition(db,pending):
    remaining=dict(pending);skipped=[]
    from .confluence_sync import incomplete_candidates
    incomplete=incomplete_candidates(db,pending)
    for cid,item in pending.items():
        if not is_binding(item.get('source')):continue
        if cid in incomplete:
            del remaining[cid];skipped.append(dict(candidate=cid,reason='confluence-analysis-resume-required',details={'checkpoint':incomplete[cid],'next_action':'Resume the saved analysis outbox; do not repeat semantic analysis.'}));continue
        try:verify_binding(db,item['source'])
        except KnowledgeError as error:
            if error.code not in ('stale-confluence-revision','confluence-page-confirmed-deleted'):raise
            del remaining[cid];skipped.append(dict(candidate=cid,reason=error.code,details=error.details))
    blocked=[dict(code=entry['reason'],details=entry['details']) for entry in skipped] if skipped and not remaining else []
    return remaining,skipped,blocked


def evidence_freshness(store,evidence,db=None):
    if db is None:
        with store.connection() as connection:return evidence_freshness(store,evidence,connection)
    try:
        old=verify_evidence(db,evidence,False);page_data=page(db,evidence['source']['identity'])
        if page_data.get('availability')=='deleted':return 'confluence-page-confirmed-deleted'
        if page_data['latest_version']==old['version']:return 'current-registered-confluence-snapshot'
        latest=snapshot(db,page_data['latest_snapshot'])
        if latest['version']==page_data['latest_version'] and latest['content_hash']==old['content_hash'] and latest['representation']==old['representation']:return 'unchanged-content-newer-confluence-version'
        return 'stale-confluence-revision'
    except KnowledgeError as error:
        if error.code.startswith(('corrupt-','invalid-')):raise
        return error.code


def integrity(db):
    if not validate_control(db):return None
    for identifier, in db.execute('SELECT identity FROM confluence_pages'):page(db,identifier)
    for identifier, in db.execute('SELECT snapshot FROM confluence_snapshots'):snapshot(db,identifier)
    if db.execute("SELECT value FROM metadata WHERE key='confluence-schema'").fetchone()==('2',):
        for hashed,content in db.execute('SELECT content_hash,content FROM confluence_blobs'):
            text,actual=normalize(content);require(text==content and hashed==actual,'corrupt-confluence-snapshot-body')
    from .confluence_sync import integrity as sync_integrity
    sync_integrity(db)
    from .confluence_command import integrity as command_integrity
    command_integrity(db)
    return {'pages':db.execute('SELECT COUNT(*) FROM confluence_pages').fetchone()[0],'snapshots':db.execute('SELECT COUNT(*) FROM confluence_snapshots').fetchone()[0],'live_verification':False}


def export(db):
    if not validate_control(db):return {}
    integrity(db)
    return {'confluence':{'version':1,'pages':[loads(p) for p, in db.execute('SELECT payload FROM confluence_pages ORDER BY identity')],
                         'snapshots':[{'snapshot':s,**snapshot(db,s)} for s, in db.execute('SELECT snapshot FROM confluence_snapshots ORDER BY snapshot')]}}


def dispatch(store,action,request):
    if action in ('observe','failure','analyze','resume_analysis','confirm_deleted','gc','register_snapshot','scope','start','next','complete_work','terms','retry','finish'):
        from .coordination import gate
        # Collection changes source/cache/queue state only. Freeze its complete
        # multi-transaction outbox, without creating a local execution artifact
        # that would invalidate an unrelated preexisting Git inventory. Normal
        # canonical application retains its existing execution ownership checks.
        with gate(store.project.root,exclusive=True):return _dispatch(store,action,request)
    return _dispatch(store,action,request)


def _dispatch(store,action,request):
    if action in ('scope','start','status','next','complete_work','terms','retry','finish'):
        from .confluence_command import dispatch as command
        return command(store,action,request)
    if action in ('observe','failure','analyze','resume_analysis','confirm_deleted','gc'):
        from .confluence_sync import dispatch as sync
        return sync(store,action,request)
    if action=='register_snapshot':return register(store,request)
    with store.connection() as db:
        if action=='inventory':
            rows=[loads(p) for p, in db.execute('SELECT payload FROM confluence_pages ORDER BY identity')] if validate_control(db) else []
            from .diagnostic_pages import page as paged
            return paged(rows,{'ok':True,'source_kind':'confluence','live_verification':False},request.get('cursor',0),request.get('limit',20),request.get('max_bytes',16000))
        if action=='related':
            from .confluence_sync import related
            return related(db,request)
        if action=='snapshot':
            data=snapshot(db,request['snapshot']);start=request.get('cursor',0);require(type(start) is int and 0<=start<=len(data['content']),'invalid-confluence-offset')
            end=min(len(data['content']),start+2000)
            from .confluence_coverage import chunk,binding,CHARS
            source=dict(kind='confluence',identity=data['identity'],revision=data['version'],snapshot=request['snapshot'])
            return {'ok':True,'snapshot':request['snapshot'],'text':data['content'][start:end],'next_cursor':end if end<len(data['content']) else None,'content_hash':data['content_hash'],'coverage_binding':binding(source,data),'analysis_chunk':chunk(data['content'],start) if start<len(data['content']) and start%CHARS==0 else None,'source_is_untrusted_data':True,'live_verification':False}
    raise KnowledgeError('unsupported-confluence-action')
