"""Exact UTF-8 statement reconciliation. Pure projection; original queue is audit.

No case folding, whitespace rewriting, model, filesystem traversal or SQL loop.
Source/provider/metadata incompatibility blocks rather than losing provenance.
"""
from copy import deepcopy
from collections import defaultdict
from .util import digest, canonical_json

VERSION='exact-utf8-v1'


def operations(item):
    if item['version']==2:return deepcopy(item['operations'])
    return [dict(action='add',kind=kind,id=r['id'],expected=0,payload=deepcopy(r),successor=None)
            for kind,rows in item['records'].items() for r in rows]


def reconcile(current,pending,revisions,bindings=None,p1=True):
    bindings=bindings or {};ops={cid:operations(item) for cid,item in pending.items()}
    canonical={r['id']:(kind,r) for kind,rows in current.items() for r in rows}
    groups=defaultdict(list);existing=defaultdict(list);report=[];aliases={};ealiases={};remove=set();updates=defaultdict(list)
    for claim in current['claims']:
        if revisions.get(claim['id'],{}).get('lifecycle','active')=='active':existing[claim['statement']].append(claim)
    total=sum(map(len,ops.values()));duplicate_refs=0
    for cid,items in ops.items():
        for index,op in enumerate(items):
            if op['action'] in ('add','update','reactivate') and op['kind']=='claims':groups[op['payload']['statement']].append((cid,index,op['payload']))
    def meta(c):return {k:v for k,v in c.items() if k not in ('id','evidence')}
    def scope(cid):return {'source':pending[cid].get('source'),'provider':bindings.get(cid)}
    for statement,rows in sorted(groups.items()):
        old=existing.get(statement,[])
        if len(rows)==1 and not old:continue
        if len(rows)==1 and len(old)==1 and old[0]['id']==rows[0][2]['id']:continue
        actions={ops[cid][index]['action'] for cid,index,_ in rows}
        ordered=sorted(rows,key=lambda row:(row[2]['id'],row[0],row[1]));leader=ordered[0]
        reference=old[0] if old else leader[2]
        conflict=(actions!={'add'} or len(old)>1 or any(meta(c)!=meta(reference) for _,_,c in rows)
                  or any(scope(cid)!=scope(leader[0]) for cid,_,_ in rows)
                  or bool(old and revisions.get(reference['id'],{}).get('lifecycle','active')!='active'))
        entry={'group':digest([VERSION,statement]),'statement_hash':digest(statement),'preview':statement[:240],
               'candidates':sorted({cid for cid,_,_ in rows}),'claims':sorted({c['id'] for _,_,c in rows}),
               'canonical':[c['id'] for c in old],'classification':'canonical-match' if old else 'within-plan',
               'actions':sorted(actions),'resolution':'blocked' if conflict else 'reconciled','reason':'incompatible metadata, source/provider scope, lifecycle or explicit non-add target' if conflict else None}
        report.append(entry)
        if conflict:continue
        evidence=list(reference['evidence'])
        for cid,index,c in ordered:
            aliases[c['id']]=reference['id'];evidence.extend(c['evidence'])
            if old or (cid,index)!=(leader[0],leader[1]):remove.add((cid,index))
        evidence=list(dict.fromkeys(evidence))
        merged=deepcopy(reference);merged['evidence']=evidence
        if old:
            if merged!=reference:
                if not p1:
                    entry.update(resolution='blocked',reason='canonical evidence update requires P1 lifecycle support');continue
                updates[leader[0]].append(dict(action='update',kind='claims',id=reference['id'],expected=revisions[reference['id']]['revision'],payload=merged,successor=None))
        else:ops[leader[0]][leader[1]]['payload']=merged
    # Rewrite only typed graph/evidence references, never arbitrary text.
    for cid,items in ops.items():
        for op in items:
            p=op['payload']
            if not p:continue
            if op['kind']=='evidence':p['substantiates']=list(dict.fromkeys(aliases.get(i,i) for i in p['substantiates']))
            if op['kind']=='claims':
                for field in ('depends_on','conflicts_with'):p[field]=list(dict.fromkeys(aliases.get(i,i) for i in p[field]))
                duplicate_refs+=len(p['evidence'])-len(set(p['evidence']));p['evidence']=list(dict.fromkeys(p['evidence']))
            if op['kind']=='relationships':
                for field in ('from','to'):p[field]=aliases.get(p[field],p[field])
    for kind in ('evidence','relationships'):
        by_signature={canonical_json({k:v for k,v in r.items() if k!='id'}):r['id'] for r in current[kind]}
        seen_ids={r['id']:r for r in current[kind]}
        for cid,items in ops.items():
            for index,op in enumerate(items):
                if op['action']!='add' or op['kind']!=kind:continue
                p=op['payload'];signature=canonical_json({k:v for k,v in p.items() if k!='id'})
                if p['id'] in seen_ids and seen_ids[p['id']]!=p:continue  # validation blocks conflicting IDs
                if p['id'] in canonical and canonical[p['id']]==(kind,p):
                    remove.add((cid,index));continue
                if signature in by_signature:
                    if kind=='evidence':ealiases[p['id']]=by_signature[signature];duplicate_refs+=1
                    remove.add((cid,index))
                else:by_signature[signature]=p['id'];seen_ids[p['id']]=p
    resolved={}
    for cid,item in pending.items():
        selected=[op for index,op in enumerate(ops[cid]) if (cid,index) not in remove]
        selected.extend(updates.get(cid,[]))
        for op in selected:
            if op['payload'] and op['kind']=='claims':op['payload']['evidence']=list(dict.fromkeys(ealiases.get(i,i) for i in op['payload']['evidence']))
        if not selected:resolved[cid]=None;continue
        if selected==operations(item):resolved[cid]=deepcopy(item)
        elif item['version']==2:resolved[cid]={**deepcopy(item),'operations':selected}
        elif p1:resolved[cid]={'version':2,'operation':'batch','operations':selected,'source':None,'reason':'Exact statement/evidence reconciliation; original payload retained in plan'}
        elif all(op['action']=='add' for op in selected):
            records={kind:[] for kind in current}
            for op in selected:records[op['kind']].append(op['payload'])
            resolved[cid]={'version':1,'operation':'add','records':records}
        else:resolved[cid]=None  # explicit conflict above prevents publication
    blocked=[{'code':'duplicate-statement' if g['actions']!=['add'] else 'duplicate-conflict','details':{'group':g['group'],'reason':g['reason']}} for g in report if g['resolution']=='blocked']
    result_ops=[op for v in resolved.values() if v for op in operations(v)]
    counts={'proposed_operations':total,'unique_statements':len(set(groups)|set(existing)),'duplicate_groups':len(report),
            'affected_claim_operations':sum(len(g['claims']) for g in report),'canonical_matches':sum(bool(g['canonical']) for g in report),
            'within_plan_groups':sum(g['classification']=='within-plan' for g in report),'duplicate_evidence_references':duplicate_refs,
            'reconciled_groups':sum(g['resolution']=='reconciled' for g in report),'unresolved_groups':len(blocked),
            'resulting_adds':sum(op['action']=='add' for op in result_ops),'evidence_updates':sum(map(len,updates.values())),
            'skipped_operations':total-len(result_ops)}
    return resolved,{'version':VERSION,'counts':counts,'groups':report},blocked
