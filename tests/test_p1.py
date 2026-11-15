from datetime import timedelta
"""Portable P1 tests; all generated repositories and statements are synthetic."""
import asyncio
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from knowledge.store import Store, checkpoint
from knowledge import lifecycle as life, discovery as disc
from knowledge.util import KnowledgeError, canonical_json, loads
from fixtures import addition


def git(root,*args):
    return subprocess.check_output(['git','-C',str(root),*args],stderr=subprocess.DEVNULL,text=True).strip()


def fixture(root):
    for name in ('Core','Api','Tests'):
        d=root/name;d.mkdir()
        (d/(name+'.csproj')).write_text('<Project Sdk="Microsoft.NET.Sdk">\n<PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup>\n</Project>\n')
    (root/'Core/ExternalManagement.cs').write_text('public interface IExternalManagement {}\npublic class ExternalManagement : IExternalManagement {}\n')
    (root/'Api/Program.cs').write_text('services.AddScoped<IExternalManagement, ExternalManagement>();\napp.MapGet("/em", () => "EM");\nservices.AddDbContext<AppContext>();\n')
    (root/'Tests/Independent.cs').write_text('public class Independent {}\n')
    (root/'README.md').write_text('Synthetic fixture; not production or external deployment evidence.\n')
    (root/'Api/appsettings.json').write_text(json.dumps({'ExternalManagement':{'Endpoint':'https://synthetic.invalid/em'},'Independent':{'Label':'EM historical logs'}}))
    git(root,'init');git(root,'config','user.email','synthetic@example.invalid');git(root,'config','user.name','Synthetic')
    git(root,'add','.');git(root,'commit','-m','synthetic before')


def upgraded(root):
    s=Store(root);s.init();life.upgrade(s,life.upgrade_preview(s)['fingerprint']);return s


def approve(s):
    p=s.prepare();assert p['ok'],p
    s.apply(p['fingerprint'],p['fingerprint']);s.acknowledge(p['fingerprint']);return p['fingerprint']


