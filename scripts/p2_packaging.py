"""Build wheels and run both installed CLIs without repository import paths."""
import json,subprocess,sys,tempfile,venv
from pathlib import Path
from p2_evidence import ROOT

def main():
    subprocess.run([sys.executable,'-B','scripts/check_packaging.py'],cwd=ROOT,check=True)
    with tempfile.TemporaryDirectory(prefix='p2-packaging-') as tmp:
        tmp=Path(tmp);wheels=tmp/'wheels';wheels.mkdir()
        subprocess.run([sys.executable,'-m','pip','wheel','--no-deps','--no-build-isolation','-w',str(wheels),str(ROOT/'packages/knowledge'),str(ROOT/'packages/harness')],check=True)
        target=tmp/'installed';venv.EnvBuilder(with_pip=True).create(target);python=target/'bin/python'
        subprocess.run([str(python),'-m','pip','install','--no-index','--no-deps',*[str(p) for p in sorted(wheels.glob('*.whl'))]],check=True)
        subprocess.run([str(python),'-m','harness.run_cli','--help'],cwd=tmp,check=True)
        project=tmp/'project';project.mkdir()
        p=subprocess.run([str(python),'-m','harness.cli','--root',str(project),'--task','bounded read'],cwd=tmp,text=True,capture_output=True,check=True)
        assert json.loads(p.stdout)['mode']=='degraded';assert not (project/'.knowledge').exists()
        subprocess.run([str(python),'-c','import harness; assert harness.__version__=="0.2.0"'],cwd=tmp,check=True)
        print('PASS: isolated installed Harness execution CLI and legacy read facade; standalone Knowledge checked separately.')
if __name__=='__main__':main()
