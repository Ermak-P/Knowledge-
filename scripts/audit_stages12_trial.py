"""Installed fresh-process P4 architecture-delivery behavior trial.

The HTTP provider is a protocol double. It knows no project path, Store object,
claim ID or expected number: its decisions read only ordinary provider messages.
The source edits, SQLite approvals, subprocess build/tests and oracle are real.
"""
import argparse,hashlib,json,runpy,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from p2_fixtures import calls,final,http_provider
from knowledge.util import canonical_json,digest

class MessageOnlyProvider:
    def __init__(self):self.requests=[];self.responses=[];self.turns={}
    def decide(self,body):
        import re
        self.requests.append(body);system=json.loads(body['messages'][0]['content']);role=system['runtime_role'];agent=system['agent']
        number=None
        for claim in system.get('knowledge',{}).get('context',{}).get('claims',[]):
            match=re.search(r'approved pricing threshold is (\d+)',claim['statement'])
            if match:number=int(match[1])
        turn=self.turns.get(agent,0);self.turns[agent]=turn+1
        if number is None:answer=final('Required current architecture knowledge is unavailable.',status='failed')
        elif role=='Main':
            if any(i['status']!='done' for i in system['ledger']['items']):answer=calls(('delegate',{'role':'Coding','assignment':'Implement the approved pricing behavior.'}))
            elif 'review' not in system['progress']['gates']:answer=calls(('delegate',{'role':'Reviewing','assignment':'Independently review pricing behavior against approved architecture and actual checks.'}))
            else:answer=final('Approved behavior independently verified.')
        elif role=='Coding':
            if turn==0:answer=calls(('read',{'path':'Feature.py'}))
            elif turn==1:
                reads=[json.loads(m['content']) for m in body['messages'] if m['role']=='tool']
                answer=calls(('patch',{'files':[{'path':'Feature.py','before':reads[-1]['sha256'],'after':'def price():\n    return '+str(number)+'\n'}]}))
            else:answer=final('Untrusted Coding narrative: the threshold is 999.')
        elif role=='Reviewing':
            if turn==0:answer=calls(('read',{'path':'Feature.py'}))
            elif turn==1:
                reads=[json.loads(m['content']) for m in body['messages'] if m['role']=='tool']
                good=reads[-1].get('text')=='def price():\n    return '+str(number)+'\n' and all(g.get('ok') for n,g in system['progress']['gates'].items() if n!='review')
                answer=calls(('review',{'verdict':'approve' if good else 'reject','findings':[] if good else ['Feature.py violates approved pricing behavior.']}))
            else:answer=final('Independent canonical-store review complete.')
        else:answer=final()
        self.responses.append(answer);return answer


def setup(root,endpoint):
    from harness.runtime import configure
    from knowledge.store import Store
    from test_audit_stage2 import fact
    root.mkdir(parents=True)
    (root/'Feature.py').write_text('def price():\n    return 0\n',encoding='utf-8')
    (root/'test_feature.py').write_text('import unittest\nfrom Feature import price\nclass ApprovedBehavior(unittest.TestCase):\n def test_price(self): self.assertEqual(price(),37)\nif __name__=="__main__":unittest.main()\n',encoding='utf-8')
    cfg={'version':1,'provider':{'endpoint':endpoint,'model':'message-only-protocol-double','evidence':'test-double'},'capture':'off','limits':{},'recipes':{
        'build':{'kind':'build','argv':[sys.executable,'-c','import py_compile; py_compile.compile("Feature.py",doraise=True)'],'result':{'format':'exit','path':''},'rerun_safe':True,'env':{}},
        'test':{'kind':'test','argv':[sys.executable,'test_feature.py'],'result':{'format':'unittest','path':''},'rerun_safe':True,'env':{}}}}
    configure(root,cfg,True)
    identifier=fact(Store(root),root,'policy.price.threshold','The approved pricing threshold is 37.')
    task={'version':2,'goal':'Implement pricing behavior using the current approved threshold and run configured checks.',
        'kind':'coding','writable':['Feature.py'],'recipes':['build','test'],'existing_test_edits':[],
        'acceptance':['The pricing function returns the approved threshold. Independent checks and review pass.'],'items':[]}
    assert identifier not in canonical_json(task) and '37' not in canonical_json(task)
    (root/'task.json').write_text(json.dumps(task),encoding='utf-8')
    return identifier


