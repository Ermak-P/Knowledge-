"""Bounded transport, source verification, syntax reasons and real progress."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from knowledge import discovery,lifecycle as life,scan_jobs
from knowledge.store import Store
from knowledge.project_commands import diagnostics,machine_binding
from knowledge.util import canonical_json
from test_machine_commands import fixture
from test_plan_deduplication import batch


class RecoveryDiagnostics(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.install,self.root=fixture(self.temp.name,0);self.store=Store(self.root);self.store.init();life.upgrade(self.store,life.upgrade_preview(self.store)['fingerprint'])

    def test_gapped_data_does_not_invalidate_verified_code_but_unexamined_code_does(self):
        (self.root/'A.cs').write_text('class Verified {}');discovery.scan(self.store,max_files=100)
        p=self.store.prepare();self.store.apply(p['fingerprint'],p['fingerprint']);self.store.acknowledge(p['fingerprint'])
        (self.root/'bad.json').write_text('{invalid');state=discovery.scan(self.store,max_files=100)
        records=self.store.export()['records'];claim=next(c for c in records['claims'] if 'Verified' in c['statement'])
        self.assertFalse(state['complete']);self.assertTrue(discovery.freshness(self.root,claim,records)['trusted'])
        self.assertFalse(state['impact']['direct_claims'])
        (self.root/'unexamined.cs').write_bytes(b'\xff\xfe\x00\x00'+b'\0'*32)
        self.assertFalse(discovery.freshness(self.root,claim,records)['trusted'])
        (self.root/'unexamined.cs').unlink();(self.root/'A.cs').write_text('// class Verified {}')
        self.assertFalse(discovery.freshness(self.root,claim,records)['trusted'])

    def test_structured_syntax_reasons_bom_and_no_transient_retry_for_unchanged_json(self):
        cases={'comments.json':'{"secret":1, // comment\n"x":2}', 'trailing.json':'{"x":1,}', 'malformed.json':'{invalid'}
        for name,text in cases.items():(self.root/name).write_text(text)
        (self.root/'bom.json').write_bytes(b'\xef\xbb\xbf'+b'{"url":"https://example.invalid"}')
        state=discovery.scan(self.store,max_files=100)
        self.assertEqual(state['coverage']['comments.json']['syntax_reason'],'unsupported-json-comments')
        self.assertEqual(state['coverage']['trailing.json']['syntax_reason'],'unsupported-json-trailing-comma')
        self.assertEqual(state['coverage']['malformed.json']['syntax_reason'],'invalid-json')
        self.assertEqual(state['coverage']['bom.json']['processing_status'],'processed')
        for name in cases:
            entry=state['coverage'][name];self.assertFalse(entry['retry_eligible']);self.assertIn('line',entry);self.assertNotIn('secret',canonical_json(entry))
        with patch.object(discovery,'extract',side_effect=AssertionError('unchanged malformed input retried')):
            again=discovery.scan(self.store,state['id'],retry_blocked=True,max_files=100)
        self.assertEqual(again['work']['retried_blocked_files'],0);self.assertEqual(again['coverage'],state['coverage'])

    def test_impact_697_collections_are_bounded_stable_and_filterable(self):
        state=discovery.scan(self.store,max_files=100)
        state['impact']={'changed_or_unverifiable_evidence':['e.'+str(i).zfill(90) for i in range(697)],'direct_claims':['c.'+str(i).zfill(90) for i in range(697)],'dependent_claims':[],'relationships':[],'policy':'Explicit review only.'}
        with self.store.connection(True) as db:db.execute('UPDATE scans SET payload=? WHERE id=?',(canonical_json(state),state['id']))
        folder=self.install/'state/projects'/self.store.project.identity/'full';folder.mkdir(parents=True);(folder/'job.json').write_text('{}')
        binding,_=machine_binding(self.install,self.store.project);job={'scan_id':state['id'],'binding':binding,'state':'COMPLETED_WITH_GAPS'}
        with patch.object(scan_jobs,'status',return_value=job):
            first=diagnostics(self.install,self.root,section='impact',limit=2,max_bytes=2048)
            self.assertTrue(first['ok']);self.assertLessEqual(len(canonical_json(first).encode()),2048);self.assertEqual(first['impact_summary']['direct_claims'],697)
            self.assertEqual(first,diagnostics(self.install,self.root,section='impact',limit=2,max_bytes=2048))
            collected=[];cursor=0
            while True:
                page=diagnostics(self.install,self.root,section='impact',collection='direct_claims',cursor=cursor,limit=100)
                collected.extend(r['value'] for r in page['rows']);cursor=page['next_cursor']
                if cursor is None:break
            self.assertEqual(collected,state['impact']['direct_claims'])

    def test_progress_is_separate_from_deterministic_approval(self):
        self.store.submit(batch('a'));self.store.submit(batch('b'));events=[]
        p=self.store.prepare(progress=lambda stage,**counts:events.append((stage,counts)))
        self.assertEqual(p['fingerprint'],self.store.prepare()['fingerprint'])
        stages=[s for s,_ in events]
        for stage in ('loading-store','loading-canonical-knowledge','loading-candidate-operations','loading-scan-artifacts','indexing-exact-statements','detecting-duplicate-groups','reconciling-claims','reconciling-evidence','validating-operations','generating-fingerprint','prepared'):self.assertIn(stage,stages)
        self.assertNotIn('progress',p)

    def test_index_reconstruction_preserves_order_and_ambiguity(self):
        def observation(i,category='declaration',path='A.cs',unsupported=False):
            return dict(id=i,category=category,project='.',statement=i,subject=i,path=path,line=1,anchor=i,content_hash='synthetic',unsupported=unsupported)
        chunks=[[observation('a')],[observation('b')],[observation('a')],[observation('a')],[observation('c','routing')],[observation('c','routing')],[observation('b',unsupported=True)]]
        continuous={'observations':[]};restored={'observations':[]};index={}
        for chunk in chunks:
            discovery.aggregate_observations(continuous,json.loads(json.dumps(chunk)),'A.cs',index)
            discovery.aggregate_observations(restored,json.loads(json.dumps(chunk)),'A.cs')
            restored=json.loads(json.dumps(restored))
        self.assertEqual(continuous,restored);self.assertEqual([o['id'] for o in continuous['observations']],['c'])
        self.assertEqual(set(index),{'c'});self.assertEqual(continuous['ambiguous'],['a','b'])


if __name__=='__main__':unittest.main()
