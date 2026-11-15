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
        p=subprocess.run([str(x) for x in argv],cwd=cwd,env=env,stdin=subprocess.DEVNULL,text=True,encoding='utf-8',capture_output=True,timeout=600)
        (out/(label+'.log')).write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==expected,(label,p.stdout[-2000:],p.stderr[-2000:]);return p
    command('prior-wheels',[sys.executable,'-m','pip','wheel','--no-deps','--no-build-isolation','-w',wheels,source/'packages/knowledge',source/'packages/harness'])
    runtime=scratch/'owned runtime';venv.EnvBuilder(with_pip=True).create(runtime);python=python_at(runtime)
    command('prior-install',[python,'-I','-m','pip','install','--no-index','--no-deps',*sorted(wheels.glob('*.whl'))])
    root=scratch/'Nonempty accepted project';root.mkdir()
    prior_versions=json.loads(command('prior-versions',[python,'-I','-c','import knowledge,harness,json;print(json.dumps([knowledge.__version__,harness.__version__]))']).stdout);assert prior_versions==['0.1.0','0.2.0']
    native_probe=None
    if os.name=='nt':
        # Accepted P2 explicitly has no native Windows executor. Exercise that
        # boundary with the actual old binaries; never patch their POSIX guards.
        probe=scratch/'prior-native-probe.py';probe.write_text('''import sys,json,hashlib
from pathlib import Path
import knowledge
assert Path(knowledge.__file__).is_relative_to(Path(sys.prefix))
sys.path.insert(0,TESTS)
from p2_fixtures import project,configuration
from fixtures import addition,legacy_fixture
from knowledge.store import Store
from knowledge import migration,lifecycle as life,discovery as disc
from knowledge.util import KnowledgeError
from harness.runtime import validate_config
root=project(Path(ROOT));legacy_fixture(root);migration.apply(root,migration.preview(root)['fingerprint']);s=Store(root);life.upgrade(s,life.upgrade_preview(s)['fingerprint'])
def approve():
 p=s.prepare();assert p['ok'];s.apply(p['fingerprint'],p['fingerprint']);s.acknowledge(p['fingerprint'])
for text in ('public class InitialFeature {}\\n','public class InitialFeature : System.Object {}\\n'):
 (root/'Feature.cs').write_text(text,encoding='utf-8')
 for decision in disc.candidate_observe(s,['Feature.cs'])['decisions']:
  if decision['decision']=='submit':s.submit(decision['payload'])
 approve()
for disposition in ('rejected','deferred'):
 q=s.submit(addition('fixture.'+disposition,'Synthetic '+disposition+' meaning.'));life.dispose(s,q['candidate'],disposition,'Explicit fixture disposition')
s.submit(addition('fixture.prepared','Synthetic prepared change.'));s.prepare()
s.submit(addition('fixture.committed','Synthetic committed pending ack.'));p=s.prepare();s.apply(p['fingerprint'],p['fingerprint'])
s.submit(addition('fixture.pending','Synthetic pending change.'))
try:validate_config(configuration('http://127.0.0.1/v1/chat/completions'))
except KnowledgeError as error:
 assert error.code=='recipe-executable-must-be-absolute'
 result={'prior_native_executor':'UNSUPPORTED_POSIX_ONLY','error':error.code}
else:raise AssertionError('unexpected prior native execution support')
result['files']={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'.knowledge').rglob('*') if p.is_file()}
result['knowledge']={'store':s.export(),'observations':disc.capture_observation_receipts(s)}
print(json.dumps(result))
'''.replace('TESTS',repr(str(ROOT/'tests'))).replace('ROOT',repr(str(root))),encoding='utf-8')
        native_probe=json.loads(command('prior-native-unsupported-probe',[python,'-I',probe]).stdout)
        command('adopt-current-install',[sys.executable,kit/'install.py','install','--env',runtime,'--profile','full','--adopt'])
        refusal='''import json,hashlib
from pathlib import Path
from knowledge.store import Store
from knowledge import discovery as disc
root=Path(ROOT)
store=Store(root);store.validate()
assert {'store':store.export(),'observations':disc.capture_observation_receipts(store)}==KNOWLEDGE
files={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'.knowledge').rglob('*') if p.is_file()}
assert files==EXPECTED
print(json.dumps({'prior_store_preserved':True,'root_identity_preserved':True}))
'''.replace('ROOT',repr(str(root))).replace('EXPECTED',repr(native_probe['files'])).replace('KNOWLEDGE',repr(native_probe['knowledge']))
        preserved_script=scratch/'prior-knowledge-preserved.py';preserved_script.write_text(refusal,encoding='utf-8')
        native_probe.update(json.loads(command('prior-native-knowledge-preserved',[python,'-I',preserved_script]).stdout))
        def old_knowledge_maintain(label,args):return json.loads(command(label,[python,'-I','-m','knowledge.maintain_cli',*args,'--root',root]).stdout)
        plan=old_knowledge_maintain('prior-knowledge-upgrade-preview',['upgrade-preview','--destination',scratch/'prior-knowledge-backup.zip']);approved=scratch/'prior-knowledge-preview.json';save(approved,plan['preview']);old_knowledge_maintain('prior-knowledge-upgrade',['apply','--input',approved,'--approve',plan['fingerprint']])
        change='import sys;sys.path.insert(0,'+repr(str(ROOT/'tests'))+');from fixtures import addition;from knowledge.store import Store;Store('+repr(str(root))+').submit(addition("fixture.after_upgrade","Synthetic later state."))'
        command('prior-knowledge-change',[python,'-I','-c',change]);(root/'user-preserved.txt').write_text('PRESERVE',encoding='utf-8')
        plan=old_knowledge_maintain('prior-knowledge-restore-preview',['restore-preview','--archive',scratch/'prior-knowledge-backup.zip','--recovery',scratch/'prior-knowledge-replaced']);save(approved,plan['preview']);old_knowledge_maintain('prior-knowledge-restore',['apply','--input',approved,'--approve',plan['fingerprint']])
        command('prior-knowledge-old-code-rollback',[python,'-I','-m','pip','install','--no-index','--no-deps',*sorted(wheels.glob('*.whl'))])
        check='import sys,knowledge;assert knowledge.__version__=="0.1.0";sys.path.insert(0,'+repr(str(ROOT/'tests'))+');from knowledge.store import Store;from knowledge import discovery as d;from pathlib import Path;root=Path('+repr(str(root))+');assert {"store":Store(root).export(),"observations":d.capture_observation_receipts(Store(root))}=='+repr(native_probe['knowledge'])+';assert (root/"user-preserved.txt").read_text()=="PRESERVE"'
        old_inspection=scratch/'prior-knowledge-old-inspection.py';old_inspection.write_text(check,encoding='utf-8')
        command('prior-knowledge-old-code-inspection',[python,'-I',old_inspection]);native_probe['prior_knowledge_upgrade_and_code_data_rollback']=True
        command('current-after-knowledge-rollback',[sys.executable,kit/'install.py','install','--env',runtime,'--profile','full'])
        root=scratch/'Native current state Ω';root.mkdir()
    fixture=scratch/'fixture.py';fixture.write_text('''import sys,json
from pathlib import Path
import knowledge,harness
assert Path(knowledge.__file__).is_relative_to(Path(sys.prefix))
sys.path.insert(0,TESTS)
from p3_state_fixtures import rich,logical
root=Path(ROOT)
print(json.dumps(rich(root)))
'''.replace('TESTS',repr(str(ROOT/'tests'))).replace('ROOT',repr(str(root))),encoding='utf-8')
    result=json.loads(command('native-nonempty-state' if native_probe else 'prior-nonempty-state',[python,'-I',fixture]).stdout);before=result['snapshot']
    if not native_probe:command('adopt-current-install',[sys.executable,kit/'install.py','install','--env',runtime,'--profile','full','--adopt'])
    inspect=scratch/'inspect.py';inspect.write_text('import sys,json;sys.path.insert(0,'+repr(str(ROOT/'tests'))+');from p3_state_fixtures import logical;print(json.dumps(logical('+repr(str(root))+')))',encoding='utf-8')
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
    if not native_probe:command('rollback-code',[python,'-I','-m','pip','install','--no-index','--no-deps',*sorted(wheels.glob('*.whl'))])
    old_versions=json.loads(command('restored-code-versions' if native_probe else 'rollback-versions',[python,'-I','-c','import knowledge,harness,json;print(json.dumps([knowledge.__version__,harness.__version__]))']).stdout);assert old_versions==(['0.3.0rc1','0.3.0rc1'] if native_probe else ['0.1.0','0.2.0'])
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
    save(out/'prior-upgrade.json',dict(profile='windows-prior-knowledge-and-current-harness' if native_probe else 'linux-accepted-prior-binaries',accepted_commit=PIN,prior_versions=prior_versions,prior_native_probe=native_probe,prior_native_harness_upgrade='UNSUPPORTED' if native_probe else 'PASS',before=before,after_install=after,after_upgrade=after_upgrade,restore_preserved_state=True,rollback_code_and_data=not bool(native_probe),native_metadata_rollback=bool(native_probe),reinstall_preserved=True,outbox_resume=resumed,after_resume=after_resume,all_authority_and_dispositions_preserved=True,source_user_bytes_preserved=True))
    print('PASS: real prior Knowledge code/data upgrade/rollback plus native current Harness rich-state round trip; old POSIX Harness native execution remains unsupported.' if native_probe else 'PASS: accepted installed P2 rich state, current upgrade, exact backup/restore, real prior code/data rollback and reinstall/outbox recovery.')
if __name__=='__main__':main()
