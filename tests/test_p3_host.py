import asyncio,tempfile,unittest,json,sys
from datetime import timedelta
from pathlib import Path
from knowledge.util import KnowledgeError
from harness import companion
from harness.runtime import configure
from p2_fixtures import project,configuration,task,http_provider,FixtureProvider

class CompanionTests(unittest.TestCase):
    def test_configured_stdio_companion_executes_real_guarded_recipes(self):
        from mcp import ClientSession,StdioServerParameters
        from mcp.client.stdio import stdio_client
        from knowledge.store import Store
        from harness.engine import status
        from harness.runtime import Journal
        provider=FixtureProvider()
        with tempfile.TemporaryDirectory(prefix='Companion Ω ') as tmp,http_provider(provider) as endpoint:
            root=project(tmp);configure(root,configuration(endpoint),True)
            (root/'task.json').write_text(json.dumps(task()),encoding='utf-8')
            plan=companion.preview(root,'task.json');companion.apply(root,plan['preview'],plan['fingerprint'])
            entry=json.loads((root/'opencode.json').read_text(encoding='utf-8'))['mcp']['servers']['harness_companion']
            async def execute():
                async with asyncio.timeout(120):
                    async with stdio_client(StdioServerParameters(command=entry['command'][0],args=entry['command'][1:])) as (read,write):
                        async with ClientSession(read,write,read_timeout_seconds=timedelta(seconds=90)) as session:
                            await session.initialize()
                            result=await session.call_tool('harness_run',{'task_name':'approved_task'})
                            return json.loads(result.content[0].text)
            try:outcome=asyncio.run(execute())
            except Exception:
                journal=Journal(root)
                print(json.dumps({'companion_failure_state':[{'run':run,'actions':journal.actions(run['id'])} for run in journal.runs()]}),file=sys.stderr)
                raise
            self.assertTrue(outcome['ok'],outcome)
            self.assertEqual((root/'Feature.cs').read_text(encoding='utf-8'),provider.desired)
            report=status(root,outcome['run_id'])
            self.assertTrue(report['run']['gates']['build']['ok']);self.assertTrue(report['run']['gates']['test']['ok'])
            store=Store(root);self.assertFalse(store.export()['records']['claims']);self.assertTrue(store.status()['queue'])

    def test_exact_local_merge_task_digest_doctor_and_reversible_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=project(tmp);configure(root,configuration('http://127.0.0.1/v1/chat/completions'),True)
            original=b'{\n "model": "synthetic-existing", "custom": {"preserve":true}\n}\n';(root/'opencode.json').write_bytes(original)
            (root/'task.json').write_text(json.dumps(task()),encoding='utf-8')
            plan=companion.preview(root,'task.json');self.assertEqual((root/'opencode.json').read_bytes(),original)
            with self.assertRaises(KnowledgeError):companion.apply(root,plan['preview'],'wrong')
            companion.apply(root,plan['preview'],plan['fingerprint']);self.assertTrue(companion.doctor(root)['ok'])
            current=json.loads((root/'opencode.json').read_text());self.assertTrue(current['custom']['preserve']);self.assertEqual(set(current['mcp']['servers']),{'knowledge_local','harness_companion'})
            with self.assertRaisesRegex(KnowledgeError,'host-task-not-enrolled'):companion.run_task(root,'arbitrary-shell')
            task_path=root/'task.json';before=task_path.read_bytes();task_path.write_text('{}')
            with self.assertRaisesRegex(KnowledgeError,'host-task-changed'):companion.doctor(root)
            task_path.write_bytes(before);remove=companion.preview(root,remove=True);companion.apply(root,remove['preview'],remove['fingerprint']);self.assertEqual((root/'opencode.json').read_bytes(),original)
    def test_host_conflicts_jsonc_and_intervening_changes_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=project(tmp);configure(root,configuration('http://127.0.0.1/v1/chat/completions'),True)
            (root/'opencode.jsonc').write_text('//existing')
            with self.assertRaisesRegex(KnowledgeError,'jsonc-config'):companion.preview(root)
            (root/'opencode.jsonc').unlink();(root/'opencode.json').write_text('{"mcp":{"legacy":{"type":"local"}}}')
            with self.assertRaisesRegex(KnowledgeError,'host-v1-config'):companion.preview(root)
            (root/'opencode.json').write_text('{}');plan=companion.preview(root);(root/'opencode.json').write_text('{"model":"USER"}')
            with self.assertRaisesRegex(KnowledgeError,'stale-host-preview'):companion.apply(root,plan['preview'],plan['fingerprint'])
