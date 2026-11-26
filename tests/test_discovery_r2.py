"""R2 capture, immutable terminal history, and bounded candidate delivery."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from threading import Barrier
import unittest
from unittest.mock import patch

from fixtures import addition
from harness.capture import deliver
from harness.runtime import Journal, source_snapshot
from knowledge import discovery as d, discovery_history, identity_migration, lifecycle as life
from knowledge.store import Store
from knowledge.util import KnowledgeError, canonical_json, digest, loads
from test_p1 import git


CAPTURED = '2026-11-26T10:00:00+00:00'


class DiscoveryR2(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / 'source'
        self.root.mkdir()
        self.store = Store(self.root)
        self.store.init()
        life.upgrade(self.store, life.upgrade_preview(self.store)['fingerprint'])

    def write(self, path, content):
        (self.root/path).write_text(content, encoding='utf-8')

    def repository(self):
        self.write('.gitignore','.knowledge/\n.knowledge-control.lock\n.harness/\n')
        git(self.root, 'init')
        git(self.root, 'config', 'user.name', 'Fixture')
        git(self.root, 'config', 'user.email', 'fixture@example.invalid')
        git(self.root, 'add', '.')
        git(self.root, 'commit', '-m', 'fixture')
        return git(self.root, 'rev-parse', 'HEAD')

    def cache(self):
        with self.store.connection() as db:
            return {p: (binding, loads(payload)) for p,binding,payload in
                    db.execute('SELECT path,binding,payload FROM discovery_file_cache')}

    def warm(self):
        for path in ('A','B'):
            self.write(path+'.cs', f'class {path} {{}}')
        return d.scan(self.store)

    def run_state(self,journal,initial,number):
        current = source_snapshot(journal.project)
        value = dict(version=1,id=f'fixture-{number}',project=journal.project.identity,
                     task={'initial_source':initial},final_source=digest(current),
                     capture_time=CAPTURED,capture_event=number)
        journal.save(value)
        return value

    def test_ten_consecutive_harness_deliveries_match_full_analysis(self):
        journal = Journal(self.root)
        for n in range(10):
            self.write(f'Source{n}.cs',f'class Initial{n} {{}}')
        self.repository()
        d.scan(self.store)
        for n in range(10):
            before = source_snapshot(journal.project)
            path = f'Source{n}.cs'
            self.write(path, f'class Revised{n} {{}}')
            trusted = d.analysis_scope(self.root)
            with self.store.connection() as db:
                record = next(o for o in trusted['observations'] if o['path']==path)
                expected = d.proposal(self.store, db, record, trusted['snapshot'], CAPTURED,
                                      self.store._records(db),life.latest(db),trusted)
            with patch.object(d,'extract',wraps=d.extract) as extracted:
                run = self.run_state(journal,before,n)
                deliver(journal,run,{'capture':'required','limits':{}})
                first = journal.outbox(run['id'])
                deliver(journal,run,{'capture':'required','limits':{}})
            self.assertEqual([c.args[1] for c in extracted.call_args_list],[path])
            self.assertEqual(run['capture']['state'],'delivered')
            self.assertEqual(first,journal.outbox(run['id']))
            accepted = next(iter(first.values()))
            self.assertEqual(accepted['decision']['payload'],expected)
            self.assertEqual(self.cache()[path][1],[record])
        self.assertEqual(len(d.status(self.store)['scans']),1)
        self.assertFalse(self.store.export()['records']['claims'])

    def test_preview_has_no_side_effect_and_empty_observations_replace_old_cache(self):
        self.warm()
        initial = self.cache()
        for text in ('// first blank','// another blank'):
            self.write('A.cs',text)
            preview = d.candidate_preview(self.store,['A.cs'],CAPTURED)
            self.assertEqual(preview['decisions'],[])
            self.assertEqual(self.cache()['A.cs'],initial['A.cs'])
            self.assertEqual(d.capture_observation_receipts(self.store)['receipts'],[])
            observed = d.candidate_observe(self.store,['A.cs'],CAPTURED)
            self.assertEqual(observed['decisions'],[])
            updated = self.cache()
            self.assertNotEqual(initial['A.cs'][0],updated['A.cs'][0])
            self.assertEqual(updated['A.cs'][1],[])
            initial = updated
        self.write('B.cs','class ChangedB {}')
        self.assertEqual(d.candidate_observe(self.store,['B.cs'],CAPTURED)['decisions'][0]['decision'],'submit')

    def test_rename_deletion_ambiguity_and_configuration_invalidation(self):
        self.warm()
        (self.root/'A.cs').rename(self.root/'Renamed.cs')
        self.write('Renamed.cs','class B {}')
        result = d.candidate_observe(self.store,['A.cs','Renamed.cs'],CAPTURED)
        trusted = d.analysis_scope(self.root)
        self.assertEqual(result['gaps'],list(trusted['ambiguous']))
        self.assertEqual([r['decision'] for r in result['decisions']],['manual-review'])
        self.assertEqual(set(self.cache()),{'B.cs','Renamed.cs'})
        (self.root/'Renamed.cs').unlink()
        self.assertEqual(d.candidate_observe(self.store,['Renamed.cs'],CAPTURED)['decisions'],[])
        self.assertEqual(set(self.cache()),{'B.cs'})
        self.write('A.cs','class A {}')
        self.write('global.json','{"sdk":{"version":"10.0.100"}}')
        with self.assertRaisesRegex(KnowledgeError,'capture-observation-cache-incomplete'):
            d.candidate_observe(self.store,['A.cs'],CAPTURED)

    def test_capture_drift_and_corrupt_rows_block_publication(self):
        self.warm()
        before = self.cache()
        self.write('A.cs','class Changed {}')
        verify = d._verify_capture_snapshot

        def drift(*args):
            self.write('A.cs','class Drifted {}')
            return verify(*args)

        with (patch.object(d,'_verify_capture_snapshot',side_effect=drift),
              self.assertRaisesRegex(KnowledgeError,'source-changed-during-preview')):
            d.candidate_observe(self.store,['A.cs'],CAPTURED)
        self.assertEqual(self.cache(),before)
        self.assertEqual(d.capture_observation_receipts(self.store)['receipts'],[])
        with self.store.connection(True) as db:
            db.execute("UPDATE discovery_file_cache SET checksum='damaged' WHERE path='B.cs'")
        with self.assertRaisesRegex(KnowledgeError,'corrupt-discovery-observation-cache'):
            d.candidate_observe(self.store,['A.cs'],CAPTURED)

    def test_capture_commit_crash_binds_receipts_and_cache_together(self):
        self.warm()
        before = self.cache()
        self.write('A.cs','class AfterCrash {}')
        script = """
