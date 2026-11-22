"""Audit stage 2: installed APIs and durable sessions, labelled model doubles."""
import asyncio,hashlib,json,subprocess,sys,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from knowledge import lifecycle as life
from knowledge.store import Store
from knowledge.util import KnowledgeError,canonical_json
from harness.host_ingress import message,read_session
from harness.runtime import configure,Journal
from test_p1 import upgraded,approve
from fixtures import addition
from test_persistent_instructions import setup_fixture
from test_persistent_semantics import local_normalizer,decision
from test_p4 import Decisions,p4task
from p2_fixtures import project,configuration,http_provider
from harness.engine import start


def fact(store,root,name,statement,depends=()):
    path=name.replace('.','_')+'.md';(root/path).write_text(statement,encoding='utf-8')
    value=addition(name,statement);c=value['records']['claims'][0];c['depends_on']=list(depends)
    value['records']['evidence'][0].update(source=path,location=path+'#L1',content_hash='sha256:'+hashlib.sha256((root/path).read_bytes()).hexdigest())
    for parent in depends:value['records']['relationships'].append({'id':name+'.edge.'+parent,'type':'depends_on','from':name,'to':parent,'provenance':{'actor':'fixture','method':'reviewed'}})
    store.submit(value);approve(store);return c['id']

class RetrievalContracts(unittest.TestCase):
    def test_dependency_closure_and_item_budget_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);s=upgraded(root)
            fact(s,root,'policy.parent','The approved threshold is 37.')
            child=fact(s,root,'policy.child','Pricing behavior follows its approved threshold.', ['policy.parent'])
            small=s.context('Pricing',max_items=1)
            self.assertEqual(small['claims'][0]['id'],child)
            self.assertEqual(small['claims'][0]['depends_on'],['policy.parent'])
            self.assertTrue(small['partial']);self.assertFalse(small['dependencies']['complete'])
            full=s.context('Pricing',max_items=2)
            self.assertEqual({c['id'] for c in full['claims']},{child,'policy.parent'})
            self.assertTrue(full['dependencies']['complete']);self.assertEqual(full['truncation']['returned'],len(full['claims']))
    def test_filtered_facts_are_explained_without_stale_statements(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);s=upgraded(root);fact(s,root,'policy.pricing','Pricing uses the approved threshold 37.')
            (root/'policy_pricing.md').write_text('Changed behavior.',encoding='utf-8')
            result=s.context('Pricing');self.assertFalse(result['claims'])
            self.assertTrue(result['diagnostics']['filtered']);self.assertTrue(result['partial'])
            self.assertNotIn('Pricing uses the approved threshold 37.',canonical_json(result))
            self.assertIn('changed',canonical_json(result['diagnostics']))
            self.assertEqual(s.context('quasarbeyondvocabulary')['diagnostics']['selection'],'lexical-no-match')
            for size in (256,400,800,1600):
                value=s.context('Pricing',max_bytes=size);self.assertLessEqual(len(canonical_json(value).encode()),size)
    def test_absent_is_distinct_and_corruption_remains_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.assertEqual(Store(root).context('Pricing')['result'],'store-absent')
            s=upgraded(root);s.path.write_bytes(b'not sqlite')
            with self.assertRaises(KnowledgeError):s.context('Pricing')

class DegradedSessions(unittest.TestCase):
    def test_installed_node_hook_accepts_degraded_chat_and_keeps_session_binding(self):
        import importlib.resources
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp);cfg['memory'].update(teaching_mode='local-model',normalizer={'endpoint':'http://127.0.0.1:1/v1/chat/completions','model':'absent','timeout':1});configure(root,cfg)
            plugin=importlib.resources.files('knowledge').joinpath('host/opencode.mjs')
            child=subprocess.run(['node',str(Path(__file__).with_name('audit_degraded_hook.mjs')),str(plugin),sys.executable,str(root)],capture_output=True,encoding='utf-8',timeout=15)
            self.assertEqual(child.returncode,0,child.stderr);self.assertTrue(json.loads(child.stdout)['ok'])
            self.assertTrue(read_session(root,'hook-outage')['pending'])

    def test_outage_chat_is_safe_and_preserves_current_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp);cfg['memory'].update(teaching_mode='local-model',normalizer={'endpoint':'http://127.0.0.1:1/v1/chat/completions','model':'absent','timeout':1});configure(root,cfg)
            result=message(root,'Fix a typo in Feature.cs.','session','m1')
            self.assertTrue(result['ok']);self.assertTrue(result['degraded']);self.assertFalse(result['saved'])
            state=read_session(root,'session');self.assertTrue(state['pending'])
            denied=message(root,'Do not start services in this run.','session','m2')
            self.assertEqual(denied['restriction'],'no-service-start');self.assertEqual(read_session(root,'session')['restrictions'],['no-service-start'])
            with self.assertRaisesRegex(KnowledgeError,'source-reused'):message(root,'different text','session','m1')
    def test_sensitive_outage_never_persists_raw_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp);cfg['memory'].update(teaching_mode='local-model',normalizer={'endpoint':'http://127.0.0.1:1/v1/chat/completions','model':'absent','timeout':1});configure(root,cfg)
            text='Read api_key=synthetic-secret-fixture'
            result=message(root,text,'sensitive','m');self.assertTrue(result['sensitive_skipped'])
            state=read_session(root,'sensitive');self.assertNotIn(text,canonical_json(state));self.assertTrue(state['pending'])

