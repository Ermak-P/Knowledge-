"""Validate retained Git evidence as data, never execute artifact content."""
import hashlib,json,subprocess,zipfile
from pathlib import Path,PurePosixPath
repo=Path('/workspace/Knowledge-');code='74b2dee16aaf8fd0dfe25854fae47d8bf8bcf016';out=repo/'reports/AuditStages12/ci';out.mkdir(exist_ok=True)
expected=json.loads((out.parent/'source.json').read_text());localdir=repo/'reports/AuditStages12/distribution'
def git(*a):return subprocess.check_output(['git',*a],cwd=repo)
subprocess.run(['git','fetch','origin','p4-ci-evidence'],cwd=repo,check=True)
evidence=git('rev-parse','FETCH_HEAD').decode().strip()
def read(path):return git('show',evidence+':'+path)
platforms={}
for platform in ('Linux','Windows'):
 prefix=code+'/'+platform+'/';paths=git('ls-tree','-r','--name-only',evidence,prefix).decode().splitlines()
 if not paths:print(platform+' evidence not yet retained');continue
 target=out/platform;target.mkdir(parents=True,exist_ok=True)
 receipt=json.loads(read(prefix+'receipt.json'));run=json.loads(read(prefix+'run/run.json'))
 assert receipt['commit']==run['commit']==code
 assert receipt['source_identity']==run['source_identity']==expected['source_identity']
 assert run['source']==expected['source'] and run['unchanged'] is True
 for c in run['commands']:
  path=PurePosixPath(c['log']);assert not path.is_absolute() and len(path.parts)==1
  data=read(prefix+'run/'+c['log']);assert hashlib.sha256(data).hexdigest()==c['sha256'];(target/c['log']).write_bytes(data)
 tests=json.loads(read(prefix+'run/tests.json')) if prefix+'run/tests.json' in paths else None
 if run['status'] in ('PASS_NATIVE','PASS_PORTABLE'):
  assert tests and tests['success'] and tests['failed']==tests['errors']==0
  assert all(v=='PASS' for v in run['checks'].values()) and all(c['returncode']==0 for c in run['commands'])
 for name,value in [('receipt.json',receipt),('run.json',run),('tests.json',tests)]:
  (target/name).write_text(json.dumps(value,indent=2)+'\n')
 release_path=prefix+'run/distribution/knowledge-harness-0.5.0rc1/RELEASE.json';release=json.loads(read(release_path));local=json.loads((localdir/'RELEASE.json').read_text())
 assert release['source_identity']==expected['source_identity'] and release['files']==local['files']
 with zipfile.ZipFile(localdir/'knowledge-harness-0.5.0rc1.zip') as archive:
  for name,wanted in local['files'].items():assert hashlib.sha256(archive.read(name)).hexdigest()==wanted
 for name,wanted in release['files'].items():
  path=PurePosixPath(name);assert not path.is_absolute() and '..' not in path.parts
  assert hashlib.sha256(read(prefix+'run/distribution/knowledge-harness-0.5.0rc1/'+name)).hexdigest()==wanted
 (target/'RELEASE.json').write_text(json.dumps(release,indent=2)+'\n')
 trialpath=prefix+'run/audit-stages12-delivery/'
 for name in ('result.json','enabled-requests.json','control-requests.json','enabled-run.json','control-run.json'):
  if trialpath+name in paths:
   directory=target/'installed-trial';directory.mkdir(exist_ok=True);(directory/name).write_bytes(read(trialpath+name))
 platforms[platform]={'status':run['status'],'url':receipt['url'],'tests':tests['tests'] if tests else None,'passed':tests['passed'] if tests else None,'failed':tests['failed'] if tests else None,'errors':tests['errors'] if tests else None,'skipped':tests['skipped'] if tests else None,'commands':len(run['commands']),'source_and_all_log_hashes_validated':True,'delivered_kit_matches_all_ci_content_hashes':True}
value={'evidence_commit':evidence,'code_commit':code,'source_identity':expected['source_identity'],'platforms':platforms,'artifact_code_executed':False}
(out/'validation.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value,indent=2))
