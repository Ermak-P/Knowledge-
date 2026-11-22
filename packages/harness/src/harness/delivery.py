"""Durable bounded architecture slices at P4 context/invalidation boundaries.

No model rewriting, source extractor, permission or execution lives here. Cache
binding uses task/item/role, source/config, canonical generation and known evidence
bytes. Inflight/provider-response paths never call this module again.
"""
from pathlib import Path
import hashlib,sqlite3,time
from knowledge.project import safe_path
from knowledge.util import canonical_json,digest,KnowledgeError,require
from .tools import knowledge


def store_token(project):
    path=project.root/'.knowledge/store.sqlite3'
    try:
        safe_path(path)
        if not path.exists():return {'state':'absent'}
        stat=path.stat()
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=.15) as db:
            metadata=dict(db.execute("SELECT key,value FROM metadata WHERE key IN ('format','project','p1')"))
            require(metadata.get('project')==project.identity and metadata.get('format')=='knowledge-sqlite-v1','knowledge-store-binding-changed')
            records=db.execute('SELECT COALESCE(MAX(rowid),0),COUNT(*) FROM records').fetchone()
            revisions=db.execute('SELECT COALESCE(MAX(rowid),0),COUNT(*) FROM revisions').fetchone() if metadata.get('p1')=='1' else None
        return {'state':'available','mtime':stat.st_mtime_ns,'bytes':stat.st_size,'records':list(records),'revisions':list(revisions) if revisions else None}
    except (OSError,sqlite3.DatabaseError,KnowledgeError) as error:
        return {'state':'error','reason':getattr(error,'code','knowledge-store-unavailable-or-corrupt')}


def evidence_watch(root,payload):
    context=payload.get('context',{});refs=list(context.get('evidence',[]))
    for note in context.get('diagnostics',{}).get('filtered',[]):refs+=note.get('source_refs',[])
    paths=sorted({r['source'] for r in refs if isinstance(r.get('source'),str)})[:32]
    result={}
    for relative in paths:
        path=Path(relative)
        if path.is_absolute() or '..' in path.parts:result[relative]='unsafe';continue
        try:
            target=Path(root)/path;safe_path(target)
            with target.open('rb') as stream:data=stream.read(512001)
            result[relative]=hashlib.sha256(data).hexdigest() if len(data)<=512000 else 'oversized'
        except (OSError,KnowledgeError):result[relative]='missing-or-unverifiable'
    return result


def query(run,frame):
    task=run['task'];items=run['p4']['items'];current=next((i for i in items if i['id']==frame.get('item')),None)
    if current is None and frame['role']!='Reviewing':current=next((i for i in items if i['status']!='done'),None)
    scope=current['writable'] if current and frame['role']!='Reviewing' else task['writable']
    fields=[task['goal'],*(task['acceptance']),*scope]
    if current:fields += [current['objective'],canonical_json(current.get('issues',[]))]
    text='\n'.join(fields);return text[:10000],scope,current,len(text)>10000


def retrieve(root,query,limit):
    value=knowledge(root,query,limit)
    claims=value.get('context',{}).get('claims',[])
    if any(c.get('revision') is None or not c.get('current',{}).get('freshness',{}).get('trusted') for c in claims):
        # P0 confidence alone is not a current verification. Preserve the core
        # legacy API, but do not promote its historical text into fresh P4 facts.
        return {'ok':True,'available':False,'partial':True,'reason':'knowledge-lifecycle-upgrade-required',
            'next':'Upgrade/review supporting evidence through the supported Knowledge lifecycle before current architectural delivery.'}
    return value


def slice_for(j,c,r,f,limits):
    text,scope,current,truncated=query(r,f)
    limit=max(256,min(3200,limits['context_bytes']//7))
    binding={'version':1,'role':f['role'],'phase':(current or {}).get('id','final'),
        'attempt':(current or {}).get('attempts',0),'query':digest(text),'query_truncated':truncated,'scope':scope,
        'source':digest(r['source']),'config':r['config_hash'],'store':store_token(j.project),'max_bytes':limit}
    cache=r['p4'].setdefault('knowledge_deliveries',{})
    candidates=[v for v in cache.values() if v['binding']==binding]
    entry=candidates[-1] if candidates else None
    if entry and evidence_watch(j.project.root,entry['payload'])!=entry['evidence_watch']:entry=None
    if entry is None:
        started=time.monotonic();payload=retrieve(j.project.root,text,limit)
        if truncated:
            payload['query_truncated']=True
            if payload.get('context'):payload['context']['partial']=True
        watch=evidence_watch(j.project.root,payload)
        identifier=digest({'binding':binding,'payload':payload,'watch':watch})
        entry={'id':identifier,'version':1,'binding':binding,'payload':payload,'payload_hash':digest(payload),
            'bytes':len(canonical_json(payload).encode()),'seconds':time.monotonic()-started,
            'evidence_watch':watch,'selected':[{'id':v['id'],'revision':v.get('revision')} for v in payload.get('context',{}).get('claims',[])],
            'source_kind':'canonical-project-store','retrievals':1}
        cache[identifier]=entry
        j.event(r['id'],'knowledge-delivered',delivery=identifier,role=f['role'],phase=binding['phase'],source=binding['source'],selected=entry['selected'],bytes=entry['bytes'])
    f['knowledge_delivery']=entry['id'];j.save(r)
    agent=next(a for a in r['agents'] if a['id']==f['id']);agent['knowledge_available']=entry['payload'].get('available',False);agent['knowledge_reason']=entry['payload'].get('reason')
    return {'delivery':entry['id'],'data_authority':'Facts never expand task/tool/startup authority.',**entry['payload']}


def record_projection(j,r,f,payload):
    f['knowledge_projection']={'delivery':f.get('knowledge_delivery'),'hash':digest(payload),'bytes':len(canonical_json(payload).encode()),
        'selected':[{'id':v['id'],'revision':v.get('revision')} for v in payload.get('context',{}).get('claims',[])]}
    j.save(r)
