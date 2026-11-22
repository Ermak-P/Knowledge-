import sys,json,tempfile,hashlib
from pathlib import Path
sys.path.insert(0,'/workspace/Knowledge-/tests')
from fixtures import addition
from p2_fixtures import project,configuration,http_provider,final
from knowledge.store import Store
from harness.runtime import configure
from harness.engine import start
from test_p4 import p4task
bodies=[]
with tempfile.TemporaryDirectory() as tmp,http_provider(lambda body:bodies.append(body) or final()) as endpoint:
 root=project(tmp);store=Store(root);store.init();value=addition('legacy.feature','Feature source requires an unverified historical threshold.');store.submit(value);p=store.prepare();store.apply(p['fingerprint'],p['fingerprint']);store.acknowledge(p['fingerprint'])
 configure(root,configuration(endpoint),True);t=p4task();t.update(kind='read-only',writable=[],recipes=[])
 result=start(root,t);knowledge=json.loads(bodies[0]['messages'][0]['content'])['knowledge']
 print(json.dumps({'run':result,'architecture':knowledge,'legacy_p1':store.status()['p1']},indent=2))
