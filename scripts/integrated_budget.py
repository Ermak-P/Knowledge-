"""Count real extraction over public knowledge-init on the pinned application."""
import contextlib,hashlib,io,json,subprocess,sys,tempfile
from pathlib import Path
from knowledge import cli,discovery
from knowledge.util import digest
ROOT=Path(__file__).resolve().parents[1]
PIN='0c2c95d9d450d07fcd4e96e95e1cd48c20834e99'
def main():
 out=Path(sys.argv[1]).absolute();out.mkdir(parents=True,exist_ok=True);host=ROOT/'benchmarks/eShopOnWeb';assert subprocess.check_output(['git','-C',str(host),'rev-parse','HEAD'],text=True).strip()==PIN
 with tempfile.TemporaryDirectory(prefix='integrated-budget-') as tmp:
  base=Path(tmp);chunked=base/'chunked';full=base/'full'
  for root in (chunked,full):subprocess.run(['git','clone','--quiet','--no-hardlinks','--local',str(host),str(root)],check=True)
  real=discovery.extract;observed=[]
  def counted(*args,**kwargs):observed.append(args[1]);return real(*args,**kwargs)
  discovery.extract=counted
  rows=[]
  def command(label,root,budget,scan=None):
   argv=['knowledge-init','--root',str(root),'--max-files',str(budget)]
   if scan:argv+=['--scan-id',scan]
   observed.clear();wire=io.StringIO();sys.argv=['knowledge',*argv]
   with contextlib.redirect_stdout(wire):code=cli.main()
   (out/(label+'.log')).write_text(wire.getvalue(),encoding='utf-8');result=json.loads(wire.getvalue());assert code==0 and result['ok'];assert len(observed)<=budget,(label,len(observed),budget);assert result['work']['extracted_this_call']==len(observed)
   rows.append(dict(label=label,argv=argv,budget=budget,actual_extract_calls=len(observed),paths=list(observed),complete=result['complete'],scan=result['id']));return result
  first=command('first',chunked,1);assert not first['complete'];second=command('partial',chunked,1,first['id']);assert not second['complete'];done=command('completion',chunked,10000,first['id']);assert done['complete'];again=command('completed-retry',chunked,1,first['id']);assert not observed
  uninterrupted=command('uninterrupted',full,10000);assert uninterrupted['complete'];assert done['observations']==uninterrupted['observations'] and done.get('ambiguous',[])==uninterrupted.get('ambiguous',[])
  value=dict(status='PASS',pin=PIN,product=__import__('knowledge').__version__,scope='entire public knowledge-init including reconciliation; real extractor forwarded unchanged',rows=rows,observation_count=len(done['observations']),observation_digest=digest(done['observations']),matches_uninterrupted=True,enumeration_and_hashing='whole-repository inventory and content/freshness hashing are outside extraction budget and remain proportional to source size')
 (out/'result.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');print(json.dumps(value))
if __name__=='__main__':main()
