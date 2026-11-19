"""AT contract: no process discovery, immutable authority, strict owned TRX."""
import copy,json,os,sys,tempfile,time,unittest,uuid
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as ET
from harness import testing,runtime
from harness.engine import start,resume
from harness.tools import Broker
from knowledge.project import Project
from knowledge.util import KnowledgeError,digest
from p2_fixtures import http_provider,final
from test_p4 import p4task

class AutomaticDiscovery(unittest.TestCase):
 def config(self,endpoint):
  return dict(version=2,provider=dict(endpoint=endpoint,model='synthetic',evidence='test-double'),capture='off',limits={},dotnet=sys.executable,recipes=dict(build=dict(kind='build',argv=[sys.executable,'-c','print("build")'],result=dict(format='exit',path=''),rerun_safe=True,env={})))
 def run_state(self,root,endpoint,count=1):
  for n in range(count):(root/('P'+str(n)+'Tests.csproj')).write_text('<Project/>',encoding='utf-8')
  (root/'Feature.cs').write_text('class Feature {}',encoding='utf-8');c=self.config(endpoint);runtime.configure(root,c);t=p4task();t['recipes']=['build'];r=start(root,t);j=runtime.Journal(root);return c,j,j.load(r['run_id'])
 def test_AT01_exact_names_case_suffix_and_readonly_inspection(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);names=['IpmAzureCommon.UnitTests.csproj','IpmAzureAutotests.csproj','FooTests.csproj','Foo.Tests.csproj','Foo.UnitTests.csproj','UPPERTESTS.CSPROJ']
   for n in names:(root/n).write_text('<Project/>')
   (root/'odd source Ω').mkdir();(root/'odd source Ω/OutsideTests.csproj').write_text('<Project/>')
   for n in ('TestSupport.csproj','FooTests.csproj.bak'):(root/n).write_text('<Project/>')
   for folder in ('tests','bin','obj','.git','.harness','.knowledge','packages'):
    (root/folder).mkdir();(root/folder/'Production.csproj').write_text('<Project/>')
    if folder!='tests':(root/folder/'RealTests.csproj').write_text('<Project/>')
   # Empty metadata placeholders are removed for Project's safety checks.
   with patch('subprocess.Popen',side_effect=AssertionError('inspection executed a process')):
    r=testing.discover(root)
   self.assertTrue(r['ok'],r);paths=[p['path'] for p in r['projects']];self.assertEqual(set(paths),set(names+['odd source Ω/OutsideTests.csproj','packages/RealTests.csproj']));self.assertEqual(paths,sorted(paths,key=lambda x:(x.casefold(),x)));self.assertEqual(r['count'],8);self.assertFalse((root/'.harness/runs.sqlite3').exists());self.assertEqual(r['identity'],testing.discover(root)['identity'])
 def test_AT08_links_hardlinks_case_collisions_are_explicit_errors(self):
  with tempfile.TemporaryDirectory() as tmp,tempfile.TemporaryDirectory() as external:
   root=Path(tmp);(Path(external)/'EscapeTests.csproj').write_text('<Project/>');(root/'linked').symlink_to(external,target_is_directory=True);(root/'LinkTests.csproj').symlink_to(Path(external)/'EscapeTests.csproj');r=testing.discover(root);self.assertFalse(r['ok']);self.assertFalse(r['projects']);self.assertTrue(r['errors'])
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'ATests.csproj').write_text('<Project/>');os.link(root/'ATests.csproj',root/'BTests.csproj');r=testing.discover(root);self.assertFalse(r['ok']);self.assertFalse(r['projects'])
  if os.name!='nt':
   with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);(root/'aTests.csproj').write_text('<Project/>');(root/'ATESTS.CSPROJ').write_text('<Project/>');r=testing.discover(root);self.assertFalse(r['ok']);self.assertEqual(r['errors'][0]['error'],'ambiguous-test-project-path')
 def test_AT02_new_schema_no_manual_test_and_explicit_legacy_migration(self):
  c=self.config('http://127.0.0.1/v1/chat/completions');self.assertEqual(runtime.validate_config(c),c);bad=copy.deepcopy(c);bad['recipes']['test']=dict(kind='test',argv=[sys.executable],result=dict(format='unittest',path=''),rerun_safe=False,env={})
  with self.assertRaisesRegex(KnowledgeError,'manual-test'):runtime.validate_config(bad)
  from harness.engine import task_shape
  t=p4task();t['recipes']=['build'];task_shape(t,c);t['version']=1;t.pop('items');t.pop('acceptance')
  with self.assertRaisesRegex(KnowledgeError,'require-task-v2'):task_shape(t,c)
  bad=copy.deepcopy(c);bad.pop('dotnet')
  with self.assertRaisesRegex(KnowledgeError,'missing-dotnet'):runtime.validate_config(bad)
 def test_AT06_new_run_inventory_and_resume_refuse_add_rename_remove(self):
  for change in ('add','rename','remove'):
   with self.subTest(change=change),tempfile.TemporaryDirectory() as tmp,http_provider(lambda b:final()) as endpoint:
    root=Path(tmp);c,j,r=self.run_state(root,endpoint);old=r['automatic_tests']['inventory']['identity'];p=root/'P0Tests.csproj'
    if change=='add':(root/'NewTests.csproj').write_text('<Project/>')
    elif change=='rename':p.rename(root/'RenamedTests.csproj')
    else:p.unlink()
    with self.assertRaisesRegex(KnowledgeError,'inventory-changed'):resume(root,r['id'])
    next_run=start(root,{k:v for k,v in r['task'].items() if k!='initial_source'});new=j.load(next_run['run_id']);self.assertNotEqual(new['automatic_tests']['inventory']['identity'],old);self.assertEqual(len(j.actions(r['id'])),0)
 def test_AT07_over_twenty_visible_with_budget_and_cancellation_not_success(self):
  for stop in ('budget','cancel'):
   with self.subTest(stop=stop),tempfile.TemporaryDirectory() as tmp,http_provider(lambda b:final()) as endpoint:
    root=Path(tmp);c,j,r=self.run_state(root,endpoint,23);self.assertEqual(r['automatic_tests']['inventory']['count'],23);self.assertEqual(len(c['recipes']),1)
    if stop=='budget':r['started']-=1000
    else:j.cancel(r['id'])
    with runtime.Lease(j) as lease:
     with self.assertRaisesRegex(KnowledgeError,'elapsed-budget|cancelled'):testing.verify(j,c,r,lease,'work',1)
    self.assertFalse(r['gates'][testing.GATE]['ok']);self.assertEqual(len(r['gates'][testing.GATE]['projects']),23);self.assertFalse(any(a.get('process_spec') for a in j.actions(r['id']).values()))
    self.assertEqual(testing.summary(r)['not_run'],23)
  # Exercise the complete scheduler beyond the user-recipe limit. This uses
  # synthetic receipts; the installed acceptance helper supplies real SDK/TRX proof.
  with tempfile.TemporaryDirectory() as tmp,http_provider(lambda b:final()) as endpoint:
   root=Path(tmp);c,j,r=self.run_state(root,endpoint,23);seen=[]
   with runtime.Lease(j) as lease:
    broker=Broker(j,c,r,lease)
    def execute(role,aid,name,args):
     recipe=testing.recipe_for(broker,args['name']);op=recipe['automatic'];seen.append((args['name'],op['project'],op['phase']))
     if op['phase']=='inspect':return dict(ok=True,properties=dict(TargetFramework='net10.0',TargetFrameworks='',AssemblyName='ExampleTests',TargetPath=str(root/'bin/ExampleTests.dll')))
     return dict(ok=True,counts=dict(executed=1,passed=1,failed=0,skipped=0))
    with patch.object(Broker,'execute',side_effect=execute):gate=testing.verify(j,c,r,lease,'work',2)
   self.assertTrue(gate['ok']);self.assertEqual(gate['counts']['executed'],23);self.assertEqual(len(seen),69);self.assertEqual(len(set(n for n,p,phase in seen)),69);self.assertEqual(len({p for n,p,phase in seen}),23);self.assertTrue(all(v['status']=='PASS' for v in gate['projects'].values()))
 def test_AT09_project_edit_authority_and_unknown_operation_cannot_expand(self):
  from harness.tools import sanitized_env
  with patch('harness.tools.system_environment',return_value={'PROGRAMFILES':'machine-folder'}),patch.dict(os.environ,{'UNRELATED_SECRET':'must-not-leak'},clear=True):
   env=sanitized_env({'PROGRAMFILES':'approved-folder'});self.assertEqual(env['PROGRAMFILES'],'approved-folder');self.assertNotIn('UNRELATED_SECRET',env)

  with tempfile.TemporaryDirectory() as tmp,http_provider(lambda b:final()) as endpoint:
   root=Path(tmp);c,j,r=self.run_state(root,endpoint)
   with runtime.Lease(j) as lease:
    b=Broker(j,c,r,lease);denied=b.execute('Coding','forbidden','patch',dict(files=[dict(path='NewTests.csproj',before=None,after='<Project/>')]))
    self.assertFalse(denied['ok']);self.assertEqual(denied['error'],'protected-build-policy')
    with self.assertRaisesRegex(KnowledgeError,'not-authorized'):testing.recipe_for(b,testing.PREFIX+'invented')
 def test_AT10_readonly_never_runs_automatic_build_or_test(self):
  with tempfile.TemporaryDirectory() as tmp,http_provider(lambda b:final()) as endpoint:
   root=Path(tmp);runtime.configure(root,self.config(endpoint));t=p4task();t.update(kind='read-only',writable=[],recipes=[]);r=start(root,t);self.assertTrue(r['ok'],r);j=runtime.Journal(root);self.assertNotIn('automatic_tests',j.load(r['run_id']));self.assertFalse(j.actions(r['run_id']))

