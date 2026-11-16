"""Actual core offline transfer/install, launcher behavior and tamper refusal."""
import argparse,json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def python_at(env):return env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--kit',type=Path,required=True);a=p.parse_args();out=a.output.absolute();out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='P3 package transfer Ω ') as tmp:
        tmp=Path(tmp);kit=tmp/'Release bundle';shutil.copytree(a.kit,kit);env=tmp/'Standalone runtime';runtime_env={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'};runtime_env.pop('PYTHONPATH',None)
        def call(name,argv,expected=0):
            r=subprocess.run([str(v) for v in argv],cwd=tmp,env=runtime_env,text=True,encoding='utf-8',capture_output=True,timeout=120);(out/(name+'.log')).write_text(r.stdout+r.stderr,encoding='utf-8');assert r.returncode==expected,(name,r.stdout[-2000:],r.stderr[-2000:]);return r
        command=[sys.executable,kit/'install.py','install','--env',env,'--profile','knowledge']
        if sys.platform=='linux':command=[sys.executable,ROOT/'scripts/offline_exec.py',*command[1:]]
        call('offline-core',command);python=python_at(env)
        standalone=json.loads(call('standalone-import',[python,'-I','-c','import knowledge,importlib.util,json,sys;print(json.dumps({"version":knowledge.__version__,"file":knowledge.__file__,"prefix":sys.prefix,"harness":importlib.util.find_spec("harness") is not None,"mcp":importlib.util.find_spec("mcp") is not None}))']).stdout)
        assert standalone['version']=='0.3.0rc1' and not standalone['harness'] and not standalone['mcp'] and not Path(standalone['file']).is_relative_to(ROOT)
        full=[sys.executable,kit/'install.py','install','--env',env,'--profile','full']
        if sys.platform=='linux':full=[sys.executable,ROOT/'scripts/offline_exec.py',*full[1:]]
        call('full-offline',full);call('doctor',[sys.executable,kit/'install.py','doctor','--env',env])
        root=tmp/'New project';root.mkdir()
        version=json.loads(call('harness-version',[python,'-I','-m','harness.run_cli','version','--root',root]).stdout);assert version['version']=='0.3.0rc1'
        for command in ('version','init','validate'):assert json.loads(call(command,[python,'-I','-m','knowledge.cli',command,'--root',root]).stdout)['ok']
        legacy=json.loads(call('legacy-facade',[python,'-I','-m','harness.cli','--root',root,'--task','read only']).stdout);assert legacy['ok']
        call('uninstall',[sys.executable,kit/'install.py','uninstall','--env',env]);assert (root/'.knowledge/store.sqlite3').exists()
        call('uninstalled-check',[python,'-I','-c','import importlib.util;assert importlib.util.find_spec("knowledge") is None;assert importlib.util.find_spec("harness") is None'])
        call('reinstall',[sys.executable,kit/'install.py','install','--env',env,'--profile','full']);call('retained-validate',[python,'-I','-m','knowledge.cli','validate','--root',root])
        if os.name!='nt':
            call('posix-launcher',['sh',kit/'install.sh','doctor','--env',env]);call('posix-launcher-failure',['sh',kit/'install.sh','doctor','--env',tmp/'not-owned'],expected=1)
        # The actual original candidate shares our version. A metadata-only
        # success while pip retains its vulnerable old code must fail this check.
        prior=ROOT/'reports/P3/runs/487b8e58b2c645db988705ff213f362c/distribution/knowledge-harness-0.3.0rc1'
        prior_env=tmp/'Prior candidate runtime';candidate=tmp/'Existing candidate project';state=tmp/'original-candidate-state.json';driver=ROOT/'tests/p3_same_version_upgrade.py'
        call('original-candidate-install',[sys.executable,prior/'install.py','install','--env',prior_env,'--profile','full'])
        prior_python=python_at(prior_env)
        call('original-candidate-probe',[prior_python,'-I',driver,'before','--root',candidate,'--state',state])
        call('same-version-candidate-refresh',[sys.executable,kit/'install.py','install','--env',prior_env,'--profile','full'])
        refreshed=json.loads(call('same-version-candidate-inspection',[prior_python,'-I',driver,'after','--root',candidate,'--state',state]).stdout)
        (out/'same-version-upgrade.json').write_bytes((json.dumps(refreshed,indent=2)+'\n').encode('utf-8'))
        # Tamper a local wheel: rejection occurs before a new environment exists.
        wheel=next((kit/'wheels').glob('*.whl'));wheel.write_bytes(wheel.read_bytes()+b'TAMPER')
        call('tampered-package',[sys.executable,kit/'install.py','install','--env',tmp/'refused'],expected=1);assert not (tmp/'refused').exists()
        value=dict(version=1,profile='core-offline',standalone=standalone,package_transfer=True,no_development_imports=True,isolated_install=True,uninstall_reinstall=True,source_store_preserved=True,same_version_candidate_refresh=refreshed,core_network='kernel connect blocked' if sys.platform=='linux' else 'pip --no-index --no-deps; all core wheel inputs local',optional_mcp='online, separately tested; not bundled as an offline wheelhouse',posix_launcher='PASS' if os.name!='nt' else 'NOT_APPLICABLE')
        (out/'packaging.json').write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('PASS: transferred local core wheels install offline, independent Knowledge, installed CLIs, tamper refusal and product-only uninstall/reinstall.')
if __name__=='__main__':main()
