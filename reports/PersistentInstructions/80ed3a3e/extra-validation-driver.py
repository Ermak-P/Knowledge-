import concurrent.futures,json,subprocess,sys,tempfile
from pathlib import Path
from unittest.mock import patch
from knowledge import operations as op
from knowledge.util import canonical_json
assert Path(op.__file__).is_relative_to(Path(sys.prefix))
with tempfile.TemporaryDirectory(prefix='memory-extra-validation-') as temporary:
 base=Path(temporary);root=base/'project';root.mkdir();shared=base/'home/.local/share/knowledge'
 binding={'aliases':['encoding'],'trigger':{'tool':'patch','name':'*'},'behavior':{'adapter':'preserve-format'}}
 first=op.teach(root,'accepted before fault',{'type':'user-message','id':'accepted'},shared=shared,binding=binding)
 appended=[False];original=op.append
 def append_then_arm(db,value):
  original(db,value);appended[0]=True
 def fail_after_append(phase):
  if phase=='before-commit' and appended[0]:raise OSError('injected after operational row and event, before commit')
 failed=False
 with patch('knowledge.operations.append',side_effect=append_then_arm),patch('knowledge.store.checkpoint',side_effect=fail_after_append):
  try:op.teach(root,'retriable write',{'type':'user-message','id':'retry'},shared=shared,binding=binding)
  except OSError:failed=True
 assert failed and appended[0]
 store=op.OperationalStore(root,'project',shared)
 assert len(store.records()['records'])==1
 with store.connection() as db:
  assert db.execute('SELECT count(*) FROM operational_history').fetchone()[0]==1
  assert db.execute('SELECT count(*) FROM operational_events').fetchone()[0]==1
 retry=op.teach(root,'retriable write',{'type':'user-message','id':'retry'},shared=shared,binding=binding)
 assert retry['saved'] and len(store.records()['records'])==2
 policy={'shared_root':str(shared),'bindings':[binding]}
 def submit(i):
  request={'text':'Запомни для всех проектов: encoding '+str(i),'message_id':'parallel-'+str(i),'policy':policy}
  p=subprocess.run([sys.executable,'-I','-m','knowledge.cli','memory-ingest','--root',str(root)],input=json.dumps(request,ensure_ascii=False),encoding='utf-8',capture_output=True,timeout=15)
  result=json.loads(p.stdout);assert p.returncode==0 and result['saved'],result
  return result
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:accepted=list(pool.map(submit,range(8)))
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:repeated=list(pool.map(submit,range(8)))
 records=op.OperationalStore(root,'shared',shared).records()['records'];assert len(records)==8
 assert all(r['duplicate'] for r in repeated)
 assert len({r['id'] for r in accepted})==8
 # Wrong machine, OS and exact tool version do not become active instructions.
 scoped=op.teach(root,'platform constrained',{'type':'user-message','id':'scope'},shared=shared,binding=binding,
   applicability={'machine':'machine-a','os':'fixture-os','tools':{'editor':'1.0'}})
 for environment in [{'machine':'machine-b','os':'fixture-os','tools':{'editor':'1.0'}},
                     {'machine':'machine-a','os':'other-os','tools':{'editor':'1.0'}},
                     {'machine':'machine-a','os':'fixture-os','tools':{'editor':'2.0'}}]:
  result=op.lookup(root,{'tool':'patch','name':'Feature.cs'},environment,shared=shared,max_items=16,max_bytes=24000)
  assert not any(r['id']==scoped['id'] for r in result['records'])
 print(json.dumps({'ok':True,'installed_prefix':sys.prefix,'fault_injected_after_append':appended[0],
  'rollback_preserved_prior_commit':True,'retry_saved_once':retry['id'],'independent_cli_processes':16,
  'concurrent_accepted_records':8,'retries_duplicated':0,'utf8_user_wording_preserved':all(r['original'].startswith('Запомни') for r in records),
  'machine_os_tool_mismatches_rejected':True,'record_ids':[r['id'] for r in records]},indent=2))
