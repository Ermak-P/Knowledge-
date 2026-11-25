"""Producer identity and evidence regressions on synthetic, public fixtures."""
import tempfile
import unittest
import sys,contextlib
from pathlib import Path
from unittest.mock import patch
from knowledge import discovery, lifecycle as life
from knowledge.store import Store
from knowledge.persistence_identity import LEGACY,identifier
from knowledge.util import canonical_json,digest


class PersistenceRecovery(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.store=Store(self.root);self.store.init()
        life.upgrade(self.store,life.upgrade_preview(self.store)['fingerprint'])

    def sources(self):
        (self.root/'P.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"/>')
        for name in ('A','B'):
            (self.root/(name+'.cs')).write_text('GetConnectionString("db");\nUseSqlServer("db");\nGetConnectionString("other");\n')

    def test_project_presence_all_occurrences_apply_and_future_scan(self):
        self.sources();state=discovery.scan(self.store,max_files=100)
        observations=[o for o in state['observations'] if o['category']=='persistence']
        self.assertEqual(len(observations),2)
        self.assertEqual(sorted(len(o['occurrences']) for o in observations),[2,4])
        before=self.store.export()['records'];plan=self.store.prepare();self.assertTrue(plan['ok'],plan['blocked'])
        self.assertEqual(before,self.store.export()['records'])
        self.store.apply(plan['fingerprint'],plan['fingerprint']);self.store.acknowledge(plan['fingerprint'])
        records=self.store.export()['records'];claims=[c for c in records['claims'] if 'persistence/configuration' in c['statement']]
        self.assertEqual(sorted(len(c['evidence']) for c in claims),[2,4])
        proof={e['id']:e for e in records['evidence']}
        for c in claims:
            self.assertTrue(discovery.freshness(self.root,c,records)['trusted'])
            self.assertEqual({proof[i]['source'] for i in c['evidence']},{'A.cs','B.cs'})
        (self.root/'C.cs').write_text('GetConnectionString("third");')
        again=discovery.scan(self.store,max_files=100);plan=self.store.prepare();self.assertTrue(plan['ok'],plan['blocked'])
        self.store.apply(plan['fingerprint'],plan['fingerprint']);self.store.acknowledge(plan['fingerprint'])
        updated=self.store.export()['records'];self.assertEqual({c['id'] for c in claims},{c['id'] for c in updated['claims'] if 'persistence/configuration' in c['statement']})
        self.assertEqual(max(len(c['evidence']) for c in updated['claims']),5)

    def test_methods_generic_arguments_and_same_display_project_names(self):
        for directory in ('One','Two'):
            path=self.root/directory;path.mkdir();(path/'P.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"/>')
            (path/'A.cs').write_text('AddDbContext<One>();\nAddDbContext<Two>();\nUseSqlite();\nUseSqlServer();\nGetConnectionString("db");')
        state=discovery.scan(self.store,max_files=100);items=[o for o in state['observations'] if o['category']=='persistence']
        self.assertEqual(len(items),10);self.assertEqual(len({o['id'] for o in items}),10);self.assertEqual(len({o['statement'] for o in items}),10)

    def legacy_scan(self):
        original=discovery.extract
        def old(root,path,entry):
            entry['_identity_policy']=LEGACY
            return original(root,path,entry)
        original_proposal=discovery.proposal
        def old_proposal(store,db,obs,*args,**kwargs):
            return original_proposal(store,db,{k:v for k,v in obs.items() if k!='occurrences'},*args,**kwargs)
        with patch.object(discovery,'extract',old),patch.object(discovery,'proposal',old_proposal):return discovery.scan(self.store,max_files=100)

    def test_legacy_gapped_queue_recovery_keeps_artifacts_and_evidence(self):
        self.sources();(self.root/'broken.json').write_text('{invalid')
        state=self.legacy_scan();self.assertEqual(state['state'],'COMPLETED_WITH_GAPS')
        with self.store.connection() as db:
            original_scans=list(db.execute('SELECT * FROM scans'));original_queue=list(db.execute('SELECT * FROM queue'))
        discovery.completed_artifact(self.store,state['id'])
        before=self.store.export()['records']
        with patch.object(discovery,'extract',side_effect=AssertionError('full extraction forbidden')):
            plan=self.store.prepare();self.assertTrue(plan['ok'],plan['blocked']);self.assertEqual(plan,self.store.prepare())
        counts=plan['deduplication']['counts'];self.assertEqual(counts['exact_duplicate_statement_groups'],2);self.assertEqual(counts['redundant_claim_records'],2)
        self.assertEqual(before,self.store.export()['records'])
        with self.store.connection() as db:
            self.assertEqual(original_scans,list(db.execute('SELECT * FROM scans')));self.assertEqual(original_queue,list(db.execute('SELECT * FROM queue')))
        self.store.apply(plan['fingerprint'],plan['fingerprint']);self.store.acknowledge(plan['fingerprint'])
        records=self.store.export()['records'];claims=[c for c in records['claims'] if 'persistence/configuration' in c['statement']]
        self.assertEqual({c['id'] for c in claims},{identifier('P.csproj','GetConnectionString',None),identifier('P.csproj','UseSqlServer',None)})
        # Legacy producer omitted repeated lines; persisted occurrences restore them.
        self.assertEqual(sorted(len(c['evidence']) for c in claims),[2,4])
        self.assertTrue(all(e['substantiates']==[c['id']] for c in claims for e in records['evidence'] if e['id'] in c['evidence']))
        self.store.apply(plan['fingerprint'],plan['fingerprint']);self.assertEqual(records,self.store.export()['records'])

    def test_legacy_canonical_id_retained_when_new_file_added(self):
        (self.root/'P.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"/>');(self.root/'A.cs').write_text('GetConnectionString("db");')
        state=self.legacy_scan();old=next(o['id'] for o in state['observations'] if o['category']=='persistence')
        # Install a historical approval using the original identity; fixture only.
        with patch('knowledge.persistence_identity.preferences',return_value={}):
            plan=self.store.prepare();self.store.apply(plan['fingerprint'],plan['fingerprint']);self.store.acknowledge(plan['fingerprint'])
        (self.root/'B.cs').write_text('GetConnectionString("other");')
        discovery.scan(self.store,max_files=100);plan=self.store.prepare();self.assertTrue(plan['ok'],plan['blocked'])
        self.store.apply(plan['fingerprint'],plan['fingerprint']);self.store.acknowledge(plan['fingerprint'])
        records=self.store.export()['records'];claims=[c for c in records['claims'] if 'persistence/configuration' in c['statement']]
        self.assertEqual([c['id'] for c in claims],[old]);self.assertEqual(len(claims[0]['evidence']),2)
        self.assertTrue(discovery.freshness(self.root,claims[0],records)['trusted'])

    def test_interrupted_prepare_is_rolled_back_and_retry_is_stable(self):
        self.sources();self.legacy_scan()
        before=self.store.export()['records']
        original=self.store._preview
        def interrupt(*args,**kwargs):
            original(*args,**kwargs);raise RuntimeError('simulated interruption')
        with patch.object(self.store,'_preview',interrupt):
            with self.assertRaises(RuntimeError):self.store.prepare()
        self.assertEqual(before,self.store.export()['records']);self.assertEqual(self.store.prepare(),self.store.prepare())


    def test_interrupted_prepare_rolls_back_and_can_be_repeated(self):
        self.sources();self.legacy_scan();original=self.store.connection
        @contextlib.contextmanager
        def interrupted(*args,**kwargs):
            with original(*args,**kwargs) as db:
                class Proxy:
                    def __getattr__(self,name):return getattr(db,name)
                    def execute(self,sql,*args):
                        result=db.execute(sql,*args)
                        if sql.startswith('INSERT OR IGNORE INTO plans'):raise RuntimeError('synthetic interruption after plan write')
                        return result
                yield Proxy()
        with original() as db:saved=list(db.execute('SELECT * FROM plans'))
        with patch.object(self.store,'connection',interrupted),self.assertRaisesRegex(RuntimeError,'synthetic interruption'):self.store.prepare()
        with original() as db:self.assertEqual(saved,list(db.execute('SELECT * FROM plans')))
        self.assertTrue(self.store.prepare()['ok']);self.assertFalse(self.store.export()['records']['claims'])

    def test_identity_collisions_remain_ambiguous_without_unrelated_id_changes(self):
        (self.root/'A.cs').write_text('class Same {}\nAddScoped<IService, First>();\nAddSingleton<IService, Second>();')
        (self.root/'B.cs').write_text('class Same {}')
        state=discovery.scan(self.store,max_files=1)
        while state['work']['remaining_files']:state=discovery.scan(self.store,state['id'],max_files=1)
        self.assertEqual(len(state['ambiguous']),2);self.assertFalse(state['observations'])
        self.assertFalse(self.store.prepare()['included'])

    def test_real_mcp_rebuild_diagnostics_candidate_detail_and_exact_approval(self):
        from test_machine_commands import fixture
        from core_wire import Wire
        with tempfile.TemporaryDirectory() as tmp:
            installation,root=fixture(tmp,0);self.root=root;self.store=Store(root);self.store.init();life.upgrade(self.store,life.upgrade_preview(self.store)['fingerprint'])
            self.sources();state=self.legacy_scan();before=self.store.export()['records']
            peer=Wire([sys.executable,'-I','-B','-m','knowledge.machine_mcp','--installation',installation],roots=lambda:[root])
            try:
                peer.initialize();caps=peer.tool('knowledge_capabilities');self.assertIn('rebuild',caps['candidate_actions'])
                preview=peer.tool('knowledge_plan',action='rebuild',scan_id=state['id']);self.assertTrue(preview['ok'],preview)
                groups=peer.tool('knowledge_scan_diagnostics',section='duplicates',limit=2,max_bytes=4096)
                self.assertEqual(groups['counts']['redundant_claim_records'],2)
                group=groups['rows'][0]['group'];members=peer.tool('knowledge_scan_diagnostics',section='duplicates',group=group,limit=2)
                self.assertTrue(members['rows']);cid=members['rows'][0]['candidate']
                detail=peer.tool('knowledge_scan_diagnostics',section='candidate',candidate=cid,max_bytes=2048)
                self.assertTrue(detail['ok']);self.assertTrue(detail['text']);self.assertIn('record_hash',detail)
                self.assertEqual(before,self.store.export()['records'])
                self.assertFalse(peer.tool('knowledge_plan',action='apply',approve='sha256:'+'0'*64)['ok'])
                applied=peer.tool('knowledge_plan',action='apply',approve=preview['fingerprint']);self.assertTrue(applied['ok'],applied)
                self.assertTrue(self.store.export()['records']['claims'])
            finally:peer.close()


if __name__=='__main__':unittest.main()
