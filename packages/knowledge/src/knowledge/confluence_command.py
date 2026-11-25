"""Durable agent-mediated Confluence MCP work queue. No remote client or model.

Every result is client-reported source data. A work receipt attests local progress,
never authenticated remote coverage. Source documents cannot change this scope.
"""
from copy import deepcopy
from urllib.parse import urlsplit
import re,uuid
from . import confluence as cf,confluence_sync as sync,lifecycle as life
from .util import require,loads,canonical_json,digest,KnowledgeError

SCHEMA='1'
TABLES={
 'confluence_command_state':('key','payload','checksum'),
 'confluence_work':('id','run','kind','priority','status','payload','checksum'),
 'confluence_seen':('run','source_id','payload','checksum')}
TABLE_SQL={
 'confluence_command_state':'CREATE TABLE confluence_command_state(key TEXT PRIMARY KEY,payload TEXT NOT NULL,checksum TEXT NOT NULL)',
 'confluence_work':'CREATE TABLE confluence_work(id TEXT PRIMARY KEY,run TEXT NOT NULL,kind TEXT NOT NULL,priority INTEGER NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL,checksum TEXT NOT NULL)',
 'confluence_seen':'CREATE TABLE confluence_seen(run TEXT NOT NULL,source_id TEXT NOT NULL,payload TEXT NOT NULL,checksum TEXT NOT NULL,PRIMARY KEY(run,source_id))'}
INDEX_SQL={'confluence_work_next':'CREATE INDEX confluence_work_next ON confluence_work(run,status,priority,id)'}
META='confluence-command-schema'


