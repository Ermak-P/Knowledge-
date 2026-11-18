"""Fresh installed P4 overflow repair on the pinned public eShopOnWeb application."""
import argparse,json,os,shutil,subprocess,sys,tempfile,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from p2_fixtures import http_provider,configuration,task,calls,final
from p2_application_fixtures import EditScenario,BASKET,NEW_TEST,OVERFLOW_TEST
from harness.runtime import configure,source_snapshot,Journal
from harness.engine import start,status
from knowledge.project import Project
from knowledge.util import loads,digest
from knowledge.store import Store
PIN='0c2c95d9d450d07fcd4e96e95e1cd48c20834e99'
class Application(EditScenario):
    def decide(self,body):
        s=loads(body['messages'][0]['content'])
        if s['runtime_role']=='Main':
            self.requests.append(body);agent=s['agent'];n=self.main_agents[agent];self.main_agents[agent]+=1
            if any(i['status']!='done' for i in s['ledger']['items']):return calls(('delegate',dict(role='Coding',assignment='Implement the specified overflow behavior and regression')))
            return calls(('delegate',dict(role='Reviewing',assignment='Inspect final diff, independent oracle and final real TRX evidence'))) if 'review' not in s['progress']['gates'] else final()
        return super().decide(body)
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.absolute();out.mkdir(parents=True,exist_ok=True)
    import harness,knowledge
    assert Path(harness.__file__).is_relative_to(Path(sys.prefix)) and Path(knowledge.__file__).is_relative_to(Path(sys.prefix))
    host=ROOT/'benchmarks/eShopOnWeb';assert subprocess.check_output(['git','-C',str(host),'rev-parse','HEAD'],text=True).strip()==PIN
    before=source_snapshot(Project(host));sdk=Path(shutil.which('dotnet') or str(ROOT/'.local/dotnet/dotnet'));assert subprocess.check_output([str(sdk),'--version'],cwd=host,text=True).strip()=='10.0.404'
    with tempfile.TemporaryDirectory(prefix='p4-application-') as tmp:
        scratch=Path(tmp);root=scratch/'eShopOnWeb';shutil.copytree(host,root,ignore=shutil.ignore_patterns('.git','bin','obj','.knowledge','.harness'))
        extra=dict(DOTNET_ROOT=str(sdk.parent),DOTNET_CLI_HOME=str(scratch/'dotnet-home'),NUGET_PACKAGES=str(ROOT/'.local/nuget'),DOTNET_CLI_TELEMETRY_OPTOUT='1',MSBUILDDISABLENODEREUSE='1')
        unit='tests/UnitTests/UnitTests.csproj';env={**os.environ,**extra};commands=[]
        def command(label,argv):
            with (out/(label+'.log')).open('w',encoding='utf-8') as log:r=subprocess.run([str(x) for x in argv],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
            commands.append(dict(label=label,argv=[str(x) for x in argv],returncode=r.returncode));assert r.returncode==0,(label,(out/(label+'.log')).read_text()[-2000:])
        original=(root/BASKET).read_text(encoding='utf-8-sig');desired=original.replace('Quantity += quantity;','Quantity = checked(Quantity + quantity);');assert desired!=original
        save(out/'scenario.json',dict(pin=PIN,sdk='10.0.404',source=BASKET,new_test=NEW_TEST,oracle=OVERFLOW_TEST,expected='Overflow throws and preserves int.MaxValue; original implementation must fail the added regression.',defined_before_execution=True))
        command('restore',[sdk,'restore',unit,'--disable-parallel','-m:1'])
        command('baseline-build',[sdk,'build',unit,'--no-restore','-m:1','-p:UseSharedCompilation=false','-p:LibraryRestore=false'])
        command('baseline-test',[sdk,'test',unit,'--no-build','--no-restore','-m:1','--logger','trx;LogFileName=baseline.trx','--results-directory',out])
        counters=ET.parse(out/'baseline.trx').getroot().find('.//{*}Counters').attrib;assert int(counters['executed'])==int(counters['passed'])==49
        t=task(BASKET);t.update(version=2,goal='AddQuantity overflow must throw without corrupting the previous quantity.',writable=[BASKET,NEW_TEST],acceptance=['Adding 1 to int.MaxValue throws OverflowException and preserves quantity.','Retain all existing tests and add the independent overflow regression.'],items=[])
        d=Application(BASKET,desired,{NEW_TEST:OVERFLOW_TEST},repair=True,first_source=original)
        with http_provider(d) as endpoint:
            c=configuration(endpoint,recipe_seconds=240,elapsed_seconds=1200,tool_bytes=10000,context_bytes=48000)
            c['recipes']={'build':dict(kind='build',argv=[str(sdk),'build',unit,'--no-restore','-m:1','-p:UseSharedCompilation=false','-p:LibraryRestore=false'],result=dict(format='exit',path=''),rerun_safe=True,env=extra),'test':dict(kind='test',argv=[str(sdk),'test',unit,'--no-build','--no-restore','-m:1','--logger','trx;LogFileName=after.trx','--results-directory','{artifacts}'],result=dict(format='trx',path='{artifacts}/after.trx'),rerun_safe=True,env=extra)}
            configure(root,c,True);result=start(root,t);report=status(root,result['run_id']);save(out/'run.json',report);save(out/'review-inputs.json',[b for b in d.requests if loads(b['messages'][0]['content'])['runtime_role']=='Reviewing'])
            for key,action in report['actions'].items():
                if action.get('process_spec'):
                    src=Path(action['process_spec']['log']).parent;shutil.copytree(src,out/'artifacts'/key)
            assert result['ok'],result
        tests=[a['result'] for a in report['actions'].values() if a['tool']=='recipe' and a['args']['name']=='test'];assert any(not x['ok'] and x.get('returncode')!=0 for x in tests);assert report['run']['gates']['test']['counts']['passed']==50
        assert (root/NEW_TEST).read_text()==OVERFLOW_TEST and (root/BASKET).read_text()==desired
        final=source_snapshot(Project(root));assert all(final.get(k)==v for k,v in before.items() if k.startswith('tests/') and k!=NEW_TEST)
        store=Store(root).export();assert not store['records']['claims'] and store['queue'];assert report['run']['capture']['state'] in ('delivered','existing')
        save(out/'result.json',dict(status='PASS',product=harness.__version__,pin=PIN,baseline_tests=49,final_tests=50,regression_failed_before_repair=True,existing_tests_preserved=True,canonical_claims=0,capture=report['run']['capture'],source=digest(report['run']['source']),commands=commands,provider='synthetic HTTP decisions; real SDK, source, TRX and capture'))
    assert before==source_snapshot(Project(host))
if __name__=='__main__':main()
