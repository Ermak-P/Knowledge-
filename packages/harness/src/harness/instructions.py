"""Generic deterministic memory gateway; effects stay in the owned broker.

Stored text never supplies a shell command or permission. Each executable
procedure must exactly match an independently approved current policy entry.
"""
from copy import deepcopy
from pathlib import Path
import platform
import fnmatch
import re
import sys
import time
from knowledge import operations as op
from knowledge.util import canonical_json, digest, require, KnowledgeError, loads


def validate_policy(policy):
    require(isinstance(policy,dict) and set(policy)<={'enabled','shared_root','environment','bindings','requirements','allowed_procedures','deny_recovery','max_items','max_bytes','normalizer','teaching_mode','procedure_templates','allowed_templates'},'invalid-memory-policy')
    require(policy.get('teaching_mode','local-model') in ('local-model','catalog'),'invalid-memory-teaching-mode')
    if policy.get('normalizer'):
        from knowledge.normalizer import validate
        validate(policy['normalizer'])
    require(type(policy.get('enabled',True)) is bool,'invalid-memory-enabled')
    if 'shared_root' in policy:op.shared_root(policy['shared_root'])
    op.validate_applicability(policy.get('environment',{}))
    require(type(policy.get('deny_recovery',False)) is bool,'invalid-memory-restriction')
    require(type(policy.get('max_items',8)) is int and 1<=policy.get('max_items',8)<=32 and
        type(policy.get('max_bytes',12000)) is int and 512<=policy.get('max_bytes',12000)<=64000,'invalid-memory-budget')
    for key in ('bindings','requirements','allowed_procedures'):
        require(isinstance(policy.get(key,[]),list) and len(policy.get(key,[]))<=32,'invalid-memory-policy-list')
    for p in policy.get('allowed_procedures',[]):op.validate_procedure(p)
    from knowledge.procedure_templates import validate as validate_template
    require(isinstance(policy.get('procedure_templates',[]),list) and len(policy.get('procedure_templates',[]))<=32,'invalid-procedure-templates')
    for template in policy.get('procedure_templates',[]):validate_template(template)
    ids=[t['id'] for t in policy.get('procedure_templates',[])]
    require(len(ids)==len(set(ids)),'duplicate-procedure-template')
    require(isinstance(policy.get('allowed_templates',[]),list) and all(isinstance(t,str) and t in ids for t in policy.get('allowed_templates',[])),'invalid-allowed-templates')
    for b in policy.get('bindings',[]):
        require(isinstance(b,dict) and {'aliases','trigger'}<=set(b)<={'aliases','trigger','behavior','applicability','description','template'} and ('behavior' in b)!=('template' in b),'invalid-teaching-binding')
        require(isinstance(b['aliases'],list) and 0<len(b['aliases'])<=10 and all(isinstance(a,str) and 1<=len(a)<=200 for a in b['aliases']),'invalid-teaching-alias')
        op.validate_binding(b['trigger'],b.get('behavior',{'adapter':'preserve-format'}));op.validate_applicability(b.get('applicability',{}))
        if 'template' in b:require(b['template'] in ids,'unknown-procedure-template')
        if 'description' in b:require(isinstance(b['description'],str) and 0<len(b['description'])<=1000,'invalid-binding-description')
    for r in policy.get('requirements',[]):
        require(isinstance(r,dict) and {'trigger','dependency'}<=set(r)<={'trigger','dependency','suite'} and isinstance(r['dependency'],str) and 0<len(r['dependency'])<=200,'invalid-memory-requirement')
        op.validate_binding(r['trigger'],{'adapter':'preserve-format'})
        if 'suite' in r:require(isinstance(r['suite'],str) and 0<len(r['suite'])<=500 and not r['suite'].startswith(('/','\\')) and '..' not in r['suite'].split('/') and '\\' not in r['suite'] and ':' not in r['suite'],'invalid-memory-suite')
    return policy


def environment(policy):
    declared=policy.get('environment',{})
    return {**declared,'machine':platform.node(),'os':sys.platform,
        'tools':{**declared.get('tools',{}),'python':platform.python_version()}}


