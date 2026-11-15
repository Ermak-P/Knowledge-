"""Pinned, uncurated discovery evaluation and explicitly synthetic change exercise."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from knowledge.store import Store
from knowledge import lifecycle as life,discovery as disc
from knowledge.util import digest
from p1_evidence import save

ROOT=Path(__file__).resolve().parents[1]
PIN='0c2c95d9d450d07fcd4e96e95e1cd48c20834e99'
# Expectations were read from these source anchors before discovery, not learned from its output.
EXPECTATIONS=[
 ('Which interface does BasketService declare?', 'src/ApplicationCore/Services/BasketService.cs','public class BasketService : IBasketService','IBasketService'),
 ('What registers IBasketViewModelService?', 'src/Web/Configuration/ConfigureWebServices.cs','services.AddScoped<IBasketViewModelService, BasketViewModelService>();','AddScoped<IBasketViewModelService, BasketViewModelService>'),
 ('What persistence context is registered by Infrastructure?', 'src/Infrastructure/Dependencies.cs','services.AddDbContext<CatalogContext>((provider, options) =>','AddDbContext<CatalogContext>'),
 ('What route literal does BaseApiController declare?', 'src/Web/Controllers/Api/BaseApiController.cs','[Route("api/[controller]/[action]")]','api/[controller]/[action]'),
 ('Which SQL Server package does Infrastructure declare?', 'src/Infrastructure/Infrastructure.csproj','<PackageReference Include="Microsoft.EntityFrameworkCore.SqlServer" />','Microsoft.EntityFrameworkCore.SqlServer'),
]


def approve(s):
    p=s.prepare();assert p['ok'],p['blocked'];s.apply(p['fingerprint'],p['fingerprint']);s.acknowledge(p['fingerprint']);return p


def scan_all(s,**kwargs):
    r=disc.scan(s,max_files=100,**kwargs)
    while not r['complete']:
        if any(e['status']=='blocked' for e in r['coverage'].values()):raise AssertionError('Blocked source analysis')
        r=disc.scan(s,r['id'],100)
    return r


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();out=a.output
    host=ROOT/'benchmarks/eShopOnWeb';assert host.is_dir(),'Run setup_benchmark.py'
    assert disc.git(host,'rev-parse','HEAD')==PIN
    assert disc.git(host,'diff','HEAD')==''
    # No curated benchmark dataset is imported or opened. Ordinary copy, never a Git worktree.
    scratch=Path(tempfile.mkdtemp(prefix='p1-evaluation-',dir=ROOT/'.local'));project=scratch/'eShopOnWeb'
    shutil.copytree(host,project,ignore=shutil.ignore_patterns('.knowledge','bin','obj','node_modules'))
    license_file=next(p for p in host.iterdir() if p.name.lower().startswith('license'))
    shutil.copyfile(license_file,out/'eShopOnWeb-LICENSE')
    sdk=ROOT/'.local/dotnet/dotnet';assert sdk.is_file()
    env=os.environ.copy();env.update(DOTNET_ROOT=str(sdk.parent),DOTNET_CLI_HOME=str(scratch/'dotnet-home'),NUGET_PACKAGES='/workspace/nuget' if Path('/workspace/nuget').exists() else str(ROOT/'.local/nuget'),TMPDIR=str(scratch/'tmp'),DOTNET_CLI_TELEMETRY_OPTOUT='1',MSBUILDDISABLENODEREUSE='1')
    Path(env['TMPDIR']).mkdir()
    def command(name,args):
        with (out/(name+'.log')).open('w') as log:p=subprocess.run(args,cwd=project,env=env,stdout=log,stderr=subprocess.STDOUT)
        assert p.returncode==0,(name,(out/(name+'.log')).read_text()[-4000:])
    unit='tests/UnitTests/UnitTests.csproj'
    command('benchmark-restore',[str(sdk),'restore',unit,'--disable-parallel','-m:1'])
    command('benchmark-build',[str(sdk),'build',unit,'--no-restore','-m:1','-p:UseSharedCompilation=false','-p:LibraryRestore=false'])
    def tests(label):
        results=out/'dotnet-results';results.mkdir(exist_ok=True)
        command(label,[str(sdk),'test',unit,'--no-restore','--no-build','-m:1','-p:LibraryRestore=false','--logger',f'trx;LogFileName={label}.trx','--results-directory',str(results)])
        counters=ET.parse(results/(label+'.trx')).getroot().find('.//{*}Counters').attrib
        assert all(int(counters[k])==49 for k in ('total','executed','passed')) and int(counters['failed'])==0,counters
        return counters
    before=tests('before-discovery')
    s=Store(project);s.init();life.upgrade(s,life.upgrade_preview(s)['fingerprint'])
    r=scan_all(s);print('Discovery observations:',len(r['observations']),flush=True)
    # Independently check literal source anchors, hashes and categories for a representative subset.
    inspected=[]
    for question,path,anchor,answer in EXPECTATIONS:
        raw=(project/path).read_text();assert anchor in raw,(path,anchor)
        matches=[o for o in r['observations'] if o['path']==path and answer in o['statement']]
        assert matches,(question,path,answer)
        for o in matches:
            assert raw.splitlines()[o['line']-1].strip()==o['anchor']
            assert 'sha256:'+hashlib.sha256((project/path).read_bytes()).hexdigest()==o['content_hash']
        inspected.append(dict(question=question,path=path,independent_anchor=anchor,expected=answer,verified_observations=[o['id'] for o in matches]))
    assert len({o['category'] for o in r['observations']})>=3
    assert len({o['project'] for o in r['observations'] if o['project'].startswith('src/')})>=3
    plan=approve(s);questions=[]
    for question,path,anchor,answer in EXPECTATIONS:
        result=s.context(question,max_items=100,max_bytes=200000)
        supported=any(answer in c['statement'] for c in result['claims'])
        questions.append(dict(question=question,expected=answer,independent_anchor=anchor,path=path,status='PASS' if supported else 'FAIL',result=result))
    no=s.context('zxqvnonexistenthyperdrive');assert not no['claims']
    # Unconfirmed synthetic record is explicitly distinct from discovered real-source data.
    sys.path.insert(0,str(ROOT/'tests'));from fixtures import addition
    s.submit(addition('synthetic.uncertain','Synthetic hypothetical hyperdrive.','INFERRED'));approve(s)
    assert not s.context('hyperdrive')['claims'];assert s.context('hyperdrive',include_unconfirmed=True)['claims']==[] # no current source evidence
    count=len(s.status()['queue']);repeat=scan_all(s);assert len(s.status()['queue'])==count
    save(out/'discovery.json',dict(scan=r,representative_inspection=inspected,candidates=s.export()['queue'],repeat_added_candidates=0,limitations=r['limits'],curated_input_used=False))
    save(out/'questions.json',dict(questions=questions,no_answer=no,unconfirmed='synthetic claim retained but excluded from trusted current: no verifiable checkout evidence',broad_accuracy_claim=False))
    after=tests('after-discovery')
    save(out/'benchmark.json',dict(pin=PIN,sdk=subprocess.check_output([str(sdk),'--version'],cwd=project,env=env,text=True).strip(),before=before,after=after))
    assert disc.git(project,'diff','HEAD')=='';assert disc.git(host,'diff','HEAD')==''
    save(out/'source-immutability.json',dict(pin=PIN,benchmark_tracked_diff='',original_tracked_diff='',source_manifest=r['snapshot'],copy=str(project)))
    controlled(out,scratch)
    # A lexical miss is a real failed evaluation, never rewritten as PASS.
    assert all(q['status']=='PASS' for q in questions),'Retrieval expectation failed; see questions.json'


def controlled(out,scratch):
    from fixtures import addition
    from test_p1 import fixture,git,upgraded
    root=scratch/'synthetic';root.mkdir();fixture(root);s=upgraded(root)
    before=scan_all(s);p=approve(s)
    consumer=next(o for o in before['observations'] if o['category']=='wiring')
    target=next(o for o in before['observations'] if o['category']=='declaration' and o['subject']=='ExternalManagement')
    payload=s.lookup('claims',consumer['id'])['record']
    relation=dict(id='synthetic.removal.dependency',type='depends_on',**{'from':consumer['id'],'to':target['id']},provenance={'actor':'synthetic','method':'reviewed fixture wiring'})
    s.submit(life.batch([life.op('update','claims',consumer['id'],1,dict(payload,depends_on=[target['id']])),life.op('add','relationships',relation['id'],0,relation)],'Reviewed synthetic source-wiring dependency'));dependency_preview=approve(s)
    base=git(root,'rev-parse','HEAD')
    (root/'Core/ExternalManagement.cs').unlink();(root/'Api/appsettings.json').write_text(json.dumps({'Replacement':{'Endpoint':'https://synthetic.invalid/new'}}));(root/'Api/Program.cs').write_text('services.AddSingleton<INewService, NewService>();\napp.MapGet("/replacement", () => "new");\n')
    (root/'Core/NewService.cs').write_text('public interface INewService {}\npublic class NewService : INewService {}\n')
    (root/'Tests/Independent.cs').rename(root/'Tests/Renamed.cs')
    git(root,'add','-A');git(root,'commit','-m','synthetic controlled removal replacement rename')
    after=scan_all(s,base=base,head='HEAD');rec=disc.reconcile(s,after['id']);assert rec['proposal'];s.submit(rec['proposal']);preview=approve(s)
    s.acknowledge(p['fingerprint']);s.apply(p['fingerprint'],p['fingerprint'])
    current=s.context('ExternalManagement');assert not any('ExternalManagement' in c['statement'] for c in current['claims'])
    assert s.context('NewService')['claims']
    save(out/'controlled.json',dict(synthetic=True,before=before,dependency_preview=dependency_preview,after=after,reconciliation=rec,preview=preview,current_removed=current,current_new=s.context('NewService'),export=s.export(),history=s.status()['revisions']))
    # Nonempty accepted P0 semantic upgrade with a committed pending acknowledgment and pending work.
    root=scratch/'upgrade';root.mkdir();s=Store(root);s.init();s.submit(addition());p=s.prepare();s.apply(p['fingerprint'],p['fingerprint']);s.submit(addition('synthetic.pending','Synthetic pending upgrade claim.'))
    old=s.export();u=life.upgrade(s,life.upgrade_preview(s)['fingerprint']);new=s.export();assert {k:new[k] for k in old}==old
    s.recover();assert s.lookup('claims','synthetic.rule')['record']==old['records']['claims'][0]
    save(out/'upgrade.json',dict(synthetic=True,before=old,after=new,upgrade=u,recovery=s.status(),preserved_p0_fields=True))


if __name__=='__main__':main()
