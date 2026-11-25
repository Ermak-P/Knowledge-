"""Bounded diagnostic projections, never a truncated approval payload."""
from .util import canonical_json, digest, require


def compact(value,depth=0):
    if isinstance(value,str):return value if len(value)<=240 else value[:240]+'…'
    if isinstance(value,list):return {'items':[compact(v,depth+1) for v in value[:4]],'total':len(value),'truncated':True} if len(value)>4 else [compact(v,depth+1) for v in value]
    if isinstance(value,dict):
        if depth>5:return {'truncated':True,'detail':'nested projection depth exceeded'}
        result={k:compact(v,depth+1) for k,v in list(value.items())[:24]}
        if len(value)>24:result['_truncated_keys']=len(value)-24
        return result
    return value


def page(rows,header,cursor,limit,budget):
    require(type(budget) is int and 256<=budget<=1000000,'invalid-byte-budget')
    answer={**header,'rows':[],'total':len(rows),'next_cursor':None,'diagnostic_projection':True,'truncated':False}
    for index in range(cursor,min(len(rows),cursor+limit)):
        raw=rows[index];value=compact(raw)
        if value!=raw:
            answer['truncated']=True
            if isinstance(value,dict):value={**value,'detail_reference':{'cursor':index}}
        candidate={**answer,'rows':answer['rows']+[value],'next_cursor':index+1 if index+1<len(rows) else None}
        if len(canonical_json(candidate).encode())>budget:
            if answer['rows']:break
            value={'detail_reference':{'cursor':index},'truncated':True}
            candidate={**answer,'rows':[value],'truncated':True,'next_cursor':index+1 if index+1<len(rows) else None}
            if len(canonical_json(candidate).encode())>budget:return {'ok':False,'error':'diagnostic-budget-too-small','cursor':cursor,'minimum_budget':1024}
        answer=candidate
    return answer
