"""SQLite is the sole canonical store, queue, plan and import journal.

All participating writers use BEGIN IMMEDIATE (bounded contention). Readers use
one snapshot. SQLite rollback journaling and FULL sync provide atomic commit;
apply and acknowledgment are deliberately separate durable transactions.
"""
from contextlib import contextmanager
from copy import deepcopy
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import unicodedata
from . import legacy_validator as legacy
from . import lifecycle as life
from .project import Project, safe_tree
from .retrieval import ContextEngine
from .util import canonical_json, digest, fingerprint, loads, require, KnowledgeError

GROUPS = {'claims': 'knowledge/claims', 'evidence': 'evidence', 'relationships': 'knowledge/relationships'}
KINDS = {'claims': 'claim', 'evidence': 'evidence', 'relationships': 'relationship'}
SCHEMAS = Path(__file__).parent / 'schemas'


def empty():
    return {g: [] for g in GROUPS}


def checkpoint(phase):
    """Internal fault-injection seam. No user input or environment activation."""


def normalized(statement):
    return ' '.join(unicodedata.normalize('NFKC', statement).casefold().split())


def shape(records):
    require(isinstance(records, dict) and set(records) == set(GROUPS), 'invalid-record-groups')
    ids = set()
    for group, items in records.items():
        require(isinstance(items, list), 'invalid-record-list')
        schema = loads((SCHEMAS / (KINDS[group] + '.schema.json')).read_text())
        for item in items:
            issues = legacy.schema_errors(item, schema)
            require(not issues, 'invalid-record', issues)
            require(item['id'] not in ids, 'duplicate-record-id')
            ids.add(item['id'])


def validate_records(records):
    shape(records)
    with tempfile.TemporaryDirectory(prefix='knowledge-validation-') as tmp:
        base = Path(tmp)
        (base/'schema').mkdir()
        (base/'manifest.yaml').write_text(canonical_json(legacy.MANIFEST))
        for p in SCHEMAS.glob('*.json'):
            shutil.copyfile(p, base/'schema'/p.name)
        for g, path in GROUPS.items():
            (base/path).mkdir(parents=True)
            for index, record in enumerate(records[g]):
                (base/path/f'{index}.json').write_text(canonical_json(record))
        errors, warnings = legacy.validate(base)
        require(not errors, 'invalid-dataset', errors)
        return warnings


def candidate(value):
    if isinstance(value,dict) and value.get('version')==2:
        return life.envelope(value)
    require(isinstance(value, dict) and set(value) == {'version', 'operation', 'records'}, 'invalid-candidate-envelope')
    require(type(value['version']) is int and value['version'] == 1, 'unsupported-candidate-version')
    require(value['operation'] == 'add', 'unsupported-operation')
    shape(value['records'])
    require(bool(value['records']['claims']), 'candidate-requires-claims')
    for claim in value['records']['claims']:
        require(bool(claim['evidence']), 'candidate-requires-evidence')
    return deepcopy(value)


def create_tables(db, identity):
    db.executescript("""
        BEGIN IMMEDIATE;
        CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE records(id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE queue(id TEXT PRIMARY KEY, payload TEXT NOT NULL, status TEXT NOT NULL, binding TEXT);
        CREATE TABLE plans(id TEXT PRIMARY KEY, payload TEXT NOT NULL, status TEXT NOT NULL);
        CREATE TABLE history(sequence INTEGER PRIMARY KEY, payload TEXT NOT NULL);
    """)
    db.executemany('INSERT INTO metadata VALUES (?,?)', [('format','knowledge-sqlite-v1'),('project',identity)])


