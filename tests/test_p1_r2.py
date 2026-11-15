"""Round-2 A/B: real resulting-model and extraction-budget regressions."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from knowledge import discovery as disc,lifecycle as life
from knowledge.store import Store
from knowledge.util import KnowledgeError,canonical_json
from test_p1 import fixture,upgraded,approve


class ReactivationModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);fixture(self.root);self.s=upgraded(self.root)
        disc.scan(self.s,max_files=100);approve(self.s)
        records=self.s.export()['records']
        self.a=next(c for c in records['claims'] if 'Independent' in c['statement'])
        self.b=next(c for c in records['claims'] if c['id']!=self.a['id'])
        self.s.submit(life.batch([life.op('retire','claims',self.a['id'],1)],'synthetic manual retirement'))
        self.retired_plan=approve(self.s)
    def tearDown(self):self.tmp.cleanup()
    def submit(self,ops):return self.s.submit(life.batch(ops,'explicit reviewed round-2 batch'))
    def relationship(self):
        return dict(id='synthetic.r2.edge',type='depends_on',**{'from':self.b['id'],'to':self.a['id']},provenance={'actor':'synthetic','method':'fixture'})
    def mixed(self,reactivate_relationship=False):
        updated=dict(self.a,statement=self.a['statement']+' Reviewed reintroduction.')
        relation=self.relationship()
        ops=[life.op('reactivate','claims',self.a['id'],2,updated),life.op('update','claims',self.b['id'],1,dict(self.b,depends_on=[self.a['id']])),
             life.op('reactivate' if reactivate_relationship else 'add','relationships',relation['id'],2 if reactivate_relationship else 0,relation)]
        return updated,ops

    def test_a_duplicate_reactivation_is_rejected_before_writes(self):
        replacement=dict(self.a,id='synthetic.replacement')
        evidence=deepcopy(next(e for e in self.s.export()['records']['evidence'] if e['id']==self.a['evidence'][0]))
        evidence.update(id='synthetic.replacement.evidence',substantiates=[replacement['id']],provenance={'actor':'synthetic-reviewer','method':'reviewed-fixture-source'});replacement['evidence']=[evidence['id']]
        self.submit([life.op('add','claims',replacement['id'],0,replacement),life.op('add','evidence',evidence['id'],0,evidence)]);approve(self.s)
        self.assertTrue(self.s.validate()['ok']) # inactive historical duplicate is allowed
        before=life.history(self.s,self.a['id'])
        disc.scan(self.s,max_files=100);preview=self.s.prepare()
        self.assertFalse(preview['ok']);self.assertIn('duplicate-statement',[b['code'] for b in preview['blocked']])
        self.assertEqual(life.history(self.s,self.a['id']),before)
        with self.assertRaises(KnowledgeError):self.s.apply(preview['fingerprint'],preview['fingerprint'])

    def test_a_valid_mixed_reactivation_uses_new_payload_and_final_graph(self):
        expected,ops=self.mixed();self.submit(ops);preview=self.s.prepare();self.assertTrue(preview['ok'],preview)
        with self.s.connection() as db:simulated=life.simulate(self.s,db,preview['candidates'])
        pid=preview['fingerprint'];self.s.apply(pid,pid);self.s.acknowledge(pid)
        self.assertEqual(simulated,self.s.export()['records'])
        self.assertEqual(self.s.lookup('claims',self.a['id'])['record'],expected)
        self.assertEqual(self.s.lookup('claims',self.b['id'])['record']['depends_on'],[self.a['id']])
        self.assertEqual([r['lifecycle'] for r in life.history(self.s,self.a['id'])['revisions']],['active','retired','active'])
        self.assertTrue(self.s.validate()['ok'])

    def test_a_reactivation_payload_orphans_cycles_and_inactive_dependencies_fail_preview(self):
        cases=[ [life.op('reactivate','claims',self.a['id'],2,dict(self.a,depends_on=['missing.claim']))],
                [life.op('reactivate','claims',self.a['id'],2,dict(self.a,depends_on=[self.b['id']])),life.op('update','claims',self.b['id'],1,dict(self.b,depends_on=[self.a['id']]))] ]
        for ops in cases:
            with self.subTest(ops=ops):
                before=life.history(self.s,self.a['id']);submitted=self.submit(ops);preview=self.s.prepare();self.assertFalse(preview['ok'])
                self.assertEqual(life.history(self.s,self.a['id']),before);life.dispose(self.s,submitted['candidate'],'rejected','invalid resulting model')
        self.submit([life.op('retire','claims',self.b['id'],1)]);approve(self.s)
        self.submit([life.op('reactivate','claims',self.a['id'],2,dict(self.a,depends_on=[self.b['id']]))]);self.assertFalse(self.s.prepare()['ok'])
        with self.assertRaises(KnowledgeError):life.batch([life.op('reactivate','claims',self.a['id'],2,dict(self.a,unsupported=True))],'bad payload')

    def test_a_retired_relationship_reactivation_checks_final_endpoints(self):
        # Add a valid edge while A is active, then retire edge and A together.
        self.submit([life.op('reactivate','claims',self.a['id'],2,self.a),life.op('update','claims',self.b['id'],1,dict(self.b,depends_on=[self.a['id']])),life.op('add','relationships','synthetic.r2.edge',0,self.relationship())]);approve(self.s)
        self.submit([life.op('retire','relationships','synthetic.r2.edge',1),life.op('retire','claims',self.a['id'],3),life.op('update','claims',self.b['id'],2,self.b)]);approve(self.s)
        bad=self.submit([life.op('reactivate','relationships','synthetic.r2.edge',2,self.relationship())]);self.assertFalse(self.s.prepare()['ok'])
        life.dispose(self.s,bad['candidate'],'rejected','inactive endpoints')
        self.submit([life.op('reactivate','claims',self.a['id'],4,self.a),life.op('update','claims',self.b['id'],3,dict(self.b,depends_on=[self.a['id']])),life.op('reactivate','relationships','synthetic.r2.edge',2,self.relationship())])
        approve(self.s);self.assertEqual(life.history(self.s,'synthetic.r2.edge')['revisions'][-1]['lifecycle'],'active')

    def test_a_validate_rejects_corrupt_active_duplicate_without_deleting_history(self):
        # Test-only corruption retains an immutable earlier receipt and matching latest payload.
        with self.s.connection(True) as db:
            bad=dict(self.b,statement=next(c for c in self.s.export()['records']['claims'] if c['id'] not in (self.a['id'],self.b['id']))['statement'])
            db.execute('UPDATE records SET payload=? WHERE id=?',(canonical_json(bad),self.b['id']))
            life.append(db,self.b['id'],'claims',bad,'active','test-only-corruption','synthetic corrupt fixture',None)
        with self.assertRaisesRegex(KnowledgeError,'duplicate-statement'):Store(self.root).validate()
        with sqlite3.connect(self.s.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM revisions WHERE id=?',(self.b['id'],)).fetchone()[0],2)
            self.assertEqual(db.execute('SELECT payload FROM records WHERE id=?',(self.b['id'],)).fetchone()[0],canonical_json(bad))

    def test_a_real_reactivation_crashes_approval_recovery_and_old_retries(self):
        expected,ops=self.mixed();self.submit(ops);preview=self.s.prepare();self.assertTrue(preview['ok']);pid=preview['fingerprint']
        with self.assertRaises(KnowledgeError):self.s.apply(pid,'wrong approval')
        from fixtures import addition
        extra=self.s.submit(addition('synthetic.extra','Synthetic unrelated pending proposal.'))
        with self.assertRaises(KnowledgeError):self.s.apply(pid,pid)
        life.dispose(self.s,extra['candidate'],'deferred','preserve unrelated proposal')
        for phase,length in [('canonical-record-written',2),('after-canonical-commit',3)]:
            code='from knowledge import store;import os;s=store.Store('+repr(str(self.root))+');store.checkpoint=lambda p:os._exit(73) if p=='+repr(phase)+' else None;s.apply('+repr(pid)+','+repr(pid)+')'
            self.assertEqual(subprocess.run([sys.executable,'-c',code]).returncode,73)
            self.assertEqual(len(life.history(self.s,self.a['id'])['revisions']),length)
        code='from knowledge import store;import os;s=store.Store('+repr(str(self.root))+');store.checkpoint=lambda p:os._exit(73) if p=="acknowledgment-written" else None;s.acknowledge('+repr(pid)+')'
        self.assertEqual(subprocess.run([sys.executable,'-c',code]).returncode,73)
        self.s.recover();self.s.acknowledge(pid);self.s.apply(pid,pid)
        self.s.apply(self.retired_plan,self.retired_plan);self.s.acknowledge(self.retired_plan)
        self.assertEqual(self.s.lookup('claims',self.a['id'])['record'],expected)
        self.assertEqual(len(life.history(self.s,self.a['id'])['revisions']),3)

    def test_a_inactive_successor_is_rejected_by_resulting_model(self):
        third=next(c for c in self.s.export()['records']['claims'] if c['id'] not in (self.a['id'],self.b['id']))
        self.submit([life.op('retire','claims',third['id'],1)]);approve(self.s)
        self.submit([life.op('reactivate','claims',self.a['id'],2,self.a),life.op('supersede','claims',self.b['id'],1,successor=third['id'])])
        preview=self.s.prepare();self.assertFalse(preview['ok'])
        self.assertIn('inactive-successor-terminal',[b['code'] for b in preview['blocked']])
        self.assertEqual(life.history(self.s,self.a['id'])['revisions'][-1]['lifecycle'],'retired')

    def test_a_mixed_v1_v2_same_target_is_not_order_dependent(self):
        from fixtures import addition
        value=addition('synthetic.shared','Synthetic shared target.')
        self.s.submit(value)
        candidate=self.s.submit(life.batch([life.op('update','claims','synthetic.shared',0,dict(value['records']['claims'][0],statement='Changed shared target.'))],'ambiguous same target'))
        self.assertFalse(self.s.prepare()['ok'])
        with self.s.connection() as db:
            for items in ({'v1':value,'v2':life.batch([life.op('update','claims','synthetic.shared',0,value['records']['claims'][0])],'test')},
                          {'v2':life.batch([life.op('update','claims','synthetic.shared',0,value['records']['claims'][0])],'test'),'v1':value}):
                with self.assertRaises(KnowledgeError):life.simulate(self.s,db,items)
        self.assertEqual(self.s.lookup('claims','synthetic.shared')['result'],'no-match')


class BoundedExtractionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);fixture(self.root)
        for i in range(20):(self.root/'Tests'/f'Extra{i:02}.cs').write_text(f'public class Extra{i:02} {{}}\n')
        self.s=upgraded(self.root)
    def tearDown(self):self.tmp.cleanup()

    def test_b_initial_resume_and_completion_reuse_real_bounded_extraction(self):
        paths=[];real=disc.extract
        def observe(*args):paths.append(args[1]);return real(*args)
        with patch.object(disc,'extract',side_effect=observe):
            result=disc.scan(self.s,max_files=1);self.assertEqual(len(paths),1)
            while not result['complete']:
                before=len(paths);result=disc.scan(self.s,result['id'],1);self.assertEqual(len(paths)-before,1)
                self.assertEqual(result['work']['extracted_this_call'],1)
            before=len(paths);again=disc.scan(self.s,result['id'],1);self.assertEqual(len(paths),before)
        self.assertTrue(all(n==1 for n in Counter(paths).values()));self.assertEqual(set(paths),set(result['coverage']))
        self.assertEqual(again['work']['extracted_this_call'],0)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fixture(root)
            for i in range(20):(root/'Tests'/f'Extra{i:02}.cs').write_text(f'public class Extra{i:02} {{}}\n')
            other=upgraded(root);full=disc.scan(other,max_files=100)
            self.assertEqual(result['observations'],full['observations'])
            def records(s):return sorted([v['payload']['operations'] for v in s.export()['queue']],key=canonical_json)
            def semantic(operations):
                for ops in operations:
                    for op in ops:
                        if op['payload']:
                            op['payload'].pop('captured_at',None);op['payload'].pop('last_verified',None)
                return operations
            self.assertEqual(semantic(records(self.s)),semantic(records(other)))

    def test_b_imported_evidence_does_not_trigger_hidden_full_extraction(self):
        disc.scan(self.s,max_files=100);approve(self.s)
        (self.root/'Tests/New.cs').write_text('public class NewlyAdded {}\n')
        real=disc.extract
        with patch.object(disc,'extract',wraps=real) as observer:
            result=disc.scan(self.s,max_files=1);self.assertEqual(observer.call_count,1)
            self.assertFalse(result['complete']);self.assertTrue(result['impact']['direct_claims'])
            observer.reset_mock();disc.scan(self.s,result['id'],1);self.assertEqual(observer.call_count,1)

    def test_b_late_collision_withholds_first_and_drift_invalidates_resume(self):
        (self.root/'Tests/Independent.cs').write_text('public class Collision {}\n')
        (self.root/'Tests/ZCollision.cs').write_text('public class Collision : System.Object {}\n')
        real=disc.extract
        with patch.object(disc,'extract',wraps=real) as observer:
            result=disc.scan(self.s,max_files=1)
            while not result['complete']:
                self.assertFalse(self.s.export()['records']['claims'])
                self.assertFalse(self.s.status()['queue'])
                result=disc.scan(self.s,result['id'],1)
            self.assertEqual(observer.call_count,len(result['coverage']))
        self.assertFalse(any(o['subject']=='Collision' for o in result['observations']));self.assertTrue(result['ambiguous'])
        approve(self.s);self.assertFalse(self.s.context('Collision')['claims'])
        (self.root/'Tests/Another.cs').write_text('public class Another {}\n')
        with self.assertRaisesRegex(KnowledgeError,'stale-scan'):disc.scan(self.s,result['id'],1)
