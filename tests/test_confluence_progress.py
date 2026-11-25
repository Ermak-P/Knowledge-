"""Progress is non-authoritative telemetry; canonical guards remain mandatory."""
import threading
from unittest.mock import patch
from knowledge import confluence as cf,confluence_command as cc
from knowledge.coordination import gate
from knowledge.util import KnowledgeError
from test_confluence_command import ConfluenceCommand


class ProgressAccess(ConfluenceCommand):
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
        with sqlite3.connect(self.store.path) as db:db.execute("INSERT INTO queue VALUES ('bad','{}','pending',NULL)")
        self.assertEqual(self.call('progress')['candidate_validation'],'NOT_RUN')
        with self.assertRaises(KnowledgeError):self.store.prepare()
        with self.assertRaises(KnowledgeError):self.call('status')
