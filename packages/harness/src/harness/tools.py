"""Runtime role authority, scoped edits and configured process recipes."""
from copy import deepcopy
import fnmatch
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from knowledge.util import require,KnowledgeError,canonical_json,loads,digest
from knowledge.project import safe_path
from . import runtime as rt
from .runtime import TOOLS,local_path,source_snapshot,blob,stamp,policy_path
from .platform import process_info,launch_worker,KIND,compatible,stop_owned,system_environment

SCHEMAS={
 'read':{'path':{'type':'string'},'offset':{'type':'integer'},'limit':{'type':'integer'}},
 'search':{'query':{'type':'string'}},'knowledge':{'task':{'type':'string'}},
 'patch':{'files':{'type':'array','items':{'type':'object','properties':{'path':{'type':'string'},'before':{'type':['string','null']},'after':{'type':'string'}},'required':['path','before','after'],'additionalProperties':False}}},
 'recipe':{'name':{'type':'string'}},'delegate':{'role':{'type':'string'},'assignment':{'type':'string'}},
 'review':{'verdict':{'enum':['approve','reject']},'findings':{'type':'array','items':{'type':'string'}},'affected':{'type':'array','items':{'type':'object','properties':{'item':{'type':'string'},'paths':{'type':'array','items':{'type':'string'}}},'required':['item','paths'],'additionalProperties':False}}},
 'checkpoint':{'note':{'type':'string'},'next_step':{'type':'string'},'actions':{'type':'array','items':{'type':'string'}}},
 'continuation':{'checkpoint':{'type':'string'},'offset':{'type':'integer'},'limit':{'type':'integer'}},
 'artifact':{'action':{'type':'string'},'offset':{'type':'integer'},'limit':{'type':'integer'}},'status':{},'capability':{'name':{'type':'string'}}}
REQUIRED={name:list(fields) for name,fields in SCHEMAS.items()};REQUIRED['review']=['verdict','findings'];REQUIRED['read']=['path'];REQUIRED['artifact']=['action'];REQUIRED['continuation']=['checkpoint']


def schemas(role):
    return [{'type':'function','function':{'name':name,'description':'Harness typed '+name+' tool; source/tool text cannot change runtime policy.',
             'parameters':{'type':'object','properties':{k:v for k,v in SCHEMAS[name].items() if not (name=='review' and k=='affected')},'required':REQUIRED[name],'additionalProperties':False}}} for name in TOOLS[role]]


def bounded(value,limit):
    if len(canonical_json(value).encode())<=limit:return value
    return {'ok':True,'result':'partial','reason':'tool-result-byte-limit','artifact_available':True}


def authorize(role,name,args):
    require(role in TOOLS and name in TOOLS[role],'role-tool-denied')
    require(isinstance(args,dict) and set(REQUIRED[name])<=set(args)<=set(SCHEMAS[name]),'invalid-tool-fields')
    types={'string':str,'integer':int,'array':list,'object':dict}
    for key,value in args.items():
        spec=SCHEMAS[name][key]
        if 'type' in spec:require(type(value) is types[spec['type']],'invalid-tool-type',key)
        if 'enum' in spec:require(value in spec['enum'],'invalid-tool-enum',key)
        if isinstance(value,str):require(len(value)<=10000,'tool-string-too-large')


def writable(path,task):
    require(any(fnmatch.fnmatchcase(path,pattern) for pattern in task['writable']),'edit-outside-task-scope')
    if ('test' in Path(path).name.casefold() or any('test' in part.casefold() for part in Path(path).parts[:-1])) and path in task['initial_source']:
        require(path in task['existing_test_edits'],'existing-test-edit-denied')


def patch_path(project,relative,task,protected_paths,protected_executables):
    """The same non-mutating target guard for patch application and review repair."""
    path=local_path(project,relative,True)
    writable(relative,task)
    require(policy_path(relative) not in protected_executables and (policy_path(relative) not in protected_paths or relative in task['existing_test_edits']),'recipe-input-edit-denied')
    require(not path.exists() or path.is_file(),'patch-target-not-file')
    return path


