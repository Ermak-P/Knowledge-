"""Interleaved, installed baseline/candidate public-operation measurements."""
import argparse,hashlib,json,math,statistics,subprocess,time
from pathlib import Path

HERE=Path(__file__).resolve().parent
DATASETS=[
    ('op-32-0','operations',32,0,1,3,False),
    ('op-32-1k','operations',32,1000,1,3,False),
    ('op-32-10k','operations',32,10000,1,3,False),
    ('op-256-10k','operations',256,10000,1,3,False),
    ('op-256-100k','operations',256,100000,1,3,False),
    ('op-long-history','operations',32,1000,1,128,False),
    ('queue-1k-1','queue',1000,0,1,3,False),
    ('queue-10k-1','queue',10000,0,1,3,False),
    ('queue-10k-10','queue',10000,0,10,3,False),
    ('queue-10k-100','queue',10000,0,100,3,False),
    ('queue-100k-1','queue',100000,0,1,3,False),
    ('queue-10k-committed','queue',10000,0,1,3,True),
    ('legacy','legacy',2,0,1,3,False),
    ('journal-1k','journal',1000,0,1,3,False),
    ('journal-10k','journal',10000,0,1,3,False),
    ('journal-100k','journal',100000,0,1,3,False)]
OPERATIONS={'operations':['records','lookup','context','filesystem','binding-read','application-read'],
    'queue':['prepare','recover','duplicate','new'],'legacy':['duplicate','new'],
    'journal':['outbox','absent-outbox','status','journal-reads','journal-writes','outbox-write','capture-retry']}
WRITES={'prepare','binding-read','application-read','new','journal-writes','outbox-write','capture-retry'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--baseline-python',type=Path,required=True);p.add_argument('--candidate-python',type=Path,required=True);p.add_argument('--work-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--only',nargs='*');a=p.parse_args()
    a.work_root.mkdir(parents=True,exist_ok=True);a.output.mkdir(parents=True,exist_ok=True)
    driver=HERE/'sqlite_benchmark.py';rows=[]
    def command(py,args,target):
        cmd=[str(py),'-I','-B',str(driver),*map(str,args),'--output',str(target)]
        started=time.time();result=subprocess.run(cmd,capture_output=True,text=True)
        if result.returncode:
            (a.output/'FAILED.json').write_text(json.dumps({'command':cmd,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr},indent=2)+'\n')
            raise RuntimeError(result.stderr+result.stdout)
        return json.loads(target.read_text()),dict(command=cmd,seconds=time.time()-started)
    for name,kind,size,events,pending,revisions,committed in DATASETS:
        if a.only and name not in a.only:continue
        root=a.work_root/name;out=a.output/name;out.mkdir(exist_ok=True)
        if not root.exists():command(a.baseline_python,['gen','--root',root,'--kind',kind,'--size',size,'--events',events,'--pending',pending,'--revisions',revisions,*(['--committed'] if committed else [])],out/'fixture.json')
        for operation in OPERATIONS[kind]:
            small=(kind=='operations' and size==32 and events<=1000 and revisions==3) or (kind in ('queue','journal') and size==1000) or kind=='legacy'
            count=3 if operation in WRITES or (operation=='recover' and committed) else 20 if small else 3 if size==100000 or events==100000 else 5
            parts=[count//2,count-count//2];values={'baseline':[],'candidate':[]};result_ids={'baseline':[],'candidate':[]};commands=[];last={}
            for block,n in enumerate(parts):
                for label,py in [('baseline',a.baseline_python),('candidate',a.candidate_python)]:
                    variant='ordinary' if label=='candidate' and kind=='journal' else 'none'
                    result,cmd=command(py,['sample','--root',root,'--operation',operation,'--count',n,'--index-variant',variant],out/f'{operation}-{label}-{block}.json')
                    values[label]+=result['samples_seconds'];result_ids[label]+=result['logical_results'];commands.append(cmd);last[label]=result
            equivalent=set(result_ids['baseline'])==set(result_ids['candidate'])
            row={'dataset':name,'operation':operation,'count_each':count,'equivalent_results':equivalent,'commands':commands}
            for label in values:
                xs=values[label];row[label]={'median':statistics.median(xs),'p95':sorted(xs)[math.ceil(.95*len(xs))-1],'samples_seconds':xs,'runtime':last[label]['runtime'],'databases':last[label]['databases']}
            row['speedup']=row['baseline']['median']/row['candidate']['median'];rows.append(row)
            save=dict(driver_sha256=hashlib.sha256(driver.read_bytes()).hexdigest(),p95='nearest rank ceil(.95*n)',interleave='baseline/candidate first half, baseline/candidate second half; warm-up each fresh subprocess',results=rows)
            (a.output/'results.json').write_text(json.dumps(save,indent=2)+'\n')
            print(name,operation,'n='+str(count),f"{row['baseline']['median']:.6f} -> {row['candidate']['median']:.6f}",f"{row['speedup']:.2f}x",'equivalent='+str(equivalent),flush=True)
            if not equivalent:raise RuntimeError('logical result mismatch: '+name+'/'+operation)
        profiled={'operations':'records','queue':'prepare','legacy':'duplicate','journal':'outbox'}[kind]
        for label,py in [('baseline',a.baseline_python),('candidate',a.candidate_python)]:
            command(py,['profile','--root',root,'--operation',profiled,'--index-variant','ordinary' if label=='candidate' and kind=='journal' else 'none'],out/f'profile-{label}.json')
if __name__=='__main__':main()
