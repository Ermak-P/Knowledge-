"""Synthetic HTTP decisions; real installed broker effects and process receipts."""
import tempfile,unittest
from pathlib import Path
from p2_fixtures import project,configuration,task,calls,final,http_provider
from harness.runtime import configure,Journal
from harness.engine import start,status,resume
from knowledge.util import loads,KnowledgeError

class Decisions:
 def __init__(self,broken=False):self.turns={};self.bodies=[];self.broken=broken
 def decide(self,b):
  self.bodies.append(b);s=loads(b['messages'][0]['content']);role=s['runtime_role'];n=self.turns.get(s['agent'],0);self.turns[s['agent']]=n+1
  if role=='Main':
   if any(i['status']!='done' for i in s['ledger']['items']):return calls(('delegate',{'role':'Coding','assignment':'Implement authorized objective'}))
   if 'review' not in s['progress']['gates']:return calls(('delegate',{'role':'Reviewing','assignment':'Independently inspect final source and evidence'}))
   return final()
  if role=='Coding':
   if n==0:return calls(('read',{'path':'Feature.cs'}))
   if n==1:
    tools=[loads(m['content']) for m in b['messages'] if m['role']=='tool'];return calls(('patch',{'files':[{'path':'Feature.cs','before':tools[-1]['sha256'],'after':'public class '+('Broken' if self.broken else 'Improved')+'Feature {}\n'}]}))
   return final()
  if role=='Reviewing':
   if n==0:return calls(('read',{'path':'Feature.cs'}))
   if n==1:
    tools=[loads(m['content']) for m in b['messages'] if m['role']=='tool'];good=tools[-1].get('text')=='public class ImprovedFeature {}\n';return calls(('review',{'verdict':'approve' if good else 'reject','findings':[] if good else ['Unexpected final source']}))
   return final()
  return final('Environment/code diagnosis: fixture expects ImprovedFeature.')

def p4task():
 t=task();t.update(version=2,acceptance=['Preserve exact expected ImprovedFeature source.'],items=[]);return t

