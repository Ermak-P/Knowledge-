"""Pinned ordinary checkout + checksum-verified workspace-local Linux x64 SDK."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from benchmark_dataset import PIN


def main():
    repo=Path(__file__).resolve().parents[1]
    host=repo/'benchmarks/eShopOnWeb'
    if not host.exists():
        subprocess.run(['git','clone','--no-checkout','https://github.com/NimblePros/eShopOnWeb.git',str(host)],check=True)
        subprocess.run(['git','-C',str(host),'checkout','--detach',PIN],check=True)
    actual=subprocess.check_output(['git','-C',str(host),'rev-parse','HEAD'],text=True).strip()
    assert actual==PIN,'Preserve existing checkout: unexpected revision'
    assert subprocess.check_output(['git','-C',str(host),'diff','HEAD','--'],text=True)=='','Preserve benchmark changes'
    if platform.system()!='Linux' or platform.machine() not in ('x86_64','AMD64'):
        print('Checkout ready. Install .NET SDK 10.0.404 for your native platform from Microsoft, then run scripts/verify.py. Linux SDK installation not applicable.')
        return
    parser=argparse.ArgumentParser()
    parser.add_argument('--sdk-dir',type=Path,default=repo/'.local/dotnet')
    args=parser.parse_args()
    sdk=args.sdk_dir.resolve()
    sdk.mkdir(parents=True,exist_ok=True)
    spec=json.loads((repo/'scripts/dotnet-sdk.json').read_text())
    binary=sdk/'dotnet'
    if binary.exists():
        version=subprocess.check_output([str(binary),'--version'],text=True,cwd=host).strip()
        assert version==spec['version'],'Existing SDK differs; preserve and inspect'
    else:
        with tempfile.TemporaryDirectory() as tmp:
            archive=Path(tmp)/'sdk.tar.gz'
            urllib.request.urlretrieve(spec['url'],archive)
            assert hashlib.sha512(archive.read_bytes()).hexdigest()==spec['hash'].lower(),'SDK checksum mismatch'
            with tarfile.open(archive) as t:t.extractall(sdk,filter='data')
    print(f'Pinned host {PIN}; verified SDK {spec["version"]}: {binary}')


if __name__=='__main__':main()
