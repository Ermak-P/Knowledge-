"""Native Confluence snapshots. No HTTP client, credentials or Git inventory.

MCP results are submitted source data. Hash verification attests local snapshot
integrity, never independent live access to Confluence or implementation truth.
"""
from copy import deepcopy
from datetime import datetime
import hashlib
import re
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
from .util import require,KnowledgeError,canonical_json,digest,loads
from .sqlite_snapshot import view

SCHEMA='1'
TABLES={'confluence_pages':('identity','instance','page_id','latest_version','payload'),
        'confluence_snapshots':('snapshot','source_id','version','content_hash','payload','checksum')}
TABLE_SQL={
 'confluence_pages':'CREATE TABLE confluence_pages(identity TEXT PRIMARY KEY,instance TEXT NOT NULL,page_id TEXT NOT NULL,latest_version INTEGER NOT NULL,payload TEXT NOT NULL,UNIQUE(instance,page_id))',
 'confluence_snapshots':'CREATE TABLE confluence_snapshots(snapshot TEXT PRIMARY KEY,source_id TEXT NOT NULL,version INTEGER NOT NULL,content_hash TEXT NOT NULL,payload TEXT NOT NULL,checksum TEXT NOT NULL,UNIQUE(source_id,version))'}
INDEX_SQL={'confluence_snapshot_source':'CREATE INDEX confluence_snapshot_source ON confluence_snapshots(source_id,version)'}
ROLES=('requirement','architecture','rationale','integration-contract','configuration','deployment','testing','limitation','historical','proposed','implementation')


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
    require(isinstance(source,dict) and set(source)=={'kind','identity','revision','snapshot'} and source['kind']=='confluence',
            'invalid-confluence-binding',{'expected_kind':'confluence','required':['identity','revision','snapshot']})
    require(all(isinstance(source[k],str) and re.fullmatch('[a-f0-9]{64}',source[k]) for k in ('identity','snapshot')),
            'invalid-confluence-binding-identity',{'expected_kind':'confluence'})
    require(type(source['revision']) is int and source['revision']>0,'invalid-confluence-page-version',{'identity':source['identity']})
    return source


