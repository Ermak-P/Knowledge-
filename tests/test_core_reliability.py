"""Generic source/worker/MCP/approval regressions; all fixtures are synthetic."""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import threading
import time
import tracemalloc
import unittest
from unittest.mock import patch
from knowledge import discovery as d, lifecycle, providers, source_reader as reader
from knowledge.auto_init import run, read_json, write_json, ScanError,lease_options
from knowledge.store import Store
from knowledge.util import KnowledgeError
from knowledge.project_commands import execute, diagnostics
from core_wire import Wire
from test_machine_commands import fixture, wait, write

REPO=Path(__file__).resolve().parents[1]


def upgraded(root):
    store=Store(root);store.init();lifecycle.upgrade(store,lifecycle.upgrade_preview(store)['fingerprint']);return store


def finish(store,maximum=2,scan=None,**kwargs):
    calls=[]
    while True:
        value=d.scan(store,scan,max_files=maximum,**kwargs);scan=value['id'];calls.extend(value['work']['paths_this_call'])
        if value['work']['remaining_files']==0:return value,calls


class SourceReliability(unittest.TestCase):
    def test_hardlink_is_never_read_and_does_not_stop_independent_files(self):
        with tempfile.TemporaryDirectory() as tmp,tempfile.TemporaryDirectory() as outside:
            root=Path(tmp);target=Path(outside)/'secret.cs';target.write_text('public class Outside {}')
            os.link(target,root/'hard.cs');(root/'safe.cs').write_text('public class Safe {}')
            value,_=finish(upgraded(root))
            self.assertEqual(value['coverage']['hard.cs']['reason_code'],'UNSAFE_PATH')
            self.assertEqual(value['counters']['processed_files'],1)
            self.assertEqual([o['subject'] for o in value['observations']],['Safe'])
            self.assertFalse(value['complete'])

    def test_mixed_encodings_and_declared_cp1251_preserve_raw_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            cases={'a.cs':('utf-8','namespace Пример; public class Один {}'),
                   'b.cs':('utf-8-sig','public class Два {}'),
                   'c.cs':('utf-16','public class Три {}'),
                   'd.cs':('utf-16-be','\ufeffpublic class Четыре {}'),
                   'e.xml':('cp1251','<?xml version="1.0" encoding="windows-1251"?><r>Пример</r>')}
            for path,(encoding,text) in cases.items():(root/path).write_bytes(text.encode(encoding))
            store=upgraded(root);value,calls=finish(store)
            self.assertTrue(value['complete'],value['coverage']);self.assertEqual(len(calls),5)
            self.assertEqual(len(value['observations']),4)
            import hashlib
            for path in cases:self.assertEqual(value['snapshot']['files'][path]['hash'],'sha256:'+hashlib.sha256((root/path).read_bytes()).hexdigest())

    def test_legacy_decoding_is_explicit_and_policy_drift_invalidates_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'legacy.cs').write_bytes('public class Пример {}'.encode('cp1251'));store=upgraded(root)
            failed=d.scan(store,max_files=10);self.assertEqual(failed['coverage']['legacy.cs']['reason_code'],'INVALID_ENCODING')
            write(root/'.knowledge/discovery.json',{'version':1,'legacy_encodings':{'legacy.cs':'windows-1251'}})
            with self.assertRaisesRegex(KnowledgeError,'stale-scan'):d.scan(store,failed['id'])
            recovered=d.scan(store,restart=True,max_files=10);self.assertTrue(recovered['complete']);self.assertEqual(len(recovered['observations']),1)

    def test_invalid_json_encoding_binary_and_xml_entities_have_specific_reasons(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);files={'invalid.json':b'{bad','encoding.md':b'\xff\xfe\x00','binary.json':b'PK\x03\x04binary',
                                  'external.xml':b'<!DOCTYPE r [<!ENTITY x SYSTEM "file:///unavailable">]><r>&x;</r>'}
            for name,data in files.items():(root/name).write_bytes(data)
            value,_=finish(upgraded(root));self.assertFalse(value['complete'])
            self.assertEqual({p:e['reason_code'] for p,e in value['coverage'].items()},
                             {'invalid.json':'EXTRACTION_FAILED','encoding.md':'INVALID_ENCODING','binary.json':'EXCLUDED_BINARY','external.xml':'EXTRACTION_FAILED'})
            self.assertEqual(value['counters']['classified_excluded_files'],1)
            self.assertNotIn('file:///unavailable',json.dumps(value['coverage']))

    def test_large_structured_previews_are_bounded_and_never_full_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('big.json','big.xml','big.yaml'):(root/name).write_text('x'*2000000,encoding='utf-8')
            store=upgraded(root);tracemalloc.start()
            value,_=finish(store);peak=tracemalloc.get_traced_memory()[1];tracemalloc.stop()
            self.assertEqual(value['counters']['partially_processed_files'],3)
            self.assertEqual(value['state'],'COMPLETED_WITH_GAPS');self.assertFalse(value['complete']);self.assertLess(peak,25*1024*1024)
            for entry in value['coverage'].values():
                self.assertEqual(entry['reason_code'],'PARTIAL_EXTRACTION');self.assertLessEqual(entry['analyzed_bytes'],d.LIMIT)
            self.assertIsNone(d.reconcile(store,value['id'])['proposal'])

    def test_source_change_after_inventory_is_not_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'a.cs';path.write_text('public class Before {}');entry=d.inventory(root)['files']['a.cs']
            path.write_text('public class After {}')
            with self.assertRaisesRegex(KnowledgeError,'FILE_CHANGED_DURING_SCAN'):d.extract(root,'a.cs',entry)

    def test_exclusions_are_explicit_and_do_not_blanket_exclude_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);store=upgraded(root)
            for name in ('data.json','infra.yaml','report.json'):(root/name).write_text('{}')
            write(root/'.knowledge/discovery.json',{'version':1,'exclude':[{'glob':'report.json','reason':'synthetic generated report'}]})
            value,_=finish(store);self.assertIn('data.json',value['coverage']);self.assertIn('infra.yaml',value['coverage']);self.assertNotIn('report.json',value['coverage'])
            self.assertTrue(any(e.get('rule')=='report.json' for e in value['snapshot']['exclusions']))
            self.assertEqual(value['counters']['discovered_files'],value['counters']['eligible_files']+value['counters']['policy_excluded_files'])


