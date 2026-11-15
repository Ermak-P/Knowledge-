import copy,tempfile,unittest,json,subprocess
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from p3_evidence import REQUIRED,VERSION,save,sha,validate,qualification,require_native

class ReleaseGate(unittest.TestCase):
    def test_ci_git_transport_retains_prior_wheels_and_exact_log_bytes(self):
        from p3_ci_receipt import copy_run,preserve_bytes
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);run=root/'current';run.mkdir();(run/'previous-P3-review.zip').write_bytes(b'superseded packet')
            wheel=run/'prior-upgrade/previous-wheels/prior.whl';wheel.parent.mkdir(parents=True);wheel.write_bytes(b'PK\x00\r\nraw wheel bytes\n')
            log=run/'command.log';log.write_bytes(b'Windows output\r\nUnicode: \xce\xa9\r\n')
            repo=root/'receipt';repo.mkdir();subprocess.run(['git','init',str(repo)],check=True,capture_output=True)
            subprocess.run(['git','config','core.autocrlf','true'],cwd=repo,check=True)
            preserve_bytes(repo);copy_run(run,repo/'runs/current')
            self.assertFalse((repo/'runs/current/previous-P3-review.zip').exists())
            subprocess.run(['git','add','.'],cwd=repo,check=True)
            for path in (wheel,log):
                stored=subprocess.check_output(['git','show',':runs/current/'+path.relative_to(run).as_posix()],cwd=repo)
                self.assertEqual(stored,path.read_bytes())
    def test_failed_stale_mixed_incomplete_modified_package_or_evidence_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);run='current';folder=root/'runs'/run;folder.mkdir(parents=True);e=folder/'evidence.log';e.write_text('executed result');manifest=folder/'distribution/knowledge-harness-0.3.0rc1/RELEASE.json';save(manifest,dict(source_identity='source',product=VERSION))
            value=dict(run_id=run,status='PASS_PORTABLE',source_identity='source',platform={'os':'Linux'},checks={n:dict(status='NOT_RUN' if n=='native' else 'PASS',returncode=0,artifacts={'runs/current/evidence.log':sha(e)}) for n in REQUIRED})
            def check(v,source='source'):save(folder/'run.json',v);return validate(v,source,root)
            check(value)
            for state in ('FAILED','IN_PROGRESS'):
                v=copy.deepcopy(value);v['status']=state
                with self.assertRaises(AssertionError):check(v)
            with self.assertRaises(AssertionError):check(value,'new code')
            v=copy.deepcopy(value);del v['checks']['application']
            with self.assertRaises(AssertionError):check(v)
            v=copy.deepcopy(value);v['checks']['rehearsal']['artifacts']={'runs/other/evidence.log':sha(e)}
            with self.assertRaises(AssertionError):check(v)
            save(folder/'run.json',value);e.write_text('tampered')
            with self.assertRaises(AssertionError):validate(value,'source',root)
            e.write_text('executed result');save(manifest,dict(source_identity='stale',product=VERSION))
            with self.assertRaises(AssertionError):check(value)
    def test_linux_pass_cannot_qualify_windows_or_stale_external_native_receipt(self):
        value=dict(status='PASS_PORTABLE',source_identity='s',wheel_sha256={'knowledge.whl':'h'},platform={'os':'Linux'},checks={n:dict(status='NOT_RUN' if n=='native' else 'PASS') for n in REQUIRED})
        self.assertEqual(qualification(value)['profiles']['windows-3.12-x64-ntfs-ps51']['verdict'],'NO_GO')
        native=dict(status='PASS',source_identity='s',wheel_sha256={'knowledge.whl':'h'},platform={'os':'Windows','filesystem':'NTFS','python':'3.12.14','shell':'Windows PowerShell 5.1','architecture':'AMD64'},required_checks={k:'PASS' for k in ('regressions','platform','offline-core','lifecycle','rehearsal','application','launchers')},ci={'commit':'test-commit','run_id':'test-run'})
        require_native(value,native)
        for field,new in (('source_identity','other'),('wheel_sha256',{'knowledge.whl':'other'}),('platform',{'os':'Linux','filesystem':'NTFS','python':'3.12.14','shell':'Windows PowerShell 5.1'})):
            bad=copy.deepcopy(native);bad[field]=new
            with self.assertRaises(AssertionError):require_native(value,bad)
        bad=copy.deepcopy(native);del bad['required_checks']['platform']
        with self.assertRaises(AssertionError):require_native(value,bad)
        bad=copy.deepcopy(native);bad['platform']['architecture']='ARM64'
        with self.assertRaises(AssertionError):require_native(value,bad)