class P1Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);fixture(self.root);self.s=upgraded(self.root)
    def tearDown(self):self.tmp.cleanup()
    def scan(self,**kwargs):return disc.scan(self.s,max_files=10000,**kwargs)

    def test_scan_resume_source_drift_and_idempotence(self):
        r=disc.scan(self.s,max_files=1);self.assertFalse(r['complete']);self.assertTrue(r['observations'])
        # Actual new process resumes durable observations, not an in-memory instance.
        p=subprocess.run([sys.executable,'-m','knowledge.cli','scan','--root',str(self.root),'--scan-id',r['id'],'--max-files','100'],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stdout);done=loads(p.stdout);self.assertTrue(done['complete'])
        count=len(self.s.status()['queue']);self.scan();self.assertEqual(len(self.s.status()['queue']),count)
        (self.root/'Api/New.cs').write_text('public class New {}')
        with self.assertRaisesRegex(KnowledgeError,'stale-scan'):disc.scan(self.s,r['id'])
        self.assertFalse(done['semantic_coverage_complete']);self.assertTrue(any(e['status']=='partial' for e in done['coverage'].values()))

    def test_removed_component_complete_pipeline(self):
        before=self.scan();approve(self.s)
        wiring=next(o for o in before['observations'] if o['category']=='wiring')
        declaration=next(o for o in before['observations'] if o['subject']=='ExternalManagement' and o['category']=='declaration')
        consumer=self.s.lookup('claims',wiring['id'])['record']
        relation=dict(id='synthetic.removal.dependency',type='depends_on',**{'from':consumer['id'],'to':declaration['id']},provenance={'actor':'synthetic','method':'reviewed fixture wiring'})
        self.s.submit(life.batch([life.op('update','claims',consumer['id'],1,dict(consumer,depends_on=[declaration['id']])),life.op('add','relationships',relation['id'],0,relation)],'Reviewed synthetic registration/declaration dependency'));approve(self.s)
        base=git(self.root,'rev-parse','HEAD')
        old={o['id'] for o in before['observations'] if o['path']=='Core/ExternalManagement.cs'}
        (self.root/'Core/ExternalManagement.cs').unlink()
        (self.root/'Api/appsettings.json').write_text('{}\n')
        (self.root/'Api/Program.cs').write_text('services.AddDbContext<AppContext>();\n')
        git(self.root,'add','-A');git(self.root,'commit','-m','synthetic complete removal')
        after=self.scan(base=base,head='HEAD');preview=disc.reconcile(self.s,after['id'])
        self.assertTrue(preview['proposal']);self.s.submit(preview['proposal']);p=approve(self.s)
        self.assertTrue(old)
        self.assertEqual(life.history(self.s,relation['id'])['revisions'][-1]['lifecycle'],'retired')
        for i in old:
            h=life.history(self.s,i)['revisions'];self.assertEqual(h[-1]['lifecycle'],'retired');self.assertEqual(len(h),2)
        self.assertFalse(any(c['id'] in old for c in self.s.context('ExternalManagement')['claims']))
        self.assertTrue(self.s.context('Independent')['claims'])
        self.assertEqual(self.s.apply(p,p)['result'],'already-committed')

    def test_update_old_ack_supersede_and_history(self):
        self.scan();old_plan=approve(self.s)
        c=next(c for c in self.s.export()['records']['claims'] if 'Independent' in c['statement'])
        change=dict(c,statement='Synthetic revised independent declaration.')
        successor=dict(c,id='synthetic.successor',statement='Synthetic explicit successor.')
        # Add evidence pointing to successor through an existing source-backed payload.
        e=dict(next(e for e in self.s.export()['records']['evidence'] if e['id']==c['evidence'][0]),id='synthetic.evidence',substantiates=[successor['id']])
        successor['evidence']=[e['id']]
        self.s.submit(life.batch([life.op('update','claims',c['id'],1,change)],'synthetic update'));approve(self.s)
        self.s.acknowledge(old_plan);self.s.apply(old_plan,old_plan)
        self.assertEqual(self.s.lookup('claims',c['id'])['record']['statement'],change['statement'])
        self.s.submit(life.batch([life.op('add','claims',successor['id'],0,successor),life.op('add','evidence',e['id'],0,e),life.op('supersede','claims',c['id'],2,successor=successor['id'])],'synthetic replacement'))
        approve(self.s);self.assertEqual(life.history(self.s,c['id'])['revisions'][-1]['lifecycle'],'superseded')
        self.assertNotIn(c['id'],[c['id'] for c in self.s.context('independent')['claims']])

    def test_disposition_and_valid_batch(self):
        self.scan();queue=self.s.status()['queue'];cid=queue[0]['id']
        life.dispose(self.s,cid,'deferred','human review required');self.scan()
        self.assertEqual(next(q for q in self.s.status()['queue'] if q['id']==cid)['status'],'deferred')
        self.assertNotIn(cid,self.s.prepare()['included']);approve(self.s)
        self.assertEqual(self.s.status()['reviews'][0]['reason'],'human review required')

    def test_stale_source_expected_approval_and_conflicting_ops(self):
        self.scan();p=self.s.prepare()['fingerprint'];(self.root/'Tests/New.cs').write_text('public class New {}')
        with self.assertRaisesRegex(KnowledgeError,'stale-plan'):self.s.apply(p,p)
        with self.assertRaisesRegex(KnowledgeError,'exact-approval'):self.s.apply(p,'wrong')
        self.assertFalse(self.s.export()['records']['claims'])
        with self.assertRaises(KnowledgeError):life.batch([life.op('delete','claims','missing',0)],'bad')

    def test_freshness_no_false_retirement_and_no_promotion(self):
        r=self.scan();approve(self.s);c=next(c for c in self.s.export()['records']['claims'] if 'Independent' in c['statement'])
        path=self.root/'Tests/Independent.cs';path.write_text('// unrelated\n'+path.read_text())
        self.assertTrue(disc.freshness(self.root,c,self.s.export()['records'])['trusted'])
        path.unlink();r=self.scan();rec=disc.reconcile(self.s,r['id'])
        self.assertIsNone(rec['proposal']);self.assertNotIn(c['id'],[c['id'] for c in self.s.context('Independent')['claims']])
        self.assertEqual(self.s.lookup('claims',c['id'])['record']['status'],'CONFIRMED')
        # External facts and historical/independent mentions never retire by text matching.
        a=addition('external.em','External EM was historically deployed.','INFERRED');self.s.submit(a);approve(self.s)
        r=self.scan();row=next(x for x in disc.reconcile(self.s,r['id'])['claims'] if x['id']=='external.em')
        self.assertEqual(row['classification'],'not-verifiable');self.assertFalse(row['retirement_proposed'])

    def test_nonempty_upgrade_preserves_pending_and_old_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);s=Store(root);s.init();s.submit(addition());p=s.prepare()['fingerprint'];s.apply(p,p)
            s.submit(addition('other','Other pending claim.'));before=s.export();preview=life.upgrade_preview(s)
            result=life.upgrade(s,preview['fingerprint']);self.assertTrue(Path(result['backup']).is_file());self.assertEqual({k:s.export()[k] for k in before},before)
            s.acknowledge(p);self.assertEqual(life.upgrade(s,life.upgrade_preview(s)['fingerprint'])['result'],'already-upgraded')
            with s.connection(True) as db:db.execute("UPDATE metadata SET value='unknown' WHERE key='p1'")
            with self.assertRaises(KnowledgeError):s.status()

    def test_graph_dependent_retirement_requires_reviewed_closure(self):
        self.scan();approve(self.s);records=self.s.export()['records'];a,b=records['claims'][:2]
        b=dict(b,depends_on=[a['id']]);rel=dict(id='synthetic.dep',type='depends_on',**{'from':b['id'],'to':a['id']},provenance={'actor':'synthetic','method':'fixture'})
        self.s.submit(life.batch([life.op('update','claims',b['id'],1,b),life.op('add','relationships',rel['id'],0,rel)],'dependency'));approve(self.s)
        x=self.s.submit(life.batch([life.op('retire','claims',a['id'],1)],'retirement'))
        self.assertFalse(self.s.prepare()['ok']);life.dispose(self.s,x['candidate'],'rejected','requires closure')
        self.s.submit(life.batch([life.op('retire','claims',a['id'],1),life.op('retire','claims',b['id'],2),life.op('retire','relationships',rel['id'],1)],'reviewed closure'));approve(self.s)
        self.assertEqual(life.history(self.s,rel['id'])['revisions'][-1]['lifecycle'],'retired')

    def test_real_crash_mixed_batch_and_pending_ack(self):
        self.scan();approve(self.s);claims=self.s.export()['records']['claims'][:2]
        ops=[life.op('update','claims',c['id'],1,dict(c,statement=c['statement']+' Revised.')) for c in claims]
        self.s.submit(life.batch(ops,'synthetic interrupted mixed update'));p=self.s.prepare()['fingerprint']
        for phase,expected in [('canonical-record-written',1),('after-canonical-commit',2)]:
            code="from knowledge import store;import os; s=store.Store("+repr(str(self.root))+");store.checkpoint=lambda phase:os._exit(73) if phase=="+repr(phase)+" else None;s.apply("+repr(p)+","+repr(p)+")"
            proc=subprocess.run([sys.executable,'-c',code]);self.assertEqual(proc.returncode,73)
            self.assertTrue(all(len(life.history(self.s,c['id'])['revisions'])==expected for c in claims))
        self.s.recover();self.s.apply(p,p);self.s.acknowledge(p)
        self.assertTrue(all(len(life.history(self.s,c['id'])['revisions'])==2 for c in claims))

    def test_incremental_rename_add_delete_dirty_and_range(self):
        self.scan();approve(self.s);base=git(self.root,'rev-parse','HEAD')
        (self.root/'Tests/Independent.cs').rename(self.root/'Tests/Renamed.cs')
        (self.root/'Tests/New.cs').write_text('public class NewThing {}\n')
        git(self.root,'add','-A');git(self.root,'commit','-m','synthetic rename addition')
        (self.root/'Api/Program.cs').write_text('app.MapGet("/new", () => "new");\n')
        r=self.scan(base=base,head='HEAD');self.assertIn('R100',r['snapshot']['delta']['committed']);self.assertEqual(r['snapshot']['snapshot_kind'],'working-tree-with-hashes')
        self.assertTrue(any(o['subject']=='NewThing' for o in r['observations']));self.assertTrue(r['snapshot']['dirty'])
        with self.assertRaises(KnowledgeError):self.scan(base='missing',head='HEAD')

    def test_lock_contention_and_upgrade_crash(self):
        with self.s.connection(True):
            with self.assertRaisesRegex(KnowledgeError,'store-busy'):life.dispose(self.s,'none','rejected','test')
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp);s.init();s.submit(addition());before=s.export();p=life.upgrade_preview(s)['fingerprint']
            code="from knowledge import store,lifecycle;import os;s=store.Store("+repr(tmp)+");store.checkpoint=lambda phase:os._exit(73) if phase=='before-commit' else None;lifecycle.upgrade(s,"+repr(p)+")"
            self.assertEqual(subprocess.run([sys.executable,'-c',code]).returncode,73)
            self.assertEqual({k:s.export()[k] for k in before},before);life.upgrade(s,p);self.assertEqual({k:s.export()[k] for k in before},before)

    def test_prepared_p0_approval_survives_upgrade(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp);s.init();s.submit(addition());p=s.prepare()['fingerprint']
            life.upgrade(s,life.upgrade_preview(s)['fingerprint']);s.apply(p,p);s.acknowledge(p)
            self.assertEqual(s.lookup('claims','synthetic.rule')['record']['statement'],addition()['records']['claims'][0]['statement'])

    def test_scan_interruption_preserves_completed_checkpoint(self):
        first=disc.scan(self.s,max_files=1)
        code="from knowledge import store,discovery;import os;s=store.Store("+repr(str(self.root))+");store.checkpoint=lambda phase:os._exit(73) if phase=='before-commit' else None;discovery.scan(s,"+repr(first['id'])+",100)"
        self.assertEqual(subprocess.run([sys.executable,'-c',code]).returncode,73)
        checkpoint=disc.status(self.s,first['id'])['scans'][0];self.assertEqual(checkpoint,{k:v for k,v in first.items() if k!='ok'})
        done=disc.scan(self.s,first['id'],100);self.assertTrue(done['complete']);self.assertEqual(len({o['id'] for o in done['observations']}),len(done['observations']))

    def test_mixed_add_update_retire_ack_crash_and_competing_approval(self):
        self.scan();approve(self.s);claims=self.s.export()['records']['claims'][:2];a,b=claims
        new=dict(a,id='synthetic.new',statement='Synthetic distinct new claim.')
        e=dict(next(e for e in self.s.export()['records']['evidence'] if e['id']==a['evidence'][0]),id='synthetic.new.evidence',substantiates=[new['id']]);new['evidence']=[e['id']]
        ops=[life.op('update','claims',a['id'],1,dict(a,statement=a['statement']+' revised')),life.op('retire','claims',b['id'],1),life.op('add','claims',new['id'],0,new),life.op('add','evidence',e['id'],0,e)]
        self.s.submit(life.batch(ops,'synthetic mixed actions'));p=self.s.prepare()['fingerprint']
        code="from knowledge import store;import os;s=store.Store("+repr(str(self.root))+");store.checkpoint=lambda phase:os._exit(73) if phase=='canonical-record-written' else None;s.apply("+repr(p)+","+repr(p)+")"
        self.assertEqual(subprocess.run([sys.executable,'-c',code]).returncode,73)
        self.assertEqual(self.s.lookup('claims',new['id'])['result'],'no-match');self.assertEqual(len(life.history(self.s,a['id'])['revisions']),1)
        # Two actual processes apply one exact plan. The loser may observe bounded contention or already committed.
        code="from knowledge import store;from knowledge.util import KnowledgeError;s=store.Store("+repr(str(self.root))+")\ntry: s.apply("+repr(p)+","+repr(p)+")\nexcept KnowledgeError as e:\n assert e.code=='store-busy-retry'"
        processes=[subprocess.Popen([sys.executable,'-c',code]) for _ in range(2)]
        self.assertEqual([p.wait() for p in processes],[0,0]);self.assertEqual(len(life.history(self.s,a['id'])['revisions']),2)
        code="from knowledge import store;import os;s=store.Store("+repr(str(self.root))+");store.checkpoint=lambda phase:os._exit(73) if phase=='acknowledgment-written' else None;s.acknowledge("+repr(p)+")"
        self.assertEqual(subprocess.run([sys.executable,'-c',code]).returncode,73);self.s.recover();self.s.acknowledge(p)
        self.assertEqual(self.s.lookup('claims',new['id'])['result'],'found')

    def test_incomplete_blocked_and_changed_evidence_refuse_absence(self):
        self.scan();approve(self.s);base=git(self.root,'rev-parse','HEAD')
        (self.root/'Core/ExternalManagement.cs').unlink();(self.root/'Api/Program.cs').write_text('')
        git(self.root,'add','-A');git(self.root,'commit','-m','synthetic removal')
        (self.root/'Tests/Huge.cs').write_text('x'*(disc.LIMIT+1))
        r=self.scan(base=base,head='HEAD');self.assertFalse(r['complete']);self.assertIsNone(disc.reconcile(self.s,r['id'])['proposal'])

    def test_rejected_proposal_remains_rejected_on_new_snapshot(self):
        self.scan();cid=self.s.status()['queue'][0]['id'];life.dispose(self.s,cid,'rejected','unsupported')
        n=len(self.s.status()['queue']);(self.root/'README.md').write_text('Unrelated new docs.')
        self.scan();self.assertEqual(len(self.s.status()['queue']),n)

