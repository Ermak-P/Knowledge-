"""Follow the shipped first-use procedure using only an extracted ZIP and SDK."""
import argparse,hashlib,json,os,shutil,subprocess,sys,tempfile,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('zip',type=Path);p.add_argument('output',type=Path);a=p.parse_args();out=a.output.absolute();out.mkdir(parents=True,exist_ok=True);commands=[]
 sdk=Path(shutil.which('dotnet') or ROOT/'.local/dotnet/dotnet').absolute()
 with tempfile.TemporaryDirectory(prefix='integrated-first-use-') as tmp:
  base=Path(tmp);kit=base/'transferred';kit.mkdir()
  with zipfile.ZipFile(a.zip) as z:
   assert z.testzip() is None;z.extractall(kit)
  manifest=json.loads((kit/'RELEASE.json').read_text(encoding='utf-8'))
  for name,h in manifest['files'].items():assert hashlib.sha256((kit/name).read_bytes()).hexdigest()==h,name
  needed=['docs/USAGE.md','examples/runner.json','examples/task.json','examples/configure.py','examples/controlled_provider.py','examples/demo/Feature.cs','examples/demo/Program.cs','examples/demo/Project.csproj','examples/demo/global.json','examples/demo/test_feature.py','install.py','optional-mcp.lock']
  assert all((kit/n).is_file() for n in needed)
  def py(env):return env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
  def call(label,argv,cwd=base,expected=0):
   proc=subprocess.run([str(x) for x in argv],cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300);(out/(label+'.log')).write_bytes(proc.stdout);commands.append(dict(label=label,argv=[str(x) for x in argv],returncode=proc.returncode,log=label+'.log'));assert proc.returncode==expected,(label,proc.stdout[-2500:]);return proc.stdout
  independent=base/'knowledge-only';full=base/'full'
  call('install-knowledge',[sys.executable,kit/'install.py','install','--env',independent,'--profile','knowledge'])
  call('independent',[py(independent),'-I','-c','import knowledge,importlib.util;assert importlib.util.find_spec("harness") is None;assert importlib.util.find_spec("mcp") is None;print(knowledge.__version__)'])
  call('install-full',[sys.executable,kit/'install.py','install','--env',full,'--profile','full'])
  call('installed-imports',[py(full),'-I','-c','import harness,knowledge,sys;from pathlib import Path;assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (harness,knowledge));print(harness.__file__,knowledge.__file__)'])
  project=base/'disposable-demo';shutil.copytree(kit/'examples/demo',project)
  assert call('sdk-version',[sdk,'--version'],cwd=project).decode().strip()=='10.0.404'
  call('restore',[sdk,'restore',project/'Project.csproj','--disable-parallel'],cwd=project)
  ready=base/'endpoint';counts=base/'requests.json'
  with (out/'controlled-provider.log').open('wb') as log:
   provider=subprocess.Popen([str(py(full)),str(kit/'examples/controlled_provider.py'),'--port','0','--ready-file',str(ready),'--counts-file',str(counts)],cwd=base,stdout=log,stderr=subprocess.STDOUT)
   try:
    until=time.monotonic()+15
    while not ready.exists() and provider.poll() is None and time.monotonic()<until:time.sleep(.05)
    assert ready.exists(),'controlled provider failed to start'
    runner=base/'runner.json';call('adapt-template',[py(full),kit/'examples/configure.py','--python',py(full),'--dotnet',sdk,'--endpoint',ready.read_text(encoding='utf-8'),'--output',runner])
    call('configure',[py(full),'-I','-m','harness.run_cli','configure','--root',project,'--input',runner,'--init-knowledge'])
    result=json.loads(call('run',[py(full),'-I','-m','harness.run_cli','run','--root',project,'--input',kit/'examples/task.json']));assert result['ok'] and result['capture']['state']=='delivered'
    report=json.loads(call('status',[py(full),'-I','-m','harness.run_cli','status','--root',project,'--run-id',result['run_id']]));assert report['run']['gates']['test']['counts']['executed']==1 and report['run']['gates']['test']['ok'] is True and report['run']['gates']['review']['verdict']=='approve';assert report['metrics']['process_attempts']>=2
    knowledge=json.loads(call('candidates',[py(full),'-I','-m','knowledge.cli','export','--root',project]));assert knowledge['queue'] and not knowledge['records']['claims'];assert (project/'Feature.cs').read_text(encoding='utf-8')=='public static class Feature { public static string Value => "fixed"; }\n'
    assert len(report['run']['requests'])==json.loads(counts.read_text())['requests']
   finally:
    provider.terminate();provider.wait(timeout=10)
  value=dict(status='PASS',source_identity=manifest['source_identity'],product=manifest['product'],zip_sha256=hashlib.sha256(a.zip.read_bytes()).hexdigest(),outside_checkout=True,profiles=['knowledge','full'],files_resolved=needed,http_requests=len(report['run']['requests']),process_attempts=report['metrics']['process_attempts'],compiled_regression_passed=1,independent_review='approve',capture=result['capture'],canonical_claims=0,commands=commands)
 (out/'result.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');print(json.dumps(value))
if __name__=='__main__':main()
