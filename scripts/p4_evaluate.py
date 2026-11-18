"""Synthetic HTTP benchmark against exact accepted P3 installed package."""
import json,os,subprocess,sys,tempfile,zipfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from p2_fixtures import FixtureProvider,http_provider,calls,final,project,configuration,task
from test_p4 import Decisions,p4task
from knowledge.util import loads
class Long:
 def __init__(self,inner):self.inner=inner;self.total=0
 def decide(self,b):
  s=loads(b['messages'][0]['content'])
  if s['runtime_role']=='Coding':
   self.total+=1
   if self.total<=8:return calls(('read',{'path':'Large.cs'}))
  return self.inner.decide(b)
def main():
 kit=Path(sys.argv[1]).absolute();out=Path(sys.argv[2]).absolute();out.mkdir(parents=True,exist_ok=True);rows=[]
 with tempfile.TemporaryDirectory(prefix='p4-evaluation-') as tmp:
  base=Path(tmp);old=base/'old';old.mkdir()
  archive=ROOT/'reports/P3/runs/c72e6b4fcb41419cb5ff40a61a506466/distribution/knowledge-harness-0.3.0rc1.zip'
  import hashlib
  assert hashlib.sha256(archive.read_bytes()).hexdigest()=='cf108d6ba7b49b42c8a81831abd9f72cdc999552cbd500cbef07ada9b0349338'
  with zipfile.ZipFile(archive) as z:z.extractall(old)
  oldkit=next(old.rglob('install.py')).parent
  for policy,bundle in [('P3',oldkit),('P4',kit)]:
   env=base/policy
   p=subprocess.run([sys.executable,str(bundle/'install.py'),'install','--env',str(env)],capture_output=True);assert p.returncode==0,p.stdout
   py=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
   subprocess.run([str(py),'-m','pip','install','-r',str(ROOT/'requirements-dev.lock')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
   for scenario in ('simple','pressure','failure'):
    for repeat in range(1 if scenario=='failure' else 3):
     root=project(base/(policy+scenario+str(repeat)));(root/'Large.cs').write_text('/* bounded diagnostic data '+('x'*5000)+' */\n')
     decider=FixtureProvider(repair=False) if policy=='P3' else Decisions(broken=scenario=='failure')
     if scenario=='failure' and policy=='P3':decider.desired='public class BrokenFeature {}\n'
     if scenario=='pressure':decider=Long(decider)
     with http_provider(decider) as endpoint:
      driver=base/'driver.py';c=configuration(endpoint);t=task() if policy=='P3' else p4task()
      driver.write_text('import json\nfrom harness.runtime import configure\nfrom harness.engine import start,status\nr='+repr(str(root))+'\nconfigure(r,'+repr(c)+',True)\nx=start(r,'+repr(t)+')\ns=status(r,x["run_id"])\nprint(json.dumps({"result":x,"run":s["run"],"metrics":s["metrics"]}))\n')
      p=subprocess.run([str(py),'-I',str(driver)],cwd=base,capture_output=True,text=True);assert p.returncode==0,p.stdout+p.stderr;v=json.loads(p.stdout)
     requests=v['run']['requests'];m=v['metrics'];row=dict(policy=policy,scenario=scenario,repeat=repeat,correct=v['result']['ok'],status=v['result']['status'],calls=m['requests'],input_bytes=sum(q['input_bytes'] for q in requests),max_coding=max((q['input_bytes'] for q in requests if q['role']=='Coding'),default=0),max_main=max(q['input_bytes'] for q in requests if q['role']=='Main'),reported_tokens=m['reported_tokens'],unknown_usage=m['unknown_usage_requests'],rotations=v['run'].get('p4',{}).get('rotations',0),elapsed=m['wall_seconds']);rows.append(row)
     (out/(policy+'-'+scenario+'-'+str(repeat)+'.json')).write_text(json.dumps(v,indent=2)+'\n')
 (out/'results.json').write_text(json.dumps({'evidence':'synthetic fixture usage, not live-model tokens','rows':rows},indent=2)+'\n')
if __name__=='__main__':main()
