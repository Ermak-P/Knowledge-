"""Synthetic, reproducible CF progress benchmark; never use a production store.

Fixtures are bulk seeded in an isolated temporary DB. Canonical validation stays
in the product; this driver only measures the old status / new progress APIs.
"""
import argparse,contextlib,hashlib,json,math,platform,sqlite3,statistics,subprocess,sys,tempfile,threading,time
from pathlib import Path
from unittest.mock import patch
from knowledge import confluence as cf,confluence_command as cc,lifecycle as life
from knowledge.store import Store
from knowledge.util import canonical_json,digest
ROOT=Path(__file__).resolve().parents[1]
SIZES={'small':(200,400,100,50),'ipm':(1000,2000,12500,500),'stress':(10000,20000,50000,5000),'ipm-queue-control':(1000,2000,100,500)}


def record(name,proofs=1):
    ids=['e.'+name+'.'+str(i) for i in range(proofs)]
    c=dict(id=name,statement='Synthetic benchmark fact '+name,type='technical_fact',status='CONFIRMED',evidence=ids,provenance=dict(actor='synthetic-benchmark',method='fixture'),last_verified='2026-11-25',depends_on=[],conflicts_with=[])
    es=[dict(id=e,type='direct-technical',status='active',source='Fixture.cs',provenance=c['provenance'],captured_at='2026-11-25T00:00:00Z',location='Fixture.cs#L1',description='Synthetic evidence.',substantiates=[name]) for e in ids]
    return c,es


