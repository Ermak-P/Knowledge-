"""Trusted local OpenCode hook ingress. Not an MCP/model-writable endpoint."""
import argparse
from copy import deepcopy
import os
from pathlib import Path
import re
import sys
import tempfile
from knowledge.coordination import gate
from knowledge.project import Project,safe_tree,safe_path
from knowledge.operations import ingest,RESTRICT
from knowledge.util import loads,canonical_json,emit_json,require,digest,KnowledgeError


def session_path(root,session_id):
    require(isinstance(session_id,str) and re.fullmatch('[A-Za-z0-9_.-]{1,160}',session_id),'invalid-host-session-id')
    project=Project(root);directory=project.root/'.harness/host-sessions';safe_tree(directory)
    return directory/(digest(session_id)+'.json')


def read_session(root,session_id):
    path=session_path(root,session_id);require(path.is_file(),'host-session-not-captured')
    require(path.stat().st_size<=32000,'invalid-host-session')
    value=loads(path.read_text(encoding='utf-8'))
    require(isinstance(value,dict) and value.get('session')==session_id and isinstance(value.get('restrictions'),list) and set(value['restrictions'])<={'no-service-start'},'invalid-host-session')
    from knowledge.text_format import validate_changes
    validate_changes(value.get('format_changes',[]))
    return value


def write_session(path,value):
    fd,tmp=tempfile.mkstemp(prefix='session-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as stream:
            stream.write(canonical_json(value));stream.flush();os.fsync(stream.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def message(root,text,session_id,message_id):
    from .runtime import config
    configuration=config(root)
    if 'memory' not in configuration or not configuration['memory'].get('enabled',True):
        return {'ok':True,'saved':False,'integration_enabled':False,'reason':'memory-integration-not-enabled'}
    policy=deepcopy(configuration['memory'])
    if policy.get('teaching_mode','local-model')!='catalog' and not policy.get('normalizer'):
        provider=configuration['provider']
        policy['normalizer']={k:provider[k] for k in ('endpoint','model','key_env','evidence') if k in provider}
        policy['normalizer']['timeout']=min(45,configuration['limits'].get('provider_seconds',20))
    path=session_path(root,session_id);path.parent.mkdir(parents=True,exist_ok=True)
    with gate(Project(root).root,exclusive=True):
        value=read_session(root,session_id) if path.exists() else {'session':session_id,'restrictions':[]}
        sequence=value.get('sequence',0)+1;value['sequence']=sequence
        if RESTRICT.search(text):value['restrictions']=['no-service-start']
        write_session(path,value)
        pending=value.get('pending_instruction')
    result=ingest(root,text,session_id+'/'+message_id,policy,reply_to=pending)
    with gate(Project(root).root,exclusive=True):
        value=read_session(root,session_id)
        if value.get('sequence')!=sequence:return {**result,'integration_enabled':True}
        if result.get('restriction')=='no-service-start' or RESTRICT.search(text):value['restrictions']=['no-service-start']
        elif result.get('restriction')=='clear-service-start-denial':value['restrictions']=[]
        formats={c['path']:c for c in value.get('format_changes',[])}
        for change in result.get('format_changes',[]):
            if change.get('reset'):formats.pop(change['path'],None)
            else:formats[change['path']]=change
        value['format_changes']=list(formats.values())
        from knowledge.text_format import validate_changes
        validate_changes(value['format_changes'])
        if result.get('saved'):
            if result['status']=='unbound':value['pending_instruction']=result['id']
            else:value.pop('pending_instruction',None)
        write_session(path,value)
    return {**result,'integration_enabled':True}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);a=parser.parse_args()
    try:
        raw=sys.stdin.buffer.read(65537).decode('utf-8');require(len(raw.encode('utf-8'))<=65536,'host-message-too-large');value=loads(raw)
        result=message(a.root,value['text'],value['session_id'],value['message_id'])
    except (KnowledgeError,OSError,ValueError,KeyError,TypeError) as error:
        result={'ok':False,'saved':False,'error':getattr(error,'code','host-ingress-error'),'details':getattr(error,'details',None)}
    emit_json(result);return 0 if result['ok'] else 1


if __name__=='__main__':raise SystemExit(main())
