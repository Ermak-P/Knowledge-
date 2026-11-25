"""Publish compact source-bound receipts only; raw outputs stay in Actions artifacts."""
import hashlib,json,os,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def git(*args,cwd=ROOT):return subprocess.check_output(['git',*args],cwd=cwd,text=True).strip()
def compact(run,ledger,receipt):
    """Read structured summaries, never copy logs, packages or artifact code."""
    result=dict(receipt,checks=ledger['checks'],source=ledger['source'],unchanged=ledger.get('unchanged'),
                commands=[{k:c[k] for k in ('name','returncode','seconds','sha256')} for c in ledger['commands']],
                artifact_name=('machine-'+receipt['platform']) if receipt['qualification']=='machine-fast' else ('p4-'+('windows-2022' if receipt['platform']=='Windows' else 'ubuntu-24.04')),
                raw_outputs='Actions Artifacts; receipt is not raw-log or package verification')
    for name in ('tests.json','machine-tests.json'):
        path=run/name
        if path.is_file():
            value=json.loads(path.read_text(encoding='utf-8'))
            result['tests']={k:value[k] for k in ('tests','passed','failed','errors','skipped','success','skip_reasons') if k in value}
            result['tests']['nonpassing']=[r for r in value.get('results',[]) if r['status'] not in ('PASS','SKIP')]
    installer=run/'machine-installer/result.json'
    if installer.is_file():
        value=json.loads(installer.read_text(encoding='utf-8'));result['installer']={k:value[k] for k in ('ok','checks') if k in value}
    native=run/'machine-native/result.json'
    if native.is_file():
        value=json.loads(native.read_text(encoding='utf-8'));result['native']={k:value[k] for k in ('ok','checks','status') if k in value}
    return result


def main():
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    assert os.environ.get('GITHUB_EVENT_NAME') in ('push','workflow_dispatch'),'PR validation cannot publish evidence'
    assert os.environ.get('GITHUB_REPOSITORY')=='Ermak-P/Knowledge-' and os.environ.get('GITHUB_REF') in ('refs/heads/main','refs/heads/codex/integrated-fixes','refs/heads/codex/automatic-test-discovery','refs/heads/codex/persistent-instructions','refs/heads/codex/audit-stages-1-2','refs/heads/codex/sqlite-optimization','refs/heads/codex/update-by-cr','refs/heads/codex/automatic-installer','refs/heads/codex/core-reliability-fix','refs/heads/codex/knowledge-plan-deduplication-recovery','refs/heads/codex/knowledge-confluence-integration'),'untrusted publication ref'
    assert os.environ.get('GITHUB_EVENT_NAME') in ('push','workflow_dispatch') and os.environ.get('GITHUB_REPOSITORY')=='Ermak-P/Knowledge-' and os.environ.get('GITHUB_REF') in ('refs/heads/main','refs/heads/codex/integrated-fixes','refs/heads/codex/automatic-test-discovery','refs/heads/codex/persistent-instructions','refs/heads/codex/audit-stages-1-2','refs/heads/codex/sqlite-optimization','refs/heads/codex/update-by-cr','refs/heads/codex/automatic-installer','refs/heads/codex/core-reliability-fix','refs/heads/codex/knowledge-plan-deduplication-recovery','refs/heads/codex/knowledge-confluence-integration'),'untrusted evidence publication context'
    layout=os.environ.get('P4_CI_LAYOUT','full');assert layout in ('full','machine-fast'),'untrusted ledger layout'
    reports=ROOT/('reports/AutomaticInstaller-fast' if layout=='machine-fast' else 'reports/P4')
    latest=reports/'latest.json'
    if not latest.exists():raise RuntimeError('No qualification ledger; inspect failed Actions job')
    index=json.loads(latest.read_text());rid=index['run'];run=reports/'runs'/rid;ledger=json.loads((run/'run.json').read_text());sha=os.environ.get('P4_CI_EXPECTED_COMMIT') or os.environ['GITHUB_SHA'];job=os.environ['P4_CI_PLATFORM']
    if sha!=os.environ['GITHUB_SHA']:
        assert os.environ['GITHUB_EVENT_NAME']=='workflow_dispatch' and os.environ.get('P4_CI_PR','').isdigit(),'only an exact PR dispatch may publish its merge revision'
    assert ledger['commit']==sha and ledger['platform']['os']==job
    assert ledger['source_identity']==hashlib.sha256(json.dumps(ledger['source'],sort_keys=True).encode()).hexdigest()
    receipt=dict(qualification=layout,commit=sha,platform=job,run=rid,source_identity=ledger['source_identity'],status=ledger['status'],url='https://github.com/'+os.environ['GITHUB_REPOSITORY']+'/actions/runs/'+os.environ['GITHUB_RUN_ID'],job=os.environ['GITHUB_JOB'],event=os.environ['GITHUB_EVENT_NAME'],pull_request=os.environ.get('P4_CI_PR') or None,workflow_revision=os.environ['GITHUB_SHA'])
    with tempfile.TemporaryDirectory(prefix='p4-ci-receipt-') as tmp:
        repo=Path(tmp)/'receipt';repo.mkdir();subprocess.run(['git','init',str(repo)],check=True)
        subprocess.run(['git','remote','add','origin',git('remote','get-url','origin')],cwd=repo,check=True)
        subprocess.run(['git','config','include.path',str(ROOT/'.git/config')],cwd=repo,check=True)
        for key,value in [('core.longpaths','true'),('core.autocrlf','false'),('user.name','github-actions[bot]'),('user.email','41898282+github-actions[bot]@users.noreply.github.com')]:subprocess.run(['git','config',key,value],cwd=repo,check=True)
        branch='knowledge-validation-receipts';fetch=subprocess.run(['git','fetch','origin',branch],cwd=repo,capture_output=True)
        subprocess.run(['git','checkout','-b',branch,'FETCH_HEAD'] if fetch.returncode==0 else ['git','checkout','--orphan',branch],cwd=repo,check=True)
        target=repo/sha/layout/job/rid
        target.mkdir(parents=True,exist_ok=True)
        summary=compact(run,ledger,receipt)
        (target/'receipt.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
        subprocess.run(['git','add','.'],cwd=repo,check=True)
        if subprocess.run(['git','diff','--cached','--quiet'],cwd=repo).returncode==0:
            print('This exact compact receipt is already retained');return
        subprocess.run(['git','commit','-m','Record compact '+layout+' '+job+' validation for '+sha],cwd=repo,check=True)
        for _ in range(4):
            if subprocess.run(['git','push','origin','HEAD:refs/heads/'+branch],cwd=repo,capture_output=True).returncode==0:print(receipt['url']);return
            subprocess.run(['git','fetch','origin',branch],cwd=repo,check=True);subprocess.run(['git','merge','--allow-unrelated-histories','--no-edit','FETCH_HEAD'],cwd=repo,check=True)
        raise RuntimeError('Cannot publish compact receipt; Actions artifacts remain available')
if __name__=='__main__':main()
