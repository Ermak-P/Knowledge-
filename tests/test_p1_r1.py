"""Independent review R1–R5 reproductions. All projects/statements are synthetic."""
from pathlib import Path
import tempfile
import unittest
from knowledge import discovery as disc,lifecycle as life
from knowledge.util import KnowledgeError,digest
from test_p1 import fixture,upgraded,approve,git


class ReviewCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);fixture(self.root)
        (self.root/'Tests/Independent.cs').write_text('public class UniqueDeclared {}\n')
        git(self.root,'add','-A');git(self.root,'commit','-m','synthetic committed unique declaration')
        self.s=upgraded(self.root)
    def tearDown(self):self.tmp.cleanup()
    def initial(self):
        scan=disc.scan(self.s,max_files=100);approve(self.s)
        return next(o for o in scan['observations'] if o['subject']=='UniqueDeclared')['id'],git(self.root,'rev-parse','HEAD')
    def after(self,base):
        git(self.root,'add','-A');git(self.root,'commit','-m','synthetic after')
        return disc.scan(self.s,max_files=100,base=base,head='HEAD')
    def retire(self):
        identifier,base=self.initial();(self.root/'Tests/Independent.cs').unlink();scan=self.after(base)
        rec=disc.reconcile(self.s,scan['id']);self.assertTrue(rec['proposal']);self.s.submit(rec['proposal']);pid=approve(self.s)
        return identifier,pid

    def test_r1_excluded_live_build_source_cannot_prove_removal(self):
        identifier,base=self.initial();directory=self.root/'Tests/build';directory.mkdir();(self.root/'Tests/Independent.cs').rename(directory/'Independent.cs')
        scan=self.after(base);rec=disc.reconcile(self.s,scan['id'])
        self.assertTrue(scan['complete']);self.assertIsNone(rec['proposal'])
        row=next(r for r in rec['claims'] if r['id']==identifier)
        self.assertEqual(row['classification'],'not-verifiable');self.assertTrue(row['coverage_gaps'])

    def test_r1_unsupported_source_and_links_are_not_negative_evidence(self):
        identifier,base=self.initial();(self.root/'Tests/Independent.cs').unlink()
        (self.root/'Tests/Existing.vb').write_text('Public Class UniqueDeclared\nEnd Class\n')
        rec=disc.reconcile(self.s,self.after(base)['id']);self.assertIsNone(rec['proposal'])
        self.assertTrue(rec['negative_evidence_gaps'])

    def test_r2_same_id_historical_revision_is_not_retired(self):
        identifier,base=self.initial();claim=self.s.lookup('claims',identifier)['record']
        historical=dict(claim,statement='UniqueDeclared was declared in Tests in the recorded earlier source snapshot.',provenance={'actor':'human-reviewer','method':'reviewed-historical-statement'})
        self.s.submit(life.batch([life.op('update','claims',identifier,1,historical)],'reviewed history'));approve(self.s)
        (self.root/'Tests/Independent.cs').unlink();rec=disc.reconcile(self.s,self.after(base)['id'])
        self.assertFalse(any(op['id']==identifier for op in (rec['proposal'] or {}).get('operations',[])))
        self.assertEqual(self.s.lookup('claims',identifier)['record'],historical)
        self.assertEqual(len(life.history(self.s,identifier)['revisions']),2)

    def test_r2_changed_statement_with_retained_extractor_method_also_abstains(self):
        identifier,base=self.initial();claim=self.s.lookup('claims',identifier)['record']
        self.s.submit(life.batch([life.op('update','claims',identifier,1,dict(claim,statement='Reviewed assertion with a different meaning.'))],'reviewed meaning'));approve(self.s)
        (self.root/'Tests/Independent.cs').unlink();rec=disc.reconcile(self.s,self.after(base)['id']);self.assertIsNone(rec['proposal'])

    def test_r3_namespaces_do_not_collapse_and_removal_does_not_transfer_history(self):
        (self.root/'Tests/Independent.cs').write_text('namespace A { public class Independent : System.Exception {} }\n')
        (self.root/'Tests/Other.cs').write_text('namespace B { public class Independent : System.Object {} }\n')
        first=disc.scan(self.s,max_files=1)
        done=disc.scan(self.s,first['id'],100);approve(self.s)
        types=[o for o in done['observations'] if o['subject']=='Independent']
        self.assertEqual(len(types),2);self.assertEqual(len({o['id'] for o in types}),2)
        a=next(o for o in types if 'A.Independent' in o['statement']);b=next(o for o in types if 'B.Independent' in o['statement'])
        self.assertTrue(self.s.lookup('claims',a['id'])['freshness']['trusted'])
        (self.root/'Tests/Independent.cs').unlink();disc.scan(self.s,max_files=100);approve(self.s)
        self.assertFalse(self.s.lookup('claims',a['id'])['freshness']['trusted'])
        self.assertEqual(len(life.history(self.s,a['id'])['revisions']),1)
        self.assertIn('B.Independent',self.s.lookup('claims',b['id'])['record']['statement'])

    def test_r3_same_named_projects_have_distinct_ids_and_statements(self):
        for directory in ('One','Two'):
            project=self.root/directory;project.mkdir();(project/'Shared.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk" />\n')
            (project/'Type.cs').write_text('namespace N; public class Same {}\n')
        scan=disc.scan(self.s,max_files=100);approve(self.s)
        types=[o for o in scan['observations'] if o['subject']=='Same'];self.assertEqual(len(types),2)
        self.assertEqual(len({o['id'] for o in types}),2)
        self.assertTrue(all(self.s.lookup('claims',o['id'])['freshness']['trusted'] for o in types))

    def test_r3_partial_and_same_scope_collision_abstain_after_import(self):
        identifier,_=self.initial()
        (self.root/'Tests/Other.cs').write_text('public class UniqueDeclared : System.Object {}\n')
        scan=disc.scan(self.s,max_files=100)
        self.assertIn(identifier,scan['ambiguous']);self.assertNotIn(identifier,[o['id'] for o in scan['observations']])
        self.assertFalse(self.s.lookup('claims',identifier)['freshness']['trusted'])
        self.assertEqual(len(life.history(self.s,identifier)['revisions']),1)
        # Different namespace types are supported; partial declarations are explicitly withheld.
        (self.root/'Tests/Partial.cs').write_text('public partial class PartialThing {}\n')
        scan=disc.scan(self.s,max_files=100);self.assertFalse(any(o['subject']=='PartialThing' for o in scan['observations']))

    def test_r3_nested_identity_and_legacy_store_compatibility(self):
        (self.root/'Tests/Types.cs').write_text('namespace A; public class Outer { public class Inner {} }\npublic class Other { public class Inner {} }\n')
        scan=disc.scan(self.s,max_files=100)
        nested=[o for o in scan['observations'] if o['subject']=='Inner'];self.assertEqual(len(nested),2);self.assertEqual(len({o['id'] for o in nested}),2)
        approve(self.s)
        # Existing v2 payload/history is retained, not reassigned to a v3 entity.
        from fixtures import addition
        import hashlib
        identifier='scan.'+digest(['Tests','declaration','LegacyOnly'])[:32]
        path=self.root/'Tests/Legacy.cs';path.write_text('public class LegacyOnly {}\n')
        old=addition(identifier,'Tests declares class LegacyOnly.')
        old['records']['claims'][0]['provenance']={'actor':'deterministic-discovery','method':'dotnet-lexical-v2'}
        old['records']['evidence'][0].update(source='Tests/Legacy.cs',location='Tests/Legacy.cs#L1',description='public class LegacyOnly {}',content_hash='sha256:'+hashlib.sha256(path.read_bytes()).hexdigest(),provenance={'actor':'deterministic-discovery','method':'dotnet-lexical-v2'})
        self.s.submit(old);approve(self.s);before=life.history(self.s,identifier)
        scan=disc.scan(self.s,max_files=100)
        self.assertEqual(life.history(self.s,identifier),before);self.assertFalse(self.s.lookup('claims',identifier)['freshness']['trusted'])
        self.assertTrue(any(identifier in item['legacy_ids'] for item in scan['compatibility']))

    def test_r4_returned_entity_requires_new_approval_and_preserves_history(self):
        identifier,oldpid=self.retire();(self.root/'Tests/Independent.cs').write_text('public class UniqueDeclared {}\n')
        disc.scan(self.s,max_files=100);p=self.s.prepare();self.assertTrue(p['ok'])
        operations=[o for v in p['candidates'].values() for o in v['operations']]
        self.assertTrue(any(o['id']==identifier and o['action']=='reactivate' for o in operations))
        self.assertEqual(life.history(self.s,identifier)['revisions'][-1]['lifecycle'],'retired')
        self.s.apply(p['fingerprint'],p['fingerprint']);self.s.acknowledge(p['fingerprint'])
        self.s.apply(oldpid,oldpid);self.s.acknowledge(oldpid)
        self.assertEqual([v['lifecycle'] for v in life.history(self.s,identifier)['revisions']],['active','retired','active'])
        self.assertTrue(self.s.lookup('claims',identifier)['freshness']['trusted'])

    def test_r4_rejected_return_and_source_drift_are_not_silently_replayed(self):
        identifier,_=self.retire();(self.root/'Tests/Independent.cs').write_text('public class UniqueDeclared {}\n');disc.scan(self.s,max_files=100)
        cid=next(q['id'] for q in self.s.status()['queue'] if q['status']=='pending');life.dispose(self.s,cid,'deferred','review return')
        (self.root/'README.md').write_text('unrelated docs');disc.scan(self.s,max_files=100)
        self.assertEqual(len([q for q in self.s.status()['queue'] if q['status']=='deferred']),1)
        life.dispose(self.s,cid,'pending','review resumed');p=self.s.prepare()['fingerprint']
        # Source drift since the deferred proposal forces rescan/new review, never reuses old authority.
        with self.assertRaises(KnowledgeError):self.s.apply(p,p)
        self.assertEqual(life.history(self.s,identifier)['revisions'][-1]['lifecycle'],'retired')

    def test_r5_ignored_source_is_not_labeled_committed(self):
        (self.root/'.gitignore').write_text('Tests/Ignored.cs\n');git(self.root,'add','.gitignore');git(self.root,'commit','-m','synthetic ignore rule')
        (self.root/'Tests/Ignored.cs').write_text('public class IgnoredYetCompiled {}\n')
        scan=disc.scan(self.s,max_files=100);self.assertEqual(scan['snapshot']['snapshot_kind'],'working-tree-with-hashes')
        self.assertEqual(scan['snapshot']['files']['Tests/Ignored.cs']['git_state'],'ignored')
        self.assertTrue(any(d['path']=='Tests/Ignored.cs' and d['status']=='!!' for d in scan['snapshot']['dirty']))
        self.assertTrue(any(o['subject']=='IgnoredYetCompiled' for o in scan['observations']))
        self.assertTrue(all(v['source']['kind']=='working-tree-with-hashes' for v in self.s.prepare()['candidates'].values()))

    def test_r4_reactivation_approval_is_bound_to_current_source(self):
        identifier,_=self.retire();(self.root/'Tests/Independent.cs').write_text('public class UniqueDeclared {}\n');disc.scan(self.s,max_files=100)
        plan=self.s.prepare();self.assertTrue(plan['ok']);pid=plan['fingerprint']
        with self.assertRaises(KnowledgeError):self.s.apply(pid,'sha256:'+'0'*64)
        (self.root/'Tests/Independent.cs').write_text('public class UniqueDeclared : System.Object {}\n')
        with self.assertRaises(KnowledgeError):self.s.apply(pid,pid)
        self.assertEqual(life.history(self.s,identifier)['revisions'][-1]['lifecycle'],'retired')

    def test_r4_return_reports_retired_edges_without_silently_restoring_them(self):
        identifier,base=self.initial();claim=self.s.lookup('claims',identifier)['record']
        target=next(c for c in self.s.export()['records']['claims'] if c['id']!=identifier)
        relation=dict(id='synthetic.return.edge',type='depends_on',**{'from':identifier,'to':target['id']},provenance={'actor':'synthetic','method':'fixture'})
        self.s.submit(life.batch([life.op('update','claims',identifier,1,dict(claim,depends_on=[target['id']])),life.op('add','relationships',relation['id'],0,relation)],'reviewed dependency'));approve(self.s)
        (self.root/'Tests/Independent.cs').unlink();scan=self.after(base);self.s.submit(disc.reconcile(self.s,scan['id'])['proposal']);approve(self.s)
        (self.root/'Tests/Independent.cs').write_text('public class UniqueDeclared {}\n');scan=disc.scan(self.s,max_files=100)
        self.assertTrue(any(relation['id'] in item['relationships'] for item in scan['reintroductions']))
        approve(self.s);self.assertEqual(life.history(self.s,relation['id'])['revisions'][-1]['lifecycle'],'retired')

    def test_r3_same_directory_project_ownership_is_explicitly_unsupported(self):
        (self.root/'Tests/Second.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk" />\n')
        scan=disc.scan(self.s,max_files=100)
        self.assertFalse(any(o['subject']=='UniqueDeclared' for o in scan['observations']))
        self.assertTrue(scan['gaps'])

    def test_r3_identical_non_entity_occurrences_merge_only_the_same_assertion(self):
        (self.root/'Api/Program.cs').write_text('services.AddDbContext<Context>();\nservices.AddDbContext<Context>();\n')
        scan=disc.scan(self.s,max_files=100);facts=[o for o in scan['observations'] if o['category']=='persistence']
        self.assertEqual(len(facts),1);self.assertEqual(len(facts[0]['occurrences']),2);approve(self.s)
        self.assertTrue(self.s.lookup('claims',facts[0]['id'])['freshness']['trusted'])

    def test_r3_unicode_namespaces_do_not_fall_back_to_short_identity(self):
        (self.root/'Tests/Independent.cs').write_text('namespace Первый; public class Same {}\n')
        (self.root/'Tests/Other.cs').write_text('namespace Второй; public class Same {}\n')
        scan=disc.scan(self.s,max_files=100);facts=[o for o in scan['observations'] if o['subject']=='Same']
        self.assertEqual(len(facts),2);self.assertEqual(len({o['id'] for o in facts}),2);approve(self.s)
        self.assertTrue(all(self.s.lookup('claims',o['id'])['freshness']['trusted'] for o in facts))

    def test_r3_unsupported_namespace_and_record_forms_abstain(self):
        (self.root/'Tests/Other.cs').write_text('namespace @class; public class Unresolved {}\n')
        (self.root/'Tests/Record.cs').write_text('public record struct RecordValue(int Value);\n')
        scan=disc.scan(self.s,max_files=100)
        self.assertFalse(any(o['path'] in ('Tests/Other.cs','Tests/Record.cs') for o in scan['observations']))
        self.assertTrue(scan['gaps'])

    def test_r1_custom_compile_include_cannot_hide_live_source_in_another_project(self):
        identifier,base=self.initial()
        destination=self.root/'Api/build';destination.mkdir();(self.root/'Tests/Independent.cs').rename(destination/'Shared.cs')
        (self.root/'Tests/Tests.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk">\n<ItemGroup><Compile Include="../Api/build/Shared.cs" /></ItemGroup>\n</Project>\n')
        scan=self.after(base);rec=disc.reconcile(self.s,scan['id'])
        self.assertFalse(any(op['id']==identifier for op in (rec['proposal'] or {}).get('operations',[])))
        self.assertTrue(any(g['project']=='Tests/Tests.csproj' and 'custom source' in g['reason'] for g in rec['negative_evidence_gaps']))
