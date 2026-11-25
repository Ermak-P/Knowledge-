"""Partial discovery recovery with durable, synthetic 500-page work receipts."""
import json,subprocess,sys
from knowledge import confluence as cf,confluence_command as cc
from knowledge.util import KnowledgeError,digest
from test_confluence_command import ConfluenceCommand,metadata
from test_confluence_source import document


class PartialRecovery(ConfluenceCommand):
    # Inherit the real command driver as well as its regression scenarios.
    def test_500_pages_resume_same_run_without_repeating_490_done(self):
        self.scope();first=self.start(operations=2000)
        with self.store.connection(True) as db:
            run=cc.state(db,'run');db.execute('DELETE FROM confluence_work')
            for n in range(500):
                sid=cc.discovered(db,run,metadata(document(page=str(n))),'mandatory')
                db.execute("DELETE FROM confluence_work WHERE run=? AND kind='metadata' AND json_extract(payload,'$.target')=?",(run['id'],sid))
                identifier=cc.enqueue(db,run,'children',sid,cursor='retained-page-2')
                work=cc.work_at(db,identifier)
                work.update(status='DONE' if n<490 else 'FAILED',coverage_exhausted=n<490)
                if n>=490:work['failure']='TIMEOUT'
                cc.save_work(db,work)
                # Remove the first-page job; retained cursor is the exact retry unit.
                db.execute("DELETE FROM confluence_work WHERE run=? AND id<>? AND json_extract(payload,'$.target')=?",(run['id'],identifier,sid))
                item=cc.seen(db,run,sid);item.update(state='UNCHANGED' if n<490 else 'FAILED',classification='unchanged',version=1);cc.save_seen(db,item)
            run.update(status='PARTIAL',completed_operations=500);cc.save_state(db,'run',run)
            done=dict(db.execute("SELECT id,checksum FROM confluence_work WHERE status='DONE'"))
        code="import json,sys;from knowledge.store import Store;from knowledge import confluence as cf;print(json.dumps(cf.dispatch(Store(sys.argv[1]),'start',{'resume':True})))"
        process=subprocess.run([sys.executable,'-I','-c',code,str(self.root)],capture_output=True,text=True)
        self.assertEqual(process.returncode,0,process.stderr);resumed=json.loads(process.stdout)
        self.assertEqual(resumed['run'],first['run']);self.assertEqual(resumed['completed_operations'],500)
        retried=[]
        for _ in range(10):
            task=self.call('next');work=task['work'];retried.append(work['id']);self.assertEqual(work['cursor'],'retained-page-2')
            request=dict(work=work['id'],result=dict(pages=[],has_more=False))
            self.call('complete_work',request);self.call('complete_work',request)
        self.assertEqual(len(set(retried)),10);self.assertTrue(self.call('next')['coverage_complete'])
        with self.store.connection() as db:
            self.assertEqual(done,{i:c for i,c in db.execute("SELECT id,checksum FROM confluence_work WHERE status='DONE'") if i in done})
            self.assertEqual(db.execute('SELECT count(*) FROM queue').fetchone()[0],0)
            self.assertEqual(cc.state(db,'run')['completed_operations'],510)
            self.assertEqual(db.execute('SELECT count(*) FROM confluence_seen WHERE run=?',(first['run'],)).fetchone()[0],500)
    def test_partial_permanent_and_skipped_not_retried_and_transients_bounded(self):
        self.scope(('200',));first=self.start()
        task=self.call('next');identifier=task['work']['id']
        for n in range(4):
            self.call('complete_work',dict(work=identifier,result={'reason':'TIMEOUT'}));self.call('next')
            self.call('start',{'resume':True})
            with self.store.connection() as db:w=cc.work_at(db,identifier)
            self.assertEqual(w['status'],'PENDING' if n<3 else 'FAILED')
        with self.assertRaisesRegex(KnowledgeError,'retry-limit'):self.call('retry',{'work':identifier})
        self.assertEqual(self.call('status')['run'],first['run'])
        new=self.call('start',{'fresh':True});self.assertNotEqual(new['run'],first['run'])
        task=self.call('next');self.call('complete_work',dict(work=task['work']['id'],result={'reason':'ACCESS_DENIED'}));self.call('next')
        self.call('start',{'resume':True})
        self.assertIsNone(self.call('next')['work'])
        self.scope(('101',))
        with self.assertRaisesRegex(KnowledgeError,'scope-changed'):self.call('start',{'resume':True})