class ScanReliability(unittest.TestCase):
    def test_observed_resume_recovers_committed_chunk_without_helper_checkpoint(self):
        from knowledge.project_commands import configure_project,machine_binding
        from knowledge.project import Project
        with tempfile.TemporaryDirectory() as tmp:
            install,root=fixture(tmp,4);store=upgraded(root);configure_project(install,Project(root))
            folder=install/'state/projects'/Project(root).identity/'full';folder.mkdir(parents=True)
            original=write_json
            def failed_checkpoint(path,value):
                if path.name=='checkpoint.json':raise OSError('synthetic checkpoint storage failure')
                return original(path,value)
            with contextlib.redirect_stdout(io.StringIO()),patch('knowledge.auto_init.write_json',failed_checkpoint):
                with self.assertRaises(OSError):run(root,folder,max_files=1)
            observed=d.status(store)['scans'][0];processed=set(observed['work']['paths_this_call'])
            write_json(folder/'job.json',{'version':1,'job':'synthetic-crashed-worker','pid':1073741823,'state':'RUNNING',
                       'root':str(root),'scope':{'kind':'full'},'binding':machine_binding(install,Project(root))[0],'chunk_started':True})
            listed=diagnostics(install,root,section='scans');self.assertEqual(listed['rows'][0]['scan_id'],observed['id'])
            # Observation/recovery remains possible even if an atomic write
            # was externally corrupted after the durable SQLite commit.
            write_json(folder/'checkpoint.json',{'version':2,'scan_id':'0'*64,'checksum':'corrupt'})
            self.assertEqual(diagnostics(install,root,section='scans')['rows'][0]['scan_id'],observed['id'])
            execute('knowledge-init',install,root,{'resume':True,'observed_scan_id':observed['id'],'max_files':10})
            result=wait(install,root);self.assertTrue(result['coverage_complete'],result);self.assertEqual(result['scan_id'],observed['id'])
            final=d.status(store,observed['id'])['scans'][0];self.assertFalse(processed.intersection(final['work']['paths_this_call']))

    def test_chunk_child_retains_writer_lease_after_parent_releases_its_handle(self):
        from knowledge.execution_lock import ProjectExecutionLock
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);lease=ProjectExecutionLock(root).acquire();child=None
            try:
                with lease_options(lease.fds) as options:
                    child=subprocess.Popen([sys.executable,'-c','import sys;print("ready",flush=True);sys.stdin.readline()'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,**options)
                self.assertEqual(child.stdout.readline().strip(),b'ready');lease.close()
                with self.assertRaisesRegex(KnowledgeError,'project-writer-busy'):ProjectExecutionLock(root).acquire()
                child.stdin.close();child.wait(timeout=10)
                acquired=ProjectExecutionLock(root).acquire();acquired.close()
            finally:
                lease.close()
                if child:
                    if child.poll() is None:child.kill();child.wait(timeout=10)
                    child.stdin.close();child.stdout.close()

    def test_bulk_queue_index_bounds_queue_reads_and_preserves_actual_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            install,root=fixture(tmp,80);store=upgraded(root);queries=[]
            original=store.connection
            @contextlib.contextmanager
            def traced(*args,**kwargs):
                with original(*args,**kwargs) as db:
                    db.set_trace_callback(queries.append);yield db
            with patch.object(store,'connection',traced):value=d.scan(store,max_files=1000)
            self.assertTrue(value['complete']);self.assertEqual(len(store.status()['queue']),81)
            full_queue_reads=[q for q in queries if 'FROM QUEUE' in q.upper() and 'WHERE' not in q.upper()]
            self.assertLess(len(full_queue_reads),20,full_queue_reads[:20])

    def test_helper_continues_after_first_failure_and_preserves_safe_positive_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            install,root=fixture(tmp,9);(root/'bad.json').write_bytes(b'\xff')
            store=upgraded(root)
            first=d.scan(store,max_files=2)
            self.assertEqual(first['counters']['failed_files'],1)
            self.assertGreater(first['work']['remaining_files'],2)
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(run(root,install/'logs',scan_id=first['id'],max_files=2),2)
            value=read_json(install/'logs/last-result.json');counts=value['counters']
            self.assertEqual(value['state'],'COMPLETED_WITH_GAPS');self.assertEqual(counts['remaining_files'],0);self.assertEqual(counts['failed_files'],1)
            self.assertGreater(counts['processed_files'],2);self.assertGreater(len(store.status()['queue']),2)
            self.assertFalse(store.export()['records']['claims']);self.assertIsNone(value['reconciliation']['proposal'])
            self.assertEqual(counts['eligible_files'],sum(counts[k] for k in ('processed_files','partially_processed_files','failed_files','remaining_files')))

    def test_fresh_is_a_new_execution_and_resume_does_not_repeat_committed_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            install,root=fixture(tmp,5);store=upgraded(root);output=install/'logs'
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ScanError,'max-calls'):run(root,output,max_files=1,max_calls=1)
                first=read_json(output/'checkpoint.json')['scan_id'];self.assertEqual(run(root,output,max_files=2),0)
                old=read_json(output/'last-result.json');queue=len(store.status()['queue'])
                self.assertEqual(old['id'],first);self.assertEqual(run(root,output,max_files=2,fresh=True),0)
            new=read_json(output/'last-result.json');self.assertNotEqual(new['id'],first);self.assertEqual(len(store.status()['queue']),queue)
            self.assertEqual(len(d.status(store)['scans']),2)

    def test_corrupt_checkpoint_stops_before_subprocess(self):
        with tempfile.TemporaryDirectory() as tmp:
            install,root=fixture(tmp,2);upgraded(root);output=install/'logs'
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(ScanError):run(root,output,max_files=1,max_calls=1)
            checkpoint=read_json(output/'checkpoint.json');checkpoint['scan_id']='corrupt';write_json(output/'checkpoint.json',checkpoint)
            with patch('knowledge.auto_init.subprocess.run') as child:
                with self.assertRaisesRegex(ScanError,'Corrupt checkpoint'):run(root,output)
                child.assert_not_called()

    def test_durable_cancel_and_resume_without_duplicate_workers(self):
        with tempfile.TemporaryDirectory() as tmp:
            install,root=fixture(tmp,20)
            first=execute('knowledge-init',install,root,{'max_files':1})
            second=execute('knowledge-init',install,root,{'max_files':1})
            self.assertEqual(first['job'],second['job'])
            execute('knowledge-init',install,root,{'action':'cancel'})
            cancelled=wait(install,root)
            self.assertIn(cancelled['state'],('CANCELLED','PARTIAL'))
            if cancelled['state']=='CANCELLED':
                execute('knowledge-init',install,root,{'resume':True,'max_files':4});finished=wait(install,root);self.assertTrue(finished['coverage_complete'],finished)
            self.assertFalse(Store(root).export()['records']['claims'])

    def test_atomic_metadata_reader_and_writer_do_not_share_incomplete_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'job.json';write_json(path,{'n':0,'body':'x'*1000});errors=[]
            def writer():
                try:
                    for n in range(50):write_json(path,{'n':n,'body':'x'*1000})
                except Exception as error:errors.append(error)
            thread=threading.Thread(target=writer);thread.start()
            while thread.is_alive():self.assertEqual(len(read_json(path)['body']),1000)
            thread.join();self.assertFalse(errors,errors)