def _validate_control(db):
    marker=db.execute("SELECT value FROM metadata WHERE key='confluence-schema'").fetchone()
    found={n for n, in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'confluence_%'")}
    if marker is None:
        require(not found,'incomplete-confluence-extension');return False
    require(marker==(SCHEMA,) and set(TABLES)<=found,'unsupported-confluence-extension')
    for table,columns in TABLES.items():
        require(tuple(r[1] for r in db.execute('PRAGMA table_info('+table+')'))==columns,'corrupt-confluence-schema',{'table':table})
    return True


def validate_control(db):return view(db,'confluence-schema',lambda:_validate_control(db))


def enable(db):
    if validate_control(db):return
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


def snapshot(db,identifier):
    def read():
        row=db.execute('SELECT source_id,version,content_hash,payload,checksum FROM confluence_snapshots WHERE snapshot=?',(identifier,)).fetchone()
        require(row is not None,'unknown-confluence-snapshot',{'snapshot':identifier,'next_action':'Submit the exact MCP page revision before its candidates.'})
        data=loads(row[3]);require(digest(data)==row[4],'corrupt-confluence-snapshot-checksum',{'snapshot':identifier});text,hashed=normalize(data['content'])
        require(text==data['content'] and hashed==data['content_hash']==row[2] and data['identity']==row[0] and data['version']==row[1]
                and identifier==digest(['confluence-revision-v1',row[0],row[1],data['representation'],hashed]),'corrupt-confluence-snapshot',{'snapshot':identifier})
        require(identity(data['instance'],data['page_id'])==data['identity'] and url(data['url'])==data['url'],'corrupt-confluence-snapshot-metadata',{'snapshot':identifier})
        timestamp(data['retrieved_at']);return data
    return view(db,('confluence-snapshot',identifier),read)


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
        else:db.execute('INSERT INTO confluence_snapshots VALUES (?,?,?,?,?,?)',(identifier,source_id,version,hashed,canonical_json(data),digest(data)))
        row=db.execute('SELECT payload FROM confluence_pages WHERE identity=?',(source_id,)).fetchone()
        current=loads(row[0]) if row else dict(identity=source_id,instance=instance,page_id=pid,latest_version=version,last_analyzed_version=None,last_applied_version=None)
        if version>=current['latest_version']:
            current.update(latest_version=version,latest_snapshot=identifier,title=data['title'],url=data['url'],content_hash=hashed,last_checked=data['retrieved_at'],processing_status='SNAPSHOT_REGISTERED')
            for key in ('space_key','modified_at'):
                if key in data:current[key]=data[key]
        db.execute('INSERT OR REPLACE INTO confluence_pages VALUES (?,?,?,?,?)',(source_id,instance,pid,current['latest_version'],canonical_json(current)))
    return {'ok':True,'result':'existing' if old else 'registered','source':dict(kind='confluence',identity=source_id,revision=version,snapshot=identifier),
            'content_hash':hashed,'integrity':data['integrity'],'canonical_unchanged':True}


def verify_binding(db,source,fresh=True):
    binding_shape(source);require(validate_control(db),'confluence-not-registered',{'identity':source['identity'],'expected_kind':'confluence'})
    data=snapshot(db,source['snapshot']);current=page(db,source['identity'])
    require(data['identity']==source['identity'] and data['version']==source['revision'],'confluence-snapshot-binding-mismatch',{'identity':source['identity'],'revision':source['revision'],'snapshot':source['snapshot']})
    if fresh:
        require(current.get('processing_status')!='DELETED','confluence-page-confirmed-deleted',{'identity':source['identity'],'revision':source['revision']})
        require(current['latest_version']==source['revision'],'stale-confluence-revision',{'identity':source['identity'],'candidate_revision':source['revision'],'observed_revision':current['latest_version'],'next_action':'Analyze the observed page revision and prepare a new exact approval; Git rescan is unnecessary.'})
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
        evidence=op['payload'] if op['kind']=='evidence' else None
        if evidence and is_binding(source):require(is_binding(evidence.get('source')),'confluence-candidate-needs-native-evidence',{'evidence':evidence['id']})
        if evidence and is_binding(evidence.get('source')):
            verify_evidence(db,evidence,fresh)
            if is_binding(source):require(all(evidence['source'][k]==source[k] for k in source),'confluence-candidate-evidence-binding-mismatch',{'evidence':evidence['id']})


def pending_partition(db,pending):
    remaining=dict(pending);skipped=[]
    for cid,item in pending.items():
        if not is_binding(item.get('source')):continue
        try:verify_binding(db,item['source'])
        except KnowledgeError as error:
            if error.code not in ('stale-confluence-revision','confluence-page-confirmed-deleted'):raise
            del remaining[cid];skipped.append(dict(candidate=cid,reason=error.code,details=error.details))
    blocked=[dict(code=entry['reason'],details=entry['details']) for entry in skipped] if skipped and not remaining else []
    return remaining,skipped,blocked


def evidence_freshness(store,evidence,db=None):
    if db is None:
        with store.connection() as connection:return evidence_freshness(store,evidence,connection)
    try:verify_evidence(db,evidence);return 'current-registered-confluence-snapshot'
    except KnowledgeError as error:
        if error.code.startswith(('corrupt-','invalid-')):raise
        return error.code


def integrity(db):
    if not validate_control(db):return None
    for identifier, in db.execute('SELECT identity FROM confluence_pages'):page(db,identifier)
    for identifier, in db.execute('SELECT snapshot FROM confluence_snapshots'):snapshot(db,identifier)
    return {'pages':db.execute('SELECT COUNT(*) FROM confluence_pages').fetchone()[0],'snapshots':db.execute('SELECT COUNT(*) FROM confluence_snapshots').fetchone()[0],'live_verification':False}


def export(db):
    if not validate_control(db):return {}
    integrity(db)
    return {'confluence':{'version':1,'pages':[loads(p) for p, in db.execute('SELECT payload FROM confluence_pages ORDER BY identity')],
                         'snapshots':[{'snapshot':s,**loads(p)} for s,p in db.execute('SELECT snapshot,payload FROM confluence_snapshots ORDER BY snapshot')]}}


def dispatch(store,action,request):
    if action=='register_snapshot':return register(store,request)
    with store.connection() as db:
        if action=='inventory':
            rows=[loads(p) for p, in db.execute('SELECT payload FROM confluence_pages ORDER BY identity')] if validate_control(db) else []
            from .diagnostic_pages import page as paged
            return paged(rows,{'ok':True,'source_kind':'confluence','live_verification':False},request.get('cursor',0),request.get('limit',20),request.get('max_bytes',16000))
        if action=='snapshot':
            data=snapshot(db,request['snapshot']);start=request.get('cursor',0);require(type(start) is int and 0<=start<=len(data['content']),'invalid-confluence-offset')
            end=min(len(data['content']),start+2000)
            return {'ok':True,'snapshot':request['snapshot'],'text':data['content'][start:end],'next_cursor':end if end<len(data['content']) else None,'content_hash':data['content_hash'],'source_is_untrusted_data':True,'live_verification':False}
    raise KnowledgeError('unsupported-confluence-action')
