"""Controlled byte-format baseline/enabled runs using the same installed broker."""
import hashlib,json,sys,tempfile,time
from pathlib import Path
from knowledge import operations as op
from harness.runtime import configure
assert Path(op.__file__).is_relative_to(Path(sys.prefix))
sys.path.insert(0,'/workspace/Knowledge-/tests')
from test_persistent_instructions import setup_fixture,worker,ingress,binding
from test_persistent_semantics import local_normalizer,decision
raw=b'\xef\xbb\xbfinitial\r\n';expected=b'\xef\xbb\xbfchanged\r\n';rows={}
with tempfile.TemporaryDirectory(prefix='persistent-format-comparison-') as tmp:
 root,shared,cfg=setup_fixture(tmp)
 with local_normalizer([decision()]) as normalizer:
  cfg['memory'].update(enabled=False,teaching_mode='local-model',normalizer=normalizer,bindings=[binding()]);configure(root,cfg)
  (root/'Feature.cs').write_bytes(raw)
  began=time.monotonic();baseline=worker(root,patch='changed\n');elapsed=time.monotonic()-began
  actual=(root/'Feature.cs').read_bytes()
  rows['baseline']={'broker_ok':baseline['result']['ok'],'byte_requirement_met':actual==expected,'bytes_hex':actual.hex(),'elapsed_seconds':elapsed,'selected_records':0,'context_bytes':0}
  cfg['memory']['enabled']=True;configure(root,cfg)
  taught=ingress(root,'For future edits preserve the existing byte format unless the current task explicitly changes it.')
  assert taught['saved'] and taught['status']=='active',taught
 # Both the teacher process and normalization endpoint have ended.
 (root/'Feature.cs').write_bytes(raw)
 began=time.monotonic();enabled=worker(root,patch='changed\n');elapsed=time.monotonic()-began
 actual=(root/'Feature.cs').read_bytes();traces=enabled['actions']['operation']['memory_traces']
 rows['enabled']={'broker_ok':enabled['result']['ok'],'byte_requirement_met':actual==expected,'bytes_hex':actual.hex(),'elapsed_seconds':elapsed,
  'selected_records':sum(len(t.get('selected',[])) for t in traces),'context_bytes':sum(t.get('selected_bytes',0) for t in traces),'record_id':taught['id'],'revision':taught['revision']}
 assert rows['baseline']['broker_ok'] and not rows['baseline']['byte_requirement_met']
 assert rows['enabled']['broker_ok'] and rows['enabled']['byte_requirement_met']
 print(json.dumps({'ok':True,'type':'actual installed ingress and fresh broker processes; local-normalizer protocol double',
  'installed_prefix':sys.prefix,'initial_bytes_hex':raw.hex(),'expected_bytes_hex':expected.hex(),'same_reset_fixture':True,
  'model_tokens':None,'performance_benefit':'NOT_ESTABLISHED','runs':rows},indent=2))