class P4Delivery(unittest.TestCase):
    def test_initial_and_fresh_roles_receive_architecture_without_tool_lookup(self):
        with tempfile.TemporaryDirectory() as tmp,http_provider(Decisions()) as endpoint:
            root=project(tmp);configure(root,configuration(endpoint),True)
            s=Store(root);identifier=fact(s,root,'policy.feature','ImprovedFeature requires the approved source shape.')
            decision_model=Decisions()
            with http_provider(decision_model) as actual:
                configure(root,configuration(actual),True);task=p4task()
                task['items']=[{'id':name,'objective':'Implement ImprovedFeature behavior.','depends':[] if name=='one' else ['one'],'writable':['Feature.cs']} for name in ('one','two')]
                result=start(root,task)
            self.assertTrue(result['ok'],result)
            for role in ('Main','Coding','Reviewing'):
                body=next(b for b in decision_model.bodies if json.loads(b['messages'][0]['content'])['runtime_role']==role)
                self.assertIn(identifier,canonical_json(body))
            run=Journal(root).load(result['run_id']);self.assertTrue(run['p4']['knowledge_deliveries'])
            coding=[v for v in run['p4']['knowledge_deliveries'].values() if v['binding']['role']=='Coding']
            self.assertEqual({v['binding']['phase'] for v in coding},{'one','two'})

    def test_diagnosis_and_repair_attempts_receive_current_independent_slices(self):
        model=Decisions(broken=True)
        with tempfile.TemporaryDirectory() as tmp,http_provider(model) as endpoint:
            root=project(tmp);configure(root,configuration(endpoint),True)
            identifier=fact(Store(root),root,'policy.feature','ImprovedFeature requires the approved source shape.')
            result=start(root,p4task());self.assertEqual(result['error'],'repair-exhausted')
            planning=[b for b in model.bodies if json.loads(b['messages'][0]['content'])['runtime_role']=='Planning']
            self.assertTrue(planning);self.assertTrue(all(identifier in canonical_json(b) for b in planning))
            run=Journal(root).load(result['run_id']);coding=[v for v in run['p4']['knowledge_deliveries'].values() if v['binding']['role']=='Coding']
            self.assertEqual({v['binding']['attempt'] for v in coding},{1,2,3})

