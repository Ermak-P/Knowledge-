"""Single P0 verification entry point. Required failures produce nonzero exit.

Run with the environment interpreter after scripts/setup.sh. A missing benchmark
or SDK is a required failure, not an implicit skip. Native Windows and real
provider/UI checks are separately documented NOT RUN subchecks.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/P0'


def run(name,args,cwd=ROOT,env=None):
    path=OUT/(name+'.log')
    with path.open('w') as f:
        p=subprocess.run(args,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT)
    print(f'{name}: {"PASS" if p.returncode==0 else "FAIL"} ({path.relative_to(ROOT)})',flush=True)
    if p.returncode:
        print(path.read_text()[-5000:]);raise SystemExit(p.returncode)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    run('packaging',[sys.executable,'-B','scripts/check_packaging.py'])
    run('product-tests',[sys.executable,'-B','-m','unittest','discover','-s','tests','-v'])
    run('migration-evidence',[sys.executable,'-B','scripts/migration_evidence.py'])
    host=ROOT/'benchmarks/eShopOnWeb'
    assert host.is_dir(),'Run scripts/setup_benchmark.py'
    candidates=[ROOT/'.local/dotnet/dotnet',Path('/workspace/dotnet/dotnet')]
    binary=next((str(p) for p in candidates if p.exists()),shutil.which('dotnet'))
    assert binary,'Install .NET 10 SDK using scripts/setup_benchmark.py'
    env=os.environ.copy()
    env.update(DOTNET_ROOT=str(Path(binary).parent),DOTNET_CLI_HOME=str(ROOT/'.local/dotnet-home'),
               NUGET_PACKAGES=str(ROOT/'.local/nuget'),TMPDIR=str(ROOT/'.local/tmp'),DOTNET_CLI_TELEMETRY_OPTOUT='1',MSBUILDDISABLENODEREUSE='1')
    Path(env['TMPDIR']).mkdir(parents=True,exist_ok=True)
    # Existing cached dependencies are reusable, but never copy them into the packet.
    if Path('/workspace/nuget').exists():env['NUGET_PACKAGES']='/workspace/nuget'
    version=subprocess.check_output([binary,'--version'],cwd=host,env=env,text=True).strip()
    assert version.startswith('10.'),version
    project='tests/UnitTests/UnitTests.csproj'
    run('benchmark-restore',[binary,'restore',project,'--disable-parallel'],host,env)
    run('benchmark-build',[binary,'build',project,'--no-restore','-m:1','-p:UseSharedCompilation=false','-p:LibraryRestore=false'],host,env)
    # Baseline is measured with integration absent. Move only our verified data,
    # restore it in finally; no application source or test is changed.
    store=host/'.knowledge'; parked=ROOT/'.local/verification-knowledge'
    assert not parked.exists(),'Previous parked integration requires inspection'
    if store.exists():store.rename(parked)
    try:
        without=test(binary,project,'without-knowledge',host,env)
    finally:
        if parked.exists():parked.rename(store)
    run('benchmark-pipeline',[sys.executable,'-B','scripts/benchmark.py'])
    after=test(binary,project,'after-knowledge',host,env)
    diff=subprocess.check_output(['git','-C',str(host),'diff','--binary','HEAD'],text=True)
    assert diff=='','Benchmark tracked source changed'
    (OUT/'benchmark-application.diff').write_text(diff)
    (OUT/'verification-summary.json').write_text(json.dumps({'status':'PASS','sdk':version,'product_command':'python -B -m unittest discover -s tests -v',
        'benchmark_tests':{'without-knowledge':without,'after-knowledge':after},
        'native_windows':'NOT_RUN','live_model_opencode':'NOT_RUN','browser_sqlserver_aspire':'NOT_RUN'},indent=2)+'\n')


def test(binary,project,label,host,env):
    results=OUT/'dotnet-results';results.mkdir(exist_ok=True)
    path=results/(label+'.trx')
    if path.exists():path.unlink() # current-run results only
    run('benchmark-'+label,[binary,'test',project,'--no-build','--no-restore','-m:1','-p:LibraryRestore=false',
        '--logger',f'trx;LogFileName={label}.trx','--results-directory',str(results)],host,env)
    counters=ET.parse(path).getroot().find('.//{*}Counters')
    assert counters is not None and int(counters.attrib['executed'])>0 and int(counters.attrib['failed'])==0,counters
    assert int(counters.attrib['passed'])==49,counters.attrib
    return dict(counters.attrib)


if __name__=='__main__':main()
