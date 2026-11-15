"""Fresh release-only UMUH-like rehearsal with actual HTTP/.NET/storage effects."""
import argparse,asyncio,hashlib,json,os,shutil,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from p2_fixtures import http_provider,FixtureProvider
from p2_application_fixtures import EditScenario
from p3_umuh_fixture import create,DOMAIN,EVIDENCE,ORIGINAL,EXPECTED,FIRST,SECOND,THIRD


def save(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def python_at(env):return env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
def run(argv,cwd,log,ok=True,env=None):
    p=subprocess.run([str(a) for a in argv],cwd=cwd,env=env,text=True,encoding='utf-8',errors='replace',capture_output=True,timeout=600)
    log.parent.mkdir(parents=True,exist_ok=True);log.write_text(p.stdout+p.stderr,encoding='utf-8')
    if ok:assert p.returncode==0,(argv,p.stdout[-1500:],p.stderr[-1500:])
    return p

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--kit',type=Path,required=True);a=ap.parse_args();out=a.output.absolute();out.mkdir(parents=True,exist_ok=True);kit=a.kit.absolute()
    scratch=Path(tempfile.mkdtemp(prefix='p3 installed Ω '));root=create(scratch/'Tenant Ω UMUH rehearsal');env=scratch/'Independent runtime';transferred=scratch/'Transferred release';shutil.copytree(kit,transferred);kit=transferred;installer=kit/'install.py'
    baseenv={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'};baseenv.pop('PYTHONPATH',None)
    install=[sys.executable,installer,'install','--env',env,'--profile','knowledge']
    if sys.platform=='linux':install=[sys.executable,ROOT/'scripts/offline_exec.py',*install[1:]]
    run(install,scratch,out/'offline-knowledge-install.log',env=baseenv);python=python_at(env)
    count=[0]
    def driver(command,input=None,id=None,expect=0):
        count[0]+=1;argv=[python,'-I',ROOT/'tests/p3_installed_driver.py',command,'--root',root]
        if input is not None:
            path=scratch/('driver-'+str(count[0])+'.json');save(path,input);argv+=['--input',path]
        if id is not None:argv+=['--id',id]
        p=run(argv,root,out/('driver-'+str(count[0])+'.log'),ok=expect==0,env=baseenv);assert p.returncode==expect,(command,p.returncode,p.stdout[-1000:]);return json.loads(p.stdout) if expect==0 else None
    def cli(module,command,**flags):
        count[0]+=1;argv=[python,'-I','-m',module,command,'--root',root]
        for key,value in flags.items():
            if value is True:argv+=['--'+key.replace('_','-')]
            elif value is not False:argv+=['--'+key.replace('_','-'),str(value)]
        p=run(argv,root,out/('cli-'+str(count[0])+'.log'),env=baseenv);return json.loads(p.stdout)
    versions=driver('versions');assert versions['knowledge']=='0.3.0rc1' and not versions['harness_available'] and not versions['mcp_available']
    initialized=driver('initialize');assert not initialized['queue']
    scan=driver('scan');assert scan['scan']['complete'] and len(scan['work_counts'])>1
    initial_approval=driver('approve');questions=driver('read',{'question':'AdmissionRule'});assert questions['context']['claims'] and not questions['no_answer']['claims']
    inferred=driver('inferred');assert not inferred['claims']
    run([sys.executable,installer,'install','--env',env,'--profile','full'],scratch,out/'add-harness.log',env=baseenv)
    versions_full=driver('versions');assert versions_full['harness_available']
    sdk=shutil.which('dotnet')
    if not sdk and sys.platform=='linux':sdk=str(ROOT/'.local/dotnet/dotnet')
    assert sdk and Path(sdk).is_file(),'native .NET SDK unavailable'
    extra={'DOTNET_ROOT':str(Path(sdk).parent),'DOTNET_CLI_HOME':str(scratch/'dotnet-home'),'DOTNET_CLI_TELEMETRY_OPTOUT':'1','MSBUILDDISABLENODEREUSE':'1'}
    if Path('/workspace/nuget').exists():extra['NUGET_PACKAGES']='/workspace/nuget'
    sdkversion=run([sdk,'--version'],root,out/'sdk-version.log',env={**baseenv,**extra}).stdout.strip();assert sdkversion=='10.0.404',sdkversion
    check='checks/Acceptance.Probe/Acceptance.Probe.csproj'
    run([sdk,'build',check,'-m:1','-p:UseSharedCompilation=false'],root,out/'initial-build.log',env={**baseenv,**extra})
    before=run([sdk,'run','--project',check,'--no-build','--',str(out/'before-check.json')],root,out/'initial-expected-failure.log',ok=False,env={**baseenv,**extra,'HARNESS_ACTION_ID':'preflight'})
    assert before.returncode!=0 and json.loads((out/'before-check.json').read_text())['failed']>0
    def configuration(endpoint):
        return dict(version=1,provider=dict(endpoint=endpoint,model='synthetic-fixture',evidence='test-double'),capture='required',limits={'recipe_seconds':180,'elapsed_seconds':900,'tool_bytes':10000,'context_bytes':32000},recipes={
            'build':dict(kind='build',argv=[sdk,'build',check,'-m:1','-p:UseSharedCompilation=false'],result=dict(format='exit',path=''),rerun_safe=True,env=extra),
            'test':dict(kind='test',argv=[sdk,'run','--project',check,'--no-build','--','{artifacts}/checks.json'],result=dict(format='json',path='{artifacts}/checks.json'),rerun_safe=True,env=extra)})
    task=dict(version=1,goal='Synthetic rehearsal: clamp count into [0,2], preserve independent check and add the supported RuleEvidence declaration.',kind='coding',writable=[DOMAIN,EVIDENCE],recipes=['build','test'],existing_test_edits=[])
    task_path=root/'tasks/approved.json';save(task_path,task)
    original_host='{\n  "model": "synthetic-original-host-model"\n}\n';(root/'opencode.json').write_text(original_host,encoding='utf-8',newline='')
    # Optional MCP is an explicitly online, pinned add-on. Core installation above was offline.
    run([sys.executable,installer,'install','--env',env,'--profile','full','--mcp-online'],scratch,out/'optional-mcp-online.log',env=baseenv)
    first=EditScenario(DOMAIN,EXPECTED,{EVIDENCE:FIRST})
    with http_provider(first) as endpoint:
        config_path=scratch/'config.json';save(config_path,configuration(endpoint));cli('harness.run_cli','configure',input=config_path)
        host=cli('harness.companion','preview',task='tasks/approved.json');host_path=scratch/'host-preview.json';save(host_path,host['preview']);cli('harness.companion','apply',input=host_path,approve=host['fingerprint'])
        doctor=cli('harness.companion','doctor');assert doctor['mcp_available']
        config=json.loads((root/'opencode.json').read_text());servers=config['mcp']['servers'];protocol={}
        async def mcp_calls():
            from mcp import ClientSession,StdioServerParameters
            from mcp.client.stdio import stdio_client
            for name,entry in servers.items():
                async with stdio_client(StdioServerParameters(command=entry['command'][0],args=entry['command'][1:],env=baseenv)) as (read,write):
                    async with ClientSession(read,write) as session:
                        await session.initialize();tools=await session.list_tools();protocol[name]={'tools':[t.name for t in tools.tools]}
                        tool='knowledge_context' if name=='knowledge_local' else 'harness_doctor';args={'task':'AdmissionRule'} if name=='knowledge_local' else {}
                        result=await session.call_tool(tool,args);protocol[name]['read']=json.loads(result.content[0].text)
                        if name=='harness_companion':
                            bad=await session.call_tool('harness_run',{'task_name':'not-enrolled'});assert not json.loads(bad.content[0].text)['ok']
                            result=await session.call_tool('harness_run',{'task_name':'approved_task'});protocol[name]['run']=json.loads(result.content[0].text)
        before_canonical=driver('snapshot')['knowledge'];asyncio.run(mcp_calls());outcome=protocol['harness_companion']['run'];assert outcome['ok'],outcome
        state1=driver('snapshot');assert state1['knowledge']['records']==before_canonical['records'] and state1['knowledge']['history']==before_canonical['history']
        pending=[q for q in state1['knowledge']['queue'] if q['status']=='pending'];assert len(pending)==1
        candidate1=pending[0];identifier=next(o['id'] for o in candidate1['payload']['operations'] if o['kind']=='claims')
        assert 'RuleEvidence' in next(o['payload']['statement'] for o in candidate1['payload']['operations'] if o['kind']=='claims')
        assert next(r for r in state1['runs'] if r['run']['id']==outcome['run_id'])['run']['gates']['test']['counts']['executed']==3
    approve1=driver('approve')
    second=EditScenario(EVIDENCE,SECOND)
    task2={**task,'writable':[EVIDENCE],'goal':'Rehearsal second supported declaration revision, same identity.'};task2_path=scratch/'task2.json';save(task2_path,task2)
    with http_provider(second) as endpoint:
        save(config_path,configuration(endpoint));cli('harness.run_cli','configure',input=config_path);outcome2=cli('harness.run_cli','run',input=task2_path);assert outcome2['ok']
    state2=driver('snapshot');candidate2=next(q for q in state2['knowledge']['queue'] if q['status']=='pending');change=next(o for o in candidate2['payload']['operations'] if o['kind']=='claims');assert change['id']==identifier and change['expected']==1 and change['action']=='update'
    history_before=driver('history',id=identifier);assert len(history_before['revisions'])==1;approve2=driver('approve');history_after=driver('history',id=identifier);assert len(history_after['revisions'])==2
    # Actual edit interruption then intervening user bytes; recovery refuses to overwrite.
    with http_provider(EditScenario(EVIDENCE,THIRD)) as endpoint:
        save(config_path,configuration(endpoint));cli('harness.run_cli','configure',input=config_path);driver('fault-run',{'phase':'edit-file-written','task':task2},expect=73)
        interrupted=next(r['run'] for r in driver('snapshot')['runs'] if r['run']['status']=='running')
        user=(root/EVIDENCE).read_text()+'// user edit preserved\n';(root/EVIDENCE).write_text(user,encoding='utf-8')
        argv=[python,'-I','-m','harness.run_cli','resume','--root',root,'--run-id',interrupted['id']]
        refused=run(argv,root,out/'user-conflict.log',ok=False,env=baseenv);assert refused.returncode!=0 and (root/EVIDENCE).read_text()==user
    # A new explicitly scoped session preserves the user comment and is killed after submit.
    desired=THIRD+'// user edit preserved\n'
    with http_provider(EditScenario(EVIDENCE,desired)) as endpoint:
        save(config_path,configuration(endpoint));cli('harness.run_cli','configure',input=config_path)
        # A comment-only same semantic revision is still a changed-source observation:
        # preceding failed session had already written THIRD. Add another supported base.
        desired=desired.replace('System.Exception','System.ApplicationException')
    with http_provider(EditScenario(EVIDENCE,desired)) as endpoint:
        save(config_path,configuration(endpoint));cli('harness.run_cli','configure',input=config_path);driver('fault-run',{'phase':'capture-after-submit','task':task2},expect=73)
        pending_run=next(r['run'] for r in driver('snapshot')['runs'] if r['run']['execution']=='passed' and r['run']['status']=='running')
        mtime=(root/EVIDENCE).stat().st_mtime_ns;recovered=cli('harness.run_cli','resume',run_id=pending_run['id']);assert recovered['ok'] and (root/EVIDENCE).stat().st_mtime_ns==mtime
    state3=driver('snapshot');third=next(q for q in state3['knowledge']['queue'] if q['status']=='pending');driver('dispose',{'id':third['id'],'disposition':'deferred'})
    rejected_source=desired.replace('System.ApplicationException','System.InvalidOperationException')
    with http_provider(EditScenario(EVIDENCE,rejected_source)) as endpoint:
        save(config_path,configuration(endpoint));cli('harness.run_cli','configure',input=config_path);rejected_run=cli('harness.run_cli','run',input=task2_path);assert rejected_run['ok']
    candidate_rejected=next(q for q in driver('snapshot')['knowledge']['queue'] if q['status']=='pending');driver('dispose',{'id':candidate_rejected['id'],'disposition':'rejected'})
    for repeated_source in (desired,rejected_source):
        with http_provider(EditScenario(EVIDENCE,repeated_source)) as endpoint:
            save(config_path,configuration(endpoint));cli('harness.run_cli','configure',input=config_path);assert cli('harness.run_cli','run',input=task2_path)['ok']
    disposed=driver('snapshot')['knowledge']['queue'];assert next(q for q in disposed if q['id']==third['id'])['status']=='deferred' and next(q for q in disposed if q['id']==candidate_rejected['id'])['status']=='rejected' and not any(q['status']=='pending' for q in disposed)
    with http_provider(FixtureProvider()) as endpoint:
        save(config_path,configuration(endpoint));cli('harness.run_cli','configure',input=config_path);readonly=scratch/'read-only.json';save(readonly,{**task,'kind':'read-only','writable':[],'recipes':[]})
        no_fact=cli('harness.run_cli','run',input=readonly);assert no_fact['ok'] and no_fact['capture']['state']=='no-candidate'
    backup=cli('knowledge.maintain_cli','backup-preview',destination=scratch/'state.zip');bp=scratch/'bp.json';save(bp,backup['preview']);cli('knowledge.maintain_cli','apply',input=bp,approve=backup['fingerprint'])
    before_roundtrip=driver('snapshot');(root/'user-unrelated.txt').write_text('PRESERVE USER SOURCE',encoding='utf-8')
    restore=cli('knowledge.maintain_cli','restore-preview',archive=scratch/'state.zip',recovery=scratch/'replaced-state');rp=scratch/'rp.json';save(rp,restore['preview']);cli('knowledge.maintain_cli','apply',input=rp,approve=restore['fingerprint'])
    assert driver('snapshot')==before_roundtrip and (root/'user-unrelated.txt').read_text()=='PRESERVE USER SOURCE'
    run([sys.executable,installer,'uninstall','--env',env],scratch,out/'uninstall.log',env=baseenv)
    run([sys.executable,installer,'install','--env',env,'--profile','full'],scratch,out/'reinstall.log',env=baseenv)
    assert driver('snapshot')==before_roundtrip
    # Two independent roots are initialized, not copied root-bound stores.
    others=[]
    for name in ('Second project','Third project'):
        other=create(scratch/name);p=run([python,'-I','-m','knowledge.cli','init','--root',other],other,out/(name+'.log'),env=baseenv);value=json.loads(p.stdout);assert value['ok'];others.append(other)
    for other in others:
        p=run([python,'-I','-m','knowledge.cli','export','--root',other],other,out/(other.name+'-export.log'),env=baseenv);assert not json.loads(p.stdout)['records']['claims'];assert (other/DOMAIN).read_text()==ORIGINAL
    removal=cli('harness.companion','remove-preview');remove_path=scratch/'remove.json';save(remove_path,removal['preview']);cli('harness.companion','apply',input=remove_path,approve=removal['fingerprint']);assert (root/'opencode.json').read_bytes()==original_host.encode()
    # Equivalent tasks from a fresh baseline through the installed comparison backend.
    comparison_root=create(scratch/'comparison source');provider=EditScenario(DOMAIN,EXPECTED,{EVIDENCE:FIRST})
    with http_provider(provider) as endpoint:
        save(config_path,configuration(endpoint));run([python,'-I','-m','harness.run_cli','configure','--root',comparison_root,'--input',config_path],comparison_root,out/'comparison-config.log',env=baseenv)
        task_json=scratch/'comparison-task.json';save(task_json,task)
        p=run([python,'-I','-m','harness.run_cli','compare','--root',comparison_root,'--input',task_json,'--output',scratch/'comparison'],comparison_root,out/'comparison.log',env=baseenv);comparison=json.loads(p.stdout);assert comparison['ok']
    save(out/'comparison.json',comparison)
    save(out/'rehearsal.json',dict(synthetic_host=True,production_UMUH=False,versions=versions,versions_full=versions_full,sdk=sdkversion,initial_scan=scan,initial_approval=initial_approval,questions=questions,inferred=inferred,first=dict(outcome=outcome,candidate=candidate1,approval=approve1,state=state1),second=dict(outcome=outcome2,candidate=candidate2,approval=approve2,state=state2,history_before=history_before,history_after=history_after),recovered_outbox=recovered,conflict_preserved=True,metadata_roundtrip_exact=True,protocol=protocol,no_fact=no_fact,final=before_roundtrip,independent_roots=[str(p) for p in others],package_imports_outside_checkout=True))
    # Real process/TRX-like JSON receipts are copied as bounded review artifacts.
    for p in (root/'.harness/artifacts').rglob('*'):
        if p.is_file():target=out/'artifacts'/p.relative_to(root/'.harness/artifacts');target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    print('PASS: isolated offline core, optional MCP protocol, real UMUH-like .NET source behavior and repeated learning, crash/conflict/outbox, restore/reinstall, comparison and root isolation.')
if __name__=='__main__':main()
