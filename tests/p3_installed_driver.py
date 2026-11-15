"""Executed with isolated installed Python -I; no development product imports."""
import argparse,json,sys,importlib.util
from pathlib import Path
from knowledge.store import Store
from knowledge import lifecycle as life,discovery as disc,__version__
from knowledge.util import canonical_json,loads,read_text

def approve(s):
    p=s.prepare();assert p['ok'],p;s.apply(p['fingerprint'],p['fingerprint']);s.acknowledge(p['fingerprint']);return p

def snapshot(root):
    from harness.engine import status
    from harness.runtime import Journal
    j=Journal(root);s=Store(root)
    return dict(knowledge=s.export(),ownership=disc.capture_observation_receipts(s),runs=[status(root,r['id']) for r in j.runs()])

def main():
    p=argparse.ArgumentParser();p.add_argument('command');p.add_argument('--root',required=True);p.add_argument('--input',type=Path);p.add_argument('--id');a=p.parse_args();s=Store(a.root)
    import knowledge
    assert Path(knowledge.__file__).is_relative_to(Path(sys.prefix)) and not Path(knowledge.__file__).is_relative_to(Path(__file__).resolve().parents[1]),knowledge.__file__
    if a.command=='versions':
        import importlib.metadata as md
        value=dict(knowledge=__version__,prefix=sys.prefix,module=knowledge.__file__,harness_available=importlib.util.find_spec('harness') is not None,mcp_available=importlib.util.find_spec('mcp') is not None)
    elif a.command=='initialize':
        s.init();assert not s.export()['records']['claims'];life.upgrade(s,life.upgrade_preview(s)['fingerprint']);value=s.status()
    elif a.command=='scan':
        counts=[];original=disc.extract;seen=[]
        def observed(*args,**kwargs):seen.append(args[1]);return original(*args,**kwargs)
        disc.extract=observed;r=disc.scan(s,max_files=2);counts.append(len(seen))
        while not r['complete']:
            before=len(seen);r=disc.scan(s,r['id'],2);counts.append(len(seen)-before)
        assert max(counts)<=2
        value=dict(scan=r,work_counts=counts,total_extractions=len(seen))
    elif a.command=='approve':value=approve(s)
    elif a.command=='read':
        question=loads(read_text(a.input))['question'];value=dict(context=s.context(question),no_answer=s.context('zxq-no-supported-answer'),all=s.export())
    elif a.command=='snapshot':value=snapshot(a.root)
    elif a.command=='dispose':
        arg=loads(read_text(a.input));value=life.dispose(s,arg['id'],arg['disposition'],'Explicit rehearsal human review')
    elif a.command=='history':value=life.history(s,a.id)
    elif a.command=='compare':
        from harness.comparison import compare
        value=compare(a.root,loads(read_text(a.input)),Path(a.id))
    elif a.command=='fault-run':
        from harness import engine,runtime
        import os
        arg=loads(read_text(a.input))
        def die(phase):
            if phase==arg['phase']:os._exit(73)
        runtime.fault=die;value=engine.start(a.root,arg['task'])
    elif a.command=='inferred':
        claim=dict(id='rehearsal.uncertain',statement='Synthetic hypothetical cross-boundary theory.',type='technical_fact',status='INFERRED',evidence=['rehearsal.uncertain.evidence'],provenance={'actor':'rehearsal','method':'unverified'},last_verified=None,depends_on=[],conflicts_with=[])
        evidence=dict(id='rehearsal.uncertain.evidence',type='direct-technical',status='active',source='unknown.cs',location='unknown.cs#L1',description='Synthetic unsupported interpretation',substantiates=[claim['id']],captured_at='2026-11-15T00:00:00Z',provenance=claim['provenance'])
        s.submit({'version':1,'operation':'add','records':{'claims':[claim],'evidence':[evidence],'relationships':[]}});approve(s);value=s.context('hypothetical',include_unconfirmed=True);assert not value['claims']
    else:raise ValueError('unknown installed fixture command')
    print(canonical_json(value))
if __name__=='__main__':main()
