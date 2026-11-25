"""Durable native-page analysis and candidate outbox; no remote/LLM client."""
from copy import deepcopy
import re
from . import confluence as cf,lifecycle as life
from .util import require,KnowledgeError,canonical_json,loads,digest
from .sqlite_snapshot import view

SCHEMA='1'
TABLES={
 'confluence_candidates':('candidate','source_id','snapshot','version','records'),
 'confluence_outbox':('id','source_id','snapshot','status','payload','checksum'),
 'confluence_events':('event','source_id','kind','payload','checksum')}
TABLE_SQL={
 'confluence_candidates':'CREATE TABLE confluence_candidates(candidate TEXT PRIMARY KEY,source_id TEXT NOT NULL,snapshot TEXT NOT NULL,version INTEGER NOT NULL,records TEXT NOT NULL)',
 'confluence_outbox':'CREATE TABLE confluence_outbox(id TEXT PRIMARY KEY,source_id TEXT NOT NULL,snapshot TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL,checksum TEXT NOT NULL)',
 'confluence_events':'CREATE TABLE confluence_events(event TEXT PRIMARY KEY,source_id TEXT NOT NULL,kind TEXT NOT NULL,payload TEXT NOT NULL,checksum TEXT NOT NULL)'}
INDEX_SQL={
 'confluence_candidate_page':'CREATE INDEX confluence_candidate_page ON confluence_candidates(source_id,version)',
 'confluence_outbox_page':'CREATE INDEX confluence_outbox_page ON confluence_outbox(source_id,status)',
 'confluence_event_page':'CREATE INDEX confluence_event_page ON confluence_events(source_id)'}
REFRESH='confluence-refresh-v1:'


