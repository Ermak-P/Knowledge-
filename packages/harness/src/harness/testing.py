"""Runner v2: immutable suffix inventory and deterministic, broker-owned .NET testing."""
from copy import deepcopy
from datetime import datetime
import json,os,re,hashlib
from pathlib import Path
import xml.etree.ElementTree as ET
from knowledge.project import Project,safe_path,linked
from knowledge.util import require,digest,KnowledgeError
from . import runtime as rt

POLICY='dotnet-tests-suffix-v1'
PREFIX='@automatic-tests/'
GATE='@automatic-tests'
SDK_PROPERTIES={'TargetFramework','TargetFrameworks','AssemblyName','TargetPath'}
PROPERTIES=SDK_PROPERTIES|{'TargetFrameworkIdentifier','TargetFrameworkVersion','TargetFrameworkProfile','UsingMicrosoftNETSdk'}
EXCLUDED={'bin','obj','.git','.harness','.knowledge','.ai','.maintenance','.venv','.local','.vs','testresults','__pycache__','node_modules'}
INSTRUCTIONS='Automatically test every eligible filename ending Tests.csproj, ignoring case, including IpmAzureCommon.UnitTests.csproj and IpmAzureAutotests.csproj, in any ordinary source directory and outside the solution. Runtime owns restore/build/test/TRX verification. No model recipe selection or omitted Testing delegation can disable the final complete suite. Inventory drift requires a newly validated run; project-file write permissions do not expand. Use test_inventory(offset,limit) or the local discover-tests/status CLI for bounded evidence.'

def discover(root,limit=1048576):
    project=root if isinstance(root,Project) else Project(root)
    matches=[];excluded=[];errors=[];identities={};folded={}
    def walk_error(e):errors.append(dict(path=str(e.filename),error='directory-unreadable'))
    for directory,dirs,files in os.walk(project.root,followlinks=False,onerror=walk_error):
        parent=Path(directory)
        for name in sorted(dirs):
            path=parent/name;rel=path.relative_to(project.root).as_posix()
            if name.casefold() in EXCLUDED:
                dirs.remove(name);excluded.append(dict(path=rel,reason='generated-or-metadata'))
            elif linked(path):
                dirs.remove(name);errors.append(dict(path=rel,error='linked-directory'));excluded.append(dict(path=rel,reason='linked-directory-not-followed'))
        for name in sorted(files):
            if not name.casefold().endswith('tests.csproj'):continue
            path=parent/name;rel=path.relative_to(project.root).as_posix()
            try:
                rt.local_path(project,rel);safe_path(path)
                require(path.is_file(),'test-project-not-file');require(path.stat().st_size<=limit,'test-project-too-large')
                identity=os.path.normcase(str(path.absolute()));fold=rel.casefold()
                require(identity not in identities and fold not in folded,'ambiguous-test-project-path')
                identity_file=(path.stat().st_dev,path.stat().st_ino)
                require(identity_file not in identities.values(),'duplicate-test-project-file')
                identities[identity]=identity_file;folded[fold]=rel
                matches.append(dict(path=rel,sha256=rt.blob(path.read_bytes())))
            except (KnowledgeError,OSError) as e:errors.append(dict(path=rel,error=getattr(e,'code','test-project-unreadable')))
    core=dict(version=1,policy=POLICY,root=str(project.root),project=project.identity,projects=sorted(matches,key=lambda x:(x['path'].casefold(),x['path'])),errors=sorted(errors,key=lambda x:(x['path'],x['error'])))
    return dict(ok=not errors,identity=digest(core),count=len(matches),exclusions=sorted(excluded,key=lambda x:x['path']),**core)

