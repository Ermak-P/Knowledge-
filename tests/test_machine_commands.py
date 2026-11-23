"""Machine commands use installed modules and real chunk subprocesses."""
import copy
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from knowledge import providers, lifecycle, discovery
from knowledge.store import Store
from knowledge.util import KnowledgeError, digest
from knowledge.project_commands import execute, resolve_root
from knowledge.auto_init import run, ScanError
from knowledge.scan_jobs import status as job_status
from harness import runtime, companion, engine
from p2_fixtures import project as harness_project, configuration, task, http_provider, FixtureProvider

ROOT = Path(__file__).resolve().parents[1]
installer = runpy.run_path(str(ROOT / 'installer/knowledge_install.py'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def fixture(base, count=4):
    install = Path(base) / 'machine'
    current = {'version': 1, 'runtime': 'runtimes/fixture', 'product': '0.5.0rc1', 'release_sha256': 'fixture-release'}
    (install / 'runtimes/fixture').mkdir(parents=True)
    write(install / 'current.json', current)
    write(install / 'knowledge-machine-install.json', {'version': 1, 'product': 'knowledge-machine', 'root': str(install), 'state': 'installed', 'current': current})
    write(install / 'config/provider.json', {'provider': {'endpoint': 'http://127.0.0.1:9000/v1/chat/completions', 'model': 'controlled-demo', 'evidence': 'test-double'}})
    root = Path(base) / 'project'
    root.mkdir()
    (root / 'Project.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>', encoding='utf-8')
    for number in range(count):
        (root / ('Class' + str(number) + '.cs')).write_text('public class Example' + str(number) + ' {}\n', encoding='utf-8')
    git(root, 'init')
    git(root, 'add', '.')
    git(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'initial')
    return install, root


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True)


def wait(install, root, command='knowledge-init'):
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        value = execute(command, install, root, {'action': 'status'})
        if value['state'] not in ('STARTING', 'RUNNING'):
            return value
        time.sleep(.1)
    raise AssertionError('Durable job did not finish')


class SharedProviderTests(unittest.TestCase):
    def test_two_projects_share_provider_and_effective_authority_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            install, root = fixture(tmp)
            other = Path(tmp) / 'other'; other.mkdir()
            raw = {'version': 1, 'provider_ref': str(install / 'config/provider.json'), 'recipes': {}, 'limits': {}, 'capture': 'off'}
            for target in (root, other): write(target / '.harness/runner.json', raw)
            before = runtime.config(root)
            self.assertEqual(before, runtime.config(other))
            changed = {'provider': {**before['provider'], 'model': 'changed-demo'}}
            write(install / 'config/provider.json', changed)
            for target in (root, other):
                self.assertEqual(runtime.config(target)['provider']['model'], 'changed-demo')
                self.assertNotEqual(digest(before), digest(runtime.config(target)))
                self.assertEqual(json.loads((target / '.harness/runner.json').read_text()), raw)
            with self.assertRaisesRegex(KnowledgeError, 'provider-configuration-drift'): runtime.validate_config(before)

    def test_legacy_inline_compatibility_and_explicit_evidence_and_reference(self):
        raw = {'version': 1, 'provider': {'endpoint': 'http://127.0.0.1:9000/v1/chat/completions', 'model': 'legacy'}, 'recipes': {}, 'limits': {}, 'capture': 'off'}
        self.assertEqual(runtime.validate_config(raw), raw)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'provider.json'; write(path, {'provider': raw['provider']})
            with self.assertRaisesRegex(KnowledgeError, 'shared-provider-evidence-required'): providers.shared(path)
            with self.assertRaisesRegex(KnowledgeError, 'ambiguous-provider'): runtime.validate_config({**raw, 'provider_ref': str(path)})
            write(path, {'provider': {**raw['provider'], 'evidence': 'test-double', 'api_key': 'do-not-accept'}})
            with self.assertRaisesRegex(KnowledgeError, 'invalid-provider-config'): providers.shared(path)

    def test_existing_companion_enrollment_rejects_changed_shared_provider(self):
        with tempfile.TemporaryDirectory() as tmp, http_provider(FixtureProvider()) as endpoint:
            base = Path(tmp); root = harness_project(base / 'project')
            shared = base / 'provider.json'; conf = configuration(endpoint)
            write(shared, {'provider': conf.pop('provider')})
            conf['provider_ref'] = str(shared); runtime.configure(root, conf, True)
            write(root / 'task.json', task(kind='read-only'))
            plan = companion.preview(root, 'task.json'); companion.apply(root, plan['preview'], plan['fingerprint'])
            from harness.runtime import Journal
            def interrupted(*args, **kwargs): raise KeyboardInterrupt()
            with patch.object(engine.provider, 'complete', interrupted):
                with self.assertRaises(KeyboardInterrupt): companion.run_task(root, 'approved_task')
            run_id = Journal(root).runs()[0]['id']
            value = json.loads(shared.read_text()); value['provider']['model'] = 'changed'; write(shared, value)
            result = engine.resume(root, run_id)
            self.assertFalse(result['ok'])
            self.assertIn(result['error'], ('host-enrollment-changed-review-required', 'configuration-changed-revalidation-required'))
            self.assertFalse(Journal(root).actions(run_id))


class ProjectCommandsTests(unittest.TestCase):
    def test_durable_chunks_rerun_no_duplicates_and_explicit_push_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            install, root = fixture(tmp, 8)
            initial = execute('knowledge-init', install, root, {'max_files': 2})
            self.assertIn(initial['state'], ('STARTING', 'RUNNING'))
            result = wait(install, root)
            self.assertTrue(result['coverage_complete'], result)
            self.assertEqual(result['state'], 'PARTIAL')
            self.assertGreater(result['queued_added'], 0)
            scan = result['scan_id']; store = Store(root)
            self.assertFalse(store.export()['records']['claims'])
            queue = store.status()['queue']
            execute('knowledge-init', install, root, {})
            repeated = wait(install, root)
            self.assertEqual(repeated['scan_id'], scan)
            self.assertEqual(repeated['queued_added'], 0)
            self.assertEqual(store.status()['queue'], queue)
            prepared = execute('knowledge-candidates-push', install, root, {})
            self.assertFalse(store.export()['records']['claims'])
            path = install / 'config/provider.json'; config = json.loads(path.read_text()); config['provider']['model'] = 'new-model'; write(path, config)
            with self.assertRaisesRegex(KnowledgeError, 'machine-plan-drift'):
                execute('knowledge-candidates-push', install, root, {'approve': prepared['fingerprint']})
            again = execute('knowledge-candidates-push', install, root, {})
            self.assertEqual(again['canonical_plan'], prepared['canonical_plan'])
            self.assertNotEqual(again['fingerprint'], prepared['fingerprint'])
            applied = execute('knowledge-candidates-push', install, root, {'approve': again['fingerprint']})
            self.assertEqual(applied['state'], 'ACKNOWLEDGED')
            self.assertTrue(store.export()['records']['claims'])
            self.assertFalse(list((root / '.knowledge').glob('*.jsonl')))

    def test_working_tree_incremental_only_extracts_changed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            install, root = fixture(tmp, 8)
            execute('knowledge-init', install, root, {}); wait(install, root)
            (root / 'Class3.cs').write_text('public class ChangedExample {}\n', encoding='utf-8')
            execute('knowledge-candidates-update', install, root, {})
            result = wait(install, root, 'knowledge-candidates-update')
            self.assertEqual(result['scope']['kind'], 'incremental')
            self.assertEqual(result['work']['durable_extracted_files'], 1)
            with Store(root).connection() as db:
                row = db.execute('SELECT payload FROM scans WHERE id=?', (result['scan_id'],)).fetchone()
            self.assertEqual(set(json.loads(row[0])['coverage']), {'Class3.cs'})
            self.assertFalse(Store(root).export()['records']['claims'])

    def test_root_ambiguity_p0_and_legacy_are_not_silently_migrated(self):
        with tempfile.TemporaryDirectory() as tmp:
            install, root = fixture(tmp)
            with self.assertRaisesRegex(KnowledgeError, 'ambiguous'): resolve_root(root, [str(root), str(install)])
            Store(root).init()
            with self.assertRaisesRegex(KnowledgeError, 'upgrade-approval-required'): execute('knowledge-init', install, root, {})
            self.assertFalse(lifecycle.upgrade_preview(Store(root))['already_upgraded'])
            self.assertFalse((root / '.knowledge/machine.json').exists())
            preview = lifecycle.upgrade_preview(Store(root))
            execute('knowledge-init', install, root, {'upgrade_approval': preview['fingerprint']}); wait(install, root)
        with tempfile.TemporaryDirectory() as tmp:
            install, root = fixture(tmp); (root / '.ai').mkdir()
            with self.assertRaises(KnowledgeError): execute('knowledge-init', install, root, {})
            self.assertFalse((root / '.knowledge').exists())

    def test_explicit_project_transition_preserves_build_memory_and_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            install, root = fixture(tmp)
            raw = {'version': 1, 'provider': {'endpoint': 'http://127.0.0.1:9100/v1/chat/completions', 'model': 'inline'}, 'recipes': {}, 'limits': {'requests': 15}, 'capture': 'off', 'memory': {'teaching_mode': 'catalog'}}
            write(root / '.harness/runner.json', raw)
            result = execute('knowledge-init', install, root, {})
            self.assertTrue(result['runner_transitioned'])
            wait(install, root)
            current = json.loads((root / '.harness/runner.json').read_text())
            self.assertEqual({k: v for k, v in current.items() if k != 'provider_ref'}, {k: v for k, v in raw.items() if k != 'provider'})
            self.assertNotIn('provider', current)

    def test_real_helper_stops_at_budget_and_resumes_same_scan_finite_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            install, root = fixture(tmp, 6)
            store = Store(root); store.init(); lifecycle.upgrade(store, lifecycle.upgrade_preview(store)['fingerprint'])
            output = install / 'manual-helper'; output.mkdir()
            # Each call is a genuine python -I knowledge.cli subprocess. The
            # helper's explicit max-calls proves no recursive automatic CLI.
            with self.assertRaisesRegex(ScanError, 'max-calls'): run(root, output, max_files=2, max_calls=1)
            first = json.loads((output / 'checkpoint.json').read_text())['scan_id']
            self.assertEqual(run(root, output, max_files=2), 0)
            self.assertEqual(json.loads((output / 'checkpoint.json').read_text())['scan_id'], first)
            self.assertTrue(json.loads((output / 'last-result.json').read_text())['reconciliation']['complete'])
            self.assertLess(len((output / 'last-stdout.txt').read_bytes()), 300000)


class MachineTransactionTests(unittest.TestCase):
    def test_fault_rolls_back_all_files_and_preserves_user_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); pointer = root / 'current.json'; pointer.write_bytes(b'old-generation')
            settings = root / 'user-setting.json'; settings.write_bytes(b'preserve')
            new = root / 'command.md'
            with self.assertRaisesRegex(installer['InstallError'], 'Injected'):
                installer['transaction'](root, {pointer: b'new-generation', new: b'command'}, fail_after=2)
            self.assertEqual(pointer.read_bytes(), b'old-generation')
            self.assertFalse(new.exists())
            self.assertEqual(settings.read_bytes(), b'preserve')
            self.assertFalse((root / 'transaction.json').exists())

    def test_interrupted_rollback_preserves_concurrent_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); path = root / 'command.md'; path.write_bytes(b'user edit')
            write(root / 'transaction.json', {'root': str(root), 'entries': [{'path': str(path), 'before': None, 'before_hash': None, 'after_hash': 'old-owned-hash'}]})
            with self.assertRaisesRegex(installer['InstallError'], 'Concurrent edit'): installer['rollback'](root)
            self.assertEqual(path.read_bytes(), b'user edit')

    def test_unrelated_directory_fails_without_creating_marker_or_global_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'unrelated'; root.mkdir(); (root / 'user.txt').write_bytes(b'preserve')
            with self.assertRaisesRegex(installer['InstallError'], 'not an owned'): installer['install'](ROOT, root)
            self.assertEqual([p.name for p in root.iterdir()], ['user.txt'])

