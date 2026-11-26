"""Durable machine command, incremental source and approval regressions."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from core_wire import Wire
from fixtures import addition
from test_confluence_source import document, proposal
from test_core_reliability import upgraded
from test_machine_commands import fixture, git, write
from knowledge import confluence, discovery, scan_jobs
from knowledge.project_commands import configure_project, diagnostics, execute, machine_binding, push
from knowledge.util import KnowledgeError, canonical_json, digest, fingerprint

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / 'packages/knowledge/src/knowledge/host/machine_opencode.mjs'
COMMAND = 'knowledge-candidates-push'
CONTROLLED_CHILD = """
import os, sys, time
from pathlib import Path
from knowledge import plan_jobs, project_commands, store
folder, ready, release, mode = map(Path, sys.argv[1:])
original = project_commands.push
def controlled(*args, observe_progress, **kwargs):
    observe_progress('verifying-current-source-inventory')
    ready.touch()
    if mode.name == 'crash':
        def fail(phase):
            if phase == 'before-commit':
                os._exit(77)
        store.checkpoint = fail
    else:
        deadline = time.monotonic() + 90
        while not release.exists() and time.monotonic() < deadline:
            time.sleep(.025)
    return original(*args, observe_progress=observe_progress, **kwargs)
project_commands.push = controlled
raise SystemExit(plan_jobs.worker(folder))
"""


def intercept(ready, release, mode):
    original = subprocess.Popen

    def spawn(argv, *args, **kwargs):
        if 'knowledge.plan_jobs' in argv:
            argv = [argv[0], '-I', '-B', '-c', CONTROLLED_CHILD, argv[-1], str(ready), str(release), mode]
        return original(argv, *args, **kwargs)
    return patch.object(scan_jobs.subprocess, 'Popen', spawn)


def until(read, predicate, seconds=40):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = read()
        if predicate(value):
            return value
        time.sleep(.05)
    raise AssertionError(value)


class PushFixture(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.install, self.root = fixture(temp.name, 5)
        self.store = upgraded(self.root)
        self.project = self.store.project
        configure_project(self.install, self.project)
        self.state = self.install / 'state/projects' / self.project.identity
        self.binding = machine_binding(self.install, self.project)[0]
        self.ready, self.release = self.base/'worker-ready', self.base/'release-worker'

    def execute(self, **params):
        return execute(COMMAND, self.install, self.root, params)

    def await_result(self, job):
        return until(lambda: self.execute(action='status', job_id=job),
                     lambda value: value['worker_state'] not in scan_jobs.ACTIVE)

    def prepare(self):
        return self.await_result(self.execute(wait_seconds=0)['job_id'])

    def scan(self, incremental=False):
        return discovery.scan(self.store, max_files=100, incremental=incremental,
                              base='HEAD' if incremental else None, head='HEAD' if incremental else None)

    def dispositions(self, plan):
        return diagnostics(self.install, self.root, section='plan-dispositions', plan=plan['canonical_plan'], limit=100)['rows']

    def add_manual(self):
        self.store.submit(addition('manual.fact', 'An independent manually supplied fixture statement.'))

    def start_controlled(self, mode='pause', **controls):
        with intercept(self.ready, self.release, mode):
            reply = self.execute(wait_seconds=0, **controls)
        until(self.ready.exists, bool)
        return reply['job_id']


class DurablePreparation(PushFixture):
    def test_observer_returns_and_worker_stays_healthy_beyond_thirty_seconds(self):
        self.add_manual()
        job = self.start_controlled()
        try:
            with ThreadPoolExecutor(max_workers=2) as hosts:
                observations = list(hosts.map(lambda _: self.execute(wait_seconds=.05), range(2)))
            self.assertEqual({observe['job_id'] for observe in observations}, {job})
            observe = observations[0]
            self.assertIn(observe['worker_state'], scan_jobs.ACTIVE)
            self.assertEqual(observe['progress']['stage'], 'verifying-current-source-inventory')
            time.sleep(31)
            status = self.execute(action='status', job_id=job)
            self.assertEqual(status['worker_state'], 'RUNNING')
            self.assertGreater(status['progress']['elapsed_seconds'], 30)
        finally:
            self.release.touch()
        finished = self.await_result(job)
        self.assertEqual(finished['state'], 'AWAITING_EXACT_APPROVAL', finished)
        self.assertFalse(self.store.export()['records']['claims'])
        self.assertEqual(self.store.status()['plans'][0]['state'], 'PREPARED')

    def test_cancel_is_cooperative_and_resume_preserves_job_id(self):
        self.add_manual()
        job = self.start_controlled()
        try:
            first = self.execute(action='cancel', job_id=job)
            second = self.execute(action='cancel', job_id=job)
            self.assertEqual(first['cancellation'], second['cancellation'])
        finally:
            self.release.touch()
        cancelled = self.await_result(job)
        self.assertEqual(cancelled['state'], 'CANCELLED', cancelled)
        self.assertFalse(self.store.status()['plans'])
        resumed = self.execute(action='resume', job_id=job, wait_seconds=0)
        self.assertEqual(resumed['job_id'], job)
        self.assertEqual(self.await_result(job)['state'], 'AWAITING_EXACT_APPROVAL')

    def test_durable_worker_accounts_for_25006_pending_candidates(self):
        count = 25006
        with self.store.connection(True) as db:
            for index in range(count):
                item = addition(f'large.{index}', f'Independent scale fixture {index}.')
                db.execute("INSERT INTO queue VALUES (?,?,'pending',NULL)", (digest(item), canonical_json(item)))
        result = self.prepare()
        self.assertEqual(result['state'], 'AWAITING_EXACT_APPROVAL', result)
        self.assertEqual(result['candidate_counts']['pending'], count)
        self.assertEqual(result['candidate_counts']['included'], count)
        self.assertEqual(result['candidate_counts']['coalesced_within_included'], 0)
        self.assertEqual(self.store.scan_counts(), {'records': 0, 'queue': count, 'plans': 1})
        self.assertLess((self.state/'last-plan.json').stat().st_size, 5000)

    def test_crash_before_commit_rolls_back_then_explicit_resume(self):
        self.add_manual()
        before = self.store.status()['queue']
        job = self.start_controlled('crash')
        failure = self.await_result(job)
        self.assertEqual(failure['state'], 'OUTCOME_UNKNOWN')
        self.assertEqual(failure['progress']['stage'], 'persisting-plan')
        self.assertEqual(self.store.status()['queue'], before)
        self.assertFalse(self.store.status()['plans'])
        with self.assertRaisesRegex(KnowledgeError, 'plan-prepare-resume-required'):
            self.execute(wait_seconds=0)
        reply = self.execute(action='resume', job_id=job)
        self.assertEqual(reply['job_id'], job)
        self.assertEqual(self.await_result(job)['state'], 'AWAITING_EXACT_APPROVAL')

    def test_execution_deadline_is_explicit_and_recoverable(self):
        self.add_manual()
        job = self.start_controlled(execution_seconds=1)
        try:
            time.sleep(1.05)
        finally:
            self.release.touch()
        result = self.await_result(job)
        self.assertEqual(result['state'], 'CANCELLED')
        self.assertEqual(result['reason'], 'plan-execution-deadline')
        self.assertFalse(self.store.status()['plans'])
        self.execute(action='resume', job_id=job, execution_seconds=None, wait_seconds=0)
        self.assertEqual(self.await_result(job)['state'], 'AWAITING_EXACT_APPROVAL')

    def host(self, launcher, **controls):
        home = self.base/'host'
        plugins = home/'plugins'
        plugins.mkdir(parents=True)
        plugin = plugins/'knowledge-machine.mjs'
        shutil.copyfile(PLUGIN, plugin)
        shutil.copytree(PLUGIN.parent/'commands', home/'knowledge-machine-templates')
        script = self.base/'launcher.py'
        script.write_text(launcher, encoding='utf-8')
        write(home/'.knowledge-machine.json', {'version': 1, 'python': sys.executable, 'launcher': str(script)})
        return subprocess.Popen([shutil.which('node'), REPO/'tests/machine_push_host.mjs', plugin, self.root],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env={**os.environ, **controls}, text=True)

    @unittest.skipUnless(shutil.which('node'), 'Node runtime for generated plugin')
    def test_terminating_host_peer_leaves_detached_plan_worker(self):
        self.add_manual()
        launcher = f"""
