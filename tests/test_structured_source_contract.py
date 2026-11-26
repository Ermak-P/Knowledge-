"""Real scan checkpoints and stdio MCP replay for structured-source compatibility."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from core_wire import Wire
from test_machine_commands import fixture, git, wait, write
from test_core_reliability import upgraded
from knowledge import discovery, source_reader
from knowledge.diagnostic_contract import SECTIONS
from knowledge.lifecycle import envelope
from knowledge.project_commands import diagnostics, execute
from knowledge.tool_help import HELP, SUBMISSION
from knowledge.util import KnowledgeError, canonical_json


class StructuredSource(unittest.TestCase):
    def test_dialects_bom_locations_and_scan_source_read_agree(self):
        with tempfile.TemporaryDirectory() as tmp:
            install, root = fixture(tmp, 1)
            store = upgraded(root)
            sample = '{\r\n  // comment\r\n  "url": "https://host/\\"/*literal*/", /* here\r\n  too */\r\n}\r\n'
            for path in ('appsettings.json', 'appsettings.Test.json', 'launchSettings.json'):
                (root / path).write_bytes(sample.encode('utf-8-sig'))
            (root / 'with-comments.jsonc').write_text('{"value": 2 /* only a comment */}')
            (root / 'strict.json').write_text(sample)
            (root / 'bad.jsonc').write_text('{\n "value": /* unfinished')
            (root / 'override.json').write_text(sample)
            write(store.base / 'discovery.json', {'version': 1, 'json_dialects': {'override.json': 'dotnet-json'}})
            full = discovery.scan(store, max_files=100)
            coverage = full['coverage']
            for path in ('appsettings.json', 'appsettings.Test.json', 'launchSettings.json', 'with-comments.jsonc', 'override.json'):
                self.assertEqual(coverage[path]['processing_status'], 'processed', coverage[path])
            self.assertEqual(coverage['appsettings.json']['encoding'], 'utf-8-sig')
            self.assertEqual(coverage['strict.json']['syntax_reason'], 'unsupported-json-comments')
            self.assertEqual((coverage['strict.json']['line'], coverage['strict.json']['column']), (2, 3))
            self.assertEqual(coverage['bad.jsonc']['syntax_reason'], 'unterminated-json-comment')
            self.assertEqual(coverage['bad.jsonc']['line'], 2)
            revision = git(root, 'rev-parse', 'HEAD').stdout.decode().strip()
            incremental = discovery.scan(store, max_files=100, incremental=True, base=revision, head=revision)
            self.assertEqual(incremental['coverage']['appsettings.json']['syntax_policy'], coverage['appsettings.json']['syntax_policy'])
            wire = Wire([sys.executable, '-I', '-m', 'knowledge.machine_mcp', '--installation', install, '--workspace', root])
            self.addCleanup(wire.close)
            wire.initialize()
            read = wire.tool('knowledge_source_read', path='appsettings.json', start_line=3)
            self.assertEqual(read['lines'][0], sample.splitlines()[2])
            self.assertEqual(read['content_hash'], coverage['appsettings.json']['hash'])
            self.assertEqual(wire.tool('knowledge_source_read', path='strict.json')['details']['line'], 2)
            self.assertEqual(discovery._evidence_source(root, 'appsettings.json', None, [sample.splitlines()[2].strip()])[1],
                             {sample.splitlines()[2].strip()})

    def test_targeted_policy_recovery_preserves_history_and_durable_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            install, root = fixture(tmp, 4)
            store = upgraded(root)
            for name in ('appsettings.json', 'launchSettings.json'):
                (root / name).write_text('{ "value": 2, /* comment */ }')
            with patch.object(source_reader, 'VERSION', 'source-reader-v1'):
                prior = discovery.scan(store, max_files=100)
            self.assertEqual(prior['state'], 'COMPLETED_WITH_GAPS')
            before = store.export()
            session = discovery.ScanSession(store)
            rid = session.prepare_recovery(prior['id'], None, None, False)
            first = session.scan(rid, max_files=1)
            self.assertEqual(first['work']['paths_this_call'], ['appsettings.json'])
            self.assertEqual(first['work']['remaining_files'], 1)
            launched = execute('knowledge-init', install, root, {'action': 'recover', 'recovery_of': prior['id'], 'max_files': 1})
            self.assertTrue(launched['ok'], launched)
            observed = wait(install, root)
            self.assertEqual(observed['worker_state'], 'COMPLETED', observed)
            self.assertEqual(observed['scan_id'], rid)
            self.assertEqual(observed['work']['extracted_this_call'], 1)
            self.assertEqual(observed['coverage']['processed_files'], prior['counters']['processed_files'] + 2)
            self.assertEqual(discovery.status(store, prior['id'])['scans'][0]['state'], 'COMPLETED_WITH_GAPS')
            self.assertEqual(discovery.status(store, rid)['scans'][0]['recovery_of'], prior['id'])
            after = store.export()
            self.assertEqual(before['records'], after['records'])
            count = len(after['queue'])
            execute('knowledge-init', install, root, {'action': 'recover', 'recovery_of': prior['id']})
            observed = wait(install, root)
            self.assertEqual(observed['work']['extracted_this_call'], 0)
            self.assertEqual(observed['scan_id'], rid)
            self.assertEqual(len(store.export()['queue']), count)
            self.assertEqual(diagnostics(install, root, section='scans', scan_id=rid)['rows'][0]['recovery_of'], prior['id'])

    def test_incremental_recovery_reuses_verified_old_json_policy_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, root = fixture(tmp, 3)
            store = upgraded(root)
            revision = git(root, 'rev-parse', 'HEAD').stdout.decode().strip()
            with patch.object(source_reader, 'VERSION', 'source-reader-v1'):
                discovery.scan(store, max_files=100)
                (root / 'appsettings.json').write_text('{ /* comment */ "valid": true, }')
                prior = discovery.scan(store, max_files=100, incremental=True, base=revision, head=revision)
            self.assertTrue(prior['identity_verification']['complete'])
            session = discovery.ScanSession(store)
            scan_id = session.prepare_recovery(prior['id'], revision, revision, True)
            recovered = session.scan(scan_id, base=revision, head=revision, incremental=True)
            self.assertEqual(recovered['state'], 'COMPLETED')
            self.assertEqual(recovered['work']['paths_this_call'], ['appsettings.json'])
            self.assertTrue(recovered['identity_verification']['complete'])
            self.assertEqual(recovered['identity_verification']['cached_files'], 4)

    def test_correction_recovers_only_failed_source_and_rejects_other_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, root = fixture(tmp, 2)
            store = upgraded(root)
            (root / 'strict.json').write_text('{bad')
            prior = discovery.scan(store, max_files=100)
            with self.assertRaisesRegex(KnowledgeError, 'scan-recovery-no-eligible-files'):
                discovery.ScanSession(store).prepare_recovery(prior['id'], None, None, False)
            (root / 'strict.json').write_text('{"valid": true}')
            (root / 'Class0.cs').write_text('public class Drift {}')
            with self.assertRaisesRegex(KnowledgeError, 'scan-recovery-successful-source-changed'):
                discovery.ScanSession(store).prepare_recovery(prior['id'], None, None, False)
            git(root, 'checkout', '--', 'Class0.cs')
            session = discovery.ScanSession(store)
            rid = session.prepare_recovery(prior['id'], None, None, False)
            self.assertEqual(session.scan(rid)['work']['paths_this_call'], ['strict.json'])


class McpContract(unittest.TestCase):
    def test_every_section_discovery_contract_and_error_transport(self):
        with tempfile.TemporaryDirectory() as tmp:
            install, root = fixture(tmp)
            store = upgraded(root)
            execute('knowledge-init', install, root, {'action': 'start'})
            scan_id = wait(install, root)['scan_id']
            plan = store.prepare()['fingerprint']
            wire = Wire([sys.executable, '-I', '-m', 'knowledge.machine_mcp', '--installation', install, '--workspace', root])
            self.addCleanup(wire.close)
            wire.initialize()
            discover = wire.tool('knowledge_scan_diagnostics', section='candidates', scan_id=scan_id, limit=1)
            cid = discover['rows'][0]['candidate']
            self.assertIsNotNone(discover['next_cursor'])
            custom = {'candidate': {'candidate': cid, 'plan': plan}, 'plan-dispositions': {'plan': plan}}
            for section in SECTIONS:
                with self.subTest(section=section):
                    value = wire.tool('knowledge_scan_diagnostics', section=section, **custom.get(section, {}))
                    self.assertTrue(value['ok'], value)
                    self.assertLessEqual(len(canonical_json(value).encode()), 16000)
            invalid = wire.request(199, 'tools/call', {'name': 'knowledge_scan_diagnostics',
                                   'arguments': {'section': 'candidate', 'scan_id': scan_id}})
            self.assertTrue(invalid['isError'])
            value = invalid['structuredContent']
            self.assertEqual(value['error'], 'invalid-diagnostic-arguments')
            self.assertEqual(value['details']['next_invocation']['scan_id'], scan_id)
            self.assertEqual(wire.tool('knowledge_scan_diagnostics', section='candidate')['details']['missing_arguments'], ['candidate'])
            self.assertEqual(wire.tool('knowledge_scan_diagnostics', section='candidate', candidate=777)['error'], 'invalid-tool-arguments')
            self.assertEqual(wire.tool('knowledge_scan_diagnostics', section='candidate', candidate='nonexistent')['error'], 'unknown-candidate')
            self.assertEqual(wire.tool('knowledge_scan_diagnostics', section='candidate', candidate=cid, max_bytes=256)['error'],
                             'diagnostic-budget-too-small')
            self.assertEqual(diagnostics(install, root, section='candidates', plan=plan)['rows'][0]['disposition'], 'included')

    def test_packaged_help_on_storeless_install_and_examples(self):
        import jsonschema

        with tempfile.TemporaryDirectory() as tmp:
            install, root = fixture(tmp, 0)
            wire = Wire([sys.executable, '-I', '-m', 'knowledge.machine_mcp', '--installation', install])
            self.addCleanup(wire.close)
            wire.initialize()
            catalog = {tool['name']: tool for tool in wire.request(102, 'tools/list')['tools']}
            self.assertEqual(set(catalog), set(HELP))
            for tool, (_, example) in HELP.items():
                if example is not None:
                    jsonschema.validate(example, catalog[tool]['inputSchema'])
            envelope(SUBMISSION['proposals'][0])
            self.assertEqual(wire.tool('knowledge_instructions', tool='knowledge_submit_candidates')['example'], SUBMISSION)
            self.assertEqual(set(wire.tool('knowledge_instructions')['instructions']), set(HELP))
            self.assertEqual(set(wire.tool('knowledge_instructions', tool='knowledge_scan_diagnostics', name='sections')['sections']), set(SECTIONS))
            self.assertFalse((root / '.knowledge').exists())
