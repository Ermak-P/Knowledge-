"""Trusted local host ingress with bounded durable source/order recovery."""
import argparse
from copy import deepcopy
import os
from pathlib import Path
import re,sys,tempfile
from knowledge.coordination import gate
from knowledge.project import Project,safe_tree
from knowledge import operations as op
from knowledge.util import loads,canonical_json,emit_json,require,digest,KnowledgeError

MAX_SESSION_BYTES=512000
MAX_MESSAGES=128
MAX_PENDING_BYTES=128000


def session_path(root,session_id):
    require(isinstance(session_id,str) and re.fullmatch('[A-Za-z0-9_.-]{1,160}',session_id),'invalid-host-session-id')
    directory=Project(root).root/'.harness/host-sessions';safe_tree(directory)
    return directory/(digest(session_id)+'.json')


def read_session(root,session_id):
    path=session_path(root,session_id);require(path.is_file(),'host-session-not-captured')
    require(path.stat().st_size<=MAX_SESSION_BYTES,'invalid-host-session')
    value=loads(path.read_text(encoding='utf-8'))
    require(isinstance(value,dict) and value.get('session')==session_id and isinstance(value.get('restrictions'),list) and set(value['restrictions'])<={'no-service-start'},'invalid-host-session')
    from knowledge.text_format import validate_changes
    validate_changes(value.get('format_changes',[]))
    messages=value.get('messages',{});require(isinstance(messages,dict) and len(messages)<=MAX_MESSAGES,'invalid-host-session')
    for source,entry in messages.items():
        require(isinstance(source,str) and isinstance(entry,dict) and type(entry.get('sequence')) is int and entry['sequence']>0 and entry.get('state') in ('pending','resolved','sensitive','overflow'),'invalid-host-envelope')
        require(isinstance(entry.get('hash'),str) and len(entry['hash'])==64,'invalid-host-envelope')
        if entry.get('text') is not None:require(digest(entry['text'])==entry['hash'],'host-pending-source-corrupt')
    value['pending']=[{'source':source,'sequence':entry['sequence'],'state':entry['state'],'hash':entry['hash']} for source,entry in messages.items() if entry['state']!='resolved']
    if value.get('overflow'):value['pending'].append({'state':'overflow'})
    return value


