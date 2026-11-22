"""One installed, final-source-bound P4 qualification route on Linux and native Windows."""
import hashlib,json,os,platform,shutil,subprocess,sys,tempfile,time,uuid
from pathlib import Path
from build_p4 import VERSION
ROOT=Path(__file__).resolve().parents[1]
FOLDERS=('packages','scripts','tests','docs/P4','release/p4-kit','examples/p4','.github/workflows','inputs')
EXTRA=('tasks/Knowledge-Audit-Stages-1-2-Review-R1.md','tasks/Knowledge-Harness-Audit-Stages-1-2-Codex-Task.md','tasks/Knowledge-Harness-Persistent-Instructions-R2-Denial-Preservation-Codex-Task.md','tasks/Knowledge-Harness-Persistent-Instructions-R1-Fixes-Codex-Task.md','tasks/Knowledge-Harness-Persistent-Instructions-Codex-Task-1.md','tasks/Knowledge-Harness-Persistent-Instructions-Codex-Task.md','tasks/Harness-Automatic-Test-Discovery-Review-R1.md','tasks/Harness-Automatic-Test-Discovery-Codex-Task.md','requirements-dev.lock','.gitattributes','.gitignore','README.md','START-HERE.md','reports/P4/TASK.md','tasks/Knowledge-Harness-P4-Review-R1.md','tasks/Knowledge-Harness-P4-Review-R2.md','tasks/Knowledge-Harness-Integrated-Fixes-Codex-Task.md','reports/P4/runs/d68c9865460a4fcbab2bdbaaa466f072/distribution/knowledge-harness-0.4.0rc3.zip','reports/P3/runs/c72e6b4fcb41419cb5ff40a61a506466/distribution/knowledge-harness-0.3.0rc1.zip')
def source():
    paths=[p for folder in FOLDERS for p in (ROOT/folder).rglob('*')]+[ROOT/p for p in EXTRA]
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths)) if p.is_file() and not any(x in p.parts for x in ('__pycache__','build','dist')) and not any(x.endswith('.egg-info') for x in p.parts)}
def py_at(env):return env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
def save(p,v):
    tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8');os.replace(tmp,p)
