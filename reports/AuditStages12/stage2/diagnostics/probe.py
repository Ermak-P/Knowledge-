import sys,tempfile,json
from pathlib import Path
sys.path.insert(0,'/workspace/Knowledge-/tests')
from test_audit_stage1 import EnumerationBoundaries,unreadable
from test_audit_stage2 import fact
from test_p1 import upgraded,approve
from fixtures import addition
from knowledge.util import canonical_json
rows={}
with tempfile.TemporaryDirectory() as tmp:
 root,folder,store,base=EnumerationBoundaries().checkout(tmp)
 with unreadable(folder):
  result=store.context('Project');assert not result['claims'];assert 'blocked-source-scope' in canonical_json(result);rows['blocked-source-scope']=result
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp);store=upgraded(root);fact(store,root,'gone.rule','Removed supporting source is relevant.')
 (root/'gone_rule.md').unlink();result=store.context('Removed supporting source');assert not result['claims'] and 'missing' in canonical_json(result['diagnostics']);rows['missing']=result
 store.submit(addition('unverifiable.rule','Unverifiable legacy evidence needs independent review.'));approve(store)
 result=store.context('Unverifiable');assert not result['claims'] and 'not-verifiable' in canonical_json(result['diagnostics']);rows['unverifiable']=result
 rows['no-match']=store.context('quasarbeyondvocabulary');assert rows['no-match']['diagnostics']['selection']=='lexical-no-match'
print(json.dumps({'status':'PASS','kind':'installed API; real Linux refusal/deletion; synthetic reviewed stores','rows':rows},indent=2))
