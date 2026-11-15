"""CI artifact transport on a dedicated branch; no source/app edits, no force push.

This supplements standard Actions artifacts for clients whose API route is blocked.
Only this task's synthetic test evidence is copied; no environment/credential dump.
"""
import json,os,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def git(*args,cwd=ROOT):return subprocess.check_output(['git',*args],cwd=cwd,text=True).strip()
def main():
    assert os.environ.get('GITHUB_ACTIONS')=='true','CI-only receipt transport'
    sha=os.environ['GITHUB_SHA'];job=os.environ['P3_CI_PLATFORM'];branch='p3-ci-evidence'
    evidence=ROOT/'reports/P3';summary=evidence/'verification-summary.json'
    if not summary.exists():print('No run ledger to retain; see failed Actions job logs.');return
    value=json.loads(summary.read_text(encoding='utf-8'));run=value['run_id']
    with tempfile.TemporaryDirectory(prefix='p3-ci-evidence-') as tmp:
        tmp=Path(tmp);repo=tmp/'receipt';repo.mkdir();subprocess.run(['git','init',str(repo)],check=True)
        subprocess.run(['git','remote','add','origin',git('remote','get-url','origin')],cwd=repo,check=True)
        # Delegate authentication to checkout's local config without reading or
        # copying credential/header values into commands, logs or artifacts.
        subprocess.run(['git','config','include.path',str(ROOT/'.git/config')],cwd=repo,check=True)
        existing=subprocess.run(['git','fetch','origin',branch],cwd=repo,capture_output=True)
        if existing.returncode==0:subprocess.run(['git','checkout','-b',branch,'FETCH_HEAD'],cwd=repo,check=True)
        else:subprocess.run(['git','checkout','--orphan',branch],cwd=repo,check=True)
        target=repo/sha/job;target.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(summary,target/'verification-summary.json');shutil.copytree(evidence/'runs'/run,target/'runs'/run,ignore=shutil.ignore_patterns('previous-*'))
        subprocess.run(['git','config','user.name','github-actions[bot]'],cwd=repo,check=True);subprocess.run(['git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com'],cwd=repo,check=True)
        subprocess.run(['git','add','.'],cwd=repo,check=True);subprocess.run(['git','commit','-m','Retain P3 '+job+' evidence for '+sha],cwd=repo,check=True)
        for attempt in range(4):
            pushed=subprocess.run(['git','push','origin','HEAD:refs/heads/'+branch],cwd=repo,capture_output=True)
            if pushed.returncode==0:print('Retained exact-source CI evidence:',sha,job);return
            subprocess.run(['git','fetch','origin',branch],cwd=repo,check=True);subprocess.run(['git','merge','--allow-unrelated-histories','--no-edit','FETCH_HEAD'],cwd=repo,check=True)
        raise RuntimeError('CI evidence branch could not be updated; standard artifacts remain authoritative')
if __name__=='__main__':main()
