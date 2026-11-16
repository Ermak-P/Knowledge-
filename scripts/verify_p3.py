"""One coherent fresh local/native release run, installed wheels and no P2 reuse."""
import json,os,subprocess,sys,tempfile
from pathlib import Path
from p3_evidence import Attempt,ROOT,save,validate_current

def main():
    a=Attempt()
    try:
        a.command('setup',[sys.executable,'-B','scripts/setup_p3.py'])
        a.command('baseline',[sys.executable,'-B','scripts/p3_baseline.py','--output',a.dir/'baseline'])
        a.command('regressions',[sys.executable,'-B','scripts/p3_tests.py','--output',a.dir/'regressions'])
        a.command('distribution',[sys.executable,'-B','scripts/build_p3.py','--output',a.dir/'distribution','--source-id',a.value['source_identity']])
        kit=a.dir/'distribution/knowledge-harness-0.3.0rc1'
        manifest=json.loads((kit/'RELEASE.json').read_text(encoding='utf-8'));a.value['wheel_sha256']={Path(p).name:h for p,h in manifest['files'].items() if p.endswith('.whl')};a.persist()
        a.command('reproducibility',[sys.executable,'-B','scripts/p3_reproducibility.py','--output',a.dir/'reproducibility','--first',a.dir/'distribution','--source-id',a.value['source_identity']])
        a.command('packaging',[sys.executable,'-B','scripts/p3_packaging.py','--output',a.dir/'packaging','--kit',kit])
        a.command('prior-upgrade',[sys.executable,'-B','scripts/p3_prior_upgrade.py','--output',a.dir/'prior-upgrade','--kit',kit])
        a.command('rehearsal',[sys.executable,'-B','scripts/p3_rehearsal.py','--output',a.dir/'rehearsal','--kit',kit])
        # Fresh independent installed environment for both bounded and realistic checks.
        with tempfile.TemporaryDirectory(prefix='p3-evaluation-runtime-') as tmp:
            env=Path(tmp)/'Product';subprocess.run([sys.executable,str(kit/'install.py'),'install','--env',str(env),'--profile','full'],check=True)
            python=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
            a.command('application',[python,'-I','-B',ROOT/'scripts/evaluate_p3_application.py','--output',a.dir/'application'])
            a.command('bounded',[python,'-I','-B',ROOT/'scripts/p3_bounded.py','--output',a.dir/'bounded'])
        a.command('native',[sys.executable,'-B','scripts/native_windows_p3.py','--output',a.dir/'native','--ledger',a.dir/'run.json','--kit',kit],not_run=os.name!='nt')
        a.finish('PASS_PORTABLE');validate_current()
    except BaseException:
        a.finish('FAILED');raise
    print('P3 verification: PASS_PORTABLE '+a.id+'; native qualification is separate.')
if __name__=='__main__':main()