class AutomaticTrx(unittest.TestCase):
 def report(self,root,**changes):
  now=time.time();target=root/'bin/ExampleTests.dll';target.parent.mkdir();target.write_bytes(b'synthetic unit-only assembly');p=root/'result.trx'
  doc=ET.Element('TestRun',id=str(uuid.uuid4()));ET.SubElement(doc,'Times',start=datetime.fromtimestamp(now-.1,timezone.utc).isoformat(),finish=datetime.fromtimestamp(now,timezone.utc).isoformat());summary=ET.SubElement(doc,'ResultSummary',outcome='Completed');ET.SubElement(summary,'Counters',total='1',executed='1',passed='1',failed='0',notExecuted='0');results=ET.SubElement(doc,'Results');row=ET.SubElement(results,'UnitTestResult',testId='test',executionId='execution',outcome='Passed');definitions=ET.SubElement(doc,'TestDefinitions');definition=ET.SubElement(definitions,'UnitTest',id='test',storage=str(target));ET.SubElement(definition,'TestMethod',codeBase=str(target));ET.ElementTree(doc).write(p);return p,dict(process_started=now-.5,process_finished=now+.5),target,doc
 def test_AT05_zero_failed_skipped_malformed_stale_missing_foreign_trx(self):
  for case in ('good','zero','failed','skip','malformed','stale','missing','foreign','mismatched-count'):
   with self.subTest(case=case),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);p,a,target,doc=self.report(root);counter=doc.find('.//Counters')
    if case=='zero':counter.attrib.update(total='0',executed='0',passed='0');doc.find('Results').clear()
    if case=='failed':counter.attrib.update(passed='0',failed='1');doc.find('Results')[0].set('outcome','Failed');doc.find('ResultSummary').set('outcome','Failed')
    if case=='skip':counter.attrib.update(total='2',notExecuted='1')
    if case=='stale':a['process_started']+=100
    if case=='foreign':doc.find('.//UnitTest').set('storage',str(root/'OtherTests.dll'))
    if case=='mismatched-count':counter.attrib.update(executed='2',passed='2',total='2')
    ET.ElementTree(doc).write(p)
    if case=='malformed':p.write_text('<bad')
    if case=='missing':p.unlink()
    if case in ('malformed','stale','missing','foreign'):
     with self.assertRaises((KnowledgeError,ET.ParseError)):testing.trx_result(p,a,str(target),root)
    else:self.assertEqual(testing.trx_result(p,a,str(target),root)['ok'],case=='good')

