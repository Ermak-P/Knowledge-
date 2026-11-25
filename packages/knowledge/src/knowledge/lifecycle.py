from contextlib import closing
"""P1 revisions share P0's database, lock, queue, plans and commit boundaries."""
from copy import deepcopy
from datetime import datetime, timezone
import sqlite3
from .util import require, canonical_json, loads, fingerprint, digest


def now():
    return datetime.now(timezone.utc).isoformat()


def enabled(db):
    return db.execute("SELECT value FROM metadata WHERE key='p1'").fetchone() == ('1',)


def envelope(value):
    from .store import shape, empty
    require(isinstance(value,dict) and set(value)=={'version','operation','operations','reason','source'}, 'invalid-v2-envelope')
    require(type(value['version']) is int and value['version']==2 and value['operation']=='batch','unsupported-operation')
    require(isinstance(value['reason'],str) and bool(value['reason'].strip()),'reason-required')
    require(value['source'] is None or isinstance(value['source'],dict),'invalid-source-binding')
    if value['source'] is not None:
        import re
        source=value['source']
        require(set(source) in ({'identity','revision','kind'},{'identity','revision','kind','delta'}) and isinstance(source['identity'],str) and re.fullmatch('[a-f0-9]{64}',source['identity']) and (source['revision'] is None or isinstance(source['revision'],str)) and source['kind'] in ('committed','working-tree-with-hashes','filesystem-no-history'),'invalid-source-binding')
    require(isinstance(value['operations'],list) and 0<len(value['operations'])<=10000,'invalid-operations')
    seen=set()
    for op in value['operations']:
        require(isinstance(op,dict) and set(op)=={'action','kind','id','expected','payload','successor'},'invalid-operation-fields')
        require(op['action'] in ('add','update','retire','supersede','reactivate') and op['kind'] in ('claims','evidence','relationships'),'unsupported-operation')
        require(isinstance(op['id'],str) and op['id'] not in seen,'ambiguous-operation-target');seen.add(op['id'])
        require(type(op['expected']) is int and op['expected']>=0,'invalid-expected-revision')
        if op['action']=='reactivate':require(op['kind'] in ('claims','relationships'),'unsupported-reactivation-kind')
        if op['action'] in ('add','update','reactivate'):
            require(op['successor'] is None and isinstance(op['payload'],dict) and op['payload'].get('id')==op['id'],'invalid-operation-payload')
            records=empty();records[op['kind']]=[op['payload']];shape(records)
            if op['kind']=='claims':require(bool(op['payload']['evidence']),'candidate-requires-evidence')
        else:
            require(op['payload'] is None,'unexpected-operation-payload')
            require(op['kind'] in ('claims','relationships'),'unsupported-retirement-kind')
            require((op['action']=='supersede' and op['kind']=='claims' and isinstance(op['successor'],str) and op['successor']!=op['id']) or
                    (op['action']=='retire' and op['successor'] is None),'invalid-successor')
    return deepcopy(value)


def op(action,kind,identifier,expected,payload=None,successor=None):
    return dict(action=action,kind=kind,id=identifier,expected=expected,payload=payload,successor=successor)


def batch(operations,reason,source=None):
    return envelope(dict(version=2,operation='batch',operations=operations,reason=reason,source=source))


def latest(db):
    return {i:loads(p) for i,p in db.execute('SELECT id,payload FROM revisions r WHERE revision=(SELECT MAX(revision) FROM revisions WHERE id=r.id)')}


def revision(db,identifier):
    return db.execute('SELECT COALESCE(MAX(revision),0) FROM revisions WHERE id=?',(identifier,)).fetchone()[0]


def append(db,identifier,kind,payload,state,pid,reason,source,successor=None):
    value=dict(id=identifier,kind=kind,revision=revision(db,identifier)+1,record=payload,lifecycle=state,
               successor=successor,plan=pid,reason=reason,source=source,captured_at=now(),verified_at=None)
    db.execute('INSERT INTO revisions VALUES (?,?,?)',(identifier,value['revision'],canonical_json(value)))
    return value


