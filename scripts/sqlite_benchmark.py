"""Root-safe installed-package benchmark. Run with -I; no checkout imports.

gen prepares synthetic data and validates it through public APIs, sample times
only public operations, profile uses separate instrumentation, reset restores
quiescent bytes at the SAME root. No live services or execution effects.
"""
import argparse
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sqlite3
import sys
import time
from unittest.mock import patch


def sha(data):return hashlib.sha256(data).hexdigest()
def save(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def logical(path):
    with sqlite3.connect(path) as db:
        return {t:sha(json.dumps(sorted(list(db.execute('SELECT * FROM "'+t+'"')),key=repr),ensure_ascii=True).encode())
            for t, in db.execute("SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")}


def fixture(root,kind='operations',size=32,events=0,pending=1,revisions=3):
    from knowledge import operations as op,lifecycle as life
    from knowledge.store import Store
    from knowledge.util import canonical_json,digest,fingerprint
    from harness.runtime import Journal
    root=Path(root).absolute();root.mkdir(parents=True,exist_ok=False)
    (root/'Fixture.cs').write_text('public class Fixture {}\n',encoding='utf-8')
    shared=root.parent/(root.name+'-shared-absent')
    store=Store(root);store.init();life.upgrade(store,life.upgrade_preview(store)['fingerprint'])
    info=dict(version=1,root=str(root),kind=kind,size=size,events=events,pending=pending,revisions=revisions,shared=str(shared))
    if kind=='operations':
        seed=op.teach(root,'Remember fixture formatting',{'type':'user-message','id':'seed'},
            binding={'trigger':{'tool':'patch','name':'Fixture.cs'},'behavior':{'adapter':'preserve-format'}})
        os_=op.OperationalStore(root)
        template=os_.records()['records'][0]
        with os_.connection(True) as db:
            db.execute('DELETE FROM operational_events');db.execute('DELETE FROM operational_current');db.execute('DELETE FROM operational_history')
            ids=[]
            for i in range(size):
                value=deepcopy(template);value['id']=digest(['rule',i]);ids.append(value['id'])
                value['trigger']['name']='Fixture.cs' if i==0 else f'irrelevant-{i}.cs'
                for revision in range(1,revisions+1):
                    value['revision']=revision;value.pop('content_hash',None);op.append(db,value)
            def event_rows():
                for i in range(events):
                    result={'id':ids[i%size],'revision':revisions if i%5 else 1}
                    if i%2:result['application']={'at':0,'outcome':{'ok':True},'evidence':[],'technical':'preconditions-satisfied','root_cause':'not-established'}
                    else:result['binding_state']={'sequence':i+1,'at':0,'state':'verified','reason':None}
                    yield digest(['event',i]),canonical_json({'request':digest(i),'result':result})
            db.executemany('INSERT INTO operational_events VALUES (?,?)',event_rows())
        info['target']=ids[0]
        os_.records();op.lookup(root,{'tool':'patch','name':'Fixture.cs'},{},shared=shared)
    elif kind=='queue':
        def item(i):return life.batch([life.op('retire','claims',f'not-yet-applied-{i}',1)],f'fixture-{i}')
        info['duplicate']=item(0);info['new']=item(size)
        with store.connection(True) as db:
            for i in range(size):
                value=item(i);state='pending' if i*100<size*pending else 'rejected' if i%2 else 'deferred'
                db.execute('INSERT INTO queue VALUES (?,?,?,NULL)',(digest(value),canonical_json(value),state))
            # Historical empty plans have no effects, receipts, approvals or roots
            # to fabricate. PREPARED and ACKNOWLEDGED states remain distinguishable.
            for i in range(max(10,size//10)):
                plan=dict(version=1,project=store.project.identity,base=digest(i),candidates={},included=[],skipped=[],blocked=[])
                pid=fingerprint(plan);state='ACKNOWLEDGED' if i%2 else 'PREPARED'
                db.execute('INSERT INTO plans VALUES (?,?,?)',(pid,canonical_json(plan),state))
                if state=='ACKNOWLEDGED':db.execute('INSERT INTO receipts VALUES (?,?)',(pid,canonical_json(plan)))
        store.validate();store.prepare();store.recover()
    elif kind=='journal':
        journal=Journal(root)
        run=dict(version=1,id='selected',project=journal.project.identity,status='completed',agents=[],frames=[],requests=[],source={},task={'version':1},gates={},capture={},config_hash='fixture',mode='fixture',started=0,finished=1,tool_calls=0)
        journal.save(run)
        journal.action('selected','a',{'tool':'read','status':'FINISHED','at':0,'finished':1,'role':'Main','agent':'main','result':{'ok':True}})
        journal.event('selected','fixture')
        with journal.db() as db:
            db.executemany('INSERT INTO outbox VALUES (?,?,?)',((f'outbox-{i}','selected' if i<3 else f'run-{i//3}',canonical_json({'version':1,'state':'delivered','attempts':1})) for i in range(size)))
        journal.load('selected');journal.outbox('selected')
    else:raise ValueError(kind)
    paths=['.knowledge/store.sqlite3']+(['.harness/runs.sqlite3'] if kind=='journal' else [])
    info['databases']={p:logical(root/p) for p in paths}
    save(root.parent/(root.name+'.fixture.json'),info)
    # Snapshot lives outside root: source inventory must not see benchmark assets.
    snaps=root.parent/(root.name+'.snapshot');snaps.mkdir()
    for i,p in enumerate(paths):(snaps/str(i)).write_bytes((root/p).read_bytes())
    return info


def restore(root):
    root=Path(root);info=json.loads((root.parent/(root.name+'.fixture.json')).read_text())
    for i,p in enumerate(info['databases']):(root/p).write_bytes((root.parent/(root.name+'.snapshot')/str(i)).read_bytes())
    return info


def operation(root,name,info):
    from knowledge import operations as op
    from knowledge.store import Store
    from harness.runtime import Journal
    if name=='records':return lambda:op.OperationalStore(root).records()
    if name=='lookup':return lambda:op.lookup(root,{'tool':'patch','name':'Fixture.cs'},{},shared=info['shared'])
    if name=='binding-read':
        record=op.OperationalStore(root).records()['records'][0]
        def bound():
            result=op.binding_event(root,record,info['shared'],'verified');op.OperationalStore(root).records();return {'state':result['state'],'sequence':result['sequence']}
        return bound
    if name=='application-read':
        def applied():
            op.application(root,'project',info['shared'],info['target'],info['revisions'],'measured',{'ok':True},[])
            return op.OperationalStore(root).records()
        return applied
    if name=='context':return lambda:Store(root).context('Fixture')
    if name in ('duplicate','new'):return lambda:Store(root).submit(info[name])
    if name=='prepare':return lambda:Store(root).prepare()
    if name=='recover':return lambda:Store(root).recover()
    journal=Journal(root) # public construction outside timings; status constructs itself
    if name=='outbox':return lambda:journal.outbox('selected')
    if name=='absent-outbox':return lambda:journal.outbox('absent')
    if name=='journal-reads':return lambda:[journal.load('selected'),journal.action('selected','a'),journal.events('selected'),journal.cancelled('selected')]
    if name=='status':
        from harness.engine import status
        return lambda:status(root,'selected')
    if name=='journal-writes':
        def written():
            journal.event('selected','write');journal.action('selected','new',{'tool':'read'});journal.cancel('selected');return journal.cancelled('selected')
        return written
    raise ValueError(name)


def canonical_result(value):
    # context timing and status wall clock are explicit nonlogical fields only.
    if isinstance(value,dict):return {k:canonical_result(v) for k,v in value.items() if k not in ('timings','wall_seconds','at')}
    if isinstance(value,list):return [canonical_result(v) for v in value]
    return value


def sample(root,name,count,profile=False):
    import knowledge,harness
    root=Path(root).absolute();info=restore(root)
    assert Path(knowledge.__file__).is_relative_to(Path(sys.prefix)) and Path(harness.__file__).is_relative_to(Path(sys.prefix))
    mutation=name in ('binding-read','application-read','new','prepare','journal-writes')
    fn=operation(root,name,info)
    samples=[];results=[]
    if not profile:
        fn();restore(root)
        for _ in range(count):
            if mutation:restore(root)
            start=time.perf_counter();value=fn();samples.append(time.perf_counter()-start)
            results.append(sha(json.dumps(canonical_result(value),sort_keys=True).encode()))
    else:
        import knowledge.operations as op,knowledge.store as st,knowledge.util as util
        stats={'sql':0,'vm_steps_approx':0,'json':0,'record_validation':0,'candidate_validation':0,'canonical_validation':0,'quick_check':0,'path_reads':0}
        real_connect=sqlite3.connect
        def connect(*args,**kw):
            db=real_connect(*args,**kw)
            def trace(sql):
                stats['sql']+=1
                if 'quick_check' in sql:stats['quick_check']+=1
            def progress():stats['vm_steps_approx']+=1000;return 0
            db.set_trace_callback(trace);db.set_progress_handler(progress,1000);return db
        with ExitStack() as stack:
            stack.enter_context(patch.object(sqlite3,'connect',connect))
            # Patch aliases by identity once, without double-counting nested loads.
            for target,key in ((util.loads,'json'),(op.validate_record,'record_validation'),(st.candidate,'candidate_validation'),(st.validate_records,'canonical_validation'),(Path.read_text,'path_reads')):
                def wrap(*a,_target=target,_key=key,**k):stats[_key]+=1;return _target(*a,**k)
                if target==Path.read_text:stack.enter_context(patch.object(Path,'read_text',wrap));continue
                for module in list(sys.modules.values()):
                    if getattr(module,'__name__','').startswith(('knowledge.','harness.')):
                        for attr,value in list(vars(module).items()):
                            if value is target:stack.enter_context(patch.object(module,attr,wrap))
            value=fn()
        return {'operation':name,'dataset':info,'profile':stats,'logical_result':sha(json.dumps(canonical_result(value),sort_keys=True).encode())}
    return dict(operation=name,dataset=info,samples_seconds=samples,median=sorted(samples)[len(samples)//2] if len(samples)%2 else sum(sorted(samples)[len(samples)//2-1:len(samples)//2+1])/2,
        p95=sorted(samples)[math.ceil(.95*len(samples))-1],p95_method='nearest rank ceil(0.95*n), one-based',logical_results=results,
        runtime={'python':sys.version,'sqlite':sqlite3.sqlite_version,'os':platform.platform(),'knowledge':knowledge.__file__,'harness':harness.__file__},
        databases={p:{'bytes':(root/p).stat().st_size,'logical':logical(root/p)} for p in info['databases']})


def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['gen','sample','profile','reset']);p.add_argument('--root',type=Path,required=True);p.add_argument('--kind',default='operations');p.add_argument('--size',type=int,default=32);p.add_argument('--events',type=int,default=0);p.add_argument('--pending',type=int,default=1);p.add_argument('--revisions',type=int,default=3);p.add_argument('--operation',default='records');p.add_argument('--count',type=int,default=20);p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.command=='gen':value=fixture(a.root,a.kind,a.size,a.events,a.pending,a.revisions)
    elif a.command=='reset':value=restore(a.root)
    else:value=sample(a.root,a.operation,a.count,a.command=='profile')
    if a.output:save(a.output,value)
    else:print(json.dumps(value))
if __name__=='__main__':main()
