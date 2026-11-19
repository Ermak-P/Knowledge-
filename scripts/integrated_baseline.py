"""Qualify failing observations on the exact checksum-pinned reviewed rc3 kit."""
import hashlib,json,os,subprocess,sys,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'reports/P4/runs/d68c9865460a4fcbab2bdbaaa466f072/distribution/knowledge-harness-0.4.0rc3.zip'
def main():
 out=Path(sys.argv[1]).absolute();out.mkdir(parents=True,exist_ok=True);assert hashlib.sha256(OLD.read_bytes()).hexdigest()=='2dfa6ebb450acfe7549197681c9091544e5e9e7f54214832c56c7eb3611f69ef'
 with tempfile.TemporaryDirectory(prefix='integrated-baseline-') as tmp:
  base=Path(tmp);kit=base/'rc3';kit.mkdir()
  with zipfile.ZipFile(OLD) as z:z.extractall(kit);members=z.namelist()
  env=base/'runtime';py=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
  for label,argv in [('install',[sys.executable,kit/'install.py','install','--env',env]),('probe',[py,'-I','-X','utf8','-B',ROOT/'tests/integrated_baseline_driver.py','--checkout',ROOT,'--output',out])]:
   with (out/(label+'.log')).open('wb') as log:proc=subprocess.run([str(x) for x in argv],cwd=base,stdout=log,stderr=subprocess.STDOUT)
   assert proc.returncode==0,(label,str(out/(label+'.log')))
  value=json.loads((out/'result.json').read_text(encoding='utf-8'));value['kit_missing_first_use_files']=[n for n in ['examples/runner.json','examples/task.json','examples/controlled_provider.py'] if n not in members];assert value['kit_missing_first_use_files'];(out/'result.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(dict(status='REPRODUCED',output=str(out))))
if __name__=='__main__':main()
