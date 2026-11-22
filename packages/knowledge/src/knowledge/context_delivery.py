"""Bounded architectural view v2: graph references and honest exclusions.

Never promotes facts or executes guards. All budgets include actually returned
records, dependency closure, evidence and diagnostics. No historical statements
are copied into filtered diagnostics.
"""
from copy import deepcopy
from . import lifecycle as life
from .retrieval import ContextEngine,tokenize,expand,STOPWORDS
from .util import canonical_json,canonical_source,require

MAX_DEPTH=4
MAX_DIAGNOSTICS=8


def relevant(task,claim,evidence):
    query=expand(tokenize(task)-STOPWORDS)
    text=' '.join([claim['id'],claim['statement'],*[str(canonical_source(evidence[e]))+' '+str(evidence[e].get('description','')) for e in claim['evidence'] if e in evidence]])
    return claim['id'].casefold() in task.casefold() or bool(expand(tokenize(text))&query)


def entry(claim):
    value={k:deepcopy(claim[k]) for k in ('id','status','type','statement','last_verified','provenance','conflicts_with','depends_on')}
    value.update(confirmed=claim['status']=='CONFIRMED',evidence_ids=list(claim['evidence']),revision=claim.get('_p1',{}).get('revision'))
    if '_p1' in claim:value['current']=deepcopy(claim['_p1'])
    return value


def evidence_ref(item):
    return {'id':item['id'],'provenance':item['provenance'],'status':item['status'],'source':canonical_source(item),
        'location':item.get('location',{}).get('reference') if isinstance(item.get('location'),dict) else item.get('location')}


def prune(result):
    ids={i for claim in result['claims'] for i in claim['evidence_ids']}
    result['evidence']=[e for e in result['evidence'] if e['id'] in ids]
    selected={c['id'] for c in result['claims']}
    result['conflicts']=[c for c in result['conflicts'] if c['claim_id'] in selected]
    result['dependencies']['references']=[ref for ref in result['dependencies']['references'] if ref['from'] in selected]
    for ref in result['dependencies']['references']:
        if ref['id'] not in selected and ref.get('delivered'):
            ref.update(delivered=False,reason='byte-budget')
    result['dependencies']['complete']=not result['dependencies'].get('omitted',0) and all(ref['delivered'] for ref in result['dependencies']['references'])
    result['truncation'].update(returned=len(selected),dropped=max(0,result['truncation']['candidates']-len(selected)))


