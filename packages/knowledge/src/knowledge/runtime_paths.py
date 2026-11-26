"""Project-local runtime paths and the stable infrastructure of a live store."""
from pathlib import Path

from .util import require

DIRECTORY = '.knowledge'
CONTROL_LOCK = '.knowledge-control.lock'
WRITER_LOCK = '.harness-writer.lock'
LEGACY = ('.maintenance', CONTROL_LOCK, WRITER_LOCK)
INFRASTRUCTURE = {'locks', 'maintenance', 'tmp'}


class RuntimePaths:
    def __init__(self, root):
        self.root = Path(root)
        self.base = self.root / DIRECTORY
        self.db = self.base / 'store.sqlite3'
        self.locks = self.base / 'locks'
        self.control = self.locks / CONTROL_LOCK
        self.writer = self.locks / WRITER_LOCK
        self.maintenance = self.base / 'maintenance'
        self.fence = self.maintenance / 'active.json'
        self.temp = self.base / 'tmp'

    def check_legacy(self):
        from .project import safe_path

        present = [name for name in LEGACY if safe_path(self.root / name).exists()]
        require(not present, 'legacy-runtime-layout', {'artifacts': present,
                'next_action': 'Stop all Knowledge and Harness processes and run knowledge-maintain runtime-migrate --offline.'})


def data_entries(base):
    """Live locks and maintenance journals survive store restore/cutover."""
    if not base.exists():
        return []
    return sorted(p for p in base.iterdir() if p.name.casefold() not in INFRASTRUCTURE or base.name.casefold() != DIRECTORY)


def move_entries(source, destination):
    """Move owned entries one at a time without overwriting a destination."""
    from .project import safe_tree

    safe_tree(source)
    safe_tree(destination)
    entries = data_entries(source)
    require(not any((destination / entry.name).exists() for entry in entries), 'runtime-data-destination-conflict')
    destination.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        entry.rename(destination / entry.name)


def storage_files(base):
    return (file for child in data_entries(base)
            for file in ([child] if child.is_file() else child.rglob('*')) if file.is_file())


def ignore_runtime(runtime):
    """Add a local Git ignore rule while preserving the repository's tracked files."""
    from .discovery import git, git_process, has_git
    from .project import safe_path

    root = runtime.root
    if not has_git(root) or git_process(root, 'check-ignore', '--no-index', '--quiet', '--', DIRECTORY + '/').returncode == 0:
        return
    exclude = safe_path(Path(git(root, 'rev-parse', '--path-format=absolute', '--git-path', 'info/exclude', required=True)))
    exclude.parent.mkdir(parents=True, exist_ok=True)
    with exclude.open('ab') as stream:
        stream.write(b'\n.knowledge/\n')
