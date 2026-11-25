"""Progress is non-authoritative telemetry; canonical guards remain mandatory."""
import threading
from contextlib import closing
from unittest.mock import patch
from knowledge import confluence as cf,confluence_command as cc
from knowledge.coordination import gate
from knowledge.util import KnowledgeError
import test_confluence_command as fixture


class ProgressAccess(fixture.ConfluenceCommand):
    def test_light_progress_matches_public_counts_without_canonical_reads(self):
        self.scope();self.start();self.drain();full=self.call('status')
        with patch.object(self.store,'connection',side_effect=AssertionError('full validation requested')):
            light=self.call('progress')
        for key in ('run','state','coverage','work','completed_operations','operation_budget','applied_pages'):
            self.assertEqual(light[key],full[key],key)
        self.assertEqual(light['candidate_validation'],'NOT_RUN')
        with self.store.progress_connection() as db:
            with self.assertRaises(Exception):db.execute('SELECT payload FROM records').fetchall()
            with self.assertRaises(Exception):db.execute("UPDATE metadata SET value='bad'")
    def test_progress_can_read_during_collection_but_maintenance_still_freezes(self):
        self.scope();self.start();entered=threading.Event();release=threading.Event();errors=[]
        original=cf._dispatch
        def paused(store,action,request):
            if action=='next':entered.set();release.wait(10)
            return original(store,action,request)
        def worker():
            try:self.call('next')
            except Exception as error:errors.append(str(error))
        with patch.object(cf,'_dispatch',paused):
            thread=threading.Thread(target=worker);thread.start()
            try:
                self.assertTrue(entered.wait(10));self.assertEqual(self.call('progress')['state'],'RUNNING')
                with self.assertRaisesRegex(KnowledgeError,'writer-busy'):self.call('next')
                with self.assertRaisesRegex(KnowledgeError,'maintenance-busy'):
                    with gate(self.root,exclusive=True):pass
            finally:release.set();thread.join(10)
        self.assertFalse(errors,errors)
    def test_progress_does_not_claim_integrity_and_corruption_still_blocks_canonical(self):
        self.scope();self.start()
        import sqlite3
        with closing(sqlite3.connect(self.store.path)) as db:
            db.execute("INSERT INTO queue VALUES ('bad','{}','pending',NULL)");db.commit()
        self.assertEqual(self.call('progress')['candidate_validation'],'NOT_RUN')
        with self.assertRaises(KnowledgeError):self.store.prepare()
        with self.assertRaises(KnowledgeError):self.call('status')

    def test_failed_page_remains_visible_when_another_operation_succeeds(self):
        self.scope(('200',));self.start();task=self.call('next')
        self.call('complete_work',dict(work=task['work']['id'],result=self.mcp.result(task['work'])))
        task=self.call('next');self.assertEqual(task['work']['kind'],'children')
        self.call('complete_work',dict(work=task['work']['id'],result={'reason':'TIMEOUT'}))
        done=self.drain();self.assertEqual(done['state'],'PARTIAL')
        self.assertEqual(done['coverage']['failed'],1)
        self.assertEqual(self.call('progress')['coverage']['failed'],1)
        self.call('start',{'resume':True});self.assertTrue(self.drain()['coverage_complete'])
        self.assertEqual(self.call('progress')['coverage']['failed'],0)