def state_fingerprint(store,db):
    return fingerprint({'records':store._records(db),'revisions':latest(db)})


def simulate(store,db,items,check_source=True):
    records=store._records(db); current={r['id']:(g,r) for g,rs in records.items() for r in rs}
    states=latest(db); versions={i:s['revision'] for i,s in states.items()};touched=set(); checked_sources=set()
    for value in items.values():
        if value['version']==1:
            for kind,rs in value['records'].items():
                for r in rs:
                    require(r['id'] not in touched,'conflicting-batch-target');touched.add(r['id'])
                    require(r['id'] not in current,'record-id-conflict');current[r['id']]=(kind,r)
                    states[r['id']]={'lifecycle':'active'}
            continue
        if value['source'] is not None and check_source and value['source'].get('identity') not in checked_sources:
            from .discovery import inventory
            require(inventory(store.project.root)['identity']==value['source'].get('identity'),'source-drift-rescan-required')
            checked_sources.add(value['source']['identity'])
        for change in value['operations']:
            i=change['id']; require(i not in touched,'conflicting-batch-target');touched.add(i)
            require(versions.get(i,0)==change['expected'],'stale-expected-revision',i)
            action=change['action']; prior=current.get(i)
            if action=='add': require(prior is None and change['expected']==0,'record-id-conflict')
            else:
                require(prior is not None and prior[0]==change['kind'],'unknown-operation-target')
                require(states[i]['lifecycle']==('retired' if action=='reactivate' else 'active'),'invalid-reactivation-target' if action=='reactivate' else 'inactive-target')
            payload,lifecycle,successor=resulting_record(change,prior[1] if prior else None)
            current[i]=(change['kind'],payload)
            states[i]={'lifecycle':lifecycle,'successor':successor}
    combined={g:[] for g in records}
    for kind,r in current.values():combined[kind].append(r)
    validate_model(combined,states)
    return combined


def apply_item(store,db,value,pid):
    from .store import checkpoint
    for change in value['operations']:
        i=change['id']; prior=db.execute('SELECT payload FROM records WHERE id=?',(i,)).fetchone()
        payload,state,successor=resulting_record(change,loads(prior[0]) if prior else None)
        if change['action']=='add':db.execute('INSERT INTO records VALUES (?,?,?)',(i,change['kind'],canonical_json(payload)))
        elif change['action'] in ('update','reactivate'):db.execute('UPDATE records SET payload=? WHERE id=?',(canonical_json(payload),i))
        append(db,i,change['kind'],payload,state,pid,value['reason'],value['source'],successor)
        checkpoint('canonical-record-written')


def upgrade_snapshot(db):
    return {table:list(db.execute('SELECT * FROM '+table+' ORDER BY rowid')) for table in ('metadata','records','queue','plans','history')}


def upgrade_preview(store):
    with store.connection() as db:
        version=db.execute("SELECT value FROM metadata WHERE key='p1'").fetchone()
        require(version is None or version==('1',),'unsupported-extension-version')
        value={'version':1,'operation':'upgrade-p1','project':store.project.identity,'base':fingerprint(upgrade_snapshot(db)),'already_upgraded':version is not None}
        return {'ok':True,'fingerprint':fingerprint(value),**value}