import os,sys
from knowledge import discovery,store
def checkpoint(phase):
    if phase=='before-commit' and sys.argv[2]=='before':
        os._exit(37)
store.checkpoint=checkpoint
discovery.candidate_observe(store.Store(sys.argv[1]),['A.cs'],sys.argv[3])
os._exit(37)
"""
        for phase in ('before','after'):
            child = subprocess.run([sys.executable,'-c',script,str(self.root),phase,CAPTURED],timeout=40)
            self.assertEqual(child.returncode,37)
            if phase=='before':
                self.assertEqual(self.cache(),before)
                self.assertEqual(d.capture_observation_receipts(self.store)['receipts'],[])
            else:
                self.assertNotEqual(self.cache(),before)
                self.assertEqual(len(d.capture_observation_receipts(self.store)['receipts']),1)
        d.candidate_observe(self.store,['A.cs'],CAPTURED)
        self.assertEqual(len(d.capture_observation_receipts(self.store)['receipts']),1)

    def test_concurrent_capture_preserves_one_replayable_receipt(self):
        self.warm()
        self.write('A.cs','class Concurrent {}')
        barrier = Barrier(2)
        verify = d._verify_capture_snapshot

        def simultaneous(*args):
            verify(*args)
            barrier.wait(timeout=10)

        def observe():
            try:
                return d.candidate_observe(Store(self.root),['A.cs'],CAPTURED)['ok']
            except KnowledgeError as error:
                self.assertEqual(error.code,'store-busy-retry')
                return False

        with patch.object(d,'_verify_capture_snapshot',side_effect=simultaneous), ThreadPoolExecutor(2) as pool:
            list(pool.map(lambda _:observe(),range(2)))
        self.assertTrue(observe())
        self.assertEqual(len(d.capture_observation_receipts(self.store)['receipts']),1)

    def test_terminal_history_reuses_exact_blocks_and_reads_legacy_rows(self):
        before = self.repository()
        original = d.scan(self.store)
        for _ in range(3):
            d.scan(self.store,base=before,head='HEAD',incremental=True,restart=True)
        with patch.object(discovery_history,'_materialize',side_effect=AssertionError('summary opened an inventory')):
            summaries = d.status(self.store,summaries=True)['scans']
        self.assertEqual(len(summaries),4)
        self.assertEqual({item['snapshot']['identity'] for item in summaries},{original['snapshot']['identity']})
        with self.store.connection(True) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM discovery_snapshot_blocks').fetchone()[0],1)
            legacy = {**original,'id':'a'*64}
            db.execute('INSERT INTO scans VALUES (?,?)',(legacy['id'],canonical_json(legacy)))
        self.assertEqual(d.status(self.store,legacy['id'])['scans'],[legacy])
        self.assertEqual(d.status(self.store,original['id'])['scans'][0],{k:v for k,v in original.items() if k!='ok'})
        self.assertEqual(d.completed_artifact(self.store,original['id'])['source_identity'],original['snapshot']['identity'])
        with self.store.connection(True) as db:
            db.execute("UPDATE discovery_snapshot_blocks SET payload='invalid'")
        with self.assertRaisesRegex(KnowledgeError,'corrupt-discovery-history'):
            d.completed_artifact(self.store,original['id'])

    def test_identity_archive_recognizes_compact_and_provisional_history(self):
        self.warm()
        self.write('C.cs','class C {}')
        d.ScanSession(self.store).scan(max_files=1)
        manifest = identity_migration.inventory(self.root,self.store.project.identity)['tables']
        self.assertEqual(manifest['scans']['count'],1)
        self.assertGreater(manifest[discovery_history.TABLE]['count'],0)
        self.assertEqual(manifest['discovery_chunks']['count'],1)
        self.assertEqual(manifest['discovery_file_cache']['count'],2)

    def candidates(self):
        snap = d.inventory(self.root)
        source = dict(identity=snap['identity'],revision=snap['revision'],kind=snap['snapshot_kind'])
        results = []
        for name in ('batch.first','batch.second'):
            data = addition(name,'Synthetic '+name)['records']
            operations = [life.op('add',kind,item['id'],0,item) for kind in ('evidence','claims') for item in data[kind]]
            results.append(life.batch(operations,'Fixture candidate',source))
        return results

    def test_batch_admission_dedup_validation_drift_and_busy_retry(self):
        first, second = self.candidates()
        initial = self.store.submit(first)
        with self.assertRaises(KnowledgeError):
            self.store.submit_git_batch([second,{'invalid':True}])
        self.assertEqual(len(self.store.status()['queue']),1)
        reader = sqlite3.connect(self.store.path)
        self.addCleanup(reader.close)
        reader.execute('BEGIN')
        reader.execute('SELECT count(*) FROM queue').fetchone()
        with self.assertRaisesRegex(KnowledgeError,'store-busy-retry'):
            self.store.submit_git_batch([first,second])
        reader.rollback()
        duplicate, new, replay = self.store.submit_git_batch([first,second,second])
        self.assertEqual(duplicate['candidate'],initial['candidate'])
        self.assertEqual(new['candidate'],digest(second))
        self.assertEqual([duplicate['result'],new['result'],replay['result']],['duplicate','submitted','duplicate'])
        self.assertEqual(self.store.submit(second)['candidate'],new['candidate'])
        self.assertEqual(len(self.store.prepare()['included']),2)
        self.write('Drift.cs','class Drift {}')
        third = {**second,'reason':'Previously unsubmitted variant'}
        with self.assertRaisesRegex(KnowledgeError,'source-changed-before-candidate-batch'):
            self.store.submit_git_batch([third])
        self.assertEqual(len(self.store.status()['queue']),2)

    def test_process_death_before_batch_commit_leaves_no_partial_candidates(self):
        payloads = self.candidates()
        manifest = self.root.parent/'batch.json'
        manifest.write_text(canonical_json(payloads),encoding='utf-8')
        script = """
