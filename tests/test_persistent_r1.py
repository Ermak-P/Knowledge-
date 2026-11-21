"""R1 regressions: real ingress/storage/resume; explicit model/Docker doubles."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from knowledge import operations as op
from knowledge.util import KnowledgeError
from harness import engine,run_cli,runtime
from harness.instructions import execute_procedure
from harness.host_ingress import read_session
from harness.tools import Broker
from p2_fixtures import project,configuration,task,http_provider,FixtureProvider
from test_persistent_instructions import setup_fixture,binding,ingress
from test_persistent_semantics import decision,local_normalizer,template
from test_persistent_reviewed import procedure,DockerContract


class InterruptedWorker(BaseException):pass


def dependency():
    p=procedure();p.update(attempts=1,docker={'executable':sys.executable,'container':'fixture'})
    return p,binding('Kafka','dependency','guard',{'adapter':'dependency','procedure':p})


def cli(*args):
    out=io.StringIO()
    with patch.object(sys,'argv',['harness-run',*map(str,args)]),redirect_stdout(out):code=run_cli.main()
    return code,json.loads(out.getvalue())


class ResumeControls(unittest.TestCase):
    def pause(self,root,phase,tool,restrictions=None):
        def interrupt(where):
            if where==phase and any(a['tool']==tool and (tool!='recipe' or a['args']['name']=='test')
                    for r in runtime.Journal(root).runs() for a in runtime.Journal(root).actions(r['id']).values()):
                raise InterruptedWorker()
        with patch('harness.runtime.fault',side_effect=interrupt),self.assertRaises(InterruptedWorker):
            engine.start(root,task(),current_restrictions=restrictions)
        return runtime.Journal(root).runs()[0]['id']

    def test_cli_hands_both_controls_to_resume_and_rejects_other_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            changes=Path(tmp)/'format.json';changes.write_text('[{"path":"Feature.cs","bom":false}]')
            with patch('harness.run_cli.resume',return_value={'ok':True}) as recorded:
                self.assertEqual(cli('resume','--root',tmp,'--run-id','saved','--no-service-start','--format-input',changes)[0],0)
                self.assertEqual(recorded.call_args.kwargs,{'current_restrictions':['no-service-start'],
                    'format_changes':[{'path':'Feature.cs','bom':False}]})
            for command,control in [('status',['--no-service-start']),('capture-retry',['--format-input',changes])]:
                code,result=cli(command,'--root',tmp,'--run-id','saved',*control)
                self.assertEqual(code,1);self.assertEqual(result['error'],'current-controls-unsupported-command')

    def test_resume_no_start_persisted_before_pending_dependency_and_omission_preserves_it(self):
        for saved_restriction in (False,True):
            with self.subTest(saved=saved_restriction),tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider()) as endpoint:
                root=project(tmp);cfg=configuration(endpoint);cfg['capture']='off';p,b=dependency()
                shared=Path(tmp)/'shared';cfg['memory']={'shared_root':str(shared),'bindings':[b],'allowed_procedures':[p],
                    'teaching_mode':'catalog','requirements':[{'trigger':{'tool':'recipe','name':'test'},'dependency':'guard'}]}
                runtime.configure(root,cfg)
                saved=op.teach(root,'Allow the configured stopped fixture.',{'type':'user-message','id':'grant'},shared=shared,binding=b,recovery_authorized=True)
                rid=self.pause(root,'tool-intent','recipe',['no-service-start'] if saved_restriction else None)
                contract=DockerContract(root,after_start=True)
                def command(broker,*args,**kwargs):
                    # Assert this is durable before even the first readiness check.
                    self.assertIn('no-service-start',runtime.Journal(root).load(rid)['current_restrictions'])
                    return contract.memory_command(*args,**kwargs)
                with patch.object(Broker,'memory_command',command):
                    cli('resume','--root',root,'--run-id',rid,*([] if saved_restriction else ['--no-service-start']))
                journal=runtime.Journal(root);run=journal.load(rid)
                self.assertIn('no-service-start',run['current_restrictions']);self.assertEqual(run['id'],rid)
                results=[a.get('result',{}) for a in journal.actions(rid).values()]
                self.assertIn('current-service-start-denied',[a.get('error') for a in results])
                self.assertTrue(contract.commands);self.assertFalse(contract.starts())
                self.assertTrue(next(r for r in op.OperationalStore(root,'project',shared).records()['records'] if r['id']==saved['id'])['recovery_authorized'])

    def test_resume_format_before_intent_changes_bytes_without_changing_default(self):
        with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider()) as endpoint:
            root=project(tmp);cfg=configuration(endpoint);cfg['capture']='off';shared=Path(tmp)/'shared'
            cfg['memory']={'shared_root':str(shared),'bindings':[binding()],'allowed_procedures':[],'teaching_mode':'catalog'}
            runtime.configure(root,cfg);saved=op.teach(root,'Preserve encoding.',{'type':'user-message','id':'format'},shared=shared,binding=binding())
            (root/'Feature.cs').write_bytes(b'\xef\xbb\xbfpublic class InitialFeature {}\r\n')
            rid=self.pause(root,'tool-intent','patch')
            changes=root/'.harness/resume-format.json';changes.write_text('[{"path":"Feature.cs","encoding":"utf-8","bom":false,"eol":"lf"}]')
            code,result=cli('resume','--root',root,'--run-id',rid,'--format-input',changes)
            self.assertEqual(code,0,result)
            self.assertEqual((root/'Feature.cs').read_bytes(),b'public class ImprovedFeature {}\n')
            current=op.OperationalStore(root,'project',shared).records()['records'][0]
            self.assertEqual((current['id'],current['revision']),(saved['id'],1))

    def test_resume_incompatible_format_after_intent_or_write_rejected_without_writes(self):
        for phase in ('edit-intent','edit-file-written'):
            with self.subTest(phase=phase),tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider()) as endpoint:
                root=project(tmp);cfg=configuration(endpoint);cfg['capture']='off';runtime.configure(root,cfg)
                rid=self.pause(root,phase,'patch');before=(root/'Feature.cs').read_bytes();mtime=(root/'Feature.cs').stat().st_mtime_ns
                changes=root/'.harness/resume-format.json';changes.write_text('[{"path":"Feature.cs","bom":true}]')
                count=len(runtime.Journal(root).load(rid)['requests'])
                code,result=cli('resume','--root',root,'--run-id',rid,'--format-input',changes)
                self.assertEqual(code,1);self.assertEqual(result['error'],'resume-format-conflicts-with-edit-intent')
                self.assertEqual((root/'Feature.cs').read_bytes(),before);self.assertEqual((root/'Feature.cs').stat().st_mtime_ns,mtime)
                self.assertEqual(len(runtime.Journal(root).load(rid)['requests']),count)
                resumed=engine.resume(root,rid);self.assertTrue(resumed['ok'],resumed)


class StartupAuthorization(unittest.TestCase):
    def exercise(self,text,quote,expected=False,ready=False):
        with tempfile.TemporaryDirectory() as tmp,local_normalizer([decision(summary='Check Kafka and start only if authorized.',
                authorize_recovery=True,permission_quote=quote)]) as normalizer:
            root,shared,cfg=setup_fixture(tmp);p,b=dependency()
            cfg['memory'].update(teaching_mode='local-model',normalizer=normalizer,bindings=[b],allowed_procedures=[p],
                requirements=[{'trigger':{'tool':'recipe','name':'test'},'dependency':'guard'}]);runtime.configure(root,cfg)
            saved=ingress(root,text);self.assertTrue(saved.get('saved'),saved)
            record=op.OperationalStore(root,'project',shared).records()['records'][0]
            self.assertEqual(record['original'],text)
            contract=DockerContract(root,ready=ready,after_start=True)
            if record['recovery_authorized'] or ready:execute_procedure(contract,'operation',record,{'shared_root':str(shared)})
            else:
                with self.assertRaisesRegex(KnowledgeError,'remembered-start-not-authorized'):
                    execute_procedure(contract,'operation',record,{'shared_root':str(shared)})
            self.assertEqual(len(contract.starts()),int(expected and not ready))
            self.assertEqual(record['recovery_authorized'],expected,saved);self.assertEqual(saved['recovery_authorized'],expected)
            self.assertTrue(contract.commands)
            return saved

    def test_wrong_normalizer_cannot_promote_english_or_russian_denials(self):
        for text,quote in [
            ('Remember Kafka: you may not start the container. Only check readiness.','you may not start the container'),
            ('Remember Kafka: do not start the container.','do not start the container'),
            ('Запомни Kafka: не запускай контейнер.','не запускай контейнер'),
            ('Запомни Kafka: запуск контейнера запрещён.','запуск контейнера запрещён')]:
            with self.subTest(text=text):self.exercise(text,quote)

    def test_wrong_normalizer_cannot_promote_quotes_examples_past_or_conditional_permission(self):
        for text,quote in [
            ('Remember Kafka: example: You may start container fixture.','You may start container fixture.'),
            ('Remember Kafka: "You may start container fixture."','You may start container fixture.'),
            ('Remember Kafka: yesterday you may start container fixture was the instruction.','you may start container fixture'),
            ('Remember Kafka: the earlier start of container fixture succeeded.','the earlier start of container fixture succeeded'),
            ('Remember Kafka: You may start container fixture if I approve later.','You may start container fixture'),
            ('Remember Kafka: You may start container other.','You may start container other.'),
            ('Remember Kafka: You may start container Fixture.','You may start container Fixture.'),
            ('Запомни Kafka: пример: Разрешаю запуск этого контейнера.','Разрешаю запуск этого контейнера.'),
            ('Remember Kafka: You may start container fixture. Do not start the container.','You may start container fixture.')]:
            with self.subTest(text=text):self.exercise(text,quote)

    def test_positive_start_and_never_restart_are_distinct_and_readiness_remains_available(self):
        for text,quote in [
            ('Remember Kafka: You may start container fixture.','You may start container fixture.'),
            ('Remember Kafka: You may start it if stopped; never restart a running container.','You may start it if stopped'),
            ('Запомни Kafka: Разрешаю запуск этого контейнера, если он остановлен; никогда не перезапускай работающий контейнер.','Разрешаю запуск этого контейнера, если он остановлен')]:
            with self.subTest(text=text):self.exercise(text,quote,expected=True)
        self.exercise('Remember Kafka: do not start the container.','do not start the container',ready=True)

    def test_positive_grant_survives_fresh_process_without_normalizer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp);p,b=dependency()
            with local_normalizer([decision(authorize_recovery=True,permission_quote='You may start container fixture.')]) as normalizer:
                cfg['memory'].update(teaching_mode='local-model',normalizer=normalizer,bindings=[b],allowed_procedures=[p]);runtime.configure(root,cfg)
                saved=ingress(root,'Remember Kafka: You may start container fixture.')
            code='from knowledge.operations import OperationalStore; import json; print(json.dumps(OperationalStore('+repr(str(root))+',"project",'+repr(str(shared))+').records()))'
            fresh=subprocess.run([sys.executable,'-I','-c',code],capture_output=True,text=True,timeout=10,check=True)
            record=json.loads(fresh.stdout)['records'][0]
            self.assertTrue(record['recovery_authorized'],saved);self.assertEqual((record['id'],record['revision']),(saved['id'],1))
            contract=DockerContract(root,after_start=True);execute_procedure(contract,'operation',record,{'shared_root':str(shared)})
            self.assertEqual(len(contract.starts()),1)

    def test_wrong_model_cannot_clear_current_prohibition(self):
        for text in ('Do not start services in this run.','В этом запуске не запускай контейнер.'):
            for modeled in ('clear-denial','unchanged'):
                with self.subTest(text=text,modeled=modeled),tempfile.TemporaryDirectory() as tmp,local_normalizer([
                        decision(intent='none',binding=None,current_start=modeled,restriction_quote=text if modeled!='unchanged' else '')]) as normalizer:
                    root,shared,cfg=setup_fixture(tmp);cfg['memory'].update(teaching_mode='local-model',normalizer=normalizer);runtime.configure(root,cfg)
                    result=ingress(root,text);self.assertTrue(result['ok'],result)
                    self.assertEqual(result['restriction'],'no-service-start');self.assertEqual(read_session(root,'teaching')['restrictions'],['no-service-start'])

    def test_observation_cannot_clear_previously_saved_current_denial(self):
        denial='Do not start services in this run.';observation='The earlier start of the container succeeded.'
        with tempfile.TemporaryDirectory() as tmp,local_normalizer([
                decision(intent='none',binding=None,current_start='deny',restriction_quote=denial),
                decision(intent='none',binding=None,current_start='clear-denial',restriction_quote=observation)]) as normalizer:
            root,shared,cfg=setup_fixture(tmp);cfg['memory'].update(teaching_mode='local-model',normalizer=normalizer);runtime.configure(root,cfg)
            self.assertTrue(ingress(root,denial)['ok'])
            self.assertTrue(ingress(root,observation,message_id='observation')['ok'])
            self.assertEqual(read_session(root,'teaching')['restrictions'],['no-service-start'])

    def test_deictic_grant_is_not_manufactured_for_ambiguous_catalog(self):
        with tempfile.TemporaryDirectory() as tmp,local_normalizer([decision(authorize_recovery=True,
                permission_quote='You may start it if stopped.')]) as normalizer:
            root,shared,cfg=setup_fixture(tmp);p,b=dependency();other=deepcopy(b)
            other['behavior']['procedure']['docker']['container']='other';other['behavior']['procedure']['id']='other'
            other['trigger']['name']='other';cfg['memory'].update(teaching_mode='local-model',normalizer=normalizer,bindings=[b,other])
            runtime.configure(root,cfg);saved=ingress(root,'Remember Kafka: You may start it if stopped.')
            self.assertTrue(saved['saved'],saved);self.assertFalse(saved['recovery_authorized'],saved)

    def test_old_quote_cannot_revive_revocation_or_grant_changed_resource(self):
        positive='You may start container first.'
        answers=[decision(authorize_recovery=True,permission_quote=positive,parameters={'container':'first','port':19092},parameter_quotes={'container':'container first','port':'port 19092'}),
            decision(intent='update',authorize_recovery=True,permission_quote=positive),
            decision(intent='update',authorize_recovery=True,permission_quote=positive,parameters={'container':'second'},parameter_quotes={'container':'container second'})]
        with tempfile.TemporaryDirectory() as tmp,local_normalizer(answers) as normalizer:
            root,shared,cfg=setup_fixture(tmp);t=template();cfg['memory'].update(teaching_mode='local-model',normalizer=normalizer,procedure_templates=[t],allowed_templates=[t['id']],
                bindings=[{'aliases':['Kafka'],'trigger':{'tool':'dependency','name':'local_broker'},'template':t['id']}]);runtime.configure(root,cfg)
            first=ingress(root,'Remember Kafka container first and port 19092. '+positive);self.assertTrue(first['recovery_authorized'])
            revoked=ingress(root,'For future runs do not start the container.',message_id='revoke')
            self.assertTrue(revoked.get('saved'),revoked);self.assertFalse(revoked['recovery_authorized'],revoked)
            moved=ingress(root,'For future runs use container second.',message_id='move')
            self.assertTrue(moved.get('saved'),moved);self.assertFalse(moved['recovery_authorized'],moved)
            row=op.OperationalStore(root,'project',shared).records()['records'][0]
            self.assertEqual(row['id'],first['id']);self.assertTrue(row['authorization_revoked'])


if __name__=='__main__':unittest.main()