def upgrade(store,approval):
    preview=upgrade_preview(store);require(approval==preview['fingerprint'],'exact-upgrade-approval-required')
    if preview['already_upgraded']:return {'ok':True,'result':'already-upgraded'}
    # A SQLite-consistent backup is retained before mutation; never overwrite one.
    backup=store.base/('backup-'+preview['fingerprint'][7:]+'.sqlite3')
    if not backup.exists():
        with closing(sqlite3.connect(store.path)) as source,closing(sqlite3.connect(backup)) as dest, dest:source.backup(dest)
    with closing(sqlite3.connect(backup)) as saved:
        require(fingerprint(upgrade_snapshot(saved))==preview['base'],'backup-state-mismatch-repreview')
    with store.connection(True) as db:
        require(fingerprint(upgrade_snapshot(db))==preview['base'],'stale-upgrade-preview')
        require(not enabled(db),'upgrade-already-completed-repreview')
        db.execute('CREATE TABLE revisions(id TEXT, revision INTEGER, payload TEXT NOT NULL, PRIMARY KEY(id,revision))')
        db.execute('CREATE TABLE scans(id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
        db.execute('CREATE TABLE reviews(sequence INTEGER PRIMARY KEY,payload TEXT NOT NULL)')
        for kind,rs in store._records(db).items():
            for r in rs:append(db,r['id'],kind,r,'active','upgrade','preserved P0 payload; verification time unknown',None)
        # Seal old ownership to historical receipts without altering P0 queue/plans/history.
        db.execute('CREATE TABLE receipts(plan TEXT PRIMARY KEY,payload TEXT NOT NULL)')
        for pid,p,state in db.execute("SELECT id,payload,status FROM plans WHERE status!='PREPARED'"):
            db.execute('INSERT INTO receipts VALUES (?,?)',(pid,p))
        db.execute("INSERT INTO metadata VALUES ('p1','1')")
    return {'ok':True,'result':'upgraded','backup':str(backup)}


def dispose(store,cid,disposition,reason):
    require(disposition in ('pending','rejected','deferred') and isinstance(reason,str) and reason.strip(),'invalid-review-disposition')
    with store.connection(True) as db:
        require(enabled(db),'upgrade-required')
        row=db.execute('SELECT payload,status FROM queue WHERE id=?',(cid,)).fetchone()
        require(row is not None and row[1]!='imported','candidate-not-reviewable')
        # A committed pending acknowledgment must retain ownership.
        for payload, in db.execute("SELECT payload FROM plans WHERE status='COMMITTED'"):
            require(cid not in loads(payload)['included'],'acknowledge-before-review')
        db.execute('INSERT INTO reviews(payload) VALUES (?)',(canonical_json(dict(candidate=cid,payload=loads(row[0]),disposition=disposition,reason=reason,at=now())),))
        db.execute('UPDATE queue SET status=? WHERE id=?',(disposition,cid))
    return {'ok':True,'candidate':cid,'disposition':disposition}


def history(store,identifier):
    with store.connection() as db:
        require(enabled(db),'upgrade-required')
        return {'ok':True,'id':identifier,'revisions':[loads(p) for p, in db.execute('SELECT payload FROM revisions WHERE id=? ORDER BY revision',(identifier,))]}


def active(store,db,records,diagnostics=False):
    if not enabled(db):return records
    states=latest(db)
    from .discovery import freshness,analysis_scope,DISCOVERY_METHODS
    evidence={e['id']:e for e in records['evidence']}
    needs_scope=any(evidence[i].get('provenance',{}).get('method') in DISCOVERY_METHODS
        for c in records['claims'] if states[c['id']]['lifecycle']=='active' for i in c['evidence'] if i in evidence)
    scope=analysis_scope(store.project.root) if needs_scope else None
    checks={c['id']:freshness(store.project.root,c,records,scope) for c in records['claims'] if states[c['id']]['lifecycle']=='active'}
    allowed={i for i,check in checks.items() if check['trusted']}
    while True:
        filtered={c['id'] for c in records['claims'] if c['id'] in allowed and all(d in allowed for d in c['depends_on'])}
        if filtered==allowed:break
        allowed=filtered
    result=dict(claims=[dict(c,_p1={'lifecycle':'active','revision':states[c['id']]['revision'],'freshness':checks[c['id']]}) for c in records['claims'] if c['id'] in allowed],
        evidence=records['evidence'],relationships=[r for r in records['relationships'] if states[r['id']]['lifecycle']=='active' and r['from'] in allowed and r['to'] in allowed])
    if diagnostics:
        result['_excluded']=[]
        for c in records['claims']:
            if c['id'] in allowed:continue
            state=states[c['id']];check=checks.get(c['id'])
            reason='lifecycle-'+state['lifecycle'] if state['lifecycle']!='active' else 'dependency-filtered' if check and check['trusted'] else 'evidence-filtered'
            if check and 'not-analyzed' in check.get('evidence',{}).values():reason='blocked-source-scope'
            result['_excluded'].append({'claim':c,'revision':state['revision'],'lifecycle':state['lifecycle'],'reason':reason,'freshness':check})
    return result


def validate_model(records,states):
    """Validate full references and the current graph separately from historical edges."""
    from .store import shape,statement_key as normalized
    shape(records)
    claims={r['id']:r for r in records['claims']};evidence={r['id']:r for r in records['evidence']}
    require(set(states)=={r['id'] for rs in records.values() for r in rs},'revision-identity-mismatch')
    active={i for i,s in states.items() if s['lifecycle']=='active'}
    statements=[normalized(c['statement']) for i,c in claims.items() if i in active]
    require(len(statements)==len(set(statements)),'duplicate-statement')
    validate_successors(states,set(claims))
    for e in evidence.values():require(all(i in claims for i in e['substantiates']),'orphan-evidence')
    for i,c in claims.items():
        require(all(e in evidence for e in c['evidence']),'orphan-claim-evidence')
        for field in ('depends_on','conflicts_with'):
            require(all(d in claims and d!=i for d in c[field]),'orphan-or-self-claim-reference')
        if i not in active:continue
        require(all(d in active for d in c['depends_on']),'active-dependent-needs-reviewed-change',i)
        require(all(i in claims[d]['conflicts_with'] for d in c['conflicts_with'] if d in active),'asymmetric-current-conflict')
        if c['status']=='CONFIRMED':
            allowed=('direct-authoritative',) if c['type']=='business_rule' else ('direct-authoritative','direct-technical')
            require(c['last_verified'] is not None and any(evidence[e]['type'] in allowed and evidence[e].get('location') and i in evidence[e]['substantiates'] for e in c['evidence']),'confirmed-requires-support')
    edges=set()
    for r in records['relationships']:
        require(r['from'] in claims and r['to'] in claims and r['from']!=r['to'],'orphan-or-self-relationship')
        if r['id'] not in active:continue
        require(r['from'] in active and r['to'] in active,'active-relationship-needs-reviewed-change',r['id'])
        require(r['to'] in claims[r['from']][r['type']],'current-relationship-mismatch')
        edge=(r['type'],*(sorted((r['from'],r['to'])) if r['type']=='conflicts_with' else (r['from'],r['to'])))
        require(edge not in edges,'duplicate-current-relationship');edges.add(edge)
    visiting=set();done=set()
    def visit(i):
        require(i not in visiting,'dependency-cycle')
        if i in done:return
        visiting.add(i)
        for d in claims[i]['depends_on']:visit(d)
        visiting.remove(i);done.add(i)
    for i in claims:
        if i in active:visit(i)
    return []


def verify_source_bindings(store,values):
    identities={v['source']['identity'] for v in values if v.get('source') is not None}
    if identities:
        from .discovery import inventory
        current=inventory(store.project.root)['identity']
        require(identities=={current},'source-drift-before-commit-rescan-required')


def validate_successors(states,claims):
    for identifier,state in states.items():
        if state['lifecycle']!='superseded':continue
        seen={identifier};target=state['successor']
        while True:
            require(target in claims,'successor-must-be-claim')
            require(target not in seen,'successor-cycle')
            seen.add(target);successor=states[target]
            if successor['lifecycle']=='active':break
            require(successor['lifecycle']=='superseded','inactive-successor-terminal')
            target=successor['successor']


def resulting_record(change,previous):
    """One transition definition for preview and commit; target checks stay upstream."""
    action=change['action']
    states={'add':'active','update':'active','reactivate':'active','retire':'retired','supersede':'superseded'}
    require(action in states,'unsupported-operation')
    payload=change['payload'] if action in ('add','update','reactivate') else previous
    require(payload is not None,'unknown-operation-target')
    return deepcopy(payload),states[action],change['successor']
