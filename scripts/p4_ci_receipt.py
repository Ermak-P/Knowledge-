"""Native receipt transport using the accepted branch-scoped Git evidence mechanism."""
import json,os,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def git(*args,cwd=ROOT):return subprocess.check_output(['git',*args],cwd=cwd,text=True).strip()
def main():
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    latest=ROOT/'reports/P4/latest.json'
    if not latest.exists():raise RuntimeError('No qualification ledger; inspect failed Actions job')
    index=json.loads(latest.read_text());rid=index['run'];run=ROOT/'reports/P4/runs'/rid;ledger=json.loads((run/'run.json').read_text());sha=os.environ['GITHUB_SHA'];job=os.environ['P4_CI_PLATFORM']
    assert ledger['commit']==sha and ledger['platform']['os']==job
    receipt=dict(commit=sha,platform=job,run=rid,source_identity=ledger['source_identity'],status=ledger['status'],url='https://github.com/'+os.environ['GITHUB_REPOSITORY']+'/actions/runs/'+os.environ['GITHUB_RUN_ID'],job=os.environ['GITHUB_JOB'])
    with tempfile.TemporaryDirectory(prefix='p4-ci-receipt-') as tmp:
        repo=Path(tmp)/'receipt';repo.mkdir();subprocess.run(['git','init',str(repo)],check=True)
        subprocess.run(['git','remote','add','origin',git('remote','get-url','origin')],cwd=repo,check=True)
        subprocess.run(['git','config','include.path',str(ROOT/'.git/config')],cwd=repo,check=True)
        for key,value in [('core.longpaths','true'),('core.autocrlf','false'),('user.name','github-actions[bot]'),('user.email','41898282+github-actions[bot]@users.noreply.github.com')]:subprocess.run(['git','config',key,value],cwd=repo,check=True)
        branch='p4-ci-evidence';fetch=subprocess.run(['git','fetch','origin',branch],cwd=repo,capture_output=True)
        subprocess.run(['git','checkout','-b',branch,'FETCH_HEAD'] if fetch.returncode==0 else ['git','checkout','--orphan',branch],cwd=repo,check=True)
        (repo/'.gitattributes').write_bytes(b'* -text\n');target=repo/sha/job;target.mkdir(parents=True,exist_ok=True)
        (target/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');shutil.copytree(run,target/'run')
        subprocess.run(['git','add','.'],cwd=repo,check=True)
        subprocess.run(['git','commit','-m','Retain P4 '+job+' evidence for '+sha],cwd=repo,check=True)
        for _ in range(4):
            if subprocess.run(['git','push','origin','HEAD:refs/heads/'+branch],cwd=repo,capture_output=True).returncode==0:print(receipt['url']);return
            subprocess.run(['git','fetch','origin',branch],cwd=repo,check=True);subprocess.run(['git','merge','--allow-unrelated-histories','--no-edit','FETCH_HEAD'],cwd=repo,check=True)
        raise RuntimeError('Cannot retain evidence branch; standard Actions artifacts still available')
if __name__=='__main__':main()