import os,sys
from pathlib import Path
from knowledge import store
from knowledge.util import loads
def crash(phase):
    if phase=='before-commit':
        os._exit(37)
store.checkpoint=crash
store.Store(sys.argv[1]).submit_git_batch(loads(Path(sys.argv[2]).read_text(encoding='utf-8')))
"""
        child = subprocess.run([sys.executable,'-c',script,str(self.root),str(manifest)],timeout=40)
        self.assertEqual(child.returncode,37)
        self.assertEqual(self.store.status()['queue'],[])
        self.assertEqual([row['candidate'] for row in self.store.submit_git_batch(payloads)],
                         [digest(value) for value in payloads])

    def test_outbox_after_batch_commit_replays_every_candidate(self):
        journal = Journal(self.root)
        self.write('A.cs','class A {}')
        d.scan(self.store)
        before = source_snapshot(journal.project)
        self.write('A.cs','class ChangedA {}\nclass ChangedB {}')
        run = self.run_state(journal,before,42)
        script = """
import os,sys
from knowledge.util import loads
from harness.capture import deliver,rt
from harness.runtime import Journal
def crash(phase):
    if phase=='capture-after-submit':
        os._exit(37)
rt.fault=crash
journal=Journal(sys.argv[1])
with journal.db() as db:
    run=loads(db.execute('SELECT payload FROM runs WHERE id=?',(sys.argv[2],)).fetchone()[0])
deliver(journal,run,{'capture':'required','limits':{}})
"""
        child = subprocess.run([sys.executable,'-c',script,str(self.root),run['id']],timeout=40)
        self.assertEqual(child.returncode,37)
        pending = journal.outbox(run['id'])
        self.assertEqual(len(pending),2)
        self.assertTrue(all(item['state']=='pending' for item in pending.values()))
        with journal.db() as db:
            run = loads(db.execute('SELECT payload FROM runs WHERE id=?',(run['id'],)).fetchone()[0])
        deliver(journal,run,{'capture':'required','limits':{}})
        delivered = journal.outbox(run['id'])
        self.assertEqual(run['capture']['state'],'delivered')
        self.assertEqual(set(delivered),set(pending))
        self.assertTrue(all(item['receipt']['result']=='duplicate' for item in delivered.values()))
        self.assertEqual(len(self.store.status()['queue']),3)
        self.assertFalse(self.store.export()['records']['claims'])