class SemanticSafety(unittest.TestCase):
    def test_test_double_requires_opt_in_and_cannot_create_confirmed_semantic_claims(self):
        provider={'endpoint':'http://localhost:12345/v1/chat/completions','model':'synthetic','evidence':'test-double'}
        with self.assertRaisesRegex(KnowledgeError,'authorization-required'):providers.semantic_preflight(provider)
        self.assertTrue(providers.semantic_preflight(provider,True)['test_mode'])
        with self.assertRaisesRegex(KnowledgeError,'cannot-produce-confirmed'):
            providers.semantic_preflight(provider,True,[{'operations':[{'kind':'claims','payload':{'status':'CONFIRMED'}}]}])

    def test_bound_semantic_candidates_cannot_prepare_under_changed_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            install,root=fixture(tmp,1);execute('knowledge-init',install,root,{});wait(install,root)
            plan=execute('knowledge-candidates-push',install,root,{});execute('knowledge-candidates-push',install,root,{'approve':plan['fingerprint']})
            store=Store(root);claim=store.export()['records']['claims'][0];state=store.status()['revisions'][claim['id']];source=d.inventory(root)
            value=lifecycle.batch([lifecycle.op('retire','claims',claim['id'],state['revision'])],'Explicit synthetic review',
                                  {'identity':source['identity'],'revision':source['revision'],'kind':source['snapshot_kind']})
            execute('knowledge-candidates-update',install,root,{'candidates':[value],'allow_test_double':True})
            old=store.prepare();self.assertTrue(old['ok'])
            config=read_json(install/'config/provider.json');config['provider']['model']='different';write(install/'config/provider.json',config)
            new=store.prepare();self.assertFalse(new['ok']);self.assertEqual(new['blocked'][0]['code'],'semantic-provider-drift-reanalysis-required')
            with self.assertRaises(KnowledgeError):store.apply(old['fingerprint'],old['fingerprint'])
            self.assertEqual(store.status()['revisions'][claim['id']]['lifecycle'],'active')


