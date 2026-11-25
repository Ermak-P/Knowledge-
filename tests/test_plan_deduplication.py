"""Synthetic exact-plan identity and preserved receipt regressions."""
import tempfile
from pathlib import Path
import unittest
from knowledge.store import Store
from knowledge import lifecycle as life
from knowledge.util import KnowledgeError
from fixtures import addition
from unittest.mock import patch
import json
from knowledge import discovery


def batch(name,statement='Synthetic exact statement.'):
    value=addition(name,statement)
    value['records']['evidence'][0]['source']=name+'.cs'
    return life.batch([life.op('add',kind,row['id'],0,row) for kind,rows in value['records'].items() for row in rows],'Synthetic review')

class Deduplication(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store(self.temp.name);self.store.init();life.upgrade(self.store,life.upgrade_preview(self.store)['fingerprint'])
    def test_identical_different_ids_merge_and_preserve_evidence(self):
        self.store.submit(batch('a'));self.store.submit(batch('b'))
        before=self.store.export()['records'];plan=self.store.prepare()
        self.assertTrue(plan['ok'],plan['blocked']);self.assertEqual(before,self.store.export()['records'])
        self.store.apply(plan['fingerprint'],plan['fingerprint']);self.store.acknowledge(plan['fingerprint'])
        result=self.store.export()['records'];self.assertEqual(len(result['claims']),1);self.assertEqual(len(result['evidence']),2)
        self.assertEqual(len(result['claims'][0]['evidence']),2)
        self.store.apply(plan['fingerprint'],plan['fingerprint']);self.assertEqual(result,self.store.export()['records'])
    def test_case_sensitive_identifiers_remain_distinct(self):
        self.store.submit(batch('a','Config Key = True.'));self.store.submit(batch('b','Config key = True.'))
        plan=self.store.prepare();self.assertTrue(plan['ok'],plan['blocked'])

    def test_canonical_additional_evidence_updates_same_id(self):
        self.store.submit(batch('a'));first=self.store.prepare();self.store.apply(first['fingerprint'],first['fingerprint']);self.store.acknowledge(first['fingerprint'])
        self.store.submit(batch('b'));plan=self.store.prepare();self.assertTrue(plan['ok'],plan['blocked'])
        self.store.apply(plan['fingerprint'],plan['fingerprint']);self.store.acknowledge(plan['fingerprint'])
        result=self.store.export()['records'];self.assertEqual([c['id'] for c in result['claims']],['a']);self.assertEqual(len(result['claims'][0]['evidence']),2)

    def test_metadata_conflict_stays_blocked(self):
        self.store.submit(batch('a'));value=batch('b');next(o for o in value['operations'] if o['kind']=='claims')['payload']['provenance']['actor']='different-author'
        self.store.submit(value);plan=self.store.prepare();self.assertFalse(plan['ok']);self.assertEqual(plan['blocked'][0]['code'],'duplicate-conflict')
        with self.assertRaisesRegex(KnowledgeError,'blocked-plan'):self.store.apply(plan['fingerprint'],plan['fingerprint'])

    def test_negation_numbers_and_whitespace_are_distinct(self):
        for i,s in enumerate(('Flag is set.','Flag is not set.','Limit=1.','Limit=2.','Value="a b".','Value="a  b".')):self.store.submit(batch('s'+str(i),s))
        self.assertTrue(self.store.prepare()['ok'])

    def test_changed_plan_requires_new_approval(self):
        self.store.submit(batch('a'));old=self.store.prepare();self.store.submit(batch('b'));new=self.store.prepare()
        self.assertNotEqual(old['fingerprint'],new['fingerprint'])
        with self.assertRaisesRegex(KnowledgeError,'stale-plan'):self.store.apply(old['fingerprint'],old['fingerprint'])

    def test_repeated_candidate_stays_single_queue_entry(self):
        value=batch('a');self.store.submit(value);self.store.submit(value)
        self.assertEqual(len(self.store.status()['queue']),1)

    def test_completed_and_gapped_scans_reused_without_extraction(self):
        root=Path(self.temp.name)
        (root/'Project.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"/>')
        (root/'A.cs').write_text('public class Foo {}')
        (root/'B.cs').write_text('public class foo {}')
        (root/'broken.json').write_text('{invalid')
        scan=discovery.scan(self.store,max_files=1)
        self.assertGreater(scan['work']['remaining_files'],0)
        while scan['work']['remaining_files']:scan=discovery.scan(self.store,scan['id'],max_files=1)
        self.assertEqual(scan['state'],'COMPLETED_WITH_GAPS');saved=discovery.status(self.store)
        with patch.object(discovery,'scan',side_effect=AssertionError('unexpected extraction')):
            plan=self.store.prepare();self.assertTrue(plan['ok'],plan['blocked'])
        self.assertEqual(saved,discovery.status(self.store))

    def test_identical_evidence_collapses_references(self):
        a=batch('a');b=batch('b')
        next(o for o in b['operations'] if o['kind']=='evidence')['payload']['source']='a.cs'
        self.store.submit(a);self.store.submit(b);plan=self.store.prepare();self.assertTrue(plan['ok'])
        self.store.apply(plan['fingerprint'],plan['fingerprint']);self.store.acknowledge(plan['fingerprint'])
        data=self.store.export()['records'];self.assertEqual(len(data['evidence']),1);self.assertEqual(len(data['claims'][0]['evidence']),1)

    def test_bounded_duplicate_diagnostics_stable_pages(self):
        from knowledge.diagnostic_pages import page
        for i in range(20):self.store.submit(batch('n'+str(i)))
        counts,groups=self.store.duplicate_diagnostics();self.assertEqual(counts['duplicate_groups'],1)
        _,members=self.store.duplicate_diagnostics(groups[0]['group']);self.assertEqual(len(members),20)
        answer=page(groups,{'ok':True},0,2,2048);self.assertLessEqual(len(json.dumps(answer).encode()),2048)
        self.assertTrue(answer['truncated']);self.assertEqual(answer,page(groups,{'ok':True},0,2,2048))

    def test_huge_impact_items_accessible(self):
        from knowledge.diagnostic_pages import page
        rows=[{'dependents':['x'*100]*30000}, {'id':'next'}]
        answer=page(rows,{'ok':True},0,1,1024)
        self.assertTrue(answer['truncated']);self.assertEqual(answer['next_cursor'],1)
        self.assertEqual(page(rows,{'ok':True},1,1,1024)['rows'],[{'id':'next'}])

    def test_repeated_input_evidence_refs_have_stable_candidate_identity(self):
        value=batch('a');other=json.loads(json.dumps(value))
        next(op for op in other['operations'] if op['kind']=='claims')['payload']['evidence']*=3
        first=self.store.submit(value);second=self.store.submit(other)
        self.assertEqual(first['candidate'],second['candidate']);self.assertEqual(second['result'],'duplicate')

    def test_verification_date_never_promoted_when_merging_canonical(self):
        self.store.submit(batch('a'));first=self.store.prepare();self.store.apply(first['fingerprint'],first['fingerprint']);self.store.acknowledge(first['fingerprint'])
        value=batch('b');next(op for op in value['operations'] if op['kind']=='claims')['payload']['last_verified']='2026-11-25'
        self.store.submit(value);plan=self.store.prepare();self.assertTrue(plan['ok'],plan['blocked'])
        self.store.apply(plan['fingerprint'],plan['fingerprint']);self.assertEqual(self.store.lookup('claims','a')['record']['last_verified'],'2026-11-14')

    def test_completed_artifact_validation_and_unchanged_rows(self):
        root=Path(self.temp.name);(root/'A.cs').write_text('public class A {}')
        state=discovery.scan(self.store,max_files=100);self.assertTrue(state['complete'])
        saved=discovery.status(self.store,state['id'])
        recovered=discovery.completed_artifact(self.store,state['id']);self.assertTrue(recovered['extraction_reused'])
        self.assertFalse(recovered['fresh_scan_started']);self.assertEqual(saved,discovery.status(self.store,state['id']))

    def test_schema_reads_bounded_and_transaction_cache_invalidates(self):
        import knowledge.store as module
        from shutil import copytree
        with tempfile.TemporaryDirectory() as temp:
            schemas=Path(temp)/'schemas';copytree(module.SCHEMAS,schemas)
            for i in range(10):self.store.submit(batch('s'+str(i),'Unique '+str(i)))
            with patch.object(module,'SCHEMAS',schemas):
                self.assertTrue(self.store.prepare()['ok'])
                p=schemas/'claim.schema.json';value=json.loads(p.read_text());value['required'].append('synthetic_missing');p.write_text(json.dumps(value))
                with self.assertRaisesRegex(KnowledgeError,'invalid-record'):self.store.prepare()

    def test_dependent_references_remapped_with_all_proofs(self):
        self.store.submit(batch('a'));self.store.submit(batch('b'));dependent=batch('dependent','A separate dependent fact.')
        next(o for o in dependent['operations'] if o['kind']=='claims')['payload']['depends_on']=['b']
        relationship=dict(id='edge',type='depends_on',**{'from':'dependent','to':'b'},provenance={'actor':'synthetic-test','method':'fixture'})
        dependent['operations'].append(life.op('add','relationships','edge',0,relationship));self.store.submit(dependent)
        plan=self.store.prepare();self.assertTrue(plan['ok'],plan['blocked']);self.store.apply(plan['fingerprint'],plan['fingerprint'])
        records=self.store.export()['records'];survivor=next(c['id'] for c in records['claims'] if c['id']!='dependent')
        self.assertEqual(next(c for c in records['claims'] if c['id']=='dependent')['depends_on'],[survivor])
        self.assertEqual(records['relationships'][0]['to'],survivor)

    def test_confidence_and_trust_conflicts_are_blocked(self):
        for field,value in [('status','INFERRED'),('type','architecture_rule')]:
            with self.subTest(field=field):
                from knowledge.plan_deduplication import reconcile
                a=batch('a');b=batch('b');c=next(o for o in b['operations'] if o['kind']=='claims')['payload'];c[field]=value
                _,_,blocked=reconcile({'claims':[],'evidence':[],'relationships':[]},{'a':a,'b':b},{})
                self.assertTrue(blocked)

    def test_identity_collision_is_diagnosed_and_never_applied(self):
        self.store.submit(batch('same','Fact one.'));self.store.submit(batch('same','Fact two.'))
        plan=self.store.prepare();self.assertFalse(plan['ok'])
        self.assertTrue(any(g['classification']=='identity-collision' for g in plan['deduplication']['groups']))
        self.assertFalse(self.store.export()['records']['claims'])