class P1StdioTests(unittest.IsolatedAsyncioTestCase):
    async def test_active_history_unicode_budgets_and_isolation(self):
        from mcp import ClientSession,StdioServerParameters,stdio_client
        from harness.consumer import context
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fixture(root);s=upgraded(root);scan=disc.scan(s,max_files=10000);approve(s)
            c=next(c for c in s.export()['records']['claims'] if 'Independent' in c['statement'])
            update=dict(c,statement='Independent синтетический Unicode факт '+('Я'*400))
            s.submit(life.batch([life.op('update','claims',c['id'],1,update)],'synthetic Unicode'));approve(s)
            params=StdioServerParameters(command=sys.executable,args=['-m','knowledge.mcp','--root',str(root)])
            async with stdio_client(params) as (reader,writer):
                async with ClientSession(reader,writer,read_timeout_seconds=timedelta(seconds=20)) as session:
                    await session.initialize()
                    for budget in (256,600,16000):
                        response=await session.call_tool('knowledge_context',{'task':'Independent','max_bytes':budget})
                        self.assertFalse(response.structuredContent);self.assertLessEqual(len(response.content[0].text.encode()),budget)
                        self.assertEqual(loads(response.content[0].text),s.context('Independent',budget))
                        response=await session.call_tool('knowledge_get_claim',{'identifier':c['id'],'history':True,'max_bytes':budget})
                        self.assertFalse(response.structuredContent);self.assertLessEqual(len(response.content[0].text.encode()),budget)
                    response=await session.call_tool('knowledge_get_claim',{'identifier':c['id'],'history':True})
                    self.assertEqual(loads(response.content[0].text),life.history(s,c['id']))
                    response=await session.call_tool('knowledge_context',{'task':'Independent','max_bytes':-1})
                    self.assertFalse(loads(response.content[0].text)['ok'])
                    self.assertEqual(context(root,'Independent')['context']['claims'],s.context('Independent')['claims'])
                    s.submit(life.batch([life.op('retire','claims',c['id'],2)],'synthetic retire'));approve(s)
                    response=await session.call_tool('knowledge_context',{'task':'Independent'})
                    self.assertNotIn(c['id'],[r['id'] for r in loads(response.content[0].text)['claims']])
                    response=await session.call_tool('knowledge_get_claim',{'identifier':c['id'],'history':True})
                    self.assertEqual(loads(response.content[0].text)['revisions'][-1]['lifecycle'],'retired')