class DegradedRecovery(unittest.TestCase):
    def test_pending_effects_block_but_reading_and_existing_grants_survive(self):
        from test_persistent_r1 import dependency
        from test_persistent_instructions import worker
        from knowledge import operations as op
        from harness.runtime import Lease,config
        from harness.tools import Broker
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp);proc,b=dependency()
            cfg['memory'].update(teaching_mode='local-model',normalizer={'endpoint':'http://127.0.0.1:1/v1/chat/completions','model':'absent','timeout':1},bindings=[b],allowed_procedures=[proc])
            configure(root,cfg);saved=op.teach(root,'Allowed existing fixture.',{'type':'user-message','id':'grant'},shared=shared,binding=b,recovery_authorized=True)
            message(root,'Fix a typo in Feature.cs.','pending','m')
            for args in ({'patch':'wrong\n'},{}):
                result=worker(root,host_session='pending',**args)
                self.assertEqual(result['result']['error'],'host-controls-unresolved');self.assertFalse(any(a.get('process_spec') for a in result['actions'].values()))
            self.assertEqual((root/'Feature.cs').read_bytes(),b'initial\n')
            self.assertTrue(next(r for r in op.OperationalStore(root,'project',shared).records()['records'] if r['id']==saved['id'])['recovery_authorized'])
            journal=Journal(root);run=journal.runs()[0]
            with Lease(journal) as lease:
                result=Broker(journal,config(root),run,lease).execute('Coding','read-only','read',{'path':'Feature.cs'})
                self.assertTrue(result['ok'])

    def test_fresh_process_recovery_preserves_format_and_binds_original_intent(self):
        from p2_fixtures import http_provider
        from test_persistent_instructions import binding
        from harness.host_ingress import session_path,write_session
        from knowledge import operations as op
        phase={'ready':False}
        def raw(body):return {'choices':[{'message':{'content':canonical_json(decision()) if phase['ready'] else 'malformed response'}}]}
        with tempfile.TemporaryDirectory() as tmp,http_provider(None,raw=raw) as endpoint:
            root,shared,cfg=setup_fixture(tmp);cfg['memory'].update(teaching_mode='local-model',normalizer={'endpoint':endpoint,'model':'protocol-double','timeout':2},bindings=[binding()]);configure(root,cfg)
            result=message(root,'Remember encoding.','recover','m');self.assertTrue(result['degraded']);identifier=result['id']
            state=read_session(root,'recover');state['format_changes']=[{'path':'Feature.cs','bom':True,'eol':'crlf'}];write_session(session_path(root,'recover'),state)
            phase['ready']=True
            child=subprocess.run([sys.executable,'-I','-m','harness.host_ingress','--root',str(root),'--recover-session','recover'],capture_output=True,encoding='utf-8',timeout=15)
            self.assertEqual(child.returncode,0,child.stdout+child.stderr);self.assertFalse(json.loads(child.stdout)['pending'])
            state=read_session(root,'recover');self.assertTrue(state['format_changes']);self.assertNotIn('Remember encoding.',canonical_json(state))
            row=op.OperationalStore(root,'project',shared).records()['records'][0];self.assertEqual((row['id'],row['revision'],row['status']),(identifier,2,'active'))
            again=message(root,'Remember encoding.','recover','m');self.assertTrue(again['duplicate']);self.assertEqual(again['revision'],2)

    def test_late_clear_and_replay_cannot_override_newer_denial(self):
        from knowledge import semantic_ingress
        entered=threading.Event();release=threading.Event();results=[]
        allow='You may start services again.';deny='Do not start services in this run.'
        def normalize(text,*args,**kwargs):
            if text==allow:entered.set();self.assertTrue(release.wait(10))
            return decision(intent='none',binding=None,current_start='clear-denial' if text==allow else 'deny',restriction_quote=text),{'method':'protocol-double'}
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp);cfg['memory'].update(teaching_mode='local-model',normalizer={'endpoint':'http://127.0.0.1:1/v1/chat/completions','model':'double'});configure(root,cfg)
            with patch.object(semantic_ingress,'normalize',side_effect=normalize):
                thread=threading.Thread(target=lambda:results.append(message(root,allow,'race','older')));thread.start();self.assertTrue(entered.wait(5))
                newer=message(root,deny,'race','newer');self.assertEqual(newer['restriction'],'no-service-start');release.set();thread.join(10)
            self.assertFalse(thread.is_alive());self.assertEqual(results[0]['controls_ignored'],'older-source')
            self.assertEqual(read_session(root,'race')['restrictions'],['no-service-start'])
            message(root,allow,'race','older');self.assertEqual(read_session(root,'race')['restrictions'],['no-service-start'])

    def test_sensitive_operator_resolution_and_envelope_integrity(self):
        from harness.host_ingress import resolve_session,session_path,write_session,guard
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp);cfg['memory']['teaching_mode']='local-model';configure(root,cfg)
            result=message(root,'Read api_key=synthetic-secret-fixture','private','s');self.assertTrue(result['sensitive_skipped'])
            state=read_session(root,'private');row=state['messages']['s']
            with self.assertRaisesRegex(KnowledgeError,'host-controls-unresolved'):guard(root,'private','patch')
            resolve_session(root,'private',{'source_id':'s','source_hash':row['hash'],'decision':'no-new-controls'});self.assertFalse(read_session(root,'private')['pending'])
            message(root,'Fix a typo.','private','pending');state=read_session(root,'private');state['messages']['pending']['text']='tampered';write_session(session_path(root,'private'),state)
            with self.assertRaisesRegex(KnowledgeError,'host-pending-source-corrupt'):read_session(root,'private')

