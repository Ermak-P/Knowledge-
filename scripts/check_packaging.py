"""Build real wheels; test standalone Knowledge in a fresh dependency-free venv."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import venv

ROOT=Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix='knowledge-packaging-') as tmp:
        tmp=Path(tmp);wheels=tmp/'wheels';wheels.mkdir()
        subprocess.run([sys.executable,'-m','pip','wheel','--no-deps','--no-build-isolation','--wheel-dir',str(wheels),
                        str(ROOT/'packages/knowledge'),str(ROOT/'packages/harness')],check=True)
        isolated=tmp/'isolated';venv.EnvBuilder(with_pip=True).create(isolated)
        python=isolated/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
        wheel=next(wheels.glob('knowledge_p0-*.whl'))
        subprocess.run([str(python),'-m','pip','install','--no-index','--no-deps',str(wheel)],check=True)
        subprocess.run([str(python),'-c',"import importlib.util; assert importlib.util.find_spec('mcp') is None; assert importlib.util.find_spec('harness') is None"],check=True)
        root=tmp/'project';root.mkdir()
        for command in ('version','init','validate'):
            p=subprocess.run([str(python),'-m','knowledge.cli',command,'--root',str(root)],text=True,capture_output=True,check=True)
            assert json.loads(p.stdout)['ok'],p.stdout
        assert len(list(wheels.glob('*.whl')))==2
        print('PASS: both wheels built; standalone Knowledge CLI works without MCP/Harness or model services')


if __name__=='__main__':main()
