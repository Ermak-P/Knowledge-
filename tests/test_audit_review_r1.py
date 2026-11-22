"""Independent-review R1 boundaries: real CLI/SQLite/HTTP, labelled doubles."""
import hashlib,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from knowledge import operations as op,lifecycle as life
from knowledge.store import Store
from knowledge.util import KnowledgeError,canonical_json,digest
from harness.runtime import configure,Journal
from harness.host_ingress import read_session,session_path,write_session
from harness.instructions import execute_procedure
from harness.engine import start
from harness import delivery
from test_persistent_instructions import setup_fixture,ingress
from test_persistent_r1 import dependency
from test_persistent_reviewed import DockerContract
from test_persistent_semantics import local_normalizer,decision,template
from test_p4 import p4task,Decisions
from p2_fixtures import project,configuration,http_provider,calls,final,task
from fixtures import addition
from test_p1 import approve
from test_audit_stage2 import fact

CASES=[
 ('Remember Kafka: Do not automatically start the container. You may start container fixture.','You may start container fixture.'),
 ('Запомни Kafka: запрещено запускать контейнер. Разрешаю запуск контейнера fixture.','Разрешаю запуск контейнера fixture.'),
 ('Remember Kafka: You may start container fixture. Approval is required before startup.','You may start container fixture.'),
 ('Remember Kafka: You may start container fixture. Management signoff precedes launching.','You may start container fixture.'),
 ('Remember Kafka: You may start container fixture. An exception applies on maintenance days.','You may start container fixture.')]


def cli_ingress(root,text,policy,source='cli'):
 child=subprocess.run([sys.executable,'-I','-m','knowledge.cli','memory-ingest','--root',str(root)],
   input=json.dumps({'text':text,'message_id':source,'policy':policy}),capture_output=True,encoding='utf-8',timeout=15)
 if child.returncode:raise AssertionError(child.stdout+child.stderr)
 return json.loads(child.stdout)

