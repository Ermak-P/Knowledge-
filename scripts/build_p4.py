"""Reproducible core wheel bundle; no SDKs, caches, fixtures or project databases."""
import argparse,hashlib,json,os,shutil,subprocess,sys,zipfile,base64,csv,io,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION='0.5.0rc1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def normalize_wheel(path):
    with zipfile.ZipFile(path) as z:files={name:z.read(name).replace(b'\r\n',b'\n') for name in z.namelist() if not name.endswith('/RECORD')}
    record=next(name.rsplit('/',1)[0]+'/RECORD' for name in files if name.endswith('.dist-info/METADATA'))
    stream=io.StringIO(newline='');writer=csv.writer(stream,lineterminator='\n')
    for name,data in sorted(files.items()):writer.writerow([name,'sha256='+base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode(),str(len(data))])
    writer.writerow([record,'','']);files[record]=stream.getvalue().encode()
    with zipfile.ZipFile(path,'w',zipfile.ZIP_STORED) as z:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(name,(2025,1,1,0,0,0));info.create_system=3;info.external_attr=0o100644<<16;z.writestr(info,data)

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--source-id',default='development-unsealed');a=p.parse_args();out=a.output.absolute();out.mkdir(parents=True,exist_ok=True)
    kit=out/'knowledge-harness-0.5.0rc1';kit.mkdir(exist_ok=True);wheels=kit/'wheels';wheels.mkdir(exist_ok=True)
    env={**os.environ,'SOURCE_DATE_EPOCH':'1735689600','PYTHONHASHSEED':'0'}
    with tempfile.TemporaryDirectory(prefix='p3-clean-build-') as tmp:
        staged=[]
        for name in ('knowledge','harness'):
            target=Path(tmp)/name;shutil.copytree(ROOT/'packages'/name,target,ignore=shutil.ignore_patterns('build','dist','*.egg-info','__pycache__','*.pyc'));staged.append(str(target))
        subprocess.run([sys.executable,'-m','pip','wheel','--no-deps','--no-build-isolation','-w',str(wheels),*staged],check=True,env=env)
    assert len(list(wheels.glob('*.whl')))==2
    for wheel in wheels.glob('*.whl'):
        with zipfile.ZipFile(wheel) as z:assert not any('__pycache__' in n.split('/') or n.endswith('.pyc') for n in z.namelist()),'build cache leaked into distribution'
        normalize_wheel(wheel)
    for path in (ROOT/'release/p4-kit').iterdir():
        if path.is_file():shutil.copyfile(path,kit/path.name)
    docs=kit/'docs';docs.mkdir(exist_ok=True)
    for path in (ROOT/'docs/P4').iterdir():
        if path.is_file() and path.suffix in ('.md','.json'):shutil.copyfile(path,docs/path.name)
    shutil.copytree(ROOT/'examples/p4',kit/'examples',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc','bin','obj'))
    host=kit/'host';host.mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'packages/knowledge/src/knowledge/host/opencode.mjs',host/'opencode.mjs')
    for package in ('knowledge','harness'):
        license=next((p for p in (ROOT/'packages'/package).glob('*LICENSE*')),None)
        if license:shutil.copyfile(license,kit/(package+'-LICENSE'))
    shutil.copyfile(ROOT/'inputs/README.md',kit/'UPSTREAM-NOTICE.md')
    files={p.relative_to(kit).as_posix():sha(p) for p in sorted(kit.rglob('*')) if p.is_file() and p.name!='RELEASE.json'}
    manifest=dict(version=1,source_identity=a.source_id,product=VERSION,python='3.12',architectures=['x64'],os_profiles=['linux','windows-native-pending-qualification'],distribution_names=['knowledge-p0','harness-p0'],record_versions=[1,2],knowledge_format='knowledge-sqlite-v1',extension=1,harness_state=1,run_states=[1,2,3],task_schemas=[1,2],runner_configs=[1,2],automatic_tests='dotnet-tests-suffix-v1',continuation_formats=[1,2],core_offline=True,optional_mcp='pinned online install; no complete offline MCP wheelhouse claim',files=files)
    (kit/'RELEASE.json').write_bytes((json.dumps(manifest,indent=2,ensure_ascii=False)+'\n').encode())
    archive=out/(kit.name+'.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_STORED) as z:
        for path in sorted(kit.rglob('*')):
            if path.is_file():
                info=zipfile.ZipInfo(path.relative_to(kit).as_posix(),date_time=(2025,1,1,0,0,0));info.external_attr=(0o100755 if path.name.endswith('.sh') else 0o100644)<<16;z.writestr(info,path.read_bytes())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for rel,h in files.items():assert hashlib.sha256(z.read(rel)).hexdigest()==h
    (out/(archive.name+'.sha256')).write_text(sha(archive)+'  '+archive.name+'\n')
    print(json.dumps(dict(ok=True,archive=str(archive),sha256=sha(archive),manifest_sha256=sha(kit/'RELEASE.json'),wheel_sha256={p.name:sha(p) for p in wheels.iterdir()})))
if __name__=='__main__':main()
