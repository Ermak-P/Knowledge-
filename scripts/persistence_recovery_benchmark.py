"""Production-shape virtual-source benchmark with explicit integrity assertions."""
import argparse,contextlib,hashlib,json,os,sys,tempfile,time,tracemalloc
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from persistence_scale_fixture import populate
from knowledge import discovery,lifecycle as life
from knowledge.store import Store
from knowledge.util import canonical_json,digest


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);a=parser.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='persistence-scale-') as tmp:
        store=Store(tmp);store.init();life.upgrade(store,life.upgrade_preview(store)['fingerprint']);state,pending=populate(store)
        before=digest(store.export()['records']);queries=[0];original=store.connection
        @contextlib.contextmanager
        def traced(*args,**kwargs):
            with original(*args,**kwargs) as db:
                db.set_trace_callback(lambda sql:queries.__setitem__(0,queries[0]+1));yield db
        tracemalloc.start();start=time.perf_counter()
        with patch.object(discovery,'inventory',return_value=state['snapshot']),patch.object(store,'connection',traced):plan=store.prepare()
        elapsed=time.perf_counter()-start;peak=tracemalloc.get_traced_memory()[1];tracemalloc.stop()
        result=dict(synthetic_only=True,virtual_source_inventory=True,files=40000,proposed_claims=12507,canonical_claims=697,
                    input_identity=digest(pending),prepare_seconds=elapsed,peak_tracemalloc_bytes=peak,prepare_body_sql_queries=queries[0],
                    ok=plan['ok'],blockers=plan['blocked'],canonical_unchanged=before==digest(store.export()['records']))
        if hasattr(store,'duplicate_diagnostics'):
            from knowledge.diagnostic_pages import page
            start=time.perf_counter();counts,groups=store.duplicate_diagnostics();result['duplicate_diagnostics_seconds']=time.perf_counter()-start
            assert counts['exact_duplicate_statement_groups']==10 and counts['claims_in_duplicate_groups']==26 and counts['redundant_claim_records']==16,counts
            assert counts['resulting_claim_adds']==12491 and counts['resulting_evidence_operations']==12507,counts
            assert plan['ok'],plan['blocked']
            result.update(counts=counts,diagnostics_bytes=len(canonical_json(page(groups,{'ok':True,'counts':counts},0,2,16000)).encode()))
            start=time.perf_counter()
            with patch.object(discovery,'inventory',return_value=state['snapshot']),patch.object(discovery,'extract',side_effect=AssertionError('unexpected extraction')):
                discovery.completed_artifact(store,state['id']);repeated=store.prepare()
            result['recovery_seconds']=time.perf_counter()-start;assert repeated['fingerprint']==plan['fingerprint']
            with store.connection() as db:
                assert digest({cid:json.loads(p) for cid,p in db.execute('SELECT id,payload FROM queue')})==digest(pending)
                saved=json.loads(db.execute('SELECT payload FROM scans WHERE id=?',(state['id'],)).fetchone()[0]);assert saved==state
            result.update(original_artifacts_unchanged=True,recovery_idempotent=True,evidence_preserved=counts['resulting_evidence_operations'])
        package=Path(discovery.__file__).parent
        result['implementation_hash']=digest({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(package.glob('*.py'))})
        assert before==digest(store.export()['records'])
        if hasattr(store,'duplicate_diagnostics'):
            effective=[op for item in plan['resolved'].values() if item for op in item['operations']]
            assert len({o['id'] for o in effective if o['kind']=='evidence'})==12507
            for cid,item in pending.items():
                if not any(o['id'].startswith('scan.') for o in item['operations']):assert plan['resolved'][cid]==item
        try:
            import resource
            result['process_peak_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        except ImportError:pass
        (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
