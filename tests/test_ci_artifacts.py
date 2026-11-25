"""Compact receipts cannot copy raw artifacts back into Git."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


class ArtifactReceipts(unittest.TestCase):
    def test_receipt_contains_summaries_but_not_raw_logs_packages_or_configuration(self):
        spec=importlib.util.spec_from_file_location('ci_receipt',ROOT/'scripts/p4_ci_receipt.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp);(run/'secret.log').write_text('SYNTHETIC-SECRET-MUST-NOT-APPEAR');(run/'provider.json').write_text('{"secret":"SYNTHETIC-SECRET-MUST-NOT-APPEAR"}');(run/'package.zip').write_bytes(b'RAW-PACKAGE')
            (run/'tests.json').write_text(json.dumps(dict(tests=2,passed=1,errors=1,results=[dict(test='fixture.teardown',status='ERROR')])))
            result=module.compact(run,dict(checks={'tests':'FAIL'},source={'source.py':'hash'},commands=[],unchanged=True),dict(platform='Windows',qualification='full'))
            self.assertEqual(result['tests']['nonpassing'],[dict(test='fixture.teardown',status='ERROR')]);self.assertEqual(result['artifact_name'],'p4-windows-2022')
            self.assertNotIn('SYNTHETIC-SECRET',json.dumps(result));self.assertNotIn('RAW-PACKAGE',json.dumps(result))
            script=(ROOT/'scripts/p4_ci_receipt.py').read_text();self.assertNotIn('copytree',script);self.assertNotIn("target/'run'",script)