class HelperFailureTests(unittest.TestCase):
    def test_invalid_json_cli_failure_and_timeout_stop_after_one_attempt(self):
        from knowledge import auto_init
        cases = [subprocess.CompletedProcess([], 0, 'not json', ''),
                 subprocess.CompletedProcess([], 1, '{"ok":false,"error":"busy"}', ''),
                 subprocess.TimeoutExpired(['python'], .01)]
        with tempfile.TemporaryDirectory() as tmp:
            install, root = fixture(tmp)
            for number, case in enumerate(cases):
                options = {'side_effect': case} if isinstance(case, Exception) else {'return_value': case}
                with self.subTest(case=number), patch.object(auto_init.subprocess, 'run', **options) as invoked:
                    with self.assertRaises(ScanError): run(root, install / ('failure' + str(number)))
                    self.assertEqual(invoked.call_count, 1)
            self.assertEqual(json.loads((install / 'failure2/last-error.json').read_text())['error'], 'command-timeout-outcome-unknown')

    def test_source_drift_on_real_resume_does_not_start_a_new_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            install, root = fixture(tmp, 4)
            store = Store(root); store.init(); lifecycle.upgrade(store, lifecycle.upgrade_preview(store)['fingerprint'])
            output = install / 'drift'
            with self.assertRaisesRegex(ScanError, 'max-calls'): run(root, output, max_files=1, max_calls=1)
            old = json.loads((output / 'checkpoint.json').read_text())
            (root / 'Added.cs').write_text('public class Added {}\n')
            with self.assertRaisesRegex(ScanError, 'stale-scan'): run(root, output, max_files=1)
            self.assertEqual(json.loads((output / 'checkpoint.json').read_text()), old)

    def test_native_worker_survives_parent_cli_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            install, root = fixture(tmp, 12)
            process = subprocess.run([sys.executable, '-I', '-B', '-m', 'knowledge.project_commands', '--installation', str(install), '--root', str(root), 'knowledge-init'], input='{"max_files":1}', text=True, capture_output=True, timeout=10)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            value = wait(install, root)
            self.assertEqual(value['state'], 'PARTIAL')
            self.assertTrue(value['coverage_complete'])

    def test_durable_journal_after_process_exit_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); before = root / 'current.json'; before.write_bytes(b'old')
            code = '''import os,runpy,sys
from pathlib import Path
namespace=runpy.run_path(sys.argv[1]); function=namespace['transaction']; original=function.__globals__['atomic']
root=Path(sys.argv[2])
def crash(path,content):
 original(path,content)
 if Path(path).name=='current.json': os._exit(74)
function.__globals__['atomic']=crash
function(root,{root/'current.json':b'new',root/'command.md':b'new'})
'''
            process = subprocess.run([sys.executable, '-I', '-c', code, str(ROOT / 'installer/knowledge_install.py'), str(root)], capture_output=True)
            self.assertEqual(process.returncode, 74)
            self.assertEqual(before.read_bytes(), b'new')
            self.assertTrue((root / 'transaction.json').exists())
            installer['rollback'](root)
            self.assertEqual(before.read_bytes(), b'old')
            self.assertFalse((root / 'command.md').exists())

