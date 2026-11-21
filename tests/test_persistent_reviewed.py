"""Reviewed A17-A20 boundaries: real stores/processes; labelled Docker doubles."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid
from knowledge import operations as op
from knowledge import bindings
from knowledge.util import KnowledgeError
from harness.instructions import execute_procedure
from harness.runtime import configure,Journal
from test_persistent_instructions import setup_fixture,binding,ingress,worker
from test_persistent_semantics import local_normalizer,decision


def procedure(script=None):
    return {'id':'guard','check':{'argv':[sys.executable,str(script)] if script else [sys.executable,'-c','pass'],'timeout':2},
        'deadline':1,'interval':.05,'attempts':0}


class DockerContract:
    """Owned-command response contract only; no Docker/real-host claim."""
    def __init__(self,root,ready=False,after_start=False,daemon='daemon-a',resource='a'*64):
        self.root=root;self.ready=ready;self.after_start=after_start;self.daemon=daemon;self.resource=resource;self.commands=[];self.action={}
        self.j=SimpleNamespace(project=SimpleNamespace(root=root),action=self.action_io,cancelled=lambda _:False)
        self.r={'id':uuid.uuid4().hex,'started':time.time()};self.limits={'elapsed_seconds':30}
    def action_io(self,run,identifier,value=None):
        if value is not None:self.action=deepcopy(value)
        return deepcopy(self.action)
    def memory_command(self,identifier,argv,timeout,rerun_safe,parent_id,record_id):
        self.commands.append(argv)
        if '-probe' in identifier:ok=self.ready;output=''
        elif identifier.endswith('docker-info'):ok=True;output=json.dumps({'ID':self.daemon,'Version':'contract'})
        elif identifier.endswith('docker-inspect'):ok=True;output=json.dumps({'ID':self.resource,'Running':False,'Status':'exited'})
        elif identifier.endswith('-start'):self.ready=self.after_start;ok=True;output=self.resource
        else:raise AssertionError(identifier)
        return {'ok':ok,'output':output,'returncode':0 if ok else 1,'reason':None,'log':'contract-only'}
    def starts(self):return [a for a in self.commands if 'start' in a]


class ReviewedInstructions(unittest.TestCase):
    def test_unlinked_dependency_ack_does_not_promise_current_host_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp);p=procedure()
            cfg['memory'].update(bindings=[binding('dependency','dependency','guard',{'adapter':'check','procedure':p})],allowed_procedures=[p]);configure(root,cfg)
            saved=ingress(root,'Remember dependency before its required tests.')
            self.assertTrue(saved['saved']);self.assertFalse(saved['executable']);self.assertEqual(saved['execution_state'],'unlinked')
            self.assertEqual(op.OperationalStore(root,'project',shared).records()['records'][0]['original'],'Remember dependency before its required tests.')

    def test_verified_automatic_suite_metadata_selects_only_declared_dependency(self):
        from harness import testing
        from harness.instructions import retrieve
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp)
            for path in ('integration/NeedsTests.csproj','unit/OtherTests.csproj'):
                p=root/path;p.parent.mkdir();p.write_text('<Project/>')
            p=procedure();b=binding('dependency','dependency','guard',{'adapter':'check','procedure':p})
            saved=op.teach(root,'Check this dependency before its declared suite.',{'type':'user-message','id':'suite'},scope='shared',shared=shared,binding=b)
            cfg['memory']['requirements']=[{'trigger':{'tool':'recipe','name':'@automatic-tests/*'},'suite':'integration/*Tests.csproj','dependency':'guard'}]
            r={'automatic_tests':{'inventory':testing.discover(root),'operations':{}}}
            journal=SimpleNamespace(project=SimpleNamespace(root=root),save=lambda _:None)
            broker=SimpleNamespace(c=cfg,r=r,j=journal)
            for path,phase,wanted in [('integration/NeedsTests.csproj','restore',False),('unit/OtherTests.csproj','test',False),('integration/NeedsTests.csproj','test',True)]:
                name=testing.register(journal,r,'generation',path,phase,'net10.0')
                _,_,records,trace=retrieve(broker,'recipe',{'name':name})
                self.assertEqual(bool(records),wanted,(path,phase,trace))
                if wanted:
                    self.assertEqual(records[0]['id'],saved['id']);self.assertEqual(trace['dependency_links'][0]['source'],'verified-test-inventory')
                    self.assertEqual(trace['dependency_links'][0]['suite'],path)

    def test_committed_intent_replay_recovers_missing_host_pending_pointer(self):
        from harness.host_ingress import session_path,write_session
        with tempfile.TemporaryDirectory() as tmp,local_normalizer([
            decision(unsupported=['local normalization needs retry'],question='Which supported binding?'),decision()]) as normalizer:
            root,shared,cfg=setup_fixture(tmp);cfg['memory'].update(teaching_mode='local-model',normalizer=normalizer,bindings=[binding()]);configure(root,cfg)
            saved=ingress(root,'Remember encoding preservation.')
            self.assertEqual(saved['status'],'unbound')
            # Model a host death after the SQLite commit but before pending state.
            path=session_path(root,'teaching');value=json.loads(path.read_text());value.pop('pending_instruction');write_session(path,value)
            retried=ingress(root,'Remember encoding preservation.')
            self.assertEqual(retried['id'],saved['id']);self.assertEqual(retried['status'],'active')
            replay=ingress(root,'Remember encoding preservation.')
            self.assertEqual(replay['id'],saved['id']);self.assertTrue(replay['duplicate'])
            self.assertEqual(replay['revision'],retried['revision'])
            self.assertEqual(len(op.OperationalStore(root,'project',shared).records()['records']),1)

    def test_shared_teaching_without_project_init_and_corrupt_existing_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp);cfg['memory']['bindings']=[binding()];configure(root,cfg)
            saved=ingress(root,'Remember for all projects: encoding preservation.')
            self.assertEqual(saved['scope'],'shared');self.assertTrue(saved['executable'])
            self.assertFalse((root/'.knowledge').exists())
            other=Path(tmp)/'other';other.mkdir()
            got=op.lookup(other,{'tool':'patch','name':'Feature.cs'},{},shared=shared)
            self.assertEqual(got['stores']['project'],'absent');self.assertEqual(got['records'][0]['id'],saved['id'])
            self.assertFalse((other/'.knowledge').exists())
            (other/'.knowledge').mkdir();(other/'.knowledge/store.sqlite3').write_bytes(b'corrupt existing')
            with self.assertRaises(KnowledgeError):op.lookup(other,{'tool':'patch','name':'Feature.cs'},{},shared=shared)
            self.assertEqual((other/'.knowledge/store.sqlite3').read_bytes(),b'corrupt existing')

    def test_changed_script_blocks_effect_and_explicit_rebind_preserves_intent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp);script=root/'guard.py';script.write_text('pass\n')
            p=procedure(script);b=binding('guard','recipe','test',{'adapter':'check','procedure':p})
            cfg['memory'].update(bindings=[b],allowed_procedures=[p]);configure(root,cfg)
            saved=ingress(root,'Remember guard before tests.');self.assertTrue(saved['executable'],saved)
            script.write_text('from pathlib import Path\nPath(".guard-ran").touch()\n')
            result=worker(root);self.assertEqual(result['result'].get('error'),'instruction-binding-stale',result)
            self.assertFalse((root/'.guard-ran').exists())
            store=op.OperationalStore(root,'project',shared);old=store.records()['records'][0]
            self.assertEqual(old['original'],'Remember guard before tests.');self.assertEqual(old['status'],'active')
            repaired=op.rebind(root,old['id'],'Revalidate the installed guard.',{'type':'user-message','id':'rebind'},
                shared=shared,expected_revision=1)
            self.assertEqual(repaired['id'],saved['id']);self.assertEqual(repaired['revision'],2)
            run=worker(root);self.assertTrue(run['result']['ok'],run);self.assertTrue((root/'.guard-ran').exists())
            self.assertEqual(store.history(old['id'])[1]['original'],old['original'])

    def test_other_execution_environment_blocks_before_any_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp);p=procedure();b=binding('guard','recipe','test',{'adapter':'check','procedure':p})
            cfg['memory'].update(bindings=[b],allowed_procedures=[p]);configure(root,cfg)
            with patch('knowledge.bindings.host',return_value={'machine':'different','os':sys.platform,'context':'other'}):
                saved=op.teach(root,'guard for this execution environment',{'type':'user-message','id':'env'},shared=shared,binding=b)
            result=worker(root);self.assertEqual(result['result'].get('error'),'instruction-binding-environment-changed',result)
            self.assertFalse(any(a.get('memory_parent') for a in result['actions'].values()))
            self.assertEqual(op.OperationalStore(root,'project',shared).records()['records'][0]['id'],saved['id'])

    def test_failed_startup_not_repeated_in_fresh_run_and_rebind_resets_only_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp);p=procedure();p.update(attempts=1,docker={'executable':sys.executable,'container':'fixture'})
            b=binding('dependency','dependency','guard',{'adapter':'dependency','procedure':p})
            saved=op.teach(root,'Start only this stopped existing fixture.',{'type':'user-message','id':'teach'},shared=shared,binding=b,recovery_authorized=True)
            store=op.OperationalStore(root,'project',shared);record=store.records()['records'][0]
            first=DockerContract(root)
            with self.assertRaisesRegex(KnowledgeError,'dependency-readiness-timeout'):execute_procedure(first,'operation',record,{'shared_root':str(shared)})
            self.assertEqual(len(first.starts()),1);self.assertEqual(first.starts()[0][-1],'a'*64)
            state=store.records()['bindings'][record['id']];self.assertEqual(state['state'],'blocked')
            fresh=DockerContract(root)
            with self.assertRaisesRegex(KnowledgeError,'memory-remedy-blocked'):execute_procedure(fresh,'operation',record,{'shared_root':str(shared)},state)
            self.assertEqual(len(fresh.commands),1);self.assertFalse(fresh.starts())
            fixed=op.rebind(root,record['id'],'Revalidate the existing resource and permit startup.',{'type':'user-message','id':'repair'},shared=shared,expected_revision=1,recovery_authorized=True)
            self.assertEqual(fixed['id'],saved['id']);self.assertNotIn(record['id'],store.records()['bindings'])
            ready=DockerContract(root,after_start=True)
            execute_procedure(ready,'operation',store.records()['records'][0],{'shared_root':str(shared)})
            self.assertEqual(len(ready.starts()),1);self.assertEqual(store.records()['bindings'][record['id']]['state'],'verified')
            self.assertEqual(store.records()['records'][0]['original'],record['original'])

    def test_changed_daemon_or_container_identity_requires_rebind(self):
        for field in ('daemon','resource'):
            with self.subTest(field=field),tempfile.TemporaryDirectory() as tmp:
                root,shared,cfg=setup_fixture(tmp);p=procedure();p.update(attempts=1,docker={'executable':sys.executable,'container':'fixture'})
                saved=op.teach(root,'One exact fixture only.',{'type':'user-message','id':'teach'},shared=shared,
                    binding=binding('dependency','dependency','guard',{'adapter':'dependency','procedure':p}),recovery_authorized=True)
                store=op.OperationalStore(root,'project',shared);record=store.records()['records'][0]
                execute_procedure(DockerContract(root,after_start=True),'operation',record,{'shared_root':str(shared)})
                state=store.records()['bindings'][record['id']]
                changed=DockerContract(root,**{field:'daemon-b' if field=='daemon' else 'b'*64})
                with self.assertRaisesRegex(KnowledgeError,'docker-'+field+'-changed'):execute_procedure(changed,'operation',record,{'shared_root':str(shared)},state)
                self.assertFalse(changed.starts())
                with self.assertRaisesRegex(KnowledgeError,'instruction-binding-revalidation-required'):
                    execute_procedure(DockerContract(root,ready=True),'operation',record,{'shared_root':str(shared)},store.records()['bindings'][record['id']])

    def test_non_ascii_intended_edit_and_untouched_content_bom_no_bom_final_newline(self):
        before='// Привет Ω\nclass Unchanged {}\nclass Old {}'
        for signature,codec,eol,final in [(b'','utf-8','\n',False),(b'\xef\xbb\xbf','utf-8','\r\n',True),(b'\xff\xfe','utf-16-le','\r\n',False)]:
            with self.subTest(codec=codec,bom=signature),tempfile.TemporaryDirectory() as tmp:
                root,shared,cfg=setup_fixture(tmp);cfg['memory']['bindings']=[binding()];configure(root,cfg)
                def raw(text):return signature+(text.replace('\n',eol)+(eol if final else '')).encode(codec)
                (root/'Feature.cs').write_bytes(raw(before))
                self.assertTrue(ingress(root,'Remember encoding preservation.')['saved'])
                changed=before.replace('class Old','class New')
                result=worker(root,patch=changed+'\n');self.assertTrue(result['result']['ok'],result)
                self.assertEqual((root/'Feature.cs').read_bytes(),raw(changed))

    def test_unsupported_host_trigger_remains_intent_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp);cfg['memory']['bindings']=[binding('custom shell','shell','*')];configure(root,cfg)
            saved=ingress(root,'Remember custom shell for future work.')
            self.assertEqual(saved['status'],'unbound',saved);self.assertFalse(saved['executable'])

    def test_compose_identity_and_local_context_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp);compose=root/'compose.yml';compose.write_text('services: {}\n')
            p=procedure();p['docker']={'executable':sys.executable,'compose_file':str(compose),'service':'fixture'}
            self.assertEqual(bindings.snapshot({'adapter':'dependency','procedure':p},root)['reason'],'compose-identity-required')
            env=root/'fixture.env';env.write_text('')
            p['docker'].update(project_name='fixture-project',env_file=str(env))
            saved=bindings.snapshot({'adapter':'dependency','procedure':p},root);self.assertEqual(saved['state'],'bound')
            compose.write_text('services: {changed: {}}\n')
            with self.assertRaisesRegex(KnowledgeError,'instruction-binding-stale'):bindings.validate_saved(saved,{'adapter':'dependency','procedure':p},root)


if __name__=='__main__':unittest.main()