def retrieve(broker, name, args, include_candidates=False):
    policy=broker.c.get('memory',{});env=environment(policy)
    actions=[{'tool':name,'name':args['name']}] if name=='recipe' else [{'tool':name,'name':f['path']} for f in args['files']]
    operation=broker.r.get('automatic_tests',{}).get('operations',{}).get(args.get('name')) if name=='recipe' else None
    source_actions=list(actions)
    links=[]
    for requirement in policy.get('requirements',[]):
        if not any(op.matches(requirement['trigger'],a) for a in source_actions):continue
        if 'suite' in requirement and not (operation and operation['phase']=='test' and fnmatch.fnmatchcase(operation['project'],requirement['suite'])):continue
        dependency={'tool':'dependency','name':requirement['dependency']}
        if dependency not in actions:actions.append(dependency)
        links.append({'dependency':requirement['dependency'],'suite':operation['project'] if operation else None,
            'source':'verified-test-inventory' if operation else 'runner-requirement'})
    lookups=[op.lookup(broker.j.project.root,a,env,shared=policy.get('shared_root'),max_items=policy.get('max_items',8),max_bytes=policy.get('max_bytes',12000),include_candidates=include_candidates) for a in actions]
    records={r['id']:r for result in lookups for r in result['records']}
    require(len(records)<=policy.get('max_items',8),'memory-context-item-limit')
    size=len(canonical_json(list(records.values())).encode());require(size<=policy.get('max_bytes',12000),'memory-context-byte-limit')
    bindings={identifier:value for result in lookups for identifier,value in result.get('bindings',{}).items()}
    return policy,env,list(records.values()),{'lookups':[{'action':a,**{k:v for k,v in result.items() if k!='records'}} for a,result in zip(actions,lookups)],
        'selected':[{'id':r['id'],'revision':r['revision'],'scope':r['scope']} for r in records.values()],
        'selected_bytes':size,'lookup_bytes':sum(r['payload_bytes'] for r in lookups),'binding_states':bindings,'dependency_links':links}


def preflight(broker, action_id, name, args):
    broker._preserve_paths=set()
    if 'memory' not in broker.c or not broker.c['memory'].get('enabled',True):return
    started=time.monotonic()
    policy,env,records,trace=retrieve(broker,name,args)
    trace.update(phase='before-action',outcomes=[],lookup_seconds=time.monotonic()-started)
    # Persist the selection before any effect; errors keep a truthful trace.
    action=broker.j.action(broker.r['id'],action_id)
    action.setdefault('memory_traces',[]).append(trace)
    broker.j.action(broker.r['id'],action_id,action)
    broker._preserve_paths=set()
    try:
        require(not any(result['conflicts'] for result in trace['lookups']),'instruction-conflict')
        require(not any(r['status']=='unbound' for r in records),'instruction-binding-required')
        require(all(any(op.matches(r['trigger'],result['action']) for r in records if r['status']=='active') for result in trace['lookups'] if result['action']['tool']=='dependency'),'required-dependency-instruction-missing')
        for r in sorted(records,key=lambda r: 1 if (r['behavior'] or {}).get('adapter')=='dependency' else 0):
            if r['kind']!='instruction':continue
            behavior=r['behavior']
            if behavior['adapter']=='preserve-format':
                broker._preserve_paths.update(f['path'] for f in args.get('files',[]) if op.matches(r['trigger'],{'tool':'patch','name':f['path']}))
                trace['outcomes'].append({'id':r['id'],'result':'preserve-format'});continue
            p=behavior['procedure']
            from knowledge.procedure_templates import permitted
            require(permitted(policy,behavior),'memory-procedure-tool-denied')
            from knowledge.bindings import validate_saved
            try:validate_saved(r.get('execution_binding'),behavior,broker.j.project.root)
            except KnowledgeError as error:
                op.binding_event(broker.j.project.root,r,policy.get('shared_root'),'blocked',error.code)
                raise
            outcome=execute_procedure(broker,action_id,r,policy,trace['binding_states'].get(r['id'],{}))
            trace['outcomes'].append({'id':r['id'],**outcome})
        trace['ok']=True
    except (KnowledgeError,OSError,ValueError) as error:
        trace.update(ok=False,error=getattr(error,'code','memory-execution-error'))
        raise
    finally:
        trace['total_seconds']=time.monotonic()-started
        action=broker.j.action(broker.r['id'],action_id)
        action['memory_traces'][-1]=trace;broker.j.action(broker.r['id'],action_id,action)
        for r in records:
            if r['kind']=='instruction':
                op.application(broker.j.project.root,r['scope'],policy.get('shared_root'),r['id'],r['revision'],
                    broker.r['id']+'/'+action_id+'/'+str(len(action['memory_traces'])),
                    {'ok':trace.get('ok',False),'error':trace.get('error'),'phase':'before-action'},
                    [{'run':broker.r['id'],'action':action_id}])


