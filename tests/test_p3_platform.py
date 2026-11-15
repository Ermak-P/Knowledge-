from contextlib import closing
"""Actual native processes. Windows-only classes never qualify from Linux skips."""
import json,os,signal,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from knowledge.project import Project,safe_path
from knowledge.util import KnowledgeError
from harness.runtime import Journal,Lease,configure
from harness import engine
from harness.platform import process_info,stop_owned
from p2_fixtures import project,configuration,task,http_provider,FixtureProvider

class PlatformSafety(unittest.TestCase):
    def test_git_blob_provenance_and_ignored_paths_use_bounded_git_processes(self):
        from knowledge import discovery
        with tempfile.TemporaryDirectory() as tmp:
            for algorithm in ('sha1','sha256'):
                root=Path(tmp)/algorithm;root.mkdir()
                def git(*args):
                    return subprocess.check_output(['git','-C',str(root),*args],stderr=subprocess.DEVNULL).decode().strip()
                git('init','--object-format='+algorithm);git('config','core.autocrlf','false')
                (root/'.gitignore').write_bytes(b'Ignored.cs\n');(root/'.gitattributes').write_bytes(b'*.cs text eol=lf\n')
                for i in range(30):(root/f'Type{i}.cs').write_bytes(b'public class Type {}\n')
                git('add','.');git('-c','user.name=Synthetic','-c','user.email=fixture@example.invalid','commit','-qm','Synthetic source fixture')
                (root/'Type0.cs').write_bytes(b'public class Type {}\r\n');(root/'Ignored.cs').write_bytes(b'public class Ignored {}\n')
                raw=git('hash-object','--no-filters','Type0.cs');head=git('rev-parse','HEAD:Type0.cs')
                with patch.object(discovery,'git_process',wraps=discovery.git_process) as commands:observed=discovery.inventory(root)
                self.assertEqual(observed['files']['Type0.cs']['git_state'],'committed' if raw==head else 'staged-or-unstaged')
                self.assertEqual(observed['files']['Type0.cs']['head_blob'],head)
                self.assertEqual(observed['files']['Ignored.cs']['git_state'],'ignored')
                self.assertLessEqual(len(commands.call_args_list),8)
    def test_unicode_validation_without_inherited_utf8_mode(self):
        # MCP deliberately inherits only a small environment; it need not inherit
        # PYTHONUTF8. Persisted validation artifacts must still use explicit UTF-8.
        code='from knowledge.store import validate_records;from fixtures import addition;validate_records(addition(statement="\\u0424\\u0430\\u043a\\u0442 \\U0001f642")["records"]);print("UTF8_OK")'
        env={**os.environ,'PYTHONUTF8':'0','PYTHONCOERCECLOCALE':'0','LC_ALL':'C'}
        result=subprocess.run([sys.executable,'-X','utf8=0','-c',code],cwd=Path(__file__).parent,env=env,capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr);self.assertIn('UTF8_OK',result.stdout)
        code=r'''
import sys,tempfile
from pathlib import Path
from fixtures import addition
from knowledge.store import Store
from knowledge.cli import main
with tempfile.TemporaryDirectory(prefix='protocol-') as tmp:
 root=Path(tmp);(root/'Fixture.cs').write_bytes(b'fixture')
 store=Store(root);store.init();store.submit(addition(statement='\u0424\u0430\u043a\u0442 \U0001f642'))
 approval=store.prepare()['fingerprint'];store.apply(approval,approval);store.acknowledge(approval)
 sys.argv=['knowledge','context','--root',str(root),'--task','synthetic.rule']
 raise SystemExit(main())
'''
        result=subprocess.run([sys.executable,'-X','utf8=0','-c',code],cwd=Path(__file__).parent,env={**env,'PYTHONIOENCODING':'ascii:strict'},capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr.decode('utf-8',errors='replace'))
        self.assertEqual(json.loads(result.stdout)['claims'][0]['statement'],'Факт 🙂')
    def test_supervisor_death_cleans_real_grandchild_before_releasing_ownership(self):
        with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider()) as endpoint:
            root=project(tmp);c=configuration(endpoint,recipe_seconds=20)
            code='import subprocess,sys,time;from pathlib import Path;p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"]);Path(sys.argv[1]).write_text(str(p.pid));time.sleep(30)'
            c['recipes']['build']['argv']=[sys.executable,'-c',code,'{artifacts}/grandchild.pid'];configure(root,c,True)
            code='from harness.engine import start;from knowledge.util import loads;start('+repr(str(root))+',loads('+repr(json.dumps(task()))+'))'
            runner=subprocess.Popen([sys.executable,'-c',code]);j=Journal(root);run_id=None;grandchild=None;supervisor=None
            until=time.monotonic()+15
            while time.monotonic()<until:
                runs=j.runs()
                if runs:
                    run_id=runs[0]['id']
                    for a in j.actions(run_id).values():
                        if a.get('process') and a.get('process_spec'):
                            path=Path(a['process_spec']['log']).parent/'grandchild.pid'
                            if path.exists():grandchild=int(path.read_text());supervisor=a['process'];break
                if grandchild:break
                time.sleep(.02)
            self.assertIsNotNone(grandchild);self.assertEqual(process_info(supervisor['pid'])['start'],supervisor['start'])
            os.kill(supervisor['pid'],signal.SIGTERM if os.name=='nt' else signal.SIGKILL)
            runner.wait(timeout=15)
            # Recovery operates only on the recorded native authority; historical final
            # failure is retained and no provider inference is replayed after completion.
            before=len(FixtureProvider().requests);outcome=engine.resume(root,run_id);self.assertFalse(outcome['ok'])
            until=time.monotonic()+5
            while time.monotonic()<until:
                info=process_info(grandchild)
                if not info or info['state']=='Z':break
                time.sleep(.02)
            self.assertTrue(info is None or info['state']=='Z')
            with Lease(j):pass
            self.assertGreaterEqual(engine.status(root,run_id)['metrics']['unknown_process_attempts'],1)

    def test_foreign_receipt_cannot_terminate_unrelated_process(self):
        with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider()) as endpoint:
            root=project(tmp);configure(root,configuration(endpoint),True)
            with patch.object(engine,'resume',return_value={'created':True}):engine.start(root,task(kind='read-only'))
            j=Journal(root);run=j.runs()[0]['id'];other=subprocess.Popen([sys.executable,'-c','import time;time.sleep(15)'])
            try:
                info=process_info(other.pid);info['platform']='foreign-platform'
                j.action(run,'foreign',{'process':info,'process_spec':{'argv':[]},'process_platform':'foreign-platform'})
                with self.assertRaisesRegex(KnowledgeError,'unverifiable-process-ownership'):stop_owned(j,run)
                self.assertIsNone(other.poll())
            finally:other.terminate();other.wait(timeout=5)

