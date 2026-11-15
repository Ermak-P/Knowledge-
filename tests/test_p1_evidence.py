"""Evidence refusal must fail for source/evidence corruption, not just syntax."""
from pathlib import Path
import importlib.util
import json
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('p1_evidence_test',Path(__file__).resolve().parents[1]/'scripts/p1_evidence.py')
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)


class EvidenceGateTests(unittest.TestCase):
    def test_failed_incomplete_mixed_missing_stale_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            old=e.OUT;e.OUT=Path(tmp)
            try:
                directory=e.OUT/'runs'/'synthetic';directory.mkdir(parents=True)
                artifact=directory/'data.json';artifact.write_text('{"synthetic":true}')
                value=dict(run_id='synthetic',status='PASS',source_identity=e.identity(),checks={n:dict(status='PASS',returncode=0,artifacts={'runs/synthetic/data.json':e.sha(artifact)}) for n in e.REQUIRED})
                def write(v):e.save(e.OUT/'verification-summary.json',v);e.save(directory/'run.json',v)
                write(value);self.assertEqual(e.validate_current()['status'],'PASS')
                for state in ('FAILED','IN_PROGRESS'):
                    write(dict(value,status=state))
                    with self.assertRaises(AssertionError):e.validate_current()
                write(dict(value,source_identity='stale'))
                with self.assertRaises(AssertionError):e.validate_current()
                write(value);e.save(directory/'run.json',dict(value,run_id='mixed'))
                with self.assertRaises(AssertionError):e.validate_current()
                write(value);artifact.write_text('changed')
                with self.assertRaises(AssertionError):e.validate_current()
                artifact.unlink()
                with self.assertRaises((AssertionError,OSError)):e.validate_current()
            finally:e.OUT=old