def seed(folder,size):
    store=Store(folder);store.init();life.upgrade(store,life.upgrade_preview(store)['fingerprint'])
    cc.configure(store,dict(roots=['https://docs.example.invalid/wiki/pages/0'],spaces=[],autonomous=False));cc.start(store,{'operations':10000})
    claims,evidence,pending,pages=size
    with store.connection(True) as db:
        run=cc.state(db,'run')
        for n in range(claims):
            c,es=record('canonical.'+str(n),evidence//claims)
            for kind,item in [('claims',c)]+[('evidence',e) for e in es]:
                db.execute('INSERT INTO records VALUES (?,?,?)',(item['id'],kind,canonical_json(item)))
                value=dict(id=item['id'],kind=kind,revision=1,record=item,lifecycle='active',successor=None,plan='synthetic-seed',reason='Synthetic benchmark only',source=None,captured_at=life.now(),verified_at=None)
                db.execute('INSERT INTO revisions VALUES (?,?,?)',(item['id'],1,canonical_json(value)))
        for n in range(pending):
            c,es=record('pending.'+str(n));ops=[life.op('add','evidence',e['id'],0,e) for e in es]+[life.op('add','claims',c['id'],0,c)]
            value=dict(version=2,operation='batch',operations=ops,reason='Synthetic unrelated pending work',source=None)
            db.execute("INSERT INTO queue VALUES (?,?,'pending',NULL)",(digest(value),canonical_json(value)))
        for n in range(pages):
            page=dict(identity=cf.identity('benchmark',str(n)),instance='benchmark',page_id=str(n),title='Synthetic page '+str(n),url='https://docs.example.invalid/wiki/pages/'+str(n),latest_version=1,last_analyzed_version=1,last_applied_version=None,origin='mandatory')
            from knowledge.confluence_sync import save_page
            save_page(db,page);cc.save_seen(db,dict(run=run['id'],identity=page['identity'],page={k:page[k] for k in ('instance','page_id','title','url')},origins=['mandatory'],state='UNCHANGED',classification='unchanged',baseline_analyzed=1,version=1,counts={}))
    return store


def percentile(values,p):return sorted(values)[max(0,math.ceil(len(values)*p)-1)] if values else None


def measure(store,action,samples,active):
    real=sqlite3.connect;local=threading.local();worker_started=threading.Event();worker_result={}
    def connect(*a,**kw):
        db=real(*a,**kw)
        def trace(sql):
            row=getattr(local,'sample',None)
            if row is not None:
                row['queries']+=1
                if sql.startswith('BEGIN'):row['begin']=time.perf_counter()
                if sql.startswith(('COMMIT','ROLLBACK')) and row.get('begin') is not None:row['transaction_ms']+=(time.perf_counter()-row.pop('begin'))*1000
            if threading.current_thread().name=='discovery-benchmark' and sql.startswith('BEGIN'):worker_started.set()
        db.set_trace_callback(trace);return db
    rows=[]
    def worker():
        try:
            started=time.perf_counter()
            cf.dispatch(store,'next',{})
            worker_result.update(ok=True,elapsed_ms=(time.perf_counter()-started)*1000)
        except Exception as error:worker_result.update(ok=False,error=str(error))
    with patch.object(sqlite3,'connect',connect):
        thread=threading.Thread(target=worker,name='discovery-benchmark') if active else None
        if thread:thread.start();worker_started.wait(60)
        for n in range(samples):
            row=dict(queries=0,transaction_ms=0,worker_active=bool(thread and thread.is_alive()));local.sample=row;started=time.perf_counter()
            try:
                result=cc.status(store) if action=='status' else cc.progress(store)
                assert result['coverage']['total_unique_pages']>0;row['ok']=True
            except Exception as error:row.update(ok=False,error=str(error))
            row['latency_ms']=(time.perf_counter()-started)*1000;row.pop('begin',None);rows.append(row);local.sample=None
        if thread:thread.join()
    times=[r['latency_ms'] for r in rows if r['ok']]
    return dict(samples=rows,successes=len(times),p50_ms=statistics.median(times) if times else None,p95_ms=percentile(times,.95),median_queries=statistics.median(r['queries'] for r in rows),p95_transaction_ms=percentile([r['transaction_ms'] for r in rows],.95),worker=worker_result if active else None)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--phase',choices=['before','after'],required=True);p.add_argument('--samples',type=int,default=7);p.add_argument('--scenarios',nargs='+',default=['small','ipm','stress']);a=p.parse_args()
    result=dict(phase=a.phase,commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),platform=platform.platform(),python=sys.version,modules={n:hashlib.sha256((ROOT/'packages/knowledge/src/knowledge'/n).read_bytes()).hexdigest() for n in ('confluence_command.py','confluence_sync.py','store.py')},scenarios={})
    a.output.parent.mkdir(parents=True,exist_ok=True)
    def save():a.output.write_text(json.dumps(result,indent=2)+'\n')
    save()
    for name in a.scenarios:
        with tempfile.TemporaryDirectory(prefix='cf-benchmark-') as tmp:
            store=seed(tmp,SIZES[name]);print('Seeded',name,SIZES[name],flush=True)
            action='status' if a.phase=='before' else 'progress'
            data=dict(size=dict(zip(('claims','evidence','pending_candidates','pages'),SIZES[name])),idle=measure(store,action,a.samples,False),active=measure(store,action,a.samples,True))
            with sqlite3.connect(store.path) as db:
                data['query_plans']={query:list(db.execute('EXPLAIN QUERY PLAN '+query)) for query in ("SELECT status,count(*) FROM confluence_work WHERE run='fixture' GROUP BY status","SELECT payload FROM confluence_work WHERE run='fixture' AND status IN ('PENDING','RUNNING') ORDER BY priority,id LIMIT 1","SELECT payload FROM confluence_seen WHERE run='fixture'")}
            if a.phase=='after':
                with store.progress_connection() as db:
                    queries=[];db.set_trace_callback(queries.append)
                    with patch.object(store,'progress_connection',lambda:contextlib.nullcontext(db)):cc.progress(store)
                    db.set_trace_callback(None)
                    data['progress_query_plans']=[dict(sql=q,plan=list(db.execute('EXPLAIN QUERY PLAN '+q))) for q in queries if q.startswith('SELECT')]
            result['scenarios'][name]=data;save();print(name,'p95 idle',data['idle']['p95_ms'],'active errors',a.samples-data['active']['successes'],flush=True)
if __name__=='__main__':main()
