"""Retain and verify exact-source CI data, including failed attempts.

No downloaded artifact code is executed. Git is a transport for logs/manifests.
"""
import argparse,hashlib,json,re,subprocess,zipfile
from pathlib import Path,PurePosixPath


def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,default=Path('/workspace/Knowledge-'));p.add_argument('--commit',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--ref',default='FETCH_HEAD');p.add_argument('--source',type=Path);p.add_argument('--distribution',type=Path);a=p.parse_args()
    assert re.fullmatch('[a-f0-9]{40}',a.commit)
    def git(*args):return subprocess.check_output(['git',*args],cwd=a.repo)
    revision=git('rev-parse',a.ref).decode().strip();a.output.mkdir(parents=True,exist_ok=True)
    def read(path):return git('show',revision+':'+path)
    expected=json.loads(a.source.read_text()) if a.source else None
    platforms={}
    for profile in ('Linux','Windows'):
        prefix=a.commit+'/'+profile+'/';paths=git('ls-tree','-r','--name-only',revision,prefix).decode().splitlines()
        if not paths:continue
        out=a.output/profile;out.mkdir(exist_ok=True)
        receipt=json.loads(read(prefix+'receipt.json'));run=json.loads(read(prefix+'run/run.json'))
        assert receipt['commit']==run['commit']==a.commit
        assert run['source_identity']==receipt['source_identity']==hashlib.sha256(json.dumps(run['source'],sort_keys=True).encode()).hexdigest()
        if expected:assert run['source']==expected['source'] and run['source_identity']==expected['source_identity'] and expected['commit']==a.commit
        # Independent proof of all source bytes against the requested Git tree,
        # accounting for the repository's LF checkout normalization only.
        normalized=[]
        for name,wanted in run['source'].items():
            path=PurePosixPath(name);assert not path.is_absolute() and '..' not in path.parts
            raw=git('show',a.commit+':'+name)
            if hashlib.sha256(raw).hexdigest()!=wanted:
                assert hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()==wanted,name;normalized.append(name)
        for c in run['commands']:
            path=PurePosixPath(c['log']);assert len(path.parts)==1 and not path.is_absolute()
            raw=read(prefix+'run/'+c['log']);assert hashlib.sha256(raw).hexdigest()==c['sha256'];(out/c['log']).write_bytes(raw)
        for name,path in [('run.json','run/run.json'),('receipt.json','receipt.json'),('tests.json','run/tests.json')]:
            if prefix+path in paths:(out/name).write_bytes(read(prefix+path))
        tests=json.loads((out/'tests.json').read_text()) if (out/'tests.json').exists() else None
        if run['status'] in ('PASS_NATIVE','PASS_PORTABLE'):
            assert run['unchanged'] and tests['success'] and tests['failed']==tests['errors']==0
            assert all(c['returncode']==0 for c in run['commands']) and all(v=='PASS' for v in run['checks'].values())
        release=json.loads(read(prefix+'run/distribution/knowledge-harness-0.5.0rc1/RELEASE.json'))
        assert release['source_identity']==run['source_identity']
        for name,wanted in release['files'].items():
            path=PurePosixPath(name);assert not path.is_absolute() and '..' not in path.parts
            assert hashlib.sha256(read(prefix+'run/distribution/knowledge-harness-0.5.0rc1/'+name)).hexdigest()==wanted
        if a.distribution:
            local=json.loads((a.distribution/'RELEASE.json').read_text());assert release['files']==local['files'] and release['source_identity']==local['source_identity']
            with zipfile.ZipFile(a.distribution/'knowledge-harness-0.5.0rc1.zip') as archive:
                for name,wanted in local['files'].items():assert hashlib.sha256(archive.read(name)).hexdigest()==wanted
        (out/'RELEASE.json').write_bytes(read(prefix+'run/distribution/knowledge-harness-0.5.0rc1/RELEASE.json'))
        platforms[profile]=dict(status=run['status'],url=receipt['url'],tests={k:tests[k] for k in ('tests','passed','failed','errors','skipped')} if tests else None,commands=len(run['commands']),source_and_every_log_and_asset_hash_verified=True,checkout_normalized_files=normalized)
    value=dict(commit=a.commit,evidence_revision=revision,platforms=platforms,artifact_code_executed=False)
    (a.output/'validation.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value,indent=2))
if __name__=='__main__':main()
