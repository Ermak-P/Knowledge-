"""Single P0 verification entry point. Required failures produce nonzero exit.

Run with the environment interpreter after scripts/setup.sh. A missing benchmark
or SDK is a required failure, not an implicit skip. Native Windows and real
provider/UI checks are separately documented NOT RUN subchecks.
"""
from evidence import Attempt
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


ATTEMPT=None

def run(name,args,cwd=ROOT,env=None):
    artifacts={
        'migration-evidence':['migration-results.json'],
        'benchmark-pipeline':['BENCHMARK-RESULTS.json','benchmark-candidates.json','benchmark-provenance.json','benchmark-store-export.json','benchmark-application.diff'],
        'benchmark-without-knowledge':['dotnet-results/without-knowledge.trx'],
        'benchmark-after-knowledge':['dotnet-results/after-knowledge.trx'],
    }.get(name,[])
    result=ATTEMPT.command(name,args,cwd,env,[OUT/p for p in artifacts])
    print(name+': PASS',flush=True)
    return result


def workflow():
    OUT.mkdir(parents=True,exist_ok=True)
    run('packaging',[sys.executable,'-B','scripts/check_packaging.py'])
    run('product-tests',[sys.executable,'-B','-m','unittest','discover','-s','tests','-v'])
    import re
    log=(OUT/'product-tests.log').read_text(encoding='utf-8')
    match=re.search(r'Ran (\d+) tests',log)
    assert match and int(match[1])>0 and log.rstrip().endswith('OK') and 'skipped=' not in log
    ATTEMPT.value['checks']['product-tests']['test_count']=int(match[1]);ATTEMPT.persist()
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
    run('benchmark-restore',[binary,'restore',project,'--disable-parallel','-m:1'],host,env)
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
    # Preserve prior integration, then exercise a genuinely new import this run.
    # Never silently replace an unknown user's dataset.
    if store.exists():
        from knowledge.store import Store
        previous=Store(host).export()
        assert len(previous['records']['claims'])==15 and all(c['id'].startswith('eshop.') for c in previous['records']['claims']), 'Unknown benchmark store: preserve and inspect'
        store.rename(ROOT/'.local'/('prior-benchmark-'+ATTEMPT.id))
    run('benchmark-pipeline',[sys.executable,'-B','scripts/benchmark.py'])
    after=test(binary,project,'after-knowledge',host,env)
    diff=subprocess.check_output(['git','-C',str(host),'diff','--binary','HEAD'],text=True)
    assert diff=='','Benchmark tracked source changed'
    (OUT/'benchmark-application.diff').write_text(diff)
    ATTEMPT.finish('PASS',sdk=version,benchmark_tests={'without-knowledge':without,'after-knowledge':after},
        native_windows='NOT_RUN',live_model_opencode='NOT_RUN',browser_sqlserver_aspire='NOT_RUN')



def test(binary,project,label,host,env):
    results=OUT/'dotnet-results';results.mkdir(exist_ok=True)
    path=results/(label+'.trx')
    if path.exists():path.unlink() # current-run results only
    run('benchmark-'+label,[binary,'test',project,'--no-build','--no-restore','-m:1','-p:LibraryRestore=false',
        '--logger',f'trx;LogFileName={label}.trx','--results-directory',str(results)],host,env)
    counters=ET.parse(path).getroot().find('.//{*}Counters')
    assert counters is not None and int(counters.attrib['executed'])>0 and int(counters.attrib['failed'])==0,counters
    assert all(int(counters.attrib[k])==49 for k in ('passed','executed','total')) and int(counters.attrib.get('notExecuted',0))==0,counters.attrib
    return dict(counters.attrib)


def main():
    global ATTEMPT
    ATTEMPT=Attempt(ROOT)
    try:
        workflow()
    except BaseException as e:
        ATTEMPT.finish('INTERRUPTED' if isinstance(e,KeyboardInterrupt) else 'FAILED',error=str(e))
        raise


if __name__=='__main__':main()
