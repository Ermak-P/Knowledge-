import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
sys.path.insert(0,'/workspace/Knowledge-/tests')
from fixtures import addition
from knowledge import lifecycle as life
from knowledge.store import Store
from knowledge.util import canonical_json
p=argparse.ArgumentParser();p.add_argument('phase');a=p.parse_args();root=Path('/tmp/audit12-existing-project');root.mkdir(exist_ok=True);s=Store(root)
if a.phase=='setup':
 (root/'Fixture.cs').write_text('public class DurableKnowledge {}\n')
 s.init();life.upgrade(s,life.upgrade_preview(s)['fingerprint'])
 value=addition('durable.rule','DurableKnowledge preserves the approved behavior.');value['records']['evidence'][0]['content_hash']='sha256:'+hashlib.sha256((root/'Fixture.cs').read_bytes()).hexdigest()
 s.submit(value);v=s.prepare();s.apply(v['fingerprint'],v['fingerprint']);s.acknowledge(v['fingerprint'])
 record=s.lookup('claims','durable.rule')['record'];record['statement']='DurableKnowledge preserves the revised approved behavior.'
 s.submit(life.batch([life.op('update','claims','durable.rule',1,record)],'Reviewed baseline correction'));v=s.prepare();s.apply(v['fingerprint'],v['fingerprint']);s.acknowledge(v['fingerprint'])
 s.submit(addition('durable.pending','Pending independent review.'));s.prepare()
 Path('/tmp/audit12-existing-before.json').write_text(canonical_json({'export':s.export(),'status':s.status(),'db_sha256':hashlib.sha256(s.path.read_bytes()).hexdigest()}))
else:
 import knowledge
 assert importlib.util.find_spec('harness') is None and importlib.util.find_spec('mcp') is None
 before=json.loads(Path('/tmp/audit12-existing-before.json').read_text());assert s.export()==before['export'];assert s.status()==before['status']
 value=s.context('DurableKnowledge');assert len(value['claims'])==1;assert value['claims'][0]['revision']==2
 assert hashlib.sha256(s.path.read_bytes()).hexdigest()==before['db_sha256']
 print(json.dumps({'status':'PASS','installed':knowledge.__file__,'harness_installed':False,'mcp_installed':False,'baseline_store_unchanged':True,'history_preserved':len(before['export']['history']),'receipts_preserved':len(before['export']['receipts']),'queue':before['status']['queue'],'plans':before['status']['plans'],'claim_revision':value['claims'][0]['revision'],'db_sha256':before['db_sha256']},indent=2))
