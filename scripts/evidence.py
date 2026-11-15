"""Run-scoped evidence ledger. Caches may be reused; success assertions may not."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import uuid

REQUIRED=('packaging','product-tests','migration-evidence','benchmark-restore','benchmark-build',
          'benchmark-without-knowledge','benchmark-pipeline','benchmark-after-knowledge')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def sources(root):
    paths=[root/p for p in ('.gitignore','README.md','requirements-dev.lock','START-HERE.md')]
    for name in ('CONTRACTS.md','MIGRATION-REPORT.md','SOURCE-AUDIT.md','BENCHMARK-BASELINE.md','P0-R1-RESPONSE.md'):
        p=root/'reports/P0'/name
        if p.exists():paths.append(p)
    for folder in ('packages','scripts','tests','tasks','inputs'):
        paths.extend(p for p in (root/folder).rglob('*') if p.is_file() and p.suffix!='.pyc' and
            not any(x in ('__pycache__','build','dist') or x.endswith('.egg-info') for x in p.parts))
    return {str(p.relative_to(root)):sha(p) for p in sorted(set(paths))}


def identity(root):
    return hashlib.sha256(json.dumps(sources(root),sort_keys=True).encode()).hexdigest()


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.next')
    temp.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    temp.replace(path)


class Attempt:
    def __init__(self,root,required=REQUIRED):
        self.root=Path(root);self.out=self.root/'reports/P0'
        self.id=uuid.uuid4().hex;self.directory=self.out/'runs'/self.id
        self.directory.mkdir(parents=True)
        self.value={'run_id':self.id,'status':'IN_PROGRESS','source_identity':identity(self.root),
                    'checks':{n:{'status':'NOT_RUN'} for n in required}}
        # Invalidate the current success assertion BEFORE any verification command.
        self.persist()
        for name in ('P0-review.zip','P0-review.zip.sha256','ACCEPTANCE.json','packet-check.json','P0-REPORT.md','STATUS.md'):
            p=self.out/name
            if p.exists():shutil.move(p,self.directory/('previous-'+name))
        save(self.out/'ACCEPTANCE.json',[{'id':f'P0-A{i:02}','status':'NOT_RUN','run_id':self.id} for i in range(1,17)])
        (self.out/'STATUS.md').write_text(f'Verification {self.id}: IN_PROGRESS; acceptance not established.\n',encoding='utf-8')

    def persist(self):
        save(self.directory/'run.json',self.value)
        save(self.out/'verification-summary.json',self.value)

    def command(self,name,args,cwd=None,env=None,artifacts=()):
        path=self.out/(name+'.log')
        self.value['checks'][name]={'status':'IN_PROGRESS','command':list(map(str,args))}
        self.persist()
        for artifact in artifacts:
            Path(artifact).unlink(missing_ok=True)
        with path.open('w',encoding='utf-8') as f:
            p=subprocess.run(args,cwd=cwd or self.root,env=env,stdout=f,stderr=subprocess.STDOUT)
        check=self.value['checks'][name]
        check.update(status='PASS' if p.returncode==0 else 'FAIL',returncode=p.returncode,artifacts={})
        missing=[str(p) for p in artifacts if not Path(p).is_file()]
        if missing:check.update(status='FAIL',missing_artifacts=missing)
        for file in [path,*artifacts]:
            file=Path(file)
            if file.exists():
                rel=file.relative_to(self.out)
                dest=self.directory/'artifacts'/rel;dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(file,dest)
                check['artifacts'][str(rel)]=sha(file)
        self.persist()
        if missing:raise RuntimeError('Missing current-run artifacts: '+str(missing))
        if p.returncode:raise RuntimeError(f'{name} exited {p.returncode}: {path.read_text(encoding="utf-8")[-4000:]}')
        return check

    def finish(self,status,**fields):
        if status=='PASS':
            assert identity(self.root)==self.value['source_identity'],'Source changed during verification'
            assert all(c['status']=='PASS' for c in self.value['checks'].values())
        self.value.update(status=status,**fields);self.persist()
        (self.out/'STATUS.md').write_text(f'Verification {self.id}: {status}. See matching run ledger; external acceptance is not asserted.\n',encoding='utf-8')


def validate_current(root,required=REQUIRED):
    root=Path(root);out=root/'reports/P0'
    value=json.loads((out/'verification-summary.json').read_text(encoding='utf-8'))
    assert value['status']=='PASS','Current verification is not completed successfully'
    directory=out/'runs'/value['run_id']
    assert value==json.loads((directory/'run.json').read_text(encoding='utf-8')),'Mixed run pointer/ledger'
    assert value['source_identity']==identity(root),'Source changed after verification'
    assert set(value['checks'])==set(required),'Incomplete required checks'
    for name,check in value['checks'].items():
        assert check['status']=='PASS' and check['returncode']==0,(name,check)
        assert check['artifacts'],'Missing evidence'
        for rel,digest in check['artifacts'].items():
            assert sha(out/rel)==digest and sha(directory/'artifacts'/rel)==digest,('Mixed or changed evidence',rel)
    return value
