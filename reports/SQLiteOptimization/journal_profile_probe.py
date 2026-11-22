"""Owned historical runs/outbox/events; public API default/opt-in measurements.

The generic fixture's provisional outbox is not used. Every outbox owner exists,
every delivered payload has an actual queued candidate/receipt and delivery event,
and every run is checked by the product's normal Journal.load validator.
"""
import argparse,hashlib,importlib.util,json,math,statistics,subprocess,sys,time
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
COMMON_DRIVER=ROOT/'scripts/sqlite_benchmark.py'
DRIVER=Path(__file__).with_name('owned_journal_driver.py')
OPERATIONS=['outbox','absent-outbox','status','journal-reads','journal-writes','outbox-write','capture-retry']


def driver_module():
    spec=importlib.util.spec_from_file_location('qualified_sqlite_driver',COMMON_DRIVER);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def prepare(root,size):
    from knowledge.store import Store
    from knowledge import lifecycle as life
    from knowledge.util import canonical_json,digest,loads
    from harness.runtime import Journal,source_snapshot
    driver=driver_module();root.mkdir(parents=True,exist_ok=False);(root/'Fixture.cs').write_text('public class Fixture {}\n')
    store=Store(root);store.init();life.upgrade(store,life.upgrade_preview(store)['fingerprint'])
    evidence=dict(id='journal.fixture.evidence',type='direct-technical',status='active',source='Fixture.cs',provenance={'actor':'synthetic-benchmark','method':'fixture'},captured_at='2026-11-22T00:00:00Z',location='Fixture.cs#L1',description='Synthetic fixture declaration.',substantiates=[])
    payload=life.batch([life.op('add','evidence',evidence['id'],0,evidence)],'Synthetic historical capture fixture')
    receipt=store.submit(payload);candidate=receipt['candidate'];decision={'decision':'submit','payload':payload}
    journal=Journal(root);source=source_snapshot(journal.project)
    def owner(i):return 'selected' if i==0 else f'run-{i}'
    def outbox_id(run,slot):return digest([run,'capture',slot,decision])
    template=dict(version=1,id='selected',project=journal.project.identity,status='completed',agents=[{'id':'main','role':'Main'}],frames=[{'id':'main','role':'Main','history':[]}],requests=[],source=source,task={'version':1,'initial_source':{}},gates={},capture={},config_hash='fixture',mode='fixture',started=0,finished=1,tool_calls=0,capture_prepared=True,final_source=digest(source),capture_time=0)
    journal.save(template);template=journal.load('selected')
    owners=[owner(i) for i in range(math.ceil(size/3))]
    def runs():
        for number,run_id in enumerate(owners):
            value=deepcopy(template);value['id']=run_id;value['capture_event']=digest(['capture',run_id])
            value['capture']={'state':'delivered','outbox':[outbox_id(run_id,slot) for slot in range(min(3,size-number*3))]}
            yield run_id,canonical_json(value)
    def outbox():
        for i in range(size):
            run_id=owner(i//3);saved=deepcopy(receipt)
            if i:saved['result']='duplicate'
            value=dict(version=1,event=digest(['capture',run_id]),run=run_id,at=0,decision=decision,state='delivered',attempts=1,coding_actions=[],receipt=saved,delivered_at=0)
            yield outbox_id(run_id,i%3),run_id,canonical_json(value)
    def events():
        for i in range(size):
            run_id=owner(i//3);sequence=i%3+1
            yield run_id,sequence,canonical_json(dict(version=1,sequence=sequence,at=0,kind='capture-delivered',outbox=outbox_id(run_id,i%3),candidate=candidate))
    with journal.db() as db:
        db.executemany('INSERT OR REPLACE INTO runs VALUES (?,?)',runs())
        db.executemany('INSERT INTO outbox VALUES (?,?,?)',outbox())
        db.executemany('INSERT INTO events VALUES (?,?,?)',events())
    journal.action('selected','a',{'tool':'read','status':'FINISHED','at':0,'finished':1,'role':'Main','agent':'main','result':{'ok':True}})
    with journal.db() as connection:
        class Snapshot:
            project=journal.project
            @contextmanager
            def db(self):yield connection
        # Exact product validator in one stable generation-time snapshot. This
        # batching is NOT used to bypass checks in the timed public operations.
        for run_id in owners:Journal.load(Snapshot(),run_id)
        assert connection.execute('SELECT count(*) FROM outbox o LEFT JOIN runs r ON o.run=r.id WHERE r.id IS NULL').fetchone()[0]==0
        for identifier,run_id,p in connection.execute('SELECT id,run,payload FROM outbox'):
            item=loads(p);assert item['run']==run_id and item['receipt']['candidate']==candidate and item['decision']['payload']==payload
        assert connection.execute('SELECT count(*) FROM events').fetchone()[0]==size
    store.validate();journal.outbox('selected');journal.outbox('absent')
    paths=['.knowledge/store.sqlite3','.harness/runs.sqlite3']
    info=dict(version=1,root=str(root),kind='journal',size=size,runs=len(owners),events=size,pending=0,revisions=0,shared=str(root.parent/(root.name+'-shared-absent')),committed=False,all_owners_validated=True,queued_candidate=candidate)
    info['databases']={p:driver.logical(root/p) for p in paths};info['snapshot_sha256']={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths}
    driver.save(root.parent/(root.name+'.fixture.json'),info);snapshot=root.parent/(root.name+'.snapshot');snapshot.mkdir()
    for i,p in enumerate(paths):(snapshot/str(i)).write_bytes((root/p).read_bytes())
    return info


def main():
    p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path);p.add_argument('--candidate',type=Path);p.add_argument('--work-root',type=Path);p.add_argument('--output',type=Path);p.add_argument('--index-profile',choices=['none','ordinary'],default='none');p.add_argument('--prepare',type=Path);p.add_argument('--size',type=int);a=p.parse_args()
    if a.prepare:print(json.dumps(prepare(a.prepare,a.size)));return
    a.work_root.mkdir(parents=True,exist_ok=True);a.output.mkdir(parents=True,exist_ok=True);results=[]
    def run(py,args,target):
        cmd=[str(py),'-I','-B',str(DRIVER),*map(str,args),'--output',str(target)]
        start=time.time();r=subprocess.run(cmd,capture_output=True,text=True);assert r.returncode==0,(cmd,r.stdout,r.stderr)
        return json.loads(target.read_text()),dict(command=cmd,seconds=time.time()-start)
    for size in (1000,10000,30000):
        name='journal-'+('1k' if size==1000 else '10k' if size==10000 else '30k');root=a.work_root/name;out=a.output/name;out.mkdir(exist_ok=True)
        if not root.exists():
            r=subprocess.run([str(a.baseline),'-I','-B',str(Path(__file__).resolve()),'--prepare',str(root),'--size',str(size)],capture_output=True,text=True);assert r.returncode==0,r.stderr
            info=json.loads(r.stdout)
        else:info=json.loads((root.parent/(root.name+'.fixture.json')).read_text())
        (out/'fixture.json').write_text(json.dumps(info,indent=2)+'\n')
        for operation in OPERATIONS:
            n=3 if operation in ('journal-writes','outbox-write','capture-retry') else 20 if size==1000 else 5 if size==10000 else 3
            xs={'baseline':[],'candidate':[]};hashes={'baseline':[],'candidate':[]};commands=[];last={}
            for block,count in enumerate((n//2,n-n//2)):
                for label,py in [('baseline',a.baseline),('candidate',a.candidate)]:
                    variant=a.index_profile if label=='candidate' else 'none'
                    value,cmd=run(py,['sample','--root',root,'--operation',operation,'--count',count,'--index-variant',variant],out/f'{operation}-{label}-{block}.json')
                    xs[label]+=value['samples_seconds'];hashes[label]+=value['logical_results'];commands.append(cmd);last[label]=value
            assert set(hashes['baseline'])==set(hashes['candidate'])
            row=dict(dataset=name,operation=operation,count_each=n,equivalent_results=True,commands=commands)
            for label,values in xs.items():row[label]=dict(median=statistics.median(values),p95=sorted(values)[math.ceil(.95*n)-1],samples_seconds=values,runtime=last[label]['runtime'],databases=last[label]['databases'])
            row['speedup']=row['baseline']['median']/row['candidate']['median'];results.append(row)
            (a.output/'results.json').write_text(json.dumps(dict(driver_sha256=hashlib.sha256(DRIVER.read_bytes()).hexdigest(),common_driver_sha256=hashlib.sha256(COMMON_DRIVER.read_bytes()).hexdigest(),fixture_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),index_profile=a.index_profile,results=results),indent=2)+'\n')
            print(name,operation,round(row['speedup'],2),'x',flush=True)
        for label,py in [('baseline',a.baseline),('candidate',a.candidate)]:run(py,['profile','--root',root,'--operation','outbox','--index-variant',a.index_profile if label=='candidate' else 'none'],out/f'profile-{label}.json')
if __name__=='__main__':main()
