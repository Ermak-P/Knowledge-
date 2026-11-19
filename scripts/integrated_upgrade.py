"""Install the sealed rc3 kit, interrupt real work, upgrade, recover via public CLI."""
import hashlib,json,os,subprocess,sys,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from p2_fixtures import project,configuration,http_provider,FixtureProvider,task
from harness.runtime import configure,Journal,source_snapshot
from knowledge.store import Store
from knowledge.util import digest
OLD=ROOT/'reports/P4/runs/d68c9865460a4fcbab2bdbaaa466f072/distribution/knowledge-harness-0.4.0rc3.zip'
EXPECTED='2dfa6ebb450acfe7549197681c9091544e5e9e7f54214832c56c7eb3611f69ef'
def main():
 kit=Path(sys.argv[1]).absolute();out=Path(sys.argv[2]).absolute();out.mkdir(parents=True,exist_ok=True);assert hashlib.sha256(OLD.read_bytes()).hexdigest()==EXPECTED;rows=[]
 for phase in ('before-first-patch','capture-after-submit'):
  with tempfile.TemporaryDirectory(prefix='integrated-upgrade-') as tmp,http_provider(d:=FixtureProvider()) as endpoint:
   base=Path(tmp);old=base/'rc3';old.mkdir()
   with zipfile.ZipFile(OLD) as z:z.extractall(old)
   env=base/'runtime';py=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python');commands=[]
   def command(label,argv,expected=0):
    proc=subprocess.run([str(x) for x in argv],cwd=base,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=240);name=phase+'-'+label+'.log';(out/name).write_bytes(proc.stdout);commands.append(dict(label=label,argv=[str(x) for x in argv],returncode=proc.returncode,log=name));assert proc.returncode==expected,(label,proc.stdout[-2000:]);return proc.stdout
   command('install-rc3',[sys.executable,old/'install.py','install','--env',env]);root=project(base/'project');c=configuration(endpoint);cfile=base/'runner.json';cfile.write_text(json.dumps(c),encoding='utf-8');tfile=base/'task.json';tfile.write_text(json.dumps(task()),encoding='utf-8')
   command('configure-rc3',[py,'-I','-m','harness.run_cli','configure','--root',root,'--input',cfile,'--init-knowledge'])
   command('interrupted-rc3',[py,'-I','-X','utf8','-B',ROOT/'tests/integrated_cli_worker.py','--die',phase,'--','run','--root',root,'--input',tfile],73)
   j=Journal(root);r=j.runs()[0];rid=r['id'];before=dict(source=source_snapshot(j.project),requests=r['requests'],actions=j.actions(rid),http=len(d.requests),outbox=j.outbox(rid),records=Store(root).export()['records'])
   command('install-correction',[sys.executable,kit/'install.py','install','--env',env]);command('doctor',[sys.executable,kit/'install.py','doctor','--env',env])
   outcome=json.loads(command('delivery-retry',[py,'-I','-m','harness.run_cli','capture-retry','--root',root,'--run-id',rid],1 if phase=='before-first-patch' else 0))
   selfsame=source_snapshot(j.project)==before['source'] and j.load(rid)['requests']==before['requests'] and j.actions(rid)==before['actions'] and len(d.requests)==before['http'];assert selfsame
   if phase=='before-first-patch':
    assert outcome['error']=='capture-retry-ineligible';outcome=json.loads(command('execution-resume',[py,'-I','-m','harness.run_cli','resume','--root',root,'--run-id',rid]));assert outcome['ok'] and len(d.requests)>before['http']
   else:
    assert outcome['ok'] and outcome['capture']['state']=='delivered';assert set(before['outbox'])==set(j.outbox(rid))
    for key,item in before['outbox'].items():
     actual=j.outbox(rid)[key]
     for name in ('event','at','decision','run','coding_actions'):assert actual[name]==item[name]
     assert actual['receipt']['candidate']==digest(item['decision']['payload'])
   assert Store(root).export()['records']==before['records'];assert len(Store(root).status()['queue'])==1
   rows.append(dict(phase=phase,status='PASS',prior='0.4.0rc3',current=__import__('harness').__version__,delivery_retry_http_delta=0,delivery_retry_edits_or_processes=0,candidate_count=1,source_bytes_preserved_on_retry=True,commands=commands))
 (out/'result.json').write_text(json.dumps(dict(status='PASS',prior_zip_sha256=EXPECTED,rows=rows),indent=2)+'\n',encoding='utf-8');print(json.dumps(rows))
if __name__=='__main__':main()
