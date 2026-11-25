"""Exact UTF-8 statement reconciliation. Pure projection; original queue is audit.

No case folding, whitespace rewriting, model, filesystem traversal or SQL loop.
Source/provider/metadata incompatibility blocks rather than losing provenance.
"""
from copy import deepcopy
from collections import defaultdict
import unicodedata
from datetime import date
from .util import digest, canonical_json

VERSION='exact-utf8-v1'


def operations(item,copy=True):
    if item['version']==2:return deepcopy(item['operations']) if copy else item['operations']
    return [dict(action='add',kind=kind,id=r['id'],expected=0,payload=deepcopy(r) if copy else r,successor=None)
            for kind,rows in item['records'].items() for r in rows]


def reconcile(current,pending,revisions,bindings=None,p1=True,preferred=None,project=None,progress=None):
    tick=progress or (lambda *args,**kwargs:None)
    preferred=preferred or {}
    bindings=bindings or {};ops={cid:operations(item,False) for cid,item in pending.items()};copied=False
    canonical={r['id']:(kind,r) for kind,rows in current.items() for r in rows}
    groups=defaultdict(list);existing=defaultdict(list);report=[];aliases={};ealiases={};remove=set();updates=defaultdict(list)
    for claim in current['claims']:
        if revisions.get(claim['id'],{}).get('lifecycle','active')=='active':existing[claim['statement']].append(claim)
    total=sum(map(len,ops.values()));duplicate_refs=0
    tick('indexing-exact-statements',total_operations=total)
    for cid,items in ops.items():
        for index,op in enumerate(items):
            if op['action'] in ('add','update','reactivate') and op['kind']=='claims':groups[op['payload']['statement']].append((cid,index,op['payload']))
    def meta(c):return {k:v for k,v in c.items() if k not in ('id','evidence','last_verified')}
    def scope(cid):return {'source':pending[cid].get('source'),'provider':bindings.get(cid)}
    proofs={r['id']:r for r in current['evidence']}
    candidate_proofs={cid:{o['id']:o['payload'] for o in items if o['kind']=='evidence' and o['payload']} for cid,items in ops.items()}
    def trust(cid,claim):
        rows=proofs if cid is None else {**proofs,**candidate_proofs[cid]}
        return {canonical_json({k:rows[i][k] for k in ('type','status','provenance')}) for i in claim['evidence'] if i in rows}
    def mutable():
        nonlocal ops,copied
        if not copied:ops=deepcopy(ops);copied=True
    tick('detecting-duplicate-groups',total_operations=total,duplicate_groups=sum(len(rows)>1 for rows in groups.values()))
    tick('reconciling-claims')
    for statement,rows in sorted(groups.items()):
        old=existing.get(statement,[])
        if len(rows)==1 and not old and preferred.get(rows[0][2]['id'],rows[0][2]['id'])==rows[0][2]['id']:continue
        if len(rows)==1 and len(old)==1 and old[0]['id']==rows[0][2]['id'] and ops[rows[0][0]][rows[0][1]]['action']!='add':continue
        actions={ops[cid][index]['action'] for cid,index,_ in rows}
        ordered=sorted(rows,key=lambda row:(row[2]['id'],row[0],row[1]));leader=ordered[0]
        reference=old[0] if old else leader[2]
        targets={preferred[c['id']] for _,_,c in rows if c['id'] in preferred}
        producer=any(c['provenance']=={'actor':'deterministic-discovery','method':'dotnet-lexical-v3'} for _,_,c in rows)
        target=reference['id'] if old else next(iter(targets)) if len(targets)==1 else reference['id'] if len({c['id'] for _,_,c in rows})==1 else 'dedup.'+digest(['exact-statement-v1',project,meta(reference),scope(leader[0])])[:40]
        dates=[reference['last_verified']]+[c['last_verified'] for _,_,c in rows]
        incompatible_dates=False
        if len(set(dates))>1:
            try:
                for value in dates:date.fromisoformat(value)
            except (ValueError,TypeError):incompatible_dates=True
        conflict=(actions!={'add'} or len(old)>1 or any(meta(c)!=meta(reference) for _,_,c in rows)
                  or incompatible_dates
                  or any(scope(cid)!=scope(leader[0]) for cid,_,_ in rows)
                  or len(targets)>1 or bool(not old and producer and (len(targets)!=1 or any(c['id'] not in preferred for _,_,c in rows)))
                  or bool(old and revisions.get(reference['id'],{}).get('lifecycle','active')!='active'))
        trusts=[trust(None,c) for c in old]+[trust(cid,c) for cid,_,c in rows]
        if any(value!=trusts[0] for value in trusts[1:]):conflict=True
        reasons=[]
        if actions!={'add'}:reasons.append('explicit-update-or-reactivation-target')
        if len(old)>1:reasons.append('multiple-canonical-identities')
        if any(meta(c)!=meta(reference) for _,_,c in rows):reasons.append('incompatible-claim-metadata-or-confidence')
        if incompatible_dates:reasons.append('incompatible-verification-dates')
        if any(scope(cid)!=scope(leader[0]) for cid,_,_ in rows):reasons.append('source-or-provider-scope-differs')
        if len(targets)>1:reasons.append('producer-identities-disagree')
        if not old and producer and (len(targets)!=1 or any(c['id'] not in preferred for _,_,c in rows)):reasons.append('missing-verified-producer-identity')
        if any(value!=trusts[0] for value in trusts[1:]):reasons.append('incompatible-evidence-trust')
        entry={'group':digest([VERSION,statement]),'statement_hash':digest(statement),'preview':statement[:240],
               'candidates':sorted({cid for cid,_,_ in rows}),'claims':sorted({c['id'] for _,_,c in rows}),
               'canonical':[c['id'] for c in old],'classification':'canonical-match' if old else 'within-plan' if len(rows)>1 else 'identity-compatibility',
               'target_identity':target,'evidence_references':sum(len(c['evidence']) for _,_,c in rows),
               'actions':sorted(actions),'resolution':'blocked' if conflict else 'reconciled','reason':', '.join(reasons) if conflict else None}
        report.append(entry)
        if conflict:continue
        evidence=list(reference['evidence']) if old else []
        for cid,index,c in ordered:
            aliases[c['id']]=target;evidence.extend(c['evidence'])
            if old or (cid,index)!=(leader[0],leader[1]):remove.add((cid,index))
        duplicate_refs+=len(evidence)-len(set(evidence));evidence=list(dict.fromkeys(evidence))
        merged=deepcopy(reference);merged['id']=target;merged['evidence']=evidence
        if not old and not incompatible_dates:merged['last_verified']=min(dates) if all(d is not None for d in dates) else None
        if old:
            if merged!=reference:
                if not p1:
                    entry.update(resolution='blocked',reason='canonical evidence update requires P1 lifecycle support');continue
                updates[leader[0]].append(dict(action='update',kind='claims',id=reference['id'],expected=revisions[reference['id']]['revision'],payload=merged,successor=None))
        else:
            mutable();ops[leader[0]][leader[1]]['payload']=merged;ops[leader[0]][leader[1]]['id']=target
    by_id=defaultdict(list)
    for rows in groups.values():
        for row in rows:by_id[row[2]['id']].append(row)
    for identifier,rows in sorted(by_id.items()):
        texts={c['statement'] for _,_,c in rows}
        old=canonical.get(identifier)
        if old and old[0]=='claims' and any(ops[cid][index]['action']=='add' for cid,index,_ in rows):texts.add(old[1]['statement'])
        if len(texts)<2:continue
        report.append({'group':digest(['identity-collision',identifier]),'statement_hash':digest(sorted(texts)),
                       'statement_hashes':sorted(digest(s) for s in texts),'preview':sorted(texts)[0][:240],
                       'claims':[identifier],'candidates':sorted({cid for cid,_,_ in rows}),'canonical':[identifier] if old else [],
                       'classification':'identity-collision','actions':sorted({ops[cid][index]['action'] for cid,index,_ in rows}),
                       'resolution':'blocked','reason':'one claim identity has different exact statements; explicit identity review required'})
    legacy=defaultdict(set)
    for text in set(groups)|set(existing):legacy[' '.join(unicodedata.normalize('NFKC',text).casefold().split())].add(text)
    for key,texts in sorted(legacy.items()):
        if len(texts)<2:continue
        members=[row for text in sorted(texts) for row in groups.get(text,[])]
        report.append({'group':digest(['legacy-normalization',key]),'statement_hash':digest(key),
                       'statement_hashes':sorted(digest(text) for text in texts),'preview':sorted(texts)[0][:240],
                       'candidates':sorted({cid for cid,_,_ in members}),'claims':sorted({c['id'] for _,_,c in members}),
                       'canonical':sorted(c['id'] for text in texts for c in existing.get(text,[])),
                       'classification':'legacy-normalization-collision','resolution':'kept-distinct','reason':None})
    tick('reconciling-evidence',resolved_groups=sum(g['resolution']=='reconciled' for g in report))
    proof_repeat=False
    for kind in ('evidence','relationships'):
        signatures={canonical_json({k:v for k,v in r.items() if k!='id'}) for r in current[kind]}
        for items in ops.values():
            for op in items:
                if op['action']!='add' or op['kind']!=kind:continue
                signature=canonical_json({k:v for k,v in op['payload'].items() if k!='id'})
                if signature in signatures:proof_repeat=True
                signatures.add(signature)
    if not aliases and not remove and not updates and not proof_repeat:
        resolved=dict(pending)
    else:
        mutable()
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
            if selected==operations(item,False):resolved[cid]=item
            elif item['version']==2:resolved[cid]={**deepcopy(item),'operations':selected}
            elif p1:resolved[cid]={'version':2,'operation':'batch','operations':selected,'source':None,'reason':'Exact statement/evidence reconciliation; original payload retained in plan'}
            elif all(op['action']=='add' for op in selected):
                records={kind:[] for kind in current}
                for op in selected:records[op['kind']].append(op['payload'])
                resolved[cid]={'version':1,'operation':'add','records':records}
            else:resolved[cid]=None  # explicit conflict above prevents publication
    blocked=[{'code':'duplicate-statement' if g['actions']!=['add'] else 'duplicate-conflict','details':{'group':g['group'],'reason':g['reason']}} for g in report if g['resolution']=='blocked']
    result_ops=[op for v in resolved.values() if v for op in operations(v,False)]
    counts={'proposed_operations':total,'unique_statements':len(set(groups)|set(existing)),'duplicate_groups':sum(len(rows)>1 for rows in groups.values()),
            'proposed_claim_operations':sum(len(v) for v in groups.values()),'unique_claim_identities':len({c['id'] for rows in groups.values() for _,_,c in rows}),
            'exact_duplicate_statement_groups':sum(len(rows)>1 for rows in groups.values()),
            'claims_in_duplicate_groups':sum(len(rows) for rows in groups.values() if len(rows)>1),
            'redundant_claim_records':sum(len(rows)-1 for rows in groups.values() if len(rows)>1),
            'legacy_normalization_collisions':sum(g['classification']=='legacy-normalization-collision' for g in report),
            'affected_claim_operations':sum(len(rows) for rows in groups.values() if len(rows)>1),'canonical_matches':sum(bool(g['canonical']) for g in report),
            'identity_compatibility_groups':sum(g['classification']=='identity-compatibility' for g in report),
            'within_plan_groups':sum(g['classification']=='within-plan' for g in report),'duplicate_evidence_references':duplicate_refs,
            'reconciled_groups':sum(g['resolution']=='reconciled' for g in report),'unresolved_groups':len(blocked),
            'resulting_adds':sum(op['action']=='add' for op in result_ops),'evidence_updates':sum(map(len,updates.values())),
            'skipped_operations':total-len(result_ops)}
    counts.update(resulting_claim_adds=sum(o['action']=='add' and o['kind']=='claims' for o in result_ops),
                  resulting_evidence_operations=sum(o['kind']=='evidence' for o in result_ops),evidence_references_remapped=sum(len(c['evidence']) for rows in groups.values() for _,_,c in rows if aliases.get(c['id'],c['id'])!=c['id']))
    report.sort(key=lambda g:(g['resolution']!='blocked',g['classification'],g['group']))
    return resolved,{'version':VERSION,'counts':counts,'groups':report,
                     'claim_aliases':{k:v for k,v in sorted(aliases.items()) if k!=v},
                     'evidence_aliases':{k:v for k,v in sorted(ealiases.items()) if k!=v}},blocked
