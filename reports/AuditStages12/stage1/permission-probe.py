import sys,json,os,hashlib
from pathlib import Path
sys.path.insert(0,'/workspace/Knowledge-/tests')
from test_audit_stage1 import EnumerationBoundaries,unreadable
from knowledge import discovery as disc
import knowledge,tempfile
with tempfile.TemporaryDirectory() as tmp:
 root,folder,store,base=EnumerationBoundaries().checkout(tmp)
 with unreadable(folder):
  refused=False
  try:list(os.scandir(folder))
  except PermissionError:refused=True
  scan=disc.scan(store,max_files=100,base=base,head='HEAD');review=disc.reconcile(store,scan['id'])
  result={'uid':os.getuid(),'permission_refused':refused,'complete':scan['complete'],'gaps':review['negative_evidence_gaps'],'proposal':review['proposal'],'installed':knowledge.__file__}
 result['source_survived']= 'StillExists' in (folder/'Initial.cs').read_text()
 print(json.dumps(result,indent=2))