def dotnet(c):
    builds=[r for r in c['recipes'].values() if r['kind']=='build']
    direct=[r['argv'][0] for r in builds if Path(r['argv'][0]).name.casefold() in ('dotnet','dotnet.exe')]
    unique={os.path.normcase(os.path.abspath(p)):p for p in direct}
    chosen=c.get('dotnet')
    if chosen:
        require(Path(chosen).is_absolute() and Path(chosen).is_file(),'dotnet-executable-must-be-absolute')
        require(not unique or set(unique)=={os.path.normcase(os.path.abspath(chosen))},'ambiguous-dotnet-executable')
    else:
        require(len(unique)==1,'ambiguous-or-missing-dotnet-executable');chosen=next(iter(unique.values()))
    if os.name=='nt':require(not chosen.startswith(('\\\\','//')) and len(Path(chosen).drive)==2,'unsupported-windows-executable-path')
    envs=[r['env'] for r in builds if r['argv'][0] in direct] or [r['env'] for r in builds]
    require(envs and all(e==envs[0] for e in envs),'ambiguous-dotnet-build-environment')
    return chosen,{**envs[0],'DOTNET_NOLOGO':'1','DOTNET_CLI_TELEMETRY_OPTOUT':'1','MSBUILDDISABLENODEREUSE':'1'}

def native_msbuild(c,authorized=None):
    """Only an already trusted build executable may provide full MSBuild."""
    builds=[r for n,r in c['recipes'].items() if (authorized is None or n in authorized) and r['kind']=='build' and Path(r['argv'][0]).name.casefold() in ('msbuild','msbuild.exe')]
    if not builds:return None
    require(len({os.path.normcase(os.path.abspath(r['argv'][0])) for r in builds})==1 and all(r['env']==builds[0]['env'] for r in builds),'ambiguous-native-msbuild-toolchain')
    return builds[0]['argv'][0],builds[0]['env']