class WholeSource(unittest.TestCase):
 def test_valid_template_grant_survives_resolved_host_and_cli_replay(self):
  text='Remember Kafka: You may start container fixture if stopped; never restart a running container.'
  with tempfile.TemporaryDirectory() as tmp,local_normalizer([
    decision(authorize_recovery=True,permission_quote='You may start container fixture if stopped')]) as normalizer:
   root,shared,cfg=setup_fixture(tmp);t=template();t['defaults'].update(container='fixture',port=19092)
   cfg['memory'].update(teaching_mode='local-model',normalizer=normalizer,procedure_templates=[t],allowed_templates=[t['id']],bindings=[{'aliases':['Kafka'],'trigger':{'tool':'dependency','name':'local_broker'},'template':t['id']}]);configure(root,cfg)
   saved=ingress(root,text);self.assertTrue(saved['recovery_authorized'])
   host=ingress(root,text);self.assertTrue(host['recovery_authorized']);self.assertEqual(host['revision'],saved['revision'])
   cli=cli_ingress(root,text,cfg['memory'],'teaching/m1');self.assertTrue(cli['recovery_authorized']);self.assertEqual(cli['revision'],saved['revision'])

 def test_positive_stopped_grant_and_ordinary_clarification_stay_usable(self):
  positive='Remember Kafka: You may start container fixture if stopped; never restart a running container.'
  with tempfile.TemporaryDirectory() as tmp,local_normalizer([
    decision(authorize_recovery=True,permission_quote='You may start container fixture if stopped'),
    decision(intent='update')]) as normalizer:
   root,shared,cfg=setup_fixture(tmp);p,b=dependency();cfg['memory'].update(teaching_mode='local-model',normalizer=normalizer,bindings=[b],allowed_procedures=[p]);configure(root,cfg)
   saved=ingress(root,positive);self.assertTrue(saved['recovery_authorized'])
   clarified=ingress(root,'Use the same container fixture.',message_id='clarify');self.assertEqual(clarified['id'],saved['id']);self.assertTrue(clarified['recovery_authorized'])
   record=op.OperationalStore(root,'project',shared).records()['records'][0]
   ready=DockerContract(root,ready=True);execute_procedure(ready,'ready',record,{'shared_root':str(shared)});self.assertFalse(ready.starts())
   stopped=DockerContract(root,after_start=True);execute_procedure(stopped,'stopped',record,{'shared_root':str(shared)});self.assertEqual(len(stopped.starts()),1)

 def test_historical_conditional_clear_receipt_is_sanitized(self):
  text='You may start services again. Approval is required before startup.'
  with tempfile.TemporaryDirectory() as tmp:
   root,shared,cfg=setup_fixture(tmp);p,b=dependency();cfg['memory'].update(bindings=[b],allowed_procedures=[p]);configure(root,cfg)
   saved=op.teach(root,text,{'type':'user-message','id':'old-clear'},shared=shared,binding=b,receipt_stage='binding',receipt_controls={'restriction':'clear-service-start-denial'})
   replay=cli_ingress(root,text,cfg['memory'],'old-clear');self.assertTrue(replay['duplicate']);self.assertIsNone(replay['restriction']);self.assertEqual(replay['revision'],saved['revision'])

 def test_review_and_unlisted_clauses_cannot_grant_through_public_ingress(self):
  for mode in ('catalog','local-model'):
   for boundary in ('host','cli'):
    for text,quote in CASES:
     with self.subTest(mode=mode,boundary=boundary,text=text),tempfile.TemporaryDirectory() as tmp,local_normalizer([
       decision(authorize_recovery=True,permission_quote=quote)]) as normalizer:
      root,shared,cfg=setup_fixture(tmp);p,b=dependency()
      cfg['memory'].update(teaching_mode=mode,normalizer=normalizer,bindings=[b],allowed_procedures=[p],requirements=[{'trigger':{'tool':'recipe','name':'test'},'dependency':'guard'}]);configure(root,cfg)
      receipt=ingress(root,text) if boundary=='host' else cli_ingress(root,text,cfg['memory'])
      self.assertTrue(receipt['saved'],receipt);record=op.OperationalStore(root,'project',shared).records()['records'][0]
      contract=DockerContract(root,after_start=True)
      try:execute_procedure(contract,'operation',record,{'shared_root':str(shared)})
      except KnowledgeError:pass
      self.assertEqual(len(contract.starts()),0);self.assertFalse(record['recovery_authorized']);self.assertEqual(record['original'],text)
      ready=DockerContract(root,ready=True);execute_procedure(ready,'ready',record,{'shared_root':str(shared)});self.assertFalse(ready.starts())

 def test_conditional_clear_keeps_denial_across_replay_restart_then_unconditional_clear(self):
  for conditional,positive in (
    ('You may start services again. Only after approval.','You may start services again.'),
    ('You may start services again. Approval is required before startup.','You may start services again.'),
    ('Разрешаю снова запуск сервисов. Требуется согласование перед запуском.','Разрешаю снова запуск сервисов.')):
   with self.subTest(conditional=conditional),tempfile.TemporaryDirectory() as tmp,local_normalizer([
     decision(intent='none',binding=None,current_start='deny',restriction_quote='Do not start services in this run.'),
     decision(intent='none',binding=None,current_start='clear-denial',restriction_quote=positive),
     decision(intent='none',binding=None,current_start='clear-denial',restriction_quote=positive)]) as normalizer:
    root,shared,cfg=setup_fixture(tmp);p,b=dependency();cfg['memory'].update(teaching_mode='local-model',normalizer=normalizer,bindings=[b],allowed_procedures=[p]);configure(root,cfg)
    saved=op.teach(root,'Operator-approved fixture startup.',{'type':'user-message','id':'operator'},shared=shared,binding=b,recovery_authorized=True)
    ingress(root,'Do not start services in this run.',message_id='deny')
    result=ingress(root,conditional,message_id='conditional');self.assertTrue(result['ok']);self.assertNotEqual(result.get('restriction'),'clear-service-start-denial')
    self.assertEqual(read_session(root,'teaching')['restrictions'],['no-service-start'])
    replay=ingress(root,conditional,message_id='conditional');self.assertTrue(replay['duplicate']);self.assertEqual(read_session(root,'teaching')['restrictions'],['no-service-start'])
    record=op.OperationalStore(root,'project',shared).records()['records'][0];self.assertEqual((record['id'],record['revision']),(saved['id'],1));self.assertTrue(record['recovery_authorized'])
    blocked=DockerContract(root,after_start=True);blocked.r['host_session']='teaching'
    with self.assertRaisesRegex(KnowledgeError,'current-service-start-denied'):execute_procedure(blocked,'blocked',record,{'shared_root':str(shared)})
    self.assertFalse(blocked.starts())
    cleared=ingress(root,positive,message_id='unconditional');self.assertEqual(cleared['restriction'],'clear-service-start-denial');self.assertEqual(read_session(root,'teaching')['restrictions'],[])
    ingress(root,conditional,message_id='conditional');self.assertEqual(read_session(root,'teaching')['restrictions'],[])
    allowed=DockerContract(root,after_start=True);allowed.r['host_session']='teaching';execute_procedure(allowed,'allowed',record,{'shared_root':str(shared)});self.assertEqual(len(allowed.starts()),1)

 def test_historical_weak_grant_replay_revalidates_without_normalizer(self):
  text,quote=CASES[2]
  for boundary in ('host','cli'):
   with self.subTest(boundary=boundary),tempfile.TemporaryDirectory() as tmp:
    root,shared,cfg=setup_fixture(tmp);p,b=dependency();cfg['memory'].update(teaching_mode='local-model',normalizer={'endpoint':'http://127.0.0.1:1/chat/completions','model':'absent','timeout':1},bindings=[b],allowed_procedures=[p]);configure(root,cfg)
    source='teaching/m1' if boundary=='host' else 'cli'
    # Seed precisely the unsafe historical natural-language record/receipt.
    old=op.teach(root,text,{'type':'user-message','id':source},shared=shared,binding=b,recovery_authorized=True,receipt_stage='binding',normalization={'method':'catalog'})
    if boundary=='host':
     path=session_path(root,'teaching');path.parent.mkdir(parents=True,exist_ok=True)
     write_session(path,{'version':2,'session':'teaching','sequence':1,'controls_sequence':1,'restrictions':['no-service-start'],'messages':{'m1':{'hash':digest(text),'sequence':1,'state':'resolved','config':digest(cfg),'record':{'id':old['id'],'scope':'project'}}}})
    replay=ingress(root,text) if boundary=='host' else cli_ingress(root,text,cfg['memory'])
    self.assertFalse(replay['recovery_authorized']);self.assertEqual(replay['id'],old['id']);self.assertEqual(replay['revision'],2)
    again=ingress(root,text) if boundary=='host' else cli_ingress(root,text,cfg['memory']);self.assertEqual(again['revision'],2)
    history=op.OperationalStore(root,'project',shared).history(old['id']);self.assertEqual(len(history),2);self.assertTrue(history[0]['recovery_authorized']);self.assertFalse(history[1]['recovery_authorized'])
    if boundary=='host':self.assertEqual(read_session(root,'teaching')['restrictions'],['no-service-start'])

