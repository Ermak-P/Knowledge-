import copy,hashlib,json,os,sys,tempfile,unittest
from pathlib import Path
from p2_fixtures import project,configuration,http_provider,final
from p4_r2_fixtures import MissingFile
from test_p4 import p4task
from harness.engine import start,status
from harness.runtime import configure,Journal,Lease,config
from harness.tools import Broker
from harness.p4 import route_review_repair,finding_names_path
from knowledge.store import Store
from knowledge.util import digest,KnowledgeError

class MissingTargetTests(unittest.TestCase):
    def exercise_creation(self,path,body,is_test):
        for structured in (False,True):
            with self.subTest(structured=structured),tempfile.TemporaryDirectory() as tmp,http_provider(d:=MissingFile(path,body,structured)) as endpoint:
                root=project(tmp);before_test=(root/'test_feature.py').read_bytes();t=p4task();t['writable']=['Feature.cs',path];t['acceptance']=['Feature.cs contains ImprovedFeature; '+path+' must exist with its required implementation.'];t['items']=[dict(id='first',objective='Implement Feature',depends=[],writable=['Feature.cs']),dict(id='missing',objective='Create required '+path,depends=['first'],writable=[path])]
                c=configuration(endpoint)
                if is_test:c['recipes']['test']['argv']=[sys.executable,'-m','unittest','discover','-s','.','-p','test_*.py']
                configure(root,c,True);r=start(root,t);self.assertTrue(r['ok'],r);report=status(root,r['run_id']);run=report['run']
                self.assertEqual((root/path).read_text(encoding='utf-8'),body);self.assertEqual((root/'Feature.cs').read_text(),'public class ImprovedFeature {}\n');self.assertEqual((root/'test_feature.py').read_bytes(),before_test)
                self.assertEqual(d.omission_read.get('error'),'file-not-found');self.assertTrue(d.repair_scopes);self.assertTrue(all(s==[path] for s in d.repair_scopes))
                self.assertEqual([i['attempts'] for i in run['p4']['items']],[1,2]);self.assertEqual(run['p4']['failures'],1);self.assertEqual(run['p4']['review_history'][0]['targets'],[dict(item='missing',paths=[path])])
                patches=[a for a in report['actions'].values() if a['tool']=='patch'];self.assertEqual(len(patches),2);created=next(a for a in patches if a['args']['files'][0]['path']==path);self.assertIsNone(created['args']['files'][0]['before']);self.assertTrue(created['result']['ok']);self.assertEqual(created['result']['written'],[path])
                self.assertEqual(len(run['p4']['verifiers']),6);self.assertTrue(all(g['source']==digest(run['source']) and g['config']==run['config_hash'] for g in run['gates'].values()));self.assertEqual(run['gates']['review']['verdict'],'approve')
                self.assertEqual(run['gates']['test']['counts']['executed'],2 if is_test else 1)
                self.assertTrue(all(q['usage']['coverage']=='reported' for q in run['requests']));self.assertEqual(report['metrics']['requests'],len(run['requests']))
                snapshot=Store(root).export();self.assertFalse(snapshot['records']['claims']);self.assertTrue(snapshot['queue']);self.assertEqual(run['capture']['state'],'delivered')
    def test_review_creates_omitted_authorized_source_file(self):
        self.exercise_creation('Missing.cs','public class RequiredFeature {}\n',False)
    def test_review_creates_and_executes_omitted_authorized_test_file(self):
        self.exercise_creation('test_missing.py','import unittest\nfrom pathlib import Path\nclass RequiredRegression(unittest.TestCase):\n def test_required_feature(self):\n  self.assertEqual(Path("Feature.cs").read_text(encoding="utf-8"),"public class ImprovedFeature {}\\n")\n',True)
    def make_run(self,root,endpoint,outer,items):
        t=p4task();t['writable']=outer;t['items']=items;configure(root,configuration(endpoint),True);r=start(root,t);self.assertFalse(r['ok']);j=Journal(root);return j,j.load(r['run_id'])
    def test_absent_reference_uses_patch_guards_without_new_authority(self):
        with tempfile.TemporaryDirectory() as tmp,tempfile.TemporaryDirectory() as external,http_provider(lambda b:final('No effects')) as endpoint:
            root=project(tmp);(root/'existing-dir').mkdir();(root/'linked').symlink_to(Path(external),target_is_directory=True)
            items=[dict(id='narrow',objective='Narrow',depends=[],writable=['Feature.cs']),dict(id='wide',objective='Wide',depends=['narrow'],writable=['*'])]
            j,run=self.make_run(root,endpoint,['Feature.cs','*'],items)
            cases=[('narrow','Outside.cs'),('wide','../escape.cs'),('wide',str(Path(external)/'absolute.cs')),('wide','.harness/runner.json'),('wide','privatekey.cs'),('wide','secrets/Missing.cs'),('wide','New.csproj'),('wide','build.py'),('wide','test_feature.py'),('wide','linked/New.cs'),('wide','existing-dir')]
            before=copy.deepcopy(run['source'])
            with Lease(j) as lease:
                for n,(item,path) in enumerate(cases):
                    with self.subTest(path=path):
                        reviewer=Broker(j,config(root),run,lease);answer=reviewer.execute('Reviewing','bad-review-'+str(n),'review',dict(verdict='reject',findings=['Create '+path],affected=[dict(item=item,paths=[path])]))
                        self.assertFalse(answer['ok'],answer)
                        narrow=copy.deepcopy(run);narrow['task']['writable']=next(i['writable'] for i in run['p4']['items'] if i['id']==item);broker=Broker(j,config(root),narrow,lease)
                        rejected=broker.execute('Coding','bad-patch-'+str(n),'patch',dict(files=[dict(path=path,before=run['source'].get(path),after='FORBIDDEN')]))
                        self.assertFalse(rejected['ok'],rejected);self.assertEqual(answer['error'],rejected['error'])
            self.assertEqual(run['source'],before);self.assertEqual(run['p4']['failures'],0);self.assertEqual([i['attempts'] for i in run['p4']['items']],[0,0]);self.assertFalse((root/'Outside.cs').exists());self.assertEqual(list(Path(external).iterdir()),[])
    def test_string_omission_refuses_ambiguous_pattern_and_outside_targets(self):
        cases=[(['Missing.cs'],[['Missing.cs'],['Missing.cs']],'Missing.cs is required.'),(['*'],[['*']],'src/New.cs is required.'),(['Feature.cs'],[['Feature.cs']],'Outside.cs is required.'),(['Missing.cs'],[['Missing.cs']],'../Missing.cs is required.')]
        for outer,scopes,finding in cases:
            with self.subTest(finding=finding),tempfile.TemporaryDirectory() as tmp,http_provider(lambda b:final('No effects')) as endpoint:
                root=project(tmp);items=[dict(id='item'+str(n),objective='Check',depends=[] if n==0 else ['item'+str(n-1)],writable=scope) for n,scope in enumerate(scopes)];j,run=self.make_run(root,endpoint,outer,items)
                with Lease(j) as lease:
                    answer=Broker(j,config(root),run,lease).execute('Reviewing','reject','review',dict(verdict='reject',findings=[finding]));self.assertTrue(answer['ok']);run['gates']['review']=answer
                    with self.assertRaisesRegex(KnowledgeError,'review-repair-target-required'):route_review_repair(run,j.project)
                self.assertEqual(run['p4']['failures'],0);self.assertTrue(all(i['attempts']==0 for i in run['p4']['items']));self.assertFalse((root/'Missing.cs').exists())
    def test_literal_finding_does_not_match_traversal_or_name_suffix(self):
        for text in ('../Missing.cs','/abs/Missing.cs','OtherMissing.cs','Missing.cs.extra','C:\\Missing.cs'):
            self.assertFalse(finding_names_path(text,'Missing.cs'),text)
        for text in ('Missing.cs is missing.','`Missing.cs` must exist.','Create Missing.cs.'):
            self.assertTrue(finding_names_path(text,'Missing.cs'),text)