def context(store,task,max_bytes,max_items,include_unconfirmed):
    require(isinstance(task,str) and bool(task.strip()) and len(task)<=10000,'invalid-query')
    require(type(max_bytes) is int and 256<=max_bytes<=1000000,'invalid-byte-budget')
    require(type(max_items) is int and 1<=max_items<=100,'invalid-item-limit')
    require(type(include_unconfirmed) is bool,'invalid-status-policy')
    if not store.path.exists():
        return {'ok':True,'result':'store-absent','claims':[],'evidence':[],'conflicts':[],'partial':True,'diagnostics':{'store':'absent','selection':'store-absent'}}
    with store.connection() as db:
        records=life.active(store,db,store._records(db),diagnostics=True)
    evidence={e['id']:e for e in records['evidence']};available={c['id']:c for c in records['claims']}
    excluded={n['claim']['id']:n for n in records.get('_excluded',[])}
    filtered=[]
    for note in records.get('_excluded',[]):
        claim=note['claim']
        if relevant(task,claim,evidence):
            filtered.append({'id':claim['id'],'revision':note['revision'],'status':claim['status'],'lifecycle':note['lifecycle'],
                'reason':note['reason'],'freshness':note['freshness'],'depends_on':list(claim['depends_on']),
                'dependency_state':[{'id':i,'reason':excluded[i]['reason'],'freshness':excluded[i]['freshness'],'lifecycle':excluded[i]['lifecycle']} for i in claim['depends_on'][:4] if i in excluded],
                'source_refs':[evidence_ref(evidence[e]) for e in claim['evidence'][:4] if e in evidence],
                'next':'inspect claim/evidence; reverify with current source and normal review/approval'})
    if not include_unconfirmed:
        for claim in records['claims']:
            if claim['status']!='CONFIRMED' and relevant(task,claim,evidence):
                filtered.append({'id':claim['id'],'revision':claim.get('_p1',{}).get('revision'),'status':claim['status'],'reason':'status-policy','next':'review evidence; no automatic promotion'})
    engine=ContextEngine()
    result=engine.assemble(records,task,max_tokens=max_bytes//4,max_items=max_items,include_unconfirmed=include_unconfirmed,compact=True)
    result['delivery_version']=2
    result['diagnostics']={'store':'available','selection':'matches' if result['claims'] else 'filtered' if filtered else 'budget-exhausted' if result['truncation']['candidates'] else 'lexical-no-match',
        'filtered':filtered[:MAX_DIAGNOSTICS],'filtered_count':len(filtered),'omitted':max(0,len(filtered)-MAX_DIAGNOSTICS)}
    result['dependencies']={'version':1,'max_depth':MAX_DEPTH,'complete':True,'references':[],'max_references':128,'omitted':0}
    selected={c['id'] for c in result['claims']};queue=[(c['id'],0) for c in result['claims']];expanded=set(selected)
    references=[];visited=set()
    while queue and len(visited)<max_items+MAX_DIAGNOSTICS:
        child,depth=queue.pop(0)
        if child in visited:continue
        visited.add(child)
        parents=available[child]['depends_on'];remaining=max(0,128-len(references))
        result['dependencies']['omitted']+=max(0,len(parents)-remaining)
        for parent in parents[:remaining]:
            ref={'from':child,'id':parent,'delivered':parent in selected,'reason':None}
            if parent not in selected:
                claim=available.get(parent)
                if not claim:ref['reason']=excluded[parent]['reason'] if parent in excluded else 'missing-dependency'
                elif claim['status']!='CONFIRMED' and not include_unconfirmed:ref['reason']='status-policy'
                elif depth>=MAX_DEPTH:ref['reason']='depth-budget'
                elif len(selected)>=max_items:ref['reason']='item-budget'
                else:
                    result['claims'].append(entry(claim));selected.add(parent);expanded.add(parent);ref['delivered']=True
                    new={e['id'] for e in result['evidence']}
                    result['evidence'].extend(evidence_ref(evidence[e]) for e in claim['evidence'] if e in evidence and e not in new)
                    queue.append((parent,depth+1))
            if parent in available:expanded.add(parent)
            references.append(ref)
    result['dependencies']['references']=references
    result['dependencies']['complete']=not result['dependencies']['omitted'] and all(ref['delivered'] for ref in references)
    result['truncation']['candidates']=len(engine.candidate_ids|expanded)
    # Preserve graph edges; withhold the statement of any filtered partner.
    conflicts=[];pairs=set();excluded={n['claim']['id']:n for n in records.get('_excluded',[])}
    for claim in result['claims']:
        for partner in claim['conflicts_with']:
            pair=tuple(sorted((claim['id'],partner)))
            if pair in pairs:continue
            pairs.add(pair);other=available.get(partner);hidden=excluded.get(partner)
            conflicts.append({'claim_id':claim['id'],'partner_id':partner,'partner_status':other['status'] if other else hidden['claim']['status'] if hidden else None,
                'partner_statement':other['statement'] if other else None,'partner_confirmed':bool(other and other['status']=='CONFIRMED'),
                'partner_current':other is not None,'note':'unresolved conflict; independent review required' if other else 'partner context withheld: '+(hidden['reason'] if hidden else 'missing')})
    result['conflicts']=conflicts
    prune(result)
    while True:
        result['partial']=bool(filtered or not result['dependencies']['complete'] or result['truncation']['dropped'])
        if result['claims']:result['result']='matches-with-gaps' if result['partial'] else 'matches'
        elif result['truncation']['candidates']:
            result['result']='budget-exhausted';result['diagnostics']['selection']='budget-exhausted'
        else:result['result']='insufficient-evidence'
        result['budget']['estimated_tokens']=max(1,len(canonical_json(result).encode())//4)
        if len(canonical_json(result).encode())<=max_bytes-1:return result
        if result['diagnostics']['filtered']:
            result['diagnostics']['filtered'].pop();result['diagnostics']['omitted']+=1;continue
        if result['claims']:
            result['claims'].pop();result['truncation']['reason']='byte-budget';prune(result);continue
        minimal={'ok':True,'result':'budget-too-small','claims':[],'evidence':[],'conflicts':[],'partial':True,
            'diagnostics':{'reason':'byte-budget'},'truncation':{'candidates':result['truncation']['candidates'],'returned':0,'dropped':result['truncation']['candidates']}}
        return minimal if len(canonical_json(minimal).encode())<=max_bytes-1 else {'ok':True,'result':'budget-too-small','claims':[],'partial':True}