def resolve_frameworks(props,host=None):
    frameworks=[v.strip() for v in (props.get('TargetFrameworks') or props.get('TargetFramework') or '').split(';') if v.strip()]
    if frameworks and not (set(props)==PROPERTIES and props['TargetFrameworkIdentifier']=='.NETFramework' and props['UsingMicrosoftNETSdk'].casefold()!='true'):
        require(len(frameworks)<=32 and len(set(frameworks))==len(frameworks) and all(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',v) for v in frameworks),'invalid-or-unresolved-test-frameworks')
        if props.get('TargetFrameworkIdentifier')=='.NETFramework':require((host or os.name)=='nt','legacy-dotnet-framework-requires-native-windows')
        return [(fw,dict(kind='sdk')) for fw in frameworks]
    # Four-property receipts from already-started SDK runs retain their meaning.
    require(set(props)==PROPERTIES,'legacy-framework-metadata-revalidation-required')
    identifier=props['TargetFrameworkIdentifier'];version=props['TargetFrameworkVersion'];profile=props['TargetFrameworkProfile']
    require(identifier=='.NETFramework' and re.fullmatch(r'v4(?:\.\d{1,2}){1,2}',version) and (not profile or re.fullmatch(r'[A-Za-z0-9_.-]+',profile)) and props['UsingMicrosoftNETSdk'].casefold()!='true','unsupported-legacy-test-framework',dict(identifier=identifier,version=version,profile=profile))
    require((host or os.name)=='nt','legacy-dotnet-framework-requires-native-windows',dict(identifier=identifier,version=version,profile=profile))
    moniker=identifier+',Version='+version+(',Profile='+profile if profile else '')
    return [(moniker,dict(kind='net-framework',identifier=identifier,version=version,profile=profile))]

def assembly_target(project,path,props):
    require(props.get('AssemblyName') and props.get('TargetPath'),'unresolved-test-assembly')
    target=Path(props['TargetPath']);target=target if target.is_absolute() else project.root/Path(path).parent/target
    safe_path(target);target=Path(os.path.abspath(target));safe_path(target);require(target.is_relative_to(project.root),'test-assembly-outside-project-root')
    return str(target)

def initialize(project,c,r):
    if c['version']!=2 or r['task']['kind']!='coding':return
    inventory=discover(project,{**rt.DEFAULT_LIMITS,**c['limits']}['file_bytes'])
    require(inventory['ok'],'automatic-test-discovery-invalid',inventory)
    r['automatic_tests']=dict(version=1,policy=POLICY,inventory=inventory,generations={},operations={},active=None)

def guard(project,c,r):
    if 'automatic_tests' not in r:return
    state=r['automatic_tests'];require(digest(c)==r['config_hash'],'configuration-changed-revalidation-required');require(c['version']==2 and state['version']==1 and state['policy']==POLICY,'unsupported-automatic-test-state')
    current=discover(project,{**rt.DEFAULT_LIMITS,**c['limits']}['file_bytes'])
    require(current['ok'] and current['identity']==state['inventory']['identity'],'test-inventory-changed-revalidation-required',dict(approved=state['inventory']['identity'],current=current))

def summary(r,offset=0,limit=8):
    require(type(offset) is int and offset>=0 and type(limit) is int and 0<limit<=20,'invalid-inventory-range')
    state=r.get('automatic_tests')
    if state is None:return dict(ok=True,enabled=False,reason='legacy explicit test recipes')
    inv=state['inventory'];gen=state['generations'].get(state['active'],{});rows=gen.get('projects',{})
    return dict(ok=True,enabled=True,root=inv['root'],identity=inv['identity'],count=inv['count'],status=gen.get('status','NOT_RUN'),projects=[dict(**p,status=rows.get(p['path'],{}).get('status','NOT_RUN'),counts=rows.get(p['path'],{}).get('counts')) for p in inv['projects'][offset:offset+limit]],partial=offset+limit<inv['count'],counts=r['gates'].get(GATE,{}).get('counts'),completed=sum(p.get('status')=='PASS' for p in rows.values()),not_run=inv['count'] if not gen else sum(p.get('status')=='NOT_RUN' for p in rows.values()))

def register(j,r,genid,path,phase,framework=None):
    state=r['automatic_tests'];name=PREFIX+digest([state['inventory']['identity'],genid,path,phase,framework]);op=dict(generation=genid,project=path,phase=phase,framework=framework)
    prior=state['operations'].get(name);require(prior is None or prior==op,'automatic-operation-conflict');state['operations'][name]=op;j.save(r);return name

def recipe_for(broker,name):
    r=broker.r;c=broker.c;guard(broker.j.project,c,r);state=r['automatic_tests'];op=state['operations'].get(name)
    require(op is not None and r['task']['kind']=='coding','automatic-recipe-not-authorized')
    gen=state['generations'][op['generation']];path=op['project'];phase=op['phase'];framework=op['framework']
    require(gen['source']==digest(r['source']) and path in [p['path'] for p in state['inventory']['projects']],'automatic-recipe-stale')
    require(name==PREFIX+digest([state['inventory']['identity'],op['generation'],path,phase,framework]),'automatic-recipe-identity-mismatch')
    rt.local_path(broker.j.project,path);exe,env=dotnet(c)
    metadata_version=gen.get('metadata_version',1)
    inspect_fields=','.join(sorted(PROPERTIES)) if metadata_version>=2 else 'TargetFramework,TargetFrameworks,AssemblyName,TargetPath'
    if phase=='restore':argv=[exe,'restore',path,'--disable-parallel','-m:1']
    elif phase in ('inspect','inspect-native'):
        require(framework is None or framework in gen['projects'][path]['frameworks'],'unknown-test-framework')
        native=native_msbuild(c,r['task']['recipes']) if phase=='inspect-native' else None
        require(phase!='inspect-native' or native is not None,'native-msbuild-not-configured')
        if native:exe,env=native
        argv=[exe,*([] if native else ['msbuild']),path,'-nologo','-getProperty:'+inspect_fields]
        if framework:argv+=['-p:TargetFramework='+framework]
    elif phase in ('legacy-restore','legacy-build'):
        sub=gen['projects'][path]['frameworks'].get(framework,{})
        require(sub.get('kind')=='net-framework' and os.name=='nt','legacy-operation-not-authorized')
        native=native_msbuild(c,r['task']['recipes'])
        if phase=='legacy-restore':
            from .platform import require_framework_runtime
            require_framework_runtime(sub['version'])
            # dotnet restore does not restore packages.config. Full MSBuild must
            # already be present in the approved build toolchain for that style.
            packages=broker.j.project.root/Path(path).parent/'packages.config';safe_path(packages)
            require(not packages.is_file() or native is not None,'legacy-packages-config-requires-trusted-native-msbuild')
        require(native is not None,'legacy-full-msbuild-required')
        exe,env=native
        argv=[exe,path,'-nologo','-m:1','-t:'+('Restore' if phase=='legacy-restore' else 'Build'),'-p:UseSharedCompilation=false']
        if phase=='legacy-restore' and native:argv+=['-p:RestorePackagesConfig=true']
    else:
        require(phase=='test' and framework in gen['projects'][path]['frameworks'],'unknown-automatic-operation')
        sub=gen['projects'][path]['frameworks'][framework]
        if sub.get('kind')=='net-framework':
            require(os.name=='nt' and framework==sub['identifier']+',Version='+sub['version']+(',Profile='+sub['profile'] if sub['profile'] else ''),'legacy-operation-not-authorized')
            target=assembly_target(broker.j.project,path,dict(AssemblyName=Path(sub['target']).stem,TargetPath=sub['target']));safe_path(Path(target));require(Path(target).is_file(),'legacy-test-assembly-missing')
            argv=[exe,'vstest',target,'/Framework:'+framework,'/TestAdapterPath:'+str(Path(target).parent),'/Logger:trx;LogFileName=harness.trx','/ResultsDirectory:{artifacts}/trx']
        else:argv=[exe,'test',path,'--framework',framework,'--logger','trx;LogFilePrefix=harness','--results-directory','{artifacts}/trx','-m:1','-p:UseSharedCompilation=false','-p:TestTfmsInParallel=false']
    return dict(kind='test' if phase=='test' else 'build',argv=argv,result=dict(format='trx' if phase=='test' else 'exit',path=''),rerun_safe=False,env=env,automatic=op)

def properties(log):
    decoder=json.JSONDecoder()
    for match in re.finditer(r'\{',log):
        try:value,end=decoder.raw_decode(log[match.start():])
        except ValueError:continue
        if isinstance(value,dict) and set(value)=={'Properties'} and isinstance(value['Properties'],dict) and not log[match.start()+end:].strip():
            props=value['Properties'];require(set(props) in (SDK_PROPERTIES,PROPERTIES) and all(isinstance(v,str) for v in props.values()),'invalid-msbuild-test-properties');return props
    raise KnowledgeError('invalid-msbuild-test-properties')

def trx_result(path,action,target,root):
    safe_path(path);require(path.is_file() and path.stat().st_size<=2000000,'missing-or-oversized-test-artifact')
    doc=ET.parse(path).getroot();require(doc.tag.rsplit('}',1)[-1]=='TestRun' and bool(doc.get('id')),'invalid-trx')
    times=doc.find('./{*}Times');counter=doc.find('./{*}ResultSummary/{*}Counters');result=doc.find('./{*}ResultSummary')
    require(times is not None and counter is not None and result.get('outcome') in ('Completed','Passed','Failed','NotExecuted','Aborted','Error','Timeout'),'invalid-trx')
    start=datetime.fromisoformat(times.attrib['start']);finish=datetime.fromisoformat(times.attrib['finish']);require(start.tzinfo is not None and finish.tzinfo is not None,'trx-timezone-required')
    require(action['process_started']-2<=start.timestamp()<=finish.timestamp()<=action['process_finished']+2 and path.stat().st_mtime>=action['process_started']-2,'stale-trx')
    counts={k:int(v) for k,v in counter.attrib.items()};require(all(v>=0 for v in counts.values()),'invalid-trx-counts')
    rows=doc.findall('./{*}Results/{*}UnitTestResult');definitions=doc.findall('./{*}TestDefinitions/{*}UnitTest');known={d.get('id'):d for d in definitions}
    require(None not in known and len(known)==len(definitions) and len({v.get('executionId') for v in rows})==len(rows) and all(v.get('executionId') for v in rows),'invalid-trx-identities')
    expected=Path(target);safe_path(expected);expected=Path(os.path.abspath(expected));safe_path(expected);require(expected.is_relative_to(root) and expected.is_file(),'test-assembly-outside-project-root-or-missing')
    # VSTest lowercases storage on some platforms. Compare to the exact evaluated
    # assembly, never infer identity from an arbitrary report basename.
    def same(value,storage=False):
        if not value:return False
        if value.startswith('file:'):
            from urllib.parse import urlsplit,unquote
            from urllib.request import url2pathname
            uri=urlsplit(value)
            if uri.netloc not in ('','localhost') or uri.query or uri.fragment:return False
            value=url2pathname(unquote(uri.path))
        if not storage and len(Path(value).parts)==1:return os.path.normcase(value)==os.path.normcase(expected.name)
        observed=os.path.abspath(value).replace('\\','/');wanted=str(expected).replace('\\','/')
        return observed.casefold()==wanted.casefold() if storage else os.path.normcase(observed)==os.path.normcase(wanted)
    for row in rows:
        require(row.get('testId') in known,'trx-result-definition-mismatch');definition=known[row.get('testId')];method=definition.find('./{*}TestMethod')
        require(same(definition.get('storage'),True) and method is not None and same(method.get('codeBase')),'trx-project-identity-mismatch')
    success=result.get('outcome') in ('Completed','Passed') and counts.get('executed',0)>0 and counts.get('executed')==counts.get('total')==counts.get('passed')==len(rows) and all(v.get('outcome')=='Passed' for v in rows) and all(v==0 for k,v in counts.items() if k not in ('total','executed','passed'))
    with expected.open('rb') as assembly:assembly_sha=hashlib.file_digest(assembly,'sha256').hexdigest()
    return dict(ok=success,run_id=doc.get('id'),counts=dict(executed=counts.get('executed',0),passed=counts.get('passed',0),failed=counts.get('failed',0),skipped=counts.get('notExecuted',0)),artifact=dict(path=str(path.relative_to(root)),sha256=rt.blob(path.read_bytes())),assembly_sha256=assembly_sha)

def parse_result(broker,recipe,action,log,log_path,success):
    op=recipe['automatic'];result=dict(automatic=op,inventory=broker.r['automatic_tests']['inventory']['identity'],log_sha256=rt.blob(log_path.read_bytes()))
    if not success and op['phase']!='test':return dict(**result,counts=None,artifact=None)
    if op['phase'] in ('inspect','inspect-native'):return dict(**result,properties=properties(log),counts=None,artifact=None)
    if op['phase'] in ('restore','legacy-restore','legacy-build'):return dict(**result,counts=None,artifact=None)
    folder=log_path.parent/'trx';safe_path(folder);paths=list(folder.rglob('*.trx')) if folder.is_dir() else []
    require(len(paths)==1,'missing-or-ambiguous-trx-reports')
    gen=broker.r['automatic_tests']['generations'][op['generation']];target=gen['projects'][op['project']]['frameworks'][op['framework']]['target']
    parsed=trx_result(paths[0],action,target,broker.j.project.root);parsed['ok']=success and parsed['ok']
    return dict(**result,**parsed)

def verify(j,c,r,lease,item,attempt,enabled=True):
    from .tools import Broker
    state=r['automatic_tests'];guard(j.project,c,r);gid=digest([state['inventory']['identity'],digest(r['source']),item,attempt]);state['active']=gid
    gen=state['generations'].setdefault(gid,dict(source=digest(r['source']),metadata_version=2,status='RUNNING',projects={p['path']:dict(status='NOT_RUN',frameworks={},actions=[]) for p in state['inventory']['projects']}))
    broker=Broker(j,c,r,lease)
    def persist(status=None):
        if status:gen['status']=status
        for row in gen['projects'].values():row['counts']={key:sum(f.get('receipt',{}).get('counts',{}).get(key,0) for f in row['frameworks'].values() if f.get('receipt',{}).get('counts')) for key in ('executed','passed','failed','skipped')}
        r['gates'][GATE]=dict(ok=gen['status']=='PASS',kind='automatic-test-suite',source=gen['source'],config=r['config_hash'],inventory=state['inventory']['identity'],count=state['inventory']['count'],counts={key:sum(f.get('receipt',{}).get('counts',{}).get(key,0) for p in gen['projects'].values() for f in p['frameworks'].values() if f.get('receipt',{}).get('counts')) for key in ('executed','passed','failed','skipped')},projects=deepcopy(gen['projects']),output=gen.get('error',gen['status']))
        j.save(r)
    def command(path,phase,framework=None):
        guard(j.project,c,r);require(not j.cancelled(r['id']),'cancelled');require(rt.stamp()-r['started']<=broker.limits['elapsed_seconds'],'elapsed-budget-exhausted');require(digest(rt.config(j.project.root))==r['config_hash'],'configuration-changed-revalidation-required')
        if 'entry_authority' in r:
            from .companion import validate_entry
            validate_entry(j.project.root,r['entry_authority'],{k:v for k,v in r['task'].items() if k!='initial_source'},c)
        name=register(j,r,gid,path,phase,framework);aid=digest(['automatic-verifier',r['id'],name]);row=gen['projects'][path]
        if aid not in row['actions']:row['actions'].append(aid)
        event=next((v for v in r['p4']['verifiers'] if v['action']==aid),None)
        if event is None:
            event=dict(action=aid,item=item,attempt=attempt,deterministic=True,source=gen['source'],config=r['config_hash'],inventory=state['inventory']['identity'],project=path,phase=phase,framework=framework,state='INTENT');r['p4']['verifiers'].append(event)
        persist();rt.fault('automatic-verifier-intent')
        answer=broker.execute('Testing' if phase=='test' else 'Building',aid,'recipe',dict(name=name));event.update(state='RECEIPT',ok=answer.get('ok'),receipt_hash=digest(answer));persist();rt.fault('automatic-verifier-receipt')
        if answer.get('error') in ('recipe-outcome-unknown','unverifiable-process-ownership','recipe-still-running'):raise KnowledgeError(answer['error'])
        require(not j.cancelled(r['id']),'cancelled');return answer
    try:
        if not enabled:gen['error']='configured-build-failed';persist('NOT_RUN');return r['gates'][GATE]
        if not gen['projects']:gen['error']='no-test-projects-discovered';persist('FAIL');return r['gates'][GATE]
        for entry in state['inventory']['projects']:
            path=entry['path'];row=gen['projects'][path]
            row['status']='RUNNING';persist()
            answer=command(path,'restore')
            if answer.get('ok'):answer=command(path,'inspect')
            if not answer.get('ok') and native_msbuild(c,r['task']['recipes']) is not None:answer=command(path,'inspect-native')
            if not answer.get('ok'):row.update(status='FAIL',error=answer.get('error',answer.get('output','restore-or-inspect-failed')));gen['error']=path+': '+row['error'];persist('FAIL');return r['gates'][GATE]
            props=answer['properties'];resolved=resolve_frameworks(props)
            for fw,descriptor in resolved:row['frameworks'].setdefault(fw,dict(status='NOT_RUN',**descriptor))
            persist()
            for fw,sub in row['frameworks'].items():
                info=props
                if sub.get('kind')=='net-framework':
                    sub['target']=assembly_target(j.project,path,props)
                    answer=command(path,'legacy-restore',fw)
                    if answer.get('ok'):answer=command(path,'legacy-build',fw)
                    if not answer.get('ok'):
                        code='legacy-reference-assemblies-missing' if 'MSB3644' in answer.get('output','') else answer.get('error','legacy-build-or-restore-prerequisite-failed')
                        sub.update(status='FAIL',error=code,receipt=answer);break
                    # Re-evaluate the built target without synthesizing a TFM.
                    answer=command(path,'inspect-native' if native_msbuild(c,r['task']['recipes']) else 'inspect')
                    require(answer.get('ok') and resolve_frameworks(answer['properties'])==resolved,'legacy-framework-or-target-changed')
                    info=answer['properties']
                elif props.get('TargetFramework')!=fw:
                    answer=command(path,'inspect',fw)
                    if not answer.get('ok'):sub.update(status='FAIL',error=answer.get('error','test-target-inspection-failed'));break
                    info=answer['properties']
                require(sub.get('kind')=='net-framework' or info.get('TargetFramework')==fw,'unresolved-test-assembly')
                target=assembly_target(j.project,path,info)
                sub['target']=str(target);sub['status']='RUNNING';persist();answer=command(path,'test',fw);sub.update(status='PASS' if answer.get('ok') else 'FAIL',receipt=answer)
                persist()
                if not answer.get('ok'):break
            if any(v['status']!='PASS' for v in row['frameworks'].values()):
                row['status']='FAIL';gen['error']=path+': '+next((v['error'] for v in row['frameworks'].values() if v.get('error')),'test-project-failed');persist('FAIL');return r['gates'][GATE]
            row['status']='PASS';persist()
        guard(j.project,c,r);persist('PASS');return r['gates'][GATE]
    except KnowledgeError as e:
        for row in gen['projects'].values():
            if row['status']=='RUNNING':
                row['status']='INTERRUPTED' if any(j.action(r['id'],aid).get('process_spec') for aid in row['actions']) else 'NOT_RUN'
                row['error']=e.code
            for sub in row['frameworks'].values():
                if sub['status']=='RUNNING':sub.update(status='INTERRUPTED',error=e.code)
        gen['error']=e.code;persist('BLOCKED' if 'unknown' in e.code or 'revalidation' in e.code else 'INTERRUPTED');raise

def final_gate(r):
    if 'automatic_tests' not in r:return
    gate=r['gates'].get(GATE,{})
    require(gate.get('ok') is True and gate.get('source')==digest(r['source']) and gate.get('config')==r['config_hash'] and gate.get('inventory')==r['automatic_tests']['inventory']['identity'],'automatic-test-suite-missing-failed-or-stale')


def validate_cached(broker,action):
    """A persisted receipt is reusable only while its owned evidence still agrees."""
    result=action['result'];recipe=recipe_for(broker,action['args']['name'])
    if not action.get('process_result'):return
    try:
        log_path=Path(action['process_spec']['log']);safe_path(log_path)
        require(log_path.is_relative_to(broker.j.base/'artifacts'/broker.r['id']) and log_path.is_file() and rt.blob(log_path.read_bytes())==result.get('log_sha256'),'automatic-test-artifact-changed')
        if result.get('ok') and recipe['automatic']['phase']=='test':
            parsed=parse_result(broker,recipe,action,log_path.read_text(encoding='utf-8',errors='replace'),log_path,True)
            require(parsed.get('ok') and parsed.get('artifact')==result.get('artifact') and parsed.get('counts')==result.get('counts') and parsed.get('assembly_sha256')==result.get('assembly_sha256'),'automatic-test-artifact-changed')
    except (KnowledgeError,OSError,ValueError,KeyError,ET.ParseError) as e:raise KnowledgeError('automatic-test-artifact-changed') from e


def inspect(root):
    project=Project(root);configuration=rt.config(root) if (project.root/'.harness/runner.json').is_file() else None
    return discover(project,{**rt.DEFAULT_LIMITS,**(configuration['limits'] if configuration else {})}['file_bytes'])


def validate_final_evidence(j,c,r,lease):
    if 'automatic_tests' not in r:return
    guard(j.project,c,r);final_gate(r)
    from .tools import Broker
    broker=Broker(j,c,r,lease);state=r['automatic_tests'];gen=state['generations'][state['active']]
    try:
        for row in gen['projects'].values():
            for aid in row['actions']:
                action=j.action(r['id'],aid)
                if action and action.get('result',{}).get('ok'):validate_cached(broker,action)
    except KnowledgeError as e:
        gen.update(status='INVALID',error=e.code);r['gates'][GATE].update(ok=False,output=e.code);j.save(r);raise


def driver_alive(journal,run_id):
    from .platform import compatible,process_info
    owner=journal.load(run_id).get('automatic_tests',{}).get('driver_owner')
    if not owner:return False
    require(compatible(owner),'unverifiable-process-ownership')
    current=process_info(owner['pid'])
    return bool(current and current['start']==owner['start'])
