"""Public SQLite integrity, snapshot lifetime and physical-index maintenance."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from knowledge import operations as op,maintenance as m,sqlite_indexes as ix
from knowledge.sqlite_snapshot import Connection
from knowledge.store import Store
from knowledge.util import KnowledgeError,canonical_json,digest
from harness.runtime import Journal
from fixtures import addition,legacy_fixture


class SQLiteOptimization(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'project';self.root.mkdir()
        (self.root/'Fixture.cs').write_text('class Fixture {}\n')
        self.shared=Path(self.tmp.name)/'shared';self.store=op.OperationalStore(self.root)
        self.saved=op.teach(self.root,'Remember fixture encoding',{'type':'user-message','id':'one'},
            binding={'trigger':{'tool':'patch','name':'Fixture.cs'},'behavior':{'adapter':'preserve-format'}})
        self.record=self.store.records()['records'][0]
    def tearDown(self):self.tmp.cleanup()
    def preview(self,operation='index-upgrade',suffix='first'):
        return m.preview(self.root,operation,Path(self.tmp.name)/(suffix+'.zip'))
    def apply(self,p):return m.apply(self.root,p['preview'],p['fingerprint'])
    def mutate(self,sql,args=()):
        with closing(sqlite3.connect(self.store.path)) as db, db:db.execute(sql,args)
    def lookup(self):return op.lookup(self.root,{'tool':'patch','name':'Fixture.cs'},{},shared=self.shared)

    def test_snapshot_bulk_audit_once_and_detached_public_results(self):
        for i in range(3):op.application(self.root,'project',self.shared,self.saved['id'],1,str(i),{'ok':True},[])
        with patch.object(op,'validate_record',wraps=op.validate_record) as validate:
            result=self.store.records()
        self.assertEqual(validate.call_count,1)
        result['records'][0]['status']='retired'
        self.assertEqual(self.store.records()['records'][0]['status'],'active')
        with self.store.connection() as db:
            a=op.current(db);a[0]['status']='retired';self.assertEqual(op.current(db)[0]['status'],'active')

    def test_snapshot_write_cursor_rollback_and_new_transaction_invalidation(self):
        with self.store.connection(True) as db:
            op.current(db);db.execute('SAVEPOINT test')
            db.execute('SELECT 1').execute('UPDATE operational_current SET payload=?',('{}',))
            with self.assertRaises(KnowledgeError):op.current(db)
            db.execute('ROLLBACK TO test');self.assertEqual(op.current(db)[0]['id'],self.saved['id'])
            db.rollback();db.execute('BEGIN IMMEDIATE');self.assertEqual(op.current(db)[0]['id'],self.saved['id'])
            # A base-class write also changes total_changes and cannot reuse trust.
            sqlite3.Connection.execute(db,'UPDATE operational_current SET payload=?',('{}',))
            with self.assertRaises(KnowledgeError):op.current(db)
            db.rollback()

    def test_base_cursor_and_transaction_trace_cannot_reuse_rolled_back_state(self):
        with self.store.connection(True) as db:
            raw=db.cursor(factory=sqlite3.Cursor)
            raw.execute('SAVEPOINT correction')
            value=deepcopy(self.record);value['revision']=2;value['status']='retired';value.pop('content_hash')
            op.append(db,value);self.assertEqual(op.current(db)[0]['status'],'retired')
            raw.execute('ROLLBACK TO correction')
            self.assertEqual(op.current(db)[0]['status'],'active')
            sqlite3.Connection.rollback(db)
            sqlite3.Connection.execute(db,'BEGIN IMMEDIATE')
            self.assertEqual(op.current(db)[0]['status'],'active')

    def test_plain_connections_never_reuse_a_view(self):
        with closing(sqlite3.connect(self.store.path)) as db, db:
            op.current(db);db.execute('UPDATE operational_current SET payload=?',('{}',))
            with self.assertRaises(KnowledgeError):op.current(db)
            db.rollback()

    def test_unselected_current_history_and_orphan_history_corruption(self):
        other=op.teach(self.root,'Other rule',{'type':'user-message','id':'two'},binding={'trigger':{'tool':'patch','name':'Other.cs'},'behavior':{'adapter':'preserve-format'}})
        raw=self.store.path.read_bytes()
        for sql,args in [
            ('UPDATE operational_current SET payload=? WHERE id=?',('{}',other['id'])),
            ('UPDATE operational_history SET payload=? WHERE id=?',('{}',other['id'])),
            ('INSERT INTO operational_history VALUES (?,?,?)',('orphan',1,canonical_json(self.record)))]:
            with self.subTest(sql=sql):
                self.store.path.write_bytes(raw);self.mutate(sql,args)
                with self.assertRaises(KnowledgeError):self.lookup()
        self.store.path.write_bytes(raw)

    def test_corrupt_older_history_detected_after_valid_current_cache(self):
        value=deepcopy(self.record);value['revision']=2;value.pop('content_hash')
        with self.store.connection(True) as db:op.append(db,value)
        self.store.records()
        self.mutate('UPDATE operational_history SET payload=? WHERE revision=1',('{}',))
        with self.assertRaises(KnowledgeError):self.lookup()

    def test_invalid_and_orphan_events_are_not_no_match(self):
        raw=self.store.path.read_bytes()
        for event in ({'request':'bad','result':{}},{'request':'a'*64,'result':{'id':'absent','revision':1}},{'request':'a'*64,'result':{'id':[],'revision':1}}):
            self.store.path.write_bytes(raw);self.mutate('INSERT INTO operational_events VALUES (?,?)',(digest(event),canonical_json(event)))
            with self.assertRaises(KnowledgeError):self.lookup()
        self.store.path.write_bytes(raw)

    def test_binding_sequences_application_row_order_and_old_revision(self):
        with patch.object(op.time,'time',return_value=9):first=op.binding_event(self.root,self.record,self.shared,'verified')
        with patch.object(op.time,'time',return_value=9):second=op.binding_event(self.root,self.record,self.shared,'blocked')
        with patch.object(op.time,'time',return_value=1):third=op.binding_event(self.root,self.record,self.shared,'attempted')
        self.assertEqual([first['sequence'],second['sequence'],third['sequence']],[1,2,3])
        self.assertEqual(self.lookup()['bindings'][self.saved['id']]['state'],'attempted')
        with patch.object(op.time,'time',return_value=9):op.application(self.root,'project',self.shared,self.saved['id'],1,'first',{'ok':True},[])
        with patch.object(op.time,'time',return_value=1):op.application(self.root,'project',self.shared,self.saved['id'],1,'last',{'ok':False},[])
        self.assertFalse(self.lookup()['signals'][self.saved['id']]['outcome']['ok'])
        value=deepcopy(self.record);value['revision']=2;value.pop('content_hash')
        with self.store.connection(True) as db:op.append(db,value)
        self.assertEqual(self.lookup()['signals'],{});self.assertEqual(self.lookup()['bindings'],{})

    def test_fault_before_commit_rolls_back_event_and_invalidates_view(self):
        with patch('knowledge.store.checkpoint',side_effect=RuntimeError('crash')):
            with self.assertRaises(RuntimeError):op.binding_event(self.root,self.record,self.shared,'blocked')
        self.assertEqual(self.lookup()['bindings'],{})

    def test_concurrent_sequences_and_bounded_busy(self):
        def write(i):return op.binding_event(self.root,self.record,self.shared,'verified')['sequence']
        with ThreadPoolExecutor(3) as pool:values=list(pool.map(write,range(3)))
        self.assertEqual(sorted(values),[1,2,3])
        with closing(sqlite3.connect(self.store.path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            with self.assertRaisesRegex(KnowledgeError,'store-busy-retry'):write(4)

    def test_fresh_process_roots_shared_and_external_corruption(self):
        op.teach(self.root,'Shared rule',{'type':'user-message','id':'shared'},scope='shared',shared=self.shared)
        code='from knowledge.operations import OperationalStore; import sys,json; print(json.dumps(OperationalStore(sys.argv[1]).records()))'
        p=subprocess.run([sys.executable,'-I','-c',code,str(self.root)],text=True,capture_output=True)
        self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(len(json.loads(p.stdout)['records']),1)
        other=Path(self.tmp.name)/'other';other.mkdir();self.assertEqual(op.OperationalStore(other).records()['state'],'absent')
        self.store.records();self.mutate('UPDATE operational_current SET payload=?',('{}',))
        p=subprocess.run([sys.executable,'-I','-c',code,str(self.root)],text=True,capture_output=True)
        self.assertNotEqual(p.returncode,0)

    def test_dedup_exact_payload_legacy_id_and_mismatched_identity(self):
        from knowledge.migration import apply as migrate,preview
        root=Path(self.tmp.name)/'legacy';root.mkdir();legacy_fixture(root)
        # Exercise the supported predecessor migration, not a fabricated ID.
        p=preview(root);migrate(root,p['fingerprint'])
        store=Store(root)
        with store.connection() as db:item=json.loads(db.execute("SELECT payload FROM queue WHERE id='legacy-pending'").fetchone()[0])
        result=store.submit(item);self.assertEqual(result['candidate'],'legacy-pending');self.assertEqual(result['result'],'duplicate')
        first=addition('new','New fixture');store.submit(first);self.assertEqual(store.submit(first)['result'],'duplicate')
        with closing(sqlite3.connect(store.path)) as db, db:db.execute('UPDATE queue SET payload=? WHERE id=?',(canonical_json(addition('wrong','Wrong payload')),digest(first)))
        with self.assertRaises(KnowledgeError):store.submit(first)

    def test_new_journal_index_and_existing_reads_do_not_migrate(self):
        journal=Journal(self.root)
        with journal.db() as db:self.assertTrue(ix.check(db));db.execute('DROP INDEX '+ix.NAME)
        before=journal.path.read_bytes()
        Journal(self.root).outbox('absent')
        self.assertEqual(journal.path.read_bytes(),before)
        with journal.db() as db:self.assertFalse(ix.check(db))

    def test_nonempty_index_upgrade_repeat_rollback_backup_restore(self):
        journal=Journal(self.root)
        journal.put_outbox('a','run',{'state':'pending'});journal.put_outbox('b','other',{'state':'delivered'})
        with journal.db() as db:db.execute('DROP INDEX '+ix.NAME)
        before=ix.identity(journal.project);p=self.preview();result=self.apply(p)
        self.assertEqual(ix.identity(journal.project),before);self.assertEqual(self.apply(p)['result'],'already-completed')
        self.assertEqual(journal.outbox('run'),{'a':{'state':'pending'}});self.assertEqual(journal.outbox('absent'),{})
        back=self.preview('index-rollback','rollback');self.apply(back)
        with journal.db() as db:self.assertFalse(ix.check(db))
        self.assertEqual(ix.identity(journal.project),before)
        upgrade=self.preview(suffix='again');self.apply(upgrade)
        restore=m.preview(self.root,'restore',archive=result['backup']['path'],recovery=Path(self.tmp.name)/'saved')
        self.apply(restore)
        with journal.db() as db:self.assertFalse(ix.check(db))
        self.assertEqual(ix.identity(journal.project),before)

    def test_interrupted_index_upgrade_recovery_before_and_after_commit(self):
        journal=Journal(self.root);journal.put_outbox('a','run',{'state':'pending'})
        for phase in ('maintenance-prepared','index-before-commit','index-after-commit','maintenance-committed'):
            with self.subTest(phase=phase):
                with journal.db() as db:db.execute('DROP INDEX IF EXISTS '+ix.NAME)
                before=ix.identity(journal.project);p=self.preview(suffix=phase)
                def fault(at):
                    if at==phase:raise RuntimeError('crash')
                with patch.object(m,'fault',side_effect=fault):
                    with self.assertRaises(RuntimeError):self.apply(p)
                with self.assertRaisesRegex(KnowledgeError,'maintenance-recovery-required'):journal.outbox('run')
                self.assertEqual(m.recover(self.root)['status'],'COMPLETED')
                self.assertEqual(ix.identity(journal.project),before)
                with journal.db() as db:self.assertTrue(ix.check(db))

    def test_index_stale_preview_and_conflicting_definition(self):
        journal=Journal(self.root);p=self.preview();journal.put_outbox('a','run',{})
        with self.assertRaisesRegex(KnowledgeError,'stale-maintenance-preview'):self.apply(p)
        with journal.db() as db:db.execute('DROP INDEX '+ix.NAME);db.execute('CREATE INDEX '+ix.NAME+' ON outbox(id)')
        with self.assertRaisesRegex(KnowledgeError,'index-definition-conflict'):self.preview(suffix='conflict')

    def test_standalone_no_journal_index_cli_is_an_explicit_backed_up_noop(self):
        before=self.store.path.read_bytes()
        cmd=[sys.executable,'-I','-m','knowledge.maintain_cli','index-upgrade-preview','--root',str(self.root),'--destination',str(Path(self.tmp.name)/'cli-backup.zip')]
        result=subprocess.run(cmd,text=True,capture_output=True);self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        value=json.loads(result.stdout);self.assertIsNone(value['preview']['index_state'])
        path=Path(self.tmp.name)/'preview.json';path.write_text(canonical_json(value['preview']))
        result=subprocess.run([sys.executable,'-I','-m','knowledge.maintain_cli','apply','--root',str(self.root),'--input',str(path),'--approve',value['fingerprint']],text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr);self.assertEqual(self.store.path.read_bytes(),before)

    def test_older_writer_preserves_index_and_journal_rows(self):
        journal=Journal(self.root)
        # An ordinary predecessor writer needs no knowledge of this physical
        # index; SQLite maintains it transactionally on inserts/updates.
        with closing(sqlite3.connect(journal.path)) as db, db:
            db.execute('INSERT INTO outbox VALUES (?,?,?)',('old','run','{"state":"pending"}'))
            db.execute('UPDATE outbox SET run=? WHERE id=?',('other','old'))
        self.assertEqual(journal.outbox('run'),{});self.assertEqual(journal.outbox('other')['old']['state'],'pending')
        with journal.db() as db:self.assertTrue(ix.check(db));self.assertEqual(db.execute('PRAGMA quick_check').fetchone(),('ok',))

    def test_pure_read_database_bytes_and_sql(self):
        journal=Journal(self.root);before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (self.store.path,journal.path)}
        traced=[];connect=sqlite3.connect
        def wrapped(*a,**kw):
            db=connect(*a,**kw);db.set_trace_callback(traced.append);return db
        with patch.object(sqlite3,'connect',wrapped):self.lookup();Journal(self.root).outbox('absent')
        self.assertEqual(before,{p:hashlib.sha256(p.read_bytes()).hexdigest() for p in before})
        self.assertFalse(any(sql.lstrip().split()[0].upper() in ('CREATE','DROP','ALTER','ANALYZE','INSERT','UPDATE','DELETE') for sql in traced))


if __name__=='__main__':unittest.main()
