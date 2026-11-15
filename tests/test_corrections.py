"""Independent review reproductions at public subprocess/stdio boundaries."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from fixtures import addition,legacy_fixture
from knowledge import migration
from knowledge.store import Store
from knowledge.util import KnowledgeError,canonical_json
from mcp import ClientSession, StdioServerParameters, stdio_client

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from evidence import Attempt,REQUIRED,validate_current


class MigrationDiscovery(unittest.TestCase):
    def test_queue_selection_and_safe_refusal(self):
        for external_data in (None,b'',b'{}\n',b'not-json\n'):
            for interchange in (False,True):
                with self.subTest(external=external_data,interchange=interchange),tempfile.TemporaryDirectory() as tmp:
                    root=Path(tmp);legacy_fixture(root)
                    q=root/'.ai/state/candidates.json'
                    if not interchange:q.unlink()
                    ext=root/'.harness/knowledge/candidates/queue.jsonl'
                    if external_data is not None:
                        ext.parent.mkdir(parents=True);ext.write_bytes(external_data)
                    before={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
                    if external_data is not None:
                        with self.assertRaises(KnowledgeError) as caught:migration.preview(root)
                        self.assertEqual(caught.exception.code,'ambiguous-legacy-queues' if interchange else 'unsupported-external-legacy-queue')
                        self.assertEqual(len(caught.exception.details['discovery']),2)
                        self.assertFalse((root/'.knowledge').exists())
                    else:
                        p=migration.preview(root);self.assertEqual(len(p['manifest']['discovery']),2)
                    self.assertEqual(before,{str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_changed_queue_or_appearance_invalidates_approval(self):
        for external in (True,False):
            with tempfile.TemporaryDirectory() as tmp:
                r=Path(tmp);legacy_fixture(r);p=migration.preview(r)
                if external:
                    f=r/'.harness/knowledge/candidates/queue.jsonl';f.parent.mkdir(parents=True);f.write_text('')
                else:
                    f=r/'.ai/state/candidates.json';f.write_text(f.read_text()+'\n')
                with self.assertRaises(KnowledgeError):migration.apply(r,p['fingerprint'])
                self.assertFalse((r/'.knowledge').exists())

    def test_supported_empty_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);legacy_fixture(r);(r/'.ai/state/candidates.json').write_text('[]')
            p=migration.preview(r);migration.apply(r,p['fingerprint']);self.assertEqual(Store(r).status()['queue'],[])


class ErrorContract(unittest.TestCase):
    def invoke(self,root,*args):
        p=subprocess.run([sys.executable,'-m','knowledge.cli',*args,'--root',str(root)],capture_output=True)
        self.assertEqual(p.returncode,1,p.stderr);self.assertNotIn(b'Traceback',p.stderr)
        v=json.loads(p.stdout);self.assertFalse(v['ok']);return v

    def test_invalid_utf8_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);s=Store(r);s.init();before=s.export();f=r/'invalid.json';f.write_bytes(b'\xff')
            self.assertEqual(self.invoke(r,'submit','--input',str(f))['error'],'invalid-utf8')
            self.assertEqual(before,s.export())

    def test_invalid_migration_document_containers(self):
        for target in ('journal','plan','manifest','queue'):
            for value in ([],{},None,42,'scalar'):
                if target=='queue' and value==[]:continue
                with self.subTest(target=target,value=value),tempfile.TemporaryDirectory() as tmp:
                    r=Path(tmp);legacy_fixture(r)
                    f={'journal':next((r/'.ai/state/population/transactions').rglob('journal.json')),
                       'plan':next((r/'.ai/state/population/plans').glob('*.json')),
                       'manifest':r/'.ai/manifest.yaml','queue':r/'.ai/state/candidates.json'}[target]
                    f.write_text(json.dumps(value),encoding='utf-8');before=f.read_bytes()
                    self.invoke(r,'migrate-preview');self.assertEqual(f.read_bytes(),before);self.assertFalse((r/'.knowledge').exists())

    def test_harness_invalid_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);p=r/'.harness/config.json';p.parent.mkdir();p.write_bytes(b'\xff')
            out=subprocess.run([sys.executable,'-m','harness.cli','--root',tmp,'--task','x'],capture_output=True)
            self.assertEqual(out.returncode,1);self.assertEqual(json.loads(out.stdout)['error'],'invalid-utf8');self.assertNotIn(b'Traceback',out.stderr)


class WireBudget(unittest.IsolatedAsyncioTestCase):
    async def test_real_text_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);legacy_fixture(root);p=migration.preview(root);migration.apply(root,p['fingerprint'])
            item=addition('synthetic.unicode','Синтетическая корзина сохраняет количество 🙂.')
            item['records']['claims'][0]['provenance']['actor']='Автор 🙂'
            item['records']['evidence'][0]['provenance']['actor']='Автор 🙂'
            store=Store(root);store.submit(item);plan=store.prepare()['fingerprint'];store.apply(plan,plan);store.acknowledge(plan)
            params=StdioServerParameters(command=sys.executable,args=['-m','knowledge.mcp','--root',tmp])
            async with stdio_client(params) as (reader,writer):
                async with ClientSession(reader,writer) as session:
                    await session.initialize()
                    for budget in (256,512,1000,4000,16000):
                        for query in ('synthetic.confirmed synthetic.inferred','synthetic.unicode','несуществующий квантовый фотон'):
                            result=await session.call_tool('knowledge_context',{'task':query,'max_bytes':budget,'include_unconfirmed':True})
                            self.assertIsNone(result.structuredContent)
                            self.assertLessEqual(sum(len(c.text.encode('utf-8')) for c in result.content),budget)
                            expected=Store(root).context(query,budget,include_unconfirmed=True)
                            self.assertEqual(json.loads(result.content[0].text),expected)
                            self.assertTrue({e for c in expected['claims'] for e in c['evidence_ids']} <= {e['id'] for e in expected['evidence']})


class EvidenceGate(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        for p in ('.gitignore','README.md','requirements-dev.lock','START-HERE.md'):(self.root/p).write_text(p)

    def success(self):
        a=Attempt(self.root)
        for name in REQUIRED:a.command(name,[sys.executable,'-c',f'print({(a.id+name)!r})'])
        a.finish('PASS');return a

    def gate(self,success=False):
        p=subprocess.run([sys.executable,str(ROOT/'scripts/make_review.py'),'--validate-only','--evidence-root',str(self.root)],capture_output=True)
        self.assertEqual(p.returncode==0,success,p.stderr)

    def test_success_then_required_subprocess_failure(self):
        self.success();self.gate(True)
        a=Attempt(self.root)
        with self.assertRaises(RuntimeError):a.command('packaging',[sys.executable,'-c',"import sys; print('controlled diagnostic',file=sys.stderr);sys.exit(9)"])
        a.finish('FAILED');self.gate()
        self.assertEqual(a.value['checks']['packaging']['returncode'],9)
        self.assertIn('controlled diagnostic',(a.directory/'artifacts/packaging.log').read_text())
        self.assertEqual(a.value['checks']['product-tests']['status'],'NOT_RUN')

    def test_interrupted_attempt(self):
        self.success();a=Attempt(self.root);self.gate()
        a.finish('INTERRUPTED');self.gate()

    def test_process_interruption_has_no_success_pointer(self):
        self.success()
        code="import sys,os;sys.path.insert(0,sys.argv[1]);from evidence import Attempt;Attempt(__import__('pathlib').Path(sys.argv[2]));os._exit(73)"
        p=subprocess.run([sys.executable,'-c',code,str(ROOT/'scripts'),str(self.root)])
        self.assertEqual(p.returncode,73);self.gate()
        self.assertEqual(json.loads((self.root/'reports/P0/verification-summary.json').read_text())['status'],'IN_PROGRESS')

    def test_stale_source(self):
        self.success();(self.root/'README.md').write_text('changed');self.gate()

    def test_mixed_artifacts(self):
        a=self.success();old=(a.directory/'artifacts/packaging.log').read_bytes()
        self.success();(self.root/'reports/P0/packaging.log').write_bytes(old);self.gate()