def publish_directory(staged, project):
    """Atomically publish a fully committed store, never replace nonempty data.

    Renaming the directory avoids a crash window with duplicate hardlinks.
    Target must be absent or an empty directory on POSIX. Windows requires an
    absent destination; native behavior is explicitly not certified by P0.
    """
    safe_tree(project.base)
    require(not project.base.exists() or (project.base.is_dir() and not any(project.base.iterdir())),
            'store-publication-target-not-empty')
    require(os.name=='posix' or not project.base.exists(), 'publication-requires-absent-target')
    try:
        os.rename(staged,project.base)
    except OSError as e:
        raise KnowledgeError('store-publication-conflict') from e
    if os.name=='posix':
        fd=os.open(project.root,os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


class Store:
    def __init__(self, root):
        self.project = Project(root)
        self.base, self.path = self.project.base, self.project.db

    @contextmanager
    def connection(self, write=False):
        safe_tree(self.base)
        require(self.path.is_file(), 'knowledge-absent')
        db = None
        try:
            db = sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True, timeout=0.15)
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA synchronous=FULL')
            db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            require(db.execute('PRAGMA quick_check').fetchone() == ('ok',), 'corrupt-database')
            metadata = dict(db.execute('SELECT key,value FROM metadata'))
            require(metadata.get('format') == 'knowledge-sqlite-v1', 'unsupported-store-format')
            require(metadata.get('project') == self.project.identity, 'project-identity-mismatch')
            legacy_base = self.project.root/'.ai'
            if legacy_base.exists() and any(legacy_base.iterdir()):
                require('migration' in metadata, 'ambiguous-dual-stores')
            extension=metadata.get('p1')
            require(extension in (None,'1'),'unsupported-extension-version')
            self._check_control(db)
            yield db
            if write:
                checkpoint('before-commit')
            db.commit()
        except sqlite3.OperationalError as e:
            if 'locked' in str(e):
                raise KnowledgeError('store-busy-retry') from e
            raise KnowledgeError('database-unavailable-or-corrupt') from e
        except sqlite3.DatabaseError as e:
            raise KnowledgeError('corrupt-database') from e
        finally:
            if db is not None:
                db.close()

    def _check_control(self, db):
        legacy_ids = {}
        row = db.execute("SELECT value FROM metadata WHERE key='migration'").fetchone()
        if row:
            manifest=loads(row[0])
            require(isinstance(manifest,dict) and isinstance(manifest.get('legacy_queue'),list), 'corrupt-migration-manifest')
            for item in manifest['legacy_queue']:
                require(isinstance(item,dict) and isinstance(item.get('id'),str) and 'payload' in item, 'corrupt-migration-manifest')
                legacy_ids[item['id']]=digest(candidate(item['payload']))

        def valid_identity(cid, item):
            hashed=digest(candidate(item))
            return cid==hashed or legacy_ids.get(cid)==hashed

        plans = {}
        for pid, payload, state in db.execute('SELECT id,payload,status FROM plans'):
            plan = loads(payload)
            require(isinstance(plan,dict) and set(plan)=={'version','project','base','candidates','included','skipped','blocked'}, 'corrupt-plan')
            require(fingerprint(plan)==pid and state in ('PREPARED','COMMITTED','ACKNOWLEDGED') and
                    plan['version']==1 and plan['project']==self.project.identity and
                    isinstance(plan['base'],str) and isinstance(plan['candidates'],dict) and
                    all(isinstance(plan[k],list) for k in ('included','skipped','blocked')), 'corrupt-plan')
            for cid,item in plan['candidates'].items():
                require(valid_identity(cid,item),'corrupt-plan-candidate')
            require(plan['included']==(list(plan['candidates']) if not plan['blocked'] else []), 'corrupt-plan-inclusion')
            plans[pid]=(plan,state)
        for cid, payload, status, binding in db.execute('SELECT id,payload,status,binding FROM queue'):
            item = candidate(loads(payload))
            require(valid_identity(cid,item) and status in ('pending','imported','rejected','deferred'), 'corrupt-queue')
            require((status in ('pending','rejected','deferred') and binding is None) or
                    (status == 'imported' and binding is not None), 'corrupt-queue-binding')
            if binding:
                bound=plans.get(binding)
                require(bound is not None and bound[1] in ('COMMITTED','ACKNOWLEDGED') and
                        cid in bound[0]['included'] and bound[0]['candidates'][cid]==item, 'corrupt-queue-binding')
        for payload, in db.execute('SELECT payload FROM history'):
            require(isinstance(loads(payload),dict),'corrupt-history')

        if life.enabled(db):
            states=life.latest(db)
            rows=list(db.execute('SELECT id,kind,payload FROM records'))
            require(set(states)=={r[0] for r in rows},'revision-identity-mismatch')
            for identifier,kind,payload in rows:
                require(states[identifier]['record']==loads(payload) and states[identifier]['kind']==kind,'canonical-revision-mismatch')
            for pid,payload in db.execute('SELECT plan,payload FROM receipts'):
                require(pid in plans and plans[pid][1]!='PREPARED' and loads(payload)==plans[pid][0],'receipt-plan-mismatch')
                self._verify_committed(db,pid,plans[pid][0])

    def init(self):
        require(not (self.project.root/'.ai').exists(), 'legacy-store-present-use-migration')
        if self.path.exists():
            return self.validate()
        safe_tree(self.base)
        with tempfile.TemporaryDirectory(prefix='knowledge-init-',dir=self.project.root) as tmp:
            staged = Path(tmp)/'store.sqlite3'
            db = sqlite3.connect(staged)
            try:
                db.execute('PRAGMA synchronous=FULL')
                create_tables(db, self.project.identity)
                db.commit()
            finally:
                db.close()
            checkpoint('init-before-publish')
            publish_directory(Path(tmp),self.project)
            checkpoint('init-after-publish')
        return self.validate()

    def _records(self, db):
        records = empty()
        for identifier, kind, payload in db.execute('SELECT id,kind,payload FROM records ORDER BY id'):
            require(kind in GROUPS, 'corrupt-record-kind')
            item = loads(payload)
            require(isinstance(item, dict) and item.get('id') == identifier, 'corrupt-record-identity')
            records[kind].append(item)
        if life.enabled(db):life.validate_model(records,life.latest(db))
        else:validate_records(records)
        return records

    def validate(self):
        with self.connection() as db:
            records = self._records(db)
            return {'ok': True, 'counts': {g:len(v) for g,v in records.items()},
                    'warning': 'Structural validation does not prove truth, authority or freshness.'}

    def submit(self, value):
        item = candidate(value)
        cid = digest(item)
        with self.connection(True) as db:
            current = self._records(db)
            if item['version']==2:require(life.enabled(db),'upgrade-required')
            row = db.execute('SELECT id,status,payload FROM queue WHERE id=? OR payload=?',(cid,canonical_json(item))).fetchone()
            if row:
                require(loads(row[2])==item,'candidate-identity-conflict')
                return {'ok':True,'candidate':row[0],'result':'duplicate','status':row[1]}
            if item['version']==2:
                db.execute('INSERT INTO queue VALUES (?,?,?,NULL)', (cid,canonical_json(item),'pending'))
                return {'ok':True,'candidate':cid,'result':'submitted','status':'pending'}
            known_ids = {r['id'] for v in current.values() for r in v}
            statements = {normalized(c['statement']) for c in current['claims']}
            for payload, in db.execute('SELECT payload FROM queue'):
                queued_item=loads(payload)
                if queued_item['version']!=1:continue
                queued = queued_item['records']
                known_ids.update(r['id'] for v in queued.values() for r in v)
                statements.update(normalized(c['statement']) for c in queued['claims'])
            proposed_ids = {r['id'] for v in item['records'].values() for r in v}
            proposed_statements = [normalized(c['statement']) for c in item['records']['claims']]
            require(len(set(proposed_statements)) == len(proposed_statements), 'duplicate-statements-in-candidate')
            if all(s in statements for s in proposed_statements):
                return {'ok':True, 'result':'duplicate-statement', 'candidate':None}
            require(not proposed_ids & known_ids, 'record-id-conflict')
            require(not any(s in statements for s in proposed_statements), 'partial-duplicate-candidate')
            # Full graph checks occur at prepare so a coordinated batch can reference another candidate.
            db.execute('INSERT INTO queue VALUES (?,?,?,NULL)', (cid,canonical_json(item),'pending'))
            checkpoint('queue-written')
        return {'ok':True,'candidate':cid,'result':'submitted','status':'pending'}

    def _preview(self, db):
        current = self._records(db)
        pending = {cid:loads(p) for cid,p in db.execute("SELECT id,payload FROM queue WHERE status='pending' ORDER BY id")}
        if life.enabled(db):
            blocked=[]
            if db.execute("SELECT 1 FROM plans WHERE status='COMMITTED' LIMIT 1").fetchone():
                blocked=[{'code':'pending-acknowledgment-recover-first','details':None}]
            try:
                if not blocked:life.simulate(self,db,pending)
            except KnowledgeError as e:blocked=[{'code':e.code,'details':e.details}]
            return {'version':1,'project':self.project.identity,'base':life.state_fingerprint(self,db),
                    'candidates':pending,'included':list(pending) if not blocked else [],'skipped':[], 'blocked':blocked}
        combined = deepcopy(current)
        for item in pending.values():
            for g in GROUPS:
                combined[g].extend(item['records'][g])
        blocked = []
        try:
            validate_records(combined)
            statements = [normalized(c['statement']) for c in combined['claims']]
            require(len(statements) == len(set(statements)), 'duplicate-statement')
        except KnowledgeError as e:
            blocked = [{'code':e.code,'details':e.details}]
        return {'version':1,'project':self.project.identity,'base':fingerprint(current),
                'candidates':pending,'included':list(pending) if not blocked else [],
                'skipped':[], 'blocked':blocked}

    def prepare(self):
        with self.connection(True) as db:
            preview = self._preview(db)
            pid = fingerprint(preview)
            db.execute('INSERT OR IGNORE INTO plans VALUES (?,?,?)',(pid,canonical_json(preview),'PREPARED'))
        return {'ok':not preview['blocked'],'fingerprint':pid,**preview}

    def _plan(self, db, pid):
        require(isinstance(pid,str) and re.fullmatch(r'sha256:[a-f0-9]{64}',pid), 'invalid-fingerprint')
        row = db.execute('SELECT payload,status FROM plans WHERE id=?',(pid,)).fetchone()
        require(row is not None, 'unknown-plan')
        value = loads(row[0])
        require(fingerprint(value) == pid, 'corrupt-plan')
        return value,row[1]

    def apply(self, pid, approval):
        require(approval == pid, 'exact-approval-required')
        with self.connection(True) as db:
            plan,state = self._plan(db,pid)
            if state != 'PREPARED':
                self._verify_committed(db,pid,plan)
                return {'ok':True,'state':state,'fingerprint':pid,'result':'already-committed'}
            require(not plan['blocked'], 'blocked-plan')
            preview=self._preview(db)
            if life.enabled(db) and all(v['version']==1 for v in plan['candidates'].values()) and plan['base']==fingerprint(self._records(db)):
                # A P0 prepared approval survives a metadata-only upgrade, never a source/canonical edit.
                preview=dict(preview,base=plan['base'])
            require(preview == plan, 'stale-plan-prepare-again')
            for cid in plan['included']:
                value=plan['candidates'][cid]
                if value['version']==2:
                    life.apply_item(self,db,value,pid)
                    continue
                for group,items in plan['candidates'][cid]['records'].items():
                    for record in items:
                        db.execute('INSERT INTO records VALUES (?,?,?)',(record['id'],group,canonical_json(record)))
                        if life.enabled(db):life.append(db,record['id'],group,record,'active',pid,'P0 compatible add',None)
                        checkpoint('canonical-record-written')
            self._records(db)
            if life.enabled(db):
                life.verify_source_bindings(self,plan['candidates'].values())
                db.execute('INSERT INTO receipts VALUES (?,?)',(pid,canonical_json(plan)))
            db.execute("UPDATE plans SET status='COMMITTED' WHERE id=?",(pid,))
            db.execute('INSERT INTO history(payload) VALUES (?)',(canonical_json({'event':'import','fingerprint':pid,'candidates':plan['included']}),))
        checkpoint('after-canonical-commit')
        return {'ok':True,'state':'COMMITTED','fingerprint':pid,'acknowledgment_required':True}

    def _verify_committed(self, db, pid, plan):
        if life.enabled(db):
            receipt=db.execute('SELECT payload FROM receipts WHERE plan=?',(pid,)).fetchone()
            require(receipt is not None and loads(receipt[0])==plan,'committed-receipt-mismatch')
        for cid in plan['included']:
            expected = plan['candidates'][cid]
            row = db.execute('SELECT payload,status,binding FROM queue WHERE id=?',(cid,)).fetchone()
            require(row is not None and loads(row[0]) == expected and
                    (row[1:] == ('pending',None) or row[1:] == ('imported',pid)), 'acknowledgment-ownership-mismatch')
            if life.enabled(db):
                if expected['version']==1:
                    targets=[(g,r) for g,rs in expected['records'].items() for r in rs]
                else:
                    targets=[(o['kind'],o['payload']) for o in expected['operations'] if o['payload'] is not None]
                if expected['version']==2:
                    for op in expected['operations']:
                        owned=db.execute('SELECT payload FROM revisions WHERE id=? AND revision=?',(op['id'],op['expected']+1)).fetchone()
                        require(owned is not None,'missing-committed-revision')
                        owned=loads(owned[0])
                        require(owned['plan']==pid and owned['lifecycle']=={'retire':'retired','supersede':'superseded'}.get(op['action'],'active') and owned['successor']==op['successor'],'historical-revision-ownership-mismatch')
                for kind,record in targets:
                    versions=[loads(p) for p, in db.execute('SELECT payload FROM revisions WHERE id=?',(record['id'],))]
                    require(any(v['record']==record and v['kind']==kind for v in versions),'historical-receipt-payload-mismatch')
                continue
            for g, items in expected['records'].items():
                for record in items:
                    stored = db.execute('SELECT kind,payload FROM records WHERE id=?',(record['id'],)).fetchone()
                    require(stored is not None and stored[0] == g and loads(stored[1]) == record,
                            'committed-payload-changed-recovery-required')

    def acknowledge(self, pid):
        with self.connection(True) as db:
            plan,state = self._plan(db,pid)
            require(state in ('COMMITTED','ACKNOWLEDGED'), 'plan-not-committed')
            self._verify_committed(db,pid,plan)
            for cid in plan['included']:
                db.execute("UPDATE queue SET status='imported',binding=? WHERE id=?",(pid,cid))
            db.execute("UPDATE plans SET status='ACKNOWLEDGED' WHERE id=?",(pid,))
            checkpoint('acknowledgment-written')
        return {'ok':True,'state':'ACKNOWLEDGED','fingerprint':pid}

    def recover(self):
        with self.connection() as db:
            self._records(db)
            pending = [r[0] for r in db.execute("SELECT id FROM plans WHERE status='COMMITTED' ORDER BY id")]
        # Each acknowledgment revalidates ownership under the write lock.
        return {'ok':True,'recovered':[self.acknowledge(pid) for pid in pending],
                'note':'Uncommitted SQLite mutations roll back on reopen; prepared plans remain unapplied.'}

    def status(self):
        with self.connection() as db:
            self._records(db)
            return {'ok':True,'project':self.project.describe(),
                    'queue':[{'id':i,'status':s,'binding':b} for i,s,b in db.execute('SELECT id,status,binding FROM queue ORDER BY id')],
                    'plans':[{'fingerprint':i,'state':s} for i,s in db.execute('SELECT id,status FROM plans ORDER BY id')],
                    'history':[loads(p) for p, in db.execute('SELECT payload FROM history ORDER BY sequence')],
                    'p1':life.enabled(db),
                    'revisions':life.latest(db) if life.enabled(db) else {},
                    'reviews':[loads(p) for p, in db.execute('SELECT payload FROM reviews ORDER BY sequence')] if life.enabled(db) else []}

    def _export_extension(self,db):
        if not life.enabled(db):return {}
        return {'view':'all-latest-with-lifecycle; use context for trusted current',
                'revisions':[loads(p) for p, in db.execute('SELECT payload FROM revisions ORDER BY id,revision')],
                'reviews':[loads(p) for p, in db.execute('SELECT payload FROM reviews ORDER BY sequence')],
                'receipts':[{'fingerprint':i,'plan':loads(p)} for i,p in db.execute('SELECT plan,payload FROM receipts ORDER BY plan')]}

    def export(self):
        with self.connection() as db:
            return {'ok':True,'records':self._records(db),
                    'queue':[{'id':i,'payload':loads(p),'status':s,'binding':b} for i,p,s,b in db.execute('SELECT * FROM queue ORDER BY id')],
                    'history':[loads(p) for p, in db.execute('SELECT payload FROM history ORDER BY sequence')],**self._export_extension(db)}

    def lookup(self, kind, identifier):
        require(kind in GROUPS, 'unsupported-record-kind')
        with self.connection() as db:
            records = self._records(db)
            item = next((r for r in records[kind] if r['id']==identifier),None)
            if life.enabled(db):
                from .discovery import freshness
                state=life.latest(db).get(identifier)
                return {'ok':True,'result':'found' if item else 'no-match','record':item,'revision':state,
                        'freshness':freshness(self.project.root,item,records) if item and kind=='claims' else None}
        return {'ok':True,'result':'found' if item else 'no-match','record':item}

    def context(self, task, max_bytes=16000, max_items=10, include_unconfirmed=False):
        require(isinstance(task,str) and bool(task.strip()) and len(task)<=10000, 'invalid-query')
        require(type(max_bytes) is int and 256 <= max_bytes <= 1000000, 'invalid-byte-budget')
        require(type(max_items) is int and 1<=max_items<=100, 'invalid-item-limit')
        require(type(include_unconfirmed) is bool, 'invalid-status-policy')
        with self.connection() as db:
            records = life.active(self,db,self._records(db))
        result = ContextEngine().assemble(records,task,max_tokens=max_bytes//4,
                                           max_items=max_items,include_unconfirmed=include_unconfirmed,compact=True)
        # Enforce actual serialized UTF-8 bytes, including the final diagnostics.
        # Refresh counts after trimming; never report a removed claim as returned.
        while True:
            for _ in range(3):
                result['budget']['estimated_tokens']=max(1,len(canonical_json(result).encode())//4)
            if len(canonical_json(result).encode())<=max_bytes:
                return result
            if not result['claims']:
                return {'ok':True,'result':'budget-too-small','claims':[],'evidence':[],'conflicts':[]}
            result['claims'].pop()
            ids = {e for c in result['claims'] for e in c['evidence_ids']}
            result['evidence'] = [e for e in result['evidence'] if e['id'] in ids]
            selected = {c['id'] for c in result['claims']}
            result['conflicts'] = [c for c in result['conflicts'] if c['claim_id'] in selected]
            result['truncation'].update(returned=len(result['claims']),
                dropped=result['truncation']['candidates']-len(result['claims']),reason='byte-budget')
            if not result['claims']:
                result['result']='budget-exhausted'



# Public manual/automatic-compatible facades have exactly one mutation implementation.
def submit_manual(root, payload):
    return Store(root).submit(payload)


def submit_automatic(root, payload):
    return Store(root).submit(payload)
