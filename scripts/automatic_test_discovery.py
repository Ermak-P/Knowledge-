"""AT-02/03/04/08/09/11: actual installed CLI/MCP, SDK, TRX, repair and recovery."""
import argparse,asyncio,hashlib,json,os,shutil,subprocess,sys,tempfile
from datetime import timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tests'))
from automatic_fixtures import create,configuration,task,Decisions,PROJECTS,FEATURE
from p2_fixtures import http_provider
from harness.runtime import configure,Journal
from harness.engine import status
from harness import companion
from knowledge.store import Store

def main():
 p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--case',choices=['cli','mcp','recovery','tamper','all'],default='all');a=p.parse_args();out=a.output.absolute();out.mkdir(parents=True,exist_ok=True);sdk=Path(shutil.which('dotnet') or ROOT/'.local/dotnet/dotnet').absolute();rows=[]
 import harness,knowledge
 assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (harness,knowledge))
 for case in (['cli','mcp','recovery','tamper'] if a.case=='all' else [a.case]):
  with tempfile.TemporaryDirectory(prefix='auto tests Ω ') as tmp,http_provider(d:=Decisions(repair=case=='cli')) as endpoint:
   base=Path(tmp);root=create(base/'project',multi=case=='cli');c=configuration(endpoint,sdk,base/'dotnet-home',ROOT/'.local/nuget');env={**os.environ,**c['recipes']['build']['env']};commands=[]
   def command(label,argv,expected=0):
    proc=subprocess.run([str(x) for x in argv],cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300);(out/(case+'-'+label+'.log')).write_bytes(proc.stdout);commands.append(dict(label=label,argv=[str(x) for x in argv],returncode=proc.returncode));assert proc.returncode==expected,(label,proc.stdout[-3000:]);return proc.stdout
   command('new-solution',[sdk,'new','sln','--format','sln','--name','Suite']);command('solution-projects',[sdk,'sln','Suite.sln','add','src/App/App.csproj',*PROJECTS[:2]])
   configfile=base/'runner.json';configfile.write_text(json.dumps(c),encoding='utf-8');taskfile=root/'task.json';taskfile.write_text(json.dumps(task()),encoding='utf-8')
   command('configure',[sys.executable,'-I','-m','harness.run_cli','configure','--root',root,'--input',configfile,'--init-knowledge'])
   inspection=json.loads(command('inspect',[sys.executable,'-I','-m','harness.run_cli','discover-tests','--root',root]));assert inspection['ok'] and inspection['count']==3
   if case=='tamper':
    def remove_report():
     p=next((root/'.harness/artifacts').rglob('*.trx'));p.unlink()
    d.on_review=remove_report
    result=json.loads(command('run-corrupt',[sys.executable,'-I','-m','harness.run_cli','run','--root',root,'--input',taskfile],1));report=status(root,result['run_id']);assert result['error']=='automatic-test-artifact-changed' and not report['run']['gates']['@automatic-tests']['ok'] and result['execution']!='passed';(out/'tamper-status.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');rows.append(dict(case='tamper',status='PASS',error=result['error'],false_success=False));continue
   if case=='recovery':
    command('interrupted',[sys.executable,'-I','-X','utf8','-B',ROOT/'tests/integrated_cli_worker.py','--die','automatic-verifier-receipt','--','run','--root',root,'--input',taskfile],73)
    j=Journal(root);pending=j.runs()[0];before=len(d.requests);added=root/'AddedTests.csproj';added.write_text('<Project/>',encoding='utf-8')
    refused=json.loads(command('drift-resume',[sys.executable,'-I','-m','harness.run_cli','resume','--root',root,'--run-id',pending['id']],1));assert refused['error']=='test-inventory-changed-revalidation-required' and len(d.requests)==before;added.unlink()
    children=[subprocess.Popen([sys.executable,'-I','-X','utf8','-B','-m','harness.run_cli','resume','--root',str(root),'--run-id',pending['id']],stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(2)]
    competing=[]
    for child in children:
     stdout,stderr=child.communicate(timeout=300);value=json.loads(stdout);assert value['ok'] or value.get('error')=='project-writer-busy',(value,stderr);competing.append(value)
    result=json.loads(command('resume-completed',[sys.executable,'-I','-m','harness.run_cli','resume','--root',root,'--run-id',pending['id']]))
   elif case=='cli':result=json.loads(command('run',[sys.executable,'-I','-m','harness.run_cli','run','--root',root,'--input',taskfile]))
   else:
    plan=companion.preview(root,'task.json');companion.apply(root,plan['preview'],plan['fingerprint']);entry=json.loads((root/'opencode.json').read_text())['mcp']['servers']['harness_companion']
    async def execute():
     from mcp import ClientSession,StdioServerParameters
     from mcp.client.stdio import stdio_client
     async with asyncio.timeout(600):
      async with stdio_client(StdioServerParameters(command=entry['command'][0],args=entry['command'][1:])) as (read,write):
       async with ClientSession(read,write,read_timeout_seconds=timedelta(seconds=580)) as session:
        await session.initialize();inventory=await session.call_tool('harness_discover_tests',{});assert json.loads(inventory.content[0].text)['count']==3;r=await session.call_tool('harness_run',dict(task_name='approved_task'));return json.loads(r.content[0].text)
    result=asyncio.run(execute())
   report=status(root,result['run_id']);(out/(case+'-status.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');assert result['ok'],result
   assert report['run']['version']==3
   run=report['run'];auto=run['automatic_tests'];gate=run['gates']['@automatic-tests'];assert gate['ok'] and gate['count']==3 and gate['counts']['executed']==(4 if case=='cli' else 3);assert all(p['status']=='PASS' for p in gate['projects'].values());assert d.inventory and len(d.requests)==report['metrics']['requests'];assert not Store(root).export()['records']['claims'] and Store(root).status()['queue']
   paths=[]
   for generation in auto['generations'].values():
    for project in generation['projects'].values():
     for framework in project['frameworks'].values():
      artifact=framework.get('receipt',{}).get('artifact')
      if not artifact:continue
      path=root/artifact['path'];assert hashlib.sha256(path.read_bytes()).hexdigest()==artifact['sha256'];target=out/case/'artifacts'/path.relative_to(root/'.harness/artifacts'/run['id']);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target);paths.append(str(path))
   for aid,action in report['actions'].items():
    if not action.get('process_spec'):continue
    path=Path(action['process_spec']['log']);target=out/case/'actions'/aid/'process.log';target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
   assert len(paths)==len(set(paths))
   if case=='recovery':
    assert report['metrics']['process_attempts']==10 and sum(x['tool']=='patch' for x in report['actions'].values())==1
    (out/'recovery-race.json').write_text(json.dumps(dict(status='PASS',competing=competing,drift_refused=True,process_attempts=10,patches=1),indent=2)+'\n',encoding='utf-8')
   if case=='cli':
    assert len(auto['generations'])==2 and run['p4']['items'][0]['attempts']==2;first=next(g for g in auto['generations'].values() if g['status']=='FAIL');assert [p['status'] for p in first['projects'].values()].count('PASS')==2 and first['status']=='FAIL';assert sum(p['frameworks'][f]['receipt'].get('counts',{}).get('failed',0) for p in first['projects'].values() for f in p['frameworks'])==1
   rows.append(dict(case=case,status='PASS',run_id=run['id'],source=gate['source'],inventory=inspection['identity'],projects=inspection['projects'],test_counts=gate['counts'],generations=len(auto['generations']),unique_trx=len(paths),requests=len(d.requests),commands=commands))
   if case=='cli':
    empty=root/'zzz newly added/EmptyTests.csproj';empty.parent.mkdir();empty.write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net10.0</TargetFramework><OutputType>Exe</OutputType></PropertyGroup><ItemGroup>'+__import__('automatic_fixtures').PACKAGES+'</ItemGroup></Project>',encoding='utf-8');(empty.parent/'Nothing.cs').write_text('// Intentionally no tests.\n',encoding='utf-8')
    before=len(d.requests);refused=json.loads(command('completed-inventory-drift',[sys.executable,'-I','-m','harness.run_cli','resume','--root',root,'--run-id',run['id']],1));assert refused['error']=='test-inventory-changed-revalidation-required' and len(d.requests)==before
    d.repair=False
    invalid=json.loads(command('empty-project-run',[sys.executable,'-I','-m','harness.run_cli','run','--root',root,'--input',taskfile],1));negative=status(root,invalid['run_id']);(out/'empty-project-status.json').write_text(json.dumps(negative,indent=2)+'\n',encoding='utf-8');assert negative['run']['automatic_tests']['inventory']['count']==4 and not negative['run']['gates']['@automatic-tests']['ok'];assert negative['run']['capture']['state']=='not-eligible'
    zero_rows=[p for g in negative['run']['automatic_tests']['generations'].values() for name,p in g['projects'].items() if name=='zzz newly added/EmptyTests.csproj'];assert zero_rows and all(p['status']=='FAIL' for p in zero_rows)
    zero_receipts=[f['receipt'] for p in zero_rows for f in p['frameworks'].values()];assert any(v.get('returncode')==0 and v.get('counts',{}).get('executed')==0 and not v['ok'] for v in zero_receipts),zero_receipts
    for action in negative['actions'].values():
     if not action.get('process_spec'):continue
     log=Path(action['process_spec']['log']);target=out/'empty-project'/log.relative_to(root/'.harness/artifacts'/invalid['run_id']);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(log,target)
    for trx in (root/'.harness/artifacts'/invalid['run_id']).rglob('*.trx'):
     target=out/'empty-project'/trx.relative_to(root/'.harness/artifacts'/invalid['run_id']);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(trx,target)
    (out/'empty-project-result.json').write_text(json.dumps(dict(status='PASS',new_inventory_count=4,configuration_unchanged=True,old_resume_refused=True,zero_exit_did_not_pass=True,error=invalid.get('error')),indent=2)+'\n',encoding='utf-8')

 (out/'result.json').write_text(json.dumps(dict(status='PASS',product=harness.__version__,platform=sys.platform,rows=rows),indent=2)+'\n',encoding='utf-8');print(json.dumps(rows))
if __name__=='__main__':main()
