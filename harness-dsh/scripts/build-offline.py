#!/usr/bin/env python3
"""Create a verified, production-offline Harness source distribution."""
import argparse
import base64
import hashlib
import csv
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import zipfile

VERSION = '0.2.3'
NPM = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
NODE = shutil.which('node')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def integrity(data):
    return 'sha512-' + base64.b64encode(hashlib.sha512(data).digest()).decode('ascii')


def name_of(path):
    return path.split('node_modules/')[-1]


def archive_name(name, version):
    require(re.fullmatch(r'(?:@[a-zA-Z0-9_.-]+/)?[a-zA-Z0-9_.-]+', name), 'Invalid package name: ' + name)
    require(re.fullmatch(r'[0-9][a-zA-Z0-9.+-]*', version), 'Invalid version: ' + version)
    return name.lstrip('@').replace('/', '-') + '-' + version + '.tgz'


def run(args, cwd):
    if os.name == 'nt' and args[0] == NPM:
        cli = Path(NPM).parent/'node_modules/npm/bin/npm-cli.js'
        require(cli.is_file(), 'Cannot locate npm-cli.js next to npm.cmd')
        subprocess.run([NODE, str(cli), *args[1:]], cwd=cwd, check=True)
    else:
        subprocess.run(args, cwd=cwd, check=True)


def check_archive(path, name, version, expected):
    data = path.read_bytes()
    require(integrity(data) == expected, 'SHA-512 mismatch: ' + str(path))
    with tarfile.open(path, 'r:gz') as tar:
        manifest = json.load(tar.extractfile('package/package.json'))
        require((manifest['name'], manifest['version']) == (name, version), 'Wrong package identity: ' + str(path))
        require(manifest.get('license') in ('MIT', 'Apache-2.0'), 'Review license: ' + str(path))
        files = [m for m in tar.getmembers() if m.isfile() and m.name.startswith('package/')]
        licenses = [m for m in files if re.match(r'^(licen[cs]e|copying|notice|copyright)(?:[._-].*)?$', Path(m.name).name, re.I)]
        require(any(re.match(r'^(licen[cs]e|copying)', Path(m.name).name, re.I) for m in licenses), 'Missing license: ' + str(path))
        require(not any(k in manifest.get('scripts', {}) for k in ('preinstall','install','postinstall')), 'Review lifecycle scripts: ' + str(path))
        require(not any(m.name == 'package/binding.gyp' for m in files), 'Review native build: ' + str(path))
        return data, [(m.name, tar.extractfile(m).read()) for m in licenses]


