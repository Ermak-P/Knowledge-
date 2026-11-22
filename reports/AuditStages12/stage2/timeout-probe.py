import json,sys,tempfile,time
from pathlib import Path
sys.path.insert(0,'/workspace/Knowledge-/tests')
from p2_fixtures import http_provider
from test_persistent_instructions import setup_fixture
from harness.host_ingress import message,read_session,guard
from harness.runtime import configure
from knowledge.util import KnowledgeError
with tempfile.TemporaryDirectory() as tmp,http_provider(None,raw=lambda body:time.sleep(1.6) or {'choices':[]}) as endpoint:
 root,shared,cfg=setup_fixture(tmp);cfg['memory'].update(teaching_mode='local-model',normalizer={'endpoint':endpoint,'model':'timeout-double','timeout':1});configure(root,cfg)
 started=time.monotonic();result=message(root,'Do not start services. Fix a typo.','timeout','m');elapsed=time.monotonic()-started
 assert result['ok'] and result['degraded'] and read_session(root,'timeout')['restrictions']==['no-service-start']
 try:guard(root,'timeout','patch');raise AssertionError('effect permitted')
 except KnowledgeError as error:assert error.code=='host-controls-unresolved'
 print(json.dumps({'status':'PASS','kind':'real HTTP deadline; protocol double; installed ingress','elapsed':elapsed,'receipt':result,'pending':read_session(root,'timeout')['pending']},indent=2))
