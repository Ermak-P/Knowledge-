"""Owned machine installation. Python 3.12 stdlib bootstrap, no project access.

Generations are immutable after verification. A durable undo journal protects
registration/configuration and the current pointer; interrupted transactions
are rolled back before the next install. Old generations keep open MCPs alive.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid
from contextlib import contextmanager

VERSION = '0.5.0rc1'
MARKER = 'knowledge-machine-install.json'
BOOTSTRAP = '''import json, os, sys
from pathlib import Path
root = Path(__file__).resolve().parent
value = json.loads((root / 'current.json').read_text(encoding='utf-8'))
python = root / value['runtime'] / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
if len(sys.argv) < 2 or sys.argv[1] not in ('mcp', 'command', 'auto'):
    raise SystemExit('Use mcp, command or auto')
module = {'mcp':'knowledge.machine_mcp', 'command':'knowledge.project_commands', 'auto':'knowledge.auto_init'}[sys.argv[1]]
args = [str(python), '-I', '-B', '-X', 'utf8', '-m', module]
if sys.argv[1] != 'auto': args += ['--installation', str(root)]
os.execv(str(python), args + sys.argv[2:])
'''


class InstallError(Exception):
    pass


def require(value, message):
    if not value:
        raise InstallError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def data(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def safe(path):
    path = Path(path).absolute()
    for item in (path, *path.parents):
        require(not item.is_symlink() and not item.is_junction(), 'Linked installation/registration path refused: ' + str(item))
    if path.is_file():
        require(path.stat().st_nlink == 1, 'Hard-linked owned file refused: ' + str(path))
    return path


def atomic(path, content):
    path = safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.knowledge-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def lock(path):
    path = safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open('a+b')
    try:
        if os.name == 'nt':
            import msvcrt
            if not path.stat().st_size:
                stream.write(b'0'); stream.flush()
            stream.seek(0)
            try: msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error: raise InstallError('Another machine installation is active: ' + str(path)) from error
        else:
            import fcntl
            try: fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error: raise InstallError('Another machine installation is active: ' + str(path)) from error
        yield
    finally:
        stream.close()


def py_at(root):
    return Path(root) / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def call(argv, log, cwd=None):
    with log.open('ab') as stream:
        result = subprocess.run([str(x) for x in argv], cwd=cwd, stdin=subprocess.DEVNULL,
                                stdout=stream, stderr=subprocess.STDOUT,
                                env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8', 'PYTHONDONTWRITEBYTECODE': '1'})
    require(result.returncode == 0, 'Build/install/verification failed; see ' + str(log))


def verify_kit(root):
    safe(root)
    manifest = read(root / 'RELEASE.json')
    require(manifest.get('product') == VERSION and manifest.get('python') == '3.12', 'Unsupported release kit')
    require(isinstance(manifest.get('files'), dict) and manifest['files'], 'Empty release manifest')
    for relative, expected in manifest['files'].items():
        require(isinstance(relative, str) and relative and chr(92) not in relative, 'Unsafe release member')
        item = Path(relative)
        require(not item.is_absolute() and not item.drive and '..' not in item.parts and item.as_posix() == relative, 'Unsafe release member')
        item = safe(root / item)
        require(item.is_file() and sha(item) == expected, 'Release hash mismatch: ' + relative)
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.name != 'RELEASE.json'}
    require(actual == set(manifest['files']), 'Unlisted/missing release files refused')
    for name in ('machine-install.py', 'default-provider.json', 'knowledge-init-auto.py', 'optional-mcp.lock', 'host/machine_opencode.mjs'):
        require(name in manifest['files'], 'Machine installer asset absent: ' + name)
    return manifest


def source_kit(source, work, log):
    if (source / 'RELEASE.json').is_file():
        verify_kit(source)
        return source
    require((source / 'scripts/build_p4.py').is_file() and (source / 'packages/knowledge/pyproject.toml').is_file()
            and (source / 'installer/default-provider.json').is_file(), 'Launch from the source or verified release launcher')
    # Hash the build closure, not Git HEAD (uncommitted/same-version bytes matter).
    files = []
    for folder in ('packages', 'release/p4-kit', 'docs/P4', 'examples/p4', 'installer'):
        files.extend(p for p in (source / folder).rglob('*') if p.is_file() and not any(
            part in ('__pycache__', 'build', 'dist', 'bin', 'obj') or part.endswith('.egg-info') for part in p.relative_to(source).parts))
    files += [source / 'scripts/build_p4.py', source / 'knowledge-init-auto.py', source / 'inputs/README.md']
    identity = hashlib.sha256(data({p.relative_to(source).as_posix(): sha(safe(p)) for p in sorted(files)})).hexdigest()
    build = work / 'builder'
    call([sys.executable, '-I', '-m', 'venv', build], log)
    call([py_at(build), '-I', '-m', 'pip', 'install', '--disable-pip-version-check', 'setuptools==80.9.0'], log)
    call([py_at(build), '-I', source / 'scripts/build_p4.py', '--output', work / 'distribution', '--source-id', identity], log)
    kit = work / 'distribution/knowledge-harness-0.5.0rc1'
    verify_kit(kit)
    return kit


def config_home():
    return Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config') / 'opencode'


def jsonc(text):
    """Read comments/trailing commas without rewriting a user's host file."""
    out = []; index = 0; quoted = False
    while index < len(text):
        char = text[index]
        if quoted:
            out.append(char)
            if char == chr(92) and index + 1 < len(text):
                index += 1; out.append(text[index])
            elif char == '"': quoted = False
        elif char == '"': quoted = True; out.append(char)
        elif text.startswith('//', index):
            end = text.find(chr(10), index)
            index = len(text) if end < 0 else end
            continue
        elif text.startswith('/*', index):
            end = text.find('*/', index + 2)
            require(end >= 0, 'Invalid OpenCode JSONC comment')
            out.append(' '); index = end + 2
            continue
        elif char == ',':
            # Comments are stripped first; trailing comma is handled below.
            out.append(char)
        else: out.append(char)
        index += 1
    text = ''.join(out); out = []; index = 0; quoted = False
    while index < len(text):
        char = text[index]
        if quoted:
            out.append(char)
            if char == chr(92) and index + 1 < len(text):
                index += 1; out.append(text[index])
            elif char == '"': quoted = False
        elif char == '"': quoted = True; out.append(char)
        elif char == ',':
            following = text[index + 1:].lstrip()
            if not following.startswith(('}', ']')): out.append(char)
        else: out.append(char)
        index += 1
    return json.loads(''.join(out))


