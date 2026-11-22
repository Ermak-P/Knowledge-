"""Verify retained review bytes; never execute ZIP/CI artifact contents."""
import hashlib,json,subprocess,zipfile
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
    with zipfile.ZipFile(root/'distribution/knowledge-harness-0.5.0rc1.zip') as z:
        assert json.loads(z.read('RELEASE.json'))==release
        for name,wanted in release['files'].items():
            path=PurePosixPath(name);assert not path.is_absolute() and '..' not in path.parts
            assert hashlib.sha256(z.read(name)).hexdigest()==wanted,name
    ci=root/'ci/validation.json'
    if ci.exists():assert json.loads(ci.read_text())['commit']==source['commit']
    print(json.dumps(dict(status='PASS',review_files=len(actual),source_files=len(source['source']),source_identity=source['source_identity'],artifact_code_executed=False)))
if __name__=='__main__':main()