class MachineMcpTests(unittest.TestCase):
    def test_real_stdio_roots_select_two_stores_and_reject_ambiguity(self):
        import asyncio
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from mcp.types import ListRootsResult, Root
        from fixtures import addition
        with tempfile.TemporaryDirectory() as tmp:
            install, first = fixture(tmp)
            second = Path(tmp) / 'second'; second.mkdir()
            for directory, text in ((first, 'FIRST unique source assertion'), (second, 'SECOND unique source assertion')):
                store = Store(directory); store.init()
                store.submit(addition('machine.common', text))
                plan = store.prepare(); store.apply(plan['fingerprint'], plan['fingerprint']); store.acknowledge(plan['fingerprint'])
            roots = [first]
            async def list_roots(context): return ListRootsResult(roots=[Root(uri=p.as_uri()) for p in roots])
            async def exercise():
                async with asyncio.timeout(30):
                    async with stdio_client(StdioServerParameters(command=sys.executable, args=['-I', '-B', '-m', 'knowledge.machine_mcp', '--installation', str(install)])) as (reader, writer):
                        async with ClientSession(reader, writer, list_roots_callback=list_roots) as session:
                            await session.initialize()
                            for directory, text in ((first, 'FIRST unique'), (second, 'SECOND unique')):
                                roots[:] = [directory]
                                value = await session.call_tool('knowledge_get_claim', {'identifier': 'machine.common'})
                                self.assertIn(text, value.content[0].text)
                            roots[:] = [first, second]
                            value = await session.call_tool('knowledge_get_claim', {'identifier': 'machine.common'})
                            self.assertEqual(json.loads(value.content[0].text)['error'], 'ambiguous-or-missing-workspace-roots')
            asyncio.run(exercise())


