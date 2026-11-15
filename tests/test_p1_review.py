"""Adversarial review cases beyond the original P1 happy-path fixtures."""
from pathlib import Path
import tempfile
import unittest
from knowledge import discovery as disc,lifecycle as life
from test_p1 import fixture,upgraded,approve


class FunctionalReviewTests(unittest.TestCase):
    def test_literals_are_not_declarations_or_registrations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fixture(root)
            (root/'Tests/Strings.cs').write_text('public class Real {\n string text = "public class Phantom {}";\n string raw = """services.AddScoped<IFake, Fake>();""";\n}\n')
            result=disc.scan(upgraded(root),max_files=100)
            self.assertNotIn('Phantom',[o['subject'] for o in result['observations']])
            self.assertFalse(any('IFake' in o['statement'] for o in result['observations']))

    def test_route_literal_preserves_slashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fixture(root)
            (root/'Api/Program.cs').write_text('app.MapGet("/files//archive", () => "ok");\n')
            result=disc.scan(upgraded(root),max_files=100)
            self.assertTrue(any(o['category']=='routing' and o['subject']=='/files//archive' for o in result['observations']))

    def test_commented_out_anchor_is_not_trusted_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fixture(root);s=upgraded(root);disc.scan(s,max_files=100);approve(s)
            path=root/'Tests/Independent.cs';path.write_text('/*\n'+path.read_text()+'*/\n')
            self.assertFalse(s.context('Independent')['claims'])

    def test_rename_reverification_preserves_reviewed_confidence_and_edges(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fixture(root);s=upgraded(root);r=disc.scan(s,max_files=100);approve(s)
            obs=next(o for o in r['observations'] if o['subject']=='Independent')
            c=s.lookup('claims',obs['id'])['record'];target=next(c for c in s.export()['records']['claims'] if c['id']!=obs['id'])
            c=dict(c,status='INFERRED',last_verified=None,depends_on=[target['id']])
            s.submit(life.batch([life.op('update','claims',c['id'],1,c)],'reviewed uncertainty and dependency'));approve(s)
            (root/'Tests/Independent.cs').rename(root/'Tests/Renamed.cs');disc.scan(s,max_files=100)
            proposed=[o['payload'] for q in s.export()['queue'] if q['status']=='pending' for o in q['payload'].get('operations',[]) if o['id']==c['id']][0]
            self.assertEqual(proposed['status'],'INFERRED');self.assertEqual(proposed['depends_on'],[target['id']]);approve(s)

    def test_xml_comments_are_not_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fixture(root)
            (root/'Core/Core.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk">\n<!-- <PackageReference Include="Phantom.Package" /> -->\n<PackageReference Include="Actual.Package" />\n</Project>\n')
            result=disc.scan(upgraded(root),max_files=100)
            self.assertFalse(any('Phantom.Package' in o['statement'] for o in result['observations']))
            self.assertTrue(any('Actual.Package' in o['statement'] for o in result['observations']))

    def test_legacy_extractor_false_positive_is_not_trusted_even_with_same_hash(self):
        import hashlib
        from fixtures import addition
        from knowledge.util import digest
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fixture(root);path=root/'Tests/Strings.cs';text='public class Real { string text = "public class Phantom {}"; }\n';path.write_text(text)
            s=upgraded(root);identifier='scan.'+digest(['Tests','declaration','Phantom'])[:32]
            value=addition(identifier,'Tests declares class Phantom.')
            value['records']['evidence'][0].update(source='Tests/Strings.cs',location='Tests/Strings.cs#L1',content_hash='sha256:'+hashlib.sha256(path.read_bytes()).hexdigest(),description=text.strip(),provenance={'actor':'deterministic-discovery','method':'dotnet-lexical-v1'})
            s.submit(value);approve(s)
            self.assertFalse(s.lookup('claims',identifier)['freshness']['trusted'])
            self.assertFalse(s.context('Phantom')['claims'])

    def test_evidence_cannot_read_through_linked_ancestor(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp,tempfile.TemporaryDirectory() as outside:
            root=Path(tmp);fixture(root);s=upgraded(root)
            external=Path(outside)/'Support.cs';external.write_text('public class External {}\n')
            (root/'linked').symlink_to(outside,target_is_directory=True)
            evidence={'source':'linked/Support.cs','content_hash':'sha256:'+hashlib.sha256(external.read_bytes()).hexdigest(),'provenance':{'method':'fixture'},'description':'synthetic'}
            self.assertEqual(disc.fresh_evidence(root,evidence),'not-verifiable')
