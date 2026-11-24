"""Real generated-launcher processes; native-only lifecycle assertions stay native."""
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import venv
import knowledge
from core_wire import Wire

ROOT=Path(__file__).resolve().parents[1]
BACKEND=runpy.run_path(str(ROOT/'installer/knowledge_install.py'))


class BootstrapFixture:
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory(prefix='bootstrap-');cls.root=Path(cls.temporary.name)/'runtime Ω with spaces';cls.root.mkdir()
        cls.runtime=cls.root/'runtimes/generation';venv.EnvBuilder(with_pip=False).create(cls.runtime)
        cls.python=cls.runtime/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        site=cls.runtime/('Lib/site-packages' if os.name=='nt' else 'lib/python%d.%d/site-packages'%sys.version_info[:2]);site.mkdir(parents=True,exist_ok=True)
        modules=cls.root/'probe modules';package=modules/'knowledge';package.mkdir(parents=True)
        actual=Path(knowledge.__file__).parent
        (package/'__init__.py').write_text('__version__="0.5.0rc1"\n__path__.append('+repr(str(actual))+')\n',encoding='utf-8')
        (package/'project_commands.py').write_text('''import json,os,subprocess,sys
detached=None
if "--detach" in sys.argv:
    flags=subprocess.CREATE_BREAKAWAY_FROM_JOB if os.name=="nt" else 0
    detached=subprocess.Popen([sys._base_executable,"-c","import time;time.sleep(60)"],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags,start_new_session=os.name!="nt")
print(json.dumps({"argv":sys.argv[1:],"pid":os.getpid(),"detached":detached.pid if detached else None}),flush=True)
print("probe-stderr",file=sys.stderr,flush=True)
value=sys.stdin.readline()
if value: print(value.strip(),flush=True)
raise SystemExit(7 if "--nonzero" in sys.argv else 0)
''',encoding='utf-8')
        dependencies=Path(sys.prefix)/('Lib/site-packages' if os.name=='nt' else 'lib/python%d.%d/site-packages'%sys.version_info[:2])
        (site/'bootstrap-fixture.pth').write_text('import sys,site;sys.path.insert(0,'+ascii(str(modules))+');site.addsitedir('+ascii(str(dependencies))+')\n',encoding='ascii')
        (cls.root/'launch.py').write_text(BACKEND['BOOTSTRAP'],encoding='utf-8')
        shutil.copyfile(ROOT/'installer/windows_process.py',cls.root/'windows-process.py')
        cls.current=cls.root/'current.json';cls.current.write_text(json.dumps({'runtime':'runtimes/generation','version':1}),encoding='utf-8')
    @classmethod
    def tearDownClass(cls):cls.temporary.cleanup()
    def argv(self,mode='command',*args):return [sys.executable,'-I','-B','-X','utf8',str(self.root/'launch.py'),mode,*args]


