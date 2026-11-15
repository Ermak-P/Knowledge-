"""Portable repository development bootstrap; product installation uses the kit."""
import os,subprocess,sys,venv
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    assert sys.version_info[:2]==(3,12),'Python 3.12 required; other runtimes preserved'
    env=ROOT/'.venv'
    if not env.exists():venv.EnvBuilder(with_pip=True).create(env)
    python=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    for argv in ([python,'-m','pip','install','--no-cache-dir','-r',ROOT/'requirements-dev.lock'],[python,'-m','pip','install','--no-build-isolation',ROOT/'packages/knowledge',ROOT/'packages/harness'],[python,'-m','pip','check']):subprocess.run([str(a) for a in argv],cwd=ROOT,check=True)
if __name__=='__main__':main()