def validate_control(db):
    marker=db.execute('SELECT value FROM metadata WHERE key=?',(META,)).fetchone()
    found={n for n, in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if marker is None:
        require(not set(TABLES)&found,'incomplete-confluence-command-extension');return False
    require(marker==(SCHEMA,) and set(TABLES)<=found,'unsupported-confluence-command-extension')
    for table,columns in TABLES.items():require(tuple(r[1] for r in db.execute('PRAGMA table_info('+table+')'))==columns,'corrupt-confluence-command-schema')
    return True


def enable(db):
    sync.enable(db)
    if validate_control(db):return
    for sql in (*TABLE_SQL.values(),*INDEX_SQL.values()):db.execute(sql)
    db.execute('INSERT INTO metadata VALUES (?,?)',(META,SCHEMA))


def state(db,key):
    if not validate_control(db):return None
    row=db.execute('SELECT payload,checksum FROM confluence_command_state WHERE key=?',(key,)).fetchone()
    return checked(*row) if row else None


def checked(raw,checksum):
    value=loads(raw);require(digest(value)==checksum,'corrupt-confluence-command-checkpoint');return value


def save_state(db,key,value):db.execute('INSERT OR REPLACE INTO confluence_command_state VALUES (?,?,?)',(key,canonical_json(value),digest(value)))


def integrity(db):
    if not validate_control(db):return
    for raw,checksum in db.execute('SELECT payload,checksum FROM confluence_command_state'):checked(raw,checksum)
    for identifier,run,kind,priority,status,raw,checksum in db.execute('SELECT * FROM confluence_work'):
        value=checked(raw,checksum);require((identifier,run,kind,priority,status)==tuple(value[k] for k in ('id','run','kind','priority','status')),'corrupt-confluence-work-index')
    for run,sid,raw,checksum in db.execute('SELECT * FROM confluence_seen'):
        value=checked(raw,checksum);require((run,sid)==(value['run'],value['identity']),'corrupt-confluence-seen-index')


def validate_control(db):
    marker=db.execute('SELECT value FROM metadata WHERE key=?',(META,)).fetchone()
    found={n for n, in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if marker is None:
        require(not set(TABLES)&found,'incomplete-confluence-command-extension');return False
    require(marker==(SCHEMA,) and set(TABLES)<=found,'unsupported-confluence-command-extension')
    for table,columns in TABLES.items():require(tuple(r[1] for r in db.execute('PRAGMA table_info('+table+')'))==columns,'corrupt-confluence-command-schema')
    return True


def enable(db):
    sync.enable(db)
    if validate_control(db):return
    for sql in (*TABLE_SQL.values(),*INDEX_SQL.values()):db.execute(sql)
    db.execute('INSERT INTO metadata VALUES (?,?)',(META,SCHEMA))


def checked(payload,checksum):
    data=loads(payload);require(digest(data)==checksum,'corrupt-confluence-command-checkpoint');return data


def state(db,key,default=None):
    if not validate_control(db):return default
    row=db.execute('SELECT payload,checksum FROM confluence_command_state WHERE key=?',(key,)).fetchone()
    return checked(*row) if row else default


def save_state(db,key,value):db.execute('INSERT OR REPLACE INTO confluence_command_state VALUES (?,?,?)',(key,canonical_json(value),digest(value)))


def integrity(db):
    if not validate_control(db):return
    for payload,checksum in db.execute('SELECT payload,checksum FROM confluence_command_state'):checked(payload,checksum)
    for identifier,rid,kind,priority,status,payload,checksum in db.execute('SELECT * FROM confluence_work'):
        value=checked(payload,checksum)
        require((identifier,rid,kind,priority,status)==tuple(value[k] for k in ('id','run','kind','priority','status')),'corrupt-confluence-work-index')
    for rid,sid,payload,checksum in db.execute('SELECT * FROM confluence_seen'):
        value=checked(payload,checksum);require(value['run']==rid and value['identity']==sid,'corrupt-confluence-seen-index')


def scope_value(value):
    require(isinstance(value,dict) and {'roots','spaces','autonomous'}<=set(value)<= {'roots','spaces','autonomous'},'invalid-confluence-discovery-scope')
    require(type(value['autonomous']) is bool and isinstance(value['roots'],list) and len(value['roots'])<=100 and isinstance(value['spaces'],list) and len(value['spaces'])<=100,'invalid-confluence-discovery-scope')
    roots=sorted({cf.url(r) for r in value['roots']});spaces=sorted(set(value['spaces']))
    require(all(isinstance(s,str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',s) for s in spaces),'invalid-confluence-space-scope')
    require(roots or value['autonomous'],'confluence-roots-or-autonomous-required')
    return dict(roots=roots,spaces=spaces,autonomous=value['autonomous'])


def configure(store,value):
    scope=scope_value(value)
    with store.connection(True) as db:
        enable(db);old=state(db,'scope');save_state(db,'scope',scope)
        run=state(db,'run')
        if old!=scope and run:
            run.update(status='SCOPE_CHANGED',next_action='Start a new run using the newly approved scope.');save_state(db,'run',run)
    return {'ok':True,'scope':scope,'scope_changed':old!=scope,'canonical_unchanged':True}


def save_work(db,value):
    db.execute('INSERT OR REPLACE INTO confluence_work VALUES (?,?,?,?,?,?,?)',tuple(value[k] for k in ('id','run','kind','priority','status'))+(canonical_json(value),digest(value)))


def enqueue(db,run,kind,target,origin='mandatory',cursor=None):
    identifier=digest(['confluence-work-v1',run['id'],kind,target,cursor])
    prior=db.execute('SELECT payload,checksum FROM confluence_work WHERE id=?',(identifier,)).fetchone()
    priority=(0 if kind in ('root','children') else 1) if origin=='mandatory' else 2 if origin=='referenced' else 3
    if prior:
        value=checked(*prior)
        if priority<value['priority']:value.update(priority=priority,origin=origin);save_work(db,value)
        return identifier
    save_work(db,dict(id=identifier,run=run['id'],kind=kind,target=target,cursor=cursor,origin=origin,priority=priority,status='PENDING',attempts=0))
    return identifier


def seen(db,run,sid):
    row=db.execute('SELECT payload,checksum FROM confluence_seen WHERE run=? AND source_id=?',(run['id'],sid)).fetchone()
    return checked(*row) if row else None


def save_seen(db,value):db.execute('INSERT OR REPLACE INTO confluence_seen VALUES (?,?,?,?)',(value['run'],value['identity'],canonical_json(value),digest(value)))


def discovered(db,run,page,origin):
    require(isinstance(page,dict) and {'instance','page_id','title','url'}<=set(page)<= {'instance','page_id','title','url','version','space_key','modified_at'},'invalid-confluence-discovered-page')
    sid=cf.identity(page['instance'],page['page_id']);address=cf.url(page['url']);scope=run['scope']
    hosts={urlsplit(r).netloc for r in scope['roots']}
    require(not hosts or urlsplit(address).netloc in hosts,'confluence-page-outside-approved-instance')
    require(not scope['spaces'] or 'space_key' not in page or page['space_key'] in scope['spaces'],'confluence-page-outside-approved-space')
    require(isinstance(page['title'],str) and len(page['title'])<=4096,'invalid-confluence-title')
    prior=seen(db,run,sid)
    if not prior:
        row=db.execute('SELECT payload FROM confluence_pages WHERE identity=?',(sid,)).fetchone()
        known=loads(row[0]) if row else None
        prior=dict(run=run['id'],identity=sid,page={k:v for k,v in page.items() if k!='version'},origins=[origin],state='DISCOVERED',classification='new' if not known or not known.get('last_analyzed_version') else 'pending',baseline_analyzed=known.get('last_analyzed_version') if known else None,counts={})
        if not known:sync.save_page(db,dict(identity=sid,instance=cf.instance_id(page['instance']),page_id=cf.page_id(page['page_id']),title=page['title'],url=address,latest_version=0,last_analyzed_version=None,last_applied_version=None,processing_status='DISCOVERED',origin=origin))
    elif origin not in prior['origins']:prior['origins'].append(origin)
    stored=deepcopy(cf.page(db,sid));members=stored.get('discovery_scopes',[])
    if digest(scope) not in members:members.append(digest(scope))
    stored['discovery_scopes']=members[-20:];sync.save_page(db,stored)
    save_seen(db,prior)
    origin='mandatory' if 'mandatory' in prior['origins'] else origin
    enqueue(db,run,'metadata',sid,origin)
    if not scope['spaces'] or page.get('space_key') in scope['spaces']:enqueue(db,run,'children',sid,origin)
    return sid


def terms(db,run,values):
    require(run['scope']['autonomous'],'confluence-autonomous-discovery-not-authorized')
    require(isinstance(values,list) and len(values)<=50 and all(isinstance(t,str) and 1<=len(t)<=160 for t in values),'invalid-confluence-search-terms')
    for term in values:
        normalized=' '.join(term.split()).casefold();require(normalized,'empty-confluence-search-term')
        enqueue(db,run,'search',normalized,'autonomous')


def start(store,request):
    with store.connection(True) as db:
        enable(db);scope=state(db,'scope');require(scope is not None,'confluence-scope-required')
        run=state(db,'run');extra=request.get('extra_operations',0)
        require(type(extra) is int and 0<=extra<=10000,'invalid-confluence-work-budget')
        caps=request.get('capabilities',{})
        require(isinstance(caps,dict) and set(caps)<= {'metadata_only','children','search','content'} and all(type(v) is bool for v in caps.values()),'invalid-confluence-mcp-capabilities')
        if run and run['scope']==scope and run['status'] not in ('COMPLETE','PARTIAL','SCOPE_CHANGED'):
            if 'capabilities' in request:run['capabilities']=caps
            run['budget']+=extra;run['status']='RUNNING';run.pop('integrity',None);save_state(db,'run',run)
        else:
            budget=request.get('operations',100);require(type(budget) is int and 1<=budget<=10000,'invalid-confluence-work-budget')
            run=dict(id=uuid.uuid4().hex,status='RUNNING',scope=scope,budget=budget,completed_operations=0,started_at=life.now(),capabilities=caps)
            save_state(db,'run',run)
            for root in scope['roots']:enqueue(db,run,'root',root)
            for payload, in db.execute('SELECT payload FROM confluence_pages ORDER BY identity'):
                page=loads(payload)
                if not scope['autonomous'] and digest(scope) not in page.get('discovery_scopes',[]):continue
                try:discovered(db,run,{k:page[k] for k in ('instance','page_id','title','url','space_key') if k in page},page.get('origin','autonomous'))
                except KnowledgeError as error:
                    if error.code not in ('confluence-page-outside-approved-instance','confluence-page-outside-approved-space'):raise
            if scope['autonomous']:
                seeds=[store.project.root.name[:160]]
                for payload, in db.execute("SELECT payload FROM records WHERE kind='claims' LIMIT 50"):
                    claim=loads(payload);seeds.extend(re.findall(r'\b[A-Z][A-Za-z0-9_.]{2,50}\b',claim['statement'])[:3])
                terms(db,run,list(dict.fromkeys(seeds))[:50])
            # Previous completed run work is temporary. Keep only three receipts;
            # immutable sources, candidate/plan history and canonical rows survive.
            previous=[r for r, in db.execute("SELECT run FROM confluence_work WHERE run<>? GROUP BY run HAVING sum(status<>'DONE')=0 ORDER BY min(rowid)",(run['id'],))]
            for rid in previous[:-3]:
                db.execute('DELETE FROM confluence_work WHERE run=?',(rid,));db.execute('DELETE FROM confluence_seen WHERE run=?',(rid,))
    return status(store)


def work_at(db,identifier):
    row=db.execute('SELECT payload,checksum FROM confluence_work WHERE id=?',(identifier,)).fetchone()
    require(row is not None,'unknown-confluence-work');return checked(*row)


def next_work(store):
    with store.connection(True) as db:
        enable(db);run=state(db,'run');require(run is not None,'confluence-run-required');require(run['scope']==state(db,'scope'),'confluence-scope-changed-restart-required')
        if run['completed_operations']>=run['budget']:
            pending=db.execute("SELECT 1 FROM confluence_work WHERE run=? AND status IN ('PENDING','RUNNING')",(run['id'],)).fetchone()
            if pending:run['status']='BUDGET_PAUSED';save_state(db,'run',run);return {'ok':True,'state':'BUDGET_PAUSED','work':None,'coverage_complete':False,'next_action':'Resume with extra_operations; unfinished work is retained.'}
        row=db.execute("SELECT payload,checksum FROM confluence_work WHERE run=? AND status IN ('PENDING','RUNNING') ORDER BY priority,id LIMIT 1",(run['id'],)).fetchone()
        if row:
            value=checked(*row);value['status']='RUNNING';save_work(db,value)
            detail={}
            if value['kind'] not in ('root','search'):
                page=cf.page(db,value['target']);detail={'page':{k:page[k] for k in ('instance','page_id','title','url','latest_version','latest_snapshot','analysis_checkpoint','analysis_offset','space_key') if k in page}}
            return {'ok':True,'state':'RUNNING','work':value,**detail,'source_content_is_untrusted':True,'metadata_only_preferred':run['capabilities'].get('metadata_only',False)}
        failures=db.execute("SELECT count(*) FROM confluence_work WHERE run=? AND status IN ('FAILED','SKIPPED')",(run['id'],)).fetchone()[0]
        run.update(status='PARTIAL' if failures else 'COMPLETE',finished_at=life.now());save_state(db,'run',run)
    return {**status(store),'work':None}


def complete_work(store,identifier,result):
    require(isinstance(result,dict) and set(result)<= {'page','pages','next_cursor','has_more','snapshot','findings','complete','terms','reason','references','analyzed_until','coverage','revalidations'},'invalid-confluence-work-result')
    with store.connection() as db:
        work=work_at(db,identifier);run=state(db,'run');require(work['run']==run['id'] and run['scope']==state(db,'scope'),'stale-confluence-work')
        if work.get('last_partial_hash')==digest(result):return status(store)
        if work['status']=='DONE':
            require(work.get('result_hash')==digest(result),'confluence-work-result-conflict');return status(store)
        require(work['status'] in ('RUNNING','PENDING'),'confluence-failed-work-needs-explicit-retry')
    reason=result.get('reason');kind=work['kind'];sid=work['target'];outcome={};origin=work['origin']
    if not reason and kind in ('metadata','content'):
        data=result['page' if kind=='metadata' else 'snapshot'];scope=run['scope']
        require(not scope['spaces'] or data.get('space_key') is not None,'confluence-space-verification-required')
        if scope['spaces'] and data['space_key'] not in scope['spaces']:reason='OUTSIDE_SCOPE'
        hosts={urlsplit(r).netloc for r in scope['roots']}
        require(not hosts or urlsplit(cf.url(data['url'])).netloc in hosts,'confluence-page-outside-approved-instance')
    if reason:
        require(reason in ('ACCESS_DENIED','TIMEOUT','UNAVAILABLE','NOT_FOUND_UNCONFIRMED','INCOMPLETE_RESPONSE','CAPABILITY_UNAVAILABLE','IRRELEVANT','OUTSIDE_SCOPE'),'invalid-confluence-work-failure')
        if kind not in ('root','search') and reason not in ('CAPABILITY_UNAVAILABLE','IRRELEVANT','OUTSIDE_SCOPE'):sync.failure(store,sid,reason)
    elif kind=='metadata':
        page=result['page'];require(cf.identity(page['instance'],page['page_id'])==sid,'confluence-work-page-mismatch')
        outcome=sync.observe(store,page)
        require(outcome['action']!='IGNORE_OLDER_METADATA','confluence-mcp-metadata-older-than-observed')
        if result.get('snapshot'):
            snapshot=result['snapshot']
            require(cf.identity(snapshot['instance'],snapshot['page_id'])==sid and snapshot['version']==page['version'],'confluence-work-page-mismatch')
            cached=cf.register(store,snapshot)
            if outcome['action']!='SKIP':outcome['action']='SKIP' if cached['sync']['action']=='SKIP_ANALYSIS' else 'RESUME_ANALYSIS'
    elif kind=='content':
        snapshot=result['snapshot'];require(cf.identity(snapshot['instance'],snapshot['page_id'])==sid,'confluence-work-page-mismatch')
        with store.connection() as db:observed=cf.page(db,sid)['latest_version']
        require(snapshot['version']>=observed,'confluence-mcp-snapshot-older-than-observed')
        sync.observe(store,{k:v for k,v in snapshot.items() if k in ('instance','page_id','version','title','url','space_key','modified_at')})
        outcome=cf.register(store,snapshot)
    elif kind=='analysis':
        with store.connection() as db:
            page=cf.page(db,sid);source=sync.source_now(page);checkpoint=page.get('analysis_checkpoint')
            saved=sync._outbox(db,checkpoint) if checkpoint else None
        if saved and saved['status']=='PREPARED':outcome=sync.resume(store,checkpoint)
        else:
            require('findings' in result,'confluence-analysis-findings-required')
            outcome=sync.analyze(store,source,result['findings'],result.get('complete',True),result.get('analyzed_until'),result.get('coverage'),result.get('revalidations'))
    with store.connection(True) as db:
        enable(db);run=state(db,'run');work=work_at(db,identifier)
        run.pop('integrity',None)
        if reason:
            work.update(status='SKIPPED' if reason in ('IRRELEVANT','OUTSIDE_SCOPE') else 'FAILED',failure=reason)
            if kind not in ('root','search'):
                item=seen(db,run,sid)
                if item:item.update(state='FAILED',failure=reason);save_seen(db,item)
        else:
            if kind=='root':discovered(db,run,result['page'],'mandatory')
            elif kind in ('children','search'):
                pages=result.get('pages',[]);require(isinstance(pages,list) and len(pages)<=1000,'confluence-discovery-batch-too-large')
                require(type(result.get('has_more')) is bool,'confluence-pagination-completion-required')
                for page in pages:
                    try:discovered(db,run,page,origin)
                    except KnowledgeError as error:
                        if error.code not in ('confluence-page-outside-approved-instance','confluence-page-outside-approved-space'):raise
                        run['skipped_outside_scope']=run.get('skipped_outside_scope',0)+1
                cursor=result.get('next_cursor')
                require(not result['has_more'] or isinstance(cursor,str) and 0<len(cursor)<=2048 and cursor!=work['cursor'],'confluence-pagination-cursor-required')
                if result['has_more']:
                    next_id=digest(['confluence-work-v1',run['id'],kind,work['target'],cursor])
                    require(not db.execute('SELECT 1 FROM confluence_work WHERE id=?',(next_id,)).fetchone(),'confluence-pagination-cycle-or-repeated-cursor')
                    enqueue(db,run,kind,work['target'],origin,cursor)
                work['coverage_exhausted']=not result['has_more']
            elif kind=='metadata':
                enqueue(db,run,'children',sid,origin)
                item=seen(db,run,sid);version=result['page']['version'];item.update(version=version,native_version_changed=bool(item['baseline_analyzed'] and item['baseline_analyzed']!=version),classification='new' if not item['baseline_analyzed'] else 'unchanged' if item['baseline_analyzed']==version or outcome['action']=='SKIP' else 'changed',state='UNCHANGED' if outcome['action']=='SKIP' else 'PENDING_ANALYSIS');save_seen(db,item)
                if outcome['action']=='FETCH_CONTENT':enqueue(db,run,'content',sid,origin)
                elif outcome['action']=='RESUME_ANALYSIS':enqueue(db,run,'analysis',sid,origin)
            elif kind=='content':
                item=seen(db,run,sid);version=result['snapshot']['version'];item.update(version=version,classification='new' if not item['baseline_analyzed'] else 'unchanged' if item['baseline_analyzed']==version else 'changed');save_seen(db,item)
                if outcome['sync']['action']!='SKIP_ANALYSIS':enqueue(db,run,'analysis',sid,origin)
                else:
                    item=seen(db,run,sid);item.update(state='UNCHANGED_CONTENT',classification='unchanged',analysis_reused=True);save_seen(db,item)
            elif kind=='analysis':
                item=seen(db,run,sid);item.update(state='ANALYZED' if outcome.get('analysis_complete',True) else 'PARTIAL_ANALYSIS',counts={k:outcome.get(k,0) for k in ('new_claim_candidates','existing_claims_enriched','duplicates_prevented','conflicts_detected')},questions=outcome.get('clarification_questions',[]));save_seen(db,item)
                if not outcome.get('analysis_complete',True):
                    run['completed_operations']+=1;work.update(status='PENDING',last_partial_hash=digest(result),attempts=work['attempts']+1);save_work(db,work);save_state(db,'run',run)
                    return {'ok':True,'state':'PARTIAL_ANALYSIS','checkpoint':outcome['checkpoint'],'work':identifier,'canonical_unchanged':True}
            if result.get('terms'):terms(db,run,result['terms'])
            references=result.get('references',[]);require(isinstance(references,list) and len(references)<=100,'invalid-confluence-references')
            for page in references:
                if run['scope']['autonomous']:discovered(db,run,page,'referenced')
                else:run['skipped_references_without_search_permission']=run.get('skipped_references_without_search_permission',0)+1
            work.update(status='DONE',result_hash=digest(result))
        run['completed_operations']+=1;save_work(db,work);save_state(db,'run',run)
    return status(store)


def status(store):
    with store.connection() as db:
        scope=state(db,'scope');run=state(db,'run')
        if scope is None:return {'ok':True,'state':'SCOPE_REQUIRED','required_questions':['Root page/section URLs (multiple or none for autonomous-only)?','Optional space keys?','Allow autonomous discovery?'],'canonical_unchanged':True}
        if run is None:return {'ok':True,'state':'CONFIGURED','scope':scope,'canonical_unchanged':True}
        rows=[checked(*r) for r in db.execute('SELECT payload,checksum FROM confluence_seen WHERE run=?',(run['id'],))]
        counts=dict(total_unique_pages=len(rows),mandatory_pages=sum('mandatory' in r['origins'] for r in rows),autonomous_pages=sum('mandatory' not in r['origins'] for r in rows),new=sum(r['classification']=='new' for r in rows),changed=sum(r['classification']=='changed' for r in rows),unchanged=sum(r['state'] in ('UNCHANGED','UNCHANGED_CONTENT') for r in rows),failed=sum(r['state']=='FAILED' for r in rows),successfully_analyzed=sum(r['state'] in ('ANALYZED','UNCHANGED','UNCHANGED_CONTENT') for r in rows),awaiting_processing=sum(r['state'] not in ('ANALYZED','UNCHANGED','UNCHANGED_CONTENT','FAILED') for r in rows))
        for key in ('new_claim_candidates','existing_claims_enriched','duplicates_prevented','conflicts_detected'):counts[key]=sum(r['counts'].get(key,0) for r in rows)
        counts['native_version_changed']=sum(r.get('native_version_changed',False) for r in rows)
        work_counts={s:n for s,n in db.execute('SELECT status,count(*) FROM confluence_work WHERE run=? GROUP BY status',(run['id'],))}
        from .discovery import candidate_refreshes
        refreshes=candidate_refreshes(db)
        queued={cid:loads(raw) for cid,raw in db.execute("SELECT id,payload FROM queue WHERE status='pending'") if cid not in refreshes}
        active,skipped,blocked=cf.pending_partition(db,queued);pending=len(active)
        source_applied=sum(cf.page(db,r['identity']).get('last_applied_version')==r.get('version') and r.get('version') is not None for r in rows)
        # Only compact failure data, never MCP page bodies or credentials.
        limitations=[dict(kind=kind,target=value['target'],reason=value.get('failure')) for kind,raw in db.execute("SELECT kind,payload FROM confluence_work WHERE run=? AND status IN ('FAILED','SKIPPED') LIMIT 20",(run['id'],)) for value in [loads(raw)]]
        mandatory_pending=db.execute("SELECT count(*) FROM confluence_work WHERE run=? AND priority<2 AND status<>'DONE'",(run['id'],)).fetchone()[0]
        sections=[dict(url=loads(raw)['target'],entry_status=state,descendant_coverage='incomplete' if mandatory_pending else 'complete') for raw,state in db.execute("SELECT payload,status FROM confluence_work WHERE run=? AND kind='root' ORDER BY id",(run['id'],))]
        states=life.latest(db)
        active_claims={i['id']:i for i in store._records(db)['claims'] if states.get(i['id'],{}).get('lifecycle')=='active'}
        conflicts={tuple(sorted((c['id'],other))) for c in active_claims.values() for other in c['conflicts_with'] if other in active_claims}
        questions=list(dict.fromkeys([q for r in rows for q in r.get('questions',[])]+['Clarify the current scope and evidence for conflict '+a+' / '+b for a,b in sorted(conflicts)]))
        return {'ok':True,'state':run['status'],'run':run['id'],'scope':scope,'mandatory_sections':sections,'coverage_complete':run['status']=='COMPLETE','coverage_attestation':'client-reported MCP traversal only; live access not independently attested','coverage':counts,'work':work_counts,'completed_operations':run['completed_operations'],'operation_budget':run['budget'],'applied_pages':source_applied,'pending_candidates':pending,'stale_or_incomplete_candidates':len(skipped),'knowledge_update_required':bool(pending or skipped),'unresolved_conflicts':len(conflicts),'clarification_questions':questions[:50],'limitations':limitations,'metadata_retrieval':'metadata-only available' if run['capabilities'].get('metadata_only') else 'metadata-only capability unavailable/unreported; use most efficient supported retrieval','integrity':run.get('integrity','NOT_RUN'),'canonical_unchanged':True}


def dispatch(store,action,request):
    if action=='scope':return {'ok':True,'scope':scope_value(request['scope'])} if request.get('validate_only') else configure(store,request['scope'])
    if action=='start':return start(store,request)
    if action=='status':return status(store)
    if action=='next':return next_work(store)
    if action=='complete_work':return complete_work(store,request['work'],request['result'])
    if action=='terms':
        with store.connection(True) as db:
            enable(db);run=state(db,'run');require(run is not None,'confluence-run-required');terms(db,run,request['terms']);run['status']='RUNNING';run.pop('integrity',None);save_state(db,'run',run)
        return status(store)
    if action=='retry':
        with store.connection(True) as db:
            run=state(db,'run');work=work_at(db,request['work']);require(work['run']==run['id'] and work['status'] in ('FAILED','SKIPPED'),'confluence-work-not-retryable')
            work.update(status='PENDING',attempts=work['attempts']+1);work.pop('failure',None);save_work(db,work);run['status']='RUNNING';run.pop('integrity',None);save_state(db,'run',run)
        return status(store)
    if action=='finish':
        validation=store.validate();retention=sync.collect(store)
        with store.connection(True) as db:
            run=state(db,'run');require(run is not None,'confluence-run-required');run['integrity']='PASS' if validation['ok'] else 'FAIL';save_state(db,'run',run)
        return {**status(store),'retention':retention}
    raise KnowledgeError('unsupported-confluence-command-action')
