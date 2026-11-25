"""Native MCP snapshots; no private URLs, credentials or live Confluence needed."""
import contextlib,json,tempfile,unittest,sys
from pathlib import Path
from unittest.mock import patch
from knowledge import confluence as cf,discovery,lifecycle as life
from knowledge.store import Store
from knowledge.util import KnowledgeError,canonical_json,digest
from fixtures import addition


def document(page='101',version=1,content='Synthetic checkout requires a shipping address.\n',**changes):
    return dict(instance='synthetic-cloud-id',page_id=page,version=version,title='Synthetic shipping rule',
                url='https://docs.example.invalid/wiki/pages/'+page,content=content,
                retrieved_at='2026-11-25T00:00:00Z',representation='text',**changes)


def proposal(store,source,name='cf.claim',quote='Synthetic checkout requires a shipping address.'):
    with store.connection() as db:snapshot=cf.verify_binding(db,source)
    evidence=dict(id='e.'+name,type='direct-authoritative',status='active',source={**source,'reference':snapshot['url']},
                  location='normalized-text#L1',content_hash=snapshot['content_hash'],description=quote,substantiates=[name],
                  captured_at=snapshot['retrieved_at'],provenance={'actor':'synthetic-confluence-MCP','method':'confluence-documentation-v1'})
    claim=dict(id=name,statement=quote,type='business_rule',status='CONFIRMED',evidence=[evidence['id']],provenance=evidence['provenance'],
               last_verified='2026-11-25',depends_on=[],conflicts_with=[])
    return life.batch([life.op('add','evidence',evidence['id'],0,evidence),life.op('add','claims',name,0,claim)],'Synthetic documentation requirement, not implementation proof',source)


