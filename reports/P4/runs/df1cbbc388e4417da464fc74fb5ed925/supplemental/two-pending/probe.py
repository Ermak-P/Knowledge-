"""Supplemental public-CLI proof: two committed tasks pending before one approval."""
import hashlib,json,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path('/workspace/Knowledge-');sys.path.insert(0,str(ROOT/'tests'))
from p2_fixtures import project,configuration,http_provider,FixtureProvider,task
from test_p1 import git
from test_integrated_knowledge import KnowledgeIntegration
from knowledge.store import Store
from knowledge import discovery, lifecycle
import harness,knowledge
OUT=Path(__file__).parent

def main():
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();assert head=='72c46b846086ef9a31275193934b1c25d70f5b6b'
 for package in ('knowledge','harness'):
  module=__import__(package);installed=Path(module.__file__).parent
  for p in (ROOT/'packages'/package/'src'/package).rglob('*.py'):assert p.read_bytes()==(installed/p.relative_to(ROOT/'packages'/package/'src'/package)).read_bytes(),p
 rows=[]
 def cli(root,module,*args):
  p=subprocess.run([sys.executable,'-I','-X','utf8','-B','-m',module,*args,'--root',str(root)],capture_output=True,timeout=45);assert p.returncode==0,(p.stdout,p.stderr);return json.loads(p.stdout)
 with tempfile.TemporaryDirectory(prefix='two-pending-tasks-') as tmp:
  base=Path(tmp);root=KnowledgeIntegration().checkout(base/'project');project(root);(root/'Other.cs').write_bytes(b'public class InitialOther {}\n');git(root,'add','.');git(root,'commit','-m','Initial two-file fixture');old=[];saved_plan=None;unrelated=None
  for n,path,desired in ((0,'Feature.cs','public class ImprovedFeature {}\n'),(1,'Other.cs','public class ImprovedOther {}\n')):
   with http_provider(d:=FixtureProvider(path=path,desired=desired)) as endpoint:
    c=configuration(endpoint)
    if n:
     (root/'test_both.py').write_text('import unittest\nfrom pathlib import Path\nclass Both(unittest.TestCase):\n def test_both(self):\n  self.assertEqual(Path("Feature.cs").read_text(),"public class ImprovedFeature {}\\n")\n  self.assertEqual(Path("Other.cs").read_text(),"public class ImprovedOther {}\\n")\nif __name__=="__main__":unittest.main()\n',encoding='utf-8');c['recipes']['test']['argv']=[sys.executable,'test_both.py']
    cfile=base/'runner.json';cfile.write_text(json.dumps(c));tfile=base/'task.json';tfile.write_text(json.dumps(task(path)));cli(root,'harness.run_cli','configure','--input',str(cfile),'--init-knowledge');r=cli(root,'harness.run_cli','run','--input',str(tfile));assert r['ok'];s=Store(root);q=s.export()['queue'];old.append(next(x['id'] for x in q if x['id'] not in old and x['id']!=unrelated));report=cli(root,'harness.run_cli','status','--run-id',r['run_id']);assert len(d.requests)==report['metrics']['requests'];assert report['metrics']['process_attempts']==2
    if n==0:
     from fixtures import addition
     unrelated=s.submit(addition('synthetic.unrelated.pending'))['candidate'];saved_plan=s.prepare();assert saved_plan['ok']
    assert not s.export()['records']['claims'];rows.append(dict(path=path,http=len(d.requests),patches=sum(a['tool']=='patch' for a in report['actions'].values()),processes=report['metrics']['process_attempts'],candidate=old[-1]));git(root,'add','.');git(root,'commit','-m','Commit completed task '+str(n))
  scan=cli(root,'knowledge.cli','knowledge-candidates-update','--max-files','100');assert scan['complete'];fresh=cli(root,'knowledge.cli','knowledge-candidates-push');assert fresh['ok'] and unrelated in fresh['included'] and not set(old)&set(fresh['included']);assert not s.export()['records']['claims']
  try:s.apply(saved_plan['fingerprint'],saved_plan['fingerprint'])
  except Exception as e:stale=getattr(e,'code',type(e).__name__)
  else:raise AssertionError('Old approval remained usable')
  cli(root,'knowledge.cli','apply','--plan',fresh['fingerprint'],'--approve',fresh['fingerprint']);cli(root,'knowledge.cli','acknowledge','--plan',fresh['fingerprint']);queries=[]
  for subject in ('ImprovedFeature','ImprovedOther'):
   identifier=next(o['id'] for o in scan['observations'] if o['subject']==subject);q=cli(root,'knowledge.cli','lookup','--kind','claims','--id',identifier);assert q['record']['id']==identifier and q['revision']['lifecycle']=='active' and q['freshness']['trusted'];assert sum(c['id']==identifier for c in s.export()['records']['claims'])==1;queries.append(dict(id=identifier,active=True,trusted=True,canonical_occurrences=1))
  assert not cli(root,'knowledge.cli','knowledge-candidates-push')['included'];value=dict(status='PASS',implementation=head,product=harness.__version__,probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),rows=rows,canonical_before_approval=0,unrelated_pending_in_fresh_plan=True,old_approval_error=stale,refreshes=s.status()['candidate_refreshes'],queries=queries,next_plan_included=[])
 (OUT/'result.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value))
if __name__=='__main__':main()
