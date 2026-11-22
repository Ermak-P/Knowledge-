from pathlib import Path,PurePosixPath
import argparse,hashlib,json,shutil,zipfile
parser=argparse.ArgumentParser();parser.add_argument('--repo',type=Path,default=Path('/workspace/Knowledge-'));parser.add_argument('--run',type=Path,default=Path('/workspace/Knowledge-/reports/P4/runs/a83ca87b88aa42929fd8263a98a4652f'));args=parser.parse_args()
root=args.repo;out=root/'reports/AuditStages12/R1';source=json.loads((out/'source.json').read_text());runpath=args.run;run=json.loads((runpath/'run.json').read_text())
assert run['status']=='PASS_PORTABLE' and run['unchanged'] and run['commit']==source['commit'] and run['source_identity']==source['source_identity'] and run['source']==source['source']
local=out/'local';local.mkdir(exist_ok=True)
for name in ('run.json','tests.json'):shutil.copy2(runpath/name,local/name)
for command in run['commands']:
 assert command['returncode']==0
 path=PurePosixPath(command['log']);assert not path.is_absolute() and len(path.parts)==1
 raw=(runpath/command['log']).read_bytes();assert hashlib.sha256(raw).hexdigest()==command['sha256'];(local/command['log']).write_bytes(raw)
trial=runpath/'audit-stages12-delivery';(out/'installed-trial').mkdir(exist_ok=True)
for name in ('result.json','enabled-requests.json','control-requests.json','enabled-run.json','control-run.json'):shutil.copy2(trial/name,out/'installed-trial'/name)
distribution=out/'distribution';distribution.mkdir(exist_ok=True);kit=runpath/'distribution/knowledge-harness-0.5.0rc1';release=json.loads((kit/'RELEASE.json').read_text());assert release['source_identity']==source['source_identity']
for name,wanted in release['files'].items():
 path=PurePosixPath(name);assert not path.is_absolute() and '..' not in path.parts;assert hashlib.sha256((kit/name).read_bytes()).hexdigest()==wanted
for package,entries in {'knowledge':('knowledge/context_delivery.py','knowledge/ingress_failure.py','knowledge/transfers.py','knowledge/source_coverage.py','knowledge/host/opencode.mjs'),'harness':('harness/delivery.py','harness/host_ingress.py')}.items():
 wheel=next((kit/'wheels').glob(package+'_p0*.whl'))
 with zipfile.ZipFile(wheel) as archive:
  assert all(name in archive.namelist() for name in entries)
archive=runpath/'distribution/knowledge-harness-0.5.0rc1.zip';shutil.copy2(archive,distribution/archive.name);shutil.copy2(kit/'RELEASE.json',distribution/'RELEASE.json')
value={'source_commit':source['commit'],'source_identity':source['source_identity'],'product':run['product'],'zip':'distribution/'+archive.name,'zip_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'wheels':{k:v for k,v in release['files'].items() if k.startswith('wheels/')},'all_kit_file_hashes_verified':True,'new_modules_and_host_plugin_in_actual_wheels':True,'qualification_commands':len(run['commands'])}
(distribution/'package.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value,indent=2))