class HistoricalGraphTests(unittest.TestCase):
    def test_retired_edge_does_not_constrain_new_current_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fixture(root);s=upgraded(root);disc.scan(s,max_files=100);approve(s)
            a,b=s.export()['records']['claims'][:2];linked=dict(b,depends_on=[a['id']]);rel=dict(id='synthetic.relation',type='depends_on',**{'from':b['id'],'to':a['id']},provenance={'actor':'synthetic','method':'fixture'})
            s.submit(life.batch([life.op('update','claims',b['id'],1,linked),life.op('add','relationships',rel['id'],0,rel)],'synthetic link'));approve(s)
            s.submit(life.batch([life.op('update','claims',b['id'],2,b),life.op('retire','relationships',rel['id'],1),life.op('retire','claims',a['id'],1)],'retain independent dependent with reviewed edge removal'));approve(s)
            self.assertEqual(s.lookup('claims',b['id'])['record']['depends_on'],[])
            self.assertEqual(life.history(s,b['id'])['revisions'][1]['record']['depends_on'],[a['id']])
            self.assertEqual(life.history(s,rel['id'])['revisions'][-1]['lifecycle'],'retired')

class UpgradeLegacyTests(unittest.TestCase):
    def test_upgraded_migrated_p0_keeps_original_queue_and_migration_history(self):
        from fixtures import legacy_fixture
        from knowledge import migration
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);legacy_fixture(root);p=migration.preview(root);migration.apply(root,p['fingerprint']);s=Store(root);before=s.export()
            life.upgrade(s,life.upgrade_preview(s)['fingerprint']);after=s.export()
            self.assertEqual({k:after[k] for k in before},before)
            self.assertTrue(any(q['id']=='legacy-pending' for q in after['queue']))
            self.assertEqual(len(after['revisions']),sum(len(rs) for rs in before['records'].values()))