def build(source, output, archive_dirs, registry=None):
    manifest = load(source/'package.json')
    lock = load(source/'package-lock.json')
    require(manifest['name'] == 'harness-dsh' and manifest['version'] in ('0.2.2', VERSION), 'Expected Harness 0.2.2 or 0.2.3')
    require(lock['lockfileVersion'] == 3 and lock['version'] == manifest['version'], 'Unexpected lockfile')
    root = lock['packages']['']
    require(root['dependencies'] == manifest['dependencies'] and root.get('devDependencies', {}) == manifest.get('devDependencies', {}), 'Manifest/lock mismatch')
    prod = [(p, e) for p, e in lock['packages'].items() if p and not e.get('dev')]
    require(prod, 'No production packages')
    require(not any(k in manifest.get('scripts', {}) for k in ('preinstall','install','postinstall','prepublish','preprepare','prepare','postprepare')), 'Review root lifecycle scripts')
    output.mkdir(parents=True, exist_ok=True)
    require(NPM and NODE, 'Node.js and npm are required')
    with tempfile.TemporaryDirectory(prefix='dsh-offline-') as temp:
        temp = Path(temp)
        stage = temp/'harness-dsh'
        stage.mkdir()
        vendor = stage/'vendor'; vendor.mkdir()
        for folder in ('src', 'tests', 'fixtures', 'scripts'):
            if (source/folder).is_dir():
                shutil.copytree(source/folder, stage/folder)
        for path in source.iterdir():
            if path.is_file() and (path.suffix == '.md' or path.name in ('.npmrc', '.gitignore', 'overlay.example.yml', 'DEPENDENCIES.csv')):
                shutil.copy2(path, stage/path.name)
        for path in (source/'vendor').iterdir():
            if path.is_file() and path.suffix != '.tgz' and path.name != 'SHA256SUMS':
                shutil.copy2(path, vendor/path.name)
        fetched = temp/'fetched'; fetched.mkdir()
        seen, inventory, missing = {}, [], []
        for path, entry in prod:
            name, version = name_of(path), entry['version']
            expected = entry['integrity']
            require(expected.startswith('sha512-'), 'Missing SHA-512: ' + path)
            filename = archive_name(name, version)
            resolved = entry.get('resolved', '')
            if resolved.startswith('file:vendor/'):
                filename = Path(resolved).name
            if filename not in seen:
                candidates = [source/'vendor'/filename] + [d/filename for d in archive_dirs]
                candidate = next((p for p in candidates if p.is_file()), None)
                if candidate is None and registry:
                    try:
                        run([NPM, 'pack', name+'@'+version, '--ignore-scripts', '--strict-ssl=true', '--registry='+registry, '--cache='+str(temp/'fetch-cache'), '--pack-destination='+str(fetched), '--fetch-retries=0', '--fetch-timeout=30000'], source)
                        candidate = fetched/filename
                    except subprocess.CalledProcessError:
                        candidate = None
                if candidate is None or not candidate.is_file():
                    missing.append(name+'@'+version); continue
                data, licenses = check_archive(candidate, name, version, expected)
                (vendor/filename).write_bytes(data)
                for license_path, content in licenses:
                    license_dir = vendor/'licenses'/filename
                    license_dir.mkdir(parents=True, exist_ok=True)
                    # Retain complete text; avoid collisions between nested notices.
                    (license_dir/(hashlib.sha256(license_path.encode()).hexdigest()[:12]+'-'+Path(license_path).name)).write_bytes(content)
                seen[filename] = expected
            require(seen[filename] == expected, 'Conflicting archive integrity: ' + filename)
            entry['resolved'] = 'file:vendor/'+filename
            inventory.append(dict(path=path, name=name, version=version, archive=filename, integrity=expected, license=entry.get('license')))
        require(not missing, 'Missing original archives:\n'+'\n'.join(sorted(set(missing))))
        manifest['version'] = lock['version'] = root['version'] = VERSION
        # The offline artifact is for source deployment, not npm publication.
        manifest.get('scripts', {}).pop('release', None)
        manifest.get('scripts', {}).pop('release:offline', None)
        # Keep dev entries unchanged, including nested paths; npm omit=dev skips them.
        dump(stage/'package.json', manifest); dump(stage/'package-lock.json', lock)
        dump(vendor/'PRODUCTION-INVENTORY.json', inventory)
        csv_path = stage/'DEPENDENCIES.csv'
        if csv_path.is_file():
            with csv_path.open(encoding='utf-8-sig', newline='') as stream:
                reader = csv.DictReader(stream); fields = reader.fieldnames; rows = list(reader)
            local = {item['path']: item['archive'] for item in inventory}
            for row in rows:
                if row['lock path'] in local:
                    row['installation source'] = 'file:vendor/'+local[row['lock path']]
                    row['reason vendored'] = 'offline production distribution'
            with csv_path.open('w', encoding='utf-8', newline='') as stream:
                writer = csv.DictWriter(stream, fields, quoting=csv.QUOTE_ALL); writer.writeheader(); writer.writerows(rows)
        (vendor/'SHA256SUMS').write_text(''.join(hashlib.sha256((vendor/f).read_bytes()).hexdigest()+'  '+f+'\n' for f in sorted(seen)), encoding='ascii')
        (stage/'OFFLINE-INSTALL.md').write_text('# Offline production installation\n\nRun '+chr(96)+'npm ci --omit=dev --offline --no-audit --no-fund'+chr(96)+' in this directory.\nAll production archives are local and verified against the original lockfile. Development dependencies still require a registry. Do not regenerate the lockfile or publish this source bundle as an npm package. The original upstream licenses are retained in the archives and vendor/licenses.\n', encoding='utf-8')
        run([NPM, 'ci', '--omit=dev', '--offline', '--legacy-peer-deps', '--no-audit', '--no-fund', '--cache='+str(temp/'empty-cache')], stage)
        for path, entry in prod:
            installed = load(stage/path/'package.json')
            require((installed['name'], installed['version']) == (name_of(path), entry['version']), 'Installed identity mismatch: '+path)
        run([NODE, '--experimental-strip-types', '--input-type=module', '-e', "const p=await import('./src/engineering.ts'); if(typeof p.apply!=='function') throw Error('Missing plugin apply'); for(const n of ['@bpc-oss/dsh-verification','@bpc-oss/dsh-evidence','stalegreen','fast-xml-parser']) await import(n)"], stage)
        shutil.rmtree(stage/'node_modules')
        target = output/f'Harness-DSH-source-{VERSION}-offline.zip'
        temporary = output/(target.name+'.tmp')
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            for path in sorted(stage.rglob('*')):
                if path.is_file():
                    z.write(path, path.relative_to(temp).as_posix())
        temporary.replace(target)
        (output/(target.name+'.sha256')).write_text(hashlib.sha256(target.read_bytes()).hexdigest()+'  '+target.name+'\n', encoding='ascii')
        print(f'PASS: {len(prod)} lock entries, {len(seen)} archives. {target}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='Extracted Harness source directory (contains package-lock.json)')
    parser.add_argument('output', type=Path)
    parser.add_argument('--archives', type=Path, action='append', default=[])
    parser.add_argument('--registry', help='Optional approved registry for missing archives; omitted = no downloads')
    args = parser.parse_args()
    build(args.source.resolve(), args.output.resolve(), [p.resolve() for p in args.archives], args.registry)


if __name__ == '__main__':
    main()