import json, subprocess, sys, traceback
from pathlib import Path
from knowledge import machine_mcp
from knowledge.project_commands import execute
from knowledge.util import emit_json
child = {CONTROLLED_CHILD!r}
real = subprocess.Popen
def launch(argv, *args, **kwargs):
    if 'knowledge.plan_jobs' in argv:
        argv = [argv[0], '-I', '-B', '-c', child, argv[-1], {str(self.ready)!r}, {str(self.release)!r}, 'pause']
    return real(argv, *args, **kwargs)
subprocess.Popen = launch
request = json.load(sys.stdin)
try:
    emit_json(execute(sys.argv[2], {str(self.install)!r}, request.pop('directory'), request))
except Exception:
    Path({str(self.base/'launcher-error')!r}).write_text(traceback.format_exc(), encoding='utf-8')
    raise
"""
        with self.host(launcher, KNOWLEDGE_OBSERVE_MS='45000', KNOWLEDGE_COMMAND_WAIT_MS='0') as host:
            try:
                until(lambda: self.ready.exists() or host.poll() is not None, bool, seconds=15)
                if host.poll() is not None:
                    if (self.base/'launcher-error').exists():
                        self.fail((self.base/'launcher-error').read_text(encoding='utf-8'))
                    self.fail(host.communicate(timeout=10))
                status = self.execute(action='status')
                self.assertEqual(status['worker_state'], 'RUNNING')
                host.kill()
                host.communicate(timeout=10)
                self.assertEqual(self.execute(action='status')['worker_state'], 'RUNNING')
            finally:
                if host.poll() is None:
                    host.kill()
                    host.communicate(timeout=10)
                self.release.touch()
        self.assertEqual(self.await_result(status['job_id'])['state'], 'AWAITING_EXACT_APPROVAL')

    @unittest.skipUnless(shutil.which('node'), 'Node runtime for generated plugin')
    def test_generated_plugin_command_wait_timeout_leaves_child_alive(self):
        launcher = f"""
