"""Actual SDK/CLI automatic-suite enforcement; provider is a protocol double."""
import json,os,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path('/workspace/Knowledge-');sys.path.insert(0,str(ROOT/'tests'))
from automatic_fixtures import create,configuration,task,Decisions,PROJECTS
from p2_fixtures import http_provider
from test_persistent_instructions import ingress,binding
from harness.runtime import configure,Journal
from harness.engine import status
from knowledge import operations as op
out=Path('/tmp/persistent-causal-auto-link');out.mkdir(exist_ok=True)
assert Path(op.__file__).is_relative_to(Path(sys.prefix))
sdk=ROOT/'.local/dotnet/dotnet'
with tempfile.TemporaryDirectory(prefix='remembered auto suite ') as tmp,http_provider(Decisions()) as endpoint:
 base=Path(tmp);root=create(base/'project');shared=base/'home/.local/share/knowledge'
 c=configuration(endpoint,sdk,base/'dotnet-home',ROOT/'.local/nuget');c['capture']='off'
 p={'id':'suite_guard','check':{'argv':[sys.executable,'-I','-c','from pathlib import Path; p=Path(".memory-guard"); p.write_text(p.read_text()+"checked\\n" if p.exists() else "checked\\n")'],'timeout':3},'attempts':0,'deadline':4,'interval':.1}
 c['memory']={'shared_root':str(shared),'teaching_mode':'catalog','bindings':[binding('suite guard','dependency','suite_guard',{'adapter':'check','procedure':p})],
  'allowed_procedures':[p],'requirements':[{'trigger':{'tool':'recipe','name':'@automatic-tests/*'},'suite':PROJECTS[1],'dependency':'suite_guard'}]}
 env={**os.environ,**c['recipes']['build']['env']}
 def command(name,args):
  r=subprocess.run([str(x) for x in args],cwd=root,env=env,capture_output=True,timeout=300)
  (out/(name+'.log')).write_bytes(r.stdout+r.stderr);assert r.returncode==0,(name,r.stdout[-2000:],r.stderr[-1000:]);return r.stdout
 command('solution',[sdk,'new','sln','--format','sln','--name','Suite'])
 command('members',[sdk,'sln','Suite.sln','add','src/App/App.csproj',*PROJECTS[:2]])
 configure(root,c)
 taught=ingress(root,'Remember for all projects: apply suite guard before the declared dependent suite.')
 assert taught['saved'] and taught['executable'],taught
 tf=root/'.harness/task.json';tf.write_text(json.dumps(task()))
 began=time.monotonic();result=json.loads(command('ordinary-run',[sys.executable,'-I','-m','harness.run_cli','run','--root',root,'--input',tf]));seconds=time.monotonic()-began
 report=status(root,result['run_id']);assert result['ok'] and report['run']['gates']['@automatic-tests']['ok']
 actions=Journal(root).actions(result['run_id']);owned=[a for a in actions.values() if a.get('memory_parent')]
 assert len(owned)==1 and (root/'.memory-guard').read_text()=='checked\n',len(owned)
 links=[link for a in actions.values() for trace in a.get('memory_traces',[]) for link in trace.get('dependency_links',[])]
 assert len(links)==1 and links[0]['suite']==PROJECTS[1] and links[0]['source']=='verified-test-inventory',links
 assert all(not a.get('memory_traces') for a in owned),'recursive lookup'
 (out/'run.json').write_text(json.dumps({'run':report['run'],'actions':actions},indent=2)+'\n')
 (out/'result.json').write_text(json.dumps({'ok':True,'type':'actual installed CLI, SDK10, automatic inventory, TRX, owned check; model protocol double',
  'record':{'id':taught['id'],'revision':taught['revision']},'goal':task()['goal'],'declared_suite':PROJECTS[1],
  'all_test_counts':report['run']['gates']['@automatic-tests']['counts'],'guard_executions':len(owned),'links':links,'recursive_lookup':False,
  'seconds':seconds,'model_evidence':'test-double','model_tokens':None},indent=2)+'\n')
print(json.dumps({'ok':True,'output':str(out)}))