class McpOperations(unittest.TestCase):
    def test_real_transport_capabilities_status_diagnostics_and_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            install,root=fixture(tmp,4);peer=Wire([sys.executable,'-I','-B','-m','knowledge.machine_mcp','--installation',install],roots=lambda:[root])
            try:
                peer.initialize();names={t['name'] for t in peer.request(102,'tools/list')['tools']}
                from knowledge.machine_mcp import TOOL_NAMES
                self.assertEqual(names,TOOL_NAMES)
                capabilities=peer.tool('knowledge_capabilities');self.assertTrue(capabilities['ok']);self.assertIn('cancel',capabilities['scan_actions'])
                denied=peer.tool('knowledge_semantic_preflight');self.assertEqual(denied['error'],'test-double-semantic-authorization-required')
                state=peer.tool('knowledge_scan',action='start',max_files=2)
                deadline=time.monotonic()+30
                while state['state'] in ('STARTING','RUNNING') and time.monotonic()<deadline:
                    time.sleep(.05);state=peer.tool('knowledge_scan',action='status')
                self.assertTrue(state['coverage_complete'],state)
                rows=peer.tool('knowledge_scan_diagnostics',section='coverage',limit=2);self.assertLessEqual(len(rows['rows']),2);self.assertIsNotNone(rows['next_cursor'])
                source=peer.tool('knowledge_source_read',path='Class0.cs');self.assertTrue(source['ok']);self.assertIn('content_hash',source)
                blocked=peer.tool('knowledge_source_read',path='../outside.cs');self.assertFalse(blocked['ok'])
                prepared=peer.tool('knowledge_plan');self.assertEqual(prepared['state'],'AWAITING_EXACT_APPROVAL');self.assertFalse(Store(root).export()['records']['claims'])
                wrong=peer.tool('knowledge_plan',action='apply',approve='sha256:'+'0'*64);self.assertFalse(wrong['ok'])
                applied=peer.tool('knowledge_plan',action='apply',approve=prepared['fingerprint']);self.assertTrue(applied['ok'])
                self.assertTrue(Store(root).export()['records']['claims'])
            finally:peer.close()