def preflight_host(home):
    for folder in ('commands', 'command'):
        for name in ('knowledge-init', 'knowledge-candidates-update', 'knowledge-candidates-push'):
            path = safe(home / folder / (name + '.md'))
            require(not path.exists(), 'Existing global command conflicts; preserved: ' + str(path))
    for name in ('config.json', 'opencode.json', 'opencode.jsonc'):
        path = safe(home / name)
        if not path.exists(): continue
        value = jsonc(path.read_text(encoding='utf-8-sig'))
        require(isinstance(value, dict), 'Invalid global OpenCode configuration: ' + str(path))
        mcp = value.get('mcp', {})
        servers = mcp.get('servers', {}) if isinstance(mcp, dict) else None
        require(isinstance(servers, dict) and 'knowledge_machine' not in servers and 'knowledge_machine' not in mcp, 'Existing MCP knowledge_machine conflicts; global configuration preserved: ' + str(path))
        commands = value.get('commands', {})
        require(isinstance(commands, dict) and not set(commands).intersection({'knowledge-init', 'knowledge-candidates-update', 'knowledge-candidates-push'}), 'Existing named Knowledge command conflicts; global configuration preserved: ' + str(path))


def legacy_owned(root):
    """Conservative adoption: validate the old marker, prefix and every RECORD.

    Never uninstall/mutate the old venv. Unrecognized top-level files or extra
    distributions require an explicit recovery decision outside this installer.
    """
    marker = root / 'knowledge-release-install.json'
    if not marker.is_file():
        return None
    old = read(safe(marker))
    require(old.get('version') == 1 and os.path.normcase(old.get('environment', '')) == os.path.normcase(str(root))
            and old.get('product') in ('0.3.0rc1', '0.4.0rc1', '0.4.0rc2', '0.4.0rc3', '0.4.0rc4', VERSION)
            and set(old.get('owned_packages', [])) in ({'knowledge-p0'}, {'knowledge-p0', 'harness-p0'}), 'Legacy ownership mismatch')
    allowed = {'Scripts', 'bin', 'lib', 'lib64', 'Lib', 'Include', 'include', 'share', 'etc', 'pyvenv.cfg', '.gitignore', marker.name}
    require(all(p.name in allowed and (p.name == 'lib64' or not p.is_symlink()) for p in root.iterdir()), 'Unrelated content in legacy environment; preserved')
    if (root / 'lib64').is_symlink():
        require((root / 'lib64').resolve() == root / 'lib', 'Unrelated legacy lib64 link; preserved')
    code = '''import importlib.metadata as m, json, sys, hashlib, base64
from pathlib import Path
assert Path(sys.prefix).resolve() == Path(sys.argv[1]).resolve()
allowed = set(json.loads(sys.argv[2]))
names = set(); owned = set(); root = Path(sys.prefix).resolve()
for d in m.distributions():
 n = d.metadata['Name'].lower().replace('_','-'); names.add(n)
 assert n in allowed, 'unrelated installed distribution: '+n
 if n in {'knowledge-p0','harness-p0'}: assert d.version == sys.argv[4], 'legacy product/version mismatch'
 for f in d.files or []:
  owned.add(Path(d.locate_file(f)).resolve())
  if f.hash:
   p=Path(d.locate_file(f)); assert p.is_file(), str(p)
   assert base64.urlsafe_b64encode(hashlib.new(f.hash.mode,p.read_bytes()).digest()).rstrip(b'=').decode()==f.hash.value, str(p)
assert set(json.loads(sys.argv[3])) <= names
venv_files = {'pyvenv.cfg', '.gitignore', 'knowledge-release-install.json'}
venv_scripts = {'python', 'python3', 'python3.12', 'python.exe', 'pythonw.exe', 'activate', 'activate.csh', 'activate.fish', 'Activate.ps1', 'activate.bat', 'deactivate.bat'}
for p in root.rglob('*'):
 if not p.is_file(): continue
 rel = p.relative_to(root)
 if p.resolve() in owned or str(rel) in venv_files: continue
 if len(rel.parts)==2 and rel.parts[0] in ('bin','Scripts') and rel.name in venv_scripts: continue
 if p.suffix=='.pyc' and p.parent.name=='__pycache__' and (p.parent.parent / (p.name.split('.')[0]+'.py')).resolve() in owned: continue
 raise AssertionError('unowned legacy file: '+str(rel))
print(json.dumps(sorted(names)))
'''
    pinned = {line.split('==')[0].lower().replace('_', '-') for line in (Path(__file__).parent / 'optional-mcp.lock').read_text().splitlines() if '==' in line} if (Path(__file__).parent / 'optional-mcp.lock').exists() else set()
    # Source layout carries the same lock under release/p4-kit.
    if not pinned:
        pinned = {line.split('==')[0].lower().replace('_', '-') for line in (Path(__file__).parent.parent / 'release/p4-kit/optional-mcp.lock').read_text().splitlines() if '==' in line}
    result = subprocess.run([str(py_at(root)), '-I', '-c', code, str(root), json.dumps(sorted(pinned | {'knowledge-p0', 'harness-p0', 'pip', 'setuptools'})), json.dumps(old['owned_packages']), old['product']], capture_output=True, text=True)
    require(result.returncode == 0, 'Legacy environment integrity/ownership not established; preserved')
    return old