class ConfluenceSource(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.store=Store(self.root);self.store.init();life.upgrade(self.store,life.upgrade_preview(self.store)['fingerprint'])

    def register(self,**changes):return cf.register(self.store,document(**changes))['source']

    def test_native_end_to_end_has_no_git_inventory_or_network(self):
        with patch.object(discovery,'inventory',side_effect=AssertionError('Confluence must not scan Git')):
            source=self.register();self.store.submit(proposal(self.store,source));p=self.store.prepare();self.assertTrue(p['ok'],p['blocked'])
            self.assertFalse(self.store.export()['records']['claims'])
            self.store.apply(p['fingerprint'],p['fingerprint']);self.store.acknowledge(p['fingerprint'])
            self.assertTrue(self.store.lookup('claims','cf.claim')['freshness']['trusted'])
            self.assertIn('cf.claim',[c['id'] for c in self.store.context('shipping address')['claims']])
            self.assertEqual(len(self.store.export()['confluence']['snapshots']),1)
            self.store.validate()

    def test_local_working_tree_changes_do_not_stale_documentation_plan(self):
        source=self.register();self.store.submit(proposal(self.store,source));p=self.store.prepare()
        (self.root/'Changed.cs').write_text('class Changed {}')
        self.store.apply(p['fingerprint'],p['fingerprint']);self.assertTrue(self.store.lookup('claims','cf.claim')['freshness']['trusted'])

    def test_new_page_revision_rejects_old_candidate_and_approval(self):
        source=self.register();self.store.submit(proposal(self.store,source));old=self.store.prepare()
        self.register(version=2,content='Synthetic new requirement.\n')
        new=self.store.prepare();self.assertFalse(new['ok']);self.assertEqual(new['blocked'][0]['code'],'stale-confluence-revision')
        self.assertEqual(new['blocked'][0]['details']['observed_revision'],2)
        with self.assertRaisesRegex(KnowledgeError,'stale-plan'):self.store.apply(old['fingerprint'],old['fingerprint'])
        self.assertFalse(self.store.export()['records']['claims'])

    def test_unrelated_git_candidate_survives_confluence_metadata_change(self):
        (self.root/'A.cs').write_text('class A {}');scan=discovery.scan(self.store,max_files=100);p=self.store.prepare()
        self.register();self.register(version=2,content='Changed documentation.')
        self.store.apply(p['fingerprint'],p['fingerprint']);self.assertTrue(self.store.export()['records']['claims'])

    def test_first_mcp_collection_does_not_add_execution_artifacts_or_stale_git(self):
        (self.root/'A.cs').write_text('class A {}');discovery.scan(self.store,max_files=100);p=self.store.prepare()
        self.assertFalse((self.root/'.harness-writer.lock').exists())
        cf.dispatch(self.store,'register_snapshot',document());cf.dispatch(self.store,'register_snapshot',document(version=2,content='Changed documentation.'))
        self.assertFalse((self.root/'.harness-writer.lock').exists())
        self.store.apply(p['fingerprint'],p['fingerprint']);self.assertTrue(self.store.export()['records']['claims'])

    def test_stale_doc_is_explicitly_skipped_when_independent_git_work_remains(self):
        source=self.register();self.store.submit(proposal(self.store,source));self.register(version=2,content='Updated documentation.')
        self.store.submit(addition('local.fact','Separate local fixture.'))
        p=self.store.prepare();self.assertTrue(p['ok'],p['blocked']);self.assertEqual(p['skipped'][0]['reason'],'stale-confluence-revision')
        self.store.apply(p['fingerprint'],p['fingerprint']);self.assertEqual([c['id'] for c in self.store.export()['records']['claims']],['local.fact'])

    def test_rename_and_movement_preserve_source_and_snapshot_identity(self):
        first=cf.register(self.store,document())
        changed=document();changed.update(title='Renamed page',url='https://docs.example.invalid/wiki/spaces/NEW/pages/101/Renamed')
        second=cf.register(self.store,changed)
        self.assertEqual(first['source'],second['source']);rows=cf.dispatch(self.store,'inventory',{})['rows'];self.assertEqual(len(rows),1);self.assertEqual(rows[0]['title'],'Renamed page')
        with self.store.connection() as db:self.assertEqual(cf.snapshot(db,first['source']['snapshot'])['title'],'Synthetic shipping rule')

    def test_normalization_and_real_hash_are_verified(self):
        a=cf.register(self.store,document(content='\ufeffa\r\nb\rc\n'));b=cf.register(self.store,document(content='a\nb\nc\n'))
        self.assertEqual(a['source'],b['source'])
        value=document(page='102');value['content_hash']='sha256:'+'0'*64
        with self.assertRaisesRegex(KnowledgeError,'content-hash-mismatch'):cf.register(self.store,value)
        with self.assertRaisesRegex(KnowledgeError,'version-content-conflict'):self.register(content='Different content for same native version.')

    def test_invalid_versions_identity_snapshot_reference_and_quote_are_rejected(self):
        source=self.register()
        for key,value in (('identity','0'*64),('snapshot','0'*64),('revision',2)):
            bad={**source,key:value}
            with self.subTest(key=key),self.assertRaises(KnowledgeError):
                with self.store.connection() as db:cf.verify_binding(db,bad)
        for version in (True,0,-1,'1'):
            with self.subTest(version=version),self.assertRaises(KnowledgeError):cf.register(self.store,document(version=version))
        value=proposal(self.store,source);value['operations'][0]['payload']['description']='Quote not present in source'
        with self.assertRaisesRegex(KnowledgeError,'quote-not-found'):self.store.submit(value)

    def test_corruption_of_content_or_metadata_is_detected(self):
        for field in ('content','title'):
            with self.subTest(field=field):
                source=self.register(page='page-'+field)
                with self.store.connection(True) as db:
                    raw=json.loads(db.execute('SELECT payload FROM confluence_snapshots WHERE snapshot=?',(source['snapshot'],)).fetchone()[0]);raw[field]='CORRUPTED'
                    db.execute('UPDATE confluence_snapshots SET payload=? WHERE snapshot=?',(canonical_json(raw),source['snapshot']))
                with self.assertRaisesRegex(KnowledgeError,'corrupt-confluence-snapshot'):self.store.validate()
                # Fixture cleanup removes the deliberately corrupt, unused source.
                with self.store.connection(True) as db:
                    db.execute('DELETE FROM confluence_snapshots WHERE snapshot=?',(source['snapshot'],));db.execute('DELETE FROM confluence_pages WHERE identity=?',(source['identity'],))

    def test_registration_is_idempotent_and_stores_one_body_per_revision(self):
        source=self.register()
        for _ in range(5):self.register()
        for n in range(4):self.store.submit(proposal(self.store,source,'fact.'+str(n)))
        with self.store.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM confluence_snapshots').fetchone()[0],1)

    def test_legacy_store_extension_is_additive_and_transactional(self):
        self.store.submit(addition());p=self.store.prepare();self.store.apply(p['fingerprint'],p['fingerprint']);self.store.acknowledge(p['fingerprint'])
        before=self.store.export();original=cf.enable
        def interrupted(db):original(db);raise RuntimeError('synthetic migration interruption')
        with patch.object(cf,'enable',interrupted),self.assertRaises(RuntimeError):self.register()
        self.assertEqual(before,self.store.export());self.register()
        after=self.store.export();self.assertEqual(before['records'],after['records']);self.assertEqual(before['queue'],after['queue']);self.assertEqual(before['revisions'],after['revisions'])

    def test_credentials_and_non_native_source_substitution_are_rejected(self):
        value=document();value['token']='synthetic-forbidden-field'
        with self.assertRaisesRegex(KnowledgeError,'snapshot-fields'):cf.register(self.store,value)
        for address in ('https://user:pass@docs.example.invalid/wiki/1','https://docs.example.invalid/wiki/1?token=secret'):
            value=document();value['url']=address
            with self.assertRaises(KnowledgeError):cf.register(self.store,value)
        source=self.register();value=proposal(self.store,source);value['source']=None
        with self.assertRaisesRegex(KnowledgeError,'native-source-binding'):self.store.submit(value)


    def test_installed_mcp_snapshot_submit_plan_apply_and_offline_retrieval(self):
        from test_machine_commands import fixture
        from knowledge.project_commands import configure_project
        from knowledge.project import Project
        from core_wire import Wire
        with tempfile.TemporaryDirectory() as tmp:
            installation,root=fixture(tmp,0);store=Store(root);store.init();life.upgrade(store,life.upgrade_preview(store)['fingerprint']);configure_project(installation,Project(root))
            peer=Wire([sys.executable,'-I','-B','-m','knowledge.machine_mcp','--installation',installation],roots=lambda:[root])
            try:
                peer.initialize();caps=peer.tool('knowledge_capabilities');self.assertIn('confluence',caps['source_kinds'])
                registered=peer.tool('knowledge_confluence',action='register_snapshot',request=document());self.assertTrue(registered['ok'],registered)
                submitted=peer.tool('knowledge_submit_candidates',proposals=[proposal(store,registered['source'])]);self.assertTrue(submitted['ok'],submitted)
                plan=peer.tool('knowledge_plan');self.assertTrue(plan['ok'],plan)
                (root/'Independent.cs').write_text('class Independent {}')
                applied=peer.tool('knowledge_plan',action='apply',approve=plan['fingerprint']);self.assertTrue(applied['ok'],applied)
                context=peer.tool('knowledge_context',task='shipping address');self.assertIn('cf.claim',[c['id'] for c in context['claims']])
            finally:peer.close()

    def test_explicit_identity_migration_preserves_native_snapshots(self):
        import shutil
        from knowledge import identity_migration
        source=self.register();self.store.submit(proposal(self.store,source));p=self.store.prepare();self.store.apply(p['fingerprint'],p['fingerprint']);self.store.acknowledge(p['fingerprint'])
        with tempfile.TemporaryDirectory() as tmp:
            moved=Path(tmp)/'moved';moved.mkdir();shutil.copytree(self.store.base,moved/'.knowledge')
            preview=identity_migration.preview(moved,self.store.project.identity,Path(tmp)/'migration')
            identity_migration.apply(moved,preview['preview'],preview['fingerprint'])
            migrated=Store(moved);self.assertTrue(migrated.validate()['ok'])
            self.assertEqual(self.store.export()['records'],migrated.export()['records'])
            self.assertTrue(migrated.lookup('claims','cf.claim')['freshness']['trusted'])
            self.assertEqual(len(migrated.export()['confluence']['snapshots']),1)


if __name__=='__main__':unittest.main()