def main():
    rid=uuid.uuid4().hex;out=ROOT/'reports/P4/runs'/rid;out.mkdir(parents=True)
    inputs=source();identity=hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest()
    state=dict(version=2,id=rid,product=VERSION,source=inputs,source_identity=identity,commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),checks={},commands=[],status='RUNNING',started=time.time(),platform=dict(os=platform.system(),python=sys.version,architecture=platform.machine(),shell='Windows PowerShell 5.1' if os.name=='nt' else 'bash'),native='EXECUTED' if os.name=='nt' else 'NOT_RUN')
    def persist():save(out/'run.json',state)
    def command(name,argv,cwd=ROOT):
        began=time.time();argv=[str(x) for x in argv]
        with (out/(name+'.log')).open('wb') as log:p=subprocess.run(argv,cwd=cwd,stdout=log,stderr=subprocess.STDOUT)
        state['commands'].append(dict(name=name,argv=argv,cwd=str(cwd),returncode=p.returncode,seconds=time.time()-began,log=name+'.log',sha256=hashlib.sha256((out/(name+'.log')).read_bytes()).hexdigest()));state['checks'][name]='PASS' if p.returncode==0 else 'FAIL';persist()
        if p.returncode:raise RuntimeError('qualification failed: '+name+'; see '+str(out/(name+'.log')))
    persist()
    try:
        command('distribution',[sys.executable,'-B',ROOT/'scripts/build_p4.py','--output',out/'distribution','--source-id',identity])
        kit=out/('distribution/knowledge-harness-'+VERSION)
        with tempfile.TemporaryDirectory(prefix='p4-installed-') as tmp:
            base=Path(tmp);transfer=base/'transferred-kit';shutil.copytree(kit,transfer);env=base/'runtime';py=py_at(env)
            command('install',[sys.executable,transfer/'install.py','install','--env',env],base)
            command('test-dependencies',[py,'-m','pip','install','-r',ROOT/'requirements-dev.lock'],base)
            driver=base/'regressions.py';driver.write_text('''import sys,unittest,json,os
from pathlib import Path
import harness,knowledge
assert Path(harness.__file__).is_relative_to(Path(sys.prefix)) and Path(knowledge.__file__).is_relative_to(Path(sys.prefix))
assert harness.__version__==knowledge.__version__==VERSION
sys.path.insert(0,TESTS)
def main():
 suite=unittest.defaultTestLoader.discover(TESTS)
 rows={}
 class Result(unittest.TextTestResult):
  def startTest(self,t):super().startTest(t);rows[t.id()]=dict(test=t.id(),status='RUNNING')
  def addSuccess(self,t):super().addSuccess(t);rows[t.id()]['status']='PASS'
  def addFailure(self,t,e):super().addFailure(t,e);rows[t.id()]['status']='FAIL'
  def addError(self,t,e):super().addError(t,e);rows[t.id()]['status']='ERROR'
  def addSkip(self,t,reason):super().addSkip(t,reason);rows[t.id()].update(status='SKIP',reason=reason)
  def addSubTest(self,t,sub,e):
   super().addSubTest(t,sub,e)
   if e:rows[t.id()]['status']='FAIL' if issubclass(e[0],t.failureException) else 'ERROR'
 r=unittest.TextTestRunner(verbosity=2,resultclass=Result).run(suite)
 rows=list(rows.values())
 valid_skips=all(os.name!='nt' and '.NativeWindowsSafety.' in t.id() for t,reason in r.skipped)
 value=dict(results=rows,run=__RUN_ID__,tests=r.testsRun,passed=sum(x['status']=='PASS' for x in rows),failed=sum(x['status']=='FAIL' for x in rows),errors=sum(x['status']=='ERROR' for x in rows),skipped=len(r.skipped),skip_reasons=[dict(test=t.id(),reason=reason) for t,reason in r.skipped],success=r.wasSuccessful() and r.testsRun>=199 and valid_skips)
 Path(RESULT).write_text(json.dumps(value,indent=2)+'\\n',encoding='utf-8')
 raise SystemExit(not value['success'])
if __name__=='__main__':main()

'''.replace('VERSION',repr(VERSION)).replace('TESTS',repr(str(ROOT/'tests'))).replace('__RUN_ID__',repr(rid)).replace('RESULT',repr(str(out/'tests.json'))),encoding='utf-8')
            compile(driver.read_text(encoding='utf-8'),str(driver),'exec')
            command('legacy-automatic-tests',[py,'-I','-X','utf8','-B',ROOT/'scripts/legacy_test_discovery.py',out/'legacy-automatic-tests'],base)
            command('regressions',[py,'-I','-X','utf8','-B',driver],base)
            command('accepted-p3-lifecycle-marked',[py,'-I','-X','utf8','-B',ROOT/'scripts/p4_lifecycle.py',kit,out/'lifecycle-marked'],base)
            command('accepted-p3-maintenance-recovery',[py,'-I','-X','utf8','-B',ROOT/'scripts/p4_lifecycle.py',kit,out/'lifecycle-pending','pending-marker'],base)
            command('accepted-p3-lifecycle-unmarked',[py,'-I','-X','utf8','-B',ROOT/'scripts/p4_lifecycle.py',kit,out/'lifecycle-unmarked','no-marker'],base)
            command('accepted-rc3-upgrade',[py,'-I','-X','utf8','-B',ROOT/'scripts/integrated_upgrade.py',kit,out/'rc3-upgrade'],base)
            command('comparison',[py,'-I','-X','utf8','-B',ROOT/'scripts/p4_evaluate.py',kit,out/'comparison'],base)
            command('benchmark-setup',[py,'-B',ROOT/'scripts/setup_benchmark.py'],base)
            command('automatic-tests',[py,'-I','-X','utf8','-B',ROOT/'scripts/automatic_test_discovery.py',out/'automatic-tests'],base)
            command('reviewed-rc3-baseline',[py,'-I','-X','utf8','-B',ROOT/'scripts/integrated_baseline.py',out/'reviewed-baseline'],base)
            command('public-init-budget',[py,'-I','-X','utf8','-B',ROOT/'scripts/integrated_budget.py',out/'public-init-budget'],base)
            command('transferred-kit-first-use',[py,'-I','-X','utf8','-B',ROOT/'scripts/integrated_kit.py',out/('distribution/knowledge-harness-'+VERSION+'.zip'),out/'first-use'],base)
            command('dotnet-application',[py,'-I','-X','utf8','-B',ROOT/'scripts/p4_application.py','--output',out/'application'],base)
            # Knowledge independence is exercised by this route, with no Harness/MCP install in its venv.
            independent=base/'knowledge-only'
            command('audit-stages12-delivery',[py,'-I','-X','utf8','-B',ROOT/'scripts/audit_stages12_trial.py','--output',out/'audit-stages12-delivery'],base)
            command('knowledge-only-install',[sys.executable,transfer/'install.py','install','--env',independent,'--profile','knowledge'],base)
            command('knowledge-only-smoke',[py_at(independent),'-I','-c','import knowledge,importlib.util;assert knowledge.__version__=='+repr(VERSION)+';assert importlib.util.find_spec("harness") is None;assert importlib.util.find_spec("mcp") is None;print("Independent core works")'],base)
            if os.name=='nt':
                command('native-launcher',[py,'-I','-X','utf8','-B',ROOT/'scripts/p4_native.py',kit,out/'native'],base)
                state['platform'].update(json.loads((out/'native/result.json').read_text()))
            command('doctor',[sys.executable,transfer/'install.py','doctor','--env',env],base)
            command('uninstall',[sys.executable,transfer/'install.py','uninstall','--env',env],base)
            command('reinstall',[sys.executable,transfer/'install.py','install','--env',env],base)
            command('reinstalled-doctor',[sys.executable,transfer/'install.py','doctor','--env',env],base)
        state['unchanged']=inputs==source()
        if not state['unchanged']:raise RuntimeError('qualification inputs changed during execution')
        state['status']='PASS_NATIVE' if os.name=='nt' else 'PASS_PORTABLE'
    except BaseException as error:
        state.update(status='FAILED',error=str(error),unchanged=inputs==source());raise
    finally:
        state['finished']=time.time();persist();save(ROOT/'reports/P4/latest.json',dict(run=rid,status=state['status'],commit=state['commit'],source_identity=identity));print(json.dumps(dict(run=rid,status=state['status'])),flush=True)
    return 0
if __name__=='__main__':raise SystemExit(main())
