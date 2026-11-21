"""Durable operational memory. No model, shell, Harness import, or implicit grant.

The optional extension shares the canonical SQLite transaction/maintenance gate.
Architecture records, queues and their approval contracts remain independent.
"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import fnmatch
import os
import re
import sqlite3
import tempfile
import time
from .project import Project, safe_path, safe_tree
from .store import Store, create_tables, normalized
from .coordination import gate
from .util import KnowledgeError, canonical_json, digest, loads, require

VERSION = '1'
SCOPES = ('project', 'shared')


def shared_root(override=None):
    """Explicit absolute override > programmatic current home; never shell '~'."""
    path = Path(override) if override is not None else Path.home()/'.local/share/knowledge'
    require(path.is_absolute() and '..' not in path.parts, 'invalid-shared-root')
    safe_tree(path)
    return path


class OperationalStore(Store):
    def __init__(self, root, scope='project', shared=None):
        require(scope in SCOPES, 'invalid-memory-scope')
        self.scope = scope
        if scope == 'project':
            super().__init__(root)
        else:
            base = shared_root(shared)
            self.project = SimpleNamespace(root=base, base=base, db=base/'store.sqlite3',
                identity=digest('shared:'+os.path.normcase(str(base.absolute()))))
            self.base, self.path = base, base/'store.sqlite3'

    def ensure(self):
        if self.scope == 'shared':
            safe_tree(self.base)
            self.base.mkdir(parents=True, exist_ok=True, mode=0o700)
        with gate(self.project.root, exclusive=True):
            if not self.path.exists():
                if self.scope == 'project':
                    self.init()
                else:
                    fd, name = tempfile.mkstemp(prefix='init-', dir=self.base)
                    os.close(fd)
                    try:
                        db = sqlite3.connect(name)
                        try:
                            db.execute('PRAGMA synchronous=FULL')
                            create_tables(db, self.project.identity)
                            db.commit()
                        finally:
                            db.close()
                        os.replace(name, self.path)
                        if os.name == 'posix':
                            fd = os.open(self.base, os.O_RDONLY)
                            try: os.fsync(fd)
                            finally: os.close(fd)
                    finally:
                        if os.path.exists(name): os.unlink(name)
            with self.connection(True) as db:
                if not enabled(db):
                    db.execute('CREATE TABLE operational_current(id TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL)')
                    db.execute('CREATE TABLE operational_history(id TEXT NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(id,revision))')
                    db.execute('CREATE TABLE operational_events(id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
                    db.execute("INSERT INTO metadata VALUES ('operations',?)", (VERSION,))

    def records(self):
        if not self.path.exists():
            return {'state': 'absent', 'records': []}
        with self.connection() as db:
            records=current(db)
            signals={};bindings={}
            if enabled(db):
                for payload, in db.execute('SELECT payload FROM operational_events ORDER BY rowid'):
                    result=loads(payload)['result']
                    record=next((r for r in records if r['id']==result.get('id')),None)
                    if record is None or record['revision']!=result.get('revision'):continue
                    if 'binding_state' in result:
                        old=bindings.get(result['id'])
                        if old is None or result['binding_state'].get('sequence',0)>=old.get('sequence',0):bindings[result['id']]=result['binding_state']
                    if 'application' in result:
                        signals[result['id']]=result['application']
            return {'state': 'available', 'records': records, 'signals':signals,'bindings':bindings}

    def history(self, identifier):
        with self.connection() as db:
            require(enabled(db), 'memory-absent')
            return [loads(p) for p, in db.execute('SELECT payload FROM operational_history WHERE id=? ORDER BY revision', (identifier,))]


def enabled(db):
    row = db.execute("SELECT value FROM metadata WHERE key='operations'").fetchone()
    require(row is None or row[0] == VERSION, 'unsupported-operational-extension')
    return row is not None


def validate_record(record):
    require(isinstance(record, dict) and record.get('version') == 1 and
        isinstance(record.get('id'), str) and len(record['id']) == 64 and
        type(record.get('revision')) is int and record['revision'] > 0 and
        record.get('kind') in ('instruction', 'experience') and
        record.get('status') in ('active', 'unbound', 'retired', 'candidate') and
        record.get('scope') in SCOPES, 'invalid-operational-record')
    require(isinstance(record.get('original'), str) and isinstance(record.get('normalized'), str)
        and isinstance(record.get('provenance'), dict) and isinstance(record.get('applicability'), dict), 'invalid-operational-source')
    require(record.get('authority') == ('user' if record['kind'] == 'instruction' else 'observation'), 'invalid-operational-authority')
    if record['status'] == 'active':
        require(record['kind'] == 'instruction', 'candidate-cannot-be-instruction')
        validate_binding(record['trigger'], record['behavior'])
    require(record.get('content_hash') == digest({k:v for k,v in record.items() if k != 'content_hash'}), 'operational-record-hash-mismatch')


def current(db):
    if not enabled(db): return []
    rows = []
    for identifier, revision, payload in db.execute('SELECT id,revision,payload FROM operational_current ORDER BY id'):
        value = loads(payload); validate_record(value)
        require(value['id'] == identifier and value['revision'] == revision, 'operational-identity-mismatch')
        history = list(db.execute('SELECT revision,payload FROM operational_history WHERE id=? ORDER BY revision', (identifier,)))
        require([r for r,p in history] == list(range(1,revision+1)) and history[-1][1] == payload, 'operational-history-mismatch')
        for r,p in history:
            old = loads(p);validate_record(old)
            require(old['id'] == identifier and old['revision'] == r, 'operational-history-mismatch')
        rows.append(value)
    require(db.execute('SELECT count(DISTINCT id) FROM operational_history').fetchone()[0] == len(rows), 'orphan-operational-history')
    for event_id,payload in db.execute('SELECT id,payload FROM operational_events'):
        event=loads(payload)
        require(isinstance(event,dict) and isinstance(event.get('request'),str) and len(event['request'])==64 and isinstance(event.get('result'),dict),'corrupt-operational-event')
        result=event['result']
        require(any(r['id']==result.get('id') and r['revision']>=result.get('revision',0) for r in rows),'orphan-operational-event')
    return rows


def validate_binding(trigger, behavior):
    require(isinstance(trigger, dict) and set(trigger) == {'tool', 'name'} and
        all(isinstance(v,str) and 0<len(v)<=200 for v in trigger.values()), 'invalid-memory-trigger')
    require(isinstance(behavior,dict) and behavior.get('adapter') in ('preserve-format','check','dependency'), 'unsupported-memory-action')
    expected={'adapter'} if behavior['adapter']=='preserve-format' else {'adapter','procedure'}
    require(expected<=set(behavior)<=expected|({'capability'} if behavior['adapter']=='dependency' else set()),'invalid-memory-behavior')
    if 'capability' in behavior:
        from .procedure_templates import parameters
        cap=behavior['capability'];require(isinstance(cap,dict) and set(cap)=={'template','parameters'} and isinstance(cap['template'],str),'invalid-procedure-capability')
        parameters(cap['parameters'])
    if behavior['adapter'] != 'preserve-format': validate_procedure(behavior['procedure'])


def validate_procedure(p):
    require(isinstance(p,dict) and {'id','check','deadline','interval','attempts'}<=set(p)<={'id','check','deadline','interval','attempts','docker'}, 'invalid-memory-procedure')
    require(isinstance(p['id'],str) and p['id'].isidentifier(), 'invalid-procedure-id')
    c=p['check'];require(isinstance(c,dict) and set(c)=={'argv','timeout'},'invalid-readiness-check')
    require(isinstance(c['argv'],list) and 0<len(c['argv'])<=30 and all(isinstance(a,str) and len(a)<=2000 and '\0' not in a for a in c['argv']) and Path(c['argv'][0]).is_absolute(), 'invalid-readiness-argv')
    require(type(c['timeout']) is int and 1<=c['timeout']<=60 and type(p['deadline']) is int and 1<=p['deadline']<=120 and
        type(p['interval']) in (int,float) and .05<=p['interval']<=10 and type(p['attempts']) is int and p['attempts'] in (0,1), 'invalid-recovery-bounds')
    if 'docker' in p:
        d=p['docker'];require(isinstance(d,dict) and 'executable' in d and Path(d['executable']).is_absolute(), 'invalid-docker-binding')
        keys=set(d)-{'context','project_name','env_file'}
        require(keys in ({'executable','container'},{'executable','compose_file','service'}), 'ambiguous-docker-binding')
        if 'context' in d:require(isinstance(d['context'],str) and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',d['context']),'invalid-docker-context')
        if 'container' in d: require(isinstance(d['container'],str) and re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}',d['container']), 'invalid-container-binding')
        else:
            require(Path(d['compose_file']).is_absolute() and isinstance(d['service'],str) and re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}',d['service']), 'invalid-compose-binding')
        if 'project_name' in d:require(isinstance(d['project_name'],str) and re.fullmatch('[a-z0-9][a-z0-9_-]{0,127}',d['project_name']),'invalid-compose-project')
        if 'env_file' in d:require(isinstance(d['env_file'],str) and Path(d['env_file']).is_absolute(),'invalid-compose-env-file')
        require('compose_file' in d or not ({'project_name','env_file'}&set(d)),'invalid-container-compose-fields')


def validate_applicability(value):
    require(isinstance(value,dict) and set(value)<={'machine','environment','os','tools'}, 'invalid-memory-applicability')
    require(all(isinstance(v,str) and 0<len(v)<=200 for k,v in value.items() if k!='tools'), 'invalid-memory-applicability')
    if 'tools' in value: require(isinstance(value['tools'],dict) and all(isinstance(k,str) and isinstance(v,str) for k,v in value['tools'].items()), 'invalid-tool-applicability')


def clean_text(text):
    require(isinstance(text,str) and 0<len(text)<=8000, 'invalid-teaching-text')
    reject_secrets(text)
    return ' '.join(text.split())


def reject_secrets(text):
    require(not re.search(r'(?i)(?:password|api[_-]?key|access[_-]?token|secret)\s*[:=]\s*\S+|-----BEGIN .*PRIVATE KEY|\bBearer\s+\S+|\b(?:sk-|ghp_)[a-zA-Z0-9_-]{20,}|https?://[^/\s]+:[^/@\s]+@|--(?:password|token|secret)(?:[ =]|\\u0020)',text),'memory-secret-denied')


def append(db, value):
    value['content_hash'] = digest(value)
    validate_record(value)
    payload=canonical_json(value)
    db.execute('INSERT INTO operational_history VALUES (?,?,?)',(value['id'],value['revision'],payload))
    db.execute('INSERT INTO operational_current VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,payload=excluded.payload',(value['id'],value['revision'],payload))


def _teach(root, text, source, *, scope='project', shared=None, binding=None,
          applicability=None, identifier=None, expected_revision=None, recovery_authorized=False,
          summary=None, missing=None, normalization=None, original=None, predecessor=None,
          semantic=False, receipt_stage=None, intent_trigger=None, authorization_intent=None,
          binding_template=None, binding_parameters=None, authorization_revoked=None, authorization_resource=None, receipt_controls=None):
    """Trusted *local user ingress*. Never exposed as a writable MCP tool.

    OS callers are trusted like the existing Knowledge operator CLI. A model
    tool/result cannot manufacture user authority through the read-only MCP.
    """
    clean_text(text)
    normalized_text=clean_text(summary if summary else text)
    if original is not None:clean_text(original)
    if normalization is not None:reject_secrets(canonical_json(normalization))
    require(missing is None or isinstance(missing,list) and len(missing)<=8 and all(isinstance(x,str) and 0<len(x)<=500 for x in missing),'invalid-instruction-missing-details')
    require(isinstance(source,dict) and set(source)=={'type','id'} and source.get('type')=='user-message' and isinstance(source.get('id'),str) and 0<len(source['id'])<=300,'user-source-required')
    reject_secrets(canonical_json(source))
    applicability=deepcopy(applicability or {});validate_applicability(applicability)
    if binding:
        validate_binding(binding['trigger'],binding['behavior']);reject_secrets(canonical_json(binding))
    # Read installation inputs before taking any store write lock.
    from .bindings import snapshot
    execution=snapshot(binding['behavior'],root) if binding else None
    store=OperationalStore(root,scope,shared);store.ensure()
    event_key={'source':source['id'],'scope':scope}
    if receipt_stage:event_key['phase']=receipt_stage
    event_id=digest(event_key)
    request=digest({'text':text,'binding':binding,'applicability':applicability,'identifier':identifier,'recovery_authorized':recovery_authorized})
    with store.connection(True) as db:
        records=current(db)
        event=db.execute('SELECT payload FROM operational_events WHERE id=?',(event_id,)).fetchone()
        if event:
            receipt=loads(event[0]);require(receipt['request']==request,'teaching-source-reused')
            saved=next(r for r in records if r['id']==receipt['result']['id'])
            result=ack(saved,duplicate=True)
        else:
            key=digest({'scope':scope,'trigger':binding['trigger'],'behavior':binding['behavior'],'applicability':applicability,'recovery':recovery_authorized}) if semantic and binding else digest({'scope':scope,'text':normalized(normalized_text),'applicability':applicability})
            old=next((r for r in records if r['id']==(identifier or key)),None)
            if identifier:
                require(old is not None,'unknown-instruction')
                require(old['kind']=='instruction','experience-requires-new-explicit-instruction')
                require(type(expected_revision) is int,'instruction-expected-revision-required')
            if old and expected_revision is not None:require(old['revision']==expected_revision,'instruction-revision-conflict')
            if old and not identifier:
                require(old['status']!='retired','retired-instruction-requires-explicit-update')
                require(old['behavior']==(binding or {}).get('behavior') and old['trigger']==(binding or {}).get('trigger'),'instruction-binding-conflict')
                result=ack(old,duplicate=True)
            else:
                now=time.time()
                value=dict(version=1,id=identifier or key,revision=old['revision']+1 if old else 1,
                    kind='instruction',status='active' if binding else 'unbound',scope=scope,
                    project=Project(root).identity if scope=='project' else None,
                    original=old['original'] if old else original if original is not None else text,
                    source_text=text if old or original is not None else None,normalized=normalized_text,missing=deepcopy(missing or []),
                    provenance=deepcopy(source),authority='user',applicability=applicability,
                    trigger=deepcopy(binding['trigger']) if binding else deepcopy(intent_trigger),
                    behavior=deepcopy(binding['behavior']) if binding else None,
                    recovery_authorized=bool(recovery_authorized),
                    authorization_intent=bool(recovery_authorized if authorization_intent is None else authorization_intent),
                    authorization_revoked=bool(authorization_revoked) if authorization_revoked is not None else bool(old and old.get('authorization_intent',old['recovery_authorized']) and not recovery_authorized),
                    authorization_resource=authorization_resource,
                    binding_template=binding_template,binding_parameters=deepcopy(binding_parameters or {}),
                    execution_binding=execution,
                    technical={'state':'configured' if binding else 'unverified','evidence':[],
                        'normalization':deepcopy(normalization)},
                    created=old['created'] if old else now,updated=now,last_verified=None,
                    supersedes={'id':old['id'],'revision':old['revision']} if old else predecessor,
                    stale=None,evidence=[])
                append(db,value);result=ack(value)
            db.execute('INSERT INTO operational_events VALUES (?,?)',(event_id,canonical_json({'request':request,'result':result,
                'source_hash':digest(text),'controls':deepcopy(receipt_controls or {})})))
    # Acknowledgement is returned ONLY after the context commits and a fresh
    # transaction validates durable bytes. No in-memory cache is authoritative.
    with store.connection() as db: current(db)
    state=store.records().get('bindings',{}).get(result['id'])
    if state and state['state'] in ('blocked','attempted'):
        result.update(executable=False,execution_state=state['state'],binding_reason=state.get('reason'))
    return result


def teach(*args,**kwargs):
    for attempt in range(6):
        try:return _teach(*args,**kwargs)
        except KnowledgeError as error:
            if error.code not in ('store-busy-retry','maintenance-busy','store-publication-conflict') or attempt==5:raise
            time.sleep(.03*(attempt+1))


def ack(r,duplicate=False):
    execution=r.get('execution_binding') or {}
    return {'ok':True,'saved':True,'duplicate':duplicate,'id':r['id'],'revision':r['revision'],
        'scope':r['scope'],'status':r['status'],'behavior':r['normalized'],
        'trigger':r['trigger'],'action':r['behavior'],'recovery_authorized':r['recovery_authorized'],
        'execution_state':execution.get('state','unbound'),'executable':r['status']=='active' and execution.get('state') in ('bound','portable'),
        'binding_reason':execution.get('reason'),
        'message':f"Сохранено ({r['scope']}, {r['status']}): {r['normalized']}",
        'missing':(r.get('missing') or ['action/procedure binding and applicability; no resource guessed']) if r['status']=='unbound' else [],
        'question':None if duplicate or r['status']!='unbound' else (r.get('missing') or ['К какой настроенной операции или процедуре относится правило? Укажите её имя; ресурс и параметры не выбраны.'])[0]}


def retire(root, identifier, *, scope='project', shared=None, expected_revision=None):
    store=OperationalStore(root,scope,shared)
    with store.connection(True) as db:
        old=next((r for r in current(db) if r['id']==identifier),None);require(old,'unknown-instruction')
        if expected_revision is not None:require(old['revision']==expected_revision,'instruction-revision-conflict')
        if old['status']!='retired':
            value=deepcopy(old);value.pop('content_hash');value.update(status='retired',revision=old['revision']+1,updated=time.time(),supersedes={'id':identifier,'revision':old['revision']});append(db,value)
    return {'ok':True,'retired':identifier}


def application(root, scope, shared, identifier, revision, event_id, outcome, evidence):
    """Verification/failure signal without rewriting user intent or claiming cause."""
    store=OperationalStore(root,scope,shared)
    value={'id':identifier,'revision':revision,'application':{'at':time.time(),'outcome':outcome,'evidence':evidence,
        'technical':'preconditions-satisfied' if outcome.get('ok') else 'blocked-or-failed','root_cause':'not-established'}}
    # Evidence here is receipt IDs/hashes, not transcripts, stdout or project text.
    event={'request':digest({'id':identifier,'revision':revision,'event':event_id}), 'result':value}
    with store.connection(True) as db:
        require(any(r['id']==identifier and r['revision']>=revision for r in current(db)),'unknown-instruction')
        db.execute('INSERT OR IGNORE INTO operational_events VALUES (?,?)',(digest({'application':event_id,'id':identifier}),canonical_json(event)))
    return {'ok':True}


def binding_event(root,record,shared,state,reason=None,**observed):
    """Durable installation signal, separate from immutable teaching revisions."""
    require(state in ('observed','attempted','verified','blocked'),'invalid-binding-state')
    store=OperationalStore(root,record['scope'],shared)
    with store.connection(True) as db:
        require(any(r['id']==record['id'] and r['revision']==record['revision'] for r in current(db)),'instruction-revision-conflict')
        previous={}
        for payload, in db.execute('SELECT payload FROM operational_events ORDER BY rowid'):
            result=loads(payload)['result'];value=result.get('binding_state')
            if result.get('id')==record['id'] and result.get('revision')==record['revision'] and value and value.get('sequence',0)>=previous.get('sequence',0):previous=value
        # Windows wall-clock ticks may coincide; time may also move backwards.
        # Order state by a revision-scoped counter allocated inside this write.
        value={**previous,**observed,'sequence':previous.get('sequence',0)+1,'at':time.time(),'state':state,'reason':reason}
        reject_secrets(canonical_json(value))
        event={'request':digest(value),'result':{'id':record['id'],'revision':record['revision'],'binding_state':value}}
        db.execute('INSERT INTO operational_events VALUES (?,?)',(digest(event),canonical_json(event)))
    return value


def rebind(root,identifier,text,source,*,scope='project',shared=None,expected_revision=None,recovery_authorized=False):
    old=next((r for r in OperationalStore(root,scope,shared).records()['records'] if r['id']==identifier),None)
    require(old and old['kind']=='instruction' and old['status']=='active','executable-instruction-required')
    require(type(expected_revision) is int and old['revision']==expected_revision,'instruction-revision-conflict')
    return teach(root,text,source,scope=scope,shared=shared,identifier=identifier,expected_revision=expected_revision,
        binding={'trigger':old['trigger'],'behavior':old['behavior']},applicability=old['applicability'],
        summary=old['normalized'],original=old['original'],recovery_authorized=recovery_authorized,
        binding_template=old.get('binding_template'),binding_parameters=old.get('binding_parameters'),
        authorization_intent=recovery_authorized,authorization_resource=old.get('authorization_resource'))


def matches(trigger, action):
    return all(fnmatch.fnmatchcase(action.get(k,''),v) for k,v in trigger.items())


def applicable(r, environment):
    for k,v in r['applicability'].items():
        if k=='tools':
            if any(environment.get('tools',{}).get(tool)!=version for tool,version in v.items()):return False
        elif environment.get(k)!=v:return False
    return True


def context_view(record):
    """Bounded retrieval references durable source instead of echoing transcripts."""
    value=deepcopy(record)
    original=value.pop('original','');latest=value.pop('source_text',None)
    value['view']='operational-context-v1'
    from hashlib import sha256
    value['source_refs']={'original_sha256':sha256(original.encode('utf-8')).hexdigest(),'original_bytes':len(original.encode('utf-8')),
        'latest_sha256':sha256((latest if latest is not None else original).encode('utf-8')).hexdigest(),'read':'memory-inspect / memory-history'}
    for owner in (value,value.get('technical',{})):
        evidence=owner.get('evidence')
        if isinstance(evidence,list) and len(evidence)>8:
            owner['evidence_total']=len(evidence);owner['evidence_partial']=True;owner['evidence']=evidence[:8]
    return value


def lookup(root, action, environment, *, shared=None, max_items=8, max_bytes=12000, include_candidates=False):
    require(isinstance(action,dict) and set(action)=={'tool','name'} and all(isinstance(v,str) for v in action.values()),'invalid-memory-action')
    require(type(max_items) is int and 1<=max_items<=32 and type(max_bytes) is int and 512<=max_bytes<=64000,'invalid-memory-budget')
    validate_applicability(environment)
    selected=[];decisions=[];states={};signals={};bindings={}
    for scope in SCOPES:
        store=OperationalStore(root,scope,shared)
        result=store.records();states[scope]=result['state']
        signals.update(result.get('signals',{}))
        bindings.update(result.get('bindings',{}))
        for r in result['records']:
            if r['status']=='unbound':
                # Surface missing binding without pretending an absent trigger
                # can authorize execution. Kept bounded like other selections.
                triggered=matches(r['trigger'],action) if r['trigger'] else any(word in normalized(r['normalized']) for word in normalized(action['name']).split() if len(word)>3)
                if applicable(r,environment) and triggered:
                    selected.append(r)
                continue
            if r['status']!='active' and not (include_candidates and r['status']=='candidate'):continue
            if not r['trigger'] or not matches(r['trigger'],action):continue
            fits=applicable(r,environment)
            decisions.append({'id':r['id'],'revision':r['revision'],'applicable':fits,'reason':'match' if fits else 'environment-mismatch'})
            if fits:selected.append(r)
    # Project and stricter applicability specialize broad instructions only for
    # the same trigger/adapter. Incomparable equally narrow contradictions fail.
    groups={}
    for r in selected:
        key=canonical_json({'adapter':(r['behavior'] or {}).get('adapter'),'procedure':(r['behavior'] or {}).get('procedure',{}).get('id')})
        groups.setdefault(key,[]).append(r)
    resolved=[];conflicts=[]
    for group in groups.values():
        def specializes(a,b):
            if a['scope']=='shared' and b['scope']=='project':return False
            aa=a['applicability'];bb=b['applicability']
            at=a['trigger'] or {};bt=b['trigger'] or {}
            trigger_narrow=all(at.get(k)==value or ('*' not in at.get(k,'') and '?' not in at.get(k,'') and fnmatch.fnmatchcase(at.get(k,''),value)) for k,value in bt.items())
            return trigger_narrow and all((all(aa.get(k,{}).get(t)==v for t,v in value.items()) if k=='tools' else aa.get(k)==value) for k,value in bb.items()) and (a['scope']!=b['scope'] or aa!=bb or at!=bt)
        narrow=[r for r in group if not any(specializes(other,r) for other in group if other is not r)]
        if len({canonical_json({'behavior':r['behavior'],'recovery':r.get('recovery_authorized')}) for r in narrow})>1:
            conflicts.append([{'id':r['id'],'revision':r['revision']} for r in narrow])
        resolved.extend(narrow)
    result={'ok':True,'state':'conflict' if conflicts else 'matched' if resolved else 'no-match',
        'stores':states,'records':[context_view(r) for r in resolved],'decisions':decisions,'conflicts':conflicts,'partial':False,
        'signals':{r['id']:signals[r['id']] for r in resolved if r['id'] in signals}}
    result['bindings']={r['id']:bindings[r['id']] for r in resolved if r['id'] in bindings}
    require(len(resolved)<=max_items, 'memory-context-item-limit')
    result['payload_bytes']=0
    for _ in range(3):result['payload_bytes']=len(canonical_json(result).encode())
    require(result['payload_bytes']<=max_bytes,'memory-context-byte-limit')
    return result


def capture_experience(root, event_id, action, environment, diagnostics, interventions, outcome, evidence, *, shared=None):
    """Observation only, project scoped, stable event identity; never mandatory."""
    store=OperationalStore(root,'project',shared);store.ensure()
    identifier=digest({'experience':event_id});now=time.time()
    # Inputs are structured receipt references, never raw command output/source.
    value=dict(version=1,id=identifier,revision=1,kind='experience',status='candidate',scope='project',
        project=Project(root).identity,original='',normalized='Observed recovery; causality not established',
        provenance={'type':'execution-receipts','id':event_id},authority='observation',
        applicability=deepcopy(environment),trigger=deepcopy(action),behavior=None,
        recovery_authorized=False,technical={'state':'unverified','evidence':deepcopy(evidence)},
        created=now,updated=now,last_verified=None,supersedes=None,stale=None,evidence=deepcopy(evidence),
        experience={'operation':action,'diagnostics':diagnostics,'interventions':interventions,
            'outcome':outcome,'uncertainty':'Retry outcome is not proof of root cause; interventions are not independent evidence.'})
    with store.connection(True) as db:
        old=next((r for r in current(db) if r['id']==identifier),None)
        if not old:append(db,value)
    return {'ok':True,'candidate':identifier,'status':'candidate'}


TEACHING = re.compile(r'(?i)^\s*(?:remember\b|please remember\b|from now on\b|always\b|never\b|запомни(?:те)?\b|впредь\b|теперь всегда\b|всегда\b|никогда\b)')
SHARED = re.compile(r'(?i)\b(?:all projects|across projects|shared memory|shared rule|for projects|для всех проектов|для проектов|общее правило|общую память)\b')
ALLOW = re.compile(r'(?i)\b(?:you may start (?:that |the |this |specific |local |configured )*(?:container|service)|(?:разрешаю запуск|можно запускать|можешь запускать) (?:этого |этот |конкретного |конкретный |локального |локальный )*(?:контейнер|сервис))')
RESTRICT = re.compile(r'(?i)(?:do not start services|don.t start services|не запускай сервис|не запускать сервис|запрещаю запуск сервис)')


def supported_binding(policy,binding):
    paths=policy.get('activation_paths')
    return paths is None or binding.get('behavior',{}).get('adapter','dependency' if binding.get('template') else None) in paths.get(binding['trigger']['tool'],[])


def binding_receipt(root,text,message_id,shared=None):
    """Replay a completed trusted source without reclassifying it or revising it."""
    for scope in SCOPES:
        store=OperationalStore(root,scope,shared);state=store.records()
        if state['state']=='absent':continue
        with store.connection() as db:
            if not enabled(db):continue
            key=digest({'source':message_id,'scope':scope,'phase':'binding'})
            row=db.execute('SELECT payload FROM operational_events WHERE id=?',(key,)).fetchone()
            if not row:continue
            event=loads(row[0])
            if 'source_hash' not in event:continue  # Compatible legacy receipt path.
            require(event['source_hash']==digest(text),'teaching-source-reused')
            record=next(r for r in state['records'] if r['id']==event['result']['id'])
            result=ack(record,duplicate=True);binding=state.get('bindings',{}).get(record['id'])
            if binding and binding['state'] in ('blocked','attempted'):
                result.update(executable=False,execution_state=binding['state'],binding_reason=binding.get('reason'))
            return {**result,**event.get('controls',{}),'normalization':{'method':'durable-source-replay'}}


def ingest(root, text, message_id, policy, reply_to=None):
    """Small transparent local normalizer for explicit teaching + named bindings.

    Unknown language/intent remains unbound, never guessed. Configuration aliases
    identify supported actions, not arbitrary natural-language command execution.
    """
    if policy.get('normalizer') is not None and policy.get('teaching_mode')!='catalog':
        from .semantic_ingress import ingest as semantic_ingest
        return semantic_ingest(root,text,message_id,policy,reply_to)
    target=re.search(r'(?i)(?:rule|правило)\s+([0-9a-f]{64})\b',text)
    bindings=[b for b in policy.get('bindings',[]) if any(re.search(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',text,re.I) for alias in b['aliases'])]
    target_id=target.group(1) if target else reply_to if reply_to and bindings and not TEACHING.search(text) else None
    teaching=TEACHING.search(text) or (target and re.search(r'(?i)bind|update|correct|привяжи|уточни|исправь',text)) or (reply_to and target_id)
    if not teaching:return {'ok':True,'saved':False,'restriction':'no-service-start' if RESTRICT.search(text) else None}
    clean_text(text)
    scope='shared' if SHARED.search(text) else 'project'
    old=None
    if target_id:
        found=[r for s in SCOPES for r in OperationalStore(root,s,policy.get('shared_root')).records()['records'] if r['id']==target_id]
        require(len(found)==1,'unknown-or-ambiguous-instruction');old=found[0];scope=old['scope']
    require(len(bindings)<=1,'ambiguous-teaching-binding')
    binding=bindings[0] if bindings else ({'trigger':old['trigger'],'behavior':old['behavior'],'applicability':old['applicability']} if old and old['status']=='active' else None)
    unsupported=binding is not None and not supported_binding(policy,binding)
    return teach(root,text,{'type':'user-message','id':message_id},scope=scope,shared=policy.get('shared_root'),
        binding=None if unsupported else binding,applicability=(binding or {}).get('applicability',{}),
        intent_trigger=binding['trigger'] if unsupported else None,
        missing=['Намерение сохранено; этот trigger/action не поддержан текущим хостом. Какой поддержанный путь должен его активировать?'] if unsupported else None,
        identifier=target_id,expected_revision=old['revision'] if old else None,
        recovery_authorized=False if RESTRICT.search(text) else bool(ALLOW.search(text) or (old and old['recovery_authorized'])))
