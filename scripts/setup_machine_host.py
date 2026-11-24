"""Private acceptance host only; the product installer never invokes this.

Official OpenCode 2.4.0 native packages, pinned to published npm SHA-512.
No npm lifecycle scripts or installer pipelines are executed.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import tarfile
import tempfile
import urllib.request

PINS = {
    'linux': ('cli-linux-x64', 'mH7h8HAuSMH+ggFY1ogihbQy1xLMX1L7fE96iqRTV9c0H6apPoTbPgEJKV0qbJGy60p3jBsMvmeMVw67SoZCrw=='),
    'windows': ('cli-windows-x64', '2F+5YdpK/+BzBaAg/33dUL1lf6n7fZxmf/YaEbTuawZO5AwnB62IGnNA86pGQuFIWjZAb9YhzOdNl5yl7LOyjw=='),
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--evidence', type=Path, required=True)
    a = p.parse_args()
    platform = 'windows' if os.name == 'nt' else 'linux'
    name, expected = PINS[platform]
    url = f'https://registry.npmjs.org/@opencode/{name}/-/{name}-2.4.0.tgz'
    a.output.mkdir(parents=True, exist_ok=True)
    binary = a.output / ('opencode.exe' if os.name == 'nt' else 'opencode')
    with tempfile.TemporaryDirectory(prefix='knowledge-host-download-') as tmp:
        archive = Path(tmp) / 'host.tgz'
        digest = hashlib.sha512(); sha = hashlib.sha256()
        with urllib.request.urlopen(url, timeout=60) as response, archive.open('wb') as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk); digest.update(chunk); sha.update(chunk)
        if base64.b64encode(digest.digest()).decode() != expected: raise RuntimeError('OpenCode package integrity mismatch')
        with tarfile.open(archive) as package:
            member = package.getmember('package/bin/' + binary.name)
            if not member.isfile(): raise RuntimeError('Expected regular native host binary')
            with package.extractfile(member) as source, binary.open('wb') as destination:
                import shutil
                shutil.copyfileobj(source, destination)
        binary.chmod(0o755)
    a.evidence.mkdir(parents=True, exist_ok=True)
    proof = {'version': '2.4.0', 'platform': platform, 'url': url, 'integrity': 'sha512-' + expected,
             'package_sha256': sha.hexdigest(), 'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
             'scope': 'private acceptance host; not installed by the product installer'}
    (a.evidence / 'provenance.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(proof))


if __name__ == '__main__': main()