class GraphDiagnostics(unittest.TestCase):
    def test_filtered_conflict_partner_retains_edge_without_stale_statement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);store=upgraded(root)
            first=fact(store,root,'pricing.first','Pricing uses the approved first shape.')
            second=fact(store,root,'pricing.second','Pricing uses the conflicting second shape.')
            operations=[]
            for identifier,partner in ((first,second),(second,first)):
                record=store.lookup('claims',identifier)['record'];operations.append(life.op('update','claims',identifier,1,dict(record,conflicts_with=[partner])))
            store.submit(life.batch(operations,'Reviewed unresolved conflict'));approve(store)
            (root/'pricing_second.md').write_text('Changed supporting source.',encoding='utf-8')
            result=store.context('Pricing');self.assertEqual([c['id'] for c in result['claims']],[first])
            self.assertEqual(result['claims'][0]['conflicts_with'],[second]);partner=result['conflicts'][0]
            self.assertFalse(partner['partner_current']);self.assertIsNone(partner['partner_statement'])
            self.assertNotIn('Pricing uses the conflicting second shape.',canonical_json(result));self.assertTrue(result['partial'])

    def test_stale_parent_and_transitive_depth_remain_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);store=upgraded(root)
            fact(store,root,'base.rule','Base threshold is 37.')
            parent='base.rule'
            for index in range(6):
                name='chain.'+str(index);fact(store,root,name,('quasartopology follows its parent.' if index==5 else 'Layer '+str(index)+' follows its parent.'),[parent]);parent=name
            result=store.context('quasartopology',max_items=20)
            self.assertFalse(result['dependencies']['complete']);self.assertIn('depth-budget',canonical_json(result['dependencies']))
            (root/'base_rule.md').write_text('Changed base.',encoding='utf-8')
            stale=store.context('quasartopology');self.assertFalse(stale['claims']);self.assertIn('dependency-filtered',canonical_json(stale['diagnostics']))
    def test_actual_cli_and_mcp_unicode_byte_caps(self):
        from knowledge.mcp import create_server
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);store=upgraded(root);fact(store,root,'unicode.rule','Pricing поведение проверено — порог 37.')
            for cap in (256,400,800,1600,4000):
                child=subprocess.run([sys.executable,'-I','-m','knowledge.cli','context','--root',str(root),'--task','Pricing','--max-bytes',str(cap)],capture_output=True,timeout=15)
                self.assertEqual(child.returncode,0,child.stderr);self.assertLessEqual(len(child.stdout),cap);value=json.loads(child.stdout)
                self.assertLessEqual(len(canonical_json(value).encode()),cap)
                async def call():return await create_server(root).call_tool('knowledge_context',{'task':'Pricing','max_bytes':cap})
                content=asyncio.run(call())
                if hasattr(content,'content'):
                    self.assertIsNone(content.structuredContent);content=content.content
                elif isinstance(content,tuple):content=content[0]
                raw=''.join(part.text for part in content if part.type=='text')
                self.assertLessEqual(len(raw.encode()),cap);self.assertEqual(json.loads(raw),value)
    def test_status_lifecycle_and_dependency_missing_are_not_no_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);store=upgraded(root);identifier=fact(store,root,'pricing.rule','Pricing confirms a threshold.')
            record=store.lookup('claims',identifier)['record'];store.submit(life.batch([life.op('update','claims',identifier,1,dict(record,status='INFERRED',last_verified=None))],'Reviewed uncertainty'));approve(store)
            value=store.context('Pricing');self.assertIn('status-policy',canonical_json(value['diagnostics']));self.assertFalse(value['claims'])
            self.assertTrue(store.context('Pricing',include_unconfirmed=True)['claims'])
            store.submit(life.batch([life.op('retire','claims',identifier,2,None)],'Reviewed retirement'));approve(store)
            value=store.context('Pricing');self.assertIn('lifecycle-retired',canonical_json(value['diagnostics']))

