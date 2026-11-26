from contextlib import closing
import tempfile
from pathlib import Path
import unittest
from harness.runtime import configure
from harness.engine import start,status
from p2_fixtures import project,configuration,task,http_provider,FixtureProvider


class RunnerTests(unittest.TestCase):
    def test_real_http_execution_roles_gates_capture(self):
        with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider()) as endpoint:
            root=project(tmp);configure(root,configuration(endpoint),True)
            result=start(root,task());self.assertEqual(result['status'],'completed',result)
            report=status(root,result['run_id']);self.assertEqual(report['run']['execution'],'passed')
            self.assertEqual({r['role'] for r in report['run']['agents']},{'Main','Planning','Coding','Building','Testing','Reviewing'})
            self.assertTrue(report['outbox']);self.assertTrue(all(v['state']=='delivered' for v in report['outbox'].values()))
            from knowledge.store import Store
            self.assertFalse(Store(root).export()['records']['claims']);self.assertTrue(Store(root).status()['queue'])
            self.assertEqual(report['metrics']['reported_tokens'],18*report['metrics']['requests'])
            self.assertEqual(report['metrics']['unknown_usage_requests'],0)

    def test_actual_failure_repair(self):
        with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider(repair=True)) as endpoint:
            root=project(tmp);configure(root,configuration(endpoint),True);result=start(root,task())
            self.assertEqual(result['status'],'completed',result)
            report=status(root,result['run_id'])
            tests=[a['result'] for a in report['actions'].values() if a['tool']=='recipe' and a['args']['name']=='test']
            self.assertTrue(any(not r['ok'] for r in tests));self.assertTrue(any(r['ok'] for r in tests))

    def test_permissions_and_review_failure_prevent_false_success(self):
        for scenario in (FixtureProvider(deny=True),FixtureProvider(review_reject=True)):
            with self.subTest(scenario=scenario),tempfile.TemporaryDirectory() as tmp,http_provider(scenario) as endpoint:
                root=project(tmp);configure(root,configuration(endpoint),True);result=start(root,task())
                self.assertFalse(result['ok']);report=status(root,result['run_id'])
                if scenario.deny:
                    errors=[event.get('error') for event in report['events'] if event['kind']=='tool-denied']
                    self.assertIn('role-tool-denied',errors)
                    self.assertFalse((root.parent/'outside.cs').exists())
                    self.assertEqual((root/'Feature.cs').read_text(),'public class InitialFeature {}\n')
                else:self.assertEqual(report['run']['gates']['review']['verdict'],'reject')

    def test_readonly_absence_and_legacy_consumer_are_explicit(self):
        from harness.consumer import context
        with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider()) as endpoint:
            root=project(tmp);configure(root,configuration(endpoint),False);result=start(root,task(kind='read-only'))
            self.assertTrue(result['ok']);report=status(root,result['run_id'])
            self.assertTrue(any(a.get('knowledge_reason')=='knowledge-absent' for a in report['run']['agents']))
            self.assertEqual(context(root,'Feature')['mode'],'degraded')
            self.assertFalse((root/'.knowledge/store.sqlite3').exists())

    def test_context_isolation_actual_bytes_and_shared_history_comparison(self):
        from harness.comparison import compare
        from knowledge.util import canonical_json,loads
        with tempfile.TemporaryDirectory() as tmp,tempfile.TemporaryDirectory() as storage:
            root=project(tmp);fixture=FixtureProvider()
            with http_provider(fixture) as endpoint:
                configure(root,configuration(endpoint),True);result=compare(root,task(),Path(storage)/'comparison')
            self.assertTrue(result['ok'],result)
            self.assertEqual(result['comparison']['quality_speed_token_benefit'],'NOT_ESTABLISHED')
            multi=[b for b in fixture.requests if loads(b['messages'][0]['content'])['mode']=='multi']
            self.assertTrue(multi)
            for body in multi:
                self.assertLessEqual(len(canonical_json(body).encode()),24000)
                system=loads(body['messages'][0]['content'])
                if system['runtime_role']!='Main':self.assertNotIn('MAIN_PRIVATE_MARKER',canonical_json(body))
            for report in result['comparison']['runs'].values():
                self.assertEqual(report['metrics']['requests'],sum(r['requests'] for r in report['metrics']['roles']))

    def test_provider_malformed_oversized_missing_usage_and_limits(self):
        import time
        from p2_fixtures import final
        cases=[('bad',lambda _: {'choices':[]},{},'invalid-provider-choices'),
               ('oversize',lambda _: {'choices':[{'message':final('x'*10000)}]},{'response_bytes':1000},'provider-response-too-large'),
               ('timeout',lambda _: (time.sleep(2) or {'choices':[{'message':final()}]}),{'provider_seconds':1},'provider-outcome-unknown')]
        for name,response,limits,error in cases:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp,http_provider(None,raw=response) as endpoint:
                root=project(tmp);configure(root,configuration(endpoint,**limits),True);result=start(root,task())
                self.assertEqual(result['error'],error,result)
                self.assertGreater(status(root,result['run_id'])['metrics']['unknown_usage_requests'],0)
        with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider(),usage=False) as endpoint:
            root=project(tmp);configure(root,configuration(endpoint,reported_tokens=1000),True);result=start(root,task())
            self.assertEqual(result['error'],'usage-required-for-token-budget')
        with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider()) as endpoint:
            root=project(tmp);configure(root,configuration(endpoint,requests=2),True);result=start(root,task())
            self.assertEqual(result['error'],'request-budget-exhausted');self.assertEqual(status(root,result['run_id'])['metrics']['requests'],2)

    def test_long_history_unicode_tool_budget_and_role_spoofing(self):
        from p2_fixtures import calls,final
        from knowledge.util import loads,canonical_json
        seen=[]
        def decide(body):
            seen.append(body);system=loads(body['messages'][0]['content']);n=len(seen)
            if n<7:return calls(('read',{'path':'Feature.cs','limit':100}),content='Д'*1000)
            if n==7:return calls(('patch',{'files':[],'role':'Coding'}))
            return final()
        with tempfile.TemporaryDirectory() as tmp,http_provider(decide) as endpoint:
            root=project(tmp);(root/'Feature.cs').write_text('Я'*3000);configure(root,configuration(endpoint,context_bytes=6000,tool_bytes=800),True)
            result=start(root,task(kind='read-only'));self.assertTrue(result['ok'],result)
            self.assertTrue(all(len(canonical_json(b).encode())<=6000 for b in seen))
            self.assertFalse(any(a['tool']=='patch' for a in status(root,result['run_id'])['actions'].values()))

    def test_capture_five_sessions_no_facts_reject_dedup_and_no_auto_apply(self):
        from knowledge.store import Store
        from knowledge import lifecycle
        from harness.engine import resume
        for index in range(5):
            desired=f'public class EligibleSession{index} {{}}\n'
            with self.subTest(session=index),tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider(desired=desired)) as endpoint:
                root=project(tmp,desired);configure(root,configuration(endpoint),True);run=start(root,task());self.assertTrue(run['ok'],run)
                store=Store(root);queue=store.export()['queue'];self.assertEqual(len(queue),1);cid=queue[0]['id']
                lifecycle.dispose(store,cid,'rejected','synthetic reviewer rejects unchanged proposal')
                resume(root,run['run_id']);self.assertEqual(len(store.export()['queue']),1);self.assertFalse(store.export()['records']['claims'])
        # A Python-only edit has real checks/review but no supported .NET observation.
        with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider(path='Feature.py',desired='VALUE=2\n')) as endpoint:
            root=project(tmp);(root/'Feature.py').write_text('VALUE=1\n')
            (root/'build.py').write_text('import py_compile;py_compile.compile("Feature.py",doraise=True)\n')
            (root/'test_feature.py').write_text('import unittest\nfrom Feature import VALUE\nclass T(unittest.TestCase):\n def test_value(self):self.assertEqual(VALUE,2)\nif __name__=="__main__":unittest.main()\n')
            configure(root,configuration(endpoint),True);result=start(root,task(path='Feature.py'));self.assertTrue(result['ok'],result);self.assertEqual(result['capture']['state'],'no-candidate')

