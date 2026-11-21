"""Actual trusted ingress/SQLite; deliberately wrong model and Docker doubles."""
import json,sys,tempfile
from pathlib import Path
sys.path.insert(0,'/workspace/Knowledge-/tests')
from test_persistent_r1 import dependency
from test_persistent_instructions import setup_fixture,ingress
from test_persistent_semantics import local_normalizer,decision
from test_persistent_reviewed import DockerContract
from harness.runtime import configure
from harness.instructions import execute_procedure
from knowledge.operations import OperationalStore
from knowledge.util import KnowledgeError
text='Remember Kafka: you may not start the container. Only check readiness.'
with tempfile.TemporaryDirectory() as tmp,local_normalizer([decision(authorize_recovery=True,permission_quote='you may not start the container')]) as normalizer:
 root,shared,cfg=setup_fixture(tmp);p,b=dependency()
 cfg['memory'].update(teaching_mode='local-model',normalizer=normalizer,bindings=[b],allowed_procedures=[p])
 configure(root,cfg);saved=ingress(root,text)
 record=OperationalStore(root,'project',shared).records()['records'][0]
 contract=DockerContract(root,after_start=True);error=None
 try:execute_procedure(contract,'probe',record,{'shared_root':str(shared)})
 except KnowledgeError as e:error=e.code
 print(json.dumps({'model':'deliberately wrong protocol double','Docker':'command response contract double; no real Docker effect',
 'source':text,'receipt':saved,'persisted_grant':record['recovery_authorized'],'startup_calls':len(contract.starts()),
 'command_calls':contract.commands,'outcome':error or 'readiness-verified'},indent=2))
