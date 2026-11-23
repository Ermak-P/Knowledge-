"""Installed acceptance: ready kit/source, independent generations and rollback.

All host paths are redirected to temporary XDG directories. No real project,
user host registration, model or SDK is installed/changed by this trial.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def py_at(root): return root / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
def read(path): return json.loads(path.read_text(encoding='utf-8'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('kit', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args(); a.output = a.output.absolute(); a.output.mkdir(parents=True, exist_ok=True)
    result = {'profile': 'native-windows-powershell-5.1' if os.name == 'nt' else 'portable-linux', 'checks': {}, 'commands': [], 'live_model': False}
    def command(name, argv, env, cwd, input=None, expected=0):
        process = subprocess.run([str(x) for x in argv], cwd=cwd, env=env, input=input, encoding='utf-8', capture_output=True)
        (a.output / (name + '.log')).write_text(process.stdout + process.stderr, encoding='utf-8')
        result['commands'].append({'name': name, 'returncode': process.returncode, 'log': name + '.log', 'sha256': sha(a.output / (name + '.log'))})
        assert process.returncode == expected, (name, process.stdout[-2000:], process.stderr[-2000:])
        return process.stdout
    with tempfile.TemporaryDirectory(prefix='Knowledge machine Ω ') as tmp:
        base = Path(tmp); cwd = base / 'unrelated cwd'; cwd.mkdir(); (cwd / 'user.txt').write_bytes(b'preserve unrelated cwd')
        env = {**os.environ, 'XDG_CONFIG_HOME': str(base / 'host settings'), 'XDG_DATA_HOME': str(base / 'host data'), 'XDG_CACHE_HOME': str(base / 'cache'), 'XDG_STATE_HOME': str(base / 'state'), 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8', 'KNOWLEDGE_PYTHON': sys.executable}
        kit = base / 'ready kit'; shutil.copytree(a.kit, kit)
        runtime = base / 'машина runtime'
        # A complete pinned wheelhouse supplies actual offline MCP installation.
        command('download-pinned-wheelhouse-online', [sys.executable, '-I', '-m', 'pip', 'download', '--disable-pip-version-check', '--only-binary=:all:', '-r', kit / 'optional-mcp.lock', '-d', kit / 'wheelhouse'], env, cwd)
        manifest = read(kit / 'RELEASE.json')
        manifest['files'].update({p.relative_to(kit).as_posix(): sha(p) for p in (kit / 'wheelhouse').iterdir()})
        write(kit / 'RELEASE.json', manifest)
        write(a.output / 'wheelhouse.json', {p.name: sha(p) for p in (kit / 'wheelhouse').iterdir()})
        host = Path(env['XDG_CONFIG_HOME']) / 'opencode'; host.mkdir(parents=True)
        unrelated = host / 'opencode.json'; unrelated.write_bytes(b'{"mcp":{"servers":{"other":{"type":"local","command":["unrelated-preserved"]}}}}\n')
        original_host = unrelated.read_bytes()
        def install_args(source, target, ready):
            if os.name == 'nt':
                return ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', source / 'install.ps1', '-McpDir', target]
            return [sys.executable, '-I', '-X', 'utf8', source / ('machine-install.py' if ready else 'install.py'), '--mcp-dir', target]
        first = command('ready-kit-install', install_args(kit, runtime, True), env, cwd)
        assert first.startswith('INSTALLED'), first
        pointer = read(runtime / 'current.json')
        assert pointer['dependency_mode'] == 'offline-mcp-wheelhouse'
        result['checks']['ready_kit_offline_mcp'] = 'PASS'
        assert unrelated.read_bytes() == original_host and not (cwd / '.knowledge').exists() and not (kit / '.knowledge').exists()
        result['checks']['no_project_install_and_unrelated_host_preserved'] = 'PASS'
        old = (runtime / 'current.json').read_bytes()
        repeated = command('same-kit', install_args(kit, runtime, True), env, cwd)
        assert repeated.startswith('UNCHANGED') and (runtime / 'current.json').read_bytes() == old
        result['checks']['verified_noop'] = 'PASS'
        provider = runtime / 'config/provider.json'
        fresh_default = read(kit / 'default-provider.json'); fresh_default['provider']['model'] = 'factory-default-refresh'
        write(kit / 'default-provider.json', fresh_default)
        manifest['files']['default-provider.json'] = sha(kit / 'default-provider.json'); write(kit / 'RELEASE.json', manifest)
        command('unchanged-factory-default-refresh', install_args(kit, runtime, True), env, cwd)
        assert read(provider) == fresh_default
        result['checks']['unmodified_factory_default_updates_verifiably'] = 'PASS'
        custom = read(provider); custom['provider']['model'] = 'user-edited-demo'; write(provider, custom)
        shared = runtime / 'shared/user-memory.bin'; shared.parent.mkdir(); shared.write_bytes(b'preserve user memory')
        # Controlled same-version factory change forces a new generation.
        factory = read(kit / 'default-provider.json'); factory['provider']['model'] = 'new-factory-demo'; write(kit / 'default-provider.json', factory)
        manifest['files']['default-provider.json'] = sha(kit / 'default-provider.json'); write(kit / 'RELEASE.json', manifest)
        changed = command('same-version-update', install_args(kit, runtime, True), env, cwd)
        assert changed.startswith('UPDATED') and (runtime / 'current.json').read_bytes() != old
        assert read(provider) == custom and shared.read_bytes() == b'preserve user memory' and unrelated.read_bytes() == original_host
        result['checks']['user_provider_memory_and_registrations_preserved'] = 'PASS'
        previous = {name: (runtime / name).read_bytes() for name in ('current.json', 'knowledge-machine-install.json', 'launch.py')}
        # Real staging/handshake, then a transaction fault. Rollback must retain
        # the previous actual installed interpreter and global registration.
        factory['provider']['model'] = 'fault-factory-demo'; write(kit / 'default-provider.json', factory)
        manifest['files']['default-provider.json'] = sha(kit / 'default-provider.json'); write(kit / 'RELEASE.json', manifest)
        namespace = runpy.run_path(str(kit / 'machine-install.py'))
        with_env = dict(os.environ)
        try:
            os.environ.update(env)
            try: namespace['install'](kit, runtime, fail_after=8)
            except namespace['InstallError'] as error: assert 'Injected' in str(error), str(error)
            else: raise AssertionError('Transaction fault did not occur')
        finally:
            os.environ.clear(); os.environ.update(with_env)
        assert all((runtime / name).read_bytes() == payload for name, payload in previous.items())
        assert read(provider) == custom and shared.read_bytes() == b'preserve user memory'
        command('previous-generation-still-operates', [py_at(runtime / 'bootstrap'), '-I', runtime / 'launch.py', 'mcp', '--self-test'], env, cwd)
        result['checks']['failed_update_rolls_back_and_previous_mcp_operates'] = 'PASS'
        for path in (runtime / 'logs').iterdir(): shutil.copyfile(path, a.output / ('ready-install-' + path.name))
        # A source-only checkout with an arbitrary name, invoked from another
        # CWD. No setup/build is run by the user/trial before the launcher.
        source = base / 'Konwledge--main исходники'
        source.mkdir()
        for folder in ('packages', 'release/p4-kit', 'docs/P4', 'examples/p4', 'installer'):
            shutil.copytree(ROOT / folder, source / folder, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.egg-info', 'build', 'dist', 'bin', 'obj'))
        (source / 'scripts').mkdir(); shutil.copyfile(ROOT / 'scripts/build_p4.py', source / 'scripts/build_p4.py')
        (source / 'inputs').mkdir(); shutil.copyfile(ROOT / 'inputs/README.md', source / 'inputs/README.md')
        for name in ('install.py', 'install.ps1', 'install.sh', 'knowledge-init-auto.py'): shutil.copyfile(ROOT / name, source / name)
        source_env = {**env, 'XDG_CONFIG_HOME': str(base / 'source host')}
        standalone = base / 'исходники установленный runtime'
        clean = command('source-one-parameter', install_args(source, standalone, False), source_env, cwd)
        assert clean.startswith('INSTALLED'), clean
        current = read(standalone / 'current.json')
        installed_python = py_at(standalone / current['runtime'])
        assert not (source / '.knowledge').exists() and not (cwd / '.knowledge').exists()
        # Changing code bytes, preserving the project version, must not reuse
        # the first wheel. This mutation exists ONLY in the temporary fixture.
        module = source / 'packages/knowledge/src/knowledge/__init__.py'
        module.write_text(module.read_text(encoding='utf-8') + '\nMACHINE_INSTALL_TEST = "changed-source-bytes"\n', encoding='utf-8')
        changed_source_hash = sha(module)
        changed = command('source-same-version-new-bytes', install_args(source, standalone, False), source_env, cwd)
        assert changed.startswith('UPDATED')
        new_current = read(standalone / 'current.json'); assert current['source_identity'] != new_current['source_identity']
        installed_python = py_at(standalone / new_current['runtime'])
        imported = command('installed-changed-code', [installed_python, '-I', '-c', 'import knowledge,hashlib; from pathlib import Path; assert knowledge.MACHINE_INSTALL_TEST=="changed-source-bytes"; print(hashlib.sha256(Path(knowledge.__file__).read_bytes()).hexdigest())'], source_env, cwd)
        assert imported.strip() == changed_source_hash
        result['checks']['same_version_new_source_bytes_delivered'] = 'PASS'
        shutil.rmtree(source)
        command('source-deleted-mcp', [py_at(standalone / 'bootstrap'), '-I', standalone / 'launch.py', 'mcp', '--self-test'], source_env, cwd)
        root = base / 'active project'; root.mkdir(); (root / 'Example.cs').write_text('public class Example {}\n')
        (root / 'Example.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>')
        for argv in (['git', 'init', str(root)], ['git', '-C', str(root), 'add', '.'], ['git', '-C', str(root), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'fixture']):
            subprocess.run(argv, check=True, capture_output=True)
        def backend(name, value):
            return json.loads(command('source-deleted-' + name + '-' + str(len(result['commands'])), [py_at(standalone / 'bootstrap'), '-I', standalone / 'launch.py', 'command', name, '--root', root], source_env, cwd, json.dumps(value)))
        backend('knowledge-init', {})
        for _ in range(100):
            value = backend('knowledge-init', {'action': 'status'})
            if value['state'] not in ('STARTING', 'RUNNING'): break
            time.sleep(.1)
        assert value['coverage_complete'] and value['state'] == 'PARTIAL', value
        plan = backend('knowledge-candidates-push', {})
        assert plan['state'] == 'AWAITING_EXACT_APPROVAL'
        backend('knowledge-candidates-push', {'approve': plan['fingerprint']})
        (root / 'Added.cs').write_text('public class Added {}\n')
        backend('knowledge-candidates-update', {})
        for _ in range(100):
            value = backend('knowledge-candidates-update', {'action': 'status'})
            if value['state'] not in ('STARTING', 'RUNNING'): break
            time.sleep(.1)
        assert value['coverage_complete'] and value['work']['durable_extracted_files'] == 1, value
        command('source-deleted-helper-wrapper', [py_at(standalone / 'bootstrap'), '-I', standalone / 'knowledge-init-auto.py', '--root', root, '--output', base / 'manual helper diagnostics'], source_env, cwd)
        assert all((Path(source_env['XDG_CONFIG_HOME']) / 'opencode/knowledge-machine-templates' / (name + '.md')).is_file() for name in ('knowledge-init', 'knowledge-candidates-update', 'knowledge-candidates-push'))
        result['checks']['deleted_source_mcp_commands_and_helper_independent'] = 'PASS'
        for path in (standalone / 'logs').iterdir(): shutil.copyfile(path, a.output / ('source-install-' + path.name))
        result['source_install'] = {'first': current, 'updated': new_current, 'installed_module_sha256': imported.strip(), 'source_fixture_deleted': True}
        legacy = base / 'legacy owned runtime'
        legacy_env = {**env, 'XDG_CONFIG_HOME': str(base / 'legacy host')}
        command('legacy-low-level-core-install', [sys.executable, '-I', kit / 'install.py', 'install', '--env', legacy, '--profile', 'knowledge'], legacy_env, cwd)
        old_marker = (legacy / 'knowledge-release-install.json').read_bytes()
        command('legacy-owned-auto-recognition', install_args(kit, legacy, True), legacy_env, cwd)
        assert (legacy / 'knowledge-release-install.json').read_bytes() == old_marker
        assert read(legacy / 'knowledge-machine-install.json')['legacy']['owned_packages'] == ['knowledge-p0']
        command('legacy-now-machine-mcp', [py_at(legacy / 'bootstrap'), '-I', legacy / 'launch.py', 'mcp', '--self-test'], legacy_env, cwd)
        result['checks']['legacy_owned_venv_automatically_recognized_and_preserved'] = 'PASS'

    result['status'] = 'PASS'
    write(a.output / 'result.json', result)
    print(json.dumps({'ok': True, 'profile': result['profile'], 'checks': result['checks']}))


if __name__ == '__main__': main()
