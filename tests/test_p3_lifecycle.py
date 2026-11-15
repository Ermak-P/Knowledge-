import json,os,sqlite3,subprocess,sys,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from knowledge import maintenance as m
from knowledge.store import Store
from knowledge.util import KnowledgeError,canonical_json
from harness.runtime import Journal,Lease
from p3_state_fixtures import rich,logical
from p2_fixtures import project,configuration
from harness.runtime import configure

class LifecycleTests(unittest.TestCase):
    def test_nonempty_upgrade_backup_restore_preserves_all_authority_and_user_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);root=base/'project';root.mkdir();fixture=rich(root);before=logical(root)
            plan=m.preview(root,'upgrade',base/'upgrade.zip')
            self.assertEqual(logical(root),before)
            with self.assertRaises(KnowledgeError):m.apply(root,plan['preview'],'wrong')
            result=m.apply(root,plan['preview'],plan['fingerprint']);self.assertTrue(result['ok']);self.assertEqual(logical(root),before)
            Store(root).recover();self.assertNotEqual(logical(root),before)
            (root/'user.txt').write_text('USER BYTES')
            restore=m.preview(root,'restore',archive=base/'upgrade.zip',recovery=base/'replaced')
            m.apply(root,restore['preview'],restore['fingerprint'])
            self.assertEqual(logical(root),before);self.assertEqual((root/'user.txt').read_text(),'USER BYTES')
            self.assertTrue((base/'replaced/.knowledge/store.sqlite3').is_file())
            self.assertEqual(Store(root).status()['plans'][-1].keys(),{'fingerprint','state'})

    def test_stale_busy_unknown_absent_and_corrupt_refuse_without_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);root=project(base/'project');configure(root,configuration('http://127.0.0.1/v1/chat/completions'),True)
            plan=m.preview(root,'backup',base/'backup.zip');(root/'unrelated.txt').write_text('intervening edit')
            with self.assertRaisesRegex(KnowledgeError,'stale-maintenance-preview'):m.apply(root,plan['preview'],plan['fingerprint'])
            with Lease(Journal(root)):
                with self.assertRaisesRegex(KnowledgeError,'project-writer-busy'):m.preview(root,'backup',base/'backup.zip')
            with Store(root).connection(True):
                with self.assertRaisesRegex(KnowledgeError,'maintenance-busy'):m.preview(root,'backup',base/'backup.zip')
            with sqlite3.connect(root/'.harness/runs.sqlite3') as db:db.execute("UPDATE meta SET value='99' WHERE key='version'")
            with self.assertRaisesRegex(KnowledgeError,'unsupported-harness-state'):m.preview(root,'backup',base/'backup.zip')
            other=base/'absent';other.mkdir()
            with self.assertRaisesRegex(KnowledgeError,'maintenance-state-absent'):m.preview(other,'upgrade',base/'absent.zip')
            self.assertFalse((other/'.knowledge').exists())

    def test_untrusted_backup_members_checksum_and_root_binding_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);root=project(base/'project');configure(root,configuration('http://127.0.0.1/v1/chat/completions'),True)
            plan=m.preview(root,'backup',base/'good.zip');m.apply(root,plan['preview'],plan['fingerprint'])
            for name in ('../outside','.knowledge/../outside','.knowledge\\outside'):
                path=base/'unsafe.zip'
                with zipfile.ZipFile(base/'good.zip') as old,zipfile.ZipFile(path,'w') as new:
                    for entry in old.infolist():new.writestr(entry,old.read(entry))
                    new.writestr(name,'bad')
                with self.assertRaises(KnowledgeError):m.preview(root,'restore',archive=path,recovery=base/'saved')
            path=base/'tampered.zip'
            with zipfile.ZipFile(base/'good.zip') as old,zipfile.ZipFile(path,'w') as new:
                for entry in old.infolist():new.writestr(entry,b'bad' if entry.filename.endswith('store.sqlite3') else old.read(entry))
            with self.assertRaisesRegex(KnowledgeError,'backup-checksum-mismatch'):m.preview(root,'restore',archive=path,recovery=base/'saved')
            other=project(base/'other');configure(other,configuration('http://127.0.0.1/v1/chat/completions'),True)
            with self.assertRaisesRegex(KnowledgeError,'backup-project-mismatch-no-relocation'):m.preview(other,'restore',archive=base/'good.zip',recovery=base/'saved')
            self.assertFalse((base/'outside').exists())

    def test_real_restore_crash_windows_fence_and_idempotent_recovery(self):
        for phase in ('maintenance-prepared','restore-old-moved','restore-new-moved','maintenance-committed'):
            with self.subTest(phase=phase),tempfile.TemporaryDirectory() as tmp:
                base=Path(tmp);root=project(base/'project');configure(root,configuration('http://127.0.0.1/v1/chat/completions'),True)
                before=logical(root);plan=m.preview(root,'backup',base/'backup.zip');m.apply(root,plan['preview'],plan['fingerprint'])
                (root/'user.txt').write_text('PRESERVE')
                plan=m.preview(root,'restore',archive=base/'backup.zip',recovery=base/'saved')
                input_path=base/'preview.json';input_path.write_text(canonical_json(plan['preview']),encoding='utf-8')
                code='from knowledge import maintenance as m;from knowledge.util import loads;from pathlib import Path;import os;m.fault=lambda p:os._exit(73) if p=='+repr(phase)+' else None;m.apply('+repr(str(root))+',loads(Path('+repr(str(input_path))+').read_text(encoding="utf-8")),'+repr(plan['fingerprint'])+')'
                p=subprocess.run([sys.executable,'-c',code],timeout=15);self.assertEqual(p.returncode,73)
                with self.assertRaisesRegex(KnowledgeError,'maintenance-recovery-required'):Store(root).validate()
                m.recover(root);self.assertEqual(logical(root),before);self.assertEqual((root/'user.txt').read_text(),'PRESERVE')
                with self.assertRaisesRegex(KnowledgeError,'no-maintenance-to-recover'):m.recover(root)

    def test_upgrade_commit_crash_recovery_preserves_exact_nonempty_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);root=project(base/'project');configure(root,configuration('http://127.0.0.1/v1/chat/completions'),True)
            before=logical(root);plan=m.preview(root,'upgrade',base/'before.zip')
            class Crash(Exception):pass
            with patch.object(m,'fault',side_effect=lambda phase:(_ for _ in ()).throw(Crash()) if phase=='maintenance-committed' else None):
                with self.assertRaises(Crash):m.apply(root,plan['preview'],plan['fingerprint'])
            m.recover(root);self.assertEqual(logical(root),before)
    def test_restore_absent_metadata_and_repeat_exact_approval_are_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);root=project(base/'project');configure(root,configuration('http://127.0.0.1/v1/chat/completions'),True)
            expected=logical(root);p=m.preview(root,'upgrade',base/'backup.zip');m.apply(root,p['preview'],p['fingerprint'])
            self.assertEqual(m.apply(root,p['preview'],p['fingerprint'])['result'],'already-completed')
            # Move, never delete the retained state; recreate it only via exact restore.
            (root/'.knowledge').rename(base/'knowledge-preserved');(root/'.harness').rename(base/'harness-preserved')
            p=m.preview(root,'restore',archive=base/'backup.zip',recovery=base/'replacement')
            m.apply(root,p['preview'],p['fingerprint']);self.assertEqual(logical(root),expected)
            self.assertEqual(m.apply(root,p['preview'],p['fingerprint'])['result'],'already-completed')
    def test_unknown_operational_marker_and_manifest_counts_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);root=project(base/'project');configure(root,configuration('http://127.0.0.1/v1/chat/completions'),True)
            p=m.preview(root,'backup',base/'backup.zip');m.apply(root,p['preview'],p['fingerprint'])
            with zipfile.ZipFile(base/'backup.zip') as old,zipfile.ZipFile(base/'bad-counts.zip','w') as new:
                for info in old.infolist():
                    data=old.read(info)
                    if info.filename=='MANIFEST.json':
                        value=json.loads(data);value['counts']['.knowledge']['records']+=1;data=json.dumps(value).encode()
                    new.writestr(info,data)
            with self.assertRaisesRegex(KnowledgeError,'backup-semantic-count-mismatch'):m.preview(root,'restore',archive=base/'bad-counts.zip',recovery=base/'saved')
            marker=root/'.maintenance/product-state.json';marker.parent.mkdir(exist_ok=True);marker.write_text('{"version":99}')
            with self.assertRaisesRegex(KnowledgeError,'unsupported-maintenance-version'):m.preview(root,'upgrade',base/'upgrade.zip')
    def test_exclusive_freeze_refuses_an_independent_canonical_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);root=project(base/'root');configure(root,configuration('http://127.0.0.1/v1/chat/completions'),True)
            from fixtures import addition
            payload=json.dumps(addition())
            code='from knowledge.store import Store;from knowledge.util import loads,KnowledgeError;import sys\ntry:Store('+repr(str(root))+').submit(loads('+repr(payload)+'))\nexcept KnowledgeError as e:print(e.code);sys.exit(17)'
            with m.frozen(root):
                p=subprocess.run([sys.executable,'-c',code],text=True,capture_output=True,timeout=5);self.assertEqual(p.returncode,17,p.stderr);self.assertIn('maintenance-busy',p.stdout);self.assertFalse(Store(root).status()['queue'])
    def test_tampered_restore_staging_cannot_replace_live_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);root=project(base/'root');configure(root,configuration('http://127.0.0.1/v1/chat/completions'),True)
            before=logical(root);backup=m.preview(root,'backup',base/'backup.zip');m.apply(root,backup['preview'],backup['fingerprint'])
            plan=m.preview(root,'restore',archive=base/'backup.zip',recovery=base/'saved')
            class Crash(Exception):pass
            with patch.object(m,'fault',side_effect=lambda phase:(_ for _ in ()).throw(Crash()) if phase=='maintenance-prepared' else None):
                with self.assertRaises(Crash):m.apply(root,plan['preview'],plan['fingerprint'])
            state=m.status(root);txn=state['active']['transaction'];staged=root/'.maintenance/transactions'/txn/'staged/.harness/runner.json';staged.write_text('{"version":99}')
            with self.assertRaisesRegex(KnowledgeError,'restore-staged-state-conflict'):m.recover(root)
            self.assertTrue((root/'.knowledge/store.sqlite3').exists());self.assertTrue(m.status(root)['active'])
    def test_legacy_sqlite_writer_without_new_gate_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);root=project(base/'root');configure(root,configuration('http://127.0.0.1/v1/chat/completions'),True)
            connection=sqlite3.connect(root/'.knowledge/store.sqlite3');connection.execute('BEGIN IMMEDIATE')
            try:
                with self.assertRaisesRegex(KnowledgeError,'maintenance-sqlite-busy'):m.preview(root,'upgrade',base/'backup.zip')
            finally:connection.rollback();connection.close()
            self.assertFalse((base/'backup.zip').exists());self.assertTrue(Store(root).validate()['ok'])
