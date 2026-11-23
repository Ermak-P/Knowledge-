"""Source-checkout machine launcher; source is anchored here, never to CWD."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    backend = runpy.run_path(str(root / 'installer/knowledge_install.py'))
    raise SystemExit(backend['main'](root))
