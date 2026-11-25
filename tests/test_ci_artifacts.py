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

    def test_draft_release_download_is_verified_and_corrupt_bytes_are_rejected(self):
        import hashlib,shutil
        from unittest.mock import patch
        spec=importlib.util.spec_from_file_location('release_receipt',ROOT/'scripts/release_receipt.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);assets=root/'dist';assets.mkdir();(assets/'kit.zip').write_bytes(b'fixture-kit');(assets/'kit.zip.sha256').write_text(hashlib.sha256(b'fixture-kit').hexdigest()+'  kit.zip')
            view=dict(isDraft=True,url='https://example.invalid/draft',tagName='knowledge-fixture',targetCommitish='source',assets=[dict(name=p.name) for p in assets.iterdir()])
            def output(args,**kw):return 'source' if args[0]=='git' else json.dumps(view)
            def download(args,**kw):
                for p in assets.iterdir():shutil.copyfile(p,Path(args[-1])/p.name)
            with patch.object(module.subprocess,'check_output',output),patch.object(module.subprocess,'run',download):
                self.assertTrue(module.verify('knowledge-fixture','source',assets)['uploaded_bytes_verified'])
                view['isDraft']=False
                with self.assertRaises(AssertionError):module.verify('knowledge-fixture','source',assets)
                view['isDraft']=True
            def corrupt(args,**kw):download(args,**kw);(Path(args[-1])/'kit.zip').write_bytes(b'changed')
            with patch.object(module.subprocess,'check_output',output),patch.object(module.subprocess,'run',corrupt):
                with self.assertRaisesRegex(AssertionError,'mismatch'):module.verify('knowledge-fixture','source',assets)

    def test_unit_failure_does_not_hide_installer_checks_or_become_pass(self):
        import contextlib,io,sys
        from types import SimpleNamespace
        from unittest.mock import patch
        for name,folder,unit in [('verify_machine.py','AutomaticInstaller-fast','machine-unit-tests'),('verify_p4.py','P4','regressions')]:
            with self.subTest(script=name),tempfile.TemporaryDirectory() as tmp,patch.object(sys,'path',[str(ROOT/'scripts'),*sys.path]):
                spec=importlib.util.spec_from_file_location('qualification_fixture',ROOT/'scripts'/name);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);root=Path(tmp)
                def run(args,**kwargs):
                    words=[str(x) for x in args]
                    if any(x.endswith('build_p4.py') for x in words):
                        kit=Path(words[words.index('--output')+1])/'knowledge-harness-0.5.0rc1';kit.mkdir(parents=True)
                    if any(x.endswith('p4_native.py') for x in words):
                        out=Path(words[-1]);out.mkdir(parents=True);(out/'result.json').write_text('{}')
                    bad=any(x.endswith(('test-driver.py','regressions.py')) for x in words)
                    return SimpleNamespace(returncode=1 if bad else 0)
                with patch.object(module,'ROOT',root),patch.object(module,'source',lambda:{}),patch.object(module.subprocess,'check_output',lambda *a,**kw:'0'*40),patch.object(module.subprocess,'run',run),contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaisesRegex(RuntimeError,'qualification failed'):module.main()
                report=next((root/'reports'/folder/'runs').glob('*/run.json'));value=json.loads(report.read_text())
                self.assertEqual(value['status'],'FAILED');self.assertEqual(value['checks'][unit],'FAIL')
                self.assertEqual(value['checks']['machine-installer'],'PASS');self.assertEqual(value['checks']['machine-native-commands'],'PASS')