def write_session(path,value):
    value=deepcopy(value);value.pop('pending',None);raw=canonical_json(value)
    require(len(raw.encode())<=MAX_SESSION_BYTES,'host-session-byte-budget')
    fd,tmp=tempfile.mkstemp(prefix='session-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def guard(root,session_id,effect):
    state=read_session(root,session_id)
    require(not state['pending'],'host-controls-unresolved',{'effect':effect,'pending':state['pending'],'recovery':'harness.host_ingress --recover-session or explicit --resolve-session'})
    return state


def _policy(root):
    from .runtime import config
    c=config(root);policy=deepcopy(c.get('memory',{}))
    policy['activation_paths']={'patch':['preserve-format','check','dependency'],'recipe':['check','dependency'],'dependency':['check','dependency']}
    if policy.get('teaching_mode','local-model')!='catalog' and not policy.get('normalizer'):
        policy['normalizer']={k:c['provider'][k] for k in ('endpoint','model','key_env','evidence') if k in c['provider']}
        policy['normalizer']['timeout']=min(45,c['limits'].get('provider_seconds',20))
    return c,policy


def _memory_binding(root,policy):
    return digest([(scope,r['id'],r['revision']) for scope in op.SCOPES for r in op.OperationalStore(root,scope,policy.get('shared_root')).records()['records']])


def _replay(root,policy,entry,source_id,text):
    if entry.get('record'):
        ref=entry['record'];record=next((r for r in op.OperationalStore(root,ref['scope'],policy.get('shared_root')).records()['records'] if r['id']==ref['id']),None)
        require(record is not None,'host-source-record-missing');result=op.ack(record,duplicate=True)
        # A committed intent is not a completed binding. Authentic redelivery
        # may finish that same source after host death/lost pending pointer.
        if record['status']=='unbound' and record['provenance']['id']==source_id:return None
        # Revalidate historical natural-language grants with the current whole-
        # source boundary. This uses durable receipts, never a new model call.
        result=op.binding_receipt(root,text,source_id,policy.get('shared_root'),policy) or result
    else:result={'ok':True,'saved':False,'duplicate':True}
    return {**result,'restriction':None,'format_changes':[],'normalization':{'method':'session-source-replay'},'controls_applied':False,'integration_enabled':True}


def message(root,text,session_id,message_id):
    c,policy=_policy(root)
    if 'memory' not in c or not policy.get('enabled',True):return {'ok':True,'saved':False,'integration_enabled':False,'reason':'memory-integration-not-enabled'}
    require(isinstance(message_id,str) and re.fullmatch('[A-Za-z0-9_.-]{1,160}',message_id),'invalid-host-message-id')
    sensitive=False
    try:op.clean_text(text)
    except KnowledgeError as error:
        if error.code!='memory-secret-denied':raise
        sensitive=True
    from knowledge.startup_authorization import restriction
    deny=restriction(text,'unchanged')=='deny'
    path=session_path(root,session_id);path.parent.mkdir(parents=True,exist_ok=True)
    with gate(Project(root).root,exclusive=True):
        value=read_session(root,session_id) if path.exists() else {'version':2,'session':session_id,'restrictions':[],'sequence':0}
        if value.get('version')!=2 and value.get('sequence',0):
            value['overflow']=True
            if deny:value['restrictions']=['no-service-start']
            write_session(path,value)
            return {'ok':True,'saved':False,'degraded':{'reason':'legacy-session-source-order-unverifiable','blocks':['patch','recipe']},'notice':'Legacy session has no ordered source ledger. Existing controls remain; use a new independent session before effects.','integration_enabled':True}
        value['version']=2
        messages=value.setdefault('messages',{})
        if message_id in messages:
            entry=messages[message_id];require(entry['hash']==digest(text),'teaching-source-reused')
            if entry['state']=='resolved':
                replay=_replay(root,policy,entry,session_id+'/'+message_id,text)
                if replay is not None:return replay
                require(sum(len(e.get('text','').encode()) for e in messages.values())+len(text.encode())<=MAX_PENDING_BYTES,'host-pending-byte-budget')
                entry.update(state='pending',text=text)
            require(entry.get('config')==digest(c),'host-pending-config-changed')
            if entry.get('memory_binding'):require(entry['memory_binding']==_memory_binding(root,policy),'host-pending-memory-changed')
        else:
            if len(messages)>=MAX_MESSAGES:
                value['overflow']=True
                if deny:value['restrictions']=['no-service-start']
                write_session(path,value)
                return {'ok':True,'saved':False,'degraded':{'reason':'session-source-budget','blocks':['patch','recipe']},'notice':'Host source budget exhausted; start a new independent session. Existing controls remain active.','integration_enabled':True}
            sequence=value.get('sequence',0)+1;value['sequence']=sequence
            entry={'hash':digest(text),'sequence':sequence,'state':'sensitive' if sensitive else 'pending','config':digest(c),
                'reply_to':value.get('pending_instruction')}
            pending_bytes=sum(len(e.get('text','').encode()) for e in messages.values())
            if not sensitive and pending_bytes+len(text.encode())<=MAX_PENDING_BYTES:entry['text']=text
            elif not sensitive:entry['state']='overflow'
            messages[message_id]=entry
        sequence=entry['sequence']
        if deny:value['restrictions']=['no-service-start'];value['controls_sequence']=max(value.get('controls_sequence',0),sequence)
        write_session(path,value)
    if sensitive or entry['state'] in ('sensitive','overflow'):
        result={'ok':True,'saved':False,'sensitive_skipped':sensitive,'degraded':{'reason':'sensitive-input-not-retained' if sensitive else 'pending-byte-budget','blocks':['patch','recipe']},'notice':'Knowledge did not persist raw sensitive/overflow input. Effects require explicit operator resolution.'}
    else:
        result=op.ingest(root,text,session_id+'/'+message_id,policy,reply_to=entry.get('reply_to'))
        action=result.get('action')
        if result.get('executable') and action and action['adapter']!='preserve-format':
            from knowledge.procedure_templates import permitted
            if not permitted(policy,action):result.update(executable=False,execution_state='tool-denied',binding_reason='Procedure/template is not allowed by current host policy.')
        if result.get('saved') and (result.get('trigger') or {}).get('tool')=='dependency' and not any(op.matches(result['trigger'],{'tool':'dependency','name':r['dependency']}) for r in policy.get('requirements',[])):
            result.update(executable=False,execution_state='unlinked',binding_reason='No declared suite/recipe requirement activates this dependency in the current project.')
    with gate(Project(root).root,exclusive=True):
        value=read_session(root,session_id);entry=value['messages'][message_id]
        newest=sequence==value['sequence'] and sequence>=value.get('controls_sequence',0)
        if newest:
            if result.get('restriction')=='no-service-start' or deny:value['restrictions']=['no-service-start']
            elif result.get('restriction')=='clear-service-start-denial':value['restrictions']=[]
            formats={change['path']:change for change in value.get('format_changes',[])}
            for change in result.get('format_changes',[]):
                if change.get('reset'):formats.pop(change['path'],None)
                else:formats[change['path']]=change
            value['format_changes']=list(formats.values());value['controls_sequence']=sequence
            if result.get('saved'):
                if result['status']=='unbound':value['pending_instruction']=result['id']
                else:value.pop('pending_instruction',None)
        else:result={**result,'restriction':None,'format_changes':[],'controls_ignored':'older-source'}
        if result.get('degraded'):
            entry['state']='sensitive' if sensitive else entry['state']
            entry['reason']=result['degraded']['reason']
            if not sensitive:entry['memory_binding']=_memory_binding(root,policy)
        else:
            entry['state']='resolved';entry.pop('text',None);entry.pop('memory_binding',None)
        if result.get('saved'):entry['record']={'id':result['id'],'scope':result['scope']}
        write_session(path,value)
        return {**result,'controls_applied':newest,'effective_restrictions':value['restrictions'],'integration_enabled':True}


def recover_session(root,session_id,source=None):
    value=read_session(root,session_id);results=[]
    for source_id,entry in sorted(value.get('messages',{}).items(),key=lambda row:row[1]['sequence']):
        if source and source_id!=source:continue
        if entry['state']=='resolved':continue
        require(entry.get('text') is not None,'host-pending-operator-resolution-required',{'source':source_id,'hash':entry['hash']})
        results.append(message(root,entry['text'],session_id,source_id))
    return {'ok':True,'results':results,'pending':read_session(root,session_id)['pending']}


def resolve_session(root,session_id,value):
    # Trusted local operator only; no MCP/model write tool or service-start grant.
    require(set(value)=={'source_id','source_hash','decision'} and value['decision']=='no-new-controls','invalid-host-resolution')
    with gate(Project(root).root,exclusive=True):
        state=read_session(root,session_id);entry=state.get('messages',{}).get(value['source_id'])
        require(entry and entry['hash']==value['source_hash'],'host-resolution-source-mismatch')
        entry['state']='resolved';entry.pop('text',None);entry.pop('memory_binding',None);entry['operator_resolution']='no-new-controls'
        write_session(session_path(root,session_id),state)
    return {'ok':True,'resolved':value['source_id'],'restrictions':state['restrictions']}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--recover-session');parser.add_argument('--resolve-session');parser.add_argument('--source-id');args=parser.parse_args()
    try:
        if args.recover_session:result=recover_session(args.root,args.recover_session,args.source_id)
        else:
            raw=sys.stdin.buffer.read(65537).decode('utf-8');require(len(raw.encode())<=65536,'host-message-too-large');value=loads(raw)
            result=resolve_session(args.root,args.resolve_session,value) if args.resolve_session else message(args.root,value['text'],value['session_id'],value['message_id'])
    except (KnowledgeError,OSError,ValueError,KeyError,TypeError) as error:result={'ok':False,'saved':False,'error':getattr(error,'code','host-ingress-error'),'details':getattr(error,'details',None)}
    emit_json(result);return 0 if result['ok'] else 1

if __name__=='__main__':raise SystemExit(main())
