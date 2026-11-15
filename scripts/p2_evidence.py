"""P2-only current-attempt source/artifact authority. Historical P1 files stay untouched."""
import hashlib,json,subprocess,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/P2'
REQUIRED=('setup','baseline','packaging','product-tests','evaluation','sessions','corrections')
DOCS=('P2-CONTRACTS.md','EXECUTION-AND-PERMISSIONS.md','CAPTURE-REPORT.md','RECOVERY-REPORT.md','ACCOUNTING-AND-COMPARISON.md','APPLICATION-EVALUATION.md','P2-R1-RESPONSE.md')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def sources(root=ROOT):
    paths=[root/p for p in ('.gitignore','README.md','START-HERE.md','requirements-dev.lock')]+[root/'reports/P2'/p for p in DOCS]
    for directory in ('packages','scripts','tests','tasks','inputs','examples'):
        paths.extend(p for p in (root/directory).rglob('*') if p.is_file() and not any(x in ('__pycache__','build','dist') or x.endswith('.egg-info') for x in p.parts) and p.suffix!='.pyc')
    return {str(p.relative_to(root)):sha(p) for p in sorted(set(paths))}
def fingerprint(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def identity():return fingerprint(sources())
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.next');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');tmp.replace(path)

def validate(value,current_identity,evidence_root):
    assert value['status']=='PASS','incomplete or failed attempt'
    assert value['source_identity']==current_identity,'stale source'
    assert value==json.loads((evidence_root/'runs'/value['run_id']/'run.json').read_text()),'mixed pointer/ledger'
    assert set(value['checks'])==set(REQUIRED),'missing check'
    for check in value['checks'].values():
        assert check['status']=='PASS' and check['returncode']==0 and check['artifacts'],'failed/unexecuted check'
        for rel,expected in check['artifacts'].items():
            p=Path(rel);assert not p.is_absolute() and '..' not in p.parts and rel.startswith('runs/'+value['run_id']+'/'),'mixed run artifact'
            assert sha(evidence_root/rel)==expected,'changed artifact'
    return value

def validate_current():return validate(json.loads((OUT/'verification-summary.json').read_text()),identity(),OUT)

class Attempt:
    def __init__(self):
        self.id=uuid.uuid4().hex;self.dir=OUT/'runs'/self.id;self.dir.mkdir(parents=True)
        # Old success pointers/archives cannot attest a new incomplete run.
        for name in ('P2-review.zip','P2-review.zip.sha256','packet-check.json','ACCEPTANCE.json','P2-REPORT.md'):
            path=OUT/name
            if path.exists():path.rename(self.dir/('previous-'+name))
        self.value=dict(version=1,run_id=self.id,status='IN_PROGRESS',source_identity=identity(),source_files=sources(),checks={k:{'status':'NOT_RUN'} for k in REQUIRED})
        self.persist()
    def persist(self):save(self.dir/'run.json',self.value);save(OUT/'verification-summary.json',self.value)
    def command(self,name,args):
        assert name in REQUIRED;folder=self.dir/name;folder.mkdir();log=folder/'command.log'
        self.value['checks'][name]={'status':'IN_PROGRESS','command':args};self.persist()
        with log.open('w') as stream:p=subprocess.run(args,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        self.value['checks'][name].update(status='PASS' if p.returncode==0 else 'FAIL',returncode=p.returncode,artifacts={str(p.relative_to(OUT)):sha(p) for p in sorted(folder.rglob('*')) if p.is_file()})
        self.persist();assert p.returncode==0,log.read_text()[-3000:];print(name+': PASS',flush=True)
    def finish(self,status):
        if status=='PASS':
            assert identity()==self.value['source_identity'],'source changed during verification'
            assert all(c['status']=='PASS' for c in self.value['checks'].values())
        self.value['status']=status;self.persist()
