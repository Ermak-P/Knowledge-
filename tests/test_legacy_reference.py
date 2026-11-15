"""Executable differential checks against the actual supplied implementation.

The archived installer is not invoked or patched. Ranking is compared at its
assemble boundary; new provenance and hard byte bounding are checked elsewhere.
"""
import hashlib
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from knowledge.retrieval import ContextEngine
from fixtures import addition


class LegacyReferenceTests(unittest.TestCase):
    def test_archive_integrity_and_ranking_parity(self):
        root=Path(__file__).resolve().parents[1]
        manifest=json.loads((root/'inputs/ai-source-manifest.json').read_text())
        archive=root/'inputs/ai-source.zip'
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),manifest['sha256'])
        with tempfile.TemporaryDirectory() as tmp,zipfile.ZipFile(archive) as z:
            for f in manifest['included_files']:
                self.assertEqual(hashlib.sha256(z.read(f['path'])).hexdigest(),f['sha256'])
            z.extractall(tmp)
            sys.path.insert(0,str(Path(tmp)/'.ai/tools'))
            try:
                reference=importlib.import_module('context_engine')
                a=addition();b=addition('synthetic.other','Synthetic alternative basket history.','INFERRED')
                records={g:a['records'][g]+b['records'][g] for g in a['records']}
                for query in ['synthetic.rule','basket quantities','xylophonequasar']:
                    for include in [False,True]:
                        old=reference.ContextEngine().assemble(records,query,max_tokens=10000,include_unconfirmed=include)
                        new=ContextEngine().assemble(records,query,max_tokens=10000,include_unconfirmed=include)
                        self.assertEqual([(r['id'],r['status'],r['score']) for r in old['claims']],
                                         [(r['id'],r['status'],r['score']) for r in new['claims']])
                        self.assertEqual(old['result'],new['result'])
            finally:
                sys.path.pop(0)
                for name,module in list(sys.modules.items()):
                    if str(getattr(module,'__file__','')).startswith(tmp):sys.modules.pop(name,None)

    def test_active_code_has_no_machine_default_or_worktree_execution(self):
        root=Path(__file__).resolve().parents[1]
        forbidden_machine='C:'+chr(92)+'Git'+chr(92)+'IPM'
        for directory in ('packages','scripts'):
            for path in (root/directory).rglob('*.py'):
                if 'build' in path.parts or '__pycache__' in path.parts:continue
                text=path.read_text()
                self.assertNotIn(forbidden_machine,text,str(path))
                self.assertNotRegex(text.lower(),r'''['"]worktree['"]|worktree\s+add''',str(path))
