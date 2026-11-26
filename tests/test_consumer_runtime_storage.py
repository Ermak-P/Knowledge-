"""Consumer, offline migration and approved storage maintenance regressions."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from threading import Event
import unittest
from unittest.mock import patch

from core_wire import Wire
from fixtures import addition
from test_core_reliability import upgraded
from test_machine_commands import fixture, git, write
from knowledge import discovery, plan_receipts, plan_storage, runtime_migration
from knowledge.access import consumer_scope
from knowledge.execution_lock import ExecutionLock, ProjectExecutionLock
from knowledge.machine_mcp import READ_TOOLS, TOOL_NAMES
from knowledge.project_commands import execute
from knowledge.store import Store
from knowledge.util import KnowledgeError

ROOT = Path(__file__).resolve().parents[1]


class OpenCodeCompatibility(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js required for the Promise Plugin fixture')
    def test_capability_registration_rollback_and_parallel_example(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home/'plugins').mkdir()
            assets = ROOT/'packages/knowledge/src/knowledge/host'
            plugin = home/'plugins/knowledge-machine.mjs'
            shutil.copyfile(assets/'machine_opencode.mjs', plugin)
            shutil.copytree(assets/'commands', home/'knowledge-machine-templates')
            write(home/'.knowledge-machine.json', {'version': 1, 'python': sys.executable, 'launcher': str(home/'launch.py')})
            subprocess.run(['node', str(ROOT/'tests/machine_compatibility.mjs'), str(plugin),
                            str(ROOT/'examples/knowledge-parallel-reads.mjs')], check=True, capture_output=True, text=True)


class ConsumerMode(unittest.TestCase):
    def test_catalog_mutations_filesystem_permissions_and_concurrent_readers(self):
        with tempfile.TemporaryDirectory() as tmp:
            install, root = fixture(tmp)
            store = upgraded(root)
            store.submit(addition('consumer.claim', 'An existing reviewed assertion'))
            prepared = store.prepare()['fingerprint']
            store.apply(prepared, prepared)
            store.acknowledge(prepared)
            import json
            current = json.loads((install/'current.json').read_text())
            current['mode'] = 'readonly'
            marker = json.loads((install/'knowledge-machine-install.json').read_text())
            write(install/'current.json', current)
            write(install/'knowledge-machine-install.json', {**marker, 'current': current})
            (install/'config/provider.json').unlink()
            # A shared consumer has read and directory traversal permissions.
            paths = [store.base, *store.base.rglob('*')]
            original = {p: p.stat().st_mode & 0o777 for p in paths}
            for p in paths:
                p.chmod(0o555 if p.is_dir() else 0o444)
            snapshot = lambda: {p.relative_to(store.base): (p.stat().st_mtime_ns, p.read_bytes())
                                for p in store.base.rglob('*') if p.is_file()}
            before = snapshot()
            try:
                def query(index):
                    wire = Wire([sys.executable, '-I', '-m', 'knowledge.machine_mcp',
                                 '--installation', install, '--workspace', root])
                    try:
                        wire.initialize()
                        self.assertEqual({item['name'] for item in wire.request(102, 'tools/list')['tools']}, READ_TOOLS)
                        self.assertEqual(wire.tool('knowledge_capabilities')['mode'], 'readonly')
                        self.assertEqual(wire.tool('knowledge_get_claim', identifier='consumer.claim')['result'], 'found')
                        self.assertTrue(wire.tool('knowledge_context', task='reviewed assertion')['ok'])
                        for mutator in sorted(TOOL_NAMES - READ_TOOLS):
                            self.assertEqual(wire.tool(mutator)['error'], 'knowledge-readonly')
                        self.assertEqual(wire.tool('knowledge_capabilities', mode='maintainer')['error'], 'invalid-tool-arguments')
                    finally:
                        wire.close()
                with ThreadPoolExecutor(max_workers=3) as pool:
                    list(pool.map(query, range(3)))
                self.assertEqual(snapshot(), before)
                with self.assertRaisesRegex(KnowledgeError, 'knowledge-readonly'):
                    execute('knowledge-init', install, root, {'action': 'start'})
                with consumer_scope(), self.assertRaisesRegex(KnowledgeError, 'knowledge-readonly'):
                    store.init()
            finally:
                for path, mode in original.items():
                    path.chmod(mode)


class RuntimeLayout(unittest.TestCase):
    def test_fresh_scan_and_maintenance_create_only_knowledge_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'project'
            root.mkdir()
            git(root, 'init')
            (root / 'appsettings.json').write_text('{ /* valid */ "name": "project", }')
            before = set(root.iterdir())
            store = upgraded(root)
            runtime = store.project.runtime
            write(runtime.base / 'private.json', {'secret': 'runtime data'})
            write(runtime.base / 'discovery.json', {'version': 1, 'include': ['.knowledge/**']})
            full = discovery.scan(store, max_files=100)
            self.assertNotIn('.knowledge/private.json', full['snapshot']['files'])
            self.assertEqual(discovery._evidence_source(root, '.knowledge/private.json', None, ()), 'not-analyzed')
            from knowledge import maintenance
            backup = Path(tmp)/'backup.zip'
            candidate = maintenance.preview(root, 'backup', backup)
            maintenance.apply(root, candidate['preview'], candidate['fingerprint'])
            git(root, 'check-ignore', '--quiet', '.knowledge/private.json')
            self.assertEqual(set(root.iterdir()) - before, {runtime.base})
            self.assertTrue(runtime.writer.is_file())
            self.assertTrue(runtime.control.is_file())
            self.assertTrue(backup.is_file())

    def test_legacy_locks_conflicts_and_interrupted_migration_keep_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = upgraded(root)
            store.submit(addition('runtime.claim', 'Pending assertion preserved'))
            before = store.path.read_bytes()
            legacy = root/'.maintenance'
            write(legacy/'transactions/old/journal.json', {'sample': 'historical bytes'})
            writer = root/'.harness-writer.lock'
            control = root/'.knowledge-control.lock'
            writer.touch()
            control.touch()
            with self.assertRaisesRegex(KnowledgeError, 'legacy-runtime-layout'):
                store.status()
            with self.assertRaisesRegex(KnowledgeError, 'runtime-migration-requires-offline'):
                runtime_migration.migrate(root)
            legacy_lease = ExecutionLock(writer).acquire()
            try:
                with self.assertRaisesRegex(KnowledgeError, 'runtime-migration-active-lock'):
                    runtime_migration.migrate(root, offline=True)
            finally:
                legacy_lease.close()
            runtime = store.project.runtime
            runtime.maintenance.mkdir()
            with self.assertRaisesRegex(KnowledgeError, 'runtime-migration-destination-conflict'):
                runtime_migration.migrate(root, offline=True)
            runtime.maintenance.rmdir()
            with patch.object(runtime_migration, 'fault', side_effect=RuntimeError('interrupted')):
                with self.assertRaisesRegex(RuntimeError, 'interrupted'):
                    runtime_migration.migrate(root, offline=True)
            self.assertTrue(writer.exists())
            result = runtime_migration.migrate(root, offline=True)
            self.assertEqual(result['state'], 'migrated')
            self.assertEqual(runtime_migration.migrate(root, offline=True)['state'], 'already-migrated')
            self.assertTrue((runtime.maintenance/'transactions/old/journal.json').exists())
            self.assertEqual(store.path.read_bytes(), before)
            lease = ProjectExecutionLock(root).acquire()
            try:
                result = subprocess.run([sys.executable, '-I', '-c',
                    'from knowledge.execution_lock import ProjectExecutionLock; import sys; ProjectExecutionLock(sys.argv[1]).acquire()',
                    str(root)], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('project-writer-busy', result.stderr)
            finally:
                lease.close()
            self.assertFalse(writer.exists())
            self.assertFalse(control.exists())


class PlanStorage(unittest.TestCase):
    def test_protected_approval_and_consumer_maintenance_contention(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = upgraded(Path(tmp))
            store.submit(addition('first.claim', 'An approval-protected candidate'))
            approved = store.prepare()['fingerprint']
            plan_storage.pin_approval(store, approved)
            store.submit(addition('second.claim', 'Another pending candidate'))
            stale = store.prepare()['fingerprint']
            store.submit(addition('third.claim', 'Newest pending candidate'))
            store.prepare()
            proposed = plan_storage.preview(tmp, keep_recent=0, older_than_days=0)
            self.assertEqual([row['fingerprint'] for row in proposed['preview']['obsolete']], [stale])
            waiting, release = Event(), Event()

            def hold(phase):
                if phase == 'before-cleanup-commit':
                    waiting.set()
                    self.assertTrue(release.wait(10))

            with patch.object(plan_storage, 'fault', side_effect=hold), ThreadPoolExecutor(max_workers=1) as pool:
                cleaning = pool.submit(plan_storage.clean, tmp, proposed['preview'], proposed['fingerprint'])
                try:
                    self.assertTrue(waiting.wait(10))
                    with consumer_scope(), self.assertRaisesRegex(KnowledgeError, 'maintenance-busy'):
                        store.lookup('claims', 'first.claim')
                finally:
                    release.set()
                self.assertTrue(cleaning.result(timeout=10)['ok'])
            with consumer_scope():
                self.assertTrue(store.lookup('claims', 'first.claim')['ok'])
            self.assertIn(approved, {row['fingerprint'] for row in store.status()['plans']})

    def test_retention_compacts_legacy_receipt_keeps_recoverable_plan_and_is_restartable(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = upgraded(Path(tmp))
            # Prepare an obsolete proposal, advance the canonical base, and
            # retain a committed plan with an outstanding acknowledgment.
            first = store.submit(addition('old.claim', 'Old pending assertion'))
            stale = store.prepare()['fingerprint']
            store.submit(addition('another.claim', 'A second pending assertion'))
            applied = store.prepare()['fingerprint']
            store.apply(applied, applied)
            store.acknowledge(applied)
            store.submit(addition('third.claim', 'A later canonical assertion'))
            outstanding = store.prepare()['fingerprint']
            store.apply(outstanding, outstanding)
            active = store.prepare()['fingerprint']
            with sqlite3.connect(store.path) as db:
                payload, = db.execute('SELECT payload FROM plans WHERE id=?', (applied,)).fetchone()
                db.execute('UPDATE receipts SET payload=? WHERE plan=?', (payload, applied))
            before = store.export()
            proposed = plan_storage.preview(tmp, keep_recent=0, older_than_days=0, compact_receipts=True, vacuum=True)
            self.assertEqual([row['fingerprint'] for row in proposed['preview']['obsolete']], [stale])
            self.assertEqual([row['fingerprint'] for row in proposed['preview']['compact_receipts']], [applied])
            self.assertGreater(proposed['storage']['allocated_bytes'], 0)
            with self.assertRaisesRegex(KnowledgeError, 'exact-plan-maintenance-approval-required'):
                plan_storage.clean(tmp, proposed['preview'], 'wrong')
            for phase in ('before-cleanup-commit', 'after-cleanup-commit'):
                with patch.object(plan_storage, 'fault', side_effect=lambda current: self.crash(current, phase)):
                    with self.assertRaisesRegex(RuntimeError, phase):
                        plan_storage.clean(tmp, proposed['preview'], proposed['fingerprint'])
            result = plan_storage.clean(tmp, proposed['preview'], proposed['fingerprint'])
            self.assertEqual((result['removed'], result['compacted_receipts']), (1, 1))
            self.assertTrue(result['validated'])
            self.assertEqual(store.export(), before)
            plans = {row['fingerprint']: row['state'] for row in store.status()['plans']}
            self.assertNotIn(stale, plans)
            self.assertEqual(plans[outstanding], 'COMMITTED')
            self.assertEqual(plans[active], 'PREPARED')
            with sqlite3.connect(store.path) as db:
                self.assertEqual(db.execute('SELECT payload FROM receipts WHERE plan=?', (applied,)).fetchone(),
                                 (plan_receipts.reference(applied),))
            self.assertEqual(store.recover()['recovered'][0]['fingerprint'], outstanding)
            self.assertIn(first['candidate'], {row['id'] for row in store.status()['queue']})

    @staticmethod
    def crash(current, phase):
        if current == phase:
            raise RuntimeError(phase)
