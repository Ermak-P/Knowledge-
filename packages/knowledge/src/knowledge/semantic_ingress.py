"""Semantic user ingress over the same transactional operational extension."""
from copy import deepcopy
import platform
import re
import sys
from . import operations as op
from .normalizer import normalize
from .coordination import gate
from .project import Project
from .util import KnowledgeError,require,digest


def records(root,policy):
    return [r for scope in op.SCOPES for r in op.OperationalStore(root,scope,policy.get('shared_root')).records()['records']]


def resource(binding,template_id,parameters,applicability):
    if template_id:
        if not parameters.get('container'):return None
        identity={'template':template_id,'parameters':parameters}
    else:
        docker=(binding or {}).get('behavior',{}).get('procedure',{}).get('docker')
        if not docker:return None
        identity={'docker':docker}
    return digest({'resource':identity,'applicability':applicability})


def ingest(root,text,message_id,policy,reply_to=None):
    try:op.clean_text(text)
    except KnowledgeError as error:
        if error.code!='memory-secret-denied':raise
        return {'ok':True,'saved':False,'sensitive_skipped':True,
            'notice':'Knowledge did not persist or normalize this message: credential-like input is excluded from memory.'}
    replay=op.binding_receipt(root,text,message_id,policy.get('shared_root'),policy)
    if replay:return replay
    target=re.search(r'(?i)(?:rule|правило)\s+([0-9a-f]{64})\b',text)
    identifier=target.group(1) if target else reply_to
    previous=next((r for r in records(root,policy) if r['id']==identifier),None) if identifier else None
    if identifier:require(previous is not None,'unknown-instruction')
    if previous is None:
        # Recover a committed incomplete intent after a host died before writing
        # its pending-session pointer. A replay must bind the same durable ID.
        matches=[r for r in records(root,policy) if r['kind']=='instruction' and r['status']=='unbound' and r['provenance']['id']==message_id]
        require(len(matches)<=1,'ambiguous-teaching-source');previous=matches[0] if matches else None
    declared=policy.get('environment',{})
    environment={**declared,'machine':platform.node(),'os':sys.platform,'project_root':str(Project(root).root),'tools':{**declared.get('tools',{}),'python':platform.python_version()}}
    try:
        result,metadata=normalize(text,policy.get('bindings',[]),policy['normalizer'],previous,policy.get('procedure_templates',[]),environment)
    except KnowledgeError as error:
        from .ingress_failure import degraded
        return degraded(root,text,message_id,policy,previous,error)
    from .startup_authorization import restriction as current_restriction,startup
    result['current_start']=current_restriction(text,result['current_start'])
    restriction={'deny':'no-service-start','clear-denial':'clear-service-start-denial','unchanged':None}[result['current_start']]
    if 'sensitive-input-not-stored' in result['unsupported']:
        return {'ok':True,'saved':False,'sensitive_skipped':True,'notice':'Knowledge did not persist sensitive input.'}
    if result['intent']=='none':
        require(not result['unsupported'],'current-request-not-representable',result['question'] or result['unsupported'])
        return {'ok':True,'saved':False,'restriction':restriction,'format_changes':result['format_changes'],'normalization':metadata}
    catalog=policy.get('bindings',[])
    chosen=deepcopy(catalog[result['binding']]) if result['binding'] is not None else None
    # Reuse an unambiguous update target's already accepted resource details.
    # The revision is checked again under the commit gate below.
    if previous is None and result['intent']=='update' and chosen:
        scope='project' if result['scope']=='ambiguous' else result['scope']
        matches=[r for r in records(root,policy) if r['kind']=='instruction' and r['status']=='active' and
            r['scope']==scope and r['trigger']==chosen['trigger'] and r.get('binding_template')==chosen.get('template')]
        require(len(matches)<=1,'ambiguous-instruction-update')
        previous=matches[0] if matches else None
    unsupported=list(result['unsupported']);parameters={};template_id=(chosen or {}).get('template')
    if chosen and not op.supported_binding(policy,chosen):unsupported.append('unsupported host trigger/action')
    if template_id:
        from .procedure_templates import materialize
        template=next((t for t in policy.get('procedure_templates',[]) if t['id']==template_id),None)
        require(template is not None,'unknown-procedure-template')
        parameters={**template['defaults'],**((previous or {}).get('binding_parameters',{}) if (previous or {}).get('binding_template')==template_id else {})}
        source=text+'\n'+(previous or {}).get('original','')+'\n'+((previous or {}).get('source_text') or '')
        for key,value in result['parameters'].items():
            if parameters.get(key)==value:continue
            quote=result['parameter_quotes'].get(key,'')
            chars=r'\d.' if key=='port' else r'A-Za-z0-9_.-'
            token=r'(?<!['+chars+r'])'+re.escape(str(value))+r'(?=$|[^'+chars+r']|\.(?=\s|$))'
            if quote and re.search(token,quote) and quote in source and re.search(token,source):parameters[key]=value
            else:unsupported.append('parameter '+key+' was not explicitly supplied')
        try:chosen['behavior']=materialize(template,parameters)
        except KnowledgeError as error:
            unsupported.append(error.code)
            unsupported.extend('missing parameter: '+k for k in sorted({'container','host','port'}-set(parameters)))
    elif result['parameters']:unsupported.append('fixed binding cannot accept new resource parameters')
    applicability=deepcopy((chosen or {}).get('applicability',{}));op.validate_applicability(result['applicability'])
    for key,value in result['applicability'].items():
        if key=='tools':
            existing=applicability.setdefault('tools',{})
            for tool,version in value.items():
                if tool in existing and existing[tool]!=version:unsupported.append('tool applicability contradicts configured binding')
                else:existing[tool]=version
        elif key in applicability and applicability[key]!=value:unsupported.append('applicability contradicts configured binding')
        else:applicability[key]=value
    if result['scope']=='ambiguous':
        unsupported.append('scope needs clarification')
        result['question']=result['question'] or 'Только текущий проект или все подходящие проекты?'
    identity=resource(chosen,template_id,parameters,applicability)
    resource_count=sum(bool(b.get('template') or b.get('behavior',{}).get('procedure',{}).get('docker')) for b in catalog)
    authorization=startup(text,chosen,result['authorize_recovery'],result.get('permission_quote',''),resource_count)
    metadata['startup_authorization']=authorization
    result['authorize_recovery']=authorization['granted']
    # A genuine current startup denial cannot be classified away by the model.
    # For temporary directives intent=none returned above without rewriting memory.
    if authorization['denied']:result['revoke_recovery']=True
    prior_identity=(previous or {}).get('authorization_resource') or (resource(
        {'behavior':previous.get('behavior') or {}},previous.get('binding_template'),previous.get('binding_parameters',{}),previous['applicability']) if previous else None)
    current_grant=result['authorize_recovery'] and result.get('permission_quote','') in text
    changing_grant=bool(previous and previous.get('authorization_intent',previous['recovery_authorized']) and
        prior_identity and identity and prior_identity!=identity and not current_grant and not result['revoke_recovery'])
    if changing_grant:
        unsupported.append('startup permission is bound to the previous resource')
        result['question']='Разрешаете запуск нового указанного ресурса? Укажите явно разрешение запуска или запрет запуска.'
    scope=previous['scope'] if previous and not result['scope_explicit'] else 'project' if result['scope']=='ambiguous' else result['scope']
    binding=chosen if chosen and not unsupported else None
    question=result['question'] or ('Какая настроенная операция/процедура реализует всё правило? '+', '.join(unsupported) if not binding else None)
    missing=([question]+unsupported)[:8] if not binding else []
    summary=result['summary'] or (previous or {}).get('normalized') or text
    # Local inference does not hold the maintenance gate. Commits/supersession do.
    with gate(Project(root).root,exclusive=True):
        old=previous if previous and (result['intent'] in ('clarify','update') or target or previous['status']=='unbound' and previous['provenance']['id']==message_id) else None
        if old:
            latest=next((r for r in records(root,policy) if r['id']==old['id']),None)
            require(latest and latest['revision']==old['revision'],'instruction-revision-conflict')
        if result['intent']=='update' and old is None and chosen and chosen.get('behavior'):
            behavior=chosen['behavior']
            candidates=[r for r in records(root,policy) if r['kind']=='instruction' and r['status']=='active' and r['scope']==scope and
                r['trigger']==chosen['trigger'] and (r['behavior'] or {}).get('adapter')==behavior['adapter'] and
                (r['behavior'] or {}).get('procedure',{}).get('id')==behavior.get('procedure',{}).get('id')]
            require(len(candidates)<=1,'ambiguous-instruction-update')
            old=candidates[0] if candidates else None
        requested=False if result['revoke_recovery'] or authorization.get('uncertain') else bool(result['authorize_recovery'] or old and old.get('authorization_intent',old['recovery_authorized']))
        grant=bool(binding and binding['behavior']['adapter']=='dependency' and requested)
        moving=bool(old and old['scope']!=scope)
        if old and old['provenance']['id']==message_id and old['status']=='unbound' and not binding and not moving:
            return {**op.ack(old,duplicate=True),'restriction':restriction,'normalization':metadata}
        kwargs=dict(scope=scope,
            binding=binding,applicability=applicability,identifier=old['id'] if old and not moving else None,
            expected_revision=old['revision'] if old and not moving else None,recovery_authorized=grant,
            authorization_intent=requested,summary=summary,missing=missing,normalization=metadata,
            authorization_revoked=bool(result['revoke_recovery'] or old and old.get('authorization_revoked') and not result['authorize_recovery']),
            original=old['original'] if old else None,intent_trigger=(chosen or {}).get('trigger'),
            binding_template=template_id,binding_parameters=parameters,
            authorization_resource=prior_identity if changing_grant else identity,
            predecessor={'id':old['id'],'revision':old['revision'],'scope':old['scope']} if moving else None,
            semantic=True,receipt_stage='binding' if binding else 'intent',
            receipt_controls={'restriction':restriction,'format_changes':result['format_changes']})
        if moving:
            from .transfers import begin
            kwargs.pop("identifier");kwargs.pop("expected_revision")
            saved=begin(root,old,text,message_id,policy.get("shared_root"),kwargs)
        else:
            saved=op.teach(root,text,{"type":"user-message","id":message_id},shared=policy.get("shared_root"),**kwargs)
    if (chosen or {}).get('behavior',{}).get('adapter')=='dependency':
        saved['message']+=' Запуск разрешён только для этой привязки.' if saved['recovery_authorized'] else ' Запуск не разрешён; доступна проверка готовности.'
        if not saved['recovery_authorized'] and not authorization['denied'] and result.get('permission_quote') and not saved.get('question'):
            saved['question']='Если нужен автоматический старт, разрешите запуск указанного контейнера явно: «Разрешаю запуск контейнера <имя>, если он остановлен».'
    return {**saved,'restriction':restriction,'normalization':metadata}
