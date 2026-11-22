"""Recoverable two-store instruction transfer; no new database or inference.

Lock order is project gate -> shared gate -> short individual SQLite transactions.
An intent is in existing project metadata before publishing a target. Relevant
lookups fail explicitly until both commits are verified. No lock spans a model,
Docker or test process. Faults after any durable step are replayable.
"""
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from . import operations as op
from .coordination import gate
from .project import Project
from .util import canonical_json,digest,loads,require,KnowledgeError

PREFIX='operational-transfer:'
PHASES={'prepared','target-saved','source-retired','completed','conflict'}
def fault(phase):pass


def validate(value,key=None):
    require(isinstance(value,dict) and value.get('version')==1 and value.get('phase') in PHASES,'corrupt-instruction-transfer')
    require(value.get('seal')==digest({k:v for k,v in value.items() if k!='seal'}),'corrupt-instruction-transfer')
    require(value['from']['scope'] in op.SCOPES and value['to']['scope'] in op.SCOPES and value['from']['scope']!=value['to']['scope'],'corrupt-instruction-transfer')
    require(not key or key==PREFIX+value['id'],'corrupt-instruction-transfer')
    return value


def intents(root):
    store=op.OperationalStore(root)
    if not store.path.exists():return []
    with store.connection() as db:
        return [validate(loads(v),k) for k,v in db.execute('SELECT key,value FROM metadata WHERE key LIKE ?', (PREFIX+'%',))]


def save(root,value):
    value=deepcopy(value);value.pop('seal',None);value['seal']=digest(value);validate(value)
    with op.OperationalStore(root).connection(True) as db:
        db.execute('INSERT INTO metadata VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(PREFIX+value['id'],canonical_json(value)))
    return value


@contextmanager
def ownership(root,shared):
    with gate(Project(root).root,exclusive=True):
        with gate(op.shared_root(shared),exclusive=True):yield


def record(root,side,shared):
    return next((r for r in op.OperationalStore(root,side['scope'],shared).records()['records'] if r['id']==side['id']),None)


def receipt(root,value,duplicate=False):
    target=record(root,value['to'],value['shared'])
    require(target is not None,'instruction-transfer-target-missing')
    return {**op.ack(target,duplicate=duplicate),**value['payload'].get('receipt_controls',{}),
        'transfer':{'id':value['id'],'phase':'completed','from':value['from'],'to':value['to']},
        'normalization':{'method':'durable-transfer-recovery'}}


def complete(root,value):
    with ownership(root,value['shared']):
        value=next(v for v in intents(root) if v['id']==value['id'])
        if value['phase']=='completed':return receipt(root,value,True)
        require(value['phase']!='conflict','instruction-transfer-conflict',{'id':value['id'],'reason':value.get('reason')})
        try:
            source=record(root,value['from'],value['shared']);target=record(root,value['to'],value['shared'])
            source_unchanged=source and source['revision']==value['from']['revision'] and source['content_hash']==value['source_record_hash']
            own_retirement=source and source['revision']==value['from']['revision']+1 and source['status']=='retired' and source.get('successor')==value['to']
            require(source_unchanged or own_retirement,'instruction-revision-conflict')
            if value['phase']=='prepared':
                fault('before-target')
                if target is None:
                    op.teach(root,value['text'],{'type':'user-message','id':value['message_id']},
                        scope=value['to']['scope'],shared=value['shared'],creation_id=value['to']['id'],**value['payload'])
                target=record(root,value['to'],value['shared'])
                require(target and target['revision']==1 and target['provenance']['id']==value['message_id'] and target['supersedes']==value['from'],'instruction-revision-conflict')
                fault('after-target')
                value['target_hash']=target['content_hash'];value['phase']='target-saved';value=save(root,value);fault('target-saved')
            target=record(root,value['to'],value['shared'])
            require(target and target['revision']==1 and target['content_hash']==value['target_hash'],'instruction-revision-conflict')
            if value['phase']=='target-saved':
                fault('before-source-retire')
                if not own_retirement:
                    op.retire(root,source['id'],scope=value['from']['scope'],shared=value['shared'],expected_revision=value['from']['revision'],successor=value['to'])
                fault('after-source-retire');value['phase']='source-retired';value=save(root,value);fault('source-retired')
            source=record(root,value['from'],value['shared'])
            require(source and source['revision']==value['from']['revision']+1 and source['status']=='retired' and source.get('successor')==value['to'],'instruction-revision-conflict')
            value['phase']='completed';value=save(root,value);fault('completed')
            return receipt(root,value)
        except KnowledgeError as error:
            if error.code not in ('instruction-revision-conflict','teaching-source-reused'):raise
            value['phase']='conflict';value['reason']=error.code;save(root,value)
            raise KnowledgeError('instruction-transfer-conflict',{'id':value['id'],'reason':error.code}) from error


def begin(root,old,text,message_id,shared,kwargs):
    shared=str(op.shared_root(shared));op.clean_text(text);op.reject_secrets(canonical_json(kwargs))
    for scope in op.SCOPES:op.OperationalStore(root,scope,shared).ensure()
    with ownership(root,shared):
        identifier=digest({'project':Project(root).identity,'message':message_id})
        prior=next((v for v in intents(root) if v['id']==identifier),None)
        if prior:
            require(prior['source_hash']==digest(text),'teaching-source-reused');return complete(root,prior)
        target_scope=kwargs.pop('scope');kwargs=deepcopy(kwargs)
        side={'scope':old['scope'],'id':old['id'],'revision':old['revision']}
        target={'scope':target_scope,'id':digest({'transfer':identifier,'scope':target_scope}),'revision':1}
        kwargs.update(original=old['original'],predecessor=side)
        # Scope movement cannot silently refresh an existing executable binding.
        if kwargs.get('binding') and old['behavior']==kwargs['binding']['behavior']:
            kwargs['execution_override']=old.get('execution_binding') or {'version':1,'state':'unavailable','reason':'scope transfer requires existing binding revalidation'}
        value={'version':1,'id':identifier,'phase':'prepared','message_id':message_id,'source_hash':digest(text),
            'text':text,'shared':shared,'from':side,'to':target,'source_record_hash':old['content_hash'],
            'payload':kwargs,'request_fingerprint':digest(kwargs)}
        fault('before-intent');value=save(root,value);fault('prepared')
        return complete(root,value)


def replay(root,text,message_id,shared=None):
    found=[v for v in intents(root) if v['message_id']==message_id]
    require(len(found)<=1,'ambiguous-instruction-transfer')
    if not found:return None
    value=found[0];require(value['source_hash']==digest(text),'teaching-source-reused')
    require(str(op.shared_root(shared))==value['shared'],'instruction-transfer-environment-changed')
    return complete(root,value)


def recover(root,shared=None):
    results=[]
    for value in intents(root):
        if value['phase']=='completed':continue
        require(str(op.shared_root(shared))==value['shared'],'instruction-transfer-environment-changed')
        results.append(complete(root,value))
    return {'ok':True,'transfers':results}


def pending(root,action,shared=None):
    result=[]
    for value in intents(root):
        if value['phase']=='completed':continue
        source=record(root,value['from'],shared);target=record(root,value['to'],shared)
        records=[r for r in (source,target) if r and r['status'] in ('active','unbound')]
        trigger=(value['payload'].get('binding') or {}).get('trigger') or value['payload'].get('intent_trigger')
        if records and (not trigger or op.matches(trigger,action)):
            result.append({'id':value['id'],'phase':value['phase'],'from':value['from'],'to':value['to']})
    return result
