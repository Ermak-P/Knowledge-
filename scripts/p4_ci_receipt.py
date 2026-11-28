"""Publish compact source-bound annotated tags; raw outputs stay in Actions artifacts."""
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


def publish(summary,sha,layout,platform,repo=ROOT):
    """Retain exact-source receipts without recreating a service branch."""
    assert len(sha)==40 and all(c in '0123456789abcdef' for c in sha)
    assert layout in ('full','machine-fast') and platform in ('Linux','Windows')
    run_id=os.environ['GITHUB_RUN_ID'];attempt=os.environ.get('GITHUB_RUN_ATTEMPT','1')
    assert run_id.isdigit() and attempt.isdigit()
    tag='validation-'+layout+'-'+platform.lower()+'-'+sha+'-'+run_id+'-'+attempt
    ref='refs/tags/'+tag
    exists=subprocess.run(['git','rev-parse','--verify','--quiet',ref],cwd=repo,capture_output=True).returncode==0
    if exists:
        assert git('rev-parse',ref+'^{commit}',cwd=repo)==sha,'receipt tag source mismatch'
        assert json.loads(git('for-each-ref','--format=%(contents)',ref,cwd=repo))==summary,'receipt tag content mismatch'
    else:
        with tempfile.TemporaryDirectory(prefix='p4-ci-receipt-') as tmp:
            message=Path(tmp)/'receipt.json'
            message.write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n',encoding='utf-8')
            subprocess.run(['git','-c','user.name=github-actions[bot]','-c','user.email=41898282+github-actions[bot]@users.noreply.github.com','tag','-a',tag,'-F',str(message),sha],cwd=repo,check=True)
    # Push only this immutable tag; source branches and working files are untouched.
    subprocess.run(['git','push','origin',ref],cwd=repo,check=True)
    return tag


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
    tag=publish(compact(run,ledger,receipt),sha,layout,job)
    print(receipt['url']);print('Compact receipt:',tag)
if __name__=='__main__':main()
