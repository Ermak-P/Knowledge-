"""Executed P2 .NET and comparison scenarios, synthetic HTTP decisions explicitly labelled."""
import argparse,hashlib,json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from p2_fixtures import http_provider,configuration,task,project,FixtureProvider
from p2_application_fixtures import EditScenario,BASKET,NEW_TEST,OVERFLOW_TEST
from harness.runtime import configure,source_snapshot,Journal
from knowledge.project import Project
from harness.engine import start,status
from harness.comparison import compare
from knowledge.store import Store
from knowledge.util import digest
PIN='0c2c95d9d450d07fcd4e96e95e1cd48c20834e99'

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def command(out,name,argv,cwd,env):
    with (out/(name+'.log')).open('w') as log:p=subprocess.run(argv,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
    assert p.returncode==0,(name,(out/(name+'.log')).read_text()[-3000:])
def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
def trx(path):
    c=ET.parse(path).getroot().find('.//{*}Counters').attrib
    assert int(c['total'])==int(c['executed'])==int(c['passed'])>0 and int(c['failed'])==0,c
    return c

def collect(root,outcome,out,label,scenario):
    report=status(root,outcome['run_id']);save(out/(label+'-run.json'),report)
    for action,a in report['actions'].items():
        if a['tool']=='recipe' and a.get('process_spec'):
            directory=Path(a['process_spec']['log']).parent
            for path in directory.iterdir():
                if path.is_file():shutil.copyfile(path,out/(label+'-'+action[:12]+'-'+path.name))
    sizes=[len(json.dumps(b,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()) for b in scenario.requests]
    return dict(outcome=outcome,metrics=report['metrics'],gates=report['run']['gates'],context_bytes=sizes,capture=report['outbox'],roles=report['run']['agents'])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
    host=ROOT/'benchmarks/eShopOnWeb';assert git(host,'rev-parse','HEAD')==PIN
    original=source_snapshot(Project(host));original_diff=git(host,'diff','HEAD');assert not original_diff
    scratch=Path(tempfile.mkdtemp(prefix='p2-application-',dir=ROOT/'.local'));root=scratch/'eShopOnWeb'
    shutil.copytree(host,root,ignore=shutil.ignore_patterns('.git','.knowledge','.harness','bin','obj','node_modules'))
    shutil.copyfile(host/'LICENSE',out/'eShopOnWeb-LICENSE')
    sdk=ROOT/'.local/dotnet/dotnet';env=os.environ.copy();extra=dict(DOTNET_ROOT=str(sdk.parent),DOTNET_CLI_HOME=str(scratch/'dotnet-home'),NUGET_PACKAGES='/workspace/nuget' if Path('/workspace/nuget').exists() else str(ROOT/'.local/nuget'),TMPDIR=str(scratch/'tmp'),DOTNET_CLI_TELEMETRY_OPTOUT='1',MSBUILDDISABLENODEREUSE='1')
    Path(extra['TMPDIR']).mkdir();env.update(extra);sdkversion=subprocess.check_output([str(sdk),'--version'],env=env,text=True).strip()
    unit='tests/UnitTests/UnitTests.csproj';initial=source_snapshot(Journal(root).project)
    expected=(root/BASKET).read_text(encoding='utf-8-sig').replace('Quantity += quantity;','Quantity = checked(Quantity + quantity);')
    assert expected!=(root/BASKET).read_text(encoding='utf-8-sig')
    expectation=dict(source=BASKET,old='Quantity += quantity;',new='Quantity = checked(Quantity + quantity);',new_test=NEW_TEST,test_source=OVERFLOW_TEST,behavior='Adding 1 to int.MaxValue throws OverflowException and preserves the prior quantity.',defined_before_execution=True)
    save(out/'application-expectation.json',expectation)
    command(out,'baseline-restore',[str(sdk),'restore',unit,'--disable-parallel','-m:1'],root,env)
    command(out,'baseline-build',[str(sdk),'build',unit,'--no-restore','-m:1','-p:UseSharedCompilation=false','-p:LibraryRestore=false'],root,env)
    command(out,'baseline-tests',[str(sdk),'test',unit,'--no-restore','--no-build','-m:1','-p:LibraryRestore=false','--logger','trx;LogFileName=baseline.trx','--results-directory',str(out)],root,env)
    before=trx(out/'baseline.trx');assert int(before['total'])==49
    scenario=EditScenario(BASKET,expected,{NEW_TEST:OVERFLOW_TEST},repair=True,first_source=(root/BASKET).read_text(encoding='utf-8-sig'))
    t=task(BASKET);t['goal']=expectation['behavior'];t['writable']=[BASKET,NEW_TEST]
    with http_provider(scenario) as endpoint:
        c=configuration(endpoint,recipe_seconds=240,elapsed_seconds=900,tool_bytes=10000,context_bytes=32000)
        c['recipes']={
          'build':dict(kind='build',argv=[str(sdk),'build',unit,'-m:1','-p:UseSharedCompilation=false','-p:LibraryRestore=false'],result=dict(format='exit',path=''),rerun_safe=True,env=extra),
          'test':dict(kind='test',argv=[str(sdk),'test',unit,'--no-restore','--no-build','-m:1','-p:LibraryRestore=false','--logger','trx;LogFileName=after.trx','--results-directory','{artifacts}'],result=dict(format='trx',path='{artifacts}/after.trx'),rerun_safe=True,env=extra)}
        configure(root,c,True);save(out/'application-config.json',c);save(out/'application-task.json',t)
        outcome=start(root,t);record=collect(root,outcome,out,'application',scenario);assert outcome['ok'],outcome
    after=record['gates']['test']['counts'];assert after['total']==50,after
    actual=status(root,outcome['run_id']);first_tests=[a['result'] for a in actual['actions'].values() if a['tool']=='recipe' and a['args']['name']=='test'];assert any(not r['ok'] and r['returncode']!=0 for r in first_tests), 'New regression must fail on old unchecked implementation'
    record['new_regression_failed_before_fix']=True
    current=source_snapshot(Journal(root).project)
    assert {p for p in set(current)|set(initial) if current.get(p)!=initial.get(p)}=={BASKET,NEW_TEST}
    assert all(current[p]==h for p,h in initial.items() if p.startswith('tests/') and p!=NEW_TEST)
    assert not Store(root).export()['records']['claims'];queue=Store(root).export()['queue'];assert queue
    # Explicit, test-only fingerprint approval verifies the existing canonical workflow.
    s=Store(root);plan=s.prepare();assert plan['ok'];s.apply(plan['fingerprint'],plan['fingerprint']);s.acknowledge(plan['fingerprint']);assert s.export()['records']['claims']
    record.update(pin=PIN,remote=git(host,'remote','get-url','origin'),sdk=sdkversion,before=before,after=after,expectation=expectation,existing_tests_preserved=True,canonical_before_approval=0,canonical_after_explicit_fixture_approval=len(s.export()['records']['claims']),initial_source=initial,final_source=current,provider_evidence='test-double over real HTTP; no model inference claim')
    save(out/'application.json',record)
    # Real SDK multi-project application; mandatory executed assertion fails then repairs.
    synthetic=scratch/'multi project проверка';(synthetic/'Core').mkdir(parents=True);(synthetic/'Checks').mkdir()
    (synthetic/'Core/Core.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>')
    good='public static class Feature { public static int Value => 2; }\n';bad='public static class Feature { public static int Value => 3; }\n'
    (synthetic/'Core/Feature.cs').write_text('public static class Feature { public static int Value => 1; }\n')
    (synthetic/'Checks/Checks.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net10.0</TargetFramework><OutputType>Exe</OutputType></PropertyGroup><ItemGroup><ProjectReference Include="../Core/Core.csproj" /></ItemGroup></Project>')
    (synthetic/'Checks/Program.cs').write_text('int failed = Feature.Value == 2 ? 0 : 1;\nSystem.IO.File.WriteAllText(args[0], System.Text.Json.JsonSerializer.Serialize(new { action=System.Environment.GetEnvironmentVariable("HARNESS_ACTION_ID"), executed=1, failed }));\nreturn failed;\n')
    st=task('Core/Feature.cs');st['goal']='Feature.Value returns 2, verified by independent Checks project.'
    def synthetic_configuration(endpoint):
        c=configuration(endpoint,recipe_seconds=120,elapsed_seconds=900)
        c['recipes']={
          'build':dict(kind='build',argv=[str(sdk),'build','Checks/Checks.csproj','-m:1','-p:UseSharedCompilation=false'],result=dict(format='exit',path=''),rerun_safe=True,env=extra),
          'test':dict(kind='test',argv=[str(sdk),'run','--project','Checks/Checks.csproj','--no-build','--','{artifacts}/checks.json'],result=dict(format='json',path='{artifacts}/checks.json'),rerun_safe=True,env=extra)}
        return c
    scenario=EditScenario('Core/Feature.cs',good,repair=True,first_source=bad)
    with http_provider(scenario) as endpoint:
        configure(synthetic,synthetic_configuration(endpoint),True);outcome=start(synthetic,st);repair=collect(synthetic,outcome,out,'repair',scenario);assert outcome['ok'],outcome
    rs=status(synthetic,outcome['run_id']);checks=[a['result'] for a in rs['actions'].values() if a['tool']=='recipe' and a['args']['name']=='test'];assert any(not c['ok'] for c in checks) and any(c['ok'] for c in checks)
    save(out/'repair.json',dict(**repair,task=st,independent_expected=good,failed_first=bad))
    # Same synthetic multi-project definition through both accounting modes.
    (synthetic/'Core/Feature.cs').write_text('public static class Feature { public static int Value => 1; }\n')
    scenario=EditScenario('Core/Feature.cs',good,repair=True,first_source=bad)
    with http_provider(scenario) as endpoint:
        configure(synthetic,synthetic_configuration(endpoint),True);comparison=compare(synthetic,st,scratch/'comparison');assert comparison['ok'],{m:r['outcome'] for m,r in comparison['comparison']['runs'].items()}
    save(out/'comparison.json',comparison)
    # An actual denied Coding operation; existing checks still execute and fail.
    scenario=EditScenario('Core/Feature.cs',good,deny=True);before_denial=source_snapshot(Journal(synthetic).project)
    with http_provider(scenario) as endpoint:
        configure(synthetic,synthetic_configuration(endpoint),True);outcome=start(synthetic,st);denied=collect(synthetic,outcome,out,'denied',scenario);assert not outcome['ok']
    assert source_snapshot(Journal(synthetic).project)==before_denial
    denied['denials']=[e for e in status(synthetic,outcome['run_id'])['events'] if e['kind']=='tool-denied'];assert denied['denials'];save(out/'denied.json',denied)
    assert source_snapshot(Project(host))==original and git(host,'diff','HEAD')==original_diff
    save(out/'original-immutability.json',dict(pin=PIN,source_identity=digest(original),after_identity=digest(source_snapshot(Project(host))),tracked_diff=original_diff,original_untouched=True,ordinary_disposable_copies=True))
    print('PASS: fresh eShop baseline 49/49; runner overflow behavior regression 50/50; real .NET repair, denial and equivalent comparison; original pin intact.',flush=True)

if __name__=='__main__':main()
