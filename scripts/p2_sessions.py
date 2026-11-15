"""Five distinct real automatic-capture sessions and explicit no-fact/degraded sessions."""
import argparse,json,sys,tempfile
from pathlib import Path
from p2_evidence import ROOT,save
sys.path.insert(0,str(ROOT/'tests'))
from p2_fixtures import project,configuration,task,http_provider,FixtureProvider
from harness.engine import start,status
from harness.runtime import configure
from knowledge.store import Store

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();sessions=[]
    for i in range(5):
        expected=f'public class CapturedSession{i} {{}}\n'
        with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider(desired=expected)) as endpoint:
            root=project(tmp,expected);configure(root,configuration(endpoint),True);outcome=start(root,task());assert outcome['ok'],outcome
            report=status(root,outcome['run_id']);store=Store(root);queue=store.export()['queue'];assert len(queue)==1;assert not store.export()['records']['claims']
            sessions.append(dict(session=i,expected_source=expected,report=report,candidates=queue,canonical_claims=0,queue_identity=queue[0]['id']))
    with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider()) as endpoint:
        root=project(tmp);configure(root,configuration(endpoint),False);outcome=start(root,task(kind='read-only'));assert outcome['ok'] and outcome['capture']['state']=='no-candidate';degraded=status(root,outcome['run_id'])
    save(a.output/'capture-sessions.json',dict(provider='test-double over actual HTTP',sessions=sessions,read_only_without_knowledge=degraded))
    print('PASS: five automatic eligible capture sessions, one candidate each, no canonical auto-apply; read-only/absent Knowledge no-candidate.')
if __name__=='__main__':main()
