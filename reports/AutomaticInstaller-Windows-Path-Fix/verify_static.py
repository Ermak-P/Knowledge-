"""Read/parse source and delivery bytes only; never run installer or tests."""
import ast
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    root = Path(__file__).resolve().parent
    repo = root.parents[1]
    source = json.loads((root / 'source.json').read_text(encoding='utf-8'))
    commit = source['commit']
    assert sha(json.dumps(source['source'], sort_keys=True).encode()) == source['source_identity']
    for name, wanted in source['source'].items():
        raw = subprocess.check_output(['git', 'show', commit + ':' + name], cwd=repo)
        assert sha(raw) == wanted, name
    inputs = ('installer/knowledge_install.py', 'packages/knowledge/src/knowledge/project.py')
    subprocess.run(['git', 'diff', '--check', commit + '^', commit, '--', *inputs,
                    'docs/P4/AutomaticInstallation-RU.md'], cwd=repo, check=True)
    for name in inputs:
        raw = subprocess.check_output(['git', 'show', commit + ':' + name], cwd=repo)
        tree = ast.parse(raw, filename=name)
        compile(tree, name, 'exec')  # Compilation only; no exec/import of product.
        if name.startswith('installer/'):
            function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'validate_provider')
            embedded = next(node.value.value for node in function.body if isinstance(node, ast.Assign)
                            and any(isinstance(target, ast.Name) and target.id == 'code' for target in node.targets))
            compile(ast.parse(embedded), name + ':validator', 'exec')
    subprocess.run(['git', 'diff', '--check', commit + '^', commit, '--', *inputs,
                    'docs/P4/AutomaticInstallation-RU.md'], cwd=repo, check=True)
    archive = root / 'distribution/knowledge-harness-0.5.0rc1.zip'
    with zipfile.ZipFile(archive) as kit:
        release = json.loads(kit.read('RELEASE.json'))
        assert release['source_identity'] == source['source_identity']
        assert set(kit.namelist()) == set(release['files']) | {'RELEASE.json'}
        for name, wanted in release['files'].items():
            assert sha(kit.read(name)) == wanted, name
        for delivered, original in (
            ('machine-install.py', inputs[0]),
            ('docs/AutomaticInstallation-RU.md', 'docs/P4/AutomaticInstallation-RU.md'),
        ):
            assert sha(kit.read(delivered)) == source['source'][original]
        name = next(name for name in kit.namelist() if name.startswith('wheels/knowledge_p0-') and name.endswith('.whl'))
        with zipfile.ZipFile(io.BytesIO(kit.read(name))) as wheel:
            assert sha(wheel.read('knowledge/project.py')) == source['source'][inputs[1]]
    built = json.loads((root / 'build.log').read_text(encoding='utf-8').splitlines()[-1])
    assert sha(archive.read_bytes()) == built['sha256']
    value = {
        'status': 'PASS', 'mode': 'static-only', 'commit': commit,
        'source_identity': source['source_identity'], 'build_inputs': len(source['source']),
        'checks': ['source Git blob hashes', 'Python and embedded validator syntax', 'git diff --check',
                   'release file inventory and hashes', 'installer/doc/wheel contain exact fixed source bytes', 'archive build hash'],
        'tests_run': False, 'installer_executed': False, 'windows_installation': 'NOT_RUN',
        'reported_owner_failure_root_cause': 'UNCONFIRMED: original rejected path/log not available',
        'archive_sha256': built['sha256'],
    }
    (root / 'static-check.json').write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(value, ensure_ascii=False))


if __name__ == '__main__':
    main()