import json, time, sys
from pathlib import Path
request = json.load(sys.stdin)
if request.get('action') == 'capabilities':
    print(json.dumps({{'ok': True, 'tools': ['knowledge_capabilities','knowledge_scan','knowledge_scan_diagnostics',
                      'knowledge_submit_candidates','knowledge_plan','knowledge_confluence']}}))
else:
    time.sleep(.65)
    Path({str(self.ready)!r}).touch()
    print('{{"ok":true,"state":"AWAITING_EXACT_APPROVAL"}}')
"""
        host = self.host(launcher, KNOWLEDGE_OBSERVE_MS='50', KNOWLEDGE_COMMAND_WAIT_MS='400')
        with host:
            _, errors = host.communicate(timeout=15)
        self.assertNotEqual(host.returncode, 0)
        self.assertIn('stopped waiting for a command response', errors)
        until(self.ready.is_file, bool, seconds=5)


class SourceReconciliation(PushFixture):
    def test_unrelated_committed_edit_keeps_candidate_ids_and_skips_extraction(self):
        scan = self.scan()
        (self.root/'README.md').write_text('# An unrelated README change\n', encoding='utf-8')
        git(self.root, 'add', 'README.md')
        git(self.root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'docs')
        with patch.object(discovery, 'extract', side_effect=AssertionError('unchanged code extracted')):
            result = push(self.store, self.root, self.state, self.binding, {})
        self.assertEqual(result['source_revalidated_git'], len(scan['candidates']))
        self.assertEqual({row['candidate'] for row in self.dispositions(result)}, set(scan['candidates']))
        self.assertEqual(result['candidate_counts']['skipped'], 0)
        self.assertEqual(self.execute(approve=result['fingerprint'])['state'], 'ACKNOWLEDGED')

    def test_edit_delete_rename_and_add_use_incremental_discovery_then_prepare(self):
        original = self.scan()
        (self.root/'Class0.cs').write_text('public class Modified {}\n', encoding='utf-8')
        (self.root/'Class1.cs').rename(self.root/'Moved.cs')
        (self.root/'Class2.cs').unlink()
        (self.root/'Added.cs').write_text('public class NewlyAdded {}\n', encoding='utf-8')
        first = self.prepare()
        self.assertEqual(first['skipped_by_reason'], {'git-source-content-changed': 1, 'git-source-deleted-or-renamed': 2})
        found = self.scan(incremental=True)
        self.assertTrue(found['identity_verification']['complete'], found['identity_verification'])
        self.assertEqual(set(found['work']['paths_this_call']), {'Class0.cs', 'Added.cs', 'Moved.cs'})
        current = self.prepare()
        rows = {row['candidate']: row for row in self.dispositions(current)}
        self.assertTrue(set(original['candidates']) <= rows.keys())
        self.assertTrue(set(found['candidates']) <= rows.keys())
        self.assertTrue(all(rows[cid]['disposition'] == 'included' for cid in found['candidates']))
        counts = current['candidate_counts']
        self.assertEqual(counts['pending'], counts['included'] + counts['skipped'] + counts['blocked_by_plan'])
        self.assertEqual(counts['pending'], len(rows))
        self.assertFalse(self.store.export()['records']['claims'])

    def test_changed_cross_file_identity_and_build_inputs_explain_deferred_candidates(self):
        self.scan()
        (self.root/'Collision.cs').write_text('public class Example0 {}\n', encoding='utf-8')
        first = self.prepare()
        self.assertEqual(first['skipped_by_reason'], {'git-lexical-identity-needs-review': 1})
        row = next(row for row in self.dispositions(first) if row['disposition'] == 'skipped')
        self.assertIn('Collision.cs', row['details']['paths'])
        (self.root/'Directory.Build.props').write_text('<Project><PropertyGroup><DefineConstants>NEW</DefineConstants></PropertyGroup></Project>', encoding='utf-8')
        second = self.prepare()
        self.assertEqual(second['state'], 'BLOCKED')
        self.assertTrue(all(row['details']['broader_scan_required'] for row in self.dispositions(second)))

    def test_mixed_sources_page_version_change_and_exact_approval(self):
        self.scan()
        page = confluence.register(self.store, document())['source']
        document_id = self.store.submit(proposal(self.store, page))['candidate']
        initial = self.prepare()
        confluence.register(self.store, document(version=2, content='A changed business rule.'))
        with self.assertRaisesRegex(KnowledgeError, 'stale-plan'):
            self.execute(approve=initial['fingerprint'])
        plan = self.prepare()
        row = next(row for row in self.dispositions(plan) if row['candidate'] == document_id)
        self.assertEqual(row['reason'], 'stale-confluence-revision')
        self.assertEqual(row['details']['observed_revision'], 2)
        self.assertEqual(self.execute(approve=plan['fingerprint'])['state'], 'ACKNOWLEDGED')
        self.assertNotIn('cf.claim', {item['id'] for item in self.store.export()['records']['claims']})

    def test_source_changes_after_prepare_and_during_apply_require_reapproval(self):
        self.scan()
        before = self.prepare()
        (self.root/'README.md').write_text('new source snapshot', encoding='utf-8')
        with self.assertRaisesRegex(KnowledgeError, 'machine-plan-drift'):
            self.execute(approve=before['fingerprint'])
        after = self.prepare()
        self.assertNotEqual(after['fingerprint'], before['fingerprint'])
        self.assertFalse(self.store.export()['records']['claims'])

        def edit(phase):
            if phase == 'canonical-record-written':
                (self.root/'Class0.cs').write_text('public class ChangedDuringApply {}', encoding='utf-8')

        with patch('knowledge.store.checkpoint', edit):
            with self.assertRaisesRegex(KnowledgeError, 'source-drift-before-commit'):
                self.execute(approve=after['fingerprint'])
        self.assertFalse(self.store.export()['records']['claims'])
        self.assertTrue(all(row['status'] == 'pending' for row in self.store.status()['queue']))

    def test_mcp_job_paging_permissions_and_legacy_exact_approval(self):
        self.scan()
        legacy = self.store.prepare()
        seal = {**self.binding, 'canonical_plan': legacy['fingerprint'],
                'source_identity': discovery.inventory(self.root)['identity']}
        approval = fingerprint(seal)
        write(self.state/'plans'/f'{approval[7:]}.json', {'version': 1, 'binding': seal, 'approved': False})
        peer = Wire([sys.executable, '-I', '-B', '-m', 'knowledge.machine_mcp', '--installation', self.install],
                    roots=lambda: [self.root])
        try:
            peer.initialize()
            started = peer.tool('knowledge_plan', action='prepare', wait_seconds=0)
            job = started['job_id']
            outcome = until(lambda: peer.tool('knowledge_plan', action='status', job_id=job),
                            lambda row: row['worker_state'] not in scan_jobs.ACTIVE)
            self.assertEqual(outcome['state'], 'AWAITING_EXACT_APPROVAL')
            counts = outcome['candidate_counts']
            page = peer.tool('knowledge_scan_diagnostics', section='plan-dispositions', limit=1)
            self.assertEqual(page['total'], counts['pending'])
            self.assertEqual(page['next_cursor'], 1)
            self.assertFalse(self.store.export()['records']['claims'])
            refused = peer.tool('knowledge_plan', action='prepare', approve=approval)
            self.assertEqual(refused['error'], 'prepare-is-not-approval')
            result = peer.tool('knowledge_plan', action='apply', approve=approval)
            self.assertEqual(result['state'], 'ACKNOWLEDGED', result)
        finally:
            peer.close()


if __name__ == '__main__':
    unittest.main()