class ToolProvider:
 def __init__(self,p4=True):self.bodies=[];self.turns={};self.p4=p4;self.base=Decisions();self.planned=False
 def decide(self,body):
  self.bodies.append(body);state=json.loads(body['messages'][0]['content']);agent=state['agent'];role=state['runtime_role'];n=self.turns.get(agent,0);self.turns[agent]=n+1
  if n==0:return calls(('knowledge',{'task':'ImprovedFeature'}))
  if self.p4:
   if role=='Main' and not self.planned:
    self.planned=True;return calls(('delegate',{'role':'Planning','assignment':'Read current approved architecture.'}))
   return self.base.decide(body)
  return final()

class CurrentKnowledge(unittest.TestCase):
 def test_fresh_process_resume_projects_cached_receipt_and_old_history(self):
  from unittest.mock import patch
  from harness import runtime,tools
  class Death(Exception):pass
  for boundary in ('receipt','history'):
   model=ToolProvider(p4=False)
   with self.subTest(boundary=boundary),tempfile.TemporaryDirectory() as tmp,http_provider(model) as endpoint:
    root=project(tmp);store=Store(root);store.init();statement='ImprovedFeature requires an unverified historical threshold.';store.submit(addition('legacy.feature',statement));approve(store)
    cfg=configuration(endpoint);cfg['capture']='off';configure(root,cfg,True);t=p4task();t.update(kind='read-only',writable=[],recipes=[])
    def crash(where):
     if where=='tool-receipt':raise Death()
    # Recreate an already committed receipt from the reviewed, weaker product.
    with patch.object(tools,'current_knowledge',side_effect=lambda value:value,create=True),patch.object(runtime,'fault',side_effect=crash),self.assertRaises(Death):start(root,t)
    journal=Journal(root);run=journal.runs()[0];first=run['requests'][0];action=next(a for a in journal.actions(run['id']).values() if a['tool']=='knowledge')
    self.assertIn(statement,canonical_json(action['result']))
    if boundary=='history':
     frame=run['frames'][-1];call=frame['pending']['tool_calls'][0]
     frame['history']=[[frame['pending'],{'role':'tool','tool_call_id':call['id'],'content':canonical_json(action['result'])}]]
     frame.update(pending=None,cursor=0,results=[]);journal.save(run)
    program='import sys,json;from harness.engine import resume;print(json.dumps(resume(sys.argv[1],sys.argv[2])))'
    child=subprocess.run([sys.executable,'-I','-c',program,str(root),run['id']],capture_output=True,encoding='utf-8',timeout=30)
    self.assertEqual(child.returncode,0,child.stderr);self.assertTrue(json.loads(child.stdout)['ok'])
    after=journal.load(run['id']);self.assertEqual(after['requests'][0],first);self.assertEqual(len(after['requests']),2)
    self.assertEqual(journal.action(run['id'],next(iter(journal.actions(run['id']))))['result'],action['result'])
    self.assertEqual(len(model.bodies),2);self.assertNotIn(statement,canonical_json(model.bodies[1]))
    payload=json.loads(next(m['content'] for m in model.bodies[1]['messages'] if m['role']=='tool'))
    self.assertEqual(payload['reason'],'knowledge-lifecycle-upgrade-required');self.assertTrue(payload['partial'])

 def test_p4_optional_tool_does_not_reverse_initial_legacy_refusal_in_any_role(self):
  model=ToolProvider()
  with tempfile.TemporaryDirectory() as tmp,http_provider(model) as endpoint:
   root=project(tmp);store=Store(root);store.init();statement='ImprovedFeature requires an unverified historical threshold.';store.submit(addition('legacy.feature',statement));approve(store)
   before=hashlib.sha256(store.path.read_bytes()).hexdigest();cfg=configuration(endpoint);cfg['capture']='off';configure(root,cfg,True)
   t=p4task();result=start(root,t);self.assertTrue(result['ok'],result)
   self.assertGreaterEqual(len(model.bodies),2)
   for body in model.bodies:
    self.assertNotIn(statement,canonical_json(body));state=json.loads(body['messages'][0]['content']);self.assertEqual(state['knowledge']['reason'],'knowledge-lifecycle-upgrade-required')
    knowledge_ids=set()
    for message in body['messages']:
     if message['role']=='assistant':knowledge_ids={c['id'] for c in message.get('tool_calls',[]) if c['function']['name']=='knowledge'}
     elif message['role']=='tool' and message['tool_call_id'] in knowledge_ids:
      value=json.loads(message['content']);self.assertEqual(value['reason'],'knowledge-lifecycle-upgrade-required');self.assertFalse(value['available']);self.assertTrue(value['partial'])
   self.assertEqual({json.loads(b['messages'][0]['content'])['runtime_role'] for b in model.bodies},{'Main','Coding','Planning','Reviewing'})
   run=Journal(root).load(result['run_id']);self.assertTrue(all(q['input_bytes']<=24000 for q in run['requests']))
   self.assertEqual(hashlib.sha256(store.path.read_bytes()).hexdigest(),before);self.assertFalse(store.status()['p1']);self.assertEqual(store.context('ImprovedFeature')['claims'][0]['statement'],statement)

 def test_fresh_p1_optional_tool_keeps_dependencies_and_diagnostics(self):
  model=ToolProvider()
  with tempfile.TemporaryDirectory() as tmp,http_provider(model) as endpoint:
   root=project(tmp);cfg=configuration(endpoint);cfg['capture']='off';configure(root,cfg,True);store=Store(root)
   fact(store,root,'current.parent','Approved supporting parent.')
   fact(store,root,'current.feature','ImprovedFeature uses the approved supporting parent.',['current.parent'])
   t=p4task();result=start(root,t);self.assertTrue(result['ok'],result)
   payloads=[json.loads(m['content']) for b in model.bodies for m in b['messages'] if m['role']=='tool' and 'context' in json.loads(m['content'])]
   self.assertTrue(payloads)
   for payload in payloads:
    claims=payload['context']['claims'];self.assertTrue(payload['available']);self.assertIn('current.feature',{c['id'] for c in claims});self.assertTrue(all(c['revision']==1 and c['current']['freshness']['trusted'] for c in claims));self.assertIn('diagnostics',payload['context'])
    child=next(c for c in claims if c['id']=='current.feature');self.assertEqual(child['depends_on'],['current.parent'])

 def test_task_v1_http_and_core_legacy_reads_remain_available(self):
  model=ToolProvider(p4=False)
  with tempfile.TemporaryDirectory() as tmp,http_provider(model) as endpoint:
   root=project(tmp);store=Store(root);store.init();statement='ImprovedFeature retains the legacy core read contract.';store.submit(addition('legacy.feature',statement));approve(store)
   cfg=configuration(endpoint);cfg['capture']='off';configure(root,cfg,True);result=start(root,task(kind='read-only'));self.assertTrue(result['ok'],result)
   self.assertTrue(any(statement in canonical_json(b) for b in model.bodies));self.assertFalse(store.status()['p1'])

if __name__=='__main__':unittest.main()
