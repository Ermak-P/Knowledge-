"""Private synthetic 40k scan-record / 25k proposed-claim benchmark; no inference."""
import argparse,contextlib,hashlib,json,sqlite3,tempfile,time,tracemalloc
from pathlib import Path
from unittest.mock import patch
from knowledge.store import Store
from knowledge import lifecycle as life
from knowledge.util import canonical_json,digest


def claim(i,statement):
    return {'id':i,'statement':statement,'type':'technical_fact','status':'CONFIRMED','evidence':['e.'+i],
            'provenance':{'actor':'synthetic','method':'benchmark'},'last_verified':'2026-11-01','depends_on':[],'conflicts_with':[]}


def evidence(c,path):
    return {'id':'e.'+c['id'],'type':'direct-technical','status':'active','source':path,'location':path+'#L1',
            'captured_at':'2026-11-01T00:00:00Z','description':'Synthetic evidence only.',
            'provenance':c['provenance'],'substantiates':[c['id']]}


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--claims',type=int,default=25000);p.add_argument('--unique',action='store_true');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='plan-benchmark-') as temp:
        store=Store(temp);store.init();life.upgrade(store,life.upgrade_preview(store)['fingerprint'])
        candidates=[];items=[]
        for n in range(a.claims):
            logical=n if a.unique else n//2
            c=claim('new.'+str(n),'Synthetic symbol '+str(logical)+'.');e=evidence(c,'source%05d.cs'%n)
            if not a.unique and n==25:c['provenance']={'actor':'incompatible','method':'benchmark'}
            items.extend([life.op('add','claims',c['id'],0,c),life.op('add','evidence',e['id'],0,e)])
            if len(items)>=500 or n==a.claims-1:
                candidates.append(life.batch(items,'Synthetic benchmark batch '+str(n)));items=[]
        # Fixture-only bulk loading, with real product validation during prepare.
        with store.connection(True) as db:
            for n in range(100):
                c=claim('canonical.'+str(n),'Canonical unique '+str(n)+'.' if a.unique else 'Synthetic symbol '+str(n)+'.');e=evidence(c,'source%05d.cs'%n)
                for kind,r in (('claims',c),('evidence',e)):
                    db.execute('INSERT INTO records VALUES (?,?,?)',(r['id'],kind,canonical_json(r)))
                    rev={'id':r['id'],'kind':kind,'revision':1,'record':r,'lifecycle':'active','successor':None,'plan':'synthetic-baseline','reason':'fixture','source':None,'captured_at':'2026-11-01T00:00:00Z','verified_at':None}
                    db.execute('INSERT INTO revisions VALUES (?,?,?)',(r['id'],1,canonical_json(rev)))
            for value in candidates:db.execute('INSERT INTO queue VALUES (?,?,?,NULL)',(digest(value),canonical_json(value),'pending'))
            files={'source%05d.cs'%n:{'hash':'sha256:'+hashlib.sha256(str(n).encode()).hexdigest(),'partition':'.','status':'blocked' if n<78 else 'partial' if n<93 else 'analyzed'} for n in range(40000)}
            scan={'id':'a'*64,'extractor':'dotnet-lexical-v3','snapshot':{'identity':'b'*64,'files':files,'revision':None},'coverage':files,'observations':[],
                  'candidates':[],'complete':False,'processing_complete':True,'state':'COMPLETED_WITH_GAPS','work':{'remaining_files':0,'durable_extracted_files':40000}}
            db.execute('INSERT INTO scans VALUES (?,?)',(scan['id'],canonical_json(scan)))
        queries=[0];original=store.connection
        @contextlib.contextmanager
        def traced(*args,**kwargs):
            with original(*args,**kwargs) as db:
                db.set_trace_callback(lambda sql:queries.__setitem__(0,queries[0]+1));yield db
        before=digest(store.export()['records']);tracemalloc.start();began=time.perf_counter()
        with patch.object(store,'connection',traced):plan=store.prepare()
        elapsed=time.perf_counter()-began;peak=tracemalloc.get_traced_memory()[1];tracemalloc.stop()
        assert before==digest(store.export()['records'])
        result={'synthetic_only':True,'source_file_records':40000,'proposed_claim_operations':a.claims,'unique_profile':a.unique,
                'input_identity':digest(candidates),'seconds':elapsed,'peak_tracemalloc_bytes':peak,'sqlite_queries':queries[0],
                'ok':plan['ok'],'blockers':plan['blocked'],'fingerprint':plan['fingerprint'],'canonical_unchanged':True,
                'normalization':'exact-utf8-v1' if hasattr(store,'duplicate_diagnostics') else 'legacy-NFKC-casefold-whitespace'}
        import knowledge.store as implementation
        result['implementation_hash']=digest({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(implementation.__file__).parent.glob('*.py'))})
        try:
            import resource
            result['process_peak_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        except ImportError:pass
        if hasattr(store,'duplicate_diagnostics'):
            from knowledge.diagnostic_pages import page
            began=time.perf_counter();counts,groups=store.duplicate_diagnostics();result['diagnostic_analysis_seconds']=time.perf_counter()-began
            reply=page(groups,{'ok':True,'counts':counts},0,2,16000)
            result.update(counts=counts,diagnostic_response_bytes=len(canonical_json(reply).encode()))
        (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
