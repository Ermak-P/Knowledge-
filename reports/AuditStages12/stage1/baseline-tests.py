"""Audit stage 1: actual files/SQLite/CLI, explicit model/Docker doubles."""
from contextlib import contextmanager
from copy import deepcopy
import json,os,re,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from knowledge import discovery as disc,operations as op,semantic_ingress as semantic
from knowledge.project import Project
from knowledge.util import KnowledgeError
from harness.runtime import source_snapshot,configure
from knowledge.maintenance import source_identity
from test_p1 import git,upgraded,approve
from test_persistent_instructions import setup_fixture,binding,ingress
from test_persistent_r1 import dependency
from test_persistent_reviewed import DockerContract
from test_persistent_semantics import local_normalizer,decision
from harness.instructions import execute_procedure

@contextmanager
def unreadable(path):
    if os.name=='nt':
        sid=re.search(r'S-1-[\d-]+',subprocess.check_output(['whoami','/user','/fo','csv','/nh'],text=True))[0]
        subprocess.run(['icacls',str(path),'/deny','*'+sid+':(OI)(CI)(RX)'],check=True,capture_output=True)
        try:yield
        finally:subprocess.run(['icacls',str(path),'/remove:d','*'+sid],check=True,capture_output=True)
    else:
        mode=path.stat().st_mode;path.chmod(0)
        try:yield
        finally:path.chmod(mode)

class EnumerationBoundaries(unittest.TestCase):
    def checkout(self,root):
        root=Path(root);(root/'Project.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"/>\n')
        (root/'Initial.cs').write_text('public class StillExists {}\n')
        (root/'.gitignore').write_text('.knowledge/\n.harness/\n.knowledge-control.lock\n')
        for args in [('init',),('config','user.name','Fixture'),('config','user.email','fixture@example.invalid'),('add','.'),('commit','-m','before')]:git(root,*args)
        store=upgraded(root);scan=disc.scan(store,max_files=100);approve(store);base=git(root,'rev-parse','HEAD')
        folder=root/'Unreadable';folder.mkdir();git(root,'mv','Initial.cs','Unreadable/Initial.cs');git(root,'commit','-m','move')
        return root,folder,store,base
    def test_real_permission_refusal_never_retires_live_claim_and_recovers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,folder,store,base=self.checkout(tmp)
            with unreadable(folder):
                with self.assertRaises(PermissionError):list(os.scandir(folder))
                scan=disc.scan(store,max_files=1,base=base,head='HEAD')
                self.assertFalse(scan['complete'],scan)
                scan=disc.scan(store,scan['id'],100)
                review=disc.reconcile(store,scan['id']);self.assertIsNone(review['proposal']);self.assertTrue(review['negative_evidence_gaps'])
                for check in (lambda:source_snapshot(Project(root)),lambda:source_identity(root)):
                    with self.assertRaises(KnowledgeError):check()
            recovered=disc.scan(store,max_files=100,restart=True)
            self.assertTrue(recovered['complete']);self.assertIn('StillExists',(folder/'Initial.cs').read_text())
            self.assertIsNone(disc.reconcile(store,recovered['id'])['proposal'])
    def test_enumeration_fault_and_disappearance_are_durable_gaps(self):
        for error in (PermissionError(13,'denied'),FileNotFoundError(2,'disappeared')):
            with self.subTest(error=type(error).__name__),tempfile.TemporaryDirectory() as tmp:
                root,folder,store,base=self.checkout(tmp);original=os.scandir
                def fault(path):
                    if Path(path)==folder:raise type(error)(error.errno,error.strerror,str(folder))
                    return original(path)
                with patch('os.scandir',side_effect=fault):
                    first=disc.scan(store,max_files=1,base=base,head='HEAD');again=disc.scan(store,first['id'],100)
                    self.assertFalse(again['complete']);self.assertEqual(first['snapshot']['identity'],again['snapshot']['identity'])
                    self.assertTrue(disc.reconcile(store,again['id'])['negative_evidence_gaps'])
                    for check in (lambda:source_snapshot(Project(root)),lambda:source_identity(root)):
                        with self.assertRaises(KnowledgeError):check()

class CatalogAuthorization(unittest.TestCase):
    def test_public_catalog_ingress_cannot_bypass_deny_wins(self):
        for text in ('Remember Kafka: do not start the container; you may start the container.',
                     'Запомни Kafka: не запускай контейнер; разрешаю запуск этого контейнера.',
                     'Remember Kafka: starting containers is forbidden. You may start the container.',
                     'Запомни Kafka: запуск контейнера не разрешен. Разрешаю запуск этого контейнера.'):
            with self.subTest(text=text),tempfile.TemporaryDirectory() as tmp:
                root,shared,cfg=setup_fixture(tmp);p,b=dependency()
                cfg['memory'].update(bindings=[b],allowed_procedures=[p],requirements=[{'trigger':{'tool':'recipe','name':'test'},'dependency':'guard'}]);configure(root,cfg)
                saved=ingress(root,text);self.assertTrue(saved.get('saved'),saved)
                record=op.OperationalStore(root,'project',shared).records()['records'][0];contract=DockerContract(root,after_start=True)
                try:execute_procedure(contract,'operation',record,{'shared_root':str(shared)})
                except KnowledgeError:pass
                self.assertFalse(contract.starts());self.assertFalse(record['recovery_authorized']);self.assertEqual(record['original'],text)

class ScopeTransfer(unittest.TestCase):
    def test_target_commit_then_replay_without_model_finishes_retirement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,shared,cfg=setup_fixture(tmp)
            answers=[decision(scope='ambiguous',question='Which scope?'),decision(intent='clarify',scope='shared',scope_explicit=True,scope_quote='All projects')]
            with local_normalizer(answers) as normalizer:
                policy={**cfg['memory'],'teaching_mode':'local-model','normalizer':normalizer,'bindings':[binding()]}
                first=semantic.ingest(root,'Remember encoding.','teach',policy)
                with patch('knowledge.operations.retire',side_effect=RuntimeError('worker interrupted')),self.assertRaises(RuntimeError):
                    semantic.ingest(root,'All projects.','scope-change',policy,first['id'])
            replay=semantic.ingest(root,'All projects.','scope-change',policy,first['id']);self.assertTrue(replay['saved'])
            selected=op.lookup(root,{'tool':'patch','name':'Feature.cs'},{},shared=shared)
            self.assertEqual(len(selected['records']),1,selected);self.assertEqual(selected['records'][0]['status'],'active')
            old=op.OperationalStore(root,'project',shared).records()['records'][0];self.assertEqual(old['status'],'retired')


if __name__=='__main__':unittest.main()