class ReviewedCandidateTests(unittest.TestCase):
    def test_reviewed_retire_supersede_preserve_decisions_history_and_revisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            install, root = fixture(tmp, 2)
            execute('knowledge-init', install, root, {}); wait(install, root)
            plan = execute('knowledge-candidates-push', install, root, {})
            execute('knowledge-candidates-push', install, root, {'approve': plan['fingerprint']})
            store = Store(root); claims = store.export()['records']['claims']
            self.assertGreaterEqual(len(claims), 3)
            source = discovery.inventory(root)
            binding = {'identity': source['identity'], 'revision': source['revision'], 'kind': source['snapshot_kind']}
            states = store.status()['revisions']
            first, successor, retired = [row['id'] for row in claims[:3]]
            operations = [lifecycle.op('supersede', 'claims', first, states[first]['revision'], successor=successor),
                          lifecycle.op('retire', 'claims', retired, states[retired]['revision'])]
            candidate = lifecycle.batch(operations, 'Reviewed fixture lifecycle decisions; no inference from lexical absence.', binding)
            result = execute('knowledge-candidates-update', install, root, {'candidates': [candidate]})
            self.assertEqual(result['added'], 1)
            cid = result['results'][0]['candidate']
            lifecycle.dispose(store, cid, 'deferred', 'Fixture review decision retained')
            repeated = execute('knowledge-candidates-update', install, root, {'candidates': [candidate]})
            self.assertEqual(repeated['skipped'], 1)
            self.assertEqual(repeated['results'][0]['status'], 'deferred')
            lifecycle.dispose(store, cid, 'pending', 'Explicit fixture review resumes this candidate')
            prepared = execute('knowledge-candidates-push', install, root, {})
            self.assertEqual(prepared['operations'], {'retire': 1, 'supersede': 1})
            execute('knowledge-candidates-push', install, root, {'approve': prepared['fingerprint']})
            self.assertEqual(store.status()['revisions'][first]['lifecycle'], 'superseded')
            self.assertEqual(store.status()['revisions'][retired]['lifecycle'], 'retired')
            self.assertGreater(len(lifecycle.history(store, first)['revisions']), 1)
            stale = copy.deepcopy(candidate); stale['operations'] = [lifecycle.op('retire', 'claims', successor, states[successor]['revision'] + 99)]
            with self.assertRaises(KnowledgeError): execute('knowledge-candidates-update', install, root, {'candidates': [stale]})