def execute_procedure(broker, parent_id, record, policy, binding_state=None):
    p=record['behavior']['procedure'];started=time.monotonic();steps=[]
    binding_state=binding_state or {}
    def signal(state,reason=None,**observed):
        return op.binding_event(broker.j.project.root,record,policy.get('shared_root'),state,reason,**observed)
    parent=broker.j.action(broker.r['id'],parent_id)
    generation=parent.get('memory_generation',0)+1;parent['memory_generation']=generation
    broker.j.action(broker.r['id'],parent_id,parent)
    prefix='memory-'+digest({'parent':parent_id,'rule':record['id'],'revision':record['revision']})[:24]
    def command(label, argv, timeout, rerun_safe=True, fixed=False):
        require(not broker.j.cancelled(broker.r['id']),'cancelled')
        require(time.time()-broker.r['started']<broker.limits['elapsed_seconds'],'memory-elapsed-budget-exhausted')
        identifier=prefix+'-'+(label if fixed else str(generation)+'-'+label)
        require(Path(argv[0]).is_file(),'memory-executable-unavailable',str(argv[0]))
        result=broker.memory_command(identifier,argv,timeout,rerun_safe,parent_id,record['id'])
        steps.append({'action':identifier,'ok':result['ok'],'returncode':result.get('returncode'),'reason':result.get('reason'),'log':result.get('log')})
        return result
    check=p['check']
    def probe(index, remaining):return command('probe'+str(index),check['argv'],min(check['timeout'],max(.1,remaining)))
    require(binding_state.get('reason') not in ('docker-daemon-changed','docker-resource-changed'),
        'instruction-binding-revalidation-required',binding_state.get('reason'))
    first=probe(0,p['deadline'])
    if first['ok']:
        signal('verified')
        return {'result':'ready','started':False,'steps':steps,'seconds':time.monotonic()-started}
    require(record['behavior']['adapter']=='dependency' and 'docker' in p,'memory-precondition-failed',steps)
    require(binding_state.get('state') not in ('blocked','attempted'),'memory-remedy-blocked',binding_state.get('reason'))
    d=p['docker'];docker=d['executable']
    selection=record['execution_binding']['docker']
    def docker_argv(*args):return [docker,'--config',selection['config_root'],'--context',selection['context'],*args]
    def compose_argv(*args):return docker_argv('compose','--project-directory',str(Path(d['compose_file']).parent),'-f',d['compose_file'],
        '--project-name',d['project_name'],'--env-file',d['env_file'],*args)
    info=command('docker-info',docker_argv('info','--format','{"ID":{{json .ID}},"Version":{{json .ServerVersion}}}'),min(5,p['deadline']))
    require(info['ok'],'docker-unavailable',steps)
    identity=loads(info['output'].strip());require(isinstance(identity,dict) and isinstance(identity.get('ID'),str) and identity['ID'],'invalid-docker-identity')
    daemon=digest(identity['ID'])
    if binding_state.get('daemon') and binding_state['daemon']!=daemon:
        signal('blocked','docker-daemon-changed');raise KnowledgeError('docker-daemon-changed')
    if 'container' in d:resource=d['container']
    else:
        result=command('compose-locate',compose_argv('ps','-a','-q',d['service']),min(5,p['deadline']))
        resource=result.get('output','').strip()
        require(result['ok'] and re.fullmatch('[0-9a-f]{12,64}',resource),'docker-resource-missing-or-ambiguous',steps)
    inspected=command('docker-inspect',docker_argv('inspect','--type','container','--format','{"ID":{{json .Id}},"Status":{{json .State.Status}},"Running":{{json .State.Running}}}',resource),min(5,p['deadline']))
    require(inspected['ok'],'docker-resource-missing',steps)
    state=loads(inspected['output'].strip());require(isinstance(state,dict) and type(state.get('Running')) is bool,'invalid-docker-state')
    require(isinstance(state.get('ID'),str) and re.fullmatch('[0-9a-f]{64}',state['ID']),'invalid-docker-resource-identity')
    resource_id=digest(state['ID'])
    if binding_state.get('resource') and binding_state['resource']!=resource_id:
        signal('blocked','docker-resource-changed');raise KnowledgeError('docker-resource-changed')
    require(not state['Running'],'dependency-running-not-ready',steps)
    require(state.get('Status') in ('exited','created'),'dependency-state-not-startable',steps)
    restrictions=list(broker.r.get('current_restrictions',[]))
    if broker.r.get('host_session'):
        from .host_ingress import read_session
        restrictions+=read_session(broker.j.project.root,broker.r['host_session'])['restrictions']
    require(not policy.get('deny_recovery',False) and 'no-service-start' not in restrictions,'current-service-start-denied')
    require(record.get('recovery_authorized') and p['attempts']==1,'remembered-start-not-authorized')
    from knowledge.bindings import validate_saved
    validate_saved(record['execution_binding'],record['behavior'],broker.j.project.root)
    # Pin daemon + immutable container ID before the effect, across fresh runs.
    signal('attempted','recovery-outcome-unknown',daemon=daemon,resource=resource_id)
    start_argv=docker_argv('start',state['ID'])
    # A start has one durable action identity. Unknown outcome is never blindly
    # retried; probes/inspect above determine current conditions on recovery.
    start=command('start',start_argv,min(10,p['deadline']),rerun_safe=False,fixed=True)
    if not start['ok']:signal('blocked','dependency-start-failed')
    require(start['ok'],'dependency-start-failed',steps)
    deadline=time.monotonic()+p['deadline'];index=1;ready=False
    while time.monotonic()<deadline:
        result=probe(index,deadline-time.monotonic());index+=1
        if result['ok']:ready=True;break
        remaining=deadline-time.monotonic()
        if remaining>0:time.sleep(min(p['interval'],remaining))
    outcome='readiness-verified' if ready else 'readiness-timeout'
    signal('verified' if ready else 'blocked',None if ready else 'dependency-readiness-timeout')
    candidate=op.capture_experience(broker.j.project.root,broker.r['id']+'/'+parent_id+'/'+prefix,
        {'tool':'dependency','name':p['id']},environment(policy),
        {'initial_check':'failed','configured_resource_state':state['Status']},
        [{'operation':'start-existing-resource','procedure':p['id']}],outcome,
        [{'run':broker.r['id'],'action':step['action'],'log':step['log']} for step in steps],shared=policy.get('shared_root'))
    require(ready,'dependency-readiness-timeout',{'candidate':candidate,'steps':steps})
    return {'result':outcome,'started':True,'candidate':candidate['candidate'],'steps':steps,'seconds':time.monotonic()-started}


