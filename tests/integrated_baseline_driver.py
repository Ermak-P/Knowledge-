"""Unchanged rc3 installed code, real effect counts, and final focused regressions."""
import argparse,contextlib,hashlib,io,json,subprocess,sys,tempfile,unittest
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--checkout',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output;sys.path.insert(0,str(a.checkout/'tests'))
 import knowledge,harness
 from harness.runtime import Journal
 from test_integrated_capture import CaptureIntegration
 from test_integrated_knowledge import KnowledgeIntegration
 from p2_fixtures import http_provider
 from test_p4 import Decisions
 from knowledge import cli,discovery
 assert knowledge.__version__==harness.__version__=='0.4.0rc3';assert Path(harness.__file__).is_relative_to(Path(sys.prefix));effects={}
 check=CaptureIntegration()
 with tempfile.TemporaryDirectory() as tmp,http_provider(d:=Decisions()) as endpoint:
  root,t=check.setup_project(tmp,endpoint);check.answer(check.invoke(root,'run',input=t,options=['--die','before-first-patch']),73);rid=Journal(root).runs()[0]['id'];before=check.effects(root,d,rid);answer=check.answer(check.invoke(root,'capture-retry',rid));after=check.effects(root,d,rid)
  effects['execution_replayed']=dict(http_before=before['http'],http_after=after['http'],additional_http=after['http']-before['http'],source_changed=before['source']!=after['source'],new_patch_actions=sum(x['tool']=='patch' for x in after['actions'].values())-sum(x['tool']=='patch' for x in before['actions'].values()),new_recipe_actions=sum(x['tool']=='recipe' for x in after['actions'].values())-sum(x['tool']=='recipe' for x in before['actions'].values()),result=answer)
  assert effects['execution_replayed']['additional_http']>0 and effects['execution_replayed']['source_changed']
 with tempfile.TemporaryDirectory() as tmp,http_provider(d:=Decisions()) as endpoint:
  root,t=check.setup_project(tmp,endpoint,'optional');initial=check.answer(check.invoke(root,'run',input=t,options=['--fail-submit']));before=Journal(root).outbox(initial['run_id']);retried=check.answer(check.invoke(root,'capture-retry',initial['run_id']));effects['optional_not_delivered']=dict(initial=initial,retried=retried,pending_outbox=len(before));assert retried['status']=='completed-degraded' and retried['capture']['state']=='pending'
 with tempfile.TemporaryDirectory() as tmp:
  root=KnowledgeIntegration().checkout(tmp,'crlf');snapshot=discovery.inventory(root);effects['crlf_clean_misclassified']=dict(git_status=subprocess.check_output(['git','-C',str(root),'status','--porcelain'],text=True),product_kind=snapshot['snapshot_kind'],dirty=snapshot['dirty'],raw_bytes=(root/'EM.cs').read_bytes().hex(),working_sha256=hashlib.sha256((root/'EM.cs').read_bytes()).hexdigest(),git_blob_sha256=hashlib.sha256(subprocess.check_output(['git','-C',str(root),'show','HEAD:EM.cs'])).hexdigest());assert not effects['crlf_clean_misclassified']['git_status'] and snapshot['dirty']
 with tempfile.TemporaryDirectory() as tmp:
  root=Path(tmp)/'eshop';subprocess.run(['git','clone','--quiet','--no-hardlinks','--local',str(a.checkout/'benchmarks/eShopOnWeb'),str(root)],check=True);real=discovery.extract;calls=[]
  def counted(*args,**kwargs):calls.append(args[1]);return real(*args,**kwargs)
  discovery.extract=counted;wire=io.StringIO();sys.argv=['knowledge','knowledge-init','--root',str(root),'--max-files','1']
  try:
   with contextlib.redirect_stdout(wire):code=cli.main()
  finally:discovery.extract=real
  (out/'public-init-baseline.log').write_text(wire.getvalue(),encoding='utf-8');result=json.loads(wire.getvalue());effects['public_init_hidden_extraction']=dict(command='knowledge-init --max-files 1',returncode=code,reported=result['work']['extracted_this_call'],actual=len(calls),paths=calls);assert code==0 and len(calls)>1
 suite=unittest.defaultTestLoader.discover(str(a.checkout/'tests'),pattern='test_integrated_*.py');result=unittest.TextTestRunner(verbosity=2).run(suite);assert not result.wasSuccessful(),'baseline unexpectedly fixed; inspect revisions'
 value=dict(status='REPRODUCED',product='0.4.0rc3',base_commit='4345352cb0fb8c20a19b51f9227fe91424c250de',installed_modules=[knowledge.__file__,harness.__file__],effects=effects,regressions=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),unexpected_pass=False))
 (out/'result.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');print(json.dumps(value))
if __name__=='__main__':main()
