"""Collect Git-transported CI artifacts without API credentials or branch dependence."""
import argparse,json,subprocess,tarfile,tempfile
from pathlib import Path
from p3_evidence import ROOT,OUT,identity,validate,validate_current,require_native,sha,save

def main():
    p=argparse.ArgumentParser();p.add_argument('--commit',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();local=validate_current()
    assert len(a.commit)==40 and all(c in '0123456789abcdef' for c in a.commit)
    fetched=subprocess.run(['git','fetch','origin','refs/heads/p3-ci-evidence:refs/remotes/origin/p3-ci-evidence'],cwd=ROOT,capture_output=True,text=True)
    if fetched.returncode:
        save(a.output/'collection.json',dict(status='NOT_RUN',reason='CI evidence branch not available; Actions API access is separately unavailable/unauthorized',requested_commit=a.commit,source_identity=identity()));print('NOT_RUN: no native CI receipt collected.');return
    prefix=a.commit+'/Windows';content=subprocess.run(['git','show','origin/p3-ci-evidence:'+prefix+'/verification-summary.json'],cwd=ROOT,capture_output=True)
    if content.returncode:
        save(a.output/'collection.json',dict(status='NOT_RUN',reason='native job has not published this exact commit receipt',requested_commit=a.commit,source_identity=identity()));print('NOT_RUN: native receipt not yet present.');return
    ledger=json.loads(content.stdout);a.output.mkdir(parents=True,exist_ok=True);tar_path=a.output/'native-artifacts.tar';tar_path.write_bytes(subprocess.check_output(['git','archive','origin/p3-ci-evidence',prefix],cwd=ROOT))
    with tarfile.open(tar_path) as tar:
        assert all((m.isfile() or m.isdir()) and '..' not in Path(m.name).parts and not Path(m.name).is_absolute() for m in tar.getmembers()),'unsafe native artifact archive'
        tar.extractall(a.output/'collected',filter='data')
    native_root=a.output/'collected'/prefix
    if ledger['status']!='PASS_PORTABLE':
        save(a.output/'collection.json',dict(status='FAIL',reason='native CI verification failed; raw logs retained',requested_commit=a.commit,source_identity=ledger['source_identity'],native_root=str(native_root)));print('FAIL: native job receipt is failed; Windows NO_GO.');return
    validate(ledger,local['source_identity'],native_root)
    for path,expected in local['source_files'].items():
        import hashlib
        assert hashlib.sha256(subprocess.check_output(['git','show',a.commit+':'+path],cwd=ROOT)).hexdigest()==expected,'CI commit differs from current source: '+path
    receipt=json.loads((native_root/'runs'/ledger['run_id']/'native/native.json').read_text(encoding='utf-8'));assert receipt['ci']['commit']==a.commit
    require_native(local,receipt)
    save(a.output/'native.json',receipt);save(a.output/'collection.json',dict(status='PASS',requested_commit=a.commit,source_identity=identity(),wheel_sha256=receipt['wheel_sha256'],native_root=str(native_root),receipt_sha256=sha(a.output/'native.json'),native_summary_sha256=sha(native_root/'verification-summary.json'),evidence_commit=subprocess.check_output(['git','rev-parse','origin/p3-ci-evidence'],cwd=ROOT,text=True).strip()))
    print('PASS: exact-source/package native CI receipt and all artifact hashes verified.')
if __name__=='__main__':main()
