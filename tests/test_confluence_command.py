"""Agent-mediated Confluence MCP fixtures; no live service/private data."""
import json,tempfile,unittest,sys,shutil
from pathlib import Path
from unittest.mock import patch
from knowledge import lifecycle as life,confluence as cf,confluence_command as command,discovery
from knowledge.store import Store
from knowledge.util import KnowledgeError,digest
from test_confluence_source import document

QUOTE='Synthetic checkout requires a shipping address.'
FINDING={'statement':QUOTE,'quote':QUOTE,'role':'requirement'}

def metadata(page):return {k:v for k,v in page.items() if k in ('instance','page_id','version','title','url','space_key','modified_at')}

class MockConfluenceMCP:
    def __init__(self):
        self.pages={p:document(page=p) for p in ('101','102','103','200')};self.calls=[];self.fail=set()
    def result(self,work):
        kind=work['kind'];target=work['target'];cursor=work['cursor'];self.calls.append((kind,target,cursor))
        if kind=='search':return dict(pages=[metadata(self.pages['103']),metadata(self.pages['101'])],has_more=False)
        pid=target.rsplit('/',1)[-1] if kind=='root' else next(p for p in self.pages if cf.identity('synthetic-cloud-id',p)==target)
        if (kind,pid) in self.fail:return {'reason':'ACCESS_DENIED'}
        if kind in ('root','metadata'):return {'page':metadata(self.pages[pid])}
        if kind=='children':
            if pid=='101':return dict(pages=[metadata(self.pages['102' if cursor is None else '103'])],has_more=cursor is None,**({'next_cursor':'second'} if cursor is None else {}))
            if pid=='103':return dict(pages=[metadata(self.pages['101'])],has_more=False) # recursive duplicate/cycle
            return dict(pages=[],has_more=False)
        if kind=='content':return {'snapshot':self.pages[pid]}
        return {'findings':[FINDING],'complete':True}

