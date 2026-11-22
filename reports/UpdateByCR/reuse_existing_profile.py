"""Actual installed existing-Knowledge reason reuse and canonical CAS refusal."""
import argparse,importlib.util,json,sys,tempfile
from pathlib import Path
from knowledge.cr_workflow import Workflow
from knowledge.store import Store
from knowledge.util import KnowledgeError


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    repo=Path(__file__).resolve().parents[2];spec=importlib.util.spec_from_file_location('ucr_fixture',repo/'tests/cr_fixtures.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
    with tempfile.TemporaryDirectory(prefix='ucr-existing-') as tmp:
        root,snapshot=f.project(tmp);w=Workflow(root);s=f.ready(w,snapshot,f.decisions(snapshot));prepared=w.prepare(s['session'],s['revision']);saved=w.apply(s['session'],prepared['proposal']['plan'],prepared['revision'])
        records=saved['receipt']['records'];items=f.decisions(snapshot)
        for item,record in zip(items,records):
            known=w.store.lookup('claims',record['id']);item['reason']={'text':known['record']['statement'].split('Reason / Причина: ',1)[1].split('Preserve / Сохранить:',1)[0].strip(),'refs':['knowledge:'+record['id']+'@'+str(record['revision'])]}
        refreshed=w.sources(saved['session'],snapshot,saved['revision']);analysis=w.analyze(saved['session'],items,refreshed['revision']);assert analysis['state']=='ready_for_review' and not analysis['questions']
        # Another legitimate canonical revision invalidates this analysis even
        # with an unchanged Git source. Its approved lifecycle is independent.
        sid=analysis['session'];other=Workflow(root);before=other.get(sid)
        corrected=f.decisions(snapshot)
        for item,record in zip(corrected,records):item['existing_id']=record['id']
        corrected[0]['statement']+=' only while the public contract is unchanged'
        state=other.analyze(sid,corrected,analysis['revision'])
        for q in other.get(sid)['questions']:
            if q['id'] not in other.get(sid)['answers']:state=other.answer(sid,q['id'],'Preserve existing ownership and compatibility','new-'+q['id'],state['revision'])
        plan=other.prepare(sid,state['revision']);changed=other.apply(sid,plan['proposal']['plan'],plan['revision'])
        try:w._fresh(before)
        except KnowledgeError as error:assert error.code=='ucr-analysis-stale';cas=error.code
        else:raise AssertionError('Competing canonical update accepted stale analysis')
        value=dict(status='PASS',profile='installed-existing-knowledge-and-canonical-cas',reused_references=[i['reason']['refs'] for i in items],no_redundant_questions=analysis['questions'],canonical_update=changed['receipt']['records'],stale_analysis_refusal=cas)
        (args.output/'result.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value,indent=2))
if __name__=='__main__':main()
