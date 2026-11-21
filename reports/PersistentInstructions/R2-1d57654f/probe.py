"""Actual ingress/SQLite; intentionally wrong model and Docker command doubles."""
import json,sys,tempfile
from pathlib import Path
sys.path.insert(0,'/workspace/Knowledge-/tests')
from test_persistent_r2 import CONFLICTS
from test_persistent_r1 import dependency
from test_persistent_instructions import setup_fixture,ingress
from test_persistent_semantics import local_normalizer,decision
from test_persistent_reviewed import DockerContract
from knowledge.operations import OperationalStore
from knowledge.startup_authorization import clauses,startup,restriction
from knowledge.util import KnowledgeError
from harness.runtime import configure
from harness.host_ingress import read_session
from harness.instructions import execute_procedure
rows=[]
for text,quote in CONFLICTS:
 with tempfile.TemporaryDirectory() as tmp,local_normalizer([decision(authorize_recovery=True,permission_quote=quote,current_start='clear-denial',restriction_quote=quote)]) as normalizer:
  root,shared,cfg=setup_fixture(tmp);p,b=dependency()
  cfg['memory'].update(teaching_mode='local-model',normalizer=normalizer,bindings=[b],allowed_procedures=[p],requirements=[{'trigger':{'tool':'recipe','name':'test'},'dependency':'guard'}])
  configure(root,cfg);saved=ingress(root,text)
  record=OperationalStore(root,'project',shared).records()['records'][0]
  session=read_session(root,'teaching');contract=DockerContract(root,after_start=True)
  contract.r['current_restrictions']=session['restrictions'];error=None
  try:execute_procedure(contract,'probe',record,{'shared_root':str(shared)})
  except KnowledgeError as e:error=e.code
  rows.append({'source':text,'permission_quote':quote,'clauses':clauses(text),'direct':startup(text,b,True,quote),
   'current_restriction':restriction(text,'clear-denial'),'original_preserved':record['original']==text,
   'persisted_grant':record['recovery_authorized'],'startup_calls':len(contract.starts()),'session_restrictions':session['restrictions'],
   'receipt':saved,'outcome':error or 'readiness-verified'})
print(json.dumps({'model':'intentionally wrong schema-valid HTTP protocol double','docker':'DockerContract command double',
 'real_docker_effects':False,'cases':rows},ensure_ascii=False,indent=2))
