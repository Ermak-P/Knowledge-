"""Offline synthetic native-version synchronization and recovery acceptance tests."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from knowledge import confluence as cf,confluence_sync as sync,discovery,lifecycle as life
from knowledge.store import Store
from knowledge.util import KnowledgeError,canonical_json,digest
from test_confluence_source import document

RULE='Synthetic checkout requires a shipping address.'
def finding(statement=RULE,quote=RULE,role='requirement',**extra):return dict(statement=statement,quote=quote,role=role,**extra)

class ConfluenceSync(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.s=Store(self.root)
        self.s.init();life.upgrade(self.s,life.upgrade_preview(self.s)['fingerprint'])
    def register(self,**kw):return cf.register(self.s,document(**kw))['source']
    def apply(self):
        p=self.s.prepare();self.assertTrue(p['ok'],p['blocked']);self.s.apply(p['fingerprint'],p['fingerprint']);self.s.acknowledge(p['fingerprint']);return p
    def page(self,source):return cf.dispatch(self.s,'inventory',{'identity':source['identity']})['rows'][0]
    def records(self):return self.s.export()['records']
    def test_inventory_separates_observation_analysis_and_application(self):
        source=self.register();self.assertIsNone(self.page(source).get('last_analyzed_version'))
        result=sync.analyze(self.s,source,[finding()]);self.assertEqual(len(result['candidates']),1)
        self.assertEqual(self.page(source)['last_analyzed_version'],1);self.assertIsNone(self.page(source).get('last_applied_version'))
        self.apply();self.assertEqual(self.page(source)['last_applied_version'],1)
        metadata={k:v for k,v in document().items() if k in ('instance','page_id','title','url','version')}
        with patch.object(sync,'analyze',side_effect=AssertionError('unchanged must skip analysis')):
            self.assertEqual(sync.observe(self.s,metadata)['action'],'SKIP')
        other=self.register(page='empty');sync.analyze(self.s,other,[])
        self.assertEqual(self.page(other)['last_analyzed_version'],1);self.assertIsNone(self.page(other).get('last_applied_version'))
    def test_identical_new_version_reuses_analysis_and_refreshes_unapplied_proofs(self):
        a=self.register();sync.analyze(self.s,a,[finding()]);old=self.s.prepare()
        b=self.register(version=2);self.assertEqual(self.page(b)['last_analyzed_version'],2)
        with self.assertRaisesRegex(KnowledgeError,'stale-plan'):self.s.apply(old['fingerprint'],old['fingerprint'])
        self.apply();rows=self.records();self.assertEqual(len(rows['claims']),1);self.assertEqual(rows['evidence'][0]['source']['revision'],2)
        with self.s.connection() as db:self.assertEqual(db.execute('SELECT count(*) FROM confluence_blobs').fetchone()[0],1)
        self.assertEqual(self.page(b)['last_applied_version'],2)

    def test_same_body_refresh_preserves_provider_binding_and_refuses_drift(self):
        from knowledge.providers import shared,semantic_bindings
        provider=self.root/'provider.json';provider.write_text(json.dumps({'provider':{'endpoint':'http://127.0.0.1:9000/v1/chat/completions','model':'synthetic-live','evidence':'live'}}))
        config,reference=shared(provider)
        binding={'version':1,'provider_ref':reference,'model':config['model'],'evidence':'live','contract':'reviewed-v2-v1'}
        a=self.register()
        with self.s.connection() as db:batches,_=sync.build_proposals(self.s,db,a,[finding()],True)
        old=self.s.submit(batches[0],semantic_binding=binding)['candidate']
        sync.analyze(self.s,a,[finding()])
        self.register(version=2)
        with self.s.connection() as db:
            links=sync.refresh_links(db);replacement=links[old]['replacement'];self.assertEqual(semantic_bindings(db)[replacement],binding)
        self.assertTrue(self.s.prepare()['ok'])
        provider.write_text(json.dumps({'provider':{'endpoint':'http://127.0.0.1:9000/v1/chat/completions','model':'changed-live','evidence':'live'}}))
        prepared=self.s.prepare();self.assertFalse(prepared['ok']);self.assertIn('provider',str(prepared['blocked']))
    def test_changed_page_reuses_claim_and_supersedes_only_its_evidence(self):
        a=self.register();sync.analyze(self.s,a,[finding()]);self.apply();cid=self.records()['claims'][0]['id']
        b=self.register(version=2,content=RULE+' Extra details.');sync.analyze(self.s,b,[finding()]);self.apply()
        rows=self.records();self.assertEqual(rows['claims'][0]['id'],cid);self.assertEqual(len(rows['evidence']),2)
        self.assertEqual(sorted(e['status'] for e in rows['evidence']),['active','superseded'])
        self.assertTrue(self.s.lookup('claims',cid)['freshness']['trusted']);self.s.validate()
    def test_multiple_pages_pending_and_repeated_imports_share_one_claim(self):
        a=self.register();b=self.register(page='102');sync.analyze(self.s,a,[finding()]);sync.analyze(self.s,b,[finding()]);self.apply()
        rows=self.records();self.assertEqual(len(rows['claims']),1);self.assertEqual(len(rows['claims'][0]['evidence']),2)
        for source in (a,b):sync.analyze(self.s,source,[finding()])
        self.assertEqual(rows,self.records());self.s.validate()

    def test_multiple_pages_can_enrich_existing_canonical_claim_in_one_plan(self):
        a=self.register();sync.analyze(self.s,a,[finding()]);self.apply()
        for pid in ('102','103'):
            source=self.register(page=pid);sync.analyze(self.s,source,[finding()])
        self.apply();rows=self.records();self.assertEqual(len(rows['claims']),1);self.assertEqual(len(rows['claims'][0]['evidence']),3)

    def test_multiple_changed_pages_and_deletions_reconcile_only_own_proofs(self):
        for pid in ('101','102'):
            source=self.register(page=pid);sync.analyze(self.s,source,[finding()])
        self.apply()
        for pid in ('101','102'):
            source=self.register(page=pid,version=2,content=RULE+' Changed context.');sync.analyze(self.s,source,[finding()])
        self.apply();self.assertEqual(len(self.records()['claims'][0]['evidence']),2)
        for pid in ('101','102'):sync.confirm_deleted(self.s,cf.identity('synthetic-cloud-id',pid),'native-page-status-deleted')
        self.apply();self.assertEqual(self.records()['claims'][0]['status'],'NEEDS_HUMAN_CONFIRMATION');self.s.validate()
    def test_git_and_documentation_pending_share_fact_without_promotion(self):
        (self.root/'A.cs').write_text('class A {}')
        discovery.scan(self.s,max_files=100)
        with self.s.connection() as db:
            candidates=[json.loads(raw) for raw, in db.execute('SELECT payload FROM queue')]
        claim=next(o['payload'] for c in candidates for o in c['operations'] if o['kind']=='claims')
        a=self.register(content=claim['statement']);sync.analyze(self.s,a,[finding(claim['statement'],claim['statement'],'implementation')]);self.apply()
        rows=self.records();self.assertEqual(len(rows['claims']),1);self.assertEqual(len(rows['claims'][0]['evidence']),2)
        self.assertEqual(rows['claims'][0]['status'],'CONFIRMED');self.assertEqual({e['type'] for e in rows['evidence']},{'supporting','direct-technical'})
    def test_documentation_then_git_preserves_existing_claim_id_and_scope(self):
        (self.root/'A.cs').write_text('class A {}');snapshot=discovery.inventory(self.s.project.root)
        # Use the actual deterministic observation wording rather than assuming it.
        discovery.scan(self.s,max_files=100)
        with self.s.connection() as db:batch=json.loads(db.execute('SELECT payload FROM queue').fetchone()[0])
        statement=next(o['payload']['statement'] for o in batch['operations'] if o['kind']=='claims')
        # Apply documentation first in a separate otherwise identical project.
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp);s.init();life.upgrade(s,life.upgrade_preview(s)['fingerprint'])
            a=cf.register(s,document(content=statement))['source'];sync.analyze(s,a,[finding(statement,statement,'implementation')]);p=s.prepare();s.apply(p['fingerprint'],p['fingerprint']);s.acknowledge(p['fingerprint'])
            cid=s.export()['records']['claims'][0]['id'];Path(tmp,'A.cs').write_text('class A {}');discovery.scan(s,max_files=100)
            p=s.prepare();self.assertTrue(p['ok'],p['blocked']);s.apply(p['fingerprint'],p['fingerprint']);s.acknowledge(p['fingerprint'])
            rows=s.export()['records'];self.assertEqual(len(rows['claims']),1);self.assertEqual(rows['claims'][0]['id'],cid);self.assertEqual(len(rows['claims'][0]['evidence']),2)
            self.assertEqual(rows['claims'][0]['status'],'INFERRED');s.validate()
    def test_deleted_page_preserves_other_page_proofs_and_failures_never_delete(self):
        a=self.register();sync.analyze(self.s,a,[finding()]);self.apply();b=self.register(page='102');sync.analyze(self.s,b,[finding()]);self.apply()
        before=self.records()
        for reason in ('ACCESS_DENIED','TIMEOUT','UNAVAILABLE','NOT_FOUND_UNCONFIRMED','INCOMPLETE_RESPONSE'):
            sync.failure(self.s,a['identity'],reason);self.assertEqual(before,self.records())
        with self.assertRaisesRegex(KnowledgeError,'needs-explicit-native-status'):sync.confirm_deleted(self.s,a['identity'],'404')
        sync.confirm_deleted(self.s,a['identity'],'native-page-status-deleted');self.apply()
        rows=self.records();self.assertEqual(len(rows['claims']),1);self.assertEqual(len(rows['claims'][0]['evidence']),1)
        self.assertTrue(self.s.lookup('claims',rows['claims'][0]['id'])['freshness']['trusted']);self.assertEqual(len(rows['evidence']),2)
        sync.confirm_deleted(self.s,b['identity'],'native-page-status-deleted');self.apply();self.assertEqual(self.records()['claims'][0]['status'],'NEEDS_HUMAN_CONFIRMATION');self.s.validate()
    def test_interrupted_submission_is_blocked_until_durable_outbox_resume(self):
        a=self.register()
        def crash(name):
            if name=='confluence-candidate-submitted':raise RuntimeError('synthetic crash after persisted submit')
        with patch('knowledge.store.checkpoint',side_effect=crash),self.assertRaises(RuntimeError):sync.analyze(self.s,a,[finding()])
        page=self.page(a);self.assertIsNone(page.get('last_analyzed_version'));checkpoint=page['analysis_checkpoint']
        registered=cf.register(self.s,document());self.assertEqual(registered['sync']['checkpoint'],checkpoint)
        p=self.s.prepare();self.assertFalse(p['ok']);self.assertIn('resume',str(p['blocked']))
        sync.resume(self.s,checkpoint);self.apply();sync.resume(self.s,checkpoint);self.assertEqual(len(self.records()['claims']),1)
        with self.s.connection() as db:self.assertEqual(db.execute('SELECT count(*) FROM queue').fetchone()[0],1)
    def test_partial_chunks_are_persisted_without_conflicting_claim_updates(self):
        a=self.register(content=RULE+' Another useful constraint.')
        first=sync.analyze(self.s,a,[finding()],complete=False);self.assertFalse(first['candidates']);self.assertFalse(self.records()['claims'])
        self.assertEqual(sync.resume(self.s,first['checkpoint'])['persisted_findings'],1)
        sync.analyze(self.s,a,[finding('Another constraint.','Another useful constraint.')],complete=True);self.apply()
        self.assertEqual(len(self.records()['claims']),2);self.assertEqual(self.page(a)['last_applied_version'],1)
    def test_conflicts_are_explicit_and_scopes_are_not_silently_merged(self):
        a=self.register();sync.analyze(self.s,a,[finding()]);self.apply();cid=self.records()['claims'][0]['id']
        b=self.register(page='102',content='Shipping address optional.')
        result=sync.analyze(self.s,b,[finding('Shipping address optional.','Shipping address optional.',conflicts_with=[cid],question='Which shipping rule applies?')]);self.assertEqual(result['conflicts_detected'],1)
        self.assertEqual(result['clarification_questions'],['Which shipping rule applies?']);self.apply()
        self.assertTrue(all(c['conflicts_with'] for c in self.records()['claims']))
        c=self.register(page='103');
        with self.assertRaisesRegex(KnowledgeError,'scope-conflict'):sync.analyze(self.s,c,[finding(role='implementation')])
    def test_retention_pins_canonical_and_pending_history_and_deduplicates_bodies(self):
        a=self.register();sync.analyze(self.s,a,[finding()]);self.apply()
        for version in range(2,12):self.register(version=version,content='Unused version '+str(version))
        result=sync.collect(self.s,keep=1);self.assertEqual(result['canonical_records_removed'],0);self.assertGreater(result['snapshots_removed'],0)
        self.s.validate()
        with self.s.connection() as db:
            self.assertIsNotNone(cf.snapshot(db,a['snapshot']));self.assertLessEqual(db.execute('SELECT count(*) FROM confluence_blobs').fetchone()[0],3)
    def test_schema_one_to_two_migration_is_transactional_and_idempotent(self):
        a=self.register()
        with self.s.connection(True) as db:
            data=cf.snapshot(db,a['snapshot']);data.pop('body_ref',None)
            db.execute('UPDATE confluence_snapshots SET payload=?,checksum=?',(canonical_json(data),digest(data)))
            db.execute('DROP TABLE confluence_blobs');db.execute("UPDATE metadata SET value='1' WHERE key='confluence-schema'")
        before=self.s.export()
        with self.assertRaises(RuntimeError):
            with self.s.connection(True) as db:cf.enable(db);raise RuntimeError('rollback migration')
        self.assertEqual(before,self.s.export())
        with self.s.connection(True) as db:cf.enable(db);cf.enable(db)
        self.s.validate()
        with self.s.connection() as db:self.assertEqual(db.execute('SELECT count(*) FROM confluence_blobs').fetchone()[0],1)
    def test_confluence_sync_never_scans_git(self):
        with patch.object(discovery,'inventory',side_effect=AssertionError('no Git scan')):
            a=self.register();sync.analyze(self.s,a,[finding()]);self.apply();self.register(version=2);self.s.context('shipping')

    def test_thousand_page_metadata_inventory_is_paged_without_git_or_bodies(self):
        with patch.object(discovery,'inventory',side_effect=AssertionError('no Git scan')):
            for index in range(1000):
                value=document(page=str(index));metadata={k:value[k] for k in ('instance','page_id','version','title','url')}
                self.assertEqual(sync.observe(self.s,metadata)['action'],'FETCH_CONTENT')
        result=cf.dispatch(self.s,'inventory',{'limit':20,'max_bytes':16000})
        self.assertEqual(len(result['rows']),20)
        with self.s.connection() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM confluence_pages').fetchone()[0],1000)
            self.assertEqual(db.execute('SELECT count(*) FROM confluence_blobs').fetchone()[0],0)

    def test_content_cache_is_bounded_and_body_corruption_is_detected(self):
        a=self.register(content='a'*5000000);b=self.register(page='102',content='b'*5000000)
        with self.s.connection() as db:
            cf.snapshot(db,a['snapshot']);cf.snapshot(db,b['snapshot'])
            from knowledge.sqlite_snapshot import view
            cache=view(db,'confluence-body-lru',lambda:None);self.assertLessEqual(cache['bytes'],8*1024*1024)
        with self.s.connection(True) as db:db.execute("UPDATE confluence_blobs SET content='CORRUPTED'")
        with self.assertRaisesRegex(KnowledgeError,'corrupt-confluence-snapshot-body'):self.s.validate()

if __name__=='__main__':unittest.main()
