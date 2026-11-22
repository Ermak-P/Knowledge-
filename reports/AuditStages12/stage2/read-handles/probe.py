import gc,hashlib,json,os,tempfile
from pathlib import Path
from knowledge.store import Store
from knowledge.project import Project
from harness import delivery
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp);Store(root).init();project=Project(root);gc.collect();gc.disable()
 try:
  before=len(os.listdir('/proc/self/fd'))
  for index in range(100):assert delivery.store_token(project)['state']=='available'
  after=len(os.listdir('/proc/self/fd'))
 finally:gc.enable();gc.collect()
 print(json.dumps({'profile':'Linux installed runtime; GC disabled only during observation','iterations':100,'fd_before':before,'fd_after':after,'growth':after-before,'installed':delivery.__file__,'module_sha256':hashlib.sha256(Path(delivery.__file__).read_bytes()).hexdigest()},indent=2))
