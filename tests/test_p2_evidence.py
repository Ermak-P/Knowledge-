import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from p2_evidence import REQUIRED,save,sha,validate

class EvidenceGate(unittest.TestCase):
    def test_failed_interrupted_stale_mixed_missing_and_modified_artifacts_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);run='test-run';folder=root/'runs'/run;folder.mkdir(parents=True);log=folder/'test.log';log.write_text('actual evidence')
            value=dict(run_id=run,status='PASS',source_identity='current',checks={name:dict(status='PASS',returncode=0,artifacts={'runs/'+run+'/test.log':sha(log)}) for name in REQUIRED})
            def check(v,identity='current'):
                save(folder/'run.json',v);return validate(v,identity,root)
            self.assertEqual(check(value),value)
            for status in ('FAILED','IN_PROGRESS'):
                v=copy.deepcopy(value);v['status']=status
                with self.assertRaises(AssertionError):check(v)
            with self.assertRaises(AssertionError):check(value,'changed source')
            v=copy.deepcopy(value);del v['checks']['evaluation']
            with self.assertRaises(AssertionError):check(v)
            v=copy.deepcopy(value);v['checks']['evaluation']['artifacts']={'runs/other/test.log':sha(log)}
            with self.assertRaises(AssertionError):check(v)
            save(folder/'run.json',value);v=copy.deepcopy(value);v['run_id']='other'
            with self.assertRaises((AssertionError,FileNotFoundError)):validate(v,'current',root)
            save(folder/'run.json',value);log.write_text('tampered')
            with self.assertRaises(AssertionError):validate(value,'current',root)
            log.unlink()
            with self.assertRaises(FileNotFoundError):validate(value,'current',root)
