"""R2: real ingress/SQLite; intentionally wrong model and Docker doubles."""
import tempfile
import unittest
from knowledge import operations as op
from knowledge.startup_authorization import clauses,DENIAL,startup,restriction
from knowledge.util import KnowledgeError
from harness.runtime import configure
from harness.host_ingress import read_session
from harness.instructions import execute_procedure
from test_persistent_instructions import setup_fixture,ingress
from test_persistent_r1 import dependency
from test_persistent_reviewed import DockerContract
from test_persistent_semantics import decision,local_normalizer

CONFLICTS=[
    ('Remember you may not start the container: You may start it.','You may start it.'),
    ('Запомни не запускай контейнер: Разрешаю запуск этого контейнера.','Разрешаю запуск этого контейнера.')]


class DenialPreservation(unittest.TestCase):
    def test_prefix_denials_remain_observable_and_win_direct_authorization(self):
        _,b=dependency()
        for text,quote in CONFLICTS:
            with self.subTest(text=text):
                self.assertTrue(any(DENIAL.search(c) for c in clauses(text)),clauses(text))
                result=startup(text,b,True,quote)
                self.assertFalse(result['granted'],result);self.assertTrue(result['denied'],result)
                self.assertEqual(restriction(text,'clear-denial'),'deny')

    def test_wrong_normalizer_cannot_persist_prefix_grant_or_start_a_resource(self):
        for text,quote in CONFLICTS:
            with self.subTest(text=text),tempfile.TemporaryDirectory() as tmp,local_normalizer([
                    decision(authorize_recovery=True,permission_quote=quote,current_start='clear-denial',restriction_quote=quote)]) as normalizer:
                root,shared,cfg=setup_fixture(tmp);p,b=dependency()
                cfg['memory'].update(teaching_mode='local-model',normalizer=normalizer,bindings=[b],allowed_procedures=[p],
                    requirements=[{'trigger':{'tool':'recipe','name':'test'},'dependency':'guard'}]);configure(root,cfg)
                saved=ingress(root,text);self.assertTrue(saved.get('saved'),saved)
                record=op.OperationalStore(root,'project',shared).records()['records'][0]
                control=read_session(root,'teaching');contract=DockerContract(root,after_start=True)
                contract.r['current_restrictions']=control['restrictions']
                try:execute_procedure(contract,'operation',record,{'shared_root':str(shared)})
                except KnowledgeError as error:self.assertEqual(error.code,'current-service-start-denied')
                self.assertFalse(contract.starts(),contract.commands)
                self.assertEqual(record['original'],text);self.assertEqual(record['source_text'] or record['original'],text)
                self.assertFalse(record['recovery_authorized'],record);self.assertFalse(saved['recovery_authorized'],saved)
                self.assertEqual(control['restrictions'],['no-service-start'])
                self.assertEqual(saved['restriction'],'no-service-start')
                # Denial must not disable harmless readiness checks or erase intent.
                ready=DockerContract(root,ready=True);execute_procedure(ready,'ready',record,{'shared_root':str(shared)})
                self.assertTrue(ready.commands);self.assertFalse(ready.starts())

    def test_conflicting_prefix_cannot_clear_previously_saved_session_denial(self):
        for text,quote in [
            ('Remember you may not start the container: You may start services again for this run.','You may start services again for this run.'),
            ('Запомни не запускай контейнер: Разрешаю снова запуск сервисов в этом запуске.','Разрешаю снова запуск сервисов в этом запуске.')]:
            with self.subTest(text=text),tempfile.TemporaryDirectory() as tmp,local_normalizer([
                    decision(intent='none',binding=None,current_start='deny',restriction_quote='Do not start services in this run.'),
                    decision(intent='none',binding=None,current_start='clear-denial',restriction_quote=quote)]) as normalizer:
                root,shared,cfg=setup_fixture(tmp);cfg['memory'].update(teaching_mode='local-model',normalizer=normalizer);configure(root,cfg)
                ingress(root,'Do not start services in this run.')
                saved=ingress(root,text,message_id='conflicting-clear')
                self.assertTrue(saved['ok'],saved);self.assertEqual(saved['restriction'],'no-service-start')
                self.assertEqual(read_session(root,'teaching')['restrictions'],['no-service-start'])

    def test_unknown_teaching_wrapper_preserves_conditions_and_cannot_grant_or_clear(self):
        _,b=dependency()
        for wrapper in ('Remember only after approval','Запомни только после согласования','Remember Kafka only on Tuesdays'):
            for separator in (' ', ' Check readiness. '):
                with self.subTest(wrapper=wrapper,separator=separator):
                    text=wrapper+':'+separator+'You may start it.'
                    self.assertTrue(any(wrapper in c for c in clauses(text)),clauses(text))
                    self.assertFalse(startup(text,b,True,'You may start it.')['granted'])
            self.assertEqual(restriction(wrapper+': You may start services again.','clear-denial'),'unchanged')

    def test_ordinary_and_shared_wrappers_keep_positive_start_and_never_restart(self):
        _,b=dependency()
        for wrapper in ('Remember','Remember Kafka','Запомни','Запомни Kafka',
                'Remember for all projects','Remember for all projects using local Kafka',
                'Remember for all projects using my local Kafka environment',
                'Запомни для всех проектов с этой локальной Kafka'):
            with self.subTest(wrapper=wrapper):
                quote='You may start container fixture if stopped'
                text=wrapper+': '+quote+'; never restart a running container.'
                result=startup(text,b,True,quote)
                self.assertTrue(result['granted'],result);self.assertFalse(result['denied'],result)
        russian='Разрешаю запуск этого контейнера, если он остановлен'
        self.assertTrue(startup('Запомни Kafka: '+russian+'; никогда не перезапускай работающий контейнер.',b,True,russian)['granted'])
        for name in ('Fixture','other'):
            quote='You may start container '+name+'.'
            self.assertFalse(startup('Remember Kafka: '+quote,b,True,quote)['granted'])
        self.assertEqual(restriction('You may start services again.','clear-denial'),'clear-denial')


if __name__=='__main__':unittest.main()
