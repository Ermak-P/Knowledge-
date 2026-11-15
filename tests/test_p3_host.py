import tempfile,unittest,json
from pathlib import Path
from knowledge.util import KnowledgeError
from harness import companion
from harness.runtime import configure
from p2_fixtures import project,configuration,task

class CompanionTests(unittest.TestCase):
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
