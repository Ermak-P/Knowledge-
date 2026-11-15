from contextlib import closing
"""Exact P2-R1/R2/R3 production reproductions, preserving the original 129 cases."""
import tempfile,unittest
from pathlib import Path
from p2_review_fixtures import learning,manual_review,verifier,overlap

class ReviewCorrections(unittest.TestCase):
    def test_r1_automatic_add_approve_two_updates_and_retired_return(self):
        with tempfile.TemporaryDirectory() as tmp:learning(Path(tmp))
    def test_r1_reviewed_meaning_and_legacy_capture_require_explicit_manual_review(self):
        for legacy in (False,True):
            with self.subTest(legacy=legacy),tempfile.TemporaryDirectory() as tmp:manual_review(Path(tmp),legacy)
    def test_r2_absolute_relative_and_project_entrypoint_cannot_replace_verifier(self):
        for absolute,executable in ((False,False),(True,False),(True,True)):
            with self.subTest(absolute=absolute,executable=executable),tempfile.TemporaryDirectory(prefix='P2 verifier путь ') as tmp:verifier(Path(tmp),absolute,executable)
    def test_r2_exact_explicit_script_edit_exception_is_observable(self):
        with tempfile.TemporaryDirectory() as tmp:verifier(Path(tmp),exception=True)
    def test_r3_prelease_race_retains_terminal_readonly_coding_and_capture(self):
        for window in ('read-only','coding','capture'):
            with self.subTest(window=window),tempfile.TemporaryDirectory() as tmp:overlap(Path(tmp),window)
    def test_r3_configuration_is_reloaded_under_ownership_before_capture(self):
        with tempfile.TemporaryDirectory() as tmp:overlap(Path(tmp),'capture',True)
    def test_r1_update_crash_and_rejected_deferred_retry_preserve_ownership(self):
        from p2_review_fixtures import update_retry
        for disposition in (None,'rejected','deferred'):
            with self.subTest(disposition=disposition),tempfile.TemporaryDirectory() as tmp:update_retry(Path(tmp),disposition)
    def test_r2_recipe_input_resolver_rejects_links_and_hardlinks(self):
        from harness.runtime import recipe_inputs
        from knowledge.project import Project
        from knowledge.util import KnowledgeError
        from p2_fixtures import project,configuration,task
        import os,sys
        with tempfile.TemporaryDirectory() as tmp,tempfile.TemporaryDirectory() as other:
            root=project(tmp);external=Path(other)/'verify.py';external.write_text('exit(1)')
            for kind in ('symlink','hardlink'):
                with self.subTest(kind=kind):
                    p=root/'verify.py'
                    if kind=='symlink':p.symlink_to(external)
                    else:os.link(external,p)
                    c=configuration('http://127.0.0.1/v1/chat/completions');c['recipes']['test']['argv']=[sys.executable,str(p)]
                    with self.assertRaises(KnowledgeError):recipe_inputs(Project(root),c,task())
                    p.unlink()
    def test_r1_malformed_observation_metadata_refuses_without_reset(self):
        from knowledge.store import Store
        from knowledge.util import KnowledgeError
        from harness.runtime import configure
        from p2_fixtures import project,configuration
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            root=project(tmp);configure(root,configuration('http://127.0.0.1/v1/chat/completions'),True);store=Store(root)
            with closing(sqlite3.connect(store.path)) as db, db:db.execute('INSERT INTO metadata VALUES (?,?)',('capture-observation-v1:invalid','{"version":99}'))
            before=store.path.read_bytes()
            with self.assertRaisesRegex(KnowledgeError,'corrupt-capture-observation-receipt'):store.validate()
            self.assertEqual(store.path.read_bytes(),before)
