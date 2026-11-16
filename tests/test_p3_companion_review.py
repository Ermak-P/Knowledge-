"""P3-R1/R2: real runner/MCP effects with deterministic filesystem scheduling."""
import asyncio,copy,json,os,runpy,sys,tempfile,unittest,uuid
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from knowledge.store import Store
from knowledge.util import KnowledgeError,fingerprint,digest
from harness import companion,engine,runtime
from harness.runtime import Journal,Lease,configure
from p2_fixtures import project,configuration,task,http_provider,FixtureProvider
from fixtures import addition

OBSERVATIONS=[]

def write(path,value):path.write_bytes((json.dumps(value,ensure_ascii=False)+'\n').encode('utf-8'))

@contextmanager
def fixture(initial=None,original=b'{"model":"original-approved"}\n'):
    provider=FixtureProvider()
    with tempfile.TemporaryDirectory(prefix='P3 authority Ω ') as tmp,http_provider(provider) as endpoint:
        base=Path(tmp);root=project(base/'Project');policy=configuration(endpoint)
        policy['recipes']['audit']=copy.deepcopy(policy['recipes']['test']);configure(root,policy,True)
        (root/'Fixture.cs').write_bytes(b'public class RetainedFixture {}\n')
        store=Store(root);store.submit(addition('companion.retained','Synthetic source declares RetainedFixture.'))
        approval=store.prepare();store.apply(approval['fingerprint'],approval['fingerprint']);store.acknowledge(approval['fingerprint'])
        store.submit(addition('companion.pending','Synthetic pending observation of RetainedFixture.'))
        if original is not None:(root/'opencode.json').write_bytes(original)
        (base/'global-config.json').write_bytes(b'PRESERVE GLOBAL')
        write(root/'task.json',initial or task(kind='read-only'))
        plan=companion.preview(root,'task.json');write(base/'install-preview.json',plan);companion.apply(root,plan['preview'],plan['fingerprint'])
        yield root,provider

def effects(root,provider):
    j=Journal(root);runs=j.runs();actions=[a for r in runs for a in j.actions(r['id']).values()]
    return {'provider_calls':len(provider.requests),'runs':len(runs),'tools':len(actions),'recipe_processes':sum(bool(a.get('process_spec')) for a in actions)}

def mutate(root,kind):
    marker=root/'.harness/companion.json';value=json.loads(marker.read_bytes())
    if kind=='configuration':
        p=root/'.harness/runner.json';c=json.loads(p.read_bytes());c['provider']['model']='changed-while-waiting';write(p,c);return
    if kind=='host':
        p=root/'opencode.json';c=json.loads(p.read_bytes());c['model']='changed-while-waiting';write(p,c);return
    if kind in ('writable','recipes','enrollment'):
        replacement=task()
        if kind=='writable':replacement['writable'].append('Other.cs')
        if kind=='recipes':replacement['recipes'].append('audit')
        path='other-task.json' if kind=='enrollment' else 'task.json'
        write(root/path,replacement);value['tasks']['approved_task']={'path':path,'digest':digest(replacement)}
    elif kind=='identity':value['installation_id']=uuid.uuid4().hex
    elif kind=='runtime':value['python']='unapproved-python'
    elif kind=='root':value['project']='different-project'
    elif kind=='version':value['version']=999
    else:raise AssertionError(kind)
    write(marker,value)

