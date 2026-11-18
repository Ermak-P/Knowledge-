"""Actual checksum-pinned accepted P3 -> P4 -> same-root restored P3 code/data."""
import hashlib,json,os,subprocess,sys,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'reports/P3/runs/c72e6b4fcb41419cb5ff40a61a506466/distribution/knowledge-harness-0.3.0rc1.zip'
def main():
 assert hashlib.sha256(OLD.read_bytes()).hexdigest()=='cf108d6ba7b49b42c8a81831abd9f72cdc999552cbd500cbef07ada9b0349338'
 kit=Path(sys.argv[1]).absolute();out=Path(sys.argv[2]).absolute();out.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='p4-lifecycle-') as tmp:
  base=Path(tmp);prior=base/'prior';prior.mkdir()
  with zipfile.ZipFile(OLD) as z:z.extractall(prior)
  old=next(prior.rglob('install.py'));env=base/'runtime';py=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
  def call(label,args):
   p=subprocess.run([str(x) for x in args],cwd=base,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);(out/(label+'.log')).write_bytes(p.stdout);assert p.returncode==0,(label,p.stdout[-2000:]);return p.stdout
  call('accepted-install',[sys.executable,old,'install','--env',env]);call('dependencies',[py,'-m','pip','install','-r',ROOT/'requirements-dev.lock'])
  root=base/'project';root.mkdir();snapshot=base/'logical.json';backup=base/'backup.zip'
  script=base/'state.py';script.write_text('''import sys,json
from pathlib import Path
sys.path.insert(0,TESTS)
from p3_state_fixtures import rich,logical
from knowledge import maintenance as m
import knowledge,harness
root=Path(ROOT);snap=Path(SNAPSHOT);backup=Path(BACKUP)
if sys.argv[1]=='seed':
 assert knowledge.__version__==harness.__version__=='0.3.0rc1'
 rich(root);snap.write_text(json.dumps(logical(root)))
 p=m.preview(root,'backup',backup);m.apply(root,p['preview'],p['fingerprint'])
else:
 assert logical(root)==json.loads(snap.read_text())
 assert knowledge.__version__==harness.__version__==sys.argv[1]
 if sys.argv[1]=='0.4.0rc1':
  from knowledge.store import Store
  Store(root).recover();(root/'user.txt').write_text('KEEP')
  p=m.preview(root,'restore',archive=backup,recovery=root.parent/'replaced');m.apply(root,p['preview'],p['fingerprint'])
  assert logical(root)==json.loads(snap.read_text())
 else:assert (root/'user.txt').read_text()=='KEEP'
print('PASS '+sys.argv[1])
'''.replace('TESTS',repr(str(ROOT/'tests'))).replace('ROOT',repr(str(root))).replace('SNAPSHOT',repr(str(snapshot))).replace('BACKUP',repr(str(backup))))
  call('seed',[py,'-I',script,'seed']);call('p4-upgrade',[sys.executable,kit/'install.py','install','--env',env]);call('preserve-restore',[py,'-I',script,'0.4.0rc1'])
  call('remove-p4',[sys.executable,kit/'install.py','uninstall','--env',env]);(env/'knowledge-release-install.json').rename(base/'retained-p4-marker.json');call('rollback-install',[sys.executable,old,'install','--env',env,'--adopt']);call('rollback-state',[py,'-I',script,'0.3.0rc1'])
 (out/'result.json').write_text(json.dumps({'status':'PASS','accepted_archive_sha256':hashlib.sha256(OLD.read_bytes()).hexdigest(),'same_root':True})+'\n')
if __name__=='__main__':main()