class RecoveryTests(unittest.TestCase):
    def child_start(self,root,phase,only_patch=False):
        import subprocess,sys
        code='''from harness import runtime,engine
from knowledge.util import loads
root=ROOT
j=runtime.Journal(root)
def die(phase):
 if phase==PHASE:
  if ONLY_PATCH:
   if not any(a['tool']=='patch' for r in j.runs() for a in j.actions(r['id']).values()):return
  import os;os._exit(73)
runtime.fault=die
raise SystemExit(0 if engine.start(root,loads(TASK))['ok'] else 1)
'''.replace('ROOT',repr(str(root))).replace('PHASE',repr(phase)).replace('ONLY_PATCH',repr(only_patch)).replace('TASK',repr(__import__('json').dumps(task())))
        return subprocess.Popen([sys.executable,'-c',code])

    def test_real_edit_intent_write_and_receipt_crashes_resume_without_double_edit(self):
        from harness.engine import resume
        from harness.runtime import Journal
        for phase in ('tool-intent','edit-intent','edit-file-written','tool-receipt','execution-passed'):
            with self.subTest(phase=phase),tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider()) as endpoint:
                root=project(tmp);configure(root,configuration(endpoint),True)
                child=self.child_start(root,phase,phase in ('tool-intent','tool-receipt'));self.assertEqual(child.wait(timeout=15),73)
                journal=Journal(root);run_id=journal.runs()[0]['id'];after=(root/'Feature.cs').stat().st_mtime_ns
                result=resume(root,run_id);self.assertTrue(result['ok'],result)
                if phase not in ('edit-intent','tool-intent'):self.assertEqual((root/'Feature.cs').stat().st_mtime_ns,after)
                patches=[a for a in journal.actions(run_id).values() if a['tool']=='patch'];self.assertEqual(len(patches),1)

    def test_recovery_preserves_intervening_user_bytes_and_unknown_provider(self):
        from harness.engine import resume
        from harness.runtime import Journal
        with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider()) as endpoint:
            root=project(tmp);configure(root,configuration(endpoint),True);child=self.child_start(root,'edit-file-written');self.assertEqual(child.wait(timeout=15),73)
            run_id=Journal(root).runs()[0]['id'];(root/'Feature.cs').write_text('USER INTERVENING EDIT\n')
            result=resume(root,run_id);self.assertFalse(result['ok']);self.assertEqual((root/'Feature.cs').read_text(),'USER INTERVENING EDIT\n')
        with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider()) as endpoint:
            root=project(tmp);configure(root,configuration(endpoint),True);child=self.child_start(root,'provider-intent');self.assertEqual(child.wait(timeout=15),73)
            run_id=Journal(root).runs()[0]['id'];result=resume(root,run_id)
            self.assertEqual(result['error'],'provider-outcome-unknown-manual-retry-required');self.assertEqual(status(root,run_id)['metrics']['requests'],1)

    def test_capture_commit_ack_crash_and_concurrent_delivery_retry(self):
        import subprocess,sys
        from harness.engine import resume
        from harness.runtime import Journal
        from knowledge.store import Store
        with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider()) as endpoint:
            root=project(tmp);configure(root,configuration(endpoint),True);child=self.child_start(root,'capture-after-submit');self.assertEqual(child.wait(timeout=15),73)
            j=Journal(root);run_id=j.runs()[0]['id'];before=(root/'Feature.cs').stat().st_mtime_ns
            self.assertEqual(len(Store(root).status()['queue']),1)
            code='from harness.engine import resume;raise SystemExit(0 if resume('+repr(str(root))+','+repr(run_id)+')["ok"] else 1)'
            children=[subprocess.Popen([sys.executable,'-c',code]) for _ in range(2)]
            self.assertEqual([c.wait(timeout=15) for c in children],[0,0]);self.assertEqual(len(Store(root).status()['queue']),1)
            self.assertEqual((root/'Feature.cs').stat().st_mtime_ns,before)
            self.assertTrue(all(i['state']=='delivered' for i in j.outbox(run_id).values()))

    def test_busy_and_corrupt_capture_are_explicit_and_recover_without_code_replay(self):
        from unittest.mock import patch
        from harness import runtime
        from harness.engine import resume
        from knowledge.store import Store
        lock=[]
        with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider()) as endpoint:
            root=project(tmp);configure(root,configuration(endpoint),True)
            def hold(phase):
                if phase=='capture-outbox' and not lock:
                    connection=Store(root).connection(True);connection.__enter__();lock.append(connection)
            with patch.object(runtime,'fault',side_effect=hold):result=start(root,task())
            self.assertEqual(result['status'],'awaiting-capture',result);self.assertEqual(result['execution'],'passed')
            before=(root/'Feature.cs').stat().st_mtime_ns;lock.pop().__exit__(None,None,None)
            result=resume(root,result['run_id']);self.assertTrue(result['ok'],result);self.assertEqual((root/'Feature.cs').stat().st_mtime_ns,before)
        # An existing corrupt Knowledge file never becomes an empty successful store.
        with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider()) as endpoint:
            root=project(tmp);configure(root,configuration(endpoint),True)
            (root/'.knowledge/store.sqlite3').write_bytes(b'corrupt synthetic database')
            result=start(root,task());self.assertEqual(result['execution'],'passed');self.assertEqual(result['status'],'awaiting-capture')
            self.assertNotEqual(result['capture']['state'],'no-candidate')

    def test_timeout_cleans_real_descendants_and_cancellation_stops_provider(self):
        import os,time,threading
        from harness.runtime import Journal
        from harness.process_worker import process_info
        with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider()) as endpoint:
            root=project(tmp);c=configuration(endpoint,recipe_seconds=1)
            code='import subprocess,sys,time;from pathlib import Path;p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"]);Path(sys.argv[1]).write_text(str(p.pid));time.sleep(30)'
            c['recipes']['build']['argv']=[__import__('sys').executable,'-c',code,'{artifacts}/child.pid']
            configure(root,c,True);result=start(root,task());self.assertFalse(result['ok'])
            report=status(root,result['run_id']);build=next(a for a in report['actions'].values() if a['tool']=='recipe' and a['args']['name']=='build')
            self.assertEqual(build['result']['reason'],'recipe-timeout');self.assertTrue(build['result']['descendants_stopped'])
            pid=int((Path(root)/build['result']['log']).parent.joinpath('child.pid').read_text());info=process_info(pid);self.assertTrue(info is None or info['state']=='Z')
        from p2_fixtures import final
        def slow(_):time.sleep(3);return {'choices':[{'message':final()}]}
        with tempfile.TemporaryDirectory() as tmp,http_provider(None,raw=slow) as endpoint:
            root=project(tmp);configure(root,configuration(endpoint),True);output=[]
            thread=threading.Thread(target=lambda:output.append(start(root,task())));thread.start();journal=Journal(root)
            until=time.time()+5
            while not journal.runs() and time.time()<until:time.sleep(.02)
            journal.cancel(journal.runs()[0]['id']);thread.join(timeout=4);self.assertFalse(thread.is_alive());self.assertEqual(output[0]['status'],'cancelled')

    def test_real_worker_death_recipe_keeps_lease_and_recovery_cleans_it(self):
        import subprocess,sys,time,signal,os
        from harness.runtime import Journal,Lease
        from harness.engine import resume
        from knowledge.util import KnowledgeError
        with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider()) as endpoint:
            root=project(tmp);c=configuration(endpoint,recipe_seconds=15)
            c['recipes']['build']['argv']=[sys.executable,'-c','import time;time.sleep(10)']
            configure(root,c,True)
            code='from harness.engine import start;from knowledge.util import loads;start('+repr(str(root))+',loads('+repr(__import__('json').dumps(task()))+'))'
            child=subprocess.Popen([sys.executable,'-c',code]);journal=Journal(root);run_id=None;until=time.time()+10
            while time.time()<until:
                runs=journal.runs()
                if runs:
                    run_id=runs[0]['id']
                    if any(a.get('process') for a in journal.actions(run_id).values()):break
                time.sleep(.02)
            self.assertTrue(run_id);child.kill();child.wait(timeout=3)
            with self.assertRaisesRegex(KnowledgeError,'project-writer-busy'):
                with Lease(journal):pass
            outcome=resume(root,run_id);self.assertFalse(outcome['ok'])
            with Lease(journal):pass