class CommandAdapterTests(unittest.TestCase):
    def test_three_actual_command_adapters_and_canonical_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fixture(root)
            def cli(command,*args):
                p=subprocess.run([sys.executable,'-m','knowledge.cli',command,'--root',str(root),*args],capture_output=True,text=True)
                self.assertEqual(p.returncode,0,p.stdout);return loads(p.stdout)
            start=cli('knowledge-init','--max-files','100');self.assertTrue(start['complete']);self.assertIn('reconciliation',start)
            s=Store(root);self.assertFalse(s.export()['records']['claims'])
            base=git(root,'rev-parse','HEAD');update=cli('knowledge-candidates-update','--base',base,'--head','HEAD','--max-files','100')
            self.assertTrue(update['complete']);preview=cli('knowledge-candidates-push');self.assertFalse(s.export()['records']['claims'])
            cli('knowledge-candidates-push','--plan',preview['fingerprint'],'--approve',preview['fingerprint']);cli('acknowledge','--plan',preview['fingerprint'])
            self.assertTrue(s.export()['records']['claims']);self.assertTrue(cli('context','--task','Independent')['claims'])

class SourceReverificationTests(unittest.TestCase):
    def test_automatic_same_id_revision_rename_and_config_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fixture(root);s=upgraded(root);r=disc.scan(s,max_files=100);approve(s)
            c=next(c for c in s.export()['records']['claims'] if 'Independent' in c['statement'])
            (root/'Tests/Independent.cs').write_text('public class Independent : System.Object {}\n')
            disc.scan(s,max_files=100);approve(s)
            versions=life.history(s,c['id'])['revisions'];self.assertEqual(len(versions),2);self.assertIn('System.Object',versions[-1]['record']['statement'])
            (root/'Tests/Independent.cs').rename(root/'Tests/Renamed.cs');disc.scan(s,max_files=100);approve(s)
            versions=life.history(s,c['id'])['revisions'];self.assertEqual(len(versions),3)
            self.assertEqual(s.lookup('claims',c['id'])['record']['status'],'CONFIRMED');self.assertTrue(s.lookup('claims',c['id'])['freshness']['trusted'])
            r=disc.scan(s,max_files=1);old=disc.LIMIT
            try:
                disc.LIMIT=old+1
                with self.assertRaisesRegex(KnowledgeError,'stale-scan'):disc.scan(s,r['id'])
            finally:disc.LIMIT=old

    def test_still_valid_independent_em_mention_survives_removal(self):
        from knowledge.util import fingerprint
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fixture(root)
            independent=root/'Tests/Independent.cs';independent.write_text('public class Independent { public string Label => "EM historical logs"; }\n')
            git(root,'add','-A');git(root,'commit','-m','synthetic independent EM label')
            s=upgraded(root);before=disc.scan(s,max_files=100);approve(s);base=git(root,'rev-parse','HEAD')
            # A separately reviewed statement mentioning EM is grounded in a stable independent source.
            a=addition('synthetic.em.history','Independent formatter labels historical EM logs.')
            e=a['records']['evidence'][0];e.update(source='Tests/Independent.cs',location='Tests/Independent.cs#L1',content_hash='sha256:'+__import__('hashlib').sha256(independent.read_bytes()).hexdigest())
            s.submit(a);approve(s)
            (root/'Core/ExternalManagement.cs').unlink();(root/'Api/appsettings.json').write_text('{}\n');(root/'Api/Program.cs').write_text('services.AddDbContext<AppContext>();\n')
            git(root,'add','-A');git(root,'commit','-m','synthetic component removal')
            after=disc.scan(s,max_files=100,base=base,head='HEAD');rec=disc.reconcile(s,after['id']);self.assertTrue(rec['proposal'])
            self.assertNotIn('synthetic.em.history',[o['id'] for o in rec['proposal']['operations']]);s.submit(rec['proposal']);approve(s)
            self.assertIn('synthetic.em.history',[c['id'] for c in s.context('historical EM logs')['claims']])

