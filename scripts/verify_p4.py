"""Fresh installed-package regression evidence; never overwrites P3 reports."""
import hashlib,json,os,subprocess,sys,tempfile,time,uuid,zipfile,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def source():
 return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('packages','scripts','tests','docs/P4','release/p4-kit','examples/p4') for p in (ROOT/folder).rglob('*') if p.is_file() and not any(x in p.parts for x in ('__pycache__','build')) and not any(x.endswith('.egg-info') for x in p.parts)}
def main():
 rid=uuid.uuid4().hex;out=ROOT/'reports/P4/runs'/rid;out.mkdir(parents=True);state=dict(version=1,id=rid,source=source(),checks={},status='running',started=time.time(),native='NOT_RUN' if os.name!='nt' else 'native-runtime');
 def save():(out/'run.json').write_text(json.dumps(state,indent=2)+'\n')
 def command(name,argv,cwd=ROOT):
  p=subprocess.run([str(x) for x in argv],cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);(out/(name+'.log')).write_bytes(p.stdout);state['checks'][name]=p.returncode;save();return p
 save()
 build=command('build',[sys.executable,'-B',ROOT/'scripts/build_p4.py','--output',out/'distribution','--source-id',hashlib.sha256(json.dumps(state['source'],sort_keys=True).encode()).hexdigest()]);assert build.returncode==0
 with tempfile.TemporaryDirectory(prefix='p4-installed-') as tmp:
  base=Path(tmp);kit=base/'kit';shutil.copytree(out/'distribution/knowledge-harness-0.4.0rc1',kit);env=base/'runtime'
  p=command('install',[sys.executable,kit/'install.py','install','--env',env],base);assert p.returncode==0
  py=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
  # Development/MCP dependencies are locked; local products remain the installed wheels.
  assert command('test-dependencies',[py,'-m','pip','install','-r',ROOT/'requirements-dev.lock'],base).returncode==0
  driver=base/'regressions.py';driver.write_text('import sys,unittest\nsys.path.insert(0,'+repr(str(ROOT/'tests'))+')\nsuite=unittest.defaultTestLoader.discover('+repr(str(ROOT/'tests'))+')\nr=unittest.TextTestRunner(verbosity=2).run(suite)\nraise SystemExit(not r.wasSuccessful())\n')
  command('regressions',[py,'-I','-B',driver],base)
  command('doctor',[sys.executable,kit/'install.py','doctor','--env',env],base)
  command('uninstall',[sys.executable,kit/'install.py','uninstall','--env',env],base)
 state['status']='PASS_PORTABLE' if all(v==0 for v in state['checks'].values()) else 'FAILED';state['finished']=time.time();state['unchanged']=state['source']==source();save()
 (ROOT/'reports/P4/latest.json').write_text(json.dumps({'run':rid,'status':state['status']})+'\n')
 print(json.dumps({'run':rid,'status':state['status']}));return 0 if state['status']=='PASS_PORTABLE' else 1
if __name__=='__main__':raise SystemExit(main())