def after_error(broker, action_id, name, args):
    if 'memory' not in broker.c or not broker.c['memory'].get('enabled',True):return
    try:
        _,_,records,trace=retrieve(broker,name,args,include_candidates=True)
        trace.update(phase='after-error',candidate_ids=[r['id'] for r in records if r['kind']=='experience'])
    except (KnowledgeError,OSError,ValueError,KeyError,TypeError) as error:
        trace={'phase':'after-error','ok':False,'error':getattr(error,'code','memory-retrieval-error')}
    action=broker.j.action(broker.r['id'],action_id);action.setdefault('memory_traces',[]).append(trace)
    broker.j.action(broker.r['id'],action_id,action)


def current_formats(broker):
    from knowledge.text_format import validate_changes
    from .runtime import policy_path
    changes=list(broker.r.get('current_format_changes',[]))
    if broker.r.get('host_session'):
        from .host_ingress import read_session
        changes+=read_session(broker.j.project.root,broker.r['host_session']).get('format_changes',[])
    result={}
    for change in changes:
        validate_changes([change]);key=policy_path(change['path'].replace('\\','/'))
        if change.get('reset'):result.pop(key,None)
        else:result[key]={k:v for k,v in change.items() if k!='path'}
    return result


def encode_edit(raw,text,change=None,exists=True):
    from knowledge.text_format import encode
    return encode(raw,text,change,exists)


def decode_edit(raw):
    from knowledge.text_format import decode
    return decode(raw)
