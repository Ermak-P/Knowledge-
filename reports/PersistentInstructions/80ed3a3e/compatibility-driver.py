import hashlib,json,subprocess,sys,tempfile
from pathlib import Path
py='/tmp/persistent-causal-final-knowledge/bin/python'
def run(args,**kwargs):
 p=subprocess.run([str(a) for a in args],capture_output=True,text=True,encoding='utf-8',timeout=30,**kwargs)
 if p.returncode:raise AssertionError(p.stdout+p.stderr)
 return p.stdout
with tempfile.TemporaryDirectory(prefix='knowledge-only-memory-') as tmp:
 base=Path(tmp);root=base/'project';root.mkdir();shared=base/'home/.local/share/knowledge'
 seed='''import sys,json,importlib.util
from pathlib import Path
import knowledge
assert Path(knowledge.__file__).is_relative_to(Path(sys.prefix))
assert importlib.util.find_spec('harness') is None
sys.path.insert(0,'/workspace/Knowledge-/tests')
from fixtures import addition
from knowledge.store import Store
s=Store(sys.argv[1]);s.init();s.submit(addition());p=s.prepare()['fingerprint'];s.apply(p,p);s.acknowledge(p)
print(json.dumps(s.export()['records']))
'''
 before=json.loads(run([py,'-I','-c',seed,root]))
 policy={'shared_root':str(shared),'bindings':[{'aliases':['encoding'],'trigger':{'tool':'patch','name':'*'},'behavior':{'adapter':'preserve-format'}}]}
 saved=json.loads(run([py,'-I','-m','knowledge.cli','memory-ingest','--root',root],input=json.dumps({'text':'Запомни: encoding preservation.','message_id':'project-user','policy':policy},ensure_ascii=False)))
 assert saved['saved'] and saved['scope']=='project'
 plugin=run([py,'-I','-c','import importlib.resources;print(importlib.resources.files("knowledge").joinpath("host/opencode.mjs"))']).strip()
 js=base/'standalone.mjs';js.write_text('''import {pathToFileURL} from 'node:url';
const [plugin,python,root,policy]=process.argv.slice(2);
const hooks=await (await import(pathToFileURL(plugin).href)).default({directory:root,client:{tui:{showToast:async()=>{}}}},{python,backend:'knowledge',policy:JSON.parse(policy)});
const out={message:{role:'user',id:'shared-user'},parts:[{type:'text',text:'Remember for all projects: encoding preservation.'}]};
await hooks['chat.message']({sessionID:'standalone-session',messageID:'shared-user'},out);
console.log(JSON.stringify({synthetic_receipt:out.parts.at(-1).synthetic}));
''',encoding='utf-8')
 assert json.loads(run(['node',js,plugin,py,root,json.dumps(policy)]))['synthetic_receipt']
 dbs=[root/'.knowledge/store.sqlite3',shared/'store.sqlite3'];hashes=[hashlib.sha256(p.read_bytes()).hexdigest() for p in dbs]
 run([py,'-m','pip','install','--no-index','--no-deps','--force-reinstall','/tmp/persistent-rollback-wheels/knowledge_p0-0.4.0rc3-py3-none-any.whl'])
 legacy='from knowledge.store import Store;import sys,json;s=Store(sys.argv[1]);assert s.validate()["ok"];print(json.dumps(s.export()["records"]))'
 assert json.loads(run([py,'-I','-c',legacy,root]))==before
 assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in dbs]==hashes
 run([sys.executable,'/tmp/persistent-causal-final-kit/knowledge-harness-0.5.0rc1/install.py','install','--env','/tmp/persistent-causal-final-knowledge','--profile','knowledge'])
 project=json.loads(run([py,'-I','-m','knowledge.cli','memory-inspect','--root',root]))
 broad=json.loads(run([py,'-I','-m','knowledge.cli','memory-inspect','--root',root,'--scope','shared','--shared-root',shared]))
 assert len(project['records'])==len(broad['records'])==1
 assert project['records'][0]['original']=='Запомни: encoding preservation.'
 assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in dbs]==hashes
 print(json.dumps({'ok':True,'standalone_without_harness':True,'standalone_host_hook':True,'old_reader':'0.4.0rc3','architectural_records_preserved':True,'project_and_shared_memory_preserved':True,'database_hashes_unchanged':hashes,'record_ids':[project['records'][0]['id'],broad['records'][0]['id']]},indent=2))