class GeneratedBootstrap(BootstrapFixture,unittest.TestCase):
    def test_streams_unicode_arguments_waiting_and_success(self):
        process=subprocess.Popen(self.argv('command','argument with spaces','аргумент Ω'),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            line=process.stdout.readline();record=json.loads(line)
            self.assertIsNone(process.poll())
            self.assertEqual(record['argv'],['--installation',str(self.root),'argument with spaces','аргумент Ω'])
            if os.name!='nt':self.assertEqual(record['pid'],process.pid)  # POSIX execv replacement.
            else:self.assertNotEqual(record['pid'],process.pid)  # Windows waiting launcher.
            output,error=process.communicate('Привет Ω\n'.encode('utf-8'),timeout=10)
            self.assertEqual(process.returncode,0);self.assertEqual(output.decode().strip(),'Привет Ω');self.assertIn(b'probe-stderr',error)
        finally:
            if process.poll() is None:process.kill();process.wait(timeout=10)
            for stream in (process.stdin,process.stdout,process.stderr):stream.close()

    def test_nonzero_child_exit_and_missing_executable(self):
        result=subprocess.run(self.argv('command','--nonzero'),input=b'',capture_output=True,timeout=15)
        self.assertEqual(result.returncode,7);self.assertIn(b'probe-stderr',result.stderr)
        saved=self.current.read_bytes()
        try:
            self.current.write_text('{"runtime":"runtimes/missing"}',encoding='utf-8')
            failed=subprocess.run(self.argv(),input=b'',capture_output=True,timeout=15)
            self.assertNotEqual(failed.returncode,0);self.assertFalse(failed.stdout);self.assertIn(b'startup failed',failed.stderr)
        finally:self.current.write_bytes(saved)

    def test_runtime_traversal_is_rejected_before_execution(self):
        saved=self.current.read_bytes()
        try:
            self.current.write_text('{"runtime":"../outside"}',encoding='utf-8')
            failed=subprocess.run(self.argv(),input=b'',capture_output=True,timeout=10)
            self.assertNotEqual(failed.returncode,0);self.assertFalse(failed.stdout);self.assertIn(b'Invalid Knowledge runtime',failed.stderr)
        finally:self.current.write_bytes(saved)

    def test_real_generated_mcp_handshake_catalog_eof_and_repeated_shutdown(self):
        from knowledge.machine_mcp import TOOL_NAMES
        for repetition in range(3):
            peer=Wire(self.argv('mcp'))
            try:
                self.assertEqual(peer.initialize()['serverInfo']['name'],'knowledge')
                self.assertEqual({t['name'] for t in peer.request(102,'tools/list')['tools']},TOOL_NAMES)
            finally:errors=peer.close()
            self.assertEqual(peer.process.returncode,0,errors)

    def test_supported_launcher_update_preserves_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);provider=root/'provider.json';provider.write_bytes(b'user-owned-provider')
            launcher=root/'launch.py';launcher.write_bytes(b'previous launcher')
            helper=root/'windows-process.py'
            updates={launcher:BACKEND['BOOTSTRAP'].encode(),helper:(ROOT/'installer/windows_process.py').read_bytes()}
            BACKEND['transaction'](root,updates)
            self.assertEqual(launcher.read_text(),BACKEND['BOOTSTRAP']);self.assertEqual(provider.read_bytes(),b'user-owned-provider')
            self.assertFalse((root/'transaction.json').exists())


@unittest.skipUnless(os.name=='nt','Actual Windows Job Object and handle inheritance required')
class NativeWindowsSafety(BootstrapFixture,unittest.TestCase):
    def test_forced_parent_death_cleans_owned_child_and_preserves_unrelated_process(self):
        from knowledge.scan_jobs import alive
        unrelated=subprocess.Popen([sys._base_executable,'-c','import time;time.sleep(60)'])
        process=subprocess.Popen(self.argv(),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            child=json.loads(process.stdout.readline())['pid'];self.assertTrue(alive(child))
            process.kill();process.wait(timeout=10);deadline=time.monotonic()+10
            while alive(child) and time.monotonic()<deadline:time.sleep(.05)
            self.assertFalse(alive(child),'Owned MCP/command child survived launcher death');self.assertIsNone(unrelated.poll())
        finally:
            if process.poll() is None:process.kill();process.wait(timeout=10)
            unrelated.kill();unrelated.wait(timeout=10)
            for stream in (process.stdin,process.stdout,process.stderr):stream.close()

    def test_explicit_breakaway_worker_survives_parent_job(self):
        from knowledge.scan_jobs import alive
        process=subprocess.Popen(self.argv('command','--detach'),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);detached=None
        try:
            record=json.loads(process.stdout.readline());detached=record['detached'];self.assertTrue(alive(detached))
            process.kill();process.wait(timeout=10);self.assertTrue(alive(detached),'Durable worker was incorrectly killed with MCP job')
        finally:
            if process.poll() is None:process.kill();process.wait(timeout=10)
            if detached and alive(detached):os.kill(detached,15)
            for stream in (process.stdin,process.stdout,process.stderr):stream.close()
