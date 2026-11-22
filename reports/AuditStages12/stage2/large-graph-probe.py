import sys,json,tempfile,hashlib,subprocess
from pathlib import Path
sys.path.insert(0,'/workspace/Knowledge-/tests')
from fixtures import addition
from test_p1 import upgraded,approve
from knowledge.util import canonical_json
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp);(root/'Fixture.cs').write_text('public class SyntheticGraph {}\n');store=upgraded(root);records={'claims':[],'evidence':[],'relationships':[]}
 names=['parent.'+str(i) for i in range(130)]
 for name in names+['graph.child']:
  value=addition(name,('quasartopology — проверенная структура depends on supporting parents.' if name=='graph.child' else 'Supporting parent statement '+name))
  value['records']['evidence'][0]['content_hash']='sha256:'+hashlib.sha256((root/'Fixture.cs').read_bytes()).hexdigest()
  if name=='graph.child':value['records']['claims'][0]['depends_on']=names
  for group in records:records[group]+=value['records'][group]
 records['relationships']=[{'id':'edge.'+name,'type':'depends_on','from':'graph.child','to':name,'provenance':{'actor':'synthetic','method':'reviewed graph'}} for name in names]
 store.submit({'version':1,'operation':'add','records':records});approve(store)
 result=store.context('quasartopology',max_items=100,max_bytes=1000000)
 assert len(result['claims'])==100 and len(result['dependencies']['references'])==128 and result['dependencies']['omitted']==2 and result['partial']
 assert result['claims'][0]['depends_on']==names
 rows=[]
 for cap in (256,400,1000,32000):
  child=subprocess.run([sys.executable,'-I','-m','knowledge.cli','context','--root',str(root),'--task','quasartopology','--max-items','100','--max-bytes',str(cap)],capture_output=True,timeout=15)
  assert child.returncode==0,child.stderr;value=json.loads(child.stdout);assert len(child.stdout)<=cap
  if 'truncation' in value:assert value['truncation']['returned']==len(value['claims']) and value['truncation']['dropped']==value['truncation']['candidates']-len(value['claims'])
  assert value['partial'];rows.append({'cap':cap,'actual_cli_bytes':len(child.stdout),'returned':len(value['claims']),'truncation':value.get('truncation'),'result':value['result']})
 print(json.dumps({'status':'PASS','kind':'installed API/CLI; 131 reviewed claims, 130 dependency edges, UTF-8','full':{'claims':len(result['claims']),'references':len(result['dependencies']['references']),'omitted_references':result['dependencies']['omitted'],'truncation':result['truncation']},'budgets':rows},indent=2))