@unittest.skipUnless(os.name=='nt','native Windows/NTFS validation is not a Linux result')
class NativeWindowsSafety(unittest.TestCase):
    def test_drive_case_unicode_identity_reserved_alias_and_traversal_policy(self):
        with tempfile.TemporaryDirectory(prefix='P3 путь ') as tmp,tempfile.TemporaryDirectory() as other:
            root=Path(tmp);self.assertEqual(Project(root).identity,Project(str(root).upper()).identity);self.assertNotEqual(Project(root).identity,Project(other).identity)
            for path in ('\\\\server\\share','\\\\?\\C:\\x','C:relative','CON','NUL.txt','file.txt:stream','bad.','bad ','SHORT~1'):
                with self.subTest(path=path),self.assertRaises(KnowledgeError):safe_path(path)
            with self.assertRaises(KnowledgeError):Project(root/'..')
    def test_junction_symlink_and_hardlink_are_rejected_before_access(self):
        with tempfile.TemporaryDirectory() as tmp,tempfile.TemporaryDirectory() as other:
            root=Path(tmp);external=Path(other);(external/'outside.txt').write_text('OUTSIDE')
            junction=root/'junction';p=subprocess.run(['cmd.exe','/d','/c','mklink','/J',str(junction),str(external)],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)
            with self.assertRaisesRegex(KnowledgeError,'linked-path'):safe_path(junction/'outside.txt')
            link=root/'symlink';os.symlink(external,link,target_is_directory=True)
            with self.assertRaisesRegex(KnowledgeError,'linked-path'):Project(link)
            hard=root/'hard.txt';os.link(external/'outside.txt',hard)
            with self.assertRaisesRegex(KnowledgeError,'unsafe-filesystem-object'):safe_path(hard)
            from knowledge.discovery import inventory
            (external/'outside.cs').write_text('public class External {}',encoding='utf-8')
            os.link(external/'outside.cs',root/'hard.cs')
            scanned=inventory(root)
            self.assertFalse(any(p.startswith('junction/') or p.startswith('symlink/') for p in scanned['files']))
            self.assertEqual(scanned['files']['hard.cs']['status'],'blocked')
            junction.rmdir();link.unlink()
    def test_compatible_upgrade_releases_backup_and_store_handles(self):
        from knowledge.windows_lock import k,INVALID
        from knowledge.store import Store
        from knowledge import lifecycle as life
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp);store.init();result=life.upgrade(store,life.upgrade_preview(store)['fingerprint'])
            for path in (store.path,Path(result['backup'])):
                handle=k.CreateFileW(str(path),0xC0000000,0,None,3,0x80,None)
                self.assertNotEqual(handle,INVALID)
                k.CloseHandle(handle)
    def test_locked_target_edit_fails_with_original_bytes_intact(self):
        from knowledge.windows_lock import k,INVALID
        with tempfile.TemporaryDirectory() as tmp,http_provider(FixtureProvider()) as endpoint:
            root=project(tmp);configure(root,configuration(endpoint),True);path=root/'Feature.cs';before=path.read_bytes();handle=k.CreateFileW(str(path),0x80000000,3,None,3,0x80,None);self.assertNotEqual(handle,INVALID)
            try:
                result=engine.start(root,task());self.assertFalse(result['ok']);self.assertEqual(path.read_bytes(),before)
            finally:k.CloseHandle(handle)
    def test_native_job_timeout_and_descendant_cleanup(self):
        from test_p2 import RecoveryTests
        # Same executed behavior, native backend; this is an explicit named counterpart.
        RecoveryTests('test_timeout_cleans_real_descendants_and_cancellation_stops_provider').test_timeout_cleans_real_descendants_and_cancellation_stops_provider()
    def test_native_parent_death_lease_and_recovery(self):
        from test_p2 import RecoveryTests
        RecoveryTests('test_real_worker_death_recipe_keeps_lease_and_recovery_cleans_it').test_real_worker_death_recipe_keeps_lease_and_recovery_cleans_it()
    def test_absolute_case_variant_verifier_is_protected(self):
        with tempfile.TemporaryDirectory(prefix='P3 verifier путь ') as tmp:
            root=project(tmp);verify=root/'verify.py';verify.write_text('raise RuntimeError("trusted verifier fails")\n',encoding='utf-8');before=verify.read_bytes()
            with http_provider(FixtureProvider(path='verify.py',desired='print("Ran 1 test in 0.001s\\n\\nOK")\n')) as endpoint:
                config=configuration(endpoint);config['recipes']['test']['argv']=[sys.executable,str(verify).upper()];configure(root,config,True);t=task();t['writable']=['*']
                result=engine.start(root,t);self.assertFalse(result['ok']);self.assertEqual(verify.read_bytes(),before)
                self.assertIn('verify.py',engine.status(root,result['run_id'])['run']['protected_paths'])
    def test_locked_metadata_restore_refuses_then_recovers_after_release(self):
        from knowledge.windows_lock import k,INVALID
        from knowledge import maintenance as m
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);root=project(base/'root');configure(root,configuration('http://127.0.0.1/v1/chat/completions'),True)
            backup=m.preview(root,'backup',base/'backup.zip');m.apply(root,backup['preview'],backup['fingerprint'])
            plan=m.preview(root,'restore',archive=base/'backup.zip',recovery=base/'replaced')
            handle=k.CreateFileW(str(root/'.knowledge/store.sqlite3'),0x80000000,3,None,3,0x80,None);self.assertNotEqual(handle,INVALID)
            try:
                with self.assertRaises((KnowledgeError,OSError)):m.apply(root,plan['preview'],plan['fingerprint'])
                self.assertTrue(m.status(root)['active'])
            finally:k.CloseHandle(handle)
            self.assertTrue(m.recover(root)['ok'])
# The following storage assertion is portable, separate from native-only cases.
class DurableInitialization(unittest.TestCase):
    def test_existing_empty_or_missing_table_state_is_not_reinitialized(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);base=root/'.harness';base.mkdir();db=base/'runs.sqlite3';db.write_bytes(b'')
            with self.assertRaisesRegex(KnowledgeError,'harness-state-incomplete'):Journal(root)
            self.assertEqual(db.read_bytes(),b'')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);j=Journal(root)
            with closing(sqlite3.connect(j.path)) as db, db:db.execute('DROP TABLE actions')
            before=j.path.read_bytes()
            with self.assertRaisesRegex(KnowledgeError,'harness-state-incomplete'):Journal(root)
            self.assertEqual(j.path.read_bytes(),before)
