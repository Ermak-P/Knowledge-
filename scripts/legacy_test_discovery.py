"""Installed R1 proof: exact metadata on both hosts, real mixed native CLI/MCP."""
import argparse,asyncio,hashlib,json,os,shutil,subprocess,sys,tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tests'))
from legacy_fixtures import MINIMAL,mixed
from automatic_fixtures import configuration,task,Decisions,PROJECTS,FEATURE,INITIAL
from p2_fixtures import http_provider,final
from harness import testing,runtime,engine,companion
from harness.tools import Broker
from knowledge.util import digest,KnowledgeError
from knowledge.store import Store

def save(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
def retain(root,run_id,out):
 report=engine.status(root,run_id);save(out/'status.json',report)
 for p in (root/'.harness/artifacts'/run_id).rglob('*'):
  if p.is_file():
   dest=out/'artifacts'/p.relative_to(root/'.harness/artifacts'/run_id);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
 return report

def main():
 parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);a=parser.parse_args();out=a.output.absolute();out.mkdir(parents=True,exist_ok=True);sdk=Path(shutil.which('dotnet') or ROOT/'.local/dotnet/dotnet').absolute()
 import harness,knowledge
 assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (harness,knowledge))
 with tempfile.TemporaryDirectory(prefix='legacy metadata Ω ') as tmp:
  base=Path(tmp);root=base/'project';root.mkdir();(root/'LegacyTests.csproj').write_text(MINIMAL,encoding='utf-8');(root/FEATURE).parent.mkdir(parents=True);(root/FEATURE).write_text(INITIAL,encoding='utf-8');c=configuration('http://127.0.0.1:1/v1/chat/completions',sdk,base/'dotnet-home',ROOT/'.local/nuget');c['recipes']['build']['argv'][2]='LegacyTests.csproj';runtime.configure(root,c)
  with patch.object(engine,'resume',return_value={'created':True}):engine.start(root,task())
  j=runtime.Journal(root);r=j.runs()[0];error=None
  with runtime.Lease(j) as lease:
   if os.name!='nt':
    try:testing.verify(j,c,r,lease,'work',1)
    except KnowledgeError as e:error=e.code
    assert error=='legacy-dotnet-framework-requires-native-windows' and not r['gates'][testing.GATE]['ok'],error
   else:
    gid='metadata-probe';r['automatic_tests']['generations'][gid]=dict(source=digest(r['source']),metadata_version=2,projects={'LegacyTests.csproj':dict(frameworks={})});b=Broker(j,c,r,lease)
    for phase in ('restore','inspect'):
     name=testing.register(j,r,gid,'LegacyTests.csproj',phase);answer=b.execute('Building','metadata-'+phase,'recipe',dict(name=name));assert answer['ok'],answer
    assert testing.resolve_frameworks(answer['properties'])[0][0]=='.NETFramework,Version=v4.7.1'
  report=retain(root,r['id'],out/'metadata');inspect=next(v['result']['properties'] for v in report['actions'].values() if v.get('result',{}).get('properties'));assert inspect['TargetFramework']==inspect['TargetFrameworks']=='' and inspect['TargetFrameworkVersion']=='v4.7.1';assert sorted(v['result']['automatic']['phase'] for v in report['actions'].values() if v.get('process_spec'))==['inspect','restore']
  save(out/'metadata/result.json',dict(status='PASS',actual_broker=True,properties=inspect,host_error=error,processes=report['metrics']['process_attempts']))
 if os.name!='nt':
  save(out/'result.json',dict(status='PASS_METADATA_NATIVE_REQUIRED',product=harness.__version__,metadata='PASS',mixed_native='NOT_RUN',reason='This host cannot execute .NET Framework; native CI is required.'));return
 from harness.platform import require_framework_runtime,system_environment
 prerequisites=dict(runtime=require_framework_runtime('v4.8'),reference_assemblies=str(Path(system_environment()['PROGRAMFILES(X86)'])/'Reference Assemblies/Microsoft/Framework/.NETFramework/v4.8'))
 if not (Path(prerequisites['reference_assemblies'])/'mscorlib.dll').is_file():
  save(out/'result.json',dict(status='NOT_RUN',error='native-net48-reference-assemblies-missing',prerequisites=prerequisites));raise RuntimeError('Native .NET Framework 4.8 Developer Pack is required; no retargeting/install performed')
 vswhere=Path(system_environment()['PROGRAMFILES(X86)'])/'Microsoft Visual Studio/Installer/vswhere.exe'
 if not vswhere.is_file():raise RuntimeError('Native Visual Studio Build Tools / vswhere is required')
 candidates=subprocess.check_output([str(vswhere),'-latest','-products','*','-requires','Microsoft.Component.MSBuild','-find','MSBuild/Current/Bin/MSBuild.exe'],text=True,encoding='utf-8').splitlines();assert len(candidates)==1,candidates;msbuild=Path(candidates[0]);assert msbuild.is_file()
 prerequisites.update(msbuild=str(msbuild),sdk='8.0.408',legacy_framework='v4.8')
 rows=[]
 for case in ('cli-recovery-repair','mcp'):
  with tempfile.TemporaryDirectory(prefix='mixed legacy Ω ') as tmp,http_provider(d:=Decisions(repair=case!='mcp')) as endpoint:
   base=Path(tmp);root=mixed(base/'project');c=configuration(endpoint,sdk,base/'dotnet-home',ROOT/'.local/nuget');c['dotnet']=str(sdk);c['recipes']['build']['argv']=[str(msbuild),'Suite.sln','-restore','-m:1','-p:UseSharedCompilation=false'];env={**os.environ,**c['recipes']['build']['env']};commands=[]
   def command(label,argv,expected=0):
    result=subprocess.run([str(x) for x in argv],cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=480);(out/(case+'-'+label+'.log')).write_bytes(result.stdout);commands.append(dict(label=label,argv=[str(x) for x in argv],returncode=result.returncode));assert result.returncode==expected,(label,result.stdout[-5000:]);return result.stdout
   command('solution',[sdk,'new','sln','--name','Suite']);command('mixed-projects',[sdk,'sln','Suite.sln','add','src/App/App.csproj',*PROJECTS]);cfg=base/'runner.json';cfg.write_text(json.dumps(c),encoding='utf-8');t=root/'task.json';t.write_text(json.dumps(task()),encoding='utf-8');command('configure',[sys.executable,'-I','-m','harness.run_cli','configure','--root',root,'--input',cfg,'--init-knowledge'])
   inspection=json.loads(command('inspect',[sys.executable,'-I','-m','harness.run_cli','discover-tests','--root',root]));assert inspection['count']==3
   if case!='mcp':
    command('interrupted',[sys.executable,'-I','-X','utf8','-B',ROOT/'tests/integrated_cli_worker.py','--die','legacy-build-receipt','--','run','--root',root,'--input',t],73);rid=runtime.Journal(root).runs()[0]['id'];result=json.loads(command('resume',[sys.executable,'-I','-m','harness.run_cli','resume','--root',root,'--run-id',rid]))
   else:
    plan=companion.preview(root,'task.json');companion.apply(root,plan['preview'],plan['fingerprint']);entry=json.loads((root/'opencode.json').read_text())['mcp']['servers']['harness_companion']
    async def execute():
     from mcp import ClientSession,StdioServerParameters
     from mcp.client.stdio import stdio_client
     async with stdio_client(StdioServerParameters(command=entry['command'][0],args=entry['command'][1:])) as (read,write):
      async with ClientSession(read,write,read_timeout_seconds=timedelta(seconds=900)) as session:
       await session.initialize();value=await session.call_tool('harness_run',dict(task_name='approved_task'));return json.loads(value.content[0].text)
    result=asyncio.run(execute())
   report=retain(root,result['run_id'],out/case);assert result['ok'],result;run=report['run'];gate=run['gates'][testing.GATE];assert gate['ok'] and gate['counts']==dict(executed=3,passed=3,failed=0,skipped=0)
   generations=run['automatic_tests']['generations'];legacy=gate['projects'][PROJECTS[2]]['frameworks'];assert list(legacy)==['.NETFramework,Version=v4.8'] and legacy['.NETFramework,Version=v4.8']['kind']=='net-framework'
   tests=[a for a in report['actions'].values() if a['tool']=='recipe' and a.get('result',{}).get('automatic',{}).get('phase')=='test'];native=[v for v in tests if v['result']['automatic']['project']==PROJECTS[2]]
   assert all(v['process_spec']['argv'][1]=='vstest' and not any(x.startswith('-p:TargetFramework=') or x=='--framework' for x in v['process_spec']['argv']) for v in native);artifacts=[v['result']['artifact']['path'] for v in tests];assert len(artifacts)==len(set(artifacts))==(6 if case!='mcp' else 3)
   if case!='mcp':
    assert len(generations)==2 and run['p4']['items'][0]['attempts']==2;failed=next(g for g in generations.values() if g['status']=='FAIL');assert sum(p['status']=='PASS' for p in failed['projects'].values())==2 and failed['projects'][PROJECTS[2]]['status']=='FAIL';assert any(v['result']['counts']['failed']==1 and v['result']['returncode']!=0 for v in native);assert report['metrics']['process_attempts']==26
   assert not Store(root).export()['records']['claims'] and Store(root).status()['queue'];rows.append(dict(case=case,status='PASS',counts=gate['counts'],generations=len(generations),unique_trx=len(artifacts),processes=report['metrics']['process_attempts'],commands=commands,legacy=legacy))
 save(out/'result.json',dict(status='PASS_NATIVE',product=harness.__version__,prerequisites=prerequisites,rows=rows));print(json.dumps(rows))
if __name__=='__main__':main()
