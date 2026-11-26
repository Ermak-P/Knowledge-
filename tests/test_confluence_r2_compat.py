import json,subprocess,sys
from copy import deepcopy
from knowledge import confluence as cf,confluence_sync as cs,confluence_command as cc,lifecycle as life
from knowledge.util import digest,KnowledgeError
import test_confluence_command as fixture
from test_confluence_command import metadata,FINDING
from test_confluence_source import document
from confluence_fixtures import coverage,analyze_page

class UpgradeAndRecovery(fixture.ConfluenceCommand):
    def test_legacy_prepared_analysis_is_revalidated_without_discarding_history(self):
        self.scope();self.start();source=cf.register(self.store,document())['source']
        with self.store.connection(True) as db:
            cs.enable(db);batches,counts=cs.build_proposals(self.store,db,source,[FINDING],True)
            legacy=dict(id=digest(['legacy-analysis',source]),source=source,status='PREPARED',complete=True,batches=batches,candidates=[],counts=counts)
            cs.save_outbox(db,legacy)
            page=dict(cf.page(db,source['identity']));page['analysis_offset']=len(cf.snapshot(db,source['snapshot'])['content']);cs.save_page(db,page)
        old=self.store.submit(batches[0])['candidate']
        self.assertFalse(self.store.prepare()['ok'])
        cf.register(self.store,document())
        with self.store.connection() as db:self.assertEqual(cf.page(db,source['identity'])['analysis_offset'],0)
        result=cs.analyze(self.store,source,[FINDING],True,coverage=coverage(self.store,source))
        self.assertIn(old,result['candidates'])
        self.apply();self.assertEqual(len(self.store.export()['records']['claims']),1)
        with self.store.connection() as db:
            self.assertEqual(cc.state(db,'run')['status'],'RUNNING')
            self.assertEqual(cs._outbox(db,legacy['id'])['batches'],batches)
            self.assertEqual(db.execute('SELECT count(*) FROM queue').fetchone()[0],1)
    def test_legacy_absence_negative_stays_quarantined_after_full_reanalysis(self):
        from knowledge.util import canonical_json
        source=cf.register(self.store,document())['source'];analyze_page(self.store,source,[FINDING]);self.apply();before=self.store.export()['records']
        newer=cf.register(self.store,document(version=2,content='Updated documentation without an extracted historical finding.'))['source']
        old=before['evidence'][0];claim=before['claims'][0]
        with self.store.connection(True) as db:
            states=life.latest(db)
            batch=life.batch([life.op('update','evidence',old['id'],states[old['id']]['revision'],{**old,'status':'superseded'}),life.op('update','claims',claim['id'],states[claim['id']]['revision'],{**claim,'status':'NEEDS_HUMAN_CONFIRMATION','last_verified':None})],'Legacy omission-based proposal',newer)
            cid=digest(batch);db.execute("INSERT INTO queue VALUES (?,?,'pending',NULL)",(cid,canonical_json(batch)));cs.note_candidate(db,cid,batch)
            legacy=dict(id=digest(['legacy-negative',newer]),source=newer,status='PREPARED',complete=True,batches=[batch],candidates=[],counts={});cs.save_outbox(db,legacy)
        result=cs.analyze(self.store,newer,[],True,coverage=coverage(self.store,newer));self.assertEqual(result['candidates'],[])
        plan=self.store.prepare();self.assertFalse(plan['ok']);self.assertIn('coverage-revalidation-required',str(plan['skipped']))
        self.assertEqual(before,self.store.export()['records'])
        with self.assertRaisesRegex(KnowledgeError,'needs-targeted-revalidation'):self.store.submit(batch)
        same=cf.register(self.store,document(version=3,content='Updated documentation without an extracted historical finding.'))
        self.assertEqual(same['sync']['action'],'SKIP_ANALYSIS')
        self.assertIn('coverage-revalidation-required',str(self.store.prepare()['skipped']))
        with self.store.connection() as db:self.assertEqual(cs._outbox(db,legacy['id'])['batches'],[batch])
    def test_500_page_analysis_recovery_replays_no_success_and_no_candidates(self):
        # One existing canonical fact; ten newly recovered pages enrich it.
        original=cf.register(self.store,document(page='900'))['source'];analyze_page(self.store,original,[FINDING]);self.apply()
        self.scope();first=self.start(operations=2000)
        sources={str(n):cf.register(self.store,document(page=str(n)))['source'] for n in range(490,500)}
        with self.store.connection(True) as db:
            run=cc.state(db,'run');db.execute('DELETE FROM confluence_work');db.execute('DELETE FROM confluence_seen WHERE run=?',(run['id'],))
            for n in range(500):
                sid=cc.discovered(db,run,metadata(document(page=str(n))),'mandatory')
                db.execute("DELETE FROM confluence_work WHERE run=? AND json_extract(payload,'$.target')=?",(run['id'],sid))
                identifier=cc.enqueue(db,run,'analysis',sid);w=cc.work_at(db,identifier);w.update(status='DONE' if n<490 else 'FAILED')
                if n>=490:w['failure']='TIMEOUT'
                cc.save_work(db,w);item=cc.seen(db,run,sid);item.update(state='ANALYZED' if n<490 else 'FAILED',classification='unchanged',version=1)
                if n>=490:item.update(failure='TIMEOUT',state_before_failure='PENDING_ANALYSIS')
                cc.save_seen(db,item)
            run.update(status='PARTIAL',completed_operations=500);cc.save_state(db,'run',run)
            done=dict(db.execute("SELECT id,checksum FROM confluence_work WHERE status='DONE'"))
        code="import json,sys;from knowledge.store import Store;from knowledge import confluence as cf;print(json.dumps(cf.dispatch(Store(sys.argv[1]),'start',{'resume':True})))"
        process=subprocess.run([sys.executable,'-I','-c',code,str(self.root)],capture_output=True,text=True)
        self.assertEqual(process.returncode,0,process.stderr);self.assertEqual(json.loads(process.stdout)['run'],first['run'])
        for _ in range(10):
            task=self.call('next');self.assertNotIn(task['work']['id'],done)
            request=dict(work=task['work']['id'],result=dict(findings=[FINDING],complete=True))
            self.call('complete_work',request)
            with self.store.connection() as db:count=db.execute('SELECT count(*) FROM queue').fetchone()[0]
            self.call('complete_work',request)
            with self.store.connection() as db:self.assertEqual(db.execute('SELECT count(*) FROM queue').fetchone()[0],count)
        final=self.call('next');self.assertTrue(final['coverage_complete']);self.assertEqual(final['coverage']['failed'],0)
        self.apply();records=self.store.export()['records'];self.assertEqual(len(records['claims']),1);self.assertEqual(len(records['evidence']),11)
        with self.store.connection() as db:self.assertEqual(done,{i:c for i,c in db.execute('SELECT id,checksum FROM confluence_work') if i in done})


    def test_targeted_native_removal_preserves_independent_git_evidence(self):
        from knowledge import discovery
        from knowledge.util import loads
        (self.root/'A.cs').write_text('class A {}');discovery.scan(self.store,max_files=100)
        with self.store.connection() as db:batch=loads(db.execute('SELECT payload FROM queue').fetchone()[0])
        statement=next(o['payload']['statement'] for o in batch['operations'] if o['kind']=='claims')
        source=cf.register(self.store,document(content=statement))['source'];analyze_page(self.store,source,[dict(statement=statement,quote=statement,role='implementation')]);self.apply()
        before=self.store.export()['records'];native=next(e for e in before['evidence'] if cf.is_binding(e['source']));git=[e for e in before['evidence'] if not cf.is_binding(e['source'])]
        text='This implementation fact is no longer documented here; code remains independent.'
        newer=cf.register(self.store,document(version=2,content=text))['source']
        with self.store.connection() as db:revision=life.latest(db)[native['id']]['revision']
        review=dict(evidence=native['id'],expected=revision,verdict='removed',quote=text,reason='Explicit synthetic targeted review of this historical native evidence; Git is independent.')
        cs.analyze(self.store,newer,[],True,coverage=coverage(self.store,newer),revalidations=[review]);self.assertEqual(before,self.store.export()['records'])
        self.apply();after=self.store.export()['records'];self.assertEqual(git,[e for e in after['evidence'] if not cf.is_binding(e['source'])]);self.assertEqual(after['claims'][0]['evidence'],[e['id'] for e in git]);self.assertEqual(after['claims'][0]['status'],'CONFIRMED');self.assertEqual(next(e for e in after['evidence'] if e['id']==native['id'])['status'],'retracted')

    def test_legacy_partial_cursor_does_not_skip_uncovered_prefix(self):
        value=document(content='A'*6500);source=cf.register(self.store,value)['source'];partial=cs.analyze(self.store,source,[],False,coverage=coverage(self.store,source,[0]))
        with self.store.connection(True) as db:
            data=cs._outbox(db,partial['checkpoint']);data.pop('coverage_chunks');cs.save_outbox(db,data)
            page=dict(cf.page(db,source['identity']));page['analysis_offset']=4000;cs.save_page(db,page)
        cf.register(self.store,value)
        with self.store.connection() as db:self.assertEqual(cf.page(db,source['identity'])['analysis_offset'],0)
        self.assertEqual(cs.resume(self.store,partial['checkpoint'])['coverage']['continuous_until'],0)

    def test_verified_noncontiguous_coverage_restores_only_its_continuous_cursor(self):
        value=document(content='A'*6500);source=cf.register(self.store,value)['source']
        partial=cs.analyze(self.store,source,[],False,coverage=coverage(self.store,source,[0,4000]))
        with self.store.connection(True) as db:
            page=dict(cf.page(db,source['identity']));page['analysis_offset']=6000;cs.save_page(db,page)
        cf.register(self.store,value)
        with self.store.connection() as db:self.assertEqual(cf.page(db,source['identity'])['analysis_offset'],2000)
        state=cs.resume(self.store,partial['checkpoint'])['coverage'];self.assertEqual(state['continuous_until'],2000);self.assertEqual(state['covered_characters'],4000)
