"""Portable repository development bootstrap; product installation uses the kit."""
import os,subprocess,sys,venv,tempfile,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    assert sys.version_info[:2]==(3,12),'Python 3.12 required; other runtimes preserved'
    env=ROOT/'.venv'
    if not env.exists():venv.EnvBuilder(with_pip=True).create(env)
    python=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    subprocess.run([str(a) for a in [python,'-m','pip','install','--no-cache-dir','-r',ROOT/'requirements-dev.lock']],cwd=ROOT,check=True)
    with tempfile.TemporaryDirectory(prefix='p3-clean-setup-') as tmp:
        staged=[]
        for name in ('knowledge','harness'):
            target=Path(tmp)/name;shutil.copytree(ROOT/'packages'/name,target,ignore=shutil.ignore_patterns('build','dist','*.egg-info','__pycache__','*.pyc'));staged.append(str(target))
        subprocess.run([str(a) for a in [python,'-m','pip','install','--no-build-isolation',*staged]],cwd=ROOT,check=True)
    subprocess.run([str(python),'-m','pip','check'],cwd=ROOT,check=True)
if __name__=='__main__':main()
