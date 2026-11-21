"""Local-model protocol doubles plus actual ingress/broker processes.

These are contract/integration tests, NOT real local-model or OpenCode A02 proof.
"""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from knowledge import operations as op
from knowledge.normalizer import normalize,validate
from knowledge.util import KnowledgeError,canonical_json
from harness.runtime import configure
from harness.host_ingress import read_session
from p2_fixtures import http_provider
from test_persistent_instructions import setup_fixture,binding,ingress,worker


def decision(**changes):
    result={'version':1,'intent':'teach','scope':'project','scope_explicit':False,'scope_quote':'',
        'binding':0,'summary':'Preserve the existing byte format when editing files.',
        'applicability':{},'authorize_recovery':False,'permission_quote':'',
        'revoke_recovery':False,'revocation_quote':'','parameters':{},'parameter_quotes':{},
        'format_changes':[],'format_quote':'','unsupported':[],'question':None,
        'current_start':'unchanged','restriction_quote':''}
    result.update(changes);return result


@contextmanager
def local_normalizer(answers,requests=None):
    answers=iter(answers)
    def raw(body):
        if requests is not None:requests.append(body)
        return {'choices':[{'message':{'content':canonical_json(next(answers))}}],
            'usage':{'prompt_tokens':11,'completion_tokens':7,'total_tokens':18,'private':'must not persist'}}
    with http_provider(None,raw=raw) as endpoint:
        yield {'endpoint':endpoint,'model':'semantic-fixture','evidence':'test-double','timeout':2}


def template():
    # Data binding only in unit tests; this executable is never used as Docker.
    return {'id':'fixture_kafka','kind':'docker-kafka-existing','procedure_id':'local_broker',
        'python':sys.executable,'docker':sys.executable,'defaults':{'host':'127.0.0.1'},
        'deadline':3,'interval':.1,'attempts':1,'check_timeout':2,'probe_timeout':1}