def guarded_mcp(root,*,replace_task=False,before_ownership=None):
    """Execute the configured module, instrumenting only a scheduling seam.

    Provider decisions, start/drive, tools, leases, processes and MCP are real.
    The wrapper delegates the exact configured module/arguments after installing
    the same one-read or pre-acquisition scheduling probe as the API tests.
    """
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    entry=json.loads((root/'opencode.json').read_bytes())['mcp']['servers']['harness_companion']['command']
    assert entry[1:4]==['-I','-m','harness.host_mcp']
    control=root.parent/'mcp-scheduling.json';write(control,{'replace_task':replace_task,'before_ownership':before_ownership,'replacement':task()})
    code='''import sys,json,runpy
from pathlib import Path
from harness import companion,engine
from harness.runtime import Lease as ActualLease
settings=json.loads(Path(sys.argv[1]).read_bytes());root=Path(sys.argv[2]);trigger=root.parent/'schedule-fired'
if settings['replace_task']:
 original=companion._read;reads=[]
 def scheduled(path):
  data=original(path)
  if path==root/'task.json':
   reads.append(True)
   if len(reads)==settings['replace_task']:
    path.write_bytes(json.dumps(settings['replacement']).encode('utf-8'));trigger.write_bytes(b'fired')
  return data
 companion._read=scheduled
if settings['before_ownership']:
 class ScheduledLease(ActualLease):
  def __enter__(self):
   if not trigger.exists():
    with ActualLease(self.journal):
     marker=root/'.harness/companion.json';value=json.loads(marker.read_bytes())
     if settings['before_ownership']=='configuration':
      p=root/'.harness/runner.json';value=json.loads(p.read_bytes());value['provider']['model']='changed-while-waiting'
     else:p=marker;value['installation_id']='new-installation'
     p.write_bytes(json.dumps(value).encode('utf-8'));trigger.write_bytes(b'fired')
   return super().__enter__()
 engine.Lease=ScheduledLease
sys.argv=['configured-companion',*sys.argv[3:]]
runpy.run_module('harness.host_mcp',run_name='__main__')
'''
    async def execute():
        async with asyncio.timeout(120):
            async with stdio_client(StdioServerParameters(command=entry[0],args=['-I','-c',code,str(control),str(root),*entry[4:]])) as (read,writer):
                async with ClientSession(read,writer,read_timeout_seconds=timedelta(seconds=90)) as session:
                    await session.initialize();answer=await session.call_tool('harness_run',{'task_name':'approved_task'})
                    return json.loads(answer.content[0].text)
    answer=asyncio.run(execute());assert (root.parent/'schedule-fired').read_bytes()==b'fired'
    return answer