def rollback(root):
    journal = root / 'transaction.json'
    if not journal.exists():
        return
    import base64
    intent = read(safe(journal))
    require(intent.get('root') == str(root), 'Rollback root mismatch')
    # Preflight ALL entries before restoring any; concurrent edits are preserved.
    for entry in intent['entries']:
        path = safe(entry['path'])
        current = sha(path) if path.exists() else None
        require(current in (entry['before_hash'], entry['after_hash']), 'Concurrent edit blocks rollback: ' + str(path))
    for entry in reversed(intent['entries']):
        path = Path(entry['path'])
        if entry['before'] is None:
            if path.exists(): path.unlink()
        else:
            atomic(path, base64.b64decode(entry['before']))
    journal.unlink()


def transaction(root, updates, fail_after=None):
    import base64
    entries = []
    for path, content in updates.items():
        path = safe(path)
        before = path.read_bytes() if path.exists() else None
        entries.append({'path': str(path), 'before': base64.b64encode(before).decode() if before is not None else None,
                        'before_hash': hashlib.sha256(before).hexdigest() if before is not None else None,
                        'after_hash': hashlib.sha256(content).hexdigest()})
    atomic(root / 'transaction.json', data({'version': 1, 'root': str(root), 'entries': entries}))
    try:
        for number, (path, content) in enumerate(updates.items(), 1):
            entry = entries[number - 1]
            require((sha(path) if path.exists() else None) == entry['before_hash'], 'Concurrent edit during installation: ' + str(path))
            atomic(path, content)
            if fail_after == number:
                raise InstallError('Injected transaction interruption')
    except BaseException:
        rollback(root)
        raise
    (root / 'transaction.json').unlink()