class AutomaticAuthority(unittest.TestCase):
 def test_AT05_empty_inventory_is_explicit_failure_without_processes(self):
  with tempfile.TemporaryDirectory() as tmp,http_provider(lambda b:final()) as endpoint:
   c,j,r=AutomaticDiscovery().run_state(Path(tmp),endpoint,0)
   with runtime.Lease(j) as lease:gate=testing.verify(j,c,r,lease,'work',1)
   self.assertFalse(gate['ok']);self.assertEqual(gate['output'],'no-test-projects-discovered');self.assertFalse(j.actions(r['id']))
 def test_AT09_live_driver_is_busy_and_format_three_requires_authority(self):
  with tempfile.TemporaryDirectory() as tmp,http_provider(lambda b:final()) as endpoint:
   c,j,r=AutomaticDiscovery().run_state(Path(tmp),endpoint);self.assertEqual(r['version'],3)
   from harness.platform import process_info
   r['automatic_tests']['driver_owner']=process_info(os.getpid());j.save(r)
   with runtime.Lease(j):
    with self.assertRaisesRegex(KnowledgeError,'project-writer-busy'):resume(tmp,r['id'])
   r['automatic_tests'].pop('driver_owner');j.save(r)
   from knowledge.execution_lock import ExecutionLock
   controller=ExecutionLock(j.base/'automatic-driver.lock').acquire()
   try:
    with patch('harness.engine.stop_owned',side_effect=AssertionError('competing controller stopped live work')):
     with self.assertRaisesRegex(KnowledgeError,'project-writer-busy'):resume(tmp,r['id'])
   finally:controller.close()
   r.pop('automatic_tests');j.save(r)
   with self.assertRaisesRegex(KnowledgeError,'unsupported-automatic-test-state'):j.load(r['id'])

 def test_AT10_new_runner_and_inventory_survive_exact_backup_restore(self):
  from knowledge import maintenance as m
  with tempfile.TemporaryDirectory() as tmp,http_provider(lambda b:final()) as endpoint:
   base=Path(tmp);root=base/'project';root.mkdir();c,j,r=AutomaticDiscovery().run_state(root,endpoint)
   before=j.load(r['id']);plan=m.preview(root,'backup',base/'backup.zip');m.apply(root,plan['preview'],plan['fingerprint'])
   plan=m.preview(root,'restore',archive=base/'backup.zip',recovery=base/'replaced');m.apply(root,plan['preview'],plan['fingerprint'])
   self.assertEqual(runtime.Journal(root).load(r['id']),before);self.assertEqual(runtime.config(root),c)