class DeliveryBoundaries(unittest.TestCase):
    def test_fresh_process_resume_preserves_delivery_and_saved_provider_response(self):
        from harness import runtime
        class Death(Exception):pass
        model=Decisions()
        with tempfile.TemporaryDirectory() as tmp,http_provider(model) as endpoint:
            root=project(tmp);configure(root,configuration(endpoint),True)
            identifier=fact(Store(root),root,'policy.feature','ImprovedFeature requires the approved source shape.')
            def crash(phase):
                if phase=='provider-response':raise Death()
            with patch.object(runtime,'fault',side_effect=crash),self.assertRaises(Death):start(root,p4task())
            journal=Journal(root);before=journal.runs()[0];first=before['requests'][0]
            self.assertEqual(len(model.bodies),1);self.assertTrue(first['knowledge_delivery']['selected'])
            program='import sys,json;from harness.engine import resume;print(json.dumps(resume(sys.argv[1],sys.argv[2])))'
            child=subprocess.run([sys.executable,'-I','-c',program,str(root),before['id']],capture_output=True,encoding='utf-8',timeout=30)
            self.assertEqual(child.returncode,0,child.stderr);self.assertTrue(json.loads(child.stdout)['ok'])
            after=journal.load(before['id']);self.assertEqual(after['requests'][0],first)
            self.assertEqual(len(model.bodies),len(after['requests']))
            self.assertIn(identifier,canonical_json(model.bodies[0]))
            self.assertEqual(len([a for a in journal.actions(before['id']).values() if a['tool']=='patch']),1)

    def test_durable_cache_reuse_and_evidence_store_config_invalidation(self):
        from harness import runtime,delivery
        class Death(Exception):pass
        with tempfile.TemporaryDirectory() as tmp,http_provider(Decisions()) as endpoint:
            root=project(tmp);configure(root,configuration(endpoint),True)
            store=Store(root);fact(store,root,'policy.feature','ImprovedFeature requires the approved source shape.')
            def crash(phase):
                if phase=='provider-response':raise Death()
            with patch.object(runtime,'fault',side_effect=crash),self.assertRaises(Death):start(root,p4task())
            journal=Journal(root);run=journal.runs()[0];rid=run['id']
            def retrieve_again():
                value=journal.load(rid);cfg=runtime.config(root)
                result=delivery.slice_for(journal,cfg,value,value['frames'][-1],{**runtime.DEFAULT_LIMITS,**cfg['limits']})
                return result,value
            with patch.object(delivery,'retrieve',wraps=delivery.retrieve) as counter:
                cached,run=retrieve_again();self.assertEqual(counter.call_count,0)
                (root/'policy_feature.md').write_text('Changed supporting evidence.',encoding='utf-8')
                stale,run=retrieve_again();self.assertEqual(counter.call_count,1)
                self.assertNotEqual(stale['delivery'],cached['delivery']);self.assertFalse(stale['context']['claims'])
                fact(store,root,'policy.second','ImprovedFeature requires reviewed behavior.')
                updated,run=retrieve_again();self.assertEqual(counter.call_count,2)
                self.assertIn('policy.second',canonical_json(updated))
                run['config_hash']='changed-configuration-binding';journal.save(run)
                changed,run=retrieve_again();self.assertEqual(counter.call_count,3)
                self.assertNotEqual(changed['delivery'],updated['delivery'])
                run['source']['new.md']='source-generation-changed';journal.save(run)
                source,run=retrieve_again();self.assertEqual(counter.call_count,4)
                self.assertNotEqual(source['delivery'],changed['delivery'])

    def test_retrieval_count_follows_events_not_tool_rounds(self):
        from harness import delivery
        from test_p4 import calls
        class Long(Decisions):
            def __init__(self):super().__init__();self.total=0
            def decide(self,body):
                state=json.loads(body['messages'][0]['content'])
                if state['runtime_role']=='Coding':
                    self.total+=1
                    if self.total<=7:self.bodies.append(body);return calls(('read',{'path':'Feature.cs'}))
                return super().decide(body)
        with tempfile.TemporaryDirectory() as tmp,http_provider(Long()) as endpoint:
            root=project(tmp);configure(root,configuration(endpoint),True);fact(Store(root),root,'policy.feature','ImprovedFeature requires the approved source shape.')
            with patch.object(delivery,'retrieve',wraps=delivery.retrieve) as counter:result=start(root,p4task())
            self.assertTrue(result['ok'],result);run=Journal(root).load(result['run_id'])
            self.assertLess(counter.call_count,len(run['requests']));self.assertGreater(run['p4']['rotations'],0)
            self.assertTrue(all(q.get('knowledge_delivery') for q in run['requests']))
            self.assertTrue(all(q['input_bytes']<=24000 for q in run['requests']))


if __name__=='__main__':unittest.main()