def inventory(root):
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob('*')) if p.is_file()
            and p.name != 'generation-files.json'}


def installed_ok(root, current):
    generation = safe(root / current['runtime'])
    require(generation.is_relative_to(root / 'runtimes'), 'Invalid runtime reference')
    manifest_path = safe(generation / 'generation-files.json')
    require(sha(manifest_path) == current.get('generation_manifest_sha256'), 'Runtime integrity manifest changed')
    expected = read(manifest_path)
    return inventory(generation) == expected


def install(source, root, fail_after=None):
    require(sys.version_info[:2] == (3, 12), 'Python 3.12 is required. Install Python 3.12 from python.org, then rerun this command.')
    source = safe(source).resolve(strict=True)
    root = safe(root).resolve()
    require(not Path(sys.base_prefix).resolve().is_relative_to(source), 'Python base runtime is inside temporary source. Install Python 3.12 from python.org, then rerun.')
    require(not root.is_relative_to(source) and not source.is_relative_to(root), 'McpDir and source must be separate directories')
    marker = root / MARKER
    old = None
    legacy = None
    if root.exists() and any(root.iterdir()) and not marker.exists():
        legacy = legacy_owned(root)
        require(legacy is not None, 'McpDir is not an owned Knowledge installation; unrelated contents preserved: ' + str(root))
    if marker.exists():
        old = read(safe(marker))
        require(old.get('version') == 1 and old.get('root') == str(root) and old.get('product') == 'knowledge-machine', 'Machine ownership mismatch')
    home = safe(config_home().absolute()).resolve()
    preflight_host(home)
    require(old is None or old.get('host_home') == str(home), 'Host registration directory changed; preserve the original XDG_CONFIG_HOME or resolve the registration explicitly.')
    # Global command/plugin names are owned only after a recorded installation.
    targets = [home / 'plugins/knowledge-machine.js', home / '.knowledge-machine.json']
    targets += [home / 'knowledge-machine-templates' / (name + '.md') for name in ('knowledge-init', 'knowledge-candidates-update', 'knowledge-candidates-push')]
    if old:
        require(old.get('host_home') == str(home), 'Host configuration location changed; preserve the old registration and resolve explicitly')
    for path in targets:
        safe(path)
        if path.exists():
            require(old is not None and old.get('files', {}).get(str(path)) == sha(path), 'Unowned or edited global host file; preserved: ' + str(path))
    host = shutil.which('opencode')
    host_version = None
    if host:
        check = subprocess.run([host, '--version'], capture_output=True, text=True, timeout=30)
        host_version = check.stdout.strip().removeprefix('opencode v')
        require(check.returncode == 0 and host_version == '2.4.0', 'Supported OpenCode version is 2.4.0; found ' + host_version)
    root.mkdir(parents=True, exist_ok=True)
    # Reservation supports retry after a failed first install, without adopting
    # arbitrary directories. It does not claim a working runtime.
    if old is None:
        old = {'version': 1, 'product': 'knowledge-machine', 'root': str(root), 'host_home': str(home), 'state': 'preparing', 'files': {}, 'legacy': legacy}
        atomic(marker, data(old))
    with lock(root / 'install.lock'), lock(home / '.knowledge-install.lock'):
        rollback(root)
        old = read(marker)
        for owned, expected in old['files'].items():
            owned_path = safe(owned)
            require(not owned_path.exists() or (owned_path.is_file() and sha(owned_path) == expected), 'Owned installation file edited; preserved: ' + owned)
        for path in targets:
            safe(path)
            if path.exists():
                require(str(path) in old['files'] and sha(path) == old['files'][str(path)], 'Global Knowledge command/registration conflict; existing file preserved: ' + str(path))
        log = root / 'logs' / (uuid.uuid4().hex + '.log')
        log.parent.mkdir(exist_ok=True)
        log.touch()
        with tempfile.TemporaryDirectory(prefix='knowledge-install-') as temporary:
            kit = source_kit(source, Path(temporary), log)
            release = verify_kit(kit)
            release_hash = sha(kit / 'RELEASE.json')
            current = read(safe(root / 'current.json')) if (root / 'current.json').exists() else None
            require(current == old.get('current'), 'Installation pointer/marker mismatch; preserved for recovery')
            provider_path = safe(root / 'config/provider.json')
            files_intact = all(Path(p).is_file() and sha(p) == h for p, h in old['files'].items())
            require(not current or provider_path.is_file(), 'Shared provider is missing; restore config/provider.json from your backup, then rerun.')
            if current and current.get('release_sha256') == release_hash and files_intact and py_at(root / 'bootstrap').is_file() and installed_ok(root, current):
                require(all(Path(p).is_file() and sha(p) == h for p, h in old['files'].items()), 'Owned machine files changed; cannot claim unchanged')
                call([py_at(root / current['runtime']), '-I', '-c', 'from knowledge.providers import shared; shared(__import__("sys").argv[1])', provider_path], log)
                return summary('UNCHANGED', root, current, provider_path, log, host_version)
            generation = root / 'runtimes' / uuid.uuid4().hex
            generation.parent.mkdir(exist_ok=True)
            call([sys.executable, '-I', '-m', 'venv', generation], log)
            python = py_at(generation)
            wheelhouse = kit / 'wheelhouse'
            mode = 'offline-mcp-wheelhouse' if wheelhouse.is_dir() else 'online-pinned-mcp'
            pip = [python, '-I', '-m', 'pip', 'install', '--disable-pip-version-check']
            dependencies = ['--no-index', '--find-links', str(wheelhouse)] if wheelhouse.is_dir() else []
            call([*pip, *dependencies, '-r', kit / 'optional-mcp.lock'], log)
            wheels = sorted((kit / 'wheels').glob('knowledge_p0-*.whl'))
            if 'harness-p0' in (old.get('legacy') or {}).get('owned_packages', []):
                wheels += sorted((kit / 'wheels').glob('harness_p0-*.whl'))
            require(wheels, 'Knowledge wheel absent')
            call([*pip, '--no-index', '--no-deps', '--force-reinstall', *wheels], log)
            shutil.copyfile(kit / 'knowledge-init-auto.py', generation / 'knowledge-init-auto.py')
            shutil.copyfile(kit / 'RELEASE.json', generation / 'RELEASE.json')
            call([python, '-I', '-c', 'from knowledge.providers import shared; shared(__import__("sys").argv[1]); import knowledge,mcp; assert knowledge.__version__=="0.5.0rc1"', kit / 'default-provider.json'], log)
            if provider_path.exists():
                call([python, '-I', '-c', 'from knowledge.providers import shared; shared(__import__("sys").argv[1])', provider_path], log)
            # A real stdio transport check, with no project and no model.
            call([python, '-I', '-m', 'knowledge.machine_mcp', '--self-test', '--installation', root], log)
            atomic(generation / 'generation-files.json', data(inventory(generation)))
            bootstrap = root / 'bootstrap'
            if not py_at(bootstrap).exists():
                call([sys.executable, '-I', '-m', 'venv', '--without-pip', bootstrap], log)
            selected = {'version': 1, 'runtime': generation.relative_to(root).as_posix(), 'product': VERSION,
                        'generation_manifest_sha256': sha(generation / 'generation-files.json'), 'release_sha256': release_hash, 'source_identity': release['source_identity'], 'dependency_mode': mode}
            updates = {}
            default_hash = sha(kit / 'default-provider.json')
            if not provider_path.exists() or sha(provider_path) == old.get('factory_provider_sha256'):
                updates[provider_path] = (kit / 'default-provider.json').read_bytes()
            updates[root / 'launch.py'] = BOOTSTRAP.encode()
            settings = {'version': 1, 'installation': str(root), 'python': str(py_at(bootstrap)), 'launcher': str(root / 'launch.py'), 'host_contract': 'opencode-2.4.0'}
            updates[home / '.knowledge-machine.json'] = data(settings)
            updates[home / 'plugins/knowledge-machine.js'] = (kit / 'host/machine_opencode.mjs').read_bytes()
            for name in ('knowledge-init', 'knowledge-candidates-update', 'knowledge-candidates-push'):
                updates[home / 'knowledge-machine-templates' / (name + '.md')] = (kit / 'commands' / (name + '.md')).read_bytes()
            # Root-local helpers use the same immutable generation backend.
            updates[root / 'knowledge-init-auto.py'] = (kit / 'knowledge-init-auto.py').read_bytes()
            files = {str(p): hashlib.sha256(b).hexdigest() for p, b in updates.items() if p != provider_path}
            updates[root / 'current.json'] = data(selected)
            value = {**old, 'state': 'installed', 'current': selected, 'files': files, 'factory_provider_sha256': default_hash}
            updates[marker] = data(value)
            transaction(root, updates, fail_after)
            return summary('UPDATED' if current or legacy else 'INSTALLED', root, selected, provider_path, log, host_version)


def summary(status, root, current, provider, log, host_version):
    return {'status': status, 'path': str(root), 'version': VERSION, 'source_identity': current['source_identity'],
            'provider': str(provider), 'mcp': 'stdio handshake/list-tools verified', 'commands': '3 global OpenCode commands installed',
            'host': host_version or 'OpenCode 2.4.0 contract; executable not on PATH', 'reload': 'Restart the host to launch the current MCP generation. Existing processes are retained.',
            'dependency_mode': current['dependency_mode'], 'log': str(log)}


def main(source):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mcp-dir', '-McpDir', type=Path, required=True)
    args = parser.parse_args()
    try:
        value = install(Path(source), args.mcp_dir.absolute())
        print(value['status'] + ' ' + value['path'])
        print('Version: ' + value['version'] + '; source: ' + value['source_identity'])
        print('Provider: ' + value['provider'])
        print(value['mcp'] + '; ' + value['commands'])
        print(value['reload'])
        print('Log: ' + value['log'])
        return 0
    except (InstallError, OSError, ValueError, subprocess.SubprocessError) as error:
        print('FAILED: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main(Path(__file__).resolve().parent))
