"""Installed worked dialogues + two fresh controlled replays and .NET behaviors.

The planner sees only task/retrieved Knowledge; a separate oracle checks choices
and preserved boundaries. This is not a live semantic/model equivalence claim.
"""
import argparse,hashlib,importlib.util,json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def load_fixture():
    path=ROOT/'tests/cr_fixtures.py';spec=importlib.util.spec_from_file_location('trial_cr_fixtures',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--dotnet',type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    import knowledge,harness
    from knowledge.cr_workflow import Workflow
    from knowledge.util import canonical_json
    assert Path(knowledge.__file__).is_relative_to(Path(sys.prefix)) and Path(harness.__file__).is_relative_to(Path(sys.prefix))
    fixtures=load_fixture();oracle=json.loads((ROOT/'tests/data/update-cr-oracle.json').read_text());cases=[]
    sdk=a.dotnet or Path(shutil.which('dotnet') or str(ROOT/'.local/dotnet/dotnet'));assert sdk.is_file(),'Existing .NET SDK is required for this behavioral qualification'
    with tempfile.TemporaryDirectory(prefix='ucr-installed-trial-') as tmp:
        for scenario,task in [('retry','An equivalent transient operation: bounded retry, independent transport recovery, caller deadline'),('cache','Эквивалентный справочник: кэш память интерфейс ILookup Find и поведение при промахе')]:
            base=Path(tmp)/scenario;base.mkdir();root,snapshot=fixtures.project(base,scenario=scenario);w=Workflow(root)
            dialogue=[];s=w.start(language='ru' if scenario=='cache' else 'en');dialogue.append(dict(step='initial',response=s))
            s=w.start(session=s['session'],cr=snapshot['cr']['url'],pr=snapshot['pr']['url']);s=w.sources(s['session'],snapshot,s['revision'])
            inspection=w.inspect(s['session'],['Transport.cs','Caller.cs'] if scenario=='retry' else ['Contracts.cs']);dialogue.append(dict(step='inspection',response=inspection))
            s=w.analyze(s['session'],fixtures.decisions(snapshot,scenario),s['revision']);dialogue.append(dict(step='questions',response=s))
            answers={'retry-limit':'max_attempts=4 fits the bounded transient operation budget.', 'transport-owner':'packet_attempts=2 is an independent per-packet recovery responsibility; changing it would multiply operation work.', 'deadline':'caller_deadline_ms=120 is the existing public caller budget.', 'capacity':'cache_capacity=32 ограничивает расход памяти; сохранить поведение при промахе.', 'contract':'Нужна совместимость прежних потребителей ILookup; сохранить сигнатуру Find.'}
            for q in w.get(s['session'])['questions']:
                answer=answers[q['item']];s=w.answer(s['session'],q['id'],answer,'trial-answer-'+q['id'],s['revision']);dialogue.append(dict(step='answer',question=q,text=answer,response=s))
            prepared=w.prepare(s['session'],s['revision']);dialogue.append(dict(step='review-concrete-exact-plan',response=prepared))
            assert prepared['state']=='awaiting_approval'
            saved=w.apply(s['session'],prepared['proposal']['plan'],prepared['revision']);dialogue.append(dict(step='fixture-user-exact-approval-and-save',response=saved))
            assert saved['state'] in ('saved','partial_saved')
            (a.output/(scenario+'-dialogue.json')).write_text(json.dumps(dialogue,ensure_ascii=False,indent=2)+'\n')
            command=[sys.executable,'-I','-B',str(ROOT/'tests/cr_replay_worker.py'),str(root),task]
            process=subprocess.run(command,capture_output=True,text=True);assert process.returncode==0,process.stdout+process.stderr
            replay=json.loads(process.stdout);plan=replay['plan'];expected=oracle[scenario]
            assert plan['parameters']==expected['parameters']
            assert all(s in ' '.join(plan['preserve']) for s in expected['preserve'])
            assert all(s in ' '.join(plan['reasons']) for s in expected['reasons'])
            (a.output/(scenario+'-replay.json')).write_text(json.dumps(replay,ensure_ascii=False,indent=2)+'\n')
            # Fresh controlled implementation in new files. The original scope
            # anchors stay unchanged; no checkout reset/PR edit is performed.
            replay_root=root/'Replay';replay_root.mkdir();params=plan['parameters']
            if scenario=='retry':
                config=f'public static class ReplayParameters {{ public const int MaxAttempts={params["max_attempts"]}; public const int DeadlineMs={params["caller_deadline_ms"]}; public const int PacketAttempts={params["packet_attempts"]}; }}\n'
                program='''using System;
int calls=0,elapsed=0;
while(calls<ReplayParameters.MaxAttempts && elapsed+20<=ReplayParameters.DeadlineMs){calls++;elapsed+=20;}
if(calls!=4 || elapsed>120 || Caller.DeadlineMs!=120 || Transport.PacketAttempts!=2 || ReplayParameters.PacketAttempts!=2) throw new Exception("retry/deadline/ownership oracle failed");
Console.WriteLine("PASS retry behavioral oracle; caller and packet owner unchanged");
''';includes='<Compile Include="../Caller.cs"/><Compile Include="../Transport.cs"/>'
            else:
                config=f'public static class ReplayParameters {{ public const int Capacity={params["cache_capacity"]}; }}\n'
                program='''using System;
using System.Collections.Generic;
var cache=new Queue<int>();
for(int i=0;i<100;i++){cache.Enqueue(i);if(cache.Count>ReplayParameters.Capacity)cache.Dequeue();}
if(cache.Count!=32 || typeof(ILookup).GetMethod("Find")!.ReturnType!=typeof(string))throw new Exception("cache/contract oracle failed");
Console.WriteLine("PASS cache behavioral oracle; ILookup.Find unchanged");
''';includes='<Compile Include="../Contracts.cs"/>'
            (replay_root/'ReplayParameters.cs').write_text(config);(replay_root/'Program.cs').write_text(program)
            (replay_root/'Replay.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net10.0</TargetFramework><OutputType>Exe</OutputType><EnableDefaultCompileItems>false</EnableDefaultCompileItems></PropertyGroup><ItemGroup><Compile Include="Program.cs"/><Compile Include="ReplayParameters.cs"/>'+includes+'</ItemGroup></Project>')
            argv=[str(sdk),'run','--project',str(replay_root/'Replay.csproj'),'--configuration','Release'];env={**os.environ,'DOTNET_ROOT':str(sdk.parent),'DOTNET_CLI_HOME':str(base/'dotnet-home'),'DOTNET_CLI_TELEMETRY_OPTOUT':'1','MSBUILDDISABLENODEREUSE':'1'}
            log=a.output/(scenario+'-dotnet.log')
            with log.open('wb') as out:built=subprocess.run(argv,cwd=replay_root,env=env,stdout=out,stderr=subprocess.STDOUT,timeout=120)
            cases.append(dict(scenario=scenario,persistence=saved['state'],records=saved['receipt']['records'],fresh_process=True,plan_oracle='PASS',behavior_command=argv,behavior_returncode=built.returncode,behavior_log=log.name,behavior_log_sha256=hashlib.sha256(log.read_bytes()).hexdigest()))
            (a.output/(scenario+'-export.json')).write_text(json.dumps(w.store.export(),ensure_ascii=False,indent=2)+'\n')
            assert built.returncode==0,log.read_text(errors='replace')
    result=dict(status='PASS',profile='installed-controlled-fresh-planner-and-dotnet-behavior',live_model='NOT_RUN; no approved live model is configured by this fixture',cases=cases,imports={'knowledge':knowledge.__file__,'harness':harness.__file__})
    (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