class ConcurrentSourceTests(unittest.TestCase):
    def test_source_drift_during_apply_rolls_back_knowledge_only(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fixture(root);s=upgraded(root);disc.scan(s,max_files=100);p=s.prepare()['fingerprint']
            source=root/'Tests/Independent.cs'
            def mutate(phase):
                if phase=='canonical-record-written':source.write_text('public class ConcurrentEdit {}\n')
            with patch('knowledge.store.checkpoint',mutate):
                with self.assertRaisesRegex(KnowledgeError,'source-drift-before-commit'):s.apply(p,p)
            self.assertEqual(s.export()['records']['claims'],[])
            self.assertEqual(source.read_text(),'public class ConcurrentEdit {}\n')
            self.assertTrue(all(q['status']=='pending' for q in s.status()['queue']))

class SuccessorIntegrityTests(unittest.TestCase):
    def test_successor_requires_claim_and_historical_chains_remain_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fixture(root);s=upgraded(root);disc.scan(s,max_files=100);approve(s)
            a,b,c=s.export()['records']['claims'][:3]
            rejected=s.submit(life.batch([life.op('supersede','claims',a['id'],1,successor=a['evidence'][0])],'invalid evidence successor'))
            self.assertFalse(s.prepare()['ok']);life.dispose(s,rejected['candidate'],'rejected','successor must be a claim')
            s.submit(life.batch([life.op('supersede','claims',a['id'],1,successor=b['id'])],'first successor'));approve(s)
            s.submit(life.batch([life.op('supersede','claims',b['id'],1,successor=c['id'])],'later successor'));approve(s)
            self.assertEqual(life.history(s,a['id'])['revisions'][-1]['successor'],b['id'])
            self.assertEqual(life.history(s,b['id'])['revisions'][-1]['successor'],c['id']);self.assertTrue(s.validate()['ok'])
            s.submit(life.batch([life.op('supersede','claims',c['id'],1,successor=a['id'])],'invalid successor cycle'))
            self.assertFalse(s.prepare()['ok'])
