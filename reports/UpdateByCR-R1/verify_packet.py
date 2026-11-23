"""Verify retained review bytes; never execute ZIP/CI artifact contents."""
import hashlib,io,json,subprocess,zipfile
from pathlib import Path,PurePosixPath


def main():
    root=Path(__file__).resolve().parent;expected=json.loads((root/'ARTIFACTS.json').read_text());actual={}
    for p in root.rglob('*'):
        if p.is_file() and p.name!='ARTIFACTS.json' and '__pycache__' not in p.parts:
            actual[p.relative_to(root).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    assert actual==expected,'missing, changed or unexpected review artifacts'
    source=json.loads((root/'source.json').read_text());repo=root.parents[1]
    assert source['source_identity']==hashlib.sha256(json.dumps(source['source'],sort_keys=True).encode()).hexdigest()
    for name,wanted in source['source'].items():
        raw=subprocess.check_output(['git','show',source['commit']+':'+name],cwd=repo)
        assert hashlib.sha256(raw).hexdigest()==wanted or hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()==wanted,name
    release=json.loads((root/'distribution/RELEASE.json').read_text());assert release['source_identity']==source['source_identity']
    installed=json.loads((root/'installed-bytes.json').read_text());assert installed['commit']==source['commit'] and installed['source_identity']==source['source_identity'] and installed['installed_outside_checkout']
    assert hashlib.sha256((root/'distribution/knowledge-harness-0.5.0rc1.zip').read_bytes()).hexdigest()==installed['zip_sha256']
    with zipfile.ZipFile(root/'distribution/knowledge-harness-0.5.0rc1.zip') as z:
        assert json.loads(z.read('RELEASE.json'))==release
        for name,wanted in release['files'].items():
            path=PurePosixPath(name);assert not path.is_absolute() and '..' not in path.parts
            assert hashlib.sha256(z.read(name)).hexdigest()==wanted,name
        found=set()
        for wheel in [n for n in release['files'] if n.endswith('.whl')]:
            with zipfile.ZipFile(io.BytesIO(z.read(wheel))) as inner:
                for name in set(inner.namelist()) & installed['installed_assets'].keys():
                    packed=inner.read(name);assert hashlib.sha256(packed).hexdigest()==installed['installed_assets'][name]
                    package=name.split('/')[0];original=subprocess.check_output(['git','show',source['commit']+':packages/'+package+'/src/'+name],cwd=repo)
                    assert original.replace(b'\r\n',b'\n')==packed;found.add(name)
        assert found==installed['installed_assets'].keys()
    probes=json.loads((root/'fixed-probes/result.json').read_text())
    assert probes['status']=='PASS' and probes['tests']==12 and probes['failures']==probes['errors']==0 and probes['harness_absent'] and probes['mcp_absent']
    assert probes['workflow_module_sha256']==installed['installed_assets']['knowledge/cr_workflow.py']
    ci=root/'ci/validation.json'
    if ci.exists():
        validation=json.loads(ci.read_text());assert validation['commit']==source['commit'] and set(validation['platforms'])=={'Linux','Windows'}
        for profile,status in [('Linux','PASS_PORTABLE'),('Windows','PASS_NATIVE')]:
            summary=validation['platforms'][profile];assert summary['status']==status and summary['source_and_every_log_and_asset_hash_verified']
            folder=root/'ci'/profile;run=json.loads((folder/'run.json').read_text());tests=json.loads((folder/'tests.json').read_text())
            assert run['commit']==source['commit'] and run['source_identity']==source['source_identity'] and run['source']==source['source'] and run['unchanged']
            assert run['status']==status and all(v=='PASS' for v in run['checks'].values()) and tests['success'] and tests['failed']==tests['errors']==0
            for command in run['commands']:
                assert command['returncode']==0 and hashlib.sha256((folder/command['log']).read_bytes()).hexdigest()==command['sha256']
            assert json.loads((folder/'RELEASE.json').read_text())==release
    print(json.dumps(dict(status='PASS',review_files=len(actual),source_files=len(source['source']),source_identity=source['source_identity'],artifact_code_executed=False)))
if __name__=='__main__':main()
