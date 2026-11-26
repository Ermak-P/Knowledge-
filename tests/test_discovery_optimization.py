"""Source verification, bounded replay, and exact incremental observations."""
import contextlib
import io
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from knowledge import auto_init, discovery, lifecycle
from knowledge.store import Store
from knowledge.util import KnowledgeError
from test_p1 import git


class DiscoveryOptimization(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / 'source'
        self.root.mkdir()
        self.store = Store(self.root)
        self.store.init()
        lifecycle.upgrade(self.store, lifecycle.upgrade_preview(self.store)['fingerprint'])

    def write(self, path, text):
        item = self.root / path
        item.parent.mkdir(parents=True, exist_ok=True)
        item.write_text(text, encoding='utf-8')
        return item

    def commit_fixture(self):
        self.write('.gitignore', '.knowledge/\n.knowledge-control.lock\n')
        git(self.root, 'init')
        git(self.root, 'config', 'user.name', 'Synthetic')
        git(self.root, 'config', 'user.email', 'fixture@example.invalid')
        git(self.root, 'add', '.')
        git(self.root, 'commit', '-m', 'fixture')
        return git(self.root, 'rev-parse', 'HEAD')

    def test_worker_keeps_a_constant_inventory_count_and_no_chunk_children(self):
        for i in range(8):
            self.write(f'Type{i}.cs', f'class Type{i} {{ }}')
        output = self.root.parent / 'results'
        with (patch.object(discovery, 'inventory', wraps=discovery.inventory) as inventories,
              patch.object(auto_init.subprocess, 'run', side_effect=AssertionError('per-chunk Python')),
              contextlib.redirect_stdout(io.StringIO())):
            self.assertEqual(auto_init.run(self.root, output, max_files=1, persistent=True), 0)
        result = auto_init.read_json(output / 'last-result.json')
        self.assertTrue(result['source_verified'])
        self.assertEqual(inventories.call_count, 2)
        self.assertEqual(len(result['observations']), 8)

    def test_same_size_changed_file_after_proposals_invalidates_completion(self):
        path = self.write('A.cs', 'class Old {}')
        self.write('B.cs', 'class Other {}')
        session = discovery.ScanSession(self.store)
        first = session.scan(max_files=1)
        self.assertFalse(first['source_verified'])
        original = discovery.proposal

        def drift(*args, **kwargs):
            stat = path.stat()
            path.write_text('class New {}', encoding='utf-8')
            os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
            return original(*args, **kwargs)

        with patch.object(discovery, 'proposal', drift):
            with self.assertRaisesRegex(KnowledgeError, 'source-changed-during-scan'):
                session.scan(first['id'], max_files=1)
        self.assertEqual(self.store.status()['queue'], [])
        checkpoint = discovery.status(self.store, first['id'])['scans'][0]
        self.assertEqual(checkpoint['work']['remaining_files'], 1)

    def test_resume_checks_branch_even_when_head_and_files_are_equal(self):
        self.write('A.cs', 'class A {}')
        self.write('B.cs', 'class B {}')
        self.commit_fixture()
        first = discovery.ScanSession(self.store).scan(max_files=1)
        git(self.root, 'checkout', '-b', 'same-content')
        with self.assertRaisesRegex(KnowledgeError, 'stale-scan'):
            discovery.ScanSession(self.store).scan(first['id'], max_files=1)

    def test_warm_cache_matches_full_identity_and_preserves_occurrences(self):
        self.write('Project.csproj', '<Project Sdk="Microsoft.NET.Sdk"/>')
        self.write('A.cs', 'class A {}\nUseSqlite();')
        self.write('B.cs', 'class B {}\nUseSqlite();')
        self.write('C.cs', 'class C {}')
        base = self.commit_fixture()
        discovery.scan(self.store)
        with patch.object(discovery, 'extract', wraps=discovery.extract) as extracts:
            no_op = discovery.scan(self.store, base=base, head='HEAD', incremental=True)
            self.assertEqual(extracts.call_count, 0)
            self.assertTrue(no_op['identity_verification']['complete'])
        self.write('C.cs', 'class B {}\nUseSqlite();')
        trusted = discovery.analysis_scope(self.root)
        with patch.object(discovery, 'extract', wraps=discovery.extract) as extracts:
            preview = discovery.candidate_observe(self.store, ['C.cs'])
        self.assertEqual([c.args[1] for c in extracts.call_args_list], ['C.cs'])
        self.assertEqual(preview['gaps'], list(trusted['ambiguous']))
        decisions = {d['decision']: d for d in preview['decisions']}
        self.assertIn('manual-review', decisions)
        additions = [o for o in decisions['submit']['payload']['operations'] if o['kind'] == 'evidence']
        self.assertEqual({o['payload']['source'] for o in additions}, {'A.cs', 'B.cs', 'C.cs'})
        incremental = discovery.scan(self.store, base=base, head='HEAD', incremental=True)
        self.assertEqual(incremental['identity_verification']['ambiguous_ids'], sorted(trusted['ambiguous']))

    def test_uncovered_cache_is_explicit_and_never_analyzes_unrelated_code(self):
        self.write('A.cs', 'class A {}')
        self.write('B.cs', 'class B {}')
        self.commit_fixture()
        self.write('A.cs', 'class Changed {}')
        with patch.object(discovery, 'extract', wraps=discovery.extract) as extracts:
            with self.assertRaisesRegex(KnowledgeError, 'capture-observation-cache-incomplete') as error:
                discovery.candidate_observe(self.store, ['A.cs'])
        self.assertEqual([c.args[1] for c in extracts.call_args_list], ['A.cs'])
        self.assertEqual(error.exception.details['path_sample'], ['B.cs'])
        self.assertEqual(discovery.capture_observation_receipts(self.store)['receipts'], [])

    def test_checkpoint_checksum_blocks_recovery_before_any_extraction(self):
        self.write('A.cs', 'class A {}')
        self.write('B.cs', 'class B {}')
        first = discovery.ScanSession(self.store).scan(max_files=1)
        with self.store.connection(True) as db:
            db.execute("UPDATE discovery_chunks SET payload=x'00'")
        with patch.object(discovery, 'extract', side_effect=AssertionError('corrupt checkpoint replayed')):
            with self.assertRaisesRegex(KnowledgeError, 'corrupt-scan-checkpoint'):
                discovery.ScanSession(self.store).scan(first['id'], max_files=1)


if __name__ == '__main__':
    unittest.main()
