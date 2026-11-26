"""SQLite is the sole canonical store, queue, plan and import journal.

All participating writers use BEGIN IMMEDIATE (bounded contention). Readers use
one snapshot. SQLite rollback journaling and FULL sync provide atomic commit;
apply and acknowledgment are deliberately separate durable transactions.
"""
from contextlib import contextmanager
from contextvars import ContextVar
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
from .sqlite_snapshot import Connection, view

GROUPS = {'claims': 'knowledge/claims', 'evidence': 'evidence', 'relationships': 'knowledge/relationships'}
GIT_BATCH_LIMIT = 100
KINDS = {'claims': 'claim', 'evidence': 'evidence', 'relationships': 'relationship'}
SCHEMAS = Path(__file__).parent / 'schemas'
_schema_snapshot=ContextVar('knowledge-validation-schema-snapshot',default=None)


@contextmanager
def validation_schemas():
    """Trusted package schemas read once per transaction, never across commits."""
    token=_schema_snapshot.set({})
    try:yield
    finally:_schema_snapshot.reset(token)


def empty():
    return {g: [] for g in GROUPS}


def checkpoint(phase):
    """Internal fault-injection seam. No user input or environment activation."""


def normalized(statement):
    """Historical operational-memory identity; intentionally unchanged."""
    return ' '.join(unicodedata.normalize('NFKC', statement).casefold().split())


def statement_key(statement):
    # exact-utf8-v1: quoted values, code identifiers and whitespace carry meaning.
    return statement


