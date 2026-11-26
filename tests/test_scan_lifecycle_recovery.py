"""Machine scan recovery with real durable chunks and installed MCP transport."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from core_wire import Wire
from fixtures import addition
from test_core_reliability import upgraded
from test_machine_commands import fixture, git, wait, write
from knowledge import discovery, discovery_checkpoint, scan_jobs
from knowledge.auto_init import ScanError, read_checkpoint, read_json, run
from knowledge.execution_lock import ProjectExecutionLock
from knowledge.project_commands import configure_project, diagnostics, execute, machine_binding, scan_binding
from knowledge.util import KnowledgeError, canonical_json, digest

FULL = 'knowledge-init'
INCREMENTAL = 'knowledge-candidates-update'


def publish_release(install):
    current = read_json(install / 'current.json')
    current['release_sha256'] = 'upgraded-fixture-release'
    current['runtime'] = 'runtimes/upgrade'
    (install / current['runtime']).mkdir()
    marker = read_json(install / 'knowledge-machine-install.json')
    write(install / 'current.json', current)
    write(install / 'knowledge-machine-install.json', {**marker, 'current': current})


class RecoveryFixture:
    def __init__(self, temporary, files=7, incremental=False, legacy=False, seed_canonical=False):
        self.install, self.root = fixture(temporary, files)
        self.store = upgraded(self.root)
        if seed_canonical:
            self.store.submit(addition('machine.existing', 'Existing reviewed source assertion'))
            plan = self.store.prepare()
            self.store.apply(plan['fingerprint'], plan['fingerprint'])
            self.store.acknowledge(plan['fingerprint'])
        self.project = self.store.project
        configure_project(self.install, self.project)
        self.provider = self.install / 'config/provider.json'
        self.scope = {'kind': 'incremental' if incremental else 'full'}
        self.command = INCREMENTAL if incremental else FULL
        if incremental:
            revision = git(self.root, 'rev-parse', 'HEAD').stdout.decode().strip()
            self.scope.update(base=revision, head=revision)
            # Seed compatible unchanged analysis before the incremental change.
            discovery.scan(self.store, max_files=files + 5)
            for number in range(files):
                (self.root / f'Class{number}.cs').write_text(f'public class Changed{number} {{}}\n', encoding='utf-8')
        self.state_dir = self.install / 'state/projects' / self.project.identity
        name = 'incremental-' + digest(self.scope) if incremental else 'full'
        self.folder = self.state_dir / name
        self.folder.mkdir(parents=True)
        if incremental:
            write(self.state_dir / 'last-incremental.json', {'folder': name})
        with redirect_stdout(io.StringIO()):
            try:
                run(self.root, self.folder, max_files=2, max_calls=1, base=self.scope.get('base'),
                    head=self.scope.get('head'), incremental=incremental, cancel_job=None if legacy else 'previous-job')
            except ScanError as error:
                if 'max-calls' not in str(error):
                    raise
            else:
                raise AssertionError('Fixture must be interrupted after its first commit')
        self.checkpoint = self.folder / 'checkpoint.json'
        self.scan_id = read_checkpoint(self.checkpoint)['scan_id']
        self.previous = discovery.status(self.store, self.scan_id)['scans'][0]
        binding = (machine_binding if legacy else scan_binding)(self.install, self.project)[0]
        self.job = {'version': 1, 'job': 'previous-job', 'pid': 1073741823, 'root': str(self.root),
                    'process_stamp': 'old-process', 'binding': binding, 'scope': self.scope,
                    'state': 'CANCELLED', 'chunk_started': True}
        self.save_job()

    def save_job(self, **changes):
        self.job.update(changes)
        write(self.folder / 'job.json', self.job)

    def active(self, stamp=None):
        self.save_job(state='RUNNING', pid=os.getpid(), process_stamp=stamp or scan_jobs.process_stamp(os.getpid()))

    def change_provider(self, **changes):
        value = read_json(self.provider)
        value['provider'].update(changes)
        write(self.provider, value)

    def call(self, **value):
        return execute(self.command, self.install, self.root, value)

    def invalid_initial(self, **changes):
        with sqlite3.connect(self.store.path) as db:
            initial, = db.execute('SELECT initial FROM discovery_runs WHERE id=?', (self.scan_id,)).fetchone()
            chunk, = db.execute('SELECT payload FROM discovery_chunks WHERE scan=?', (self.scan_id,)).fetchone()
            state = {**discovery_checkpoint._unpack(initial), **changes}
            packed, checksum, _, payload, tail = discovery_checkpoint.encode(
                self.scan_id, None, state, discovery_checkpoint._unpack(chunk))
            db.execute('UPDATE discovery_runs SET initial=?,initial_hash=?,tail=? WHERE id=?',
                       (packed, checksum, tail, self.scan_id))
            db.execute('UPDATE discovery_chunks SET payload=?,checksum=? WHERE scan=?', (payload, tail, self.scan_id))


class ScanLifecycleRecovery(unittest.TestCase):
    def test_active_status_reports_model_endpoint_and_runtime_drift_without_inventory_or_database(self):
        for key, value, changed in (
                ('model', 'unpublished-provider-model', 'provider.model'),
                ('endpoint', 'https://my-private.example/chat/completions', 'provider.endpoint'),
                ('runtime', None, 'runtime_release')):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as tmp:
                f = RecoveryFixture(tmp)
                f.active()
                if key == 'runtime':
                    publish_release(f.install)
                else:
                    f.change_provider(**{key: value})
                before = f.checkpoint.read_bytes()
                with patch.object(discovery, 'inventory', side_effect=AssertionError('status ran inventory')), \
                        patch.object(type(f.store), 'connection', side_effect=AssertionError('status opened store')):
                    result = f.call(action='status')
                self.assertEqual(result['worker_state'], 'RUNNING')
                self.assertEqual(result['scan_id'], f.scan_id)
                compatibility = result['compatibility']
                self.assertEqual(compatibility['changed_fields'], [changed])
                self.assertTrue(compatibility['checkpoint_available'])
                self.assertFalse(compatibility['resume_allowed'])
                self.assertEqual(compatibility['source_compatibility'], 'unverified')
                self.assertEqual(f.checkpoint.read_bytes(), before)
                if value:
                    self.assertNotIn(value, canonical_json(result))

    def test_actual_mcp_reads_legacy_job_and_history_and_rejects_active_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = RecoveryFixture(tmp, legacy=True)
            f.active()
            f.change_provider(endpoint='https://private.example/chat/completions', key_env='PRIVATE_ENV_NAME')
            publish_release(f.install)
            peer = Wire([sys.executable, '-I', '-B', '-m', 'knowledge.machine_mcp',
                         '--installation', f.install], roots=lambda: [f.root])
            self.addCleanup(peer.close)
            peer.initialize()
            observed = peer.tool('knowledge_scan')
            self.assertEqual(observed['compatibility']['changed_fields'], ['runtime_release', 'provider_reference.hash'])
            self.assertEqual(observed['scan_id'], f.scan_id)
            error = peer.tool('knowledge_scan', action='resume')
            self.assertEqual(error['error'], 'scan-worker-active')
            self.assertEqual(error['details']['job_id'], 'previous-job')
            self.assertEqual(error['details']['worker_state'], 'RUNNING')
            self.assertNotIn('PRIVATE_ENV_NAME', canonical_json(error))
            self.assertNotIn('private.example', canonical_json(error))
            terminal = peer.tool('knowledge_scan', action='status', observed_scan_id=f.scan_id)
            self.assertEqual(terminal['error'], 'observed-scan-requires-resume')
            checkpoint = peer.tool('knowledge_scan_diagnostics', section='checkpoint')
            self.assertEqual(checkpoint['rows'][0]['scan_id'], f.scan_id)
            self.assertTrue(checkpoint['canonical_unchanged'])
            history = peer.tool('knowledge_scan_diagnostics', section='scans', scan_id=f.scan_id)
            self.assertEqual(history['rows'][0]['scan_id'], f.scan_id)
            coverage = peer.tool('knowledge_scan_diagnostics', section='coverage', scan_id=f.scan_id)
            self.assertTrue(coverage['ok'], coverage)
            self.assertTrue(coverage['rows'])
            result = peer.tool('knowledge_scan', action='cancel')
            self.assertEqual(result['cancellation'], 'requested at durable chunk boundary')
            self.assertEqual(peer.tool('knowledge_scan')['phase'], 'CANCELLING_AT_CHUNK_BOUNDARY')

    def test_cancellation_is_idempotent_with_missing_invalid_or_changed_provider(self):
        for variant in ('missing', 'invalid', 'model', 'endpoint', 'runtime'):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as tmp:
                f = RecoveryFixture(tmp, incremental=variant in ('invalid', 'endpoint'))
                f.active()
                if variant == 'missing':
                    f.provider.unlink()
                elif variant == 'invalid':
                    write(f.provider, {'api_key': 'SECRET-CONFIG-VALUE'})
                elif variant == 'runtime':
                    publish_release(f.install)
                else:
                    f.change_provider(**{variant: 'other' if variant == 'model' else 'https://other.example/chat/completions'})
                checkpoint = f.checkpoint.read_bytes()
                records = f.store.export()
                first = f.call(action='cancel')
                marker = f.folder / 'cancel.json'
                stamp = marker.stat().st_mtime_ns
                self.assertEqual(f.call(action='cancel'), first)
                self.assertEqual(marker.stat().st_mtime_ns, stamp)
                self.assertEqual(read_json(marker)['job'], f.job['job'])
                self.assertNotIn('SECRET-CONFIG-VALUE', canonical_json(f.call(action='status')))
                f.save_job(state='CANCELLED', pid=1073741823, process_stamp='dead')
                self.assertEqual(f.call(action='cancel')['cancellation'], 'already terminal')
                self.assertEqual(f.checkpoint.read_bytes(), checkpoint)
                self.assertEqual(f.store.export(), records)

    def test_real_worker_cancels_at_a_boundary_after_runtime_and_provider_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            install, root = fixture(tmp, 125)
            initial = execute(FULL, install, root, {'max_files': 1})
            folder = Path(initial['diagnostics'])
            deadline = time.monotonic() + 20
            while not (folder / 'checkpoint.json').exists() and time.monotonic() < deadline:
                time.sleep(.02)
            checkpoint = read_checkpoint(folder / 'checkpoint.json')
            publish_release(install)
            (install / 'config/provider.json').unlink()
            cancellation = execute(FULL, install, root, {'action': 'cancel'})
            self.assertEqual(cancellation['job'], initial['job'])
            cancelled = wait(install, root)
            self.assertEqual(cancelled['worker_state'], 'CANCELLED', cancelled)
            self.assertEqual(cancelled['scan_id'], checkpoint['scan_id'])
            resumed = execute(FULL, install, root, {'resume': True, 'max_files': 1000})
            self.assertNotEqual(resumed['job'], initial['job'])
            self.assertEqual(wait(install, root)['worker_state'], 'COMPLETED')

    def test_model_endpoint_runtime_and_incremental_resume_preserve_durable_work(self):
        cases = ('runtime', 'model', 'endpoint', 'incremental')
        for variant in cases:
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as tmp:
                f = RecoveryFixture(tmp, incremental=variant == 'incremental', legacy=variant == 'runtime', seed_canonical=True)
                f.store.submit(addition('machine.pending', 'Existing unapproved source assertion'))
                canonical = f.store.export()['records']
                queue = {row['id']: row for row in f.store.status()['queue']}
                if variant in ('runtime', 'incremental'):
                    publish_release(f.install)
                elif variant == 'model':
                    f.change_provider(model='different-model')
                else:
                    f.change_provider(endpoint='https://alternate.example/chat/completions')
                self.assertTrue(f.call(action='status')['compatibility']['checkpoint_available'])
                f.call(resume=True)
                final = wait(f.install, f.root, f.command)
                self.assertEqual(final['worker_state'], 'COMPLETED', final)
                self.assertEqual(final['scan_id'], f.scan_id)
                self.assertEqual(final['compatibility']['source_compatibility'], 'verified-at-resume')
                last = read_json(f.folder / 'last-result.json')
                done = set(f.previous['work']['paths_this_call'])
                pending = {path for path, entry in f.previous['coverage'].items() if entry['status'] == 'not-analyzed'}
                self.assertTrue(done)
                self.assertEqual(set(last['work']['paths_this_call']), pending)
                self.assertFalse(done.intersection(last['work']['paths_this_call']))
                actual = {row['id']: row for row in f.store.status()['queue']}
                self.assertEqual({identifier: actual[identifier] for identifier in queue}, queue)
                self.assertEqual(len(last['candidates']), len(set(last['candidates'])))
                self.assertEqual(f.store.export()['records'], canonical)

    def test_incompatible_resume_reports_checkpoint_source_and_schema_diagnostics(self):
        for variant, reason, changed in (
                ('extractor', 'stale-extractor-restart-required', 'extractor'),
                ('identity', 'incompatible-scan-identity-policy', 'identity_policy'),
                ('contract', 'incompatible-scan-resume-contract', 'runtime_capabilities'),
                ('format', 'unsupported-checkpoint-format', 'checkpoint_format'),
                ('policy', 'stale-discovery-policy', 'discovery_configuration'),
                ('source', 'stale-scan-restart-required', 'source_snapshot'),
                ('branch', 'stale-scan-git-branch', 'git_branch'),
                ('revision', 'stale-scan-git-revision', 'git_revision'),
                ('schema', 'unsupported-store-format', 'database_schema')):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as tmp:
                f = RecoveryFixture(tmp)
                publish_release(f.install)
                if variant in ('extractor', 'identity', 'contract'):
                    key = {'extractor': 'extractor', 'identity': 'identity_policy', 'contract': 'resume_contract'}[variant]
                    f.invalid_initial(**{key: 'future-format'})
                if variant == 'format':
                    write(f.checkpoint, {**read_json(f.checkpoint), 'version': 99})
                if variant == 'policy':
                    write(f.root / '.knowledge/discovery.json', {'version': 1, 'max_file_bytes': 2048})
                if variant == 'source':
                    (f.root / 'Class2.cs').write_text('public class Updated {}', encoding='utf-8')
                if variant == 'branch':
                    git(f.root, 'checkout', '-b', 'second')
                if variant == 'revision':
                    git(f.root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                        'commit', '--allow-empty', '-m', 'new revision')
                if variant == 'schema':
                    with sqlite3.connect(f.store.path) as db:
                        db.execute("UPDATE metadata SET value='future' WHERE key='format'")
                original = f.checkpoint.read_bytes()
                with self.assertRaisesRegex(KnowledgeError, 'resume-scan-configuration-drift') as failure:
                    f.call(resume=True)
                detail = failure.exception.details
                self.assertEqual(detail['reason'], reason)
                self.assertEqual(detail['worker_state'], 'CANCELLED')
                self.assertFalse(detail['resume_allowed'])
                self.assertIn(changed, detail['changed_fields'])
                self.assertIn('runtime_release', detail['changed_fields'])
                self.assertEqual(detail['execution_compatibility'], 'incompatible')
                self.assertTrue(detail['next_action'])
                self.assertEqual(f.checkpoint.read_bytes(), original)
                status = wait(f.install, f.root)
                self.assertIn(status['worker_state'], ('BLOCKED', 'CANCELLED'))
                if status['worker_state'] == 'BLOCKED':
                    self.assertEqual(status['compatibility']['reason'], reason)
                    self.assertIn(changed, status['compatibility']['changed_fields'])

    def test_unknown_outcome_requires_verified_observed_id_and_rejects_database_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = RecoveryFixture(tmp)
            f.save_job(state='RUNNING')
            # The first chunk is durable even without a usable helper locator.
            write(f.checkpoint, {**read_json(f.checkpoint), 'checksum': 'broken'})
            original = f.checkpoint.read_bytes()
            observed = f.call(action='status')
            self.assertEqual(observed['worker_state'], 'OUTCOME_UNKNOWN')
            self.assertFalse(observed['compatibility']['checkpoint_available'])
            self.assertEqual(observed['compatibility']['reason'], 'invalid-scan-checkpoint')
            with self.assertRaisesRegex(KnowledgeError, 'resume-scan-configuration-drift'):
                f.call(resume=True)
            with self.assertRaisesRegex(KnowledgeError, 'scan-recovery-required'):
                f.call()
            self.assertEqual(f.checkpoint.read_bytes(), original)
            with sqlite3.connect(f.store.path) as db:
                saved, = db.execute('SELECT checksum FROM discovery_chunks').fetchone()
                db.execute("UPDATE discovery_chunks SET checksum='broken'")
            with self.assertRaisesRegex(KnowledgeError, 'resume-scan-configuration-drift') as failure:
                f.call(resume=True, observed_scan_id=f.scan_id)
            self.assertEqual(failure.exception.details['reason'], 'corrupt-scan-checkpoint')
            self.assertEqual(f.checkpoint.read_bytes(), original)
            with sqlite3.connect(f.store.path) as db:
                db.execute('UPDATE discovery_chunks SET checksum=?', (saved,))
            known = diagnostics(f.install, f.root, section='scans', scan_id=f.scan_id)
            self.assertEqual(known['rows'][0]['scan_id'], f.scan_id)
            f.call(resume=True, observed_scan_id=f.scan_id)
            final = wait(f.install, f.root)
            self.assertEqual(final['worker_state'], 'COMPLETED', final)
            self.assertEqual(final['scan_id'], f.scan_id)

    def test_unknown_fresh_attempt_does_not_use_previous_job_locator(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = RecoveryFixture(tmp)
            f.save_job(state='RUNNING', fresh=True, job='new-worker')
            result = f.call(action='status')
            self.assertEqual(result['worker_state'], 'OUTCOME_UNKNOWN')
            self.assertIsNone(result['scan_id'])
            self.assertEqual(result['compatibility']['reason'], 'scan-checkpoint-precedes-fresh-worker')
            with self.assertRaisesRegex(KnowledgeError, 'resume-scan-configuration-drift'):
                f.call(resume=True)

    def test_active_owner_blocks_resume_and_other_scope_fresh_during_concurrent_cancel(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = RecoveryFixture(tmp)
            f.active()
            publish_release(f.install)
            probe = ProjectExecutionLock(f.root).acquire()
            try:
                def resume():
                    with self.assertRaisesRegex(KnowledgeError, 'scan-worker-active') as failure:
                        f.call(resume=True)
                    return failure.exception.details
                with ThreadPoolExecutor(max_workers=2) as executor:
                    rejection = executor.submit(resume)
                    cancellation = executor.submit(f.call, action='cancel')
                    self.assertEqual(rejection.result()['worker_state'], 'RUNNING')
                    self.assertEqual(cancellation.result()['job'], 'previous-job')
                with self.assertRaisesRegex(KnowledgeError, 'project-writer-busy'):
                    execute(INCREMENTAL, f.install, f.root, {'fresh': True})
                self.assertFalse((f.state_dir / 'last-incremental.json').exists())
            finally:
                probe.close()

    def test_wrong_owner_and_reused_pid_cannot_target_process_or_replace_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = RecoveryFixture(tmp)
            f.active(stamp='reused-pid-from-old-installation')
            self.assertEqual(f.call(action='status')['worker_state'], 'OUTCOME_UNKNOWN')
            self.assertIn('unverified', f.call(action='cancel')['cancellation'])
            marker = f.folder / 'cancel.json'
            self.assertFalse(marker.exists())
            if os.name != 'nt':
                unsafe = f.folder / 'progress.json'
                unsafe.unlink()
                unsafe.symlink_to(f.provider)
                with self.assertRaisesRegex(KnowledgeError, 'linked-path'):
                    f.call(action='status')
                unsafe.unlink()
            f.save_job(root=str(f.root / 'different-root'))
            for args in ({'action': 'status'}, {'action': 'cancel'}, {'resume': True}):
                with self.subTest(args=args), self.assertRaisesRegex(KnowledgeError, 'scan-job-root-binding-mismatch'):
                    f.call(**args)
            self.assertFalse(marker.exists())

    def test_unstamped_legacy_process_can_be_cancelled_cooperatively_but_not_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = RecoveryFixture(tmp, legacy=True)
            f.save_job(state='RUNNING', pid=os.getpid(), process_stamp=None)
            status = f.call(action='status')
            self.assertEqual(status['worker_state'], 'OUTCOME_UNKNOWN')
            self.assertEqual(status['compatibility']['reason'], 'scan-worker-liveness-unverified')
            with self.assertRaisesRegex(KnowledgeError, 'scan-worker-liveness-unverified'):
                f.call(resume=True)
            self.assertEqual(f.call(action='cancel')['cancellation'], 'requested at durable chunk boundary')
            self.assertEqual(read_json(f.folder / 'cancel.json')['job'], f.job['job'])

    def test_legacy_locator_and_old_sqlite_shapes_stay_observable(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = RecoveryFixture(tmp, legacy=True)
            legacy = {k: v for k, v in f.previous.items() if k not in ('git_branch', 'resume_contract')}
            with sqlite3.connect(f.store.path) as db:
                db.execute('DELETE FROM discovery_chunks')
                db.execute('DELETE FROM discovery_runs')
                db.execute('INSERT INTO scans VALUES (?,?)', (f.scan_id, canonical_json(legacy)))
            write(f.checkpoint, {'version': 1, 'root': str(f.root), 'scan_id': f.scan_id})
            publish_release(f.install)
            result = f.call(action='status')
            self.assertEqual(result['scan_id'], f.scan_id)
            self.assertEqual(result['compatibility']['checkpoint_integrity'], 'legacy-locator')
            historical = diagnostics(f.install, f.root, section='coverage', scan_id=f.scan_id)
            self.assertTrue(historical['rows'])
            with self.assertRaisesRegex(KnowledgeError, 'resume-scan-configuration-drift') as failure:
                f.call(resume=True)
            self.assertEqual(failure.exception.details['reason'], 'scan-git-branch-unverified')
            self.assertEqual(failure.exception.details['execution_compatibility'], 'unverified')
            self.assertEqual(discovery.status(f.store, f.scan_id)['scans'][0], legacy)


if __name__ == '__main__':
    unittest.main()
