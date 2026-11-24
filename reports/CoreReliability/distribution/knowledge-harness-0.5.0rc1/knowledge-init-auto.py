"""Compatibility launcher; all scanning logic lives in knowledge.auto_init."""
from pathlib import Path
import runpy
import sys

if __name__ == '__main__':
    base = Path(__file__).resolve().parent
    if (base / 'current.json').is_file() and (base / 'launch.py').is_file():
        sys.argv.insert(1, 'auto')
        runpy.run_path(str(base / 'launch.py'), run_name='__main__')
    else:
        from knowledge.auto_init import main
        raise SystemExit(main())
