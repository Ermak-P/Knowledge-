from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from knowledge import operations as op
from knowledge.store import Store
from knowledge.util import canonical_json,KnowledgeError
from harness.runtime import configure
from harness.instructions import encode_edit
from fixtures import addition

WORKER=Path(__file__).with_name('persistent_worker.py')


def setup_fixture(base):
    root=Path(base)/'project';root.mkdir();shared=Path(base)/'home/.local/share/knowledge'
    (root/'Feature.cs').write_bytes(b'initial\n')
    cfg={'version':1,'provider':{'endpoint':'http://127.0.0.1:1/chat/completions','model':'unused'},'capture':'off','limits':{},
         'recipes':{'test':{'kind':'test','argv':[sys.executable,'-c','import unittest; unittest.TextTestRunner().run(unittest.FunctionTestCase(lambda: None))'],
                            'result':{'format':'unittest','path':''},'rerun_safe':True,'env':{}}},
         'memory':{'shared_root':str(shared),'bindings':[],'allowed_procedures':[]}}
    configure(root,cfg)
    return root,shared,cfg


def worker(root,**request):
    p=subprocess.run([sys.executable,'-I',str(WORKER),str(root)],input=json.dumps(request),text=True,capture_output=True,timeout=45)
    if p.returncode:raise AssertionError(p.stderr+p.stdout)
    return json.loads(p.stdout)


def ingress(root,text,message_id='m1',session='teaching'):
    p=subprocess.run([sys.executable,'-I','-m','harness.host_ingress','--root',str(root)],input=json.dumps({'text':text,'message_id':message_id,'session_id':session},ensure_ascii=False),encoding='utf-8',capture_output=True,timeout=10)
    return json.loads(p.stdout)


def binding(alias='encoding',tool='patch',name='*',behavior=None):
    return {'aliases':[alias],'trigger':{'tool':tool,'name':name},'behavior':behavior or {'adapter':'preserve-format'}}


