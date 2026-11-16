"""Pure kit validation negative cases; real offline installs are in release checks."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('kit_install',ROOT/'release/kit/install.py');kit=importlib.util.module_from_spec(spec);spec.loader.exec_module(kit)
class InstallerValidation(unittest.TestCase):
    def test_tampered_unsafe_unknown_release_refuse_before_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);file=root/'wheel.whl';file.write_bytes(b'actual local artifact')
            manifest={'version':1,'product':kit.VERSION,'files':{'wheel.whl':kit.sha(file)}};(root/'RELEASE.json').write_text(json.dumps(manifest))
            self.assertEqual(kit.manifest(root),manifest)
            file.write_bytes(b'tampered')
            with self.assertRaisesRegex(RuntimeError,'checksum'):kit.manifest(root)
            manifest['files']={'../escape':'bad'};(root/'RELEASE.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(RuntimeError,'unsafe release'):kit.manifest(root)
            manifest['version']=99;(root/'RELEASE.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(RuntimeError,'unsupported release'):kit.manifest(root)
