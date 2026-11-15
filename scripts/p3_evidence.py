"""P3 source/package/run/CI authority; native qualification requires native receipts."""
import hashlib,json,os,platform,subprocess,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/P3'
REQUIRED=('setup','baseline','regressions','distribution','reproducibility','packaging','prior-upgrade','rehearsal','application','bounded','native')
VERSION='0.3.0rc1'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def sources(root=ROOT):
    paths=[root/n for n in ('.gitignore','.gitattributes','README.md','START-HERE.md','requirements-dev.lock')]
    for directory in ('packages','scripts','tests','tasks','inputs','examples','release','docs/P3','.github'):
        base=root/directory
        if not base.exists():continue
        paths.extend(p for p in base.rglob('*') if p.is_file() and p.suffix!='.pyc' and not any(x in ('__pycache__','build','dist') or x.endswith('.egg-info') for x in p.parts))
    return {p.relative_to(root).as_posix():sha(p) for p in sorted(set(paths))}
def identity():return digest(sources())
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.next');tmp.write_bytes((json.dumps(value,indent=2,ensure_ascii=False)+'\n').encode());tmp.replace(path)
def validate(value,source_id,out=OUT):
    assert value['status']=='PASS_PORTABLE','current run incomplete or failed'
    assert value['source_identity']==source_id,'stale source'
    assert value==json.loads((out/'runs'/value['run_id']/'run.json').read_text(encoding='utf-8')),'mixed current run'
    assert set(value['checks'])==set(REQUIRED),'missing checks'
    for name,c in value['checks'].items():
        if name=='native' and value['platform']['os']!='Windows':assert c['status']=='NOT_RUN'
        else:assert c['status']=='PASS' and c['returncode']==0,(name,'check not passed')
        assert c['artifacts'],'missing evidence'
        for rel,h in c['artifacts'].items():
            p=Path(rel);assert not p.is_absolute() and '..' not in p.parts and rel.startswith('runs/'+value['run_id']+'/'),'mixed artifacts'
            assert sha(out/p)==h,'changed artifact'
    manifest=json.loads((out/'runs'/value['run_id']/'distribution/knowledge-harness-0.3.0rc1/RELEASE.json').read_text(encoding='utf-8'))
    assert manifest['source_identity']==source_id and manifest['product']==VERSION
    return value

def validate_current():return validate(json.loads((OUT/'verification-summary.json').read_text(encoding='utf-8')),identity())
def qualification(value,native=None):
    linux=value['platform']['os']=='Linux' and value['status']=='PASS_PORTABLE' and all(c['status']=='PASS' for n,c in value['checks'].items() if n!='native')
    windows=False;reasons=['native Windows evidence not executed/collected for this exact source/package']
    if native:
        require_native(value,native);windows=native['status']=='PASS' and all(c=='PASS' for c in native['required_checks'].values());reasons=[] if windows else ['required native check did not pass']
    return dict(version=1,source_identity=value['source_identity'],implementation_review='READY_FOR_EXTERNAL_REVIEW' if value['status']=='PASS_PORTABLE' else 'NOT_READY',profiles={'linux-3.12-x64':{'verdict':'GO' if linux else 'NO_GO','scope':'tested standalone core plus optional MCP; synthetic HTTP decisions'},'windows-3.12-x64-ntfs-ps51':{'verdict':'GO' if windows else 'NO_GO','reasons':reasons}},live_model='NOT_RUN',OpenCode='NOT_RUN',production_migration='NOT_AUTHORIZED',external_acceptance='PENDING',publication='USER_CONTROLLED')
def require_native(value,native):
    assert native['source_identity']==value['source_identity'],'native source mismatch'
    assert native['platform']['os']=='Windows' and native['platform']['filesystem']=='NTFS','not native NTFS evidence'
    assert native['platform']['python'].startswith('3.12.') and native['platform']['shell']=='Windows PowerShell 5.1','wrong native runtime/shell'
    assert set(native['required_checks'])=={'regressions','platform','offline-core','lifecycle','rehearsal','application','launchers'},'incomplete native coverage'
    assert native['wheel_sha256']==value['wheel_sha256'],'native package mismatch'
    assert native.get('ci',{}).get('commit') and native['ci'].get('run_id'),'missing CI provenance'

class Attempt:
    def __init__(self):
        self.id=uuid.uuid4().hex;self.dir=OUT/'runs'/self.id;self.dir.mkdir(parents=True)
        for name in ('P3-review.zip','P3-review.zip.sha256','packet-check.json','ACCEPTANCE.json','QUALIFICATION.json','P3-REPORT.md'):
            p=OUT/name
            if p.exists():p.rename(self.dir/('previous-'+name))
        self.value=dict(version=1,run_id=self.id,status='IN_PROGRESS',source_identity=identity(),source_files=sources(),product=VERSION,commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),platform={'os':platform.system(),'python':platform.python_version(),'machine':platform.machine()},checks={k:{'status':'NOT_RUN'} for k in REQUIRED});self.persist()
    def persist(self):save(self.dir/'run.json',self.value);save(OUT/'verification-summary.json',self.value)
    def command(self,name,args,not_run=False):
        folder=self.dir/name;folder.mkdir(exist_ok=True);log=folder/'command.log';self.value['checks'][name]={'status':'IN_PROGRESS','command':[str(a) for a in args]};self.persist()
        # Keep an infrastructure hang from exhausting the whole CI job before
        # its always-run artifact upload/receipt steps can preserve diagnostics.
        timeout=600 if name=='regressions' else 900
        with log.open('w',encoding='utf-8') as out:
            try:
                p=subprocess.run([str(a) for a in args],cwd=ROOT,stdout=out,stderr=subprocess.STDOUT,timeout=timeout,env={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'})
            except subprocess.TimeoutExpired:
                out.write('\nVerification check exceeded its '+str(timeout)+' second bound; FAIL.\n');out.flush()
                p=subprocess.CompletedProcess(args,124)
        self.value['checks'][name].update(status='NOT_RUN' if not_run and p.returncode==0 else 'PASS' if p.returncode==0 else 'FAIL',returncode=p.returncode,artifacts={p.relative_to(OUT).as_posix():sha(p) for p in sorted(folder.rglob('*')) if p.is_file()})
        self.persist();assert p.returncode==0,log.read_text(encoding='utf-8')[-4000:];print(name+': '+self.value['checks'][name]['status'],flush=True)
    def finish(self,status):
        if status=='PASS_PORTABLE':
            assert self.value['source_identity']==identity(),'source changed during verification'
            assert all(c['status']=='PASS' or (n=='native' and self.value['platform']['os']!='Windows' and c['status']=='NOT_RUN') for n,c in self.value['checks'].items())
        self.value['status']=status;self.persist()