class GlobalRegistrationTests(unittest.TestCase):
    def test_v2_global_jsonc_preserved_and_name_conflicts_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            original = b'// user comment\n{"mcp":{"servers":{"other":{"type":"remote","url":"https://example.invalid/mcp"}}},"plugins":["user-plugin"],}\n'
            config = home / 'opencode.jsonc'; config.write_bytes(original)
            installer['preflight_host'](home)
            self.assertEqual(config.read_bytes(), original)
            write(config, {'mcp': {'servers': {'knowledge_machine': {'type': 'local', 'command': ['user-owned']}}}})
            before = config.read_bytes()
            with self.assertRaisesRegex(installer['InstallError'], 'conflicts'): installer['preflight_host'](home)
            self.assertEqual(config.read_bytes(), before)
            write(config, {'commands': {'knowledge-init': {'template': 'user-owned command'}}})
            with self.assertRaisesRegex(installer['InstallError'], 'conflicts'): installer['preflight_host'](home)

    def test_unlisted_release_asset_refused_before_consumption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file = root / 'wheel.whl'; file.write_bytes(b'fixture owned wheel')
            write(root / 'RELEASE.json', {'product': installer['VERSION'], 'python': '3.12', 'files': {'wheel.whl': installer['sha'](file)}})
            (root / 'unlisted.whl').write_bytes(b'extra untrusted artifact')
            with self.assertRaisesRegex(installer['InstallError'], 'Unlisted'): installer['verify_kit'](root)

class IncrementalIdentityTests(unittest.TestCase):
    def test_cached_unchanged_declaration_blocks_conflicting_delta_without_full_parse(self):
        with tempfile.TemporaryDirectory() as tmp:
            install, root = fixture(tmp, 2)
            execute('knowledge-init', install, root, {}); wait(install, root)
            (root / 'Добавленный файл.cs').write_text('public class Example0 {}\n', encoding='utf-8')
            parsed = []; original = discovery.extract
            def record(directory, path, entry):
                parsed.append(path); return original(directory, path, entry)
            with patch.object(discovery, 'extract', record):
                state = discovery.scan(Store(root), base='HEAD', head='HEAD', incremental=True)
            self.assertEqual(parsed, ['Добавленный файл.cs'])
            self.assertTrue(state['identity_verification']['ambiguous_ids'])
            self.assertFalse(state['candidates'])
            self.assertTrue(state['gaps'])

    def test_missing_baseline_is_explicit_gap_and_committed_unicode_range_is_not_lost(self):
        with tempfile.TemporaryDirectory() as tmp:
            install, root = fixture(tmp, 2)
            store = Store(root); store.init(); lifecycle.upgrade(store, lifecycle.upgrade_preview(store)['fingerprint'])
            (root / 'Новый файл.cs').write_text('public class Added {}\n', encoding='utf-8')
            git(root, 'add', '.'); git(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'added unicode file')
            result = discovery.scan(store, base='HEAD~1', head='HEAD', incremental=True)
            self.assertEqual(set(result['coverage']), {'Новый файл.cs'})
            self.assertFalse(result['identity_verification']['complete'])
            self.assertFalse(result['candidates'])