class BoundaryTests(unittest.TestCase):
    def test_cli_backend_and_legacy_configuration_compatibility(self):
        import json,subprocess,sys
        from knowledge.util import canonical_json
        with tempfile.TemporaryDirectory(prefix='P2 cli путь ') as tmp,http_provider(FixtureProvider()) as endpoint:
            root=project(tmp);legacy=root/'.harness/config.json';legacy.parent.mkdir();legacy.write_text('{"response_max_bytes":2048}')
            original=legacy.read_bytes();inputs=root.parent/(root.name+'-inputs.json')
            def command(name,**flags):
                argv=[sys.executable,'-m','harness.run_cli',name,'--root',str(root)]
                for k,v in flags.items():argv.extend(['--'+k.replace('_','-'),str(v)])
                p=subprocess.run(argv,text=True,capture_output=True,timeout=15);self.assertEqual(p.returncode,0,p.stdout+p.stderr);return json.loads(p.stdout)
            try:
                inputs.write_text(canonical_json(configuration(endpoint)));command('configure',input=inputs);command('validate-config')
                inputs.write_text(canonical_json(task(kind='read-only')));r=command('run',input=inputs)
                self.assertTrue(command('status',run_id=r['run_id'])['run']);self.assertTrue(command('status')['runs'])
                self.assertGreater(command('metrics',run_id=r['run_id'])['metrics']['requests'],0)
                command('capture-status',run_id=r['run_id']);command('capture-retry',run_id=r['run_id']);command('cancel',run_id=r['run_id']);command('resume',run_id=r['run_id'])
                old=subprocess.run([sys.executable,'-m','harness.cli','--root',str(root),'--task','Feature'],text=True,capture_output=True)
                self.assertEqual(old.returncode,0,old.stderr);self.assertEqual(json.loads(old.stdout)['runner'],'not-invoked');self.assertEqual(legacy.read_bytes(),original)
            finally:inputs.unlink(missing_ok=True)

    def test_protected_tests_recipes_paths_and_typed_spoof_denied(self):
        from p2_fixtures import calls,final
        class Attempts(FixtureProvider):
            def decide(self,body):
                from knowledge.util import loads
                system=loads(body['messages'][0]['content']);role=system['runtime_role'];agent=system['agent']
                if role=='Coding':
                    n=self.agent_turns[agent];self.agent_turns[agent]+=1
                    if n:return final()
                    return calls(*[('patch',{'files':[{'path':p,'before':None,'after':'FORBIDDEN'}]}) for p in ('../escape.cs','.harness/runner.json','test_feature.py','build.py','verifier.py','linked.cs','linked-dir/a.cs','Project.csproj')],('patch',{'files':[],'role':'Main'}),('recipe',{'name':'build; echo bad'}))
                return super().decide(body)
        with tempfile.TemporaryDirectory() as tmp,tempfile.TemporaryDirectory() as other,http_provider(Attempts()) as endpoint:
            root=project(tmp);outside=Path(other)/'outside.cs';outside.write_text('OUTSIDE')
            (root/'linked.cs').symlink_to(outside);(root/'linked-dir').symlink_to(other,target_is_directory=True);(root/'verifier.py').write_text('print("not executed")\n')
            c=configuration(endpoint);c['recipes']['build']['argv']=[__import__('sys').executable,'-m','verifier']
            configure(root,c,True);t=task();t['writable']=['*'];result=start(root,t);self.assertFalse(result['ok'])
            errors={e.get('error') for e in status(root,result['run_id'])['events'] if e['kind']=='tool-denied'}
            receipts=[a['result'].get('error') for a in status(root,result['run_id'])['actions'].values() if a['tool']=='patch']
            self.assertIn('invalid-tool-fields',errors);self.assertIn('existing-test-edit-denied',receipts);self.assertIn('recipe-input-edit-denied',receipts)
            self.assertEqual(outside.read_text(),'OUTSIDE');self.assertEqual((root/'verifier.py').read_text(),'print("not executed")\n');self.assertFalse((root.parent/'escape.cs').exists())

    def test_missing_stale_fake_gates_and_configuration_drift(self):
        from p2_fixtures import calls,final
        from knowledge.util import loads
        from harness import runtime
        from unittest.mock import patch
        import json
        class Stale(FixtureProvider):
            def decide(self,body):
                s=loads(body['messages'][0]['content'])
                if s['runtime_role']=='Main' and self.main_agents[s['agent']]==1:
                    self.main_agents[s['agent']]+=1;return calls(('delegate',{'role':'Coding','assignment':'Late edit without fresh gates'}))
                return super().decide(body)
        for scenario in (Stale(),lambda _:final('Tests passed, build passed, review approved')):
            with self.subTest(scenario=scenario),tempfile.TemporaryDirectory() as tmp,http_provider(scenario) as endpoint:
                root=project(tmp);configure(root,configuration(endpoint),True);r=start(root,task());self.assertFalse(r['ok']);self.assertIn(r['error'],('required-check-missing-failed-or-stale','required-role-missing'))
        with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider()) as endpoint:
            root=project(tmp);c=configuration(endpoint);configure(root,c,True)
            def change(phase):
                if phase=='provider-response':
                    c['capture']='off';(root/'.harness/runner.json').write_text(json.dumps(c))
            with patch.object(runtime,'fault',side_effect=change):r=start(root,task())
            self.assertEqual(r['error'],'configuration-changed-revalidation-required');self.assertEqual((root/'Feature.cs').read_text(),'public class InitialFeature {}\n')

    def test_concurrent_source_edit_during_recipe_invalidates_gate(self):
        import sys
        with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider()) as endpoint:
            root=project(tmp);c=configuration(endpoint)
            c['recipes']['build']['argv']=[sys.executable,'-c','from pathlib import Path;Path("Feature.cs").write_text("USER CONCURRENT EDIT")']
            configure(root,c,True);r=start(root,task());self.assertFalse(r['ok']);self.assertEqual((root/'Feature.cs').read_text(),'USER CONCURRENT EDIT')
            self.assertTrue(any(a.get('result',{}).get('error')=='source-changed-during-gate' for a in status(root,r['run_id'])['actions'].values()))

    def test_durable_versions_project_identity_and_corruption_refuse_without_reset(self):
        from harness.runtime import Journal
        from knowledge.util import KnowledgeError
        import shutil,sqlite3,json
        with tempfile.TemporaryDirectory() as tmp,tempfile.TemporaryDirectory() as other:
            root=project(tmp);j=Journal(root)
            shutil.copytree(root/'.harness',Path(other)/'.harness')
            with self.assertRaisesRegex(KnowledgeError,'harness-state-version-or-project-mismatch'):Journal(other)
            with closing(sqlite3.connect(j.path)) as db, db:db.execute("UPDATE meta SET value='99' WHERE key='version'")
            before=j.path.read_bytes()
            with self.assertRaisesRegex(KnowledgeError,'harness-state-version-or-project-mismatch'):Journal(root)
            self.assertEqual(j.path.read_bytes(),before)
        with tempfile.TemporaryDirectory() as tmp:
            root=project(tmp);j=Journal(root);j.path.write_bytes(b'corrupt')
            with self.assertRaisesRegex(KnowledgeError,'harness-state-corrupt'):Journal(root)
            self.assertEqual(j.path.read_bytes(),b'corrupt')

    def test_provider_surrogates_usage_subsets_and_final_version_refuse(self):
        from harness.provider import usage
        from p2_fixtures import final
        for raw in ({'prompt_tokens':1,'completion_tokens':2,'total_tokens':6},{'prompt_tokens':1,'completion_tokens':2,'prompt_tokens_details':{'cached_tokens':3}}):
            self.assertEqual(usage(raw)['coverage'],'unknown')
        self.assertEqual(usage({'prompt_tokens':4,'completion_tokens':3,'prompt_tokens_details':{'cached_tokens':2},'completion_tokens_details':{'reasoning_tokens':1}})['total'],7)
        for message,error in (({'role':'assistant','content':'\ud800'},'invalid-provider-response'),({'role':'assistant','content':'{"version":99,"status":"done","summary":"fake"}'},'invalid-final-response')):
            with self.subTest(error=error),tempfile.TemporaryDirectory() as tmp,http_provider(None,raw=lambda _,m=message:{'choices':[{'message':m}]}) as endpoint:
                root=project(tmp);configure(root,configuration(endpoint),True);r=start(root,task());self.assertEqual(r['error'],error)

    def test_terminal_window_and_unchanged_deferred_candidate_are_idempotent(self):
        from harness import runtime
        from harness.engine import resume
        from unittest.mock import patch
        from knowledge.store import Store
        from knowledge import lifecycle
        class Crash(Exception):pass
        with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider()) as endpoint:
            root=project(tmp);configure(root,configuration(endpoint),True)
            def crash(phase):
                if phase=='execution-passed':raise Crash()
            with patch.object(runtime,'fault',side_effect=crash):
                with self.assertRaises(Crash):start(root,task())
            j=runtime.Journal(root);r=j.runs()[0];before=(root/'Feature.cs').stat().st_mtime_ns
            self.assertTrue(resume(root,r['id'])['ok']);self.assertEqual((root/'Feature.cs').stat().st_mtime_ns,before)
            s=Store(root);candidate=s.export()['queue'][0]['id'];lifecycle.dispose(s,candidate,'deferred','unchanged proposal deferred')
            (root/'Feature.cs').write_text('public class InitialFeature {}\n')
            with http_provider(FixtureProvider()) as second:
                configure(root,configuration(second),True);r2=start(root,task());self.assertTrue(r2['ok'],r2)
            self.assertEqual(len(s.export()['queue']),1);self.assertEqual(s.export()['queue'][0]['status'],'deferred')

    def test_supervisor_imports_cannot_be_replaced_by_application_package(self):
        import json,subprocess,sys
        from knowledge.util import canonical_json
        with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider()) as endpoint:
            root=project(tmp);(root/'harness').mkdir();(root/'harness/__init__.py').write_text('')
            (root/'harness/process_worker.py').write_text('from pathlib import Path\nPath("FORBIDDEN").write_text("hijacked")\n')
            configure(root,configuration(endpoint),True)
            taskfile=root/'task.json';taskfile.write_text(canonical_json(task()))
            p=subprocess.run([sys.executable,'-I','-m','harness.run_cli','run','--root',str(root),'--input',str(taskfile)],cwd=root,text=True,capture_output=True,timeout=20)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr);self.assertFalse((root/'FORBIDDEN').exists())

    def test_actual_log_caps_delegation_guards_and_artifact_recipe_validation(self):
        import sys
        from harness.runtime import validate_config
        from knowledge.util import KnowledgeError
        with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider()) as endpoint:
            root=project(tmp);c=configuration(endpoint,log_bytes=128,tool_bytes=3000)
            c['recipes']['build']['argv']=[sys.executable,'-c','print("Я"*5000)']
            configure(root,c,True);r=start(root,task());self.assertTrue(r['ok'],r)
            receipt=next(a['result'] for a in status(root,r['run_id'])['actions'].values() if a['tool']=='recipe' and a['args']['name']=='build')
            self.assertEqual(receipt['log_bytes'],128);self.assertTrue(receipt['truncated']);self.assertGreater(receipt['observed_log_bytes'],128)
        with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider()) as endpoint:
            root=project(tmp);configure(root,configuration(endpoint,delegations=1),True);r=start(root,task());self.assertFalse(r['ok'])
            self.assertTrue(any(e.get('error')=='delegation-budget-exhausted' for e in status(root,r['run_id'])['events']))
        for path in ('{artifacts}/../old.trx','{artifacts}//absolute.trx','{artifacts}/{other}.trx'):
            c=configuration('http://127.0.0.1/v1/chat/completions');c['recipes']['test']['result']={'format':'trx','path':path}
            with self.assertRaises(KnowledgeError):validate_config(c)

    def test_recipe_cancellation_and_competing_run_refuse_before_effect(self):
        import threading,time,sys
        from harness.runtime import Journal
        from knowledge.util import KnowledgeError
        with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider()) as endpoint:
            root=project(tmp);c=configuration(endpoint,recipe_seconds=20)
            c['recipes']['build']['argv']=[sys.executable,'-c','import time;time.sleep(15)']
            configure(root,c,True);results=[]
            thread=threading.Thread(target=lambda:results.append(start(root,task())));thread.start();journal=Journal(root);run_id=None
            until=time.monotonic()+10
            while time.monotonic()<until:
                runs=journal.runs()
                if runs:
                    run_id=runs[0]['id']
                    if any(a.get('process') for a in journal.actions(run_id).values()):break
                time.sleep(.02)
            self.assertTrue(run_id)
            with self.assertRaisesRegex(KnowledgeError,'project-writer-busy'):start(root,task())
            self.assertEqual(len(journal.runs()),1)
            journal.cancel(run_id);thread.join(timeout=6);self.assertFalse(thread.is_alive());self.assertEqual(results[0]['status'],'cancelled')
            recipe=next(a for a in journal.actions(run_id).values() if a['tool']=='recipe')
            self.assertEqual(recipe['process_result']['reason'],'cancelled');self.assertTrue(recipe['process_result']['descendants_stopped'])
