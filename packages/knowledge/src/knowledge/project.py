"""One explicit resolver; reject links in all ancestors and store descendants."""
import os
from pathlib import Path
import stat
from .util import require, digest


def _linked_info(info):
    # lstat does not follow the final component. Windows junctions and other
    # reparse points are exposed by the same result, avoiding several extra
    # filesystem queries for every ancestor of every discovered source file.
    return stat.S_ISLNK(info.st_mode) or (os.name=='nt' and bool(getattr(info,'st_file_attributes',0)&0x400))


def linked(p):
    try:
        return _linked_info(Path(p).lstat())
    except (FileNotFoundError, NotADirectoryError):
        return False


def windows_spelling(p):
    import re
    p=Path(p);text=str(p)
    require(not text.startswith(('\\\\','//')) and (not p.drive or p.is_absolute()),'unsupported-windows-path')
    for name in p.parts[1:] if p.anchor else p.parts:
        require(not any(ch in name for ch in ':<>"|?*~') and not any(ord(ch)<32 for ch in name) and not name.endswith((' ','.')) and not re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?',name,re.I),'unsupported-windows-path')

def safe_path(p):
    p = Path(p)
    require('\0' not in str(p),'invalid-path')
    if os.name=='nt':windows_spelling(p)
    target_info = None
    for part in [p, *p.parents]:
        try:
            info = part.lstat()
        except (FileNotFoundError, NotADirectoryError):
            continue
        require(not _linked_info(info), 'linked-path')
        if part == p:
            target_info = info
    if target_info is not None:
        mode = target_info.st_mode
        require(stat.S_ISDIR(mode) or (stat.S_ISREG(mode) and target_info.st_nlink == 1),
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
