from contextlib import closing
from copy import deepcopy
import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from knowledge.store import Store, submit_manual, submit_automatic, validate_records
from knowledge.project import Project
from knowledge.util import KnowledgeError, canonical_json, loads
from knowledge import migration
from harness.consumer import context
from fixtures import addition,legacy_fixture


def competing(root,barrier,results,automatic):
    barrier.wait()
    try:
        result=(submit_automatic if automatic else submit_manual)(root,addition('synthetic.other','Synthetic basket preserves quantities.') if automatic else addition())
        results.put(result['result'])
    except KnowledgeError as e:
        results.put(e.code)


def crash(root,phase,operation,pid=None):
    def kill(p):
        if p==phase: os._exit(73)
    with patch('knowledge.store.checkpoint',kill),patch('knowledge.migration.checkpoint',kill):
        s=Store(root)
        if operation=='submit': s.submit(addition())
        elif operation=='apply': s.apply(pid,pid)
        elif operation=='ack': s.acknowledge(pid)
        elif operation=='init': s.init()
        else: migration.apply(root,pid)


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='knowledge-tests-')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'проект with spaces'; self.root.mkdir()
        (self.root/'Fixture.cs').write_text('Synthetic basket preserves quantities.\n')
        self.s=Store(self.root); self.s.init()

    def commit(self,item=None):
        self.s.submit(item or addition()); p=self.s.prepare(); self.assertTrue(p['ok']); f=p['fingerprint']
        self.s.apply(f,f); self.s.acknowledge(f); return f

    def test_init_and_version_cli(self):
        self.assertEqual(self.s.validate()['counts'],{'claims':0,'evidence':0,'relationships':0})
        p=subprocess.run([sys.executable,'-m','knowledge.cli','version','--root',str(self.root)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr); self.assertEqual(loads(p.stdout)['operations'],['add'])
        self.assertFalse((self.root/'.knowledge/tools').exists())

    def test_end_to_end_identity_provenance(self):
        item=addition(); f=self.commit(item)
        self.assertEqual(self.s.lookup('claims','synthetic.rule')['record'],item['records']['claims'][0])
        q=self.s.context('synthetic.rule'); self.assertEqual(q['claims'][0]['provenance'],item['records']['claims'][0]['provenance'])
        self.assertEqual(q['evidence'][0]['id'],'evidence.synthetic.rule')
        self.assertEqual(self.s.status()['queue'][0]['binding'],f)
        self.assertEqual(context(self.root,'synthetic.rule')['context']['claims'],q['claims'])

    def test_duplicate_retry(self):
        f=self.commit(); self.assertEqual(self.s.submit(addition())['result'],'duplicate')
        self.assertEqual(self.s.apply(f,f)['result'],'already-committed'); self.s.acknowledge(f)
        self.assertEqual(self.s.validate()['counts']['claims'],1)
        self.assertEqual(self.s.submit(addition('other','Synthetic basket preserves quantities.'))['result'],'duplicate-statement')
        self.assertEqual(self.s.submit(addition('case-sensitive-other','  SYNTHETIC   basket preserves quantities. '))['result'],'submitted')

    def test_busy_all_mutations(self):
        self.s.submit(addition()); p=self.s.prepare()['fingerprint']
        with self.s.connection(True):
            for fn in [lambda:submit_manual(self.root,addition()),lambda:submit_automatic(self.root,addition()),self.s.prepare,
                       lambda:self.s.apply(p,p),lambda:self.s.acknowledge(p)]:
                with self.assertRaisesRegex(KnowledgeError,'store-busy-retry'): fn()
        self.s.apply(p,p); self.s.acknowledge(p)

    def test_competing_writers(self):
        ctx=multiprocessing.get_context('fork' if os.name=='posix' else 'spawn'); barrier=ctx.Barrier(3); results=ctx.Queue()
        workers=[ctx.Process(target=competing,args=(str(self.root),barrier,results,i)) for i in (False,True)]
        for p in workers:p.start()
        barrier.wait()
        for p in workers:p.join(20); self.assertEqual(p.exitcode,0)
        values=[results.get(timeout=2) for _ in workers]
        self.assertEqual(values.count('submitted'),1,values)
        self.assertIn(next(v for v in values if v!='submitted'),('duplicate-statement','store-busy-retry'))
        self.assertEqual(len(self.s.status()['queue']),1)

    def test_bad_candidates(self):
        originals=self.s.export()
        mutations=[lambda x:x.update(operation='retire'),lambda x:x.update(version=True),
                   lambda x:x.update(lifecycle='retired'),lambda x:x['records']['claims'][0].update(id='../escape'),
                   lambda x:x['records']['claims'][0].update(statement=' '),
                   lambda x:x['records']['claims'][0].update(statement=chr(0xD800)),lambda x:x['records']['claims'][0].update(evidence=[])]
        for mutate in mutations:
            item=addition(); mutate(item)
            with self.assertRaises(KnowledgeError):self.s.submit(item)
        self.assertEqual(self.s.export(),originals)

    def test_json_restrictions(self):
        for text in ['{"a":1,"a":2}','{"a":NaN}','{broken']:
            with self.assertRaises(KnowledgeError): loads(text)

    def test_damaged_plan_refused(self):
        self.s.submit(addition());self.s.prepare()
        with closing(sqlite3.connect(self.s.path)) as db, db:db.execute("UPDATE plans SET payload='{}'")
        with self.assertRaisesRegex(KnowledgeError,'corrupt-plan'):self.s.recover()

    def test_conflicting_ids_and_partial_duplicate(self):
        self.s.submit(addition())
        with self.assertRaisesRegex(KnowledgeError,'record-id-conflict'):
            self.s.submit(addition(statement='Changed payload with reused identity.'))
        a=addition('new','Synthetic basket preserves quantities.');b=addition('another','Different statement.')
        for g in a['records']:a['records'][g].extend(b['records'][g])
        with self.assertRaisesRegex(KnowledgeError,'partial-duplicate'):self.s.submit(a)

    def test_stale_and_wrong_approval(self):
        self.s.submit(addition()); p=self.s.prepare()['fingerprint']
        with self.assertRaisesRegex(KnowledgeError,'exact-approval'):self.s.apply(p,'wrong')
        self.s.submit(addition('another','Synthetic separate item.'))
        with self.assertRaisesRegex(KnowledgeError,'stale-plan'):self.s.apply(p,p)
        self.assertEqual(self.s.validate()['counts']['claims'],0)
        p=self.s.prepare()['fingerprint']; self.s.apply(p,p)

    def test_invalid_graph_is_blocked(self):
        item=addition();item['records']['evidence'][0]['substantiates']=['missing']
        self.s.submit(item);p=self.s.prepare();self.assertFalse(p['ok']);self.assertTrue(p['blocked'])
        with self.assertRaisesRegex(KnowledgeError,'blocked-plan'):self.s.apply(p['fingerprint'],p['fingerprint'])

    def test_corrupt_queue_refused(self):
        self.s.submit(addition())
        with closing(sqlite3.connect(self.s.path)) as db, db:db.execute("UPDATE queue SET payload='{}'")
        for fn in [self.s.prepare,lambda:self.s.submit(addition()),self.s.recover,self.s.validate]:
            with self.assertRaises(KnowledgeError):fn()

    def test_crash_boundaries(self):
        ctx=multiprocessing.get_context('fork' if os.name=='posix' else 'spawn')
        def run(phase,op,pid=None):
            p=ctx.Process(target=crash,args=(str(self.root),phase,op,pid));p.start();p.join(20);self.assertEqual(p.exitcode,73)
        run('queue-written','submit');self.assertEqual(self.s.status()['queue'],[])
        self.s.submit(addition());pid=self.s.prepare()['fingerprint']
        run('canonical-record-written','apply',pid);self.assertEqual(self.s.validate()['counts']['claims'],0)
        run('after-canonical-commit','apply',pid);self.assertEqual(self.s.validate()['counts']['claims'],1)
        self.assertEqual(self.s.status()['queue'][0]['status'],'pending')
        run('acknowledgment-written','ack',pid);self.assertEqual(self.s.status()['queue'][0]['status'],'pending')
        self.s.recover();self.assertEqual(self.s.status()['queue'][0]['status'],'imported')
        self.s.recover();self.assertEqual(self.s.validate()['counts']['claims'],1)

    def test_init_crash_before_and_after_publication(self):
        other=self.root.parent/'fresh';other.mkdir()
        for phase in ('init-before-publish','init-after-publish'):
            p=multiprocessing.get_context('fork' if os.name=='posix' else 'spawn').Process(target=crash,args=(str(other),phase,'init'))
            p.start();p.join(20);self.assertEqual(p.exitcode,73)
            if phase=='init-before-publish':self.assertFalse((other/'.knowledge/store.sqlite3').exists())
            else:self.assertEqual(Store(other).validate()['counts']['claims'],0)
        Store(other).init()

    def test_changed_committed_payload_preserved(self):
        self.s.submit(addition());pid=self.s.prepare()['fingerprint'];self.s.apply(pid,pid)
        with closing(sqlite3.connect(self.s.path)) as db, db:
            row=db.execute("SELECT payload FROM records WHERE kind='claims'").fetchone();item=loads(row[0]);item['statement']='Unrelated edit.'
            db.execute("UPDATE records SET payload=? WHERE kind='claims'",(canonical_json(item),))
        with self.assertRaisesRegex(KnowledgeError,'committed-payload-changed'):self.s.recover()
        self.assertEqual(self.s.lookup('claims','synthetic.rule')['record']['statement'],'Unrelated edit.')
        self.assertEqual(self.s.status()['queue'][0]['status'],'pending')

    def test_ack_payload_not_just_id(self):
        self.s.submit(addition());pid=self.s.prepare()['fingerprint'];self.s.apply(pid,pid)
        with closing(sqlite3.connect(self.s.path)) as db, db:
            item=addition();item['records']['claims'][0]['statement']='Replaced same claim ID.'
            from knowledge.util import digest
            db.execute('UPDATE queue SET id=?,payload=?',(digest(item),canonical_json(item)))
        with self.assertRaisesRegex(KnowledgeError,'ownership-mismatch'):self.s.acknowledge(pid)
        self.assertEqual(self.s.validate()['counts']['claims'],1)

    def test_roots_links_and_escape(self):
        other=self.root.parent/'проект with spaces2';other.mkdir();Store(other).init()
        self.commit();self.assertEqual(Store(other).context('synthetic.rule')['claims'],[])
        self.assertNotEqual(Project(other).identity,Project(self.root).identity)
        for root in [None,str(self.root/'..'),str(self.root/'missing')]:
            with self.assertRaises(KnowledgeError):Project(root)
        link=self.root.parent/'link';link.symlink_to(self.root,target_is_directory=True)
        with self.assertRaisesRegex(KnowledgeError,'linked'):Store(link)
        (other/'.knowledge/evil').symlink_to(self.s.path)
        with self.assertRaisesRegex(KnowledgeError,'linked'):Store(other)

    def test_copied_store_identity(self):
        import shutil
        other=self.root.parent/'copied';other.mkdir();shutil.copytree(self.s.base,other/'.knowledge')
        with self.assertRaisesRegex(KnowledgeError,'identity-mismatch'):Store(other).validate()

    def test_budget_no_answer_and_unconfirmed(self):
        self.commit(addition(status='INFERRED'))
        self.assertEqual(self.s.context('synthetic.rule')['claims'],[])
        q=self.s.context('synthetic.rule',include_unconfirmed=True)
        self.assertEqual(q['claims'][0]['status'],'INFERRED'); self.assertFalse(q['claims'][0]['confirmed'])
        self.assertEqual(self.s.context('xylophonequasar')['result'],'insufficient-evidence')
        for size in [256,512,1000,16000]:
            value=self.s.context('synthetic.rule',size,include_unconfirmed=True)
            self.assertLessEqual(len(canonical_json(value).encode()),size)
            if 'truncation' in value:
                self.assertEqual(value['truncation']['returned'],len(value['claims']))
                self.assertEqual(value['truncation']['dropped'],value['truncation']['candidates']-len(value['claims']))
        for size in [-1,True,255,1000001]:
            with self.assertRaises(KnowledgeError):self.s.context('query',size)

    def test_harness_absence_and_corruption(self):
        other=self.root.parent/'absent';other.mkdir()
        self.assertEqual(context(other,'query')['mode'],'degraded')
        self.s.path.write_bytes(b'corrupt')
        with self.assertRaises(KnowledgeError):context(self.root,'query')

    def test_harness_configuration_budget(self):
        self.commit();(self.root/'.harness').mkdir();(self.root/'.harness/config.json').write_text('{"response_max_bytes":1024}')
        self.assertLessEqual(len(canonical_json(context(self.root,'synthetic.rule')).encode()),1024)

    def test_legacy_schema_hashes_and_confidence_semantics(self):
        import hashlib
        from knowledge.store import SCHEMAS
        from knowledge import legacy_validator as v
        for kind in ('claim','evidence','relationship'):
            schema=loads((SCHEMAS/f'{kind}.schema.json').read_text())
            hashed=hashlib.sha256(json.dumps(schema,sort_keys=True).encode()).hexdigest()
            self.assertEqual(hashed,v.CONFLUENCE_EVIDENCE_SCHEMA if kind=='evidence' else v.SCHEMA_HASHES[kind])
            if kind=='evidence':
                # Removing only the native source alternative recovers the exact
                # pinned legacy schema, including original confidence semantics.
                schema['properties']['source']['anyOf'].pop()
                self.assertEqual(hashlib.sha256(json.dumps(schema,sort_keys=True).encode()).hexdigest(),v.SCHEMA_HASHES[kind])
        item=addition();item['records']['claims'][0]['type']='business_rule'
        with self.assertRaisesRegex(KnowledgeError,'invalid-dataset'):validate_records(item['records'])


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'legacy space';self.root.mkdir()
        self.records,self.queue=legacy_fixture(self.root)

    def test_lossless_repeat_restore(self):
        before=migration.snapshot(self.root);preview=migration.preview(self.root)
        migration.apply(self.root,preview['fingerprint'])
        exported=Store(self.root).export()
        for g,items in self.records.items():self.assertEqual(sorted(exported['records'][g],key=lambda r:r['id']),sorted(items,key=lambda r:r['id']))
        self.assertEqual(exported['history'][0]['legacy_queue'],self.queue)
        self.assertEqual({q['id']:q['status'] for q in exported['queue']},{q['id']:q['status'] for q in self.queue})
        for q in self.queue:
            result=Store(self.root).submit(q['payload']);self.assertEqual(result['candidate'],q['id']);self.assertEqual(result['status'],q['status'])
        self.assertEqual(migration.snapshot(self.root),before)
        self.assertEqual(migration.apply(self.root,preview['fingerprint'])['result'],'already-migrated')
        dest=self.root.parent/'restored';migration.restore_legacy(self.root,dest)
        original=self.root/'.ai'
        self.assertEqual({p.relative_to(original).as_posix():p.read_bytes() for p in original.rglob('*') if p.is_file()},
                         {p.relative_to(dest).as_posix():p.read_bytes() for p in dest.rglob('*') if p.is_file()})
        with self.assertRaises(KnowledgeError):migration.restore_legacy(self.root,dest)
        p=Store(self.root).prepare();self.assertTrue(p['ok']);Store(self.root).apply(p['fingerprint'],p['fingerprint']);Store(self.root).recover()

    def test_incomplete_and_dual_store(self):
        next((self.root/'.ai/state/population/plans').glob('*.json')).unlink()
        with self.assertRaisesRegex(KnowledgeError,'missing-plan'):migration.preview(self.root)
        with self.assertRaisesRegex(KnowledgeError,'legacy-store-present'):Store(self.root).init()

    def test_interrupted_migration(self):
        before=migration.snapshot(self.root);pid=migration.preview(self.root)['fingerprint']
        for phase in ('migration-record-written','migration-before-publish'):
            p=multiprocessing.get_context('fork' if os.name=='posix' else 'spawn').Process(target=crash,args=(str(self.root),phase,'migrate',pid));p.start();p.join(20)
            self.assertEqual(p.exitcode,73);self.assertFalse((self.root/'.knowledge/store.sqlite3').exists())
            self.assertEqual(migration.snapshot(self.root),before)
        migration.apply(self.root,pid);Store(self.root).validate()

    def test_migration_crash_after_publication(self):
        pid=migration.preview(self.root)['fingerprint']
        p=multiprocessing.get_context('fork' if os.name=='posix' else 'spawn').Process(target=crash,args=(str(self.root),'migration-after-publish','migrate',pid))
        p.start();p.join(20);self.assertEqual(p.exitcode,73)
        Store(self.root).validate()
        self.assertEqual(migration.apply(self.root,pid)['result'],'already-migrated')

    def test_stale_and_ambiguous_target(self):
        pid=migration.preview(self.root)['fingerprint'];(self.root/'.ai/extra.txt').write_text('unrelated')
        with self.assertRaisesRegex(KnowledgeError,'approval'):migration.apply(self.root,pid)
        # Independent store + legacy input must never be silently merged.
        import shutil
        backup=self.root.parent/'saved';shutil.move(self.root/'.ai',backup)
        Store(self.root).init();shutil.move(backup,self.root/'.ai')
        with self.assertRaisesRegex(KnowledgeError,'ambiguous-dual'):Store(self.root).validate()
        with self.assertRaises(KnowledgeError):migration.apply(self.root,migration.preview(self.root)['fingerprint'])