def validate_control(db):
    marker=db.execute("SELECT value FROM metadata WHERE key='confluence-sync-schema'").fetchone()
    found={n for n, in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if marker is None:
        require(not set(TABLES)&found,'incomplete-confluence-sync-extension');return False
    require(marker==(SCHEMA,) and set(TABLES)<=found,'unsupported-confluence-sync-extension')
    for table,columns in TABLES.items():require(tuple(r[1] for r in db.execute('PRAGMA table_info('+table+')'))==columns,'corrupt-confluence-sync-schema',{'table':table})
    return True


def integrity(db):
    if not validate_control(db):return
    for identifier, in db.execute('SELECT event FROM confluence_events'):event(db,identifier)
    for identifier,sid,snapshot,status in db.execute('SELECT id,source_id,snapshot,status FROM confluence_outbox'):
        data=_outbox(db,identifier)
        require(data['source']['identity']==sid and data['source']['snapshot']==snapshot and status in ('COLLECTING','PREPARED','DONE'),'corrupt-confluence-analysis-checkpoint')
        cf.verify_binding(db,data['source'],False)


def related(db,request):
    from .diagnostic_pages import page
    sid=request['identity'];cf.page(db,sid);rows=[]
    if validate_control(db):
        for cid,raw in db.execute('SELECT candidate,records FROM confluence_candidates WHERE source_id=? ORDER BY candidate',(sid,)):
            rows.append(dict(kind='candidate',id=cid))
            for kind in ('claims','evidence'):
                rows.extend(dict(kind=kind,id=i,candidate=cid) for i in loads(raw)[kind])
    # Resolved IDs can differ from original candidates after source-aware dedup.
    for identifier,payload in db.execute("SELECT id,payload FROM records WHERE kind='evidence'"):
        evidence=loads(payload)
        if cf.is_binding(evidence['source']) and evidence['source']['identity']==sid:
            rows.append(dict(kind='canonical-evidence',id=identifier,status=evidence['status']))
            rows.extend(dict(kind='canonical-claim',id=i,evidence=identifier) for i in evidence['substantiates'])
    return page(rows,dict(ok=True,identity=sid),request.get('cursor',0),request.get('limit',20),request.get('max_bytes',16000))


def enable(db):
    cf.enable(db)
    if validate_control(db):return
    for sql in (*TABLE_SQL.values(),*INDEX_SQL.values()):db.execute(sql)
    db.execute("INSERT INTO metadata VALUES ('confluence-sync-schema',?)",(SCHEMA,))
    for cid,payload in list(db.execute('SELECT id,payload FROM queue')):
        value=loads(payload)
        if cf.is_binding(value.get('source')):note_candidate(db,cid,value,ensure=False)


def save_page(db,data):
    db.execute('INSERT OR REPLACE INTO confluence_pages VALUES (?,?,?,?,?)',(data['identity'],data['instance'],data['page_id'],data['latest_version'],canonical_json(data)))


def relation(value):
    ops=value.get('operations',[])
    return dict(claims=sorted({o['id'] for o in ops if o['kind']=='claims'}),evidence=sorted({o['id'] for o in ops if o['kind']=='evidence'}),
                snapshots=sorted({value['source']['snapshot']}|{o['payload']['source']['snapshot'] for o in ops if o['kind']=='evidence' and o['payload'] and cf.is_binding(o['payload']['source'])}))


def note_candidate(db,cid,value,ensure=True):
    if not cf.is_binding(value.get('source')):return
    if ensure:enable(db)
    s=value['source'];db.execute('INSERT OR REPLACE INTO confluence_candidates VALUES (?,?,?,?,?)',(cid,s['identity'],s['snapshot'],s['revision'],canonical_json(relation(value))))


def validate_relations(db,queued):
    if not db.execute("SELECT 1 FROM metadata WHERE key='confluence-sync-schema'").fetchone():return
    expected={cid:item for cid,status,raw,item in queued if cf.is_binding(item.get('source'))}
    rows=list(db.execute('SELECT candidate,source_id,snapshot,version,records FROM confluence_candidates'))
    require({r[0] for r in rows}==set(expected),'corrupt-confluence-candidate-index')
    for cid,sid,snap,version,record in rows:
        value=expected[cid];source=value['source']
        require((sid,snap,version)==(source['identity'],source['snapshot'],source['revision']) and loads(record)==relation(value),'corrupt-confluence-candidate-index',{'candidate':cid})


def incomplete_candidates(db,pending):
    if not db.execute("SELECT 1 FROM metadata WHERE key='confluence-sync-schema'").fetchone():return {}
    sources={v['source']['identity'] for v in pending.values() if cf.is_binding(v.get('source'))};result={}
    for sid in sources:
        for identifier, in db.execute("SELECT id FROM confluence_outbox WHERE source_id=? AND status='PREPARED'",(sid,)):
            data=_outbox(db,identifier)
            for batch in data.get('batches',[]):result[digest(batch)]=identifier
    return result


def observe(store,value):
    require(isinstance(value,dict) and {'instance','page_id','version','title','url'}<=set(value)<= {'instance','page_id','version','title','url','space_key','modified_at','origin'},'invalid-confluence-metadata')
    sid=cf.identity(value['instance'],value['page_id']);version=value['version'];require(type(version) is int and version>0,'invalid-confluence-page-version')
    require(isinstance(value['title'],str) and len(value['title'])<=4096,'invalid-confluence-title');address=cf.url(value['url'])
    with store.connection(True) as db:
        enable(db);row=db.execute('SELECT 1 FROM confluence_pages WHERE identity=?',(sid,)).fetchone()
        page=deepcopy(cf.page(db,sid)) if row else dict(identity=sid,instance=cf.instance_id(value['instance']),page_id=cf.page_id(value['page_id']),latest_version=0,last_analyzed_version=None,last_applied_version=None)
        if version<page['latest_version']:return {'ok':True,'identity':sid,'action':'IGNORE_OLDER_METADATA','observed_version':page['latest_version']}
        page.update(latest_version=version,title=value['title'],url=address,last_checked=life.now(),availability='available',last_error=None)
        if 'space_key' in value:page['space_key']=value['space_key']
        if 'modified_at' in value:page['modified_at']=cf.timestamp(value['modified_at'])
        if 'origin' in value:page['origin']=value['origin']
        current=cf.snapshot_info(db,page['latest_snapshot']) if page.get('latest_snapshot') else None
        action='SKIP' if page.get('last_analyzed_version')==version and page.get('coverage_certified_hash') and current and page.get('coverage_certified_hash')==current['content_hash'] and page.get('coverage_certified_representation')==current['representation'] else 'RESUME_ANALYSIS' if current and current['version']==version else 'FETCH_CONTENT'
        page['processing_status']='UNCHANGED' if action=='SKIP' else 'ANALYSIS_REQUIRED' if action=='RESUME_ANALYSIS' else 'FETCH_REQUIRED';save_page(db,page)
    return {'ok':True,'identity':sid,'version':version,'action':action,'content_retrieval_required':action=='FETCH_CONTENT','semantic_analysis_required':action!='SKIP','live_verification':'client-reported MCP metadata, not independently attested'}


def failure(store,sid,reason):
    require(reason in ('ACCESS_DENIED','TIMEOUT','UNAVAILABLE','NOT_FOUND_UNCONFIRMED','INCOMPLETE_RESPONSE'),'invalid-confluence-failure-kind')
    with store.connection(True) as db:
        enable(db);page=deepcopy(cf.page(db,sid));page.update(last_checked=life.now(),last_error=reason,availability='verification-failed')
        save_page(db,page)
    return {'ok':True,'identity':sid,'verification_failure':reason,'knowledge_preserved':True,'deletion_inferred':False}


def on_snapshot(store,source):
    with store.connection(True) as db:
        enable(db);data=cf.snapshot(db,source['snapshot']);page=deepcopy(cf.page(db,source['identity']))
        if page.get('availability')=='deleted':return {'action':'CONFIRMED_DELETED_REQUIRES_AVAILABLE_METADATA'}
        if page['latest_version']!=source['revision']:return {'action':'IGNORE_OLDER_SNAPSHOT'}
        if page.get('analysis_source_snapshot')!=source['snapshot']:
            page.update(analysis_offset=0,analysis_source_snapshot=source['snapshot'])
        for identifier, in list(db.execute("SELECT id FROM confluence_outbox WHERE source_id=? AND snapshot<>? AND status='COLLECTING'",(source['identity'],source['snapshot']))):
            obsolete=_outbox(db,identifier);count=sum(map(len,obsolete.pop('chunks').values()))
            obsolete.pop('coverage_chunks',None);obsolete.pop('revalidations',None)
            obsolete.update(status='DONE',candidates=[],counts={'abandoned_partial_findings':count,'reason':'source-revision-advanced'});save_outbox(db,obsolete)
        unfinished=db.execute("SELECT id,status FROM confluence_outbox WHERE source_id=? AND snapshot=? AND status IN ('PREPARED','COLLECTING') ORDER BY id LIMIT 1",(source['identity'],source['snapshot'])).fetchone()
        if unfinished:
            page.update(analysis_checkpoint=unfinished[0],processing_status='ANALYSIS_SUBMITTING' if unfinished[1]=='PREPARED' else 'PARTIAL_ANALYSIS');save_page(db,page)
            return {'action':'RESUME_ANALYSIS','checkpoint':unfinished[0],'semantic_analysis_required':unfinished[1]=='COLLECTING','applied':False}
        reused=page.get('coverage_certified_hash')==data['content_hash'] and page.get('coverage_certified_representation')==data['representation']
        if reused:page.update(last_analyzed_version=source['revision'],last_analyzed_snapshot=source['snapshot'],analysis_reused=True)
        page['processing_status']='UNCHANGED' if reused else 'ANALYSIS_REQUIRED';page['analysis_checkpoint']=None;save_page(db,page)
    refreshed=refresh_unchanged_pending(store,source) if reused else []
    return {'action':'SKIP_ANALYSIS' if reused else 'ANALYZE','analysis_reused':reused,'refreshed_candidates':refreshed,'applied':False}


def role_of(claim,evidence):
    method=claim['provenance']['method']
    if method.startswith('confluence-documentation-v1:'):return method.split(':',1)[1]
    if claim['type']=='business_rule':return 'requirement'
    if claim['type']=='architecture':return 'architecture'
    if any(not cf.is_binding(e.get('source')) for e in evidence):return 'implementation'
    return 'documentation'


def evidence_id(claim,source,quote,role):return 'cf.evidence.'+digest([claim,source['identity'],source['snapshot'],quote,role])[:48]


def source_now(page):return dict(kind='confluence',identity=page['identity'],revision=page['latest_version'],snapshot=page['latest_snapshot'])


def _pending_records(db):
    from .discovery import candidate_refreshes
    refreshed=candidate_refreshes(db);rows=[]
    for cid,payload,status in db.execute('SELECT id,payload,status FROM queue'):
        if status!='pending' or cid in refreshed:continue
        value=loads(payload)
        if cf.is_binding(value.get('source')):
            try:cf.verify_binding(db,value['source'])
            except KnowledgeError as error:
                if error.code in ('stale-confluence-revision','confluence-page-confirmed-deleted'):continue
                raise
        rows.append(value)
    return rows


def build_proposals(store,db,source,findings,complete,reviews=None,coverage_checkpoint=None):
    data=cf.verify_binding(db,source);records=store._records(db);states=life.latest(db)
    canonical={c['id']:c for c in records['claims']};proofs={e['id']:e for e in records['evidence']};known=dict(canonical)
    normalized=[];review_token=None
    for r in reviews or []:
        require(isinstance(r,dict) and set(r)=={'evidence','expected','verdict','quote','reason'},'invalid-confluence-revalidation')
        old=proofs.get(r['evidence']);state=states.get(r['evidence'])
        require(old is not None and state and state['lifecycle']=='active' and state['revision']==r['expected'] and type(r['expected']) is int,'stale-confluence-evidence-revalidation')
        require(cf.is_binding(old['source']) and old['source']['identity']==source['identity'] and old['status']=='active','confluence-revalidation-wrong-source')
        require(r['verdict'] in ('retained','changed','removed','superseded') and isinstance(r['quote'],str) and 0<len(r['quote'])<=8192 and r['quote'] in data['content'] and isinstance(r['reason'],str) and 0<len(r['reason'])<=2000,'confluence-revalidation-needs-targeted-current-evidence')
        normalized.append({**r,'old_record_hash':digest(old)})
        if r['verdict']=='retained':
            for cid in old['substantiates']:
                c=canonical[cid];findings=list(findings)+[dict(statement=c['statement'],type=c['type'],role=role_of(c,[proofs[i] for i in c['evidence']]),quote=r['quote'])]
    if normalized:
        require(len({r['evidence'] for r in normalized})==len(normalized),'duplicate-confluence-evidence-revalidation')
        group=dict(identity=source['identity'],kind='evidence-revalidation',source=source,coverage_checkpoint=coverage_checkpoint,reviews=sorted(normalized,key=lambda r:r['evidence']))
        review_token=digest(group);db.execute('INSERT OR IGNORE INTO confluence_events VALUES (?,?,?,?,?)',(review_token,source['identity'],group['kind'],canonical_json(group),review_token))
    for value in _pending_records(db):
        for op in value.get('operations',[]):
            if op['kind']=='claims' and op['payload'] and op['action']=='add':known.setdefault(op['id'],op['payload'])
            if op['kind']=='evidence' and op['payload']:proofs.setdefault(op['id'],op['payload'])
    by_statement={}
    for claim in known.values():
        if claim['id'] not in states or states[claim['id']]['lifecycle']=='active':by_statement.setdefault(claim['statement'],[]).append(claim)
    touched={};eops={};new_count=0;enriched=0;duplicates=0
    for finding in findings:
        require(isinstance(finding,dict) and {'statement','quote','role'}<=set(finding)<= {'statement','quote','role','type','conflicts_with','question'},'invalid-confluence-finding')
        statement=finding['statement'];quote=finding['quote'];role=finding['role'];kind=finding.get('type','business_rule' if role=='requirement' else 'architecture' if role in ('architecture','rationale') else 'technical_fact')
        require(isinstance(statement,str) and 0<len(statement)<=4096 and isinstance(quote,str) and 0<len(quote)<=8192 and quote in data['content'],'confluence-finding-not-source-supported')
        require(role in cf.ROLES and kind in ('business_rule','architecture','technical_fact'),'invalid-confluence-finding-role')
        candidates=by_statement.get(statement,[]);require(len(candidates)<=1,'confluence-ambiguous-existing-claim')
        old=candidates[0] if candidates else None
        if old:
            prior_role=role_of(old,[proofs[i] for i in old['evidence'] if i in proofs])
            require(old['type']==kind and prior_role==role,'confluence-claim-scope-conflict',{'claim':old['id'],'existing_role':prior_role,'proposed_role':role,'next_action':'Clarify meaning/scope; do not merge requirements, historical statements and implemented behavior.'})
            claim=touched.setdefault(old['id'],deepcopy(old))
        else:
            cid='cf.claim.'+digest([store.project.identity,statement,kind,role])[:40]
            claim=dict(id=cid,statement=statement,type=kind,status='INFERRED' if role=='implementation' else 'CONFIRMED',evidence=[],
                       provenance={'actor':'knowledge-confluence','method':'confluence-documentation-v1:'+role},last_verified=None if role=='implementation' else data['retrieved_at'][:10],depends_on=[],conflicts_with=[])
            touched[cid]=claim;by_statement[statement]=[claim];new_count+=1
        eid=evidence_id(claim['id'],source,quote,role)
        evidence=dict(id=eid,type='supporting' if role=='implementation' else 'direct-authoritative',status='active',source={**source,'reference':data['url'],'role':role},
                      location='normalized-text#offset='+str(data['content'].index(quote)),content_hash=data['content_hash'],description=quote,substantiates=[claim['id']],captured_at=data['retrieved_at'],
                      provenance={'actor':'knowledge-confluence','method':'confluence-documentation-v1:'+role})
        if eid not in claim['evidence']:claim['evidence'].append(eid);enriched+=int(old is not None)
        else:duplicates+=1
        prior=proofs.get(eid)
        if prior!=evidence:eops[eid]=life.op('update' if eid in {e['id'] for e in records['evidence']} else 'add','evidence',eid,states[eid]['revision'] if eid in states else 0,evidence)
        conflicts=finding.get('conflicts_with',[])
        require(isinstance(conflicts,list) and all(isinstance(i,str) for i in conflicts),'invalid-confluence-conflict-targets')
        if conflicts:claim.update(status='NEEDS_HUMAN_CONFIRMATION',last_verified=None)
        for target in conflicts:
            require(target in canonical and target!=claim['id'] and states[target]['lifecycle']=='active','unknown-confluence-conflict-target')
            other=touched.setdefault(target,deepcopy(canonical[target]))
            require(role_of(other,[proofs[i] for i in other['evidence'] if i in proofs])==role,'confluence-conflict-scope-needs-clarification',{'claim':target,'proposed_role':role})
            if target not in claim['conflicts_with']:claim['conflicts_with'].append(target)
            if claim['id'] not in other['conflicts_with']:other['conflicts_with'].append(claim['id'])
    reviewed={r['evidence']:r for r in (reviews or [])}
    if complete:
        for claim in canonical.values():
            affected=[proofs[i] for i in claim['evidence'] if cf.is_binding(proofs[i]['source']) and proofs[i]['source']['identity']==source['identity'] and i in reviewed and reviewed[i]['verdict']!='retained' and proofs[i]['status']=='active']
            if not affected:continue
            updated=touched.setdefault(claim['id'],deepcopy(claim));removed={e['id'] for e in affected}
            updated['evidence']=[i for i in updated['evidence'] if i not in removed]
            for old in affected:eops[old['id']]=life.op('update','evidence',old['id'],states[old['id']]['revision'],{**old,'status':'retracted' if reviewed[old['id']]['verdict']=='removed' else 'superseded'})
            if not updated['evidence']:updated.update(status='NEEDS_HUMAN_CONFIRMATION',last_verified=None)
            if not updated['evidence']:updated['evidence']=list(claim['evidence'])
    cops=[]
    for cid,claim in touched.items():
        if canonical.get(cid)==claim or (cid not in canonical and known.get(cid)==claim):continue
        cops.append(life.op('update' if cid in canonical else 'add','claims',cid,states[cid]['revision'] if cid in states else 0,claim))
    ops=list(eops.values())+cops
    # Existing v2 batches allow 10k operations. Split the projection, never facts;
    # the ordinary plan validates/applies the complete pending graph atomically.
    batches=[life.batch(ops[i:i+1000],'Reviewed Confluence '+source['identity']+' revision '+str(source['revision']),{**source,'revalidation':review_token} if review_token else source) for i in range(0,len(ops),1000)]
    questions=[f.get('question') or 'Clarify '+f['role']+' contradiction against '+', '.join(f['conflicts_with']) for f in findings if f.get('conflicts_with')]
    return batches,dict(new_claim_candidates=new_count,existing_claims_enriched=enriched,duplicates_prevented=duplicates,operations=len(ops),conflicts_detected=sum(len(f.get('conflicts_with',[])) for f in findings),clarification_questions=questions)


def _outbox(db,identifier):
    row=db.execute('SELECT payload,checksum,status FROM confluence_outbox WHERE id=?',(identifier,)).fetchone()
    require(row is not None,'unknown-confluence-analysis-checkpoint')
    data=loads(row[0]);require(digest(data)==row[1] and data['status']==row[2],'corrupt-confluence-analysis-checkpoint')
    return data


def save_outbox(db,data):
    db.execute('INSERT OR REPLACE INTO confluence_outbox VALUES (?,?,?,?,?,?)',(data['id'],data['source']['identity'],data['source']['snapshot'],data['status'],canonical_json(data),digest(data)))


def analyze(store,source,findings,complete=True,analyzed_until=None,coverage=None,revalidations=None):
    from . import confluence_coverage as cv
    require(isinstance(findings,list) and len(findings)<=1000 and type(complete) is bool,'invalid-confluence-analysis-batch')
    reviews=revalidations or [];require(isinstance(reviews,list) and len(reviews)<=1000,'invalid-confluence-revalidations')
    identifier=digest(['confluence-analysis-v2',source,findings,complete,coverage,reviews])
    collector=digest(['confluence-analysis-chunks-v1',source])
    with store.connection(True) as db:
        enable(db);snapshot=cf.verify_binding(db,source)
        # A scalar cursor is only a compatibility hint. It cannot establish any
        # analyzed range, and gaps are never filled from its maximum value.
        if analyzed_until is not None:require(type(analyzed_until) is int and 0<=analyzed_until<=len(snapshot['content']),'invalid-confluence-analysis-offset')
        previous=db.execute("SELECT 1 FROM confluence_outbox WHERE id=? AND status='COLLECTING'",(collector,)).fetchone()
        data=_outbox(db,collector) if previous else dict(id=collector,source=source,status='COLLECTING',chunks={})
        entries=cv.merge(source,snapshot,coverage,data.get('coverage_chunks'))
        state=cv.progress(snapshot,entries)
        if db.execute("SELECT 1 FROM confluence_outbox WHERE id=? AND status IN ('PREPARED','DONE')",(identifier,)).fetchone():pass
        elif not complete:
            # Buffer source-supported findings. Canonical graph/scope validation
            # is deferred to the complete projection, not repeated per chunk.
            for f in findings:
                require(isinstance(f,dict) and isinstance(f.get('quote'),str) and f['quote'] and f['quote'] in snapshot['content'] and isinstance(f.get('statement'),str) and 0<len(f['statement'])<=4096 and f.get('role') in cf.ROLES,'confluence-finding-not-source-supported')
            data['chunks'][identifier]=findings
            require(sum(map(len,data['chunks'].values()))<=10000,'confluence-analysis-page-budget-exhausted')
            prior_reviews=data.get('revalidations',{})
            for r in reviews:
                require(isinstance(r,dict) and isinstance(r.get('evidence'),str),'invalid-confluence-revalidation')
                require(r['evidence'] not in prior_reviews or prior_reviews[r['evidence']]==r,'conflicting-confluence-revalidation');prior_reviews[r['evidence']]=r
            data.update(coverage_chunks=entries,revalidations=prior_reviews);save_outbox(db,data)
            page=deepcopy(cf.page(db,source['identity']));page.update(analysis_checkpoint=collector,processing_status='PARTIAL_ANALYSIS',analysis_offset=state['continuous_until']);save_page(db,page)
            return {'ok':True,'checkpoint':collector,'analysis_complete':False,'coverage':state,'persisted_findings':sum(map(len,data['chunks'].values())),'candidates':[],'canonical_unchanged':True}
        else:
            cert=cv.certificate(source,snapshot,entries)
            combined=[f for values in data['chunks'].values() for f in values]+findings
            require(len(combined)<=10000,'confluence-analysis-page-budget-exhausted')
            all_reviews=dict(data.get('revalidations',{}))
            for r in reviews:
                require(isinstance(r,dict) and isinstance(r.get('evidence'),str),'invalid-confluence-revalidation')
                require(r['evidence'] not in all_reviews or all_reviews[r['evidence']]==r,'conflicting-confluence-revalidation');all_reviews[r['evidence']]=r
            batches,counts=build_proposals(store,db,source,combined,True,list(all_reviews.values()),identifier)
            prepared=dict(id=identifier,source=source,status='PREPARED',complete=True,coverage_certificate=cert,batches=batches,candidates=[],counts=counts)
            save_outbox(db,prepared)
            if previous:
                data.update(status='DONE',candidates=[],counts={});data.pop('chunks',None);data.pop('coverage_chunks',None);data.pop('revalidations',None);save_outbox(db,data)
            page=deepcopy(cf.page(db,source['identity']));page.update(analysis_checkpoint=identifier,analysis_offset=state['continuous_until'],processing_status='ANALYSIS_SUBMITTING');save_page(db,page)
    return resume(store,identifier)


def resume(store,identifier):
    with store.connection() as db:data=_outbox(db,identifier)
    if data['status']=='COLLECTING':
        from .confluence_coverage import progress
        with store.connection() as db:coverage=progress(cf.verify_binding(db,data['source']),data.get('coverage_chunks',{}))
        return {'ok':True,'checkpoint':identifier,'analysis_complete':False,'coverage':coverage,'persisted_findings':sum(map(len,data['chunks'].values())),'candidates':[],'next_action':'Read missing deterministic snapshot chunks, then submit complete=true with their coverage descriptors.'}
    if data['status']=='DONE':return {'ok':True,'checkpoint':identifier,'source':data['source'],'replayed':True,**data['counts'],'candidates':data['candidates']}
    if data.get('complete'):
        from .confluence_coverage import verify
        with store.connection() as db:verify(db,data['source'],data.get('coverage_certificate'))
    candidates=[]
    for value in data['batches']:
        result=store.submit(value);candidates.append(result['candidate'])
        from .store import checkpoint
        checkpoint('confluence-candidate-submitted')
    with store.connection(True) as db:
        cf.verify_binding(db,data['source']);page=deepcopy(cf.page(db,data['source']['identity']))
        if data['complete']:
            snap=cf.snapshot_info(db,data['source']['snapshot']);page.update(last_analyzed_version=data['source']['revision'],last_analyzed_snapshot=data['source']['snapshot'],last_analyzed_hash=snap['content_hash'],last_analyzed_representation=snap['representation'],last_analysis_counts=data['counts'],coverage_certified_snapshot=data['source']['snapshot'],coverage_certified_hash=snap['content_hash'],coverage_certified_representation=snap['representation'])
        page.update(processing_status='DELETED' if data.get('deletion') else 'AWAITING_APPLY' if candidates else 'ANALYZED_NO_CLAIMS' if data['complete'] else 'PARTIAL_ANALYSIS',last_analysis_checkpoint=identifier,analysis_checkpoint=None);save_page(db,page)
        data.update(status='DONE',candidates=candidates);data.pop('batches',None);save_outbox(db,data)
    return {'ok':True,'checkpoint':identifier,**data['counts'],'candidates':candidates,'canonical_unchanged':True,'analysis_complete':data['complete']}


def rebind(value,data,source):
    result=deepcopy(value);old_source=result['source'];result['source']=source;aliases={}
    for op in result['operations']:
        if op['kind']!='evidence' or op['action']!='add' or op['payload']['status']!='active':continue
        evidence=op['payload'];s=evidence['source']
        if not cf.is_binding(s) or s['snapshot']!=old_source['snapshot']:continue
        role=s.get('role','documentation');newid=evidence_id(evidence['substantiates'][0],source,evidence['description'],role)
        aliases[op['id']]=newid;op['id']=newid;evidence.update(id=newid,source={**s,**source,'reference':data['url']},content_hash=data['content_hash'],captured_at=data['retrieved_at'])
    for op in result['operations']:
        if op['kind']=='claims' and op['payload']:op['payload']['evidence']=[aliases.get(i,i) for i in op['payload']['evidence']]
    return result


def refresh_links(db):
    from .providers import semantic_bindings
    bindings=semantic_bindings(db)
    links={}
    for key,payload in db.execute('SELECT key,value FROM metadata WHERE key LIKE ?',(REFRESH+'%',)):
        link=loads(payload);old=link['previous'];new=link['replacement']
        require(key==REFRESH+old and link.get('version')==1,'corrupt-confluence-refresh')
        rows=[db.execute('SELECT payload FROM queue WHERE id=?',(cid,)).fetchone() for cid in (old,new)];require(all(rows),'corrupt-confluence-refresh')
        first,second=(loads(r[0]) for r in rows)
        require(cf.is_binding(first.get('source')) and cf.is_binding(second.get('source')) and first['source']['identity']==second['source']['identity'] and first['source']['revision']<second['source']['revision'],'corrupt-confluence-refresh')
        a=cf.snapshot(db,first['source']['snapshot']);b=cf.snapshot(db,second['source']['snapshot'])
        require(a['content_hash']==b['content_hash'] and a['representation']==b['representation'] and rebind(first,b,second['source'])==second,'corrupt-confluence-refresh')
        require(bindings.get(old)==bindings.get(new),'confluence-refresh-semantic-binding-mismatch')
        links[old]=link
    return links


def refresh_unchanged_pending(store,source):
    from .providers import semantic_bindings
    with store.connection() as db:
        bindings=semantic_bindings(db)
        existing=refresh_links(db);new=cf.snapshot(db,source['snapshot']);owned={cid for p, in db.execute("SELECT payload FROM plans WHERE status='COMMITTED'") for cid in loads(p)['included']}
        work=[]
        for cid,payload,status in db.execute('SELECT id,payload,status FROM queue'):
            value=loads(payload)
            if status!='pending' or cid in existing or cid in owned or not cf.is_binding(value.get('source')):continue
            old=value['source']
            if old.get('revalidation'):continue # Explicit review authority is bound to its exact native revision.
            if old['identity']!=source['identity'] or old['revision']>=source['revision']:continue
            prior=cf.snapshot(db,old['snapshot'])
            if prior['content_hash']==new['content_hash'] and prior['representation']==new['representation']:work.append((cid,rebind(value,new,source)))
    updated=[]
    for previous,value in work:
        result=store.submit(value,semantic_binding=bindings.get(previous));replacement=result['candidate']
        with store.connection(True) as db:
            link=dict(version=1,previous=previous,replacement=replacement,at=life.now());db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',(REFRESH+previous,canonical_json(link)))
        updated.append(replacement)
    return updated


def record_applied(db,plan,pid):
    if not db.execute("SELECT 1 FROM metadata WHERE key='confluence-sync-schema'").fetchone():return
    for value in plan['candidates'].values():
        if not cf.is_binding(value.get('source')):continue
        source=value['source'];page=deepcopy(cf.page(db,source['identity']))
        if db.execute("SELECT 1 FROM confluence_outbox WHERE source_id=? AND snapshot=? AND status='PREPARED'",(source['identity'],source['snapshot'])).fetchone():
            page['last_partially_applied_version']=source['revision'];save_page(db,page);continue
        remaining=db.execute("SELECT candidate FROM confluence_candidates c JOIN queue q ON q.id=c.candidate WHERE c.source_id=? AND c.snapshot=? AND q.status='pending'",(source['identity'],source['snapshot'])).fetchall()
        if any(cid not in plan['included'] for cid, in remaining):
            page['last_partially_applied_version']=source['revision'];save_page(db,page);continue
        page.update(last_applied_version=max(page.get('last_applied_version') or 0,source['revision']),last_applied_plan=pid,last_applied_at=life.now())
        if source.get('deletion'):page['last_applied_deletion']=source['deletion']
        if page['latest_version']==source['revision'] and page.get('availability')!='deleted':page['processing_status']='APPLIED'
        save_page(db,page)


def event(db,identifier):
    row=db.execute('SELECT source_id,kind,payload,checksum FROM confluence_events WHERE event=?',(identifier,)).fetchone()
    require(row is not None,'unknown-confluence-deletion-event');data=loads(row[2]);require(digest(data)==row[3]==identifier and data['identity']==row[0] and data['kind']==row[1],'corrupt-confluence-deletion-event')
    return data


def verify_revalidation(db,source,operation):
    require(cf.is_binding(source) and source.get('revalidation'),'confluence-evidence-needs-targeted-revalidation',{'evidence':operation['id'],'next_action':'Submit complete deterministic coverage and an explicit review of this evidence at its expected revision.'})
    group=event(db,source['revalidation']);base={k:source[k] for k in ('kind','identity','revision','snapshot')}
    require(group['kind']=='evidence-revalidation' and group['source']==base,'confluence-revalidation-binding-mismatch')
    checkpoint=_outbox(db,group['coverage_checkpoint'])
    from .confluence_coverage import verify
    verify(db,base,checkpoint.get('coverage_certificate'))
    review=next((r for r in group['reviews'] if r['evidence']==operation['id']),None)
    row=db.execute('SELECT payload FROM revisions WHERE id=? AND revision=?',(operation['id'],operation['expected'])).fetchone()
    require(review and row and review['expected']==operation['expected'] and review['old_record_hash']==digest(loads(row[0])['record']),'stale-confluence-evidence-revalidation')
    require(review['verdict']!='retained' and operation['payload']['status']==('retracted' if review['verdict']=='removed' else 'superseded'),'confluence-revalidation-verdict-mismatch')


def confirm_deleted(store,sid,confirmation):
    require(confirmation=='native-page-status-deleted','confluence-deletion-needs-explicit-native-status',{'next_action':'Permission errors, 404s, missing search hits and incomplete listings are not deletion confirmation.'})
    with store.connection(True) as db:
        enable(db);page=deepcopy(cf.page(db,sid))
        if page.get('availability')=='deleted' and page.get('deletion_event') and db.execute('SELECT 1 FROM confluence_events WHERE event=?',(page['deletion_event'],)).fetchone():identifier=page['deletion_event']
        else:
            generation=page.get('deletion_generation',0)+1;data=dict(identity=sid,kind='deleted',version=page['latest_version'],generation=generation,confirmation=confirmation,reported_at=life.now())
            identifier=digest(data);db.execute('INSERT INTO confluence_events VALUES (?,?,?,?,?)',(identifier,sid,'deleted',canonical_json(data),identifier));page['deletion_generation']=generation
        page.update(availability='deleted',processing_status='DELETED',deletion_event=identifier,last_checked=life.now());save_page(db,page)
        if not page.get('latest_snapshot'):return {'ok':True,'identity':sid,'state':'CONFIRMED_DELETED','candidates':[],'affected_evidence':0,'canonical_unchanged':True}
        snap=cf.snapshot_info(db,page['latest_snapshot']);source=dict(kind='confluence',identity=sid,revision=snap['version'],snapshot=page['latest_snapshot'],deletion=identifier)
        records=store._records(db);states=life.latest(db);evidence={e['id']:e for e in records['evidence']};ops=[]
        affected={e['id'] for e in records['evidence'] if cf.is_binding(e['source']) and e['source']['identity']==sid and e['status']=='active'}
        for eid in sorted(affected):ops.append(life.op('update','evidence',eid,states[eid]['revision'],{**evidence[eid],'status':'retracted'}))
        for claim in records['claims']:
            if not affected.intersection(claim['evidence']):continue
            c=deepcopy(claim);c['evidence']=[i for i in c['evidence'] if i not in affected]
            if not c['evidence']:c.update(status='NEEDS_HUMAN_CONFIRMATION',last_verified=None,evidence=list(claim['evidence']))
            ops.append(life.op('update','claims',c['id'],states[c['id']]['revision'],c))
        batches=[life.batch(ops[i:i+1000],'Explicit native Confluence deletion; preserve independent evidence',source) for i in range(0,len(ops),1000)]
        outbox=digest(['confluence-deletion-outbox-v1',identifier])
        if not db.execute('SELECT 1 FROM confluence_outbox WHERE id=?',(outbox,)).fetchone():
            save_outbox(db,dict(id=outbox,source=source,status='PREPARED',complete=False,deletion=True,batches=batches,candidates=[],counts={'affected_evidence':len(affected)}))
    result=resume(store,outbox)
    return {**result,'identity':sid,'state':'CONFIRMED_DELETED','canonical_unchanged':True}


def dispatch(store,action,request):
    if action=='observe':return observe(store,request)
    if action=='failure':return failure(store,request['identity'],request['reason'])
    if action=='analyze':return analyze(store,request['source'],request['findings'],request.get('complete',True),request.get('analyzed_until'),request.get('coverage'),request.get('revalidations'))
    if action=='resume_analysis':return resume(store,request['checkpoint'])
    if action=='confirm_deleted':return confirm_deleted(store,request['identity'],request.get('confirmation'))
    if action=='gc':return collect(store,request.get('keep_unreferenced',2))
    raise KnowledgeError('unsupported-confluence-action')


def collect(store,keep=2):
    require(type(keep) is int and 0<=keep<=20,'invalid-confluence-retention')
    with store.connection(True) as db:
        enable(db);pinned=set()
        def bindings(value):
            if isinstance(value,dict):
                if cf.is_binding(value) and isinstance(value.get('snapshot'),str):pinned.add(value['snapshot'])
                for item in value.values():bindings(item)
            elif isinstance(value,list):
                for item in value:bindings(item)
        # Approved historical provenance, pending/decided proposals, original
        # approvals and durable outboxes remain re-verifiable. Never age them out.
        for table,column in (('records','payload'),('revisions','payload'),('queue','payload'),('plans','payload')):
            for payload, in db.execute('SELECT '+column+' FROM '+table):bindings(loads(payload))
        for payload, in db.execute("SELECT payload FROM confluence_outbox WHERE status IN ('PREPARED','COLLECTING')"):bindings(loads(payload))
        for payload, in db.execute('SELECT payload FROM confluence_pages'):
            page=loads(payload);pinned.update(page[k] for k in ('latest_snapshot','last_analyzed_snapshot','coverage_certified_snapshot') if page.get(k))
        retained={};removed=[]
        for identifier,sid,version in db.execute('SELECT snapshot,source_id,version FROM confluence_snapshots ORDER BY source_id,version DESC'):
            cf.snapshot_info(db,identifier)
            if identifier in pinned:continue
            count=retained.get(sid,0);retained[sid]=count+1
            if count>=keep:removed.append(identifier)
        for identifier in removed:
            db.execute("DELETE FROM confluence_outbox WHERE snapshot=? AND status='DONE'",(identifier,))
            db.execute('DELETE FROM confluence_snapshots WHERE snapshot=?',(identifier,))
        before=db.execute('SELECT COUNT(*) FROM confluence_blobs').fetchone()[0]
        db.execute('DELETE FROM confluence_blobs WHERE content_hash NOT IN (SELECT content_hash FROM confluence_snapshots)')
        after=db.execute('SELECT COUNT(*) FROM confluence_blobs').fetchone()[0]
    return {'ok':True,'snapshots_removed':len(removed),'bodies_removed':before-after,'pinned_snapshots':len(pinned),'keep_unreferenced_per_page':keep,'canonical_records_removed':0}
