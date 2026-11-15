"""Real accepted P2 wheel -> current wheel -> retained prior code/data round trip."""
import argparse,json,os,shutil,subprocess,sys,tarfile,tempfile,venv
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PIN='91689475a283a2cdc654cfb6090074f0251f895d'
def save(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def python_at(env):return env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--kit',type=Path,required=True);a=p.parse_args();out=a.output.absolute();out.mkdir(parents=True,exist_ok=True);kit=a.kit.absolute()
    scratch=Path(tempfile.mkdtemp(prefix='p3-prior-'));transferred=scratch/'Transferred release';shutil.copytree(kit,transferred);kit=transferred;source=scratch/'accepted-source';source.mkdir()
    archive=scratch/'accepted.tar';archive.write_bytes(subprocess.check_output(['git','archive',PIN,'packages'],cwd=ROOT))
    with tarfile.open(archive) as tar:tar.extractall(source,filter='data')
    wheels=out/'previous-wheels';wheels.mkdir();env={**os.environ,'SOURCE_DATE_EPOCH':'1735689600','PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'};env.pop('PYTHONPATH',None)
    def command(label,argv,cwd=scratch,expected=0):
        p=subprocess.run([str(x) for x in argv],cwd=cwd,env=env,text=True,encoding='utf-8',capture_output=True,timeout=600)
        (out/(label+'.log')).write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==expected,(label,p.stdout[-2000:],p.stderr[-2000:]);return p
    command('prior-wheels',[sys.executable,'-m','pip','wheel','--no-deps','--no-build-isolation','-w',wheels,source/'packages/knowledge',source/'packages/harness'])
    runtime=scratch/'owned runtime';venv.EnvBuilder(with_pip=True).create(runtime);python=python_at(runtime)
    command('prior-install',[python,'-I','-m','pip','install','--no-index','--no-deps',*sorted(wheels.glob('*.whl'))])
    root=scratch/'Nonempty accepted project';root.mkdir()
    fixture=scratch/'fixture.py';fixture.write_text('''import sys,json
from pathlib import Path
import knowledge,harness
assert Path(knowledge.__file__).is_relative_to(Path(sys.prefix))
sys.path.insert(0,TESTS)
from p3_state_fixtures import rich,logical
root=Path(ROOT)
print(json.dumps(rich(root),ensure_ascii=False))
'''.replace('TESTS',repr(str(ROOT/'tests'))).replace('ROOT',repr(str(root))),encoding='utf-8')
    result=json.loads(command('prior-nonempty-state',[python,'-I',fixture]).stdout);before=result['snapshot']
    command('adopt-current-install',[sys.executable,kit/'install.py','install','--env',runtime,'--profile','full','--adopt'])
    inspect=scratch/'inspect.py';inspect.write_text('import sys,json;sys.path.insert(0,'+repr(str(ROOT/'tests'))+');from p3_state_fixtures import logical;print(json.dumps(logical('+repr(str(root))+'),ensure_ascii=False))',encoding='utf-8')
    after=json.loads(command('current-inspect',[python,'-I',inspect]).stdout);assert after==before
    def maintain(name,args):return json.loads(command(name,[python,'-I','-m','knowledge.maintain_cli',*args,'--root',root]).stdout)
    plan=maintain('upgrade-preview',['upgrade-preview','--destination',scratch/'before-upgrade.zip']);preview=scratch/'preview.json';save(preview,plan['preview']);upgrade=maintain('upgrade-apply',['apply','--input',preview,'--approve',plan['fingerprint']]);assert upgrade['ok']
    after_upgrade=json.loads(command('upgraded-inspect',[python,'-I',inspect]).stdout);assert after_upgrade==before
    # Introduce a new queued change through the supported current API; rollback must undo
    # that metadata while preserving the old version of it in a separate recovery path.
    change='from knowledge.store import Store;import sys;sys.path.insert(0,'+repr(str(ROOT/'tests'))+');from fixtures import addition;Store('+repr(str(root))+').submit(addition("fixture.new","Synthetic post-upgrade pending candidate."))'
    command('new-queue',[python,'-I','-c',change]);(root/'user-after-upgrade.txt').write_text('PRESERVE USER BYTES',encoding='utf-8')
    restore=maintain('restore-preview',['restore-preview','--archive',scratch/'before-upgrade.zip','--recovery',scratch/'replaced-state']);save(preview,restore['preview']);maintain('restore-apply',['apply','--input',preview,'--approve',restore['fingerprint']])
    assert json.loads(command('restored-inspect',[python,'-I',inspect]).stdout)==before
    command('rollback-code',[python,'-I','-m','pip','install','--no-index','--no-deps',*sorted(wheels.glob('*.whl'))])
    old_versions=json.loads(command('rollback-versions',[python,'-I','-c','import knowledge,harness,json;print(json.dumps([knowledge.__version__,harness.__version__]))']).stdout);assert old_versions==['0.1.0','0.2.0']
    assert json.loads(command('rollback-inspect',[python,'-I',inspect]).stdout)==before
    command('reinstall-current',[sys.executable,kit/'install.py','install','--env',runtime,'--profile','full'])
    assert json.loads(command('reinstalled-inspect',[python,'-I',inspect]).stdout)==before
    assert (root/'user-after-upgrade.txt').read_text()=='PRESERVE USER BYTES'
    # Inspection/recovery of capture delivery does not acknowledge canonical commits.
    pending=next(r for r in before['runs'] if r['execution']=='passed' and r['status']=='running')
    resumed=json.loads(command('retained-outbox-resume',[python,'-I','-m','harness.run_cli','resume','--root',root,'--run-id',pending['id']],expected=1).stdout);assert resumed['execution']=='passed' and resumed['capture']['state']=='delivered' and resumed['error']=='final-source-changed'
    after_resume=json.loads(command('after-resume-inspect',[python,'-I',inspect]).stdout)
    assert after_resume['knowledge']==before['knowledge']
    assert after_resume['runs'][[r['id'] for r in after_resume['runs']].index(pending['id'])]['requests']==pending['requests']
    save(out/'prior-upgrade.json',dict(accepted_commit=PIN,prior_versions=old_versions,before=before,after_install=after,after_upgrade=after_upgrade,restore_preserved_state=True,rollback_code_and_data=True,reinstall_preserved=True,outbox_resume=resumed,after_resume=after_resume,all_authority_and_dispositions_preserved=True,source_user_bytes_preserved=True))
    print('PASS: accepted installed P2 rich state, current upgrade, exact backup/restore, real prior code/data rollback and reinstall/outbox recovery.')
if __name__=='__main__':main()
