"""R1 F1: exact classic metadata, native invocation, authority and compatibility."""
import copy,json,os,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from harness import testing,runtime
from harness.tools import Broker
from knowledge.util import KnowledgeError,digest
from p2_fixtures import http_provider,final
import test_automatic_discovery as automatic

def metadata(**overrides):
 return dict(TargetFramework='',TargetFrameworks='',AssemblyName='LegacyTests',TargetPath='bin/Debug/LegacyTests.dll',TargetFrameworkIdentifier='.NETFramework',TargetFrameworkVersion='v4.7.1',TargetFrameworkProfile='',UsingMicrosoftNETSdk='',**overrides)
class LegacyMetadata(unittest.TestCase):
 def test_exact_review_metadata_resolves_native_moniker_not_synthetic_tfm(self):
  props=metadata();self.assertEqual(testing.properties(json.dumps(dict(Properties=props))),props)
  fw,descriptor=testing.resolve_frameworks(props,host='nt')[0];self.assertEqual(fw,'.NETFramework,Version=v4.7.1');self.assertEqual(descriptor['kind'],'net-framework')
  props['TargetFrameworkProfile']='Client';self.assertTrue(testing.resolve_frameworks(props,host='nt')[0][0].endswith(',Profile=Client'))
  with self.assertRaisesRegex(KnowledgeError,'requires-native-windows'):testing.resolve_frameworks(props,host='posix')
  for field,value in [('TargetFrameworkVersion','v2.0'),('TargetFrameworkIdentifier','Silverlight'),('TargetFrameworkProfile','bad;profile')]:
   bad=copy.deepcopy(props);bad[field]=value
   with self.assertRaisesRegex(KnowledgeError,'unsupported-legacy-test-framework'):testing.resolve_frameworks(bad,host='nt')
 def test_sdk_four_property_receipts_and_old_operations_remain_compatible(self):
  props=dict(TargetFramework='net10.0',TargetFrameworks='',AssemblyName='ExampleTests',TargetPath='bin/ExampleTests.dll')
  self.assertEqual(testing.properties(json.dumps(dict(Properties=props))),props);self.assertEqual(testing.resolve_frameworks(props),[('net10.0',dict(kind='sdk'))])
  props['TargetFramework']=''
  with self.assertRaisesRegex(KnowledgeError,'metadata-revalidation'):testing.resolve_frameworks(props,host='nt')
 def test_legacy_commands_use_broker_target_and_preserve_path_authority(self):
  with tempfile.TemporaryDirectory() as tmp,http_provider(lambda b:final()) as endpoint:
   root=Path(tmp);c,j,r=automatic.AutomaticDiscovery().run_state(root,endpoint);path=r['automatic_tests']['inventory']['projects'][0]['path'];gid='generation';fw,descriptor=testing.resolve_frameworks(metadata(),host='nt')[0];target=root/'bin/LegacyTests.dll';target.parent.mkdir();target.write_bytes(b'unit-only assembly')
   r['automatic_tests']['generations'][gid]=dict(source=digest(r['source']),metadata_version=2,projects={path:dict(frameworks={fw:dict(**descriptor,target=str(target))})})
   with runtime.Lease(j) as lease:
    broker=Broker(j,c,r,lease)
    def recipe(phase):return testing.recipe_for(broker,testing.register(j,r,gid,path,phase,fw if phase!='inspect' else None))
    with patch.object(testing,'os',SimpleNamespace(**{**vars(os),'name':'nt'})),patch('harness.platform.require_framework_runtime'),patch.object(testing,'dotnet',return_value=(sys.executable,{})):
     r['automatic_tests']['generations'][gid].pop('metadata_version');old=recipe('inspect');self.assertEqual(old['argv'][-1],'-getProperty:TargetFramework,TargetFrameworks,AssemblyName,TargetPath');r['automatic_tests']['generations'][gid]['metadata_version']=2
     query=recipe('inspect');self.assertIn('TargetFrameworkVersion',query['argv'][-1]);self.assertFalse(any(a.startswith('-p:TargetFramework=') for a in query['argv']))
     with patch.object(testing,'native_msbuild',return_value=(sys.executable,{})):build=recipe('legacy-build')
     self.assertIn('-t:Build',build['argv']);test=recipe('test');self.assertEqual(test['argv'][1:3],['vstest',str(target)]);self.assertIn('/Framework:'+fw,test['argv']);self.assertFalse(any(a=='--framework' or a.startswith('-p:TargetFramework=') for a in test['argv']));self.assertFalse(test['rerun_safe'])
     (root/'packages.config').write_text('<packages/>')
     with self.assertRaisesRegex(KnowledgeError,'packages-config-requires-trusted'):recipe('legacy-restore')
    native=root/'MSBuild.exe';native.write_bytes(b'unit-only tool placeholder');trusted=copy.deepcopy(c);trusted['recipes']['native']=dict(kind='build',argv=[str(native),'Solution.sln'],result=dict(format='exit',path=''),rerun_safe=False,env={})
    authorized=copy.deepcopy(r['task']);authorized['recipes'].append('native');self.assertIsNone(testing.native_msbuild(trusted,r['task']['recipes']));protected,executables=runtime.recipe_inputs(j.project,trusted,authorized);self.assertIn(runtime.policy_path('MSBuild.exe'),executables)
    with self.assertRaisesRegex(KnowledgeError,'outside-project-root'):testing.assembly_target(j.project,path,dict(AssemblyName='bad',TargetPath=str(root.parent/'foreign.dll')))
