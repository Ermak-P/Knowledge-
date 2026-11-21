"""Run the repository host trial with an isolated HOME/XDG/OpenCode profile.

Use the installed core Python. This wrapper never simulates a missing host/model.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[3])
    args,forward=parser.parse_known_args()
    driver=args.repo/'scripts/validate_persistent_host.py'
    if not driver.is_file():raise SystemExit('Supply --repo pointing to the Knowledge checkout')
    with tempfile.TemporaryDirectory(prefix='knowledge-isolated-host-profile-') as tmp:
        home=Path(tmp)/'home';home.mkdir()
        env=dict(os.environ);env.update(HOME=str(home),USERPROFILE=str(home))
        for key,folder in [('XDG_CONFIG_HOME','config'),('XDG_DATA_HOME','data'),('XDG_CACHE_HOME','cache'),('XDG_STATE_HOME','state'),('APPDATA','appdata'),('LOCALAPPDATA','localappdata')]:
            path=home/folder;path.mkdir();env[key]=str(path)
        for key in ('OPENCODE_CONFIG','OPENCODE_CONFIG_DIR','OPENCODE_CONFIG_CONTENT'):env.pop(key,None)
        return subprocess.run([sys.executable,'-I',str(driver),*forward],env=env).returncode


if __name__=='__main__':raise SystemExit(main())