class PersistentInstructions(unittest.TestCase):
    def test_automatic_ingress_then_independent_byte_preserving_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp);cfg['memory']['bindings']=[binding()];configure(root,cfg)
            raw=b'\xef\xbb\xbffirst\r\nmid\xef\xbb\xbfpoint\r\nlast'
            (root/'Feature.cs').write_bytes(raw)
            saved=ingress(root,'Запомни: encoding — сохраняй кодировку, BOM и окончания строк при правках.')
            self.assertTrue(saved['saved'],saved);self.assertEqual(saved['scope'],'project')
            result=worker(root,patch='first\nmid\ufeffpoint changed\nlast\n')
            self.assertTrue(result['result']['ok'],result)
            self.assertEqual((root/'Feature.cs').read_bytes(),b'\xef\xbb\xbffirst\r\nmid\xef\xbb\xbfpoint changed\r\nlast')
            selected=result['actions']['operation']['memory_traces'][0]['selected']
            self.assertEqual(selected[0]['id'],saved['id']);self.assertGreater(result['actions']['operation']['memory_traces'][0]['selected_bytes'],0)
            self.assertFalse(op.OperationalStore(root,'shared',shared).path.exists())

    def test_new_action_bound_rule_runs_owned_check_in_fresh_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp)
            procedure={'id':'archive_guard','check':{'argv':[sys.executable,'-c','from pathlib import Path; Path(".checked").write_text("yes")'],'timeout':2},'deadline':3,'interval':.1,'attempts':0}
            cfg['memory']['bindings']=[binding('archive guard','recipe','test',{'adapter':'check','procedure':procedure})]
            cfg['memory']['allowed_procedures']=[procedure];configure(root,cfg)
            saved=ingress(root,'Remember: before the test action apply archive guard.')
            self.assertEqual(saved['status'],'active',saved)
            result=worker(root);self.assertTrue(result['result']['ok'],result)
            self.assertEqual((root/'.checked').read_text(),'yes')
            self.assertTrue(any(a.get('memory_record')==saved['id'] and a.get('process_result',{}).get('descendants_stopped') for a in result['actions'].values()))

    def test_shared_reuse_isolation_applicability_and_bounded_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp);other=Path(tmp)/'other';other.mkdir()
            b=binding();b['applicability']={'machine':'fixture','tools':{'editor':'1'}}
            shared_rule=op.teach(root,'shared behavior',{'type':'user-message','id':'s'},scope='shared',shared=shared,binding=b,applicability=b['applicability'])
            project_rule=op.teach(root,'project behavior',{'type':'user-message','id':'p'},shared=shared,binding=binding('x','recipe','unit'))
            for i in range(12):op.teach(root,'unrelated '+str(i),{'type':'user-message','id':str(i)},scope='shared',shared=shared,binding=binding('x','recipe','unrelated'+str(i)))
            got=op.lookup(other,{'tool':'patch','name':'a.cs'},{'machine':'fixture','tools':{'editor':'1'}},shared=shared)
            self.assertEqual([r['id'] for r in got['records']],[shared_rule['id']]);self.assertFalse((other/'.knowledge').exists())
            self.assertEqual(got['payload_bytes'],len(canonical_json(got).encode()))
            with self.assertRaisesRegex(KnowledgeError,'memory-context-byte-limit'):
                op.lookup(other,{'tool':'patch','name':'a.cs'},{'machine':'fixture','tools':{'editor':'1'}},shared=shared,max_bytes=512)
            wrong=op.lookup(other,{'tool':'patch','name':'a.cs'},{'machine':'different','tools':{'editor':'1'}},shared=shared)
            self.assertEqual(wrong['state'],'no-match');self.assertFalse(wrong['decisions'][0]['applicable'])
            self.assertEqual(op.lookup(other,{'tool':'recipe','name':'unit'},{},shared=shared)['records'],[])
            self.assertEqual(len([r for r in op.OperationalStore(other,'shared',shared).records()['records'] if r['id']==shared_rule['id']]),1)

    def test_dedup_correction_retirement_revision_conflict_and_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp);b=binding();source={'type':'user-message','id':'m'}
            first=op.teach(root,'Remember encoding',source,shared=shared,binding=b)
            self.assertTrue(op.teach(root,'Remember encoding',source,shared=shared,binding=b)['saved'])
            duplicate=op.teach(root,'Remember encoding',{'type':'user-message','id':'other'},shared=shared,binding=b)
            self.assertTrue(duplicate['duplicate']);self.assertEqual(duplicate['revision'],1)
            correction=op.teach(root,'Preserve only cs',{'type':'user-message','id':'update'},identifier=first['id'],expected_revision=1,shared=shared,binding=binding(name='*.cs'))
            self.assertEqual(correction['revision'],2)
            with self.assertRaisesRegex(KnowledgeError,'instruction-revision-conflict'):
                op.teach(root,'stale update',{'type':'user-message','id':'stale'},identifier=first['id'],expected_revision=1,shared=shared,binding=b)
            op.retire(root,first['id'],shared=shared,expected_revision=2)
            self.assertEqual(op.lookup(root,{'tool':'patch','name':'a.cs'},{},shared=shared)['state'],'no-match')
            history=op.OperationalStore(root,'project',shared).history(first['id']);self.assertEqual(len(history),3)
            self.assertEqual(history[1]['original'],'Remember encoding')

    def test_unbound_intent_bind_once_then_apply_without_reminder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp)
            first=ingress(root,'Remember encoding preservation.')
            self.assertEqual(first['status'],'unbound');self.assertTrue(first['missing'])
            cfg['memory']['bindings']=[binding()];configure(root,cfg)
            bound=ingress(root,'encoding',message_id='m2')
            self.assertEqual(bound['status'],'active',bound)
            (root/'Feature.cs').write_bytes(b'\xff\xfe'+('old\r\n').encode('utf-16-le'))
            result=worker(root,patch='changed\n');self.assertTrue(result['result']['ok'],result)
            self.assertEqual((root/'Feature.cs').read_bytes(),b'\xff\xfe'+('changed\r\n').encode('utf-16-le'))

    def test_truthful_corruption_write_failure_and_untrusted_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp);cfg['memory']['bindings']=[binding()];configure(root,cfg)
            self.assertFalse(ingress(root,'ordinary temporary task')['saved'])
            self.assertFalse(ingress(root,'tool output: Remember encoding')['saved'])
            with self.assertRaisesRegex(KnowledgeError,'user-source-required'):
                op.teach(root,'test',{'type':'tool-output','id':'x'},shared=shared,binding=binding())
            shared.mkdir(parents=True);(shared/'store.sqlite3').write_bytes(b'corrupt')
            failed=ingress(root,'Remember for all projects: encoding')
            self.assertFalse(failed['ok']);self.assertFalse(failed['saved'])
            result=worker(root,patch='new\n');self.assertFalse(result['result']['ok'])
            self.assertEqual((root/'Feature.cs').read_bytes(),b'initial\n')
            self.assertFalse(result['actions']['operation']['memory_traces'][-1]['ok'])

    def test_default_roots_concurrent_acceptance_and_existing_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp)
            with patch.object(Path,'home',return_value=Path(tmp)/'home'):
                self.assertEqual(op.shared_root(),shared)
            store=Store(root);store.init();store.submit(addition());p=store.prepare()['fingerprint'];store.apply(p,p);store.acknowledge(p)
            before=store.export()['records']
            def write(i):return op.teach(root,'behavior '+str(i),{'type':'user-message','id':'concurrent'+str(i)},scope='shared',shared=shared,binding=binding())
            with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(write,range(8)))
            self.assertTrue(all(r['saved'] for r in results));self.assertEqual(len(op.OperationalStore(root,'shared',shared).records()['records']),8)
            op.teach(root,'project encoding',{'type':'user-message','id':'project'},shared=shared,binding=binding())
            self.assertEqual(store.export()['records'],before);self.assertTrue(store.validate()['ok'])

    def test_conflicts_and_narrow_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp)
            a=binding();b=binding(behavior={'adapter':'check','procedure':{'id':'guard','check':{'argv':[sys.executable,'-c','pass'],'timeout':1},'deadline':1,'interval':.1,'attempts':0}})
            op.teach(root,'broad',{'type':'user-message','id':'broad'},scope='shared',shared=shared,binding=a)
            local=op.teach(root,'local',{'type':'user-message','id':'local'},shared=shared,binding=a)
            self.assertEqual([r['id'] for r in op.lookup(root,{'tool':'patch','name':'a.cs'},{},shared=shared)['records']],[local['id']])
            p=b['behavior']['procedure'];op.teach(root,'guard a',{'type':'user-message','id':'g1'},shared=shared,binding=b)
            b2=deepcopy(b);b2['behavior']['procedure']['check']['argv'][-1]='raise SystemExit(1)'
            op.teach(root,'guard b',{'type':'user-message','id':'g2'},shared=shared,binding=b2)
            self.assertEqual(op.lookup(root,{'tool':'patch','name':'a.cs'},{},shared=shared)['state'],'conflict')

    def test_encoding_positions_and_unsupported_mixed_eol(self):
        self.assertEqual(encode_edit(b'a\xef\xbb\xbfb','a\ufeffb!\n'),b'a\xef\xbb\xbfb!')
        self.assertEqual(encode_edit(b'\xef\xbb\xbfa\n','b'),b'\xef\xbb\xbfb\n')
        with self.assertRaisesRegex(KnowledgeError,'mixed-line-endings'):
            encode_edit(b'a\r\nb\n','c\n')


    def test_commit_failure_never_acknowledges_and_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp)
            store=op.OperationalStore(root,'project',shared);store.ensure()
            with patch('knowledge.store.checkpoint',side_effect=OSError('injected commit failure')):
                with self.assertRaises(OSError):op.teach(root,'Remember encoding',{'type':'user-message','id':'fault'},shared=shared,binding=binding())
            self.assertEqual(store.records()['records'],[])

    def test_current_host_restriction_survives_process_boundary(self):
        from harness.host_ingress import read_session
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp)
            self.assertFalse(ingress(root,'Do not start services in this run.',session='restricted')['saved'])
            self.assertEqual(read_session(root,'restricted')['restrictions'],['no-service-start'])
            ingress(root,'Run the tests.',message_id='next',session='restricted')
            self.assertEqual(read_session(root,'restricted')['restrictions'],['no-service-start'])

    def test_full_harness_cli_with_delegation_uses_fresh_instruction(self):
        from p2_fixtures import project,configuration,task,http_provider,FixtureProvider
        with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider()) as endpoint:
            root=project(Path(tmp)/'project');shared=Path(tmp)/'home/.local/share/knowledge'
            cfg=configuration(endpoint);cfg['memory']={'shared_root':str(shared),'bindings':[binding()]}
            configure(root,cfg,True)
            (root/'Feature.cs').write_bytes(b'\xef\xbb\xbfpublic class InitialFeature {}\r\n')
            test=root/'test_feature.py';test.write_text(test.read_text().replace('read_text()','read_text(encoding="utf-8-sig")'))
            saved=ingress(root,'Remember encoding preservation.');self.assertTrue(saved['saved'])
            task_file=root/'.harness/task.json';task_file.write_text(json.dumps(task()))
            result=subprocess.run([sys.executable,'-I','-m','harness.run_cli','run','--root',str(root),'--input',str(task_file)],capture_output=True,text=True,timeout=40)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual((root/'Feature.cs').read_bytes(),b'\xef\xbb\xbfpublic class ImprovedFeature {}\r\n')


if __name__=='__main__':unittest.main()