def worker(root,disabled):
    from harness.engine import start,status
    from unittest.mock import patch
    task=json.loads((root/'task.json').read_text())
    if disabled:
        with patch('harness.delivery.retrieve',return_value={'ok':True,'available':False,'reason':'controlled-delivery-disabled'}):result=start(root,task)
    else:result=start(root,task)
    print(json.dumps({'result':result,**status(root,result['run_id'])},ensure_ascii=False))


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--phase',choices=['setup','run','verify']);p.add_argument('--endpoint');p.add_argument('--disabled',action='store_true');a=p.parse_args()
    if a.phase=='setup':print(setup(a.output,a.endpoint));return 0
    if a.phase=='run':worker(a.output,a.disabled);return 0
    if a.phase=='verify':
        value=runpy.run_path(str(a.output/'Feature.py'))['price']();print(json.dumps({'actual':value,'expected':37,'passed':value==37}));return 0
    import harness,knowledge
    assert Path(harness.__file__).is_relative_to(Path(sys.prefix)) and Path(knowledge.__file__).is_relative_to(Path(sys.prefix))
    out=a.output.absolute();out.mkdir(parents=True,exist_ok=False);rows={}
    for name,disabled in (('enabled',False),('control',True)):
        provider=MessageOnlyProvider();root=out/name
        with http_provider(provider) as endpoint:
            setup_run=subprocess.run([sys.executable,'-I',__file__,'--phase','setup','--output',str(root),'--endpoint',endpoint],capture_output=True,text=True,check=True)
            before=hashlib.sha256((root/'.knowledge/store.sqlite3').read_bytes()).hexdigest()
            run=subprocess.run([sys.executable,'-I',__file__,'--phase','run','--output',str(root),*(['--disabled'] if disabled else [])],capture_output=True,text=True,check=True)
        value=json.loads(run.stdout);oracle=json.loads(subprocess.check_output([sys.executable,'-I',__file__,'--phase','verify','--output',str(root)],text=True))
        assert hashlib.sha256((root/'.knowledge/store.sqlite3').read_bytes()).hexdigest()==before
        for index,body in enumerate(provider.requests):assert digest(body)==value['run']['requests'][index]['input_hash']
        used={call['function']['name'] for response in provider.responses for call in response.get('tool_calls',[])}
        assert 'knowledge' not in used
        if not disabled:
            assert value['result']['ok'] and oracle['passed']
            for role in ('Main','Coding','Reviewing'):
                body=next(b for b in provider.requests if json.loads(b['messages'][0]['content'])['runtime_role']==role)
                assert 'policy.price.threshold' in canonical_json(body)
            reviewing=next(json.loads(b['messages'][0]['content']) for b in provider.requests if json.loads(b['messages'][0]['content'])['runtime_role']=='Reviewing')
            assert '999' not in canonical_json(reviewing['knowledge']) and '999' in canonical_json(reviewing['ledger'])
        else:assert not value['result']['ok'] and not oracle['passed'] and 'policy.price.threshold' not in canonical_json(provider.requests)
        (out/(name+'-requests.json')).write_text(json.dumps(provider.requests,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (out/(name+'-run.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        rows[name]={'result':value['result'],'oracle':oracle,'provider_requests':len(provider.requests),'used_tools':sorted(used),'knowledge_store_unchanged':True,
            'claim_id':setup_run.stdout.strip() if not disabled else None,'knowledge_deliveries':len(value['run']['p4'].get('knowledge_deliveries',{}))}
    result={'status':'PASS','evidence':'real installed Python/SQLite/edits/checks; controlled HTTP provider, not a live model','rows':rows,'installed':{'harness':str(Path(harness.__file__)),'knowledge':str(Path(knowledge.__file__))}}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result));return 0

if __name__=='__main__':raise SystemExit(main())