def shape(records):
    require(isinstance(records, dict) and set(records) == set(GROUPS), 'invalid-record-groups')
    ids = set()
    for group, items in records.items():
        require(isinstance(items, list), 'invalid-record-list')
        if not items:continue
        path=SCHEMAS / (KINDS[group] + '.schema.json');cache=_schema_snapshot.get()
        if cache is None:schema=loads(path.read_text(encoding='utf-8'))
        else:
            if path not in cache:cache[path]=loads(path.read_text(encoding='utf-8'))
            schema=cache[path]
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
        (base/'manifest.yaml').write_text(canonical_json(legacy.MANIFEST),encoding='utf-8')
        for p in SCHEMAS.glob('*.json'):
            shutil.copyfile(p, base/'schema'/p.name)
        for g, path in GROUPS.items():
            (base/path).mkdir(parents=True)
            for index, record in enumerate(records[g]):
                (base/path/f'{index}.json').write_text(canonical_json(record),encoding='utf-8')
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
    from .confluence import is_binding
    require(not any(is_binding(e.get('source')) for e in value['records']['evidence']),'confluence-requires-v2-source-binding')
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
    def connection(self,write=False):
        from .coordination import gate
        with gate(self.project.root):
            with self._connection(write) as db:yield db

    def progress_connection(self):
        """Read-only source telemetry, never candidate or canonical validation.

        Keep path, project identity and maintenance boundaries. The authorizer
        prevents accidental expansion into the canonical graph/queue hot path.
        All authoritative operations continue through connection().
        """
        return self._telemetry_connection({'confluence_command_state','confluence_work','confluence_seen','confluence_pages'})

    def scan_counts(self):
        tables = ('records', 'queue', 'plans')
        with self._telemetry_connection(set(tables)) as db:
            return {table: db.execute('SELECT count(*) FROM ' + table).fetchone()[0] for table in tables}

    @contextmanager
    def _telemetry_connection(self, tables):
        from .coordination import gate
        with gate(self.project.root):
            safe_tree(self.base);require(self.path.is_file(),'knowledge-absent');db=None
            try:
                db=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True,timeout=0.15)
                allowed=tables | {'metadata','sqlite_master'}
                def authorize(action,table,column,database,trigger):
                    if action==sqlite3.SQLITE_READ:return sqlite3.SQLITE_OK if table in allowed else sqlite3.SQLITE_DENY
                    return sqlite3.SQLITE_OK if action in (sqlite3.SQLITE_SELECT,sqlite3.SQLITE_FUNCTION,sqlite3.SQLITE_TRANSACTION) else sqlite3.SQLITE_DENY
                db.set_authorizer(authorize);db.execute('BEGIN')
                metadata=dict(db.execute("SELECT key,value FROM metadata WHERE key IN ('format','project','p1','migration')"))
                require(metadata.get('format')=='knowledge-sqlite-v1','unsupported-store-format')
                require(metadata.get('project')==self.project.identity,'project-identity-mismatch',
                        {'database':str(self.path),'expected_identity':self.project.identity,
                         'stored_identity':metadata.get('project'),
                         'next_action':'Use knowledge.maintain_cli identity-inventory and an explicitly approved identity-preview/apply. Restart, MCP registration and fresh scan cannot repair database identity. Existing data may already be present.'})
                require(metadata.get('p1') in (None,'1'),'unsupported-extension-version')
                legacy=self.project.root/'.ai'
                require(not legacy.exists() or not any(legacy.iterdir()) or 'migration' in metadata,'ambiguous-dual-stores')
                yield db
                db.commit()
            except sqlite3.OperationalError as error:
                raise KnowledgeError('store-busy-retry' if 'locked' in str(error) else 'database-unavailable-or-corrupt') from error
            except sqlite3.DatabaseError as error:
                raise KnowledgeError('corrupt-database') from error
            finally:
                if db is not None:db.close()

    @contextmanager
    def discovery_checkpoint_connection(self):
        """Provisional checkpoint writes have no authority over canonical tables."""
        from .coordination import gate
        from . import discovery_checkpoint
        with gate(self.project.root):
            safe_tree(self.base)
            db = None
            try:
                db = sqlite3.connect(self.path.as_uri()+'?mode=rw', uri=True, timeout=0.15)
                db.execute('PRAGMA foreign_keys=ON')
                db.execute('PRAGMA synchronous=FULL')
                db.execute('BEGIN IMMEDIATE')
                metadata = dict(db.execute("SELECT key,value FROM metadata WHERE key IN ('format','project','p1','migration')"))
                require(metadata.get('format') == 'knowledge-sqlite-v1', 'unsupported-store-format')
                require(metadata.get('project') == self.project.identity, 'project-identity-mismatch')
                require(metadata.get('p1') == '1', 'upgrade-required')
                legacy = self.project.root/'.ai'
                require(not legacy.exists() or not any(legacy.iterdir()) or 'migration' in metadata, 'ambiguous-dual-stores')

                if not discovery_checkpoint.exists(db):
                    discovery_checkpoint.create(db)

                def authorize(action, table, column, database, trigger):
                    if action == sqlite3.SQLITE_READ and table in ('sqlite_master', 'scans') and not trigger:
                        return sqlite3.SQLITE_OK
                    if action in (sqlite3.SQLITE_READ, sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE):
                        return sqlite3.SQLITE_OK if table in ('discovery_runs', 'discovery_chunks') and not trigger else sqlite3.SQLITE_DENY
                    return sqlite3.SQLITE_OK if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_TRANSACTION) else sqlite3.SQLITE_DENY

                db.set_authorizer(authorize)
                yield db
                checkpoint('before-commit')
                db.commit()
            except sqlite3.OperationalError as error:
                raise KnowledgeError('store-busy-retry' if 'locked' in str(error) else 'database-unavailable-or-corrupt') from error
            except sqlite3.DatabaseError as error:
                raise KnowledgeError('corrupt-database') from error
            finally:
                if db is not None:
                    db.close()

    @contextmanager
    def discovery_completion_connection(self):
        """Validate and compute against one SQLite snapshot, then promote to write.

        A concurrent write prevents promotion and the caller can retry from the
        durable checkpoint. The read phase holds no reserved writer lock.
        """
        from .coordination import gate
        with gate(self.project.root):
            with self._connection(write=True, deferred=True) as db:
                yield db

    @contextmanager
    def _connection(self, write=False, deferred=False):
        safe_tree(self.base)
        require(self.path.is_file(), 'knowledge-absent')
        db = None
        try:
            db = sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True, timeout=0.15, factory=Connection)
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA synchronous=FULL')
            db.execute('BEGIN IMMEDIATE' if write and not deferred else 'BEGIN')
            require(db.execute('PRAGMA quick_check').fetchone() == ('ok',), 'corrupt-database')
            metadata = dict(db.execute('SELECT key,value FROM metadata'))
            require(metadata.get('format') == 'knowledge-sqlite-v1', 'unsupported-store-format')
            require(metadata.get('project') == self.project.identity, 'project-identity-mismatch',
                    {'database':str(self.path),'expected_identity':self.project.identity,
                     'stored_identity':metadata.get('project'),
                     'next_action':'Use knowledge.maintain_cli identity-inventory and an explicitly approved identity-preview/apply. Restart, MCP registration and fresh scan cannot repair database identity. Existing data may already be present.'})
            legacy_base = self.project.root/'.ai'
            if legacy_base.exists() and any(legacy_base.iterdir()):
                require('migration' in metadata, 'ambiguous-dual-stores')
            extension=metadata.get('p1')
            require(extension in (None,'1'),'unsupported-extension-version')
            with validation_schemas():
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
        from .confluence import validate_control,validate_candidate
        validate_control(db)
        from .identity_migration import validate_archive
        validate_archive(db)
        from .cr_workflow import validate_workflows
        validate_workflows(db,self.project.identity)
        from .operations import validated_view
        validated_view(db)
        from .transfers import PREFIX,validate as validate_transfer
        for key,payload in db.execute('SELECT key,value FROM metadata WHERE key LIKE ?', (PREFIX+'%',)):
            validate_transfer(loads(payload),key)
        legacy_ids = {}
        row = db.execute("SELECT value FROM metadata WHERE key='migration'").fetchone()
        if row:
            manifest=loads(row[0])
            require(isinstance(manifest,dict) and isinstance(manifest.get('legacy_queue'),list), 'corrupt-migration-manifest')
            for item in manifest['legacy_queue']:
                require(isinstance(item,dict) and isinstance(item.get('id'),str) and 'payload' in item, 'corrupt-migration-manifest')
                legacy_ids[item['id']]=digest(candidate(item['payload']))

        def valid_identity(cid, item, validated=False):
            hashed=digest(item if validated else candidate(item))
            return cid==hashed or legacy_ids.get(cid)==hashed

        plans = {}
        for pid, payload, state in db.execute('SELECT id,payload,status FROM plans'):
            plan = loads(payload)
            fields={'version','project','base','candidates','included','skipped','blocked'}
            require(isinstance(plan,dict) and set(plan)==(fields|{'resolved','deduplication'} if plan.get('version')==2 else fields), 'corrupt-plan')
            require(fingerprint(plan)==pid and state in ('PREPARED','COMMITTED','ACKNOWLEDGED') and
                    plan['version'] in (1,2) and plan['project']==self.project.identity and
                    isinstance(plan['base'],str) and isinstance(plan['candidates'],dict) and
                    all(isinstance(plan[k],list) for k in ('included','skipped','blocked')), 'corrupt-plan')
            for cid,item in plan['candidates'].items():
                require(valid_identity(cid,item),'corrupt-plan-candidate')
                validate_candidate(db,item,fresh=False)
            if plan['version']==2:
                require(set(plan['resolved'])==set(plan['candidates']),'corrupt-resolved-candidates')
                for value in plan['resolved'].values():
                    if value is not None:candidate(value)
            require(plan['included']==(list(plan['candidates']) if not plan['blocked'] else []), 'corrupt-plan-inclusion')
            plans[pid]=(plan,state)
        queue=[]
        for cid, payload, status, binding in db.execute('SELECT id,payload,status,binding FROM queue'):
            item = candidate(loads(payload))
            validate_candidate(db,item,fresh=False)
            require(valid_identity(cid,item,validated=True) and status in ('pending','imported','rejected','deferred'), 'corrupt-queue')
            require((status in ('pending','rejected','deferred') and binding is None) or
                    (status == 'imported' and binding is not None), 'corrupt-queue-binding')
            if binding:
                bound=plans.get(binding)
                require(bound is not None and bound[1] in ('COMMITTED','ACKNOWLEDGED') and
                        cid in bound[0]['included'] and bound[0]['candidates'][cid]==item, 'corrupt-queue-binding')
            queue.append((cid,status,payload,item))
        for payload, in db.execute('SELECT payload FROM history'):
            require(isinstance(loads(payload),dict),'corrupt-history')

        if life.enabled(db):
            from .discovery import validate_capture_receipts,candidate_refreshes
            validate_capture_receipts(db);candidate_refreshes(db)
            from .providers import semantic_bindings
            semantic_bindings(db)
            states=life.latest(db)
            rows=list(db.execute('SELECT id,kind,payload FROM records'))
            require(set(states)=={r[0] for r in rows},'revision-identity-mismatch')
            for identifier,kind,payload in rows:
                require(states[identifier]['record']==loads(payload) and states[identifier]['kind']==kind,'canonical-revision-mismatch')
            for pid,payload in db.execute('SELECT plan,payload FROM receipts'):
                require(pid in plans and plans[pid][1]!='PREPARED' and loads(payload)==plans[pid][0],'receipt-plan-mismatch')
                self._verify_committed(db,pid,plans[pid][0])
        view(db,'validated-queue',lambda:queue)
        from .confluence_sync import validate_relations
        validate_relations(db,queue)
        return queue

    def init(self):
        from .coordination import gate
        with gate(self.project.root):return self._init()

    def _init(self):
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
        from .confluence import is_binding,verify_evidence
        for evidence in records['evidence']:
            if is_binding(evidence['source']):verify_evidence(db,evidence,fresh=False)
        return records

    def validate(self):
        with self.connection() as db:
            records = self._records(db)
            from .confluence import integrity
            integrity(db)
            return {'ok': True, 'counts': {g:len(v) for g,v in records.items()},
                    'warning': 'Structural validation does not prove truth, authority or freshness.'}

    def _queue_rows(self, db):
        return view(db,'validated-queue',lambda:self._check_control(db))

    def submit(self, value, semantic_binding=None):
        item = candidate(value)
        if semantic_binding is not None:
            from .providers import validate_semantic_binding
            validate_semantic_binding(semantic_binding);require(item['version']==2,'semantic-binding-requires-v2')
        cid = digest(item)
        with self.connection(True) as db:
            current = self._records(db)
            if item['version']==2:require(life.enabled(db),'upgrade-required')
            from .confluence import is_binding,validate_candidate
            if is_binding(item.get('source')):validate_candidate(db,item)
            # _check_control has checked every row in this same snapshot. Keep
            # the old table traversal order and exact raw TEXT equality, including
            # predecessor IDs/noncanonical JSON; a digest never replaces equality.
            queued=self._queue_rows(db)
            serialized=canonical_json(item)
            row=next((r for r in queued if r[0]==cid or r[2]==serialized),None)
            if row:
                require(row[3]==item,'candidate-identity-conflict')
                if semantic_binding is not None:
                    from .providers import semantic_bindings
                    require(semantic_bindings(db).get(row[0])==semantic_binding,'candidate-semantic-binding-conflict')
                return {'ok':True,'candidate':row[0],'result':'duplicate','status':row[1]}
            if item['version']==2:
                db.execute('INSERT INTO queue VALUES (?,?,?,NULL)', (cid,canonical_json(item),'pending'))
                from .confluence_sync import note_candidate
                note_candidate(db,cid,item)
                if semantic_binding is not None:
                    from .providers import SEMANTIC_PREFIX
                    db.execute('INSERT INTO metadata VALUES (?,?)',(SEMANTIC_PREFIX+cid,canonical_json(semantic_binding)))
                    checkpoint('semantic-candidate-written')
                if item['source'] is not None and not is_binding(item['source']):
                    from .discovery import inventory,proposal_identity,refresh_pending
                    signature=proposal_identity(item)
                    if any(status=='pending' and prior['version']==2 and prior['source'] is not None
                           and prior['source']['identity']!=item['source']['identity'] and proposal_identity(prior)==signature
                           for _,status,_,prior in queued):
                        if inventory(self.project.root)['identity']==item['source']['identity']:
                            refresh_pending(db,cid,item)
                return {'ok':True,'candidate':cid,'result':'submitted','status':'pending'}
            known_ids = {r['id'] for v in current.values() for r in v}
            statements = {statement_key(c['statement']) for c in current['claims']}
            for _,_,_,queued_item in queued:
                if queued_item['version']!=1:continue
                queued = queued_item['records']
                known_ids.update(r['id'] for v in queued.values() for r in v)
                statements.update(statement_key(c['statement']) for c in queued['claims'])
            if life.enabled(db):
                # P1 can retain additional evidence and reconcile in an exact
                # reviewed plan. P0's add-only admission contract is unchanged.
                existing={r['id']:(g,r) for g,rs in current.items() for r in rs}
                for g,rs in item['records'].items():
                    for r in rs:
                        old=existing.get(r['id'])
                        if old and old[1]!=r:
                            require(g=='claims' and old[0]==g and
                                    {k:v for k,v in r.items() if k!='evidence'}=={k:v for k,v in old[1].items() if k!='evidence'},'record-id-conflict')
                db.execute('INSERT INTO queue VALUES (?,?,?,NULL)',(cid,canonical_json(item),'pending'))
                checkpoint('queue-written')
                return {'ok':True,'candidate':cid,'result':'submitted','status':'pending'}
            proposed_ids = {r['id'] for v in item['records'].values() for r in v}
            proposed_statements = [statement_key(c['statement']) for c in item['records']['claims']]
            require(len(set(proposed_statements)) == len(proposed_statements), 'duplicate-statements-in-candidate')
            if all(s in statements for s in proposed_statements):
                return {'ok':True, 'result':'duplicate-statement', 'candidate':None}
            require(not proposed_ids & known_ids, 'record-id-conflict')
            require(not any(s in statements for s in proposed_statements), 'partial-duplicate-candidate')
            # Full graph checks occur at prepare so a coordinated batch can reference another candidate.
            db.execute('INSERT INTO queue VALUES (?,?,?,NULL)', (cid,canonical_json(item),'pending'))
            checkpoint('queue-written')
        return {'ok':True,'candidate':cid,'result':'submitted','status':'pending'}

    def submit_git_batch(self, values):
        """Atomically admit bounded Git observations for one source snapshot.

        Receipts follow input order, including duplicates. The caller can
        replay the original payloads if delivery acknowledgments were lost.
        """
        from .confluence import is_binding
        from .discovery import CandidateIndex, inventory, refresh_pending, _write_refreshes

        require(isinstance(values, list) and 1 <= len(values) <= GIT_BATCH_LIMIT, 'invalid-git-candidate-batch-size')
        items = []
        identity = None
        for index, value in enumerate(values):
            try:
                item = candidate(value)
                source = item.get('source')
                require(item['version']==2 and source is not None and not is_binding(source),
                        'incompatible-git-candidate-batch')
                if identity is None:
                    identity = source['identity']
                require(source['identity']==identity, 'incompatible-git-candidate-batch')
            except KnowledgeError as error:
                raise KnowledgeError(error.code, {'index': index, 'details': error.details}) from error
            items.append(item)

        with self.discovery_completion_connection() as db:
            require(life.enabled(db), 'upgrade-required')
            self._records(db)
            queue = self._queue_rows(db)
            by_id = {}
            by_payload = {}
            for position, (cid, status, raw, item) in enumerate(queue):
                row = (position, cid, status, item)
                by_id[cid] = row
                by_payload.setdefault(raw, row)
            pending = []
            receipts = []
            for item in items:
                cid = digest(item)
                serialized = canonical_json(item)
                matches = [row for row in (by_id.get(cid), by_payload.get(serialized)) if row is not None]
                if matches:
                    _, existing, status, registered = min(matches, key=lambda row: row[0])
                    require(registered==item, 'candidate-identity-conflict')
                    receipts.append({'ok':True,'candidate':existing,'result':'duplicate','status':status})
                    continue
                row = (len(queue)+len(pending), cid, 'pending', item)
                by_id[cid] = by_payload[serialized] = row
                pending.append((cid, serialized, item))
                receipts.append({'ok':True,'candidate':cid,'result':'submitted','status':'pending'})
            if pending:
                index = CandidateIndex(db, (row for row in queue if row[3].get('source') is not None))
                refreshes = []
                for cid, _, item in pending:
                    refresh_pending(db,cid,item,index,staged=refreshes)
                require(inventory(self.project.root)['identity']==identity, 'source-changed-before-candidate-batch')
                db.executemany('INSERT INTO queue VALUES (?,?,?,NULL)',
                               ((cid,raw,'pending') for cid,raw,_ in pending))
                _write_refreshes(db, refreshes)
                checkpoint('queue-written')
        return receipts

    def _preview(self, db, source_identity=None, progress=None):
        tick=progress or (lambda *args,**kwargs:None)
        tick('loading-canonical-knowledge')
        current = self._records(db)
        tick('loading-candidate-operations')
        queued=view(db,'validated-queue',lambda:self._check_control(db))
        pending = {cid:item for cid,status,raw,item in sorted(queued) if status=='pending'}
        if life.enabled(db):
            from .discovery import candidate_refreshes
            refreshed=candidate_refreshes(db)
            skipped=[dict(candidate=cid,reason='source-refreshed',replacement=refreshed[cid]['replacement']) for cid in pending if cid in refreshed]
            pending={cid:item for cid,item in pending.items() if cid not in refreshed}
            from .confluence import pending_partition
            pending,source_skipped,blocked=pending_partition(db,pending)
            skipped.extend(source_skipped)
            if db.execute("SELECT 1 FROM plans WHERE status='COMMITTED' LIMIT 1").fetchone():
                blocked=[{'code':'pending-acknowledgment-recover-first','details':None}]
            try:
                if not blocked:
                    from .providers import verify_semantic_bindings
                    bindings=verify_semantic_bindings(db,pending)
                    life.verify_source_bindings(self,pending.values(),db,git_identity=source_identity)
                    from .plan_deduplication import reconcile
                    from .persistence_identity import recovery_projection
                    tick('loading-scan-artifacts')
                    derived,preferred=recovery_projection(db,pending)
                    resolved,diagnostic,conflicts=reconcile(current,derived,life.latest(db),bindings,preferred=preferred,project=self.project.identity,progress=tick)
                    blocked.extend(conflicts)
                    if not blocked:
                        tick('validating-operations',total_operations=diagnostic['counts']['proposed_operations'])
                        life.simulate(self,db,{cid:v for cid,v in resolved.items() if v is not None},check_source=False)
            except KnowledgeError as e:blocked=[{'code':e.code,'details':e.details}]
            base=life.state_fingerprint(self,db)
            if not blocked and bindings:base=fingerprint({'canonical':base,'semantic_bindings':bindings})
            result={'version':1,'project':self.project.identity,'base':base,
                    'candidates':pending,'included':list(pending) if not blocked else [],'skipped':skipped, 'blocked':blocked}
            if 'resolved' in locals() and (resolved!=pending or diagnostic['groups']):
                result.update(version=2,resolved=resolved,deduplication=diagnostic)
            return result
        combined = deepcopy(current)
        for item in pending.values():
            for g in GROUPS:
                combined[g].extend(item['records'][g])
        blocked = []
        try:
            validate_records(combined)
            statements = [statement_key(c['statement']) for c in combined['claims']]
            require(len(statements) == len(set(statements)), 'duplicate-statement')
        except KnowledgeError as e:
            blocked = [{'code':e.code,'details':e.details}]
        return {'version':1,'project':self.project.identity,'base':fingerprint(current),
                'candidates':pending,'included':list(pending) if not blocked else [],
                'skipped':[], 'blocked':blocked}

    def prepare(self, _source_identity=None, progress=None):
        tick=progress or (lambda *args,**kwargs:None)
        tick('loading-store')
        with self.connection(True) as db:
            preview = self._preview(db,_source_identity,tick)
            tick('building-final-plan')
            tick('generating-fingerprint')
            pid = fingerprint(preview)
            tick('persisting-plan', total_candidates=len(preview['candidates']) + len(preview['skipped']))
            db.execute('INSERT OR IGNORE INTO plans VALUES (?,?,?)',(pid,canonical_json(preview),'PREPARED'))
        tick('blocked' if preview['blocked'] else 'prepared')
        return {'ok':not preview['blocked'],'fingerprint':pid,**preview}

    def pending_git_sources(self):
        """Machine approval inventory applies only to actual local-source work."""
        from .confluence import is_binding
        from .discovery import candidate_refreshes
        with self.connection() as db:
            refreshed=candidate_refreshes(db) if life.enabled(db) else {}
            return any(not is_binding(item.get('source'))
                       for cid,status,raw,item in view(db,'validated-queue',lambda:self._check_control(db)) if status=='pending' and cid not in refreshed)

    def duplicate_diagnostics(self,group=None):
        from .plan_deduplication import reconcile,operations
        from .providers import semantic_bindings
        from .discovery import candidate_refreshes
        with self.connection() as db:
            pending={cid:item for cid,status,raw,item in sorted(view(db,'validated-queue',lambda:self._check_control(db))) if status=='pending'}
            refreshed=candidate_refreshes(db) if life.enabled(db) else {}
            pending={cid:v for cid,v in pending.items() if cid not in refreshed}
            from .persistence_identity import recovery_projection
            derived,preferred=recovery_projection(db,pending)
            _,report,_=reconcile(self._records(db),derived,life.latest(db) if life.enabled(db) else {},semantic_bindings(db),life.enabled(db),preferred,self.project.identity)
            if group is None:return report['counts'],report['groups']
            found=next((g for g in report['groups'] if g['group']==group),None);require(found is not None,'unknown-duplicate-group')
            rows=[]
            for cid in found['candidates']:
                item=pending[cid];ops=operations(item);evidence={o['id']:o['payload'] for o in ops if o['kind']=='evidence' and o['payload']}
                for index,op in enumerate(ops):
                    if op['kind']=='claims' and op['payload'] and digest(op['payload']['statement']) in found.get('statement_hashes',[found['statement_hash']]):
                        for eid in op['payload']['evidence']:
                            rows.append({'candidate':cid,'operation':index,'claim':op['id'],'evidence':eid,'source':evidence.get(eid,{}).get('source'),'group':group})
            return report['counts'],rows

    def candidate_text(self,identifier,operation=None,plan=None):
        from .plan_deduplication import operations
        require(isinstance(identifier,str) and 0<len(identifier)<=256,'invalid-candidate-identifier')
        with self.connection() as db:
            if plan:
                value,_=self._plan(db,plan)
                require(identifier in value['candidates'],'unknown-plan-candidate')
                item=value.get('resolved',value['candidates'])[identifier]
            else:
                row=db.execute('SELECT payload FROM queue WHERE id=?',(identifier,)).fetchone();require(row is not None,'unknown-candidate')
                item=loads(row[0])
            if operation is not None:
                require(type(operation) is int and operation>=0 and item is not None,'invalid-candidate-operation')
                items=operations(item);require(operation<len(items),'invalid-candidate-operation');item=items[operation]
            return canonical_json(item)

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
            if plan['version']==1 and life.enabled(db) and all(v['version']==1 for v in plan['candidates'].values()) and plan['base']==fingerprint(self._records(db)):
                # A P0 prepared approval survives a metadata-only upgrade, never a source/canonical edit.
                preview=dict(preview,base=plan['base'])
            require(preview == plan, 'stale-plan-prepare-again')
            for cid in plan['included']:
                value=plan.get('resolved',plan['candidates'])[cid]
                if value is None:continue
                if value['version']==2:
                    life.apply_item(self,db,value,pid)
                    continue
                for group,items in value['records'].items():
                    for record in items:
                        db.execute('INSERT INTO records VALUES (?,?,?)',(record['id'],group,canonical_json(record)))
                        if life.enabled(db):life.append(db,record['id'],group,record,'active',pid,'P0 compatible add',None)
                        checkpoint('canonical-record-written')
            self._records(db)
            if life.enabled(db):
                from .providers import verify_semantic_bindings
                verify_semantic_bindings(db,plan['candidates'])
                life.verify_source_bindings(self,plan['candidates'].values(),db)
                db.execute('INSERT INTO receipts VALUES (?,?)',(pid,canonical_json(plan)))
            db.execute("UPDATE plans SET status='COMMITTED' WHERE id=?",(pid,))
            from .confluence_sync import record_applied
            record_applied(db,plan,pid)
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
                effective=plan.get('resolved',plan['candidates'])[cid]
                if effective is None:continue
                expected=effective
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
        from .discovery import candidate_refreshes
        from .identity_migration import summary
        with self.connection() as db:
            self._records(db)
            return {'ok':True,'project':self.project.describe(),'identity_history':summary(db),
                    'queue':[{'id':i,'status':s,'binding':b} for i,s,b in db.execute('SELECT id,status,binding FROM queue ORDER BY id')],
                    'plans':[{'fingerprint':i,'state':s} for i,s in db.execute('SELECT id,status FROM plans ORDER BY id')],
                    'history':[loads(p) for p, in db.execute('SELECT payload FROM history ORDER BY sequence')],
                    'candidate_refreshes':list(candidate_refreshes(db).values()) if life.enabled(db) else [],
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
        from .cr_workflow import export_workflows
        from .identity_migration import summary
        from .confluence import export as export_confluence
        with self.connection() as db:
            return {'ok':True,'records':self._records(db),'identity_history':summary(db),
                    'queue':[{'id':i,'payload':loads(p),'status':s,'binding':b} for i,p,s,b in db.execute('SELECT * FROM queue ORDER BY id')],
                    'history':[loads(p) for p, in db.execute('SELECT payload FROM history ORDER BY sequence')],**self._export_extension(db),**export_workflows(self,db),**export_confluence(db)}

    def lookup(self, kind, identifier):
        require(kind in GROUPS, 'unsupported-record-kind')
        with self.connection() as db:
            records = self._records(db)
            item = next((r for r in records[kind] if r['id']==identifier),None)
            if life.enabled(db):
                from .discovery import freshness
                state=life.latest(db).get(identifier)
                return {'ok':True,'result':'found' if item else 'no-match','record':item,'revision':state,
                        'freshness':freshness(self.project.root,item,records,db=db) if item and kind=='claims' else None}
        return {'ok':True,'result':'found' if item else 'no-match','record':item}

    def context(self, task, max_bytes=16000, max_items=10, include_unconfirmed=False):
        from .context_delivery import context
        return context(self,task,max_bytes,max_items,include_unconfirmed)



# Public manual/automatic-compatible facades have exactly one mutation implementation.
def submit_manual(root, payload):
    return Store(root).submit(payload)


def submit_automatic(root, payload):
    return Store(root).submit(payload)