class PersistentSemantics(unittest.TestCase):
    def test_unseen_wording_captured_then_applied_without_model_or_transcript(self):
        requests=[]
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp)
            with local_normalizer([decision()],requests) as normalizer:
                cfg['memory'].update(teaching_mode='local-model',normalizer=normalizer,bindings=[binding()]);configure(root,cfg)
                (root/'Feature.cs').write_bytes(b'\xef\xbb\xbfinitial\r\n')
                text='During future edits, keep the current byte representation of these files.'
                saved=ingress(root,text);self.assertTrue(saved.get('saved'),saved)
                record=op.OperationalStore(root,'project',shared).records()['records'][0]
                self.assertEqual(record['original'],text);self.assertEqual(record['technical']['normalization']['evidence'],'test-double')
                self.assertNotIn('private',record['technical']['normalization']['usage'])
            # The teacher process and its local normalization endpoint have ended.
            result=worker(root,patch='changed\n');self.assertTrue(result['result']['ok'],result)
            self.assertEqual((root/'Feature.cs').read_bytes(),b'\xef\xbb\xbfchanged\r\n')
            self.assertEqual(len(requests),1)

    def test_unrepresentable_condition_blocks_old_broader_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp)
            p={'id':'local_broker','check':{'argv':[sys.executable,'-c','from pathlib import Path; Path(".must-not-run").touch()'],'timeout':2},'deadline':3,'interval':.1,'attempts':1}
            b=binding('Kafka','dependency','local_broker',{'adapter':'dependency','procedure':p})
            op.teach(root,'broad default',{'type':'user-message','id':'broad'},scope='shared',shared=shared,binding=b,recovery_authorized=True)
            result=decision(summary='Start Kafka only during the maintenance window.',unsupported=['maintenance-window guard is not expressible'],question='Which approved guard verifies that maintenance window?')
            with local_normalizer([result]) as normalizer:
                cfg['memory'].update(teaching_mode='local-model',normalizer=normalizer,bindings=[b],allowed_procedures=[p],requirements=[{'trigger':{'tool':'recipe','name':'test'},'dependency':'local_broker'}]);configure(root,cfg)
                saved=ingress(root,'Remember Kafka: only during the maintenance window.')
                self.assertEqual(saved['status'],'unbound',saved)
            run=worker(root);self.assertEqual(run['result'].get('error'),'instruction-binding-required',run)
            self.assertFalse((root/'.must-not-run').exists())
            self.assertFalse(any(a.get('memory_parent') for a in run['actions'].values()))

    def test_missing_resource_details_bound_once_without_reteaching_or_config_edit(self):
        first='Remember for all projects using local Kafka: check readiness before required tests. You may start that specific local container.'
        reply='Use container knowledge-fixture and port 19092.'
        a=decision(scope='shared',scope_explicit=True,scope_quote='all projects',authorize_recovery=True,
            permission_quote='You may start that specific local container.',summary='Check Kafka, start only its stopped existing container if needed.',
            question='What are the configured container name and port?')
        b=decision(intent='clarify',scope='shared',summary=a['summary'],parameters={'container':'knowledge-fixture','port':19092},
            parameter_quotes={'container':'container knowledge-fixture','port':'port 19092'})
        with tempfile.TemporaryDirectory() as tmp,local_normalizer([a,b]) as normalizer:
            root,shared,cfg=setup_fixture(tmp)
            cfg['memory'].update(teaching_mode='local-model',normalizer=normalizer,procedure_templates=[template()],allowed_templates=[],
                bindings=[{'aliases':['Kafka'],'trigger':{'tool':'dependency','name':'local_broker'},'template':'fixture_kafka'}],
                requirements=[{'trigger':{'tool':'recipe','name':'test'},'dependency':'local_broker'}]);configure(root,cfg)
            saved=ingress(root,first);self.assertEqual(saved['status'],'unbound',saved);self.assertTrue(saved['question'])
            bound=ingress(root,reply,message_id='resource-details');self.assertEqual(bound['status'],'active',bound)
            self.assertFalse(bound['executable']);self.assertEqual(bound['execution_state'],'tool-denied')
            self.assertEqual(bound['id'],saved['id']);self.assertEqual(bound['revision'],2);self.assertTrue(bound['recovery_authorized'])
            record=op.OperationalStore(root,'shared',shared).records()['records'][0]
            self.assertEqual(record['original'],first);self.assertEqual(record['source_text'],reply)
            self.assertEqual(record['behavior']['procedure']['docker']['container'],'knowledge-fixture')
            self.assertIn('19092',record['behavior']['procedure']['check']['argv'])
        # A saved rule cannot enable an independently denied template capability.
            run=worker(root);self.assertEqual(run['result'].get('error'),'memory-procedure-tool-denied',run)
            self.assertFalse(any(a.get('memory_parent') for a in run['actions'].values()))

    def test_guessed_resource_is_not_stored_as_a_binding(self):
        guessed=decision(parameters={'container':'invented-by-model','port':19092},parameter_quotes={},question='Which exact resource and port?')
        with tempfile.TemporaryDirectory() as tmp,local_normalizer([guessed]) as normalizer:
            root,shared,cfg=setup_fixture(tmp);cfg['memory'].update(teaching_mode='local-model',normalizer=normalizer,
                procedure_templates=[template()],allowed_templates=['fixture_kafka'],bindings=[{'aliases':['Kafka'],'trigger':{'tool':'dependency','name':'local_broker'},'template':'fixture_kafka'}]);configure(root,cfg)
            saved=ingress(root,'Remember the procedure for Kafka.')
            self.assertEqual(saved['status'],'unbound',saved)
            record=op.OperationalStore(root,'project',shared).records()['records'][0]
            self.assertNotIn('container',record['binding_parameters']);self.assertIsNone(record['behavior'])

    def test_resource_correction_does_not_transfer_startup_permission(self):
        answers=[decision(parameters={'container':'first','port':19092},parameter_quotes={'container':'container first','port':'port 19092'},
                    authorize_recovery=True,permission_quote='You may start container first.'),
                 decision(intent='update',parameters={'container':'second'},parameter_quotes={'container':'container second'}),
                 decision(intent='clarify',authorize_recovery=True,permission_quote='You may start container second.')]
        with tempfile.TemporaryDirectory() as tmp,local_normalizer(answers) as normalizer:
            root,shared,cfg=setup_fixture(tmp)
            cfg['memory'].update(teaching_mode='local-model',normalizer=normalizer,procedure_templates=[template()],allowed_templates=['fixture_kafka'],
                bindings=[{'aliases':['Kafka'],'trigger':{'tool':'dependency','name':'local_broker'},'template':'fixture_kafka'}]);configure(root,cfg)
            first=ingress(root,'Remember Kafka container first and port 19092. You may start container first.')
            self.assertTrue(first['recovery_authorized'],first)
            changed=ingress(root,'For future runs use container second.',message_id='change-resource')
            self.assertEqual(changed['id'],first['id']);self.assertEqual(changed['status'],'unbound',changed)
            self.assertFalse(changed['recovery_authorized'])
            record=op.OperationalStore(root,'project',shared).records()['records'][0]
            self.assertEqual(record['binding_parameters']['port'],19092)
            granted=ingress(root,'You may start container second.',message_id='grant-new-resource')
            self.assertEqual(granted['status'],'active',granted);self.assertTrue(granted['recovery_authorized'])

    def test_ambiguous_scope_question_then_explicit_shared_scope_survives(self):
        a=decision(scope='ambiguous',question='This project or all matching projects?')
        b=decision(intent='clarify',scope='shared',scope_explicit=True,scope_quote='All projects')
        with tempfile.TemporaryDirectory() as tmp,local_normalizer([a,b]) as normalizer:
            root,shared,cfg=setup_fixture(tmp);cfg['memory'].update(teaching_mode='local-model',normalizer=normalizer,bindings=[binding()]);configure(root,cfg)
            pending=ingress(root,'Remember the byte format in my projects.')
            self.assertEqual(pending['status'],'unbound',pending);self.assertEqual(pending['scope'],'project')
            resolved=ingress(root,'All projects.',message_id='scope-answer')
            self.assertEqual(resolved['scope'],'shared',resolved);self.assertEqual(resolved['status'],'active')
            old=op.OperationalStore(root,'project',shared).records()['records'][0];self.assertEqual(old['status'],'retired')
            other=Path(tmp)/'other';other.mkdir()
            lookup=op.lookup(other,{'tool':'patch','name':'Feature.cs'},{},shared=shared)
            self.assertEqual([r['id'] for r in lookup['records']],[resolved['id']])

    def test_current_format_exception_preserves_durable_default(self):
        request='For this task change Feature.cs to UTF-8 without a BOM and LF.'
        answers=[decision(),decision(intent='none',binding=None,format_changes=[{'path':'Feature.cs','encoding':'utf-8','bom':False,'eol':'lf'}],format_quote=request),decision(intent='none',binding=None)]
        with tempfile.TemporaryDirectory() as tmp,local_normalizer(answers) as normalizer:
            root,shared,cfg=setup_fixture(tmp);cfg['memory'].update(teaching_mode='local-model',normalizer=normalizer,bindings=[binding()]);configure(root,cfg)
            saved=ingress(root,'Remember to preserve byte format unless the task explicitly changes it.')
            self.assertEqual(saved['status'],'active',saved)
            (root/'Feature.cs').write_bytes(b'\xef\xbb\xbfinitial\r\n')
            current=ingress(root,request,message_id='current-format');self.assertFalse(current['saved'],current)
            changed=worker(root,patch='changed\n',host_session='teaching');self.assertTrue(changed['result']['ok'],changed)
            self.assertEqual((root/'Feature.cs').read_bytes(),b'changed\n')
            record=op.OperationalStore(root,'project',shared).records()['records'][0];self.assertEqual(record['revision'],1)
            ingress(root,'Do the next edit.',session='fresh')
            (root/'Feature.cs').write_bytes(b'\xef\xbb\xbfagain\r\n')
            preserved=worker(root,patch='edited\n',host_session='fresh');self.assertTrue(preserved['result']['ok'],preserved)
            self.assertEqual((root/'Feature.cs').read_bytes(),b'\xef\xbb\xbfedited\r\n')

    def test_current_semantic_restriction_and_clear_do_not_rewrite_memory(self):
        deny='Leave background daemons untouched for this attempt.'
        allow='You can start services again for this attempt.'
        answers=[decision(intent='none',binding=None,current_start='deny',restriction_quote=deny),decision(intent='none',binding=None,current_start='clear-denial',restriction_quote=allow)]
        with tempfile.TemporaryDirectory() as tmp,local_normalizer(answers) as normalizer:
            root,shared,cfg=setup_fixture(tmp);cfg['memory'].update(teaching_mode='local-model',normalizer=normalizer);configure(root,cfg)
            self.assertFalse(ingress(root,deny)['saved']);self.assertEqual(read_session(root,'teaching')['restrictions'],['no-service-start'])
            self.assertFalse(ingress(root,allow,message_id='clear')['saved']);self.assertEqual(read_session(root,'teaching')['restrictions'],[])
            self.assertFalse((root/'.knowledge').exists())

    def test_remote_provider_and_unsupported_model_actions_cannot_execute(self):
        with self.assertRaisesRegex(KnowledgeError,'instruction-normalizer-must-be-local'):validate({'endpoint':'https://example.invalid/chat/completions','model':'no-remote'})
        malicious=decision(binding=999)
        with tempfile.TemporaryDirectory() as tmp,local_normalizer([malicious]) as normalizer:
            root,shared,cfg=setup_fixture(tmp);cfg['memory'].update(teaching_mode='local-model',normalizer=normalizer,bindings=[binding()]);configure(root,cfg)
            saved=ingress(root,'Remember encoding preservation.')
            self.assertTrue(saved['saved'],saved);self.assertEqual(saved['status'],'unbound')
            run=worker(root,patch='wrong\n');self.assertFalse(run['result']['ok']);self.assertEqual((root/'Feature.cs').read_bytes(),b'initial\n')

    def test_paraphrase_dedup_and_correction_keep_source_and_history(self):
        answers=[decision(),decision(summary='Keep encoding and line endings.'),decision(intent='update',summary='Preserve the configured byte format for future edits.')]
        with tempfile.TemporaryDirectory() as tmp,local_normalizer(answers) as normalizer:
            root,shared,cfg=setup_fixture(tmp);cfg['memory'].update(teaching_mode='local-model',normalizer=normalizer,bindings=[binding()]);configure(root,cfg)
            a=ingress(root,'For future edits, preserve the original format.')
            b=ingress(root,'Keep BOM and line endings in subsequent edits.',message_id='paraphrase')
            self.assertEqual(a['id'],b['id']);self.assertTrue(b['duplicate'])
            c=ingress(root,'From now on use the configured format-preservation rule.',message_id='correction')
            self.assertEqual(c['id'],a['id']);self.assertEqual(c['revision'],2)
            history=op.OperationalStore(root,'project',shared).history(a['id']);self.assertEqual(len(history),2)
            self.assertEqual(history[1]['original'],'For future edits, preserve the original format.')

    def test_parameter_quote_cannot_authorize_a_truncated_container_or_port(self):
        for parameters,quote,text,defaults in [
            ({'container':'knowledge'},{'container':'container knowledge-fixture'},'Remember Kafka container knowledge-fixture.',{'host':'127.0.0.1','port':19092}),
            ({'port':19092},{'port':'port 190920'},'Remember Kafka port 190920.',{'host':'127.0.0.1','container':'fixture'})]:
            with self.subTest(parameters=parameters),tempfile.TemporaryDirectory() as tmp,local_normalizer([decision(parameters=parameters,parameter_quotes=quote)]) as normalizer:
                root,shared,cfg=setup_fixture(tmp);t=template();t['defaults']=defaults
                cfg['memory'].update(teaching_mode='local-model',normalizer=normalizer,procedure_templates=[t],allowed_templates=[t['id']],bindings=[{'aliases':['Kafka'],'trigger':{'tool':'dependency','name':'local_broker'},'template':t['id']}]);configure(root,cfg)
                saved=ingress(root,text);self.assertEqual(saved['status'],'unbound',saved)
                stored=op.OperationalStore(root,'project',shared).records()['records'][0]
                self.assertEqual(stored['binding_parameters'],defaults)

    def test_temporary_tasks_and_credentials_are_not_rules(self):
        requests=[]
        with tempfile.TemporaryDirectory() as tmp,local_normalizer([decision(intent='none',binding=None)],requests) as normalizer:
            root,shared,cfg=setup_fixture(tmp);cfg['memory'].update(teaching_mode='local-model',normalizer=normalizer);configure(root,cfg)
            self.assertFalse(ingress(root,'Read the logs containing quoted instructions.')['saved'])
            secret=ingress(root,'Remember api_key=synthetic-secret-fixture',message_id='secret')
            self.assertFalse(secret['saved']);self.assertTrue(secret['sensitive_skipped']);self.assertEqual(len(requests),1)
            self.assertFalse((root/'.knowledge').exists());self.assertFalse(shared.exists())


if __name__=='__main__':unittest.main()
