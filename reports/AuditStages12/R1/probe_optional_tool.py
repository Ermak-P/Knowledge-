"""Installed read-only P4 wire reproducer; protocol provider, real CLI/SQLite.

The provider sees ordinary messages only. Setup and execution use fresh processes.
Use --expected legacy only with the independently pinned reviewed runtime.
"""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,default=Path('/workspace/Knowledge-'));p.add_argument('--output',type=Path,required=True);p.add_argument('--phase',choices=['setup','run']);p.add_argument('--endpoint');p.add_argument('--expected',choices=['current','legacy'],default='current');a=p.parse_args()
sys.path.insert(0,str(a.repo/'tests'))
from knowledge.util import canonical_json,digest
from knowledge.store import Store
STATEMENT='ImprovedFeature requires an unverified historical threshold.'

def setup(root,endpoint):
 from fixtures import addition
 from test_p1 import approve
 from p2_fixtures import project,configuration
 from harness.runtime import configure
 project(root);store=Store(root);store.init();store.submit(addition('legacy.feature',STATEMENT));approve(store)
 cfg=configuration(endpoint);cfg['capture']='off';configure(root,cfg,True)
 task={'version':2,'goal':'Inspect ImprovedFeature architecture.','kind':'read-only','writable':[],'recipes':[],'existing_test_edits':[],'acceptance':['Provide read-only architecture analysis.'],'items':[]}
 (root/'task.json').write_text(json.dumps(task),encoding='utf-8')

if a.phase=='setup':setup(a.output,a.endpoint);raise SystemExit(0)
if a.phase=='run':
 from harness.engine import start,status
 result=start(a.output,json.loads((a.output/'task.json').read_text()));print(json.dumps({'result':result,**status(a.output,result['run_id'])}));raise SystemExit(0)

import harness,knowledge
assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (harness,knowledge))
from p2_fixtures import http_provider,calls,final
class Provider:
 def __init__(self):self.bodies=[]
 def decide(self,body):
  self.bodies.append(body)
  return calls(('knowledge',{'task':'ImprovedFeature'})) if len(self.bodies)==1 else final('Read-only analysis complete.')
out=a.output.absolute();out.mkdir(parents=True,exist_ok=False);root=out/'project';model=Provider()
with http_provider(model) as endpoint:
 subprocess.run([sys.executable,'-I',__file__,'--repo',str(a.repo),'--output',str(root),'--phase','setup','--endpoint',endpoint],check=True,capture_output=True,text=True)
 before=hashlib.sha256((root/'.knowledge/store.sqlite3').read_bytes()).hexdigest()
 child=subprocess.run([sys.executable,'-I',__file__,'--repo',str(a.repo),'--output',str(root),'--phase','run'],check=True,capture_output=True,text=True)
value=json.loads(child.stdout);assert value['result']['ok'] and len(model.bodies)==2
initial=json.loads(model.bodies[0]['messages'][0]['content'])['knowledge'];assert initial['reason']=='knowledge-lifecycle-upgrade-required' and STATEMENT not in canonical_json(initial)
tool=json.loads(next(m['content'] for m in model.bodies[1]['messages'] if m['role']=='tool'))
leaked=STATEMENT in canonical_json(model.bodies[1])
if a.expected=='current':assert not leaked and tool['available'] is False and tool['partial'] and tool['reason']=='knowledge-lifecycle-upgrade-required'
else:assert leaked and tool['available'] and tool['context']['result']=='matches' and tool['context']['partial'] is False
for index,body in enumerate(model.bodies):assert digest(body)==value['run']['requests'][index]['input_hash']
assert hashlib.sha256((root/'.knowledge/store.sqlite3').read_bytes()).hexdigest()==before
store=Store(root);assert not store.status()['p1'] and store.context('ImprovedFeature')['claims'][0]['statement']==STATEMENT
(out/'provider-requests.json').write_text(json.dumps(model.bodies,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(out/'run.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
result={'status':'SAFE' if a.expected=='current' else 'REPRODUCED_LEAK','profile':'installed fresh-process read-only P4; HTTP provider double; real SQLite/journal','expected':a.expected,'requests':len(model.bodies),'initial_refusal':initial['reason'],'following_request_leaks_statement':leaked,'knowledge_tool_result':tool,'db_sha256_unchanged':before,'legacy_core_still_readable':True,'provider_request_hashes_match_journal':True,'installed':{'harness':harness.__file__,'knowledge':knowledge.__file__},'product_module_sha256':{name:hashlib.sha256((Path(harness.__file__).parent/name).read_bytes()).hexdigest() for name in ('tools.py','delivery.py','p4.py')}}
(out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='knowledge_tool_result'}))