class P4Tests(unittest.TestCase):
 def run_case(self,d,t=None,**limits):
  with tempfile.TemporaryDirectory() as tmp,http_provider(d) as endpoint:
   root=project(tmp);configure(root,configuration(endpoint,**limits),True);r=start(root,t or p4task());report=status(root,r['run_id']);return r,report
 def test_real_pipeline_and_no_attendance(self):
  d=Decisions();r,s=self.run_case(d);self.assertTrue(r['ok'],r)
  self.assertEqual({x['role'] for x in s['run']['agents']},{'Main','Coding','Reviewing'})
  self.assertEqual(len(s['run']['p4']['verifiers']),2)
  self.assertTrue(all(g['ok'] for g in s['run']['gates'].values()))
 def test_sequential_fresh_items_final_gates(self):
  t=p4task();t['items']=[dict(id=n,objective='Keep ImprovedFeature correct',depends=[] if n=='one' else ['one'],writable=['Feature.cs']) for n in ('one','two')]
  r,s=self.run_case(Decisions(),t);self.assertTrue(r['ok'],r)
  items=s['run']['p4']['items'];self.assertNotEqual(items[0]['epochs'][0],items[1]['epochs'][0]);self.assertEqual(len(s['run']['p4']['verifiers']),4)
 def test_scope_and_cycle_rejected_before_http(self):
  for field,value in [('writable',['outside.cs']),('depends',['later'])]:
   t=p4task();t['items']=[dict(id='one',objective='work',depends=[],writable=['Feature.cs'])];t['items'][0][field]=value
   d=Decisions()
   with self.assertRaises(KnowledgeError):self.run_case(d,t)
   self.assertEqual(d.bodies,[])
 def test_oversized_irreducible_no_call(self):
  t=p4task();t['goal']='X'*9000;d=Decisions();r,s=self.run_case(d,t,context_bytes=4096);self.assertEqual(r['error'],'split-required');self.assertEqual(d.bodies,[])
 def test_finite_real_failed_checks(self):
  r,s=self.run_case(Decisions(True));self.assertFalse(r['ok']);self.assertEqual(r['error'],'repair-exhausted');self.assertEqual(s['run']['p4']['items'][0]['attempts'],3)
 def test_checkpoint_and_receipt_recovery(self):
  from unittest.mock import patch
  from harness import runtime
  class Crash(Exception):pass
  for phase in ('edit-file-written','p4-verifier-receipt'):
   with self.subTest(phase=phase),tempfile.TemporaryDirectory() as tmp,http_provider(Decisions()) as endpoint:
    root=project(tmp);configure(root,configuration(endpoint),True)
    def crash(p):
     if p==phase:raise Crash()
    with patch.object(runtime,'fault',side_effect=crash):
     with self.assertRaises(Crash):start(root,p4task())
    j=Journal(root);r=j.runs()[0];self.assertTrue(resume(root,r['id'])['ok']);actions=j.actions(r['id']);self.assertEqual(len([a for a in actions.values() if a['tool']=='recipe']),2)
 def test_unknown_provider_never_replayed(self):
  from unittest.mock import patch
  from harness import runtime
  class Crash(Exception):pass
  with tempfile.TemporaryDirectory() as tmp,http_provider(Decisions()) as endpoint:
   root=project(tmp);configure(root,configuration(endpoint),True)
   def crash(p):
    if p=='provider-intent':raise Crash()
   with patch.object(runtime,'fault',side_effect=crash):
    with self.assertRaises(Crash):start(root,p4task())
   rid=Journal(root).runs()[0]['id'];r=resume(root,rid);self.assertFalse(r['ok']);self.assertEqual(r['error'],'provider-outcome-unknown-manual-retry-required');self.assertEqual(len(Journal(root).load(rid)['requests']),1)
 def test_rotation_preserves_early_requirement(self):
  class Long(Decisions):
   def __init__(self):super().__init__();self.total=0
   def decide(self,b):
    s=loads(b['messages'][0]['content'])
    if s['runtime_role']=='Coding':
     self.assertion=s['acceptance'];self.total+=1
     if self.total<=5:return calls(('read',{'path':'Feature.cs'}))
    return super().decide(b)
  d=Long();r,s=self.run_case(d);self.assertTrue(r['ok'],r);self.assertGreater(s['run']['p4']['rotations'],0);self.assertEqual(d.assertion,p4task()['acceptance']);self.assertTrue(all(q['input_bytes']<=24000 for q in s['run']['requests']))
 def test_reviewer_rejection_cannot_complete(self):
  class Reject(Decisions):
   def decide(self,b):
    s=loads(b['messages'][0]['content'])
    if s['runtime_role']=='Reviewing':
     n=self.turns.get(s['agent'],0);self.turns[s['agent']]=n+1
     return calls(('review',{'verdict':'reject','findings':['Missing criterion']})) if n==0 else final()
    return super().decide(b)
  r,s=self.run_case(Reject());self.assertFalse(r['ok']);self.assertEqual(s['run']['p4']['items'][0]['attempts'],3)
 def test_plan_proposal_is_validated(self):
  from harness.p4 import propose,initialize
  t=p4task();r={'task':t};initialize(r)
  c=configuration('http://127.0.0.1/v1/chat/completions')
  with self.assertRaises(KnowledgeError):propose(r,c,{'items':[dict(id='bad',objective='escape',depends=[],writable=['outside.cs'])]})
  propose(r,c,{'items':[dict(id='one',objective='work',depends=[],writable=['Feature.cs'])]})
  self.assertEqual(t,p4task())
  with self.assertRaises(KnowledgeError):propose(r,c,{'items':[]})
 def test_fake_summary_and_zero_tests_do_not_pass(self):
  r,s=self.run_case(lambda b:final('Build/test/review passed'));self.assertFalse(r['ok'])
  with tempfile.TemporaryDirectory() as tmp,http_provider(Decisions()) as endpoint:
   root=project(tmp);(root/'test_feature.py').write_text('import unittest\nunittest.main()\n');configure(root,configuration(endpoint),True);r=start(root,p4task());self.assertFalse(r['ok']);self.assertEqual(r['error'],'repair-exhausted')
 def test_read_only_has_no_irrelevant_checks(self):
  t=p4task();t.update(kind='read-only',writable=[],recipes=[])
  r,s=self.run_case(lambda b:final('Read-only analysis complete'),t);self.assertTrue(r['ok'],r);self.assertEqual(len(s['actions']),0)
 def test_owned_artifact_range_recovers_real_log(self):
  from harness.tools import Broker
  from harness.runtime import Lease,config
  with tempfile.TemporaryDirectory() as tmp,http_provider(Decisions()) as endpoint:
   root=project(tmp);configure(root,configuration(endpoint),True);r=start(root,p4task());j=Journal(root);run=j.load(r['run_id']);aid=run['p4']['verifiers'][0]['action']
   with Lease(j) as lease:
    broker=Broker(j,config(root),run,lease);answer=broker.execute('Reviewing','range-read','artifact',dict(action=aid,offset=0,limit=40));self.assertIn('synthetic lexical build',answer['log_excerpt']);self.assertEqual(len(answer['log_sha256']),64)
    denied=broker.execute('Reviewing','forged-read','artifact',dict(action='unknown-action',offset=0,limit=40));self.assertFalse(denied['ok'])
 def test_p4_companion_crossing_rejects_before_effect(self):
  from test_p3_companion_review import fixture,mutate
  from harness import companion,engine
  from harness.runtime import Lease as ActualLease
  from unittest.mock import patch
  for kind in ('configuration','host','writable','recipes','enrollment','identity','runtime','root','version'):
   with self.subTest(kind=kind),fixture(initial=p4task()) as (root,provider):
    class ScheduledLease(ActualLease):
     def __enter__(self):
      mutate(root,kind)
      return super().__enter__()
    with patch.object(engine,'Lease',ScheduledLease):
     with self.assertRaises(KnowledgeError):companion.run_task(root,'approved_task')
    self.assertEqual(provider.requests,[]);self.assertEqual(Journal(root).runs(),[])
 def test_noise_does_not_escape_finite_repair(self):
  import sys
  with tempfile.TemporaryDirectory() as tmp,http_provider(Decisions(True)) as endpoint:
   root=project(tmp);c=configuration(endpoint)
   c['recipes']['build']['argv']=[sys.executable,'-c','import time;print("failure timestamp",time.time());raise SystemExit(1)']
   configure(root,c,True);r=start(root,p4task());run=Journal(root).load(r['run_id']);self.assertEqual(r['error'],'repair-exhausted');self.assertEqual(len(run['p4']['cycles']),3);self.assertEqual(run['p4']['diagnoses'],1)
 def test_empty_test_report_never_passes(self):
  import sys
  with tempfile.TemporaryDirectory() as tmp,http_provider(Decisions()) as endpoint:
   root=project(tmp);c=configuration(endpoint);c['recipes']['test']['argv']=[sys.executable,'-c','print("Ran 0 tests\\n\\nOK")']
   configure(root,c,True);r=start(root,p4task());self.assertFalse(r['ok']);run=Journal(root).load(r['run_id']);self.assertFalse(run['gates']['test']['ok'])
 def test_checkpoint_interruption_reconstructs_without_replaying_edit(self):
  from unittest.mock import patch
  from harness import runtime
  class Crash(Exception):pass
  class Long(Decisions):
   def __init__(self):super().__init__();self.count=0
   def decide(self,b):
    s=loads(b['messages'][0]['content'])
    if s['runtime_role']=='Coding':
     self.count+=1
     if self.count<=5:return calls(('read',{'path':'Feature.cs'}))
    return super().decide(b)
  d=Long()
  with tempfile.TemporaryDirectory() as tmp,http_provider(d) as endpoint:
   root=project(tmp);configure(root,configuration(endpoint),True)
   def crash(p):
    if p=='p4-checkpoint':raise Crash()
   with patch.object(runtime,'fault',side_effect=crash):
    with self.assertRaises(Crash):start(root,p4task())
   j=Journal(root);rid=j.runs()[0]['id'];self.assertTrue(resume(root,rid)['ok']);self.assertEqual(sum(a['tool']=='patch' for a in j.actions(rid).values()),1)