class CompanionReviewTests(unittest.TestCase):
    def assert_no_effects(self,root,provider,before,policy,knowledge,label,allowed_runs=(0,)):
        self.assertEqual((root/'Feature.cs').read_bytes(),before)
        self.assertEqual((root/'.harness/runner.json').read_bytes(),policy)
        self.assertEqual(Store(root).export(),knowledge)
        actual=effects(root,provider);self.assertIn(actual['runs'],allowed_runs)
        self.assertEqual({k:v for k,v in actual.items() if k!='runs'},{'provider_calls':0,'tools':0,'recipe_processes':0})
        for run in Journal(root).runs():self.assertEqual(run['task']['kind'],'read-only')
        OBSERVATIONS.append({'case':label,'status':'PASS',**actual,'mcp_transport_processes':1 if '/configured-MCP-' in label else 0,'application_unchanged':True,'policy_unchanged':True,'nonempty_canonical_and_queue_unchanged':True})

    def test_task_replacement_after_validated_read_cannot_gain_coding_authority(self):
        for read_index in (1,2):
            with self.subTest(read_index=read_index),fixture() as (root,provider):
                source=(root/'Feature.cs').read_bytes();policy=(root/'.harness/runner.json').read_bytes();knowledge=Store(root).export();original=companion._read;reads=[];fired=[]
                def scheduled(path):
                    raw=original(path)
                    if path==root/'task.json':
                        reads.append(True)
                        if len(reads)==read_index:fired.append(True);write(path,task())
                    return raw
                with patch.object(companion,'_read',scheduled):
                    try:answer=companion.run_task(root,'approved_task')
                    except KnowledgeError:answer={'ok':False}
                self.assertFalse(answer['ok']);self.assertEqual(fired,[True])
                self.assert_no_effects(root,provider,source,policy,knowledge,'P3-R1/API-read-replacement-'+str(read_index),allowed_runs=(0,1))

    def test_changed_scope_enrollment_or_policy_at_ownership_is_rejected(self):
        for kind in ('writable','recipes','enrollment','identity','configuration','host','runtime','root','version'):
            with self.subTest(kind=kind),fixture(initial=task() if kind in ('writable','recipes') else None) as (root,provider):
                source=(root/'Feature.cs').read_bytes();knowledge=Store(root).export();fired=[];expected=[]
                class ScheduledLease(Lease):
                    def __enter__(lease):
                        with Lease(lease.journal):mutate(root,kind);fired.append(True);expected.append((root/'.harness/runner.json').read_bytes())
                        return super().__enter__()
                with patch.object(engine,'Lease',ScheduledLease),self.assertRaises(KnowledgeError) as error:companion.run_task(root,'approved_task')
                self.assertNotEqual(error.exception.code,'project-writer-busy');self.assertEqual(fired,[True])
                self.assert_no_effects(root,provider,source,expected[0],knowledge,'P3-R1/owned-'+kind)

    def test_configured_mcp_rejects_read_replacement_before_provider_or_tools(self):
        for read_index in (1,2):
            with self.subTest(read_index=read_index),fixture() as (root,provider):
                before=(root/'Feature.cs').read_bytes();policy=(root/'.harness/runner.json').read_bytes();knowledge=Store(root).export()
                answer=guarded_mcp(root,replace_task=read_index);self.assertFalse(answer['ok'])
                self.assert_no_effects(root,provider,before,policy,knowledge,'P3-R1/configured-MCP-read-replacement-'+str(read_index),allowed_runs=(0,1))

    def test_configured_mcp_rechecks_installation_and_config_at_ownership(self):
        for kind in ('identity','configuration'):
            with self.subTest(kind=kind),fixture() as (root,provider):
                before=(root/'Feature.cs').read_bytes();knowledge=Store(root).export()
                answer=guarded_mcp(root,before_ownership=kind);self.assertFalse(answer['ok'])
                self.assert_no_effects(root,provider,before,(root/'.harness/runner.json').read_bytes(),knowledge,'P3-R1/configured-MCP-owned-'+kind)

    def test_interrupted_companion_run_rechecks_authority_before_resume(self):
        class Interrupted(BaseException):pass
        with fixture() as (root,provider):
            before=(root/'Feature.cs').read_bytes();knowledge=Store(root).export()
            def interrupted(phase):
                if phase=='provider-intent':raise Interrupted()
            with patch.object(runtime,'fault',interrupted),self.assertRaises(Interrupted):companion.run_task(root,'approved_task')
            run=Journal(root).runs()[0];mutate(root,'identity');answer=engine.resume(root,run['id'])
            self.assertFalse(answer['ok']);self.assertEqual(answer['error'],'host-enrollment-changed-review-required')
            self.assertFalse(provider.requests);self.assertEqual((root/'Feature.cs').read_bytes(),before);self.assertEqual(Store(root).export(),knowledge)
            self.assertFalse(Journal(root).actions(run['id']));OBSERVATIONS.append({'case':'P3-R1/resume-authority','status':'PASS','provider_calls':0,'tools':0,'recipe_processes':0,'unknown_request_intent_preserved':True})
            retained=Journal(root).load(run['id'])['requests'][0];self.assertEqual(retained['state'],'inflight');self.assertEqual(retained['usage']['coverage'],'unknown')

    def test_remove_rechecks_marker_after_waiting_for_real_ownership(self):
        for window in ('waiting','after-marker-read'):
            with self.subTest(window=window),fixture() as (root,provider):
                plan=companion.preview(root,remove=True);before=(root/'opencode.json').read_bytes();fired=[];changed=[]
                def replace():
                    mutate(root,'identity');fired.append(True);changed.append((root/'.harness/companion.json').read_bytes())
                class ScheduledLease(Lease):
                    def __enter__(lease):
                        with Lease(lease.journal):replace()
                        return super().__enter__()
                original=companion._installed
                def scheduled(project):
                    result=original(project);replace();return result
                seam=patch.object(companion,'Lease',ScheduledLease) if window=='waiting' else patch.object(companion,'_installed',scheduled)
                with seam,self.assertRaisesRegex(KnowledgeError,'stale-companion-preview'):companion.apply(root,plan['preview'],plan['fingerprint'])
                self.assertEqual(fired,[True]);self.assertEqual((root/'opencode.json').read_bytes(),before)
                self.assertEqual((root/'.harness/companion.json').read_bytes(),changed[0]);self.assertFalse(list((root/'.harness').glob('companion-removed-*')))
                OBSERVATIONS.append({'case':'P3-R2/owned-marker-change-'+window,'status':'PASS','host_unchanged':True,'new_marker_retained':True})

    def test_remove_approval_rejects_changed_restore_bytes_or_absence(self):
        for kind in ('replacement','absence','absence-to-file','same-json-new-bytes'):
            with self.subTest(kind=kind),fixture(original=None if kind=='absence-to-file' else b'{"model":"original-approved"}\n') as (root,provider):
                plan=companion.preview(root,remove=True);target=root/'opencode.json';before=target.read_bytes();marker=root/'.harness/companion.json';installed=json.loads(marker.read_bytes())
                if kind in ('replacement','absence-to-file'):installed.update(original={'model':'unreviewed-replacement'},original_bytes='{"model":"unreviewed-replacement"}')
                elif kind=='absence':installed.update(original=None,original_bytes=None)
                else:installed['original_bytes']='{ "model": "original-approved" }\r\n'
                write(marker,installed);state=marker.read_bytes()
                with self.assertRaises(KnowledgeError):companion.apply(root,plan['preview'],plan['fingerprint'])
                self.assertEqual(target.read_bytes(),before);self.assertEqual(marker.read_bytes(),state);self.assertFalse(list(marker.parent.glob('companion-removed-*')))
                OBSERVATIONS.append({'case':'P3-R2/restore-'+kind,'status':'PASS','host_unchanged':True,'marker_unchanged':True})

    def test_remove_approval_rejects_changed_installation_tasks_host_and_versions(self):
        for kind in ('identity','enrollment','host','version','runtime','root'):
            with self.subTest(kind=kind),fixture() as (root,provider):
                plan=companion.preview(root,remove=True);mutate(root,kind);target=root/'opencode.json';before=target.read_bytes();marker=root/'.harness/companion.json';state=marker.read_bytes()
                with self.assertRaises(KnowledgeError):companion.apply(root,plan['preview'],plan['fingerprint'])
                self.assertEqual(target.read_bytes(),before);self.assertEqual(marker.read_bytes(),state)
                OBSERVATIONS.append({'case':'P3-R2/stale-'+kind,'status':'PASS','host_unchanged':True,'marker_unchanged':True})

    def test_valid_remove_preserves_exact_unicode_bytes_absence_history_and_global(self):
        original='{\r\n  "model": "Проверка Ω", "custom": {"untouched":true}\r\n}\r\n'.encode('utf-8')
        for old,legacy in ((original,False),(None,False),(original,True)):
            with self.subTest(absent=old is None,legacy=legacy),fixture(original=old) as (root,provider):
                marker=root/'.harness/companion.json'
                if legacy:
                    value=json.loads(marker.read_bytes());value.pop('installation_id');write(marker,value)
                installed=marker.read_bytes();plan=companion.preview(root,remove=True);companion.apply(root,plan['preview'],plan['fingerprint'])
                target=root/'opencode.json';self.assertEqual(target.read_bytes() if target.exists() else None,old);self.assertFalse(marker.exists())
                self.assertEqual(next(marker.parent.glob('companion-removed-*')).read_bytes(),installed)
                if old is not None:self.assertEqual(next((marker.parent/'host-backups').rglob('opencode.json')).read_bytes(),old)
                self.assertEqual((root.parent/'global-config.json').read_bytes(),b'PRESERVE GLOBAL')
                OBSERVATIONS.append({'case':'P3-R2/exact-valid-remove','status':'PASS','original_absent':old is None,'legacy_marker':legacy,'exact_bytes_and_history':True,'global_unchanged':True})
                # Even reusing the exact original install plan creates a new
                # installation; the previous removal approval cannot remove it.
                install=json.loads((root.parent/'install-preview.json').read_bytes());companion.apply(root,install['preview'],install['fingerprint'])
                newer=marker.read_bytes();live=target.read_bytes();self.assertNotEqual(newer,installed)
                with self.assertRaisesRegex(KnowledgeError,'stale-companion-preview'):companion.apply(root,plan['preview'],plan['fingerprint'])
                self.assertEqual(target.read_bytes(),live);self.assertEqual(marker.read_bytes(),newer)
                fresh=companion.preview(root,remove=True);companion.apply(root,fresh['preview'],fresh['fingerprint'])
                self.assertEqual(target.read_bytes() if target.exists() else None,old)
                OBSERVATIONS.append({'case':'P3-R2/stale-remove-after-reinstall','status':'PASS','new_installation_retained':True,'same_install_preview_reused':True})

    def test_unknown_preview_version_or_operation_refuses_before_mutation(self):
        for field,value in (('version',1),('version',999),('operation','unreviewed-operation')):
            with self.subTest(field=field,value=value),fixture() as (root,provider):
                plan=companion.preview(root,remove=True)['preview'];plan[field]=value;host=(root/'opencode.json').read_bytes();marker=(root/'.harness/companion.json').read_bytes()
                with self.assertRaises(KnowledgeError):companion.apply(root,plan,fingerprint(plan))
                self.assertEqual((root/'opencode.json').read_bytes(),host);self.assertEqual((root/'.harness/companion.json').read_bytes(),marker)

    def test_install_preview_rechecks_task_config_and_existing_marker(self):
        for kind in ('task','config','marker'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
                root=project(tmp);configure(root,configuration('http://127.0.0.1/v1/chat/completions'),True);write(root/'task.json',task(kind='read-only'));plan=companion.preview(root,'task.json')
                if kind=='task':write(root/'task.json',task())
                elif kind=='config':
                    p=root/'.harness/runner.json';value=json.loads(p.read_bytes());value['provider']['model']='changed';write(p,value)
                else:write(root/'.harness/companion.json',{'new':'installation'})
                with self.assertRaises(KnowledgeError):companion.apply(root,plan['preview'],plan['fingerprint'])
                self.assertFalse((root/'opencode.json').exists())
