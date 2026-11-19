"""Delivery-only CLI effects, durable identities and configured snapshot boundaries."""
import copy,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from harness.runtime import configure,Journal,Lease
from knowledge.store import Store
from knowledge.util import digest
from p2_fixtures import project,configuration,http_provider
from test_p4 import Decisions,p4task
WORKER=Path(__file__).with_name('integrated_cli_worker.py')
class CaptureIntegration(unittest.TestCase):
 def invoke(self,root,command,rid=None,*,options=(),input=None):
  argv=[sys.executable,'-I','-X','utf8','-B',str(WORKER),*options,'--',command,'--root',str(root)]
  if rid:argv+=['--run-id',rid]
  if input:argv+=['--input',str(input)]
  return subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 def answer(self,p,expected=0):
  out,err=p.communicate(timeout=40);self.assertEqual(p.returncode,expected,(out.decode(errors='replace'),err.decode(errors='replace')));return json.loads(out) if out else None
 def setup_project(self,tmp,endpoint,policy='required',large=False):
  root=project(Path(tmp)/'project');c=configuration(endpoint,**({'file_bytes':2000000} if large else {}));c['capture']=policy
  if large:(root/'Unrelated.txt').write_bytes(b'x'*1100000)
  configure(root,c,True);taskfile=Path(tmp)/'task.json';taskfile.write_text(json.dumps(p4task()));return root,taskfile
 def effects(self,root,d,rid):
  j=Journal(root);return dict(http=len(d.bodies),source=digest(__import__('harness.runtime',fromlist=['source_snapshot']).source_snapshot(j.project,2000000)),actions=j.actions(rid),requests=j.load(rid)['requests'])
 def test_capture_retry_refuses_execution_without_http_edits_or_processes(self):
  with tempfile.TemporaryDirectory() as tmp,http_provider(d:=Decisions()) as endpoint:
   root,t=self.setup_project(tmp,endpoint);self.answer(self.invoke(root,'run',input=t,options=['--die','before-first-patch']),73);j=Journal(root);rid=j.runs()[0]['id'];before=self.effects(root,d,rid);self.assertFalse(any(a['tool']=='patch' for a in before['actions'].values()))
   refused=self.answer(self.invoke(root,'capture-retry',rid),1);self.assertEqual(refused['error'],'capture-retry-ineligible');self.assertEqual(self.effects(root,d,rid),before)
   self.assertTrue(self.answer(self.invoke(root,'resume',rid))['ok']);self.assertEqual((root/'Feature.cs').read_text(),'public class ImprovedFeature {}\n');self.assertGreater(len(d.bodies),before['http'])
 def test_required_and_optional_delivery_retry_preserve_original_candidate(self):
  for policy in ('required','optional'):
   with self.subTest(policy=policy),tempfile.TemporaryDirectory() as tmp,http_provider(d:=Decisions()) as endpoint:
    root,t=self.setup_project(tmp,endpoint,policy);initial=self.answer(self.invoke(root,'run',input=t,options=['--fail-submit']),1 if policy=='required' else 0);self.assertEqual(initial['status'],'awaiting-capture' if policy=='required' else 'completed-degraded');j=Journal(root);rid=initial['run_id'];r=copy.deepcopy(j.load(rid));outbox=j.outbox(rid);self.assertEqual(len(outbox),1);identifier,item=next(iter(outbox.items()));self.assertEqual(item['state'],'pending');self.assertFalse(Store(root).status()['queue']);before=self.effects(root,d,rid)
    done=self.answer(self.invoke(root,'capture-retry',rid));self.assertEqual(done['status'],'completed');self.assertEqual(done['capture']['state'],'delivered');self.assertEqual(self.effects(root,d,rid),before)
    actual=j.outbox(rid)[identifier]
    for key in ('event','at','decision','run','coding_actions'):self.assertEqual(actual[key],item[key])
    self.assertEqual(actual['receipt']['candidate'],digest(item['decision']['payload']));self.assertEqual(len(Store(root).status()['queue']),1)
    for key in ('capture_time','capture_event','final_source','p4'):self.assertEqual(j.load(rid)[key],r[key])
    completed=copy.deepcopy(j.load(rid));self.answer(self.invoke(root,'capture-retry',rid));self.assertEqual(j.load(rid),completed);self.assertEqual(j.outbox(rid)[identifier],actual);self.assertEqual(self.effects(root,d,rid),before)
 def test_delivery_after_acceptance_death_and_competing_cli_retries_converges(self):
  with tempfile.TemporaryDirectory() as tmp,http_provider(d:=Decisions()) as endpoint:
   root,t=self.setup_project(tmp,endpoint);self.answer(self.invoke(root,'run',input=t,options=['--die','capture-after-submit']),73);j=Journal(root);rid=j.runs()[0]['id'];before=self.effects(root,d,rid);original=j.outbox(rid);self.assertEqual(len(Store(root).status()['queue']),1)
   children=[self.invoke(root,'capture-retry',rid) for _ in range(2)]
   for child in children:
    out,err=child.communicate(timeout=40);self.assertIn(child.returncode,(0,1));value=json.loads(out);self.assertTrue(value['ok'] or value['error']=='project-writer-busy',value)
   self.answer(self.invoke(root,'capture-retry',rid));self.assertEqual(self.effects(root,d,rid),before);self.assertEqual(len(Store(root).status()['queue']),1);self.assertEqual(set(j.outbox(rid)),set(original))
   for k,old in original.items():
    now=j.outbox(rid)[k];self.assertEqual(now['state'],'delivered');self.assertEqual(now['decision'],old['decision']);self.assertEqual(now['receipt']['candidate'],digest(old['decision']['payload']));self.assertEqual(now['event'],old['event']);self.assertEqual(now['at'],old['at'])
 def test_configured_file_limit_applies_through_capture_finalization_and_retry(self):
  for failure in (False,True):
   with self.subTest(failure=failure),tempfile.TemporaryDirectory() as tmp,http_provider(d:=Decisions()) as endpoint:
    root,t=self.setup_project(tmp,endpoint,large=True);initial=self.answer(self.invoke(root,'run',input=t,options=['--fail-submit'] if failure else []),1 if failure else 0);self.assertEqual(initial['execution'],'passed');self.assertEqual(initial['capture']['state'],'pending' if failure else 'delivered')
    if failure:self.assertEqual(self.answer(self.invoke(root,'capture-retry',initial['run_id']))['status'],'completed')
    self.assertEqual(len(Store(root).status()['queue']),1);self.assertEqual((root/'Unrelated.txt').stat().st_size,1100000)
  with tempfile.TemporaryDirectory() as tmp,http_provider(d:=Decisions()) as endpoint:
   root,t=self.setup_project(tmp,endpoint,large=True);(root/'Unrelated.txt').write_bytes(b'x'*2000001);refused=self.answer(self.invoke(root,'run',input=t),1);self.assertEqual(refused['error'],'source-file-too-large');self.assertFalse(d.bodies)
 def test_delivery_retry_obeys_lease_and_bound_source_configuration(self):
  with tempfile.TemporaryDirectory() as tmp,http_provider(d:=Decisions()) as endpoint:
   root,t=self.setup_project(tmp,endpoint);initial=self.answer(self.invoke(root,'run',input=t,options=['--fail-submit']),1);rid=initial['run_id'];j=Journal(root);before=self.effects(root,d,rid);outbox=j.outbox(rid)
   with Lease(j):self.assertEqual(self.answer(self.invoke(root,'capture-retry',rid),1)['error'],'project-writer-busy')
   self.assertEqual(j.outbox(rid),outbox);source=(root/'Feature.cs').read_bytes();(root/'Feature.cs').write_bytes(source+b'// drift\n');self.assertEqual(self.answer(self.invoke(root,'capture-retry',rid),1)['error'],'final-source-changed');self.assertEqual(j.outbox(rid),outbox);self.assertEqual(self.answer(self.invoke(root,'resume',rid),1)['error'],'final-source-changed');self.assertEqual(j.outbox(rid),outbox);(root/'Feature.cs').write_bytes(source)
   from harness.runtime import config
   original=config(root);changed=copy.deepcopy(original);changed['limits']['file_bytes']=2000000;configure(root,changed);self.assertEqual(self.answer(self.invoke(root,'capture-retry',rid),1)['error'],'configuration-changed-revalidation-required');configure(root,original);self.assertEqual(self.effects(root,d,rid),before);self.answer(self.invoke(root,'capture-retry',rid));self.assertEqual(self.effects(root,d,rid),before)
 def test_resume_uses_configured_file_limit_after_saved_response(self):
  with tempfile.TemporaryDirectory() as tmp,http_provider(d:=Decisions()) as endpoint:
   root,t=self.setup_project(tmp,endpoint,large=True);self.answer(self.invoke(root,'run',input=t,options=['--die','before-first-patch']),73);rid=Journal(root).runs()[0]['id'];done=self.answer(self.invoke(root,'resume',rid));self.assertEqual(done['capture']['state'],'delivered');self.assertEqual((root/'Unrelated.txt').stat().st_size,1100000)
