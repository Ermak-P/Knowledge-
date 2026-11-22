"""Fresh CLI processes, full context including current source/freshness checks."""
import argparse,hashlib,json,math,statistics,subprocess,time
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--root',type=Path,required=True);p.add_argument('--count',type=int,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    times={'baseline':[],'candidate':[]};hashes={'baseline':[],'candidate':[]};commands={}
    for label,py in [('baseline',a.baseline),('candidate',a.candidate)]:
        cmd=[str(py),'-I','-B','-m','knowledge.cli','context','--root',str(a.root),'--task','Fixture'];commands[label]=cmd
        warm=subprocess.run(cmd,capture_output=True,text=True,cwd=a.root.parent);assert warm.returncode==0,warm.stderr
    for _ in range(a.count):
        for label in ('baseline','candidate'):
            start=time.perf_counter();r=subprocess.run(commands[label],capture_output=True,text=True,cwd=a.root.parent);elapsed=time.perf_counter()-start
            assert r.returncode==0,(r.stdout,r.stderr);value=json.loads(r.stdout)
            times[label].append(elapsed);hashes[label].append(hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest())
    assert set(hashes['baseline'])==set(hashes['candidate'])
    result=dict(root=str(a.root),count=a.count,fresh_process=True,cold_disk=False,commands=commands,equivalent_results=True,logical_hashes=hashes,
        results={k:dict(samples_seconds=v,median=statistics.median(v),p95=sorted(v)[math.ceil(.95*len(v))-1]) for k,v in times.items()},p95='nearest rank ceil(.95*n)')
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v['median'] for k,v in result['results'].items()}))
if __name__=='__main__':main()
