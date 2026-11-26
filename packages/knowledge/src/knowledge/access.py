"""Local installation policy. RPC arguments never select the operating mode."""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import sys

from .project import safe_path
from .util import read_text, loads, require

MODES = ('readonly', 'maintainer')
_readonly = ContextVar('knowledge_readonly', default=False)


def installation_mode(installation):
    path = safe_path(Path(installation) / 'current.json')
    if not path.exists():
        return 'maintainer'  # Pre-existing standalone invocations and installer staging.
    value = loads(read_text(path))
    require(isinstance(value, dict), 'invalid-installation-mode')
    mode = value.get('mode', 'maintainer')
    require(mode in MODES, 'invalid-installation-mode')
    return mode


def readonly(installation=None):
    if _readonly.get():
        return True
    runtime = Path(sys.prefix)
    if installation is None and runtime.parent.name == 'runtimes':
        installation = runtime.parent.parent
    return installation is not None and installation_mode(installation) == 'readonly'


def require_maintainer(installation=None):
    require(not readonly(installation), 'knowledge-readonly',
            {'mode': 'readonly', 'next_action': 'Use a maintainer installation for this operation.'})


@contextmanager
def consumer_scope(enabled=True):
    token = _readonly.set(enabled or _readonly.get())
    try:
        yield
    finally:
        _readonly.reset(token)


def verify_readable_database(path):
    # In WAL mode a read-only connection can still create sidecars or update
    # shared-memory marks. The default rollback-journal store has no such writes.
    with path.open('rb') as stream:
        header = stream.read(20)
    require(header[18:20] != b'\x02\x02', 'readonly-wal-database',
            {'next_action': 'Ask the maintainer for a checkpointed rollback-journal database or a read-only snapshot.'})
