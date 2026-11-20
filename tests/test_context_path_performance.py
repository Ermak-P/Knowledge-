"""Regression coverage for context metadata work and unchanged trust boundaries."""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import os
import stat
import tempfile
import unittest
from unittest.mock import patch

from knowledge import discovery, lifecycle, project
from knowledge.store import Store
from knowledge.util import KnowledgeError
from fixtures import addition
from test_p1 import approve, upgraded


class ContextPathPerformanceTests(unittest.TestCase):
    def test_safe_path_reads_each_component_once_without_a_persistent_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);target=root/'a'/'b'/'file.cs'
            target.parent.mkdir(parents=True);target.write_text('public class File {}')
            original=Path.lstat;calls=[]
            def observed(path,*args,**kwargs):
                calls.append(path);return original(path,*args,**kwargs)
            with patch.object(Path,'lstat',observed):
                project.safe_path(target)
            expected=[target,*target.parents]
            self.assertEqual(calls,expected)
            calls.clear()
            with patch.object(Path,'lstat',observed):
                project.safe_path(target)
            self.assertEqual(calls,expected)

    def test_missing_target_below_link_and_broken_link_still_rejected(self):
        with tempfile.TemporaryDirectory() as tmp,tempfile.TemporaryDirectory() as other:
            root=Path(tmp);outside=Path(other)
            try:
                (root/'link').symlink_to(outside,target_is_directory=True)
                (root/'broken').symlink_to(outside/'missing',target_is_directory=True)
            except OSError as e:
                self.skipTest('Platform does not permit creating test symlinks: '+str(e))
            for target in (root/'link'/'missing.cs',root/'broken',root/'broken'/'missing.cs'):
                with self.subTest(path=target),self.assertRaisesRegex(KnowledgeError,'linked-path'):
                    project.safe_path(target)

    def test_hardlinks_and_special_objects_still_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'file.cs';source.write_text('source')
            os.link(source,root/'hard.cs')
            with self.assertRaisesRegex(KnowledgeError,'unsafe-filesystem-object'):
                project.safe_path(root/'hard.cs')
            if hasattr(os,'mkfifo'):
                os.mkfifo(root/'pipe')
                with self.assertRaisesRegex(KnowledgeError,'unsafe-filesystem-object'):
                    project.safe_path(root/'pipe')

    def test_new_link_is_detected_on_the_next_call(self):
        with tempfile.TemporaryDirectory() as tmp,tempfile.TemporaryDirectory() as other:
            root=Path(tmp);directory=root/'dir';directory.mkdir()
            project.safe_path(directory/'new.cs');directory.rmdir()
            try:directory.symlink_to(other,target_is_directory=True)
            except OSError as e:self.skipTest('Test symlink unavailable: '+str(e))
            with self.assertRaisesRegex(KnowledgeError,'linked-path'):
                project.safe_path(directory/'new.cs')

    def test_windows_reparse_attribute_and_symbolic_links_fail_closed(self):
        with patch.object(project,'os',SimpleNamespace(name='nt')):
            for mode,attributes in ((stat.S_IFREG,0x400),(stat.S_IFDIR,0x400),(stat.S_IFLNK,0)):
                self.assertTrue(project._linked_info(SimpleNamespace(st_mode=mode,st_file_attributes=attributes)))
            self.assertFalse(project._linked_info(SimpleNamespace(st_mode=stat.S_IFREG,st_file_attributes=0)))

    def test_partition_identity_matches_original_for_nested_and_ambiguous_projects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('Root.csproj','OtherRoot.csproj','Root.cs','a/A.csproj','a/AA.csproj',
                         'a/Plain.cs','a/sub/Deep.cs','b/B.csproj','b/sub/Nested.csproj','b/sub/Deep.cs',
                         'b/sub/deeper/More.cs','sibling/File.cs','outside.txt'):
                target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text('<Project Sdk="Microsoft.NET.Sdk"/>' if name.endswith('.csproj') else 'public class Source {}')
            files=discovery.inventory(root)['files']
            projects=[p for p in files if p.endswith('.csproj')]
            for name,item in files.items():
                ancestors=[p for p in projects if Path(p).parent==Path(name).parent or Path(p).parent in Path(name).parents]
                if ancestors:
                    depth=max(len(Path(p).parent.parts) for p in ancestors)
                    nearest=sorted(p for p in ancestors if len(Path(p).parent.parts)==depth)
                    self.assertEqual(item['partition'],name if name.endswith('.csproj') else nearest[0],name)
                    self.assertEqual(item['partition_ambiguous'],not name.endswith('.csproj') and len(nearest)>1,name)
            self.assertTrue(files['a/sub/Deep.cs']['partition_ambiguous'])
            self.assertEqual(files['b/sub/deeper/More.cs']['partition'],'b/sub/Nested.csproj')

    def reviewed_store(self,root):
        text='Synthetic basket preserves quantities.\n'
        (root/'Fixture.cs').write_text(text)
        s=upgraded(root);value=addition()
        value['records']['evidence'][0]['content_hash']='sha256:'+hashlib.sha256(text.encode()).hexdigest()
        s.submit(value);approve(s);return s

    def test_reviewed_context_checks_supporting_files_without_full_source_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);s=self.reviewed_store(root)
            with patch.object(discovery,'analysis_scope',side_effect=AssertionError('unrelated full source walk')):
                result=s.context('synthetic.rule')
                self.assertEqual([c['id'] for c in result['claims']],['synthetic.rule'])
                (root/'Fixture.cs').write_text('Changed behavior.\n')
                self.assertFalse(s.context('synthetic.rule')['claims'])

    def test_empty_upgraded_store_does_not_walk_unrelated_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=upgraded(Path(tmp))
            with patch.object(discovery,'analysis_scope',side_effect=AssertionError('empty store full walk')):
                self.assertFalse(s.context('unrelated')['claims'])

    def test_discovery_context_keeps_complete_scope_and_detects_new_ambiguity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'App.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"/>')
            (root/'A.cs').write_text('namespace Sample; public class Target {}\n')
            s=upgraded(root);discovery.scan(s,max_files=100);approve(s)
            with patch.object(discovery,'analysis_scope',wraps=discovery.analysis_scope) as scope:
                before=s.context('Target')
                self.assertEqual(scope.call_count,1)
            target=next(c['id'] for c in before['claims'] if 'Target' in c['statement'])
            (root/'New.cs').write_text('namespace Sample; public class Target {}\n')
            with patch.object(discovery,'analysis_scope',wraps=discovery.analysis_scope) as scope:
                after=s.context('Target')
                self.assertEqual(scope.call_count,1)
            self.assertNotIn(target,[c['id'] for c in after['claims']])

    def test_retired_discovery_claims_do_not_force_full_source_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'A.cs').write_text('public class Target {}\n')
            s=upgraded(root);discovery.scan(s,max_files=100);approve(s)
            current=s.export()['records']['claims']
            s.submit(lifecycle.batch([lifecycle.op('retire','claims',c['id'],1) for c in current],'retire synthetic scope'))
            approve(s)
            with patch.object(discovery,'analysis_scope',side_effect=AssertionError('retired-only scope')):
                self.assertFalse(s.context('Target')['claims'])


if __name__=='__main__':
    unittest.main()
