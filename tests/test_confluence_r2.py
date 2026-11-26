"""External review regressions: coverage, targeted review and durable recovery."""
import ast,hashlib,inspect,json,tempfile,unittest,subprocess,sys
from pathlib import Path
from unittest.mock import patch
from knowledge import confluence as cf,confluence_sync as cs,confluence_command as cc,lifecycle as life
from knowledge.store import Store
from knowledge.util import KnowledgeError,canonical_json,digest
from test_confluence_source import document

QUOTE='Synthetic checkout requires a shipping address.'
FINDING=dict(statement=QUOTE,quote=QUOTE,role='requirement')


from confluence_fixtures import coverage,analyze_page

class CoverageSafety(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.store=Store(self.root);self.store.init();life.upgrade(self.store,life.upgrade_preview(self.store)['fingerprint'])
    def register(self,**kw):return cf.register(self.store,document(**kw))['source']
    def apply(self):
        p=self.store.prepare();self.assertTrue(p['ok'],p);self.store.apply(p['fingerprint'],p['fingerprint']);self.store.acknowledge(p['fingerprint'])
    def test_complete_requires_explicit_snapshot_coverage(self):
        source=self.register()
        with self.assertRaisesRegex(KnowledgeError,'coverage'):cs.analyze(self.store,source,[],True)
    def test_maximum_offset_is_not_coverage(self):
        source=self.register(content='A'*6500)
        with self.assertRaisesRegex(KnowledgeError,'coverage'):cs.analyze(self.store,source,[],True,6500)
    def test_gaps_and_bad_chunk_hash_are_rejected(self):
        source=self.register(content='A'*6500)
        with self.assertRaisesRegex(KnowledgeError,'incomplete.*coverage'):cs.analyze(self.store,source,[],True,coverage=coverage(self.store,source,[0,4000,6000]))
        value=coverage(self.store,source,[0]);value['chunks'][0]['hash']='sha256:'+'0'*64
        with self.assertRaisesRegex(KnowledgeError,'chunk'):cs.analyze(self.store,source,[],False,coverage=value)
    def test_duplicate_chunks_and_process_restart_preserve_continuous_coverage(self):
        source=self.register(content='A'*6500);first=coverage(self.store,source,[0,4000]);a=cs.analyze(self.store,source,[],False,coverage=first);b=cs.analyze(self.store,source,[],False,coverage=first)
        self.assertEqual(a['coverage'],b['coverage']);self.assertEqual(a['coverage']['covered_characters'],4000);self.assertEqual(a['coverage']['continuous_until'],2000)
        code="""import json,sys
from knowledge.store import Store
from knowledge import confluence_sync as cs
v=json.load(sys.stdin);print(json.dumps(cs.analyze(Store(v['root']),v['source'],[],True,coverage=v['coverage'])))
"""
        value=dict(root=str(self.root),source=source,coverage=coverage(self.store,source,[2000,6000]))
        process=subprocess.run([sys.executable,'-I','-c',code],input=json.dumps(value),text=True,capture_output=True)
        self.assertEqual(process.returncode,0,process.stderr);self.assertTrue(json.loads(process.stdout)['analysis_complete'])
        self.assertTrue(cs.analyze(self.store,source,[],True,coverage=value['coverage'])['replayed'])
        self.assertEqual(cs.resume(self.store,a['checkpoint'])['candidates'],[])
    def test_native_version_change_rejects_old_completion(self):
        source=self.register(content='A'*6500);cs.analyze(self.store,source,[],False,coverage=coverage(self.store,source,[0]));self.register(version=2,content='B'*6500)
        with self.assertRaisesRegex(KnowledgeError,'stale-confluence'):cs.analyze(self.store,source,[],True,coverage=coverage(self.store,source))
    def test_omitted_historical_fact_is_not_superseded_by_absence(self):
        source=self.register();analyze_page(self.store,source,[FINDING]);self.apply();before=self.store.export()['records']
        newer=self.register(version=2,content=QUOTE+' Additional documentation.')
        analyze_page(self.store,newer,[])
        pending=self.store.prepare();self.assertTrue(pending['ok'],pending)
        self.apply();self.assertEqual(self.store.export()['records'],before)
    def test_targeted_change_has_durable_review_and_needs_approved_apply(self):
        source=self.register();analyze_page(self.store,source,[FINDING]);self.apply();before=self.store.export()['records'];eid=before['evidence'][0]['id']
        newer=self.register(version=2,content='Shipping addresses are now optional.')
        review=dict(evidence=eid,expected=1,verdict='changed',quote='Shipping addresses are now optional.',reason='The current documentation explicitly changes this requirement.')
        cs.analyze(self.store,newer,[],True,coverage=coverage(self.store,newer),revalidations=[review]);self.assertEqual(before,self.store.export()['records'])
        self.apply();self.assertEqual(self.store.export()['records']['evidence'][0]['status'],'superseded')
        self.assertEqual(self.store.export()['records']['claims'][0]['status'],'NEEDS_HUMAN_CONFIRMATION');self.store.validate()

if __name__=='__main__':unittest.main()