class ConfluenceCommand(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.store=Store(self.root)
        self.store.init();life.upgrade(self.store,life.upgrade_preview(self.store)['fingerprint']);self.mcp=MockConfluenceMCP()
    def call(self,action,request=None):return cf.dispatch(self.store,action,request or {})
    def scope(self,roots=('101',),autonomous=False,**extra):
        return self.call('scope',{'scope':dict(roots=[document(page=p)['url'] for p in roots],spaces=[],autonomous=autonomous,**extra)})
    def start(self,**extra):return self.call('start',{'capabilities':{'metadata_only':True,'children':True,'search':True,'content':True},**extra})
    def drain(self,limit=200,inspect=None):
        for _ in range(limit):
            task=self.call('next');work=task.get('work')
            if work is None:return self.call('status')
            if inspect:inspect(work)
            self.call('complete_work',{'work':work['id'],'result':self.mcp.result(work)})
        self.fail('mock driver exceeded bounded fixture budget')
    def apply(self):
        plan=self.store.prepare();self.assertTrue(plan['ok'],plan['blocked']);self.store.apply(plan['fingerprint'],plan['fingerprint']);self.store.acknowledge(plan['fingerprint'])
    def test_first_use_scope_persists_multiple_roots_and_no_automatic_apply(self):
        self.assertEqual(self.call('status')['state'],'SCOPE_REQUIRED');self.scope(('101','200'));self.start();done=self.drain()
        self.assertEqual(done['coverage']['total_unique_pages'],4);self.assertEqual(done['coverage']['mandatory_pages'],4)
        self.assertEqual(len(done['mandatory_sections']),2);self.assertTrue(done['coverage_complete']);self.assertEqual(done['applied_pages'],0)
        self.assertTrue(done['knowledge_update_required']);self.assertFalse(self.store.export()['records']['claims'])
        self.assertEqual(self.call('finish')['integrity'],'PASS');self.apply();self.assertEqual(len(self.store.export()['records']['claims']),1)
        reopened=Store(self.root);self.assertEqual(cf.dispatch(reopened,'status',{})['scope'],done['scope'])
    def test_recursive_pagination_and_duplicate_references_are_durable(self):
        self.scope();self.start();self.drain();children=[v for v in self.mcp.calls if v[0]=='children']
        self.assertEqual(len(children),4);self.assertEqual(len({(v[1],v[2]) for v in children}),4)
        self.assertEqual(self.call('status')['coverage']['total_unique_pages'],3)
    def test_subsequent_unchanged_run_does_not_fetch_or_analyze_content(self):
        self.scope();self.start();self.drain();self.apply();self.mcp.calls=[];self.start();done=self.drain()
        self.assertEqual(done['coverage']['unchanged'],3);self.assertFalse(any(k in ('content','analysis') for k,_,_ in self.mcp.calls))
        self.assertEqual(done['pending_candidates'],0);self.assertFalse(done['knowledge_update_required'])
    def test_one_changed_page_only_is_reanalyzed_then_applied(self):
        self.scope();self.start();self.drain();self.apply();cid=self.store.export()['records']['claims'][0]['id']
        self.mcp.pages['102']=document(page='102',version=2,content=QUOTE+' New context.');self.mcp.calls=[];self.start();done=self.drain()
        self.assertEqual(done['coverage']['changed'],1);self.assertEqual([t for k,t,_ in self.mcp.calls if k=='analysis'],[cf.identity('synthetic-cloud-id','102')])
        self.apply();self.assertEqual(self.store.export()['records']['claims'][0]['id'],cid);self.assertTrue(self.store.lookup('claims',cid)['freshness']['trusted'])
    def test_same_body_new_version_skips_semantics(self):
        self.scope();self.start();self.drain();self.apply();self.mcp.pages['102']=document(page='102',version=2);self.mcp.calls=[];self.start();done=self.drain()
        self.assertFalse(any(k=='analysis' for k,_,_ in self.mcp.calls));self.assertEqual(done['coverage']['unchanged'],3);self.assertEqual(done['pending_candidates'],0)
    def test_budget_pause_retains_queue_and_resumes_same_run(self):
        self.scope();first=self.start(operations=2);stopped=self.drain();self.assertEqual(stopped['state'],'BUDGET_PAUSED');self.assertFalse(stopped['coverage_complete'])
        second=self.call('start',{'extra_operations':100});self.assertEqual(second['run'],first['run']);done=self.drain();self.assertTrue(done['coverage_complete'])
    def test_autonomous_search_only_after_mandatory_work_and_terms_deduplicate(self):
        self.scope(autonomous=True);self.start();self.call('terms',{'terms':['Shipping',' shipping  ','SHIPPING']})
        seen_search=False
        def inspect(work):
            nonlocal seen_search
            if work['kind']=='search':seen_search=True
            if seen_search:self.assertGreaterEqual(work['priority'],2)
        done=self.drain(inspect=inspect);self.assertTrue(done['coverage_complete'])
        searches=[t for k,t,_ in self.mcp.calls if k=='search'];self.assertEqual(searches.count('shipping'),1)
        self.assertEqual(done['coverage']['total_unique_pages'],3)
    def test_autonomous_only_scope_and_unapproved_search_refuses(self):
        with self.assertRaisesRegex(KnowledgeError,'roots-or-autonomous'):self.scope(roots=())
        self.scope(roots=(),autonomous=True);self.start();done=self.drain();self.assertTrue(done['coverage_complete']);self.assertEqual(done['coverage']['mandatory_pages'],0)
        self.scope();self.start()
        with self.assertRaisesRegex(KnowledgeError,'not-authorized'):self.call('terms',{'terms':['Shipping']})
    def test_inaccessible_section_is_partial_and_explicit_retry_preserves_knowledge(self):
        self.scope(('101','200'));self.mcp.fail.add(('root','200'));self.start();done=self.drain();self.assertFalse(done['coverage_complete']);self.assertEqual(done['state'],'PARTIAL')
        self.assertTrue(done['limitations']);self.mcp.fail.clear()
        with self.store.connection() as db:identifier=db.execute("SELECT id FROM confluence_work WHERE status='FAILED'").fetchone()[0]
        self.call('retry',{'work':identifier});self.assertTrue(self.drain()['coverage_complete']);self.store.validate()
    def test_incomplete_pagination_is_not_silently_complete(self):
        self.scope();self.start();task=self.call('next');self.call('complete_work',{'work':task['work']['id'],'result':self.mcp.result(task['work'])});task=self.call('next')
        self.assertEqual(task['work']['kind'],'children')
        with self.assertRaisesRegex(KnowledgeError,'pagination-cursor-required'):self.call('complete_work',{'work':task['work']['id'],'result':{'pages':[],'has_more':True}})
        self.assertFalse(self.call('status')['coverage_complete'])
    def test_restart_and_replayed_receipts_are_idempotent(self):
        self.scope();self.start();task=self.call('next');result=self.mcp.result(task['work']);request={'work':task['work']['id'],'result':result}
        first=self.call('complete_work',request);second=cf.dispatch(Store(self.root),'complete_work',request)
        self.assertEqual(first['completed_operations'],second['completed_operations']);self.drain();self.apply();self.assertEqual(len(self.store.export()['records']['claims']),1)
    def test_scope_change_cannot_resume_old_work_or_reuse_unapproved_autonomous_pages(self):
        self.scope(roots=(),autonomous=True);self.start();self.drain();self.scope(('200',));self.start();done=self.drain()
        self.assertEqual(done['coverage']['total_unique_pages'],1);self.assertEqual(done['coverage']['autonomous_pages'],0)
    def test_partial_analysis_persists_offset_and_retry_does_not_charge_twice(self):
        self.scope();self.start()
        while True:
            task=self.call('next');work=task['work']
            if work['kind']=='analysis':break
            self.call('complete_work',{'work':work['id'],'result':self.mcp.result(work)})
        request={'work':work['id'],'result':{'findings':[FINDING],'complete':False,'analyzed_until':10}}
        self.call('complete_work',request);before=self.call('status')['completed_operations'];self.call('complete_work',request)
        self.assertEqual(self.call('status')['completed_operations'],before)
        task=cf.dispatch(Store(self.root),'next',{});self.assertEqual(task['page']['analysis_offset'],10)
        self.call('complete_work',{'work':work['id'],'result':{'findings':[],'complete':True}});self.drain();self.apply()
        self.assertEqual(len(self.store.export()['records']['claims']),1)

    def test_space_metadata_is_required_before_traversal_or_content(self):
        self.call('scope',{'scope':{'roots':[document()['url']],'spaces':['SYN'],'autonomous':False}});self.start()
        root=self.call('next')['work'];self.call('complete_work',{'work':root['id'],'result':self.mcp.result(root)})
        task=self.call('next')['work'];self.assertEqual(task['kind'],'metadata')
        with self.assertRaisesRegex(KnowledgeError,'space-verification-required'):
            self.call('complete_work',{'work':task['id'],'result':self.mcp.result(task)})
        page=metadata(document());page['space_key']='SYN'
        self.call('complete_work',{'work':task['id'],'result':{'page':page}})
        self.assertEqual(self.call('next')['work']['kind'],'children')

    def test_source_results_cannot_change_approved_scope(self):
        self.scope();self.start();work=self.call('next')['work'];scope=self.call('status')['scope']
        with self.assertRaisesRegex(KnowledgeError,'invalid-confluence-work-result'):
            self.call('complete_work',{'work':work['id'],'result':{'scope':{'autonomous':True}}})
        self.assertEqual(self.call('status')['scope'],scope)

    def test_command_checkpoint_corruption_is_detected(self):
        self.scope();self.start()
        with self.store.connection(True) as db:db.execute("UPDATE confluence_work SET payload='{}'")
        with self.assertRaisesRegex(KnowledgeError,'corrupt-confluence-command-checkpoint'):self.store.validate()

    def test_full_page_metadata_fallback_reuses_snapshot_without_second_fetch(self):
        self.scope();self.start();work=self.call('next')['work'];self.call('complete_work',{'work':work['id'],'result':self.mcp.result(work)})
        while True:
            work=self.call('next')['work']
            if work['kind']=='metadata':break
            self.call('complete_work',{'work':work['id'],'result':self.mcp.result(work)})
        pid=next(p for p in self.mcp.pages if cf.identity('synthetic-cloud-id',p)==work['target'])
        self.call('complete_work',{'work':work['id'],'result':{'page':metadata(self.mcp.pages[pid]),'snapshot':self.mcp.pages[pid]}})
        with self.store.connection() as db:self.assertIsNone(db.execute("SELECT 1 FROM confluence_work WHERE kind='content' AND json_extract(payload,'$.target')=?",(work['target'],)).fetchone())
        self.drain();self.apply();self.store.validate()

    def test_repeating_pagination_cursor_does_not_claim_complete(self):
        self.scope();self.start()
        while True:
            work=self.call('next')['work']
            if work['kind']=='children' and work['cursor'] is None:break
            self.call('complete_work',{'work':work['id'],'result':self.mcp.result(work)})
        target=work['target'];self.call('complete_work',{'work':work['id'],'result':{'pages':[],'has_more':True,'next_cursor':'A'}})
        work=self.call('next')['work'];self.assertEqual(work['cursor'],'A')
        self.call('complete_work',{'work':work['id'],'result':{'pages':[],'has_more':True,'next_cursor':'B'}})
        work=self.call('next')['work'];self.assertEqual(work['cursor'],'B')
        with self.assertRaisesRegex(KnowledgeError,'pagination-cycle'):
            self.call('complete_work',{'work':work['id'],'result':{'pages':[],'has_more':True,'next_cursor':'A'}})
        self.assertFalse(self.call('status')['coverage_complete'])

    def test_scope_changes_invalidate_previous_complete_coverage(self):
        self.scope();self.start();self.drain();self.scope(('200',))
        self.assertEqual(self.call('status')['state'],'SCOPE_CHANGED');self.assertFalse(self.call('status')['coverage_complete'])

    def test_explicit_identity_migration_preserves_canonical_source_evidence(self):
        from knowledge import identity_migration
        self.scope();self.start();self.drain();self.apply()
        with tempfile.TemporaryDirectory() as tmp:
            moved=Path(tmp)/'moved';moved.mkdir();shutil.copytree(self.store.base,moved/'.knowledge')
            preview=identity_migration.preview(moved,self.store.project.identity,Path(tmp)/'migration')
            identity_migration.apply(moved,preview['preview'],preview['fingerprint'])
            migrated=Store(moved);self.assertTrue(migrated.validate()['ok']);self.assertEqual(self.store.export()['records'],migrated.export()['records'])

    def test_installed_command_and_mcp_complete_native_lifecycle_and_alias(self):
        from test_machine_commands import fixture
        from knowledge.project_commands import execute
        from core_wire import Wire
        with tempfile.TemporaryDirectory() as tmp:
            installation,root=fixture(tmp,0)
            first=execute('knowledge-confluence',installation,root,{})
            self.assertEqual(first['state'],'SCOPE_REQUIRED');store=Store(root)
            peer=Wire([sys.executable,'-I','-B','-m','knowledge.machine_mcp','--installation',installation],roots=lambda:[root])
            try:
                peer.initialize();self.assertTrue(peer.tool('knowledge_confluence',action='scope',request={'scope':{'roots':[document()['url']],'spaces':[],'autonomous':False}})['ok'])
                self.assertTrue(peer.tool('knowledge_confluence',action='start',request={})['ok'])
                for _ in range(100):
                    task=peer.tool('knowledge_confluence',action='next',request={});self.assertTrue(task['ok'],task)
                    work=task.get('work')
                    if not work:break
                    response=peer.tool('knowledge_confluence',action='complete_work',request={'work':work['id'],'result':self.mcp.result(work)})
                    self.assertTrue(response['ok'],response)
                else:self.fail('MCP did not finish')
                prepared=execute('knowledge-update',installation,root,{});self.assertTrue(prepared['ok'],prepared)
                execute('knowledge-update',installation,root,{'approve':prepared['fingerprint']});self.assertEqual(len(store.export()['records']['claims']),1)
                self.assertTrue(peer.tool('knowledge_context',task='shipping')['claims'])
                original=prepared['fingerprint']
                self.mcp.pages['102']=document(page='102',version=2,content=QUOTE+' Updated.');peer.tool('knowledge_confluence',action='start',request={})
                for _ in range(100):
                    task=peer.tool('knowledge_confluence',action='next',request={});work=task.get('work')
                    if not work:break
                    response=peer.tool('knowledge_confluence',action='complete_work',request={'work':work['id'],'result':self.mcp.result(work)});self.assertTrue(response['ok'],response)
                else:self.fail('Incremental MCP run did not finish')
                prepared=execute('knowledge-update',installation,root,{});execute('knowledge-update',installation,root,{'approve':prepared['fingerprint']});self.assertTrue(store.validate()['ok'])
                self.assertNotEqual(prepared['fingerprint'],original)
                native=[e for e in store.export()['records']['evidence'] if e['source']['identity']==cf.identity('synthetic-cloud-id','102')]
                self.assertEqual(sorted((e['source']['revision'],e['status']) for e in native),[(1,'superseded'),(2,'active')])
            finally:peer.close()

    def test_collection_enrollment_does_not_stale_existing_core_git_plan(self):
        from test_machine_commands import fixture
        from knowledge.project_commands import execute
        with tempfile.TemporaryDirectory() as tmp:
            installation,root=fixture(tmp,1);store=Store(root);store.init();life.upgrade(store,life.upgrade_preview(store)['fingerprint'])
            discovery.scan(store,max_files=100);plan=store.prepare();self.assertTrue(plan['ok'],plan)
            self.assertFalse((root/'.harness-writer.lock').exists())
            execute('knowledge-confluence',installation,root,{})
            self.assertFalse((root/'.harness-writer.lock').exists())
            store.apply(plan['fingerprint'],plan['fingerprint']);self.assertTrue(store.validate()['ok'])

if __name__=='__main__':unittest.main()
