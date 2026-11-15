"""P1 run identity, strict evidence gate, never reuse another run's PASS."""
import hashlib
import json
from pathlib import Path
import subprocess
import uuid

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/P1'
REQUIRED=('packaging','product-tests','evaluation')


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sources(root=ROOT):
    files=[root/p for p in ('.gitignore','README.md','START-HERE.md','requirements-dev.lock','reports/P1/P1-CONTRACTS.md')]
    for folder in ('packages','scripts','tests','tasks','inputs'):
        files.extend(p for p in (root/folder).rglob('*') if p.is_file() and p.suffix!='.pyc' and not any(x in ('__pycache__','build','dist') or x.endswith('.egg-info') for x in p.parts))
    return {str(p.relative_to(root)):sha(p) for p in sorted(set(files))}


def identity(root=ROOT):return hashlib.sha256(json.dumps(sources(root),sort_keys=True).encode()).hexdigest()


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.next');tmp.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');tmp.replace(path)


class Attempt:
    def __init__(self):
        self.id=uuid.uuid4().hex;self.dir=OUT/'runs'/self.id;self.dir.mkdir(parents=True)
        self.value=dict(run_id=self.id,status='IN_PROGRESS',source_identity=identity(),source_files=sources(),checks={n:{'status':'NOT_RUN'} for n in REQUIRED})
        # Prior packet is no longer a statement about current verification.
        for name in ('P1-review.zip','P1-review.zip.sha256','packet-check.json','ACCEPTANCE.json'):
            p=OUT/name
            if p.exists():p.rename(self.dir/('previous-'+name))
        self.persist()
    def persist(self):
        save(self.dir/'run.json',self.value);save(OUT/'verification-summary.json',self.value)
        save(OUT/'STATUS.json',dict(phase='verification',run_id=self.id,status=self.value['status']))
    def command(self,name,args,artifacts=()):
        log=self.dir/(name+'.log');self.value['checks'][name]=dict(status='IN_PROGRESS',command=args);self.persist()
        with log.open('w') as out:p=subprocess.run(args,cwd=ROOT,stdout=out,stderr=subprocess.STDOUT)
        result=self.value['checks'][name];result.update(status='PASS' if p.returncode==0 else 'FAIL',returncode=p.returncode,artifacts={})
        for path in [log,*artifacts]:
            assert Path(path).is_file(),str(path)
            result['artifacts'][str(Path(path).relative_to(OUT))]=sha(path)
        self.persist();assert p.returncode==0,log.read_text()[-6000:]
        print(name+': PASS',flush=True)
    def finish(self,status):
        if status=='PASS':
            assert identity()==self.value['source_identity']
            assert all(c['status']=='PASS' for c in self.value['checks'].values())
        self.value['status']=status;self.persist()


def validate_current():
    value=json.loads((OUT/'verification-summary.json').read_text())
    assert value['status']=='PASS','Current attempt is incomplete or failed'
    assert value['source_identity']==identity(),'Source changed after verification'
    assert value==json.loads((OUT/'runs'/value['run_id']/'run.json').read_text()),'Mixed run pointer'
    assert set(value['checks'])==set(REQUIRED)
    for check in value['checks'].values():
        assert check['status']=='PASS' and check['returncode']==0 and check['artifacts']
        for rel,expected in check['artifacts'].items():
            assert rel.startswith('runs/'+value['run_id']+'/'),'Mixed run artifacts'
            assert sha(OUT/rel)==expected,'Changed/missing artifact'
    return value