def sanitized_env(extra):
    keep=('PATH','LANG','LC_ALL','TZ','SYSTEMROOT','TMPDIR','HTTPS_PROXY','HTTP_PROXY','ALL_PROXY','NO_PROXY','https_proxy','http_proxy','all_proxy','no_proxy','SSL_CERT_FILE','REQUESTS_CA_BUNDLE')
    if os.name=='nt':keep+=('TEMP','TMP','LOCALAPPDATA','APPDATA','USERPROFILE','PROGRAMFILES','PROGRAMFILES(X86)','PROGRAMW6432','PROGRAMDATA','WINDIR','PROCESSOR_ARCHITECTURE')
    return {**system_environment(),**{k:os.environ[k] for k in keep if k in os.environ},**extra,'PYTHONUNBUFFERED':'1','PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'}


class Broker:
    def __init__(self,journal,configuration,run,lease):self.j=journal;self.c=configuration;self.r=run;self.lease=lease;self.limits={**rt.DEFAULT_LIMITS,**configuration['limits']}
    def execute(self,role,action_id,name,args):
        if 'automatic_tests' in self.r and name=='test_inventory':
            require(role in ('Main','Planning','Coding','Reviewing','Testing') and isinstance(args,dict) and set(args)<={'offset','limit'},'role-tool-denied')
            from .testing import summary
            summary(self.r,**args)
        elif self.r.get('p4') and name in ('checkpoint','continuation'):
            from .p4 import authorize_memory
            authorize_memory(role,name,args,self.limits)
        elif self.r.get('p4') and role in ('Main','Planning','Coding') and name=='artifact':authorize('Reviewing',name,args)
        else:authorize(role,name,args)
        previous=self.j.action(self.r['id'],action_id)
        signature=digest({'role':role,'tool':name,'args':args})
        if previous:
            require(previous['signature']==signature,'tool-action-identity-conflict')
            if previous['status']=='FINISHED':
                if name=='knowledge' and self.r.get('p4'):return current_knowledge(previous['result'])
                if name=='recipe' and args['name'].startswith('@automatic-tests/'):
                    from .testing import validate_cached
                    validate_cached(self,previous)
                return previous['result']
        else:
            previous={'version':1,'status':'INTENT','role':role,'tool':name,'args':deepcopy(args),'signature':signature,'at':stamp(),'agent':getattr(self,'agent_id',None),'request':getattr(self,'request_id',None)}
            self.j.action(self.r['id'],action_id,previous)
        rt.fault('tool-intent')
        try:
            if name in ('patch','recipe') and self.r.get('host_session'):
                from .host_ingress import guard
                guard(self.j.project.root,self.r['host_session'],name)
            if name in ('checkpoint','continuation'):
                from .p4 import memory_tool
                result=memory_tool(self,name,args)
            elif name=='patch':result=self.patch(action_id,previous)
            elif name=='recipe':result=self.recipe(role,action_id,previous)
            elif name=='read':
                path=local_path(self.j.project,args['path']);require(path.is_file(),'file-not-found')
                offset=args.get('offset',0);limit=args.get('limit',self.limits['tool_bytes']//2)
                require(type(offset) is int and offset>=0 and type(limit) is int and 0<limit<=self.limits['tool_bytes']//2,'invalid-read-bound')
                require(path.stat().st_size<=self.limits['file_bytes'],'read-file-too-large')
                from .instructions import decode_edit
                raw=path.read_bytes();text=decode_edit(raw);result={'ok':True,'path':args['path'],'sha256':blob(raw),'text':text[offset:offset+limit],'partial':len(text)>offset+limit}
            elif name=='search':
                require(isinstance(args['query'],str) and 0<len(args['query'])<=200,'invalid-search')
                matches=[]
                for path in self.r['source']:
                    try:
                        p=local_path(self.j.project,path)
                        for number,line in enumerate(p.read_text(encoding='utf-8-sig').splitlines(),1):
                            if args['query'].casefold() in line.casefold():matches.append({'path':path,'line':number,'excerpt':line[:250]})
                    except (KnowledgeError,OSError,UnicodeError):continue
                    if len(matches)>=20:break
                result={'ok':True,'matches':matches[:20],'partial':len(matches)>20}
            elif name=='knowledge':
                result=knowledge(self.j.project.root,args['task'],self.limits['tool_bytes'])
                if self.r.get('p4'):result=current_knowledge(result)
            elif name=='artifact':
                action=self.j.action(self.r['id'],args['action']);require(action is not None,'unknown-artifact');result={'ok':True,'action':args['action'],'receipt':action.get('result',{}),'signature':action['signature']}
                if action['tool']=='recipe' and action.get('process_spec'):
                    offset=args.get('offset',0);limit=args.get('limit',1000)
                    require(type(offset) is int and offset>=0 and type(limit) is int and 0<limit<=self.limits['tool_bytes']//2,'invalid-artifact-range')
                    path=Path(action['process_spec']['log']);safe_path(path)
                    require(path.is_relative_to(self.j.base/'artifacts'/self.r['id']) and path.stat().st_size<=self.limits['log_bytes'],'invalid-artifact-path')
                    raw=path.read_bytes();result['log_excerpt']=raw[offset:offset+limit].decode('utf-8',errors='replace');result['log_sha256']=blob(raw);result['size']=len(raw)
                if action['tool']=='patch':
                    result['receipt']={k:v for k,v in result['receipt'].items() if k!='after_source'}
                    import difflib
                    result['diff']=''.join(''.join(difflib.unified_diff(action['edit_intent']['before_text'][f['path']].splitlines(True),f['after'].splitlines(True),fromfile=f['path'],tofile=f['path'])) for f in action['args']['files'])[:self.limits['tool_bytes']//2]
            elif name=='test_inventory':
                from .testing import summary
                result=summary(self.r,**args)
            elif name=='status':
                result={'ok':True,'gates':deepcopy(self.r['gates']),'agents':[{'id':a['id'],'role':a['role'],'status':a['status']} for a in self.r['agents']]}
                if 'automatic_tests' in self.r:
                    from .testing import GATE,summary
                    result['gates'][GATE]=summary(self.r)
            elif name=='capability':result={'ok':True,'name':args['name'],'available':False,'reason':'optional specialist/host adapter not installed; no permission expansion'}
            elif name=='review':
                require(self.r.get('p4') or 'affected' not in args,'legacy-review-fields')
                if self.r.get('p4'):
                    from .p4 import validate_affected
                    validate_affected(self.r,args.get('affected',[]),self.j.project)
                require(args['verdict'] in ('approve','reject') and isinstance(args['findings'],list) and len(args['findings'])<=20 and all(isinstance(f,str) and len(f)<=1000 for f in args['findings']),'invalid-review')
                result={'ok':True,**args,'source':digest(source_snapshot(self.j.project,self.limits['file_bytes'])),'config':self.r['config_hash']}
            else:raise KnowledgeError('coordinator-tool-requires-runtime-dispatch')
        except (KnowledgeError,OSError,UnicodeError,ValueError,TypeError,KeyError,ET.ParseError) as e:
            result={'ok':False,'error':getattr(e,'code','tool-filesystem-error'),'details':getattr(e,'details',None)}
        if not result['ok'] and name in ('patch','recipe'):
            from .instructions import after_error
            after_error(self,action_id,name,args)
        previous=self.j.action(self.r['id'],action_id) or previous
        previous.update(status='FINISHED',result=result,finished=stamp());self.j.action(self.r['id'],action_id,previous)
        self.j.event(self.r['id'],'tool-finished',action=action_id,role=role,tool=name,ok=result['ok'])
        rt.fault('tool-receipt')
        return result
    def patch(self,action_id,action):
        require(self.r['task']['kind']=='coding','read-only-task')
        files=action['args']['files'];require(isinstance(files,list) and 0<len(files)<=20,'invalid-patch-list')
        if 'edit_intent' not in action:
            before=source_snapshot(self.j.project,self.limits['file_bytes']);require(before==self.r['source'],'source-conflict')
            seen=set()
            for f in files:
                require(isinstance(f,dict) and set(f)=={'path','before','after'} and isinstance(f['path'],str) and f['path'] not in seen,'invalid-patch-fields');seen.add(f['path'])
                path=patch_path(self.j.project,f['path'],self.r['task'],self.r['protected_paths'],self.r.get('protected_executables',[]))
                require(isinstance(f['after'],str) and len(f['after'].encode())<=self.limits['file_bytes'],'patch-too-large')
                require(before.get(f['path'])==f['before'],'edit-before-state-mismatch')
            from .instructions import preflight,encode_edit,decode_edit,current_formats
            preflight(self,action_id,'patch',action['args'])
            exceptions=[f['path'] for f in files if f['path'] in self.r['task']['existing_test_edits']]
            if exceptions:self.j.event(self.r['id'],'explicit-test-edit-authorized',action=action_id,paths=exceptions)
            # Refresh after the gateway persisted its trace. Intended bytes are
            # journaled before any write, so recovery cannot re-encode an edit.
            action=self.j.action(self.r['id'],action_id)
            raw_before={f['path']:local_path(self.j.project,f['path']).read_bytes() if local_path(self.j.project,f['path']).exists() else b'' for f in files}
            formats=current_formats(self)
            raw_after={f['path']:(encode_edit(raw_before[f['path']],f['after'],formats.get(policy_path(f['path'])),f['before'] is not None) if (f['path'] in self._preserve_paths and f['before'] is not None) or policy_path(f['path']) in formats else f['after'].encode()).hex() for f in files}
            if action.get('memory_traces'):action['memory_traces'][-1]['current_format_overrides']=[{'path':f['path'],**formats[policy_path(f['path'])]} for f in files if policy_path(f['path']) in formats]
            action['edit_intent']={'before_source':before,'files':files,'before_text':{p:decode_edit(raw) for p,raw in raw_before.items()},'after_bytes':raw_after};self.j.action(self.r['id'],action_id,action)
        intent=action['edit_intent'];current=source_snapshot(self.j.project,self.limits['file_bytes']);paths={f['path'] for f in files}
        intended={f['path']:bytes.fromhex(intent['after_bytes'][f['path']]) if 'after_bytes' in intent else f['after'].encode() for f in files}
        require({k:v for k,v in current.items() if k not in paths}=={k:v for k,v in intent['before_source'].items() if k not in paths},'unrelated-source-conflict')
        for f in files:
            require(current.get(f['path']) in (f['before'],blob(intended[f['path']])),'edit-recovery-conflict',f['path'])
        rt.fault('edit-intent')
        written=[];reconciled=[]
        for f in files:
            path=patch_path(self.j.project,f['path'],self.r['task'],self.r['protected_paths'],self.r.get('protected_executables',[]))
            actual=blob(path.read_bytes()) if path.exists() else None;after=blob(intended[f['path']])
            if actual==after:reconciled.append(f['path']);continue
            require(actual==f['before'],'edit-recovery-conflict',f['path'])
            path.parent.mkdir(parents=True,exist_ok=True);safe_path(path.parent)
            fd,tmp=tempfile.mkstemp(prefix='.harness-edit-',dir=path.parent)
            try:
                with os.fdopen(fd,'wb') as out:out.write(intended[f['path']]);out.flush();os.fsync(out.fileno())
                os.replace(tmp,path)
            finally:
                if os.path.exists(tmp):os.unlink(tmp)
            written.append(f['path']);rt.fault('edit-file-written')
        return {'ok':True,'written':written,'reconciled':reconciled,'after_source':source_snapshot(self.j.project,self.limits['file_bytes'])}
    def memory_command(self,action_id,argv,timeout,rerun_safe,parent_id,record_id):
        """Private policy-checked handoff to the existing owned supervisor."""
        action=self.j.action(self.r['id'],action_id)
        recipe={'kind':'build','argv':argv,'result':{'format':'exit','path':''},'rerun_safe':rerun_safe,'env':{}}
        signature=digest(recipe)
        if action:
            require(action['signature']==signature,'memory-action-identity-conflict')
            if action['status']=='FINISHED':return action['result']
        else:
            action={'version':1,'status':'INTENT','role':'Building','tool':'recipe','args':{'name':'@memory/'+action_id},'signature':signature,'at':stamp(),'memory_parent':parent_id,'memory_record':record_id}
            self.j.action(self.r['id'],action_id,action)
        result=self.recipe('Building',action_id,action,_owned_recipe=recipe,_timeout=timeout)
        action=self.j.action(self.r['id'],action_id);action.update(status='FINISHED',result=result,finished=stamp());self.j.action(self.r['id'],action_id,action)
        self.j.event(self.r['id'],'memory-command-finished',action=action_id,parent=parent_id,ok=result['ok'])
        return result
    def recipe(self,role,action_id,action,*,_owned_recipe=None,_timeout=None):
        name=action['args']['name']
        if _owned_recipe is not None:recipe=_owned_recipe
        elif name.startswith('@automatic-tests/'):
            from .testing import recipe_for
            recipe=recipe_for(self,name)
        else:
            require(name in self.c['recipes'],'unknown-recipe');recipe=self.c['recipes'][name]
        require(role==('Building' if recipe['kind']=='build' else 'Testing'),'recipe-role-denied')
        require(_owned_recipe is not None or 'automatic' in recipe or name in self.r['task']['recipes'],'recipe-not-in-task')
        if _owned_recipe is None and 'process_result' not in action:
            from .instructions import preflight
            preflight(self,action_id,'recipe',action['args'])
            action=self.j.action(self.r['id'],action_id)
        source=source_snapshot(self.j.project,self.limits['file_bytes']);require(source==self.r['source'],'source-conflict')
        attempt=action.get('process_attempt',0)
        if action.get('process_spec') and not action.get('process_result'):
            info=action.get('process');current=process_info(info['pid']) if info else None
            if info:require(compatible(info),'unverifiable-process-ownership')
            require(current is None or current['start']!=info['start'],'recipe-still-running')
            require(recipe['rerun_safe'],'recipe-outcome-unknown')
            action.setdefault('process_history',[]).append({'state':'unknown','process_spec':action['process_spec'],'process':action.get('process'),'child_process':action.get('child_process'),'job_name':action.get('job_name'),'process_platform':action.get('process_platform'),'started':action.get('process_started')})
            attempt+=1
        if 'process_result' not in action:
            for field in ('process','child_process','process_started','process_finished','recovery_stop'):action.pop(field,None)
            artifacts=self.j.base/'artifacts'/self.r['id']/action_id/str(attempt);safe_path(artifacts);artifacts.mkdir(parents=True,exist_ok=True)
            argv=list(recipe['argv']) if _owned_recipe is not None else [a.replace('{artifacts}',str(artifacts)) for a in recipe['argv']]
            require(_owned_recipe is not None or not any('{' in a or '}' in a for a in argv),'unknown-recipe-placeholder')
            action.update(process_attempt=attempt,process_spec={'argv':argv,'cwd':str(self.j.project.root),'log':str(artifacts/'process.log'),'timeout':min(self.limits['recipe_seconds'],max(.1,self.limits['elapsed_seconds']-(stamp()-self.r['started']))),'log_bytes':self.limits['log_bytes']},source_before=source)
            if _timeout is not None:action['process_spec']['timeout']=min(action['process_spec']['timeout'],_timeout)
            action['process_platform']=KIND
            if os.name=='nt':
                import uuid
                action['job_name']='Local\\Knowledge-'+uuid.uuid4().hex
            self.j.action(self.r['id'],action_id,action)
            env=sanitized_env(recipe['env']);env['HARNESS_ACTION_ID']=action_id
            worker=launch_worker([sys.executable,'-I','-m','harness.process_worker','--root',str(self.j.project.root),'--run',self.r['id'],'--action',action_id,'--lease-fd',str(self.lease.fd)],env,self.lease)
            while worker.poll() is None:time.sleep(.05)
            action=self.j.action(self.r['id'],action_id)
            require('process_result' in action,'recipe-outcome-unknown')
        process=action['process_result'];log_path=Path(action['process_spec']['log']);safe_path(log_path)
        log=log_path.read_text(encoding='utf-8',errors='replace') if log_path.exists() else ''
        result_path=recipe['result']['path'].replace('{artifacts}',str(log_path.parent))
        success=process['returncode']==0 and process['reason'] is None
        counts=None;artifact=None
        automatic={}
        if 'automatic' in recipe:
            from .testing import parse_result
            automatic=parse_result(self,recipe,action,log,log_path,success);success=success and automatic.pop('ok',True);counts=automatic.pop('counts',None);artifact=automatic.pop('artifact',None)
        elif success and recipe['kind']=='test':
            fmt=recipe['result']['format']
            if fmt=='unittest':
                match=re.search(r'Ran (\d+) tests?',log);success=bool(match and int(match[1])>0 and log.rstrip().endswith('OK') and 'skipped=' not in log)
                counts={'executed':int(match[1]) if match else 0}
            else:
                path=Path(result_path);safe_path(path);require(path.is_file() and path.stat().st_size<=2000000,'missing-or-oversized-test-artifact')
                artifact={'path':str(path.relative_to(self.j.project.root)),'sha256':blob(path.read_bytes())}
                if fmt=='trx':
                    tree=ET.parse(path);counter=tree.getroot().find('.//{*}Counters');require(counter is not None,'invalid-trx')
                    counts={k:int(v) for k,v in counter.attrib.items()};success=counts.get('executed',0)>0 and counts.get('executed')==counts.get('passed')==counts.get('total') and counts.get('failed',0)==0 and counts.get('notExecuted',0)==0
                    created=tree.getroot().find('.//{*}Times')
                    require(created is not None,'trx-timestamps-required')
                    if created is not None:
                        from datetime import datetime
                        require(datetime.fromisoformat(created.attrib['start']).timestamp()>=action['process_started']-2,'stale-trx')
                else:
                    data=loads(path.read_text(encoding='utf-8'));require(data.get('action')==action_id,'test-artifact-identity-mismatch')
                    counts={'executed':data.get('executed',0),'failed':data.get('failed',0)};success=data.get('skipped',0)==0 and type(counts['executed']) is int and counts['executed']>0 and type(counts['failed']) is int and counts['failed']==0
        after=source_snapshot(self.j.project,self.limits['file_bytes'])
        require(after==action['source_before'],'source-changed-during-gate')
        return {'ok':bool(success),'recipe':name,'kind':recipe['kind'],'source':digest(after),'config':self.r['config_hash'],'counts':counts,'artifact':artifact,'output':log[-min(self.limits['tool_bytes']//2,4000):],'log':str(log_path.relative_to(self.j.project.root)),**process,**automatic}


def current_knowledge(value):
    """One P4-facing current-fact boundary, also for cached tool receipts."""
    claims=value.get('context',{}).get('claims',[])
    if any(c.get('revision') is None or not c.get('current',{}).get('freshness',{}).get('trusted') for c in claims):
        return {'ok':True,'available':False,'partial':True,'reason':'knowledge-lifecycle-upgrade-required',
            'next':'Upgrade/review supporting evidence through the supported Knowledge lifecycle before current architectural delivery.'}
    return value


def knowledge_history(history):
    """Project old paired Knowledge messages before a NEW P4 request only.

    Durable history/receipts and already begun provider requests stay unchanged.
    Tool IDs are scoped to their assistant turn (fixtures/hosts may reuse IDs).
    No Store lookup or inference is needed to withhold unverified legacy text.
    """
    messages=[]
    for chunk in deepcopy(history):
        names={}
        for message in chunk:
            if message['role']=='assistant':names={c['id']:c['function']['name'] for c in message.get('tool_calls',[])}
            elif message['role']=='tool' and names.get(message.get('tool_call_id'))=='knowledge':
                message['content']=canonical_json(current_knowledge(loads(message['content'])))
            messages.append(message)
    return messages


def knowledge(root,task,limit):
    from knowledge.store import Store
    try:
        value=Store(root).context(task,max_bytes=max(256,limit-200))
        return {'ok':True,'available':value.get('result')!='store-absent','reason':'knowledge-absent' if value.get('result')=='store-absent' else None,'context':value}
    except KnowledgeError as e:return {'ok':False,'available':False,'reason':e.code}
