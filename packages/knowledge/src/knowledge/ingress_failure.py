"""Expected local-normalizer failure, distinct from store/source integrity errors."""
from . import operations as op
from .startup_authorization import restriction


def degraded(root,text,message_id,policy,previous,error):
    denied=restriction(text,'unchanged')=='deny'
    result={'ok':True,'saved':False}
    if op.TEACHING.search(text) and not (previous and previous['status']=='active'):
        if previous and previous['provenance']['id']==message_id:result=op.ack(previous,duplicate=True)
        elif previous is None:
            bindings=[b for b in policy.get('bindings',[]) if any(alias.casefold() in text.casefold() for alias in b['aliases'])]
            chosen=bindings[0] if len(bindings)==1 else None
            result=op.teach(root,text,{'type':'user-message','id':message_id},
                scope='shared' if op.SHARED.search(text) else 'project',shared=policy.get('shared_root'),
                binding=None,intent_trigger=(chosen or {}).get('trigger'),receipt_stage='intent',
                missing=['Local normalization unavailable; retry this trusted source before effects.'],
                normalization={'method':'local-model','state':'degraded','error':error.code},
                recovery_authorized=False,authorization_intent=False)
    return {**result,'restriction':'no-service-start' if denied else None,'format_changes':[],
        'degraded':{'reason':error.code,'state':'unparsed','blocks':['patch','recipe','service-start']},
        'notice':'Knowledge: локальная нормализация недоступна ('+error.code+'). Чат и чтение доступны; неразобранный запрос не разрешает эффекты. Нужен retry или явное operator resolution.',
        'normalization':{'method':'local-model','state':'degraded','error':error.code}}
