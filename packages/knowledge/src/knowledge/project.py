"""One explicit resolver; reject links in all ancestors and store descendants."""
import os
from pathlib import Path
import stat
from .util import require, digest


def linked(p):
    return p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction())


def safe_path(p):
    p = Path(p)
    for part in [p, *p.parents]:
        require(not linked(part), 'linked-path')
    if p.exists():
        mode = p.stat().st_mode
        require(stat.S_ISDIR(mode) or (stat.S_ISREG(mode) and p.stat().st_nlink == 1),
                'unsafe-filesystem-object')
    return p


def safe_tree(p):
    safe_path(p)
    if p.is_dir():
        for child in p.iterdir():
            safe_tree(child)


class Project:
    def __init__(self, root):
        require(root is not None and str(root).strip(), 'explicit-project-root-required')
        raw = Path(root).expanduser()
        require('..' not in raw.parts, 'parent-traversal-not-allowed')
        safe_path(raw.absolute())
        require(raw.is_dir(), 'project-root-must-exist')
        self.root = raw.resolve(strict=True)
        self.identity = digest(os.path.normcase(str(self.root)))
        self.base = self.root / '.knowledge'
        safe_tree(self.base)
        self.db = self.base / 'store.sqlite3'

    def describe(self):
        return {'root': str(self.root), 'identity': self.identity}
