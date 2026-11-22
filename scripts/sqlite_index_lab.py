"""Final index experiment: valid rows and explicit connection lifetime.

Fixture companion manifest/snapshot is required. SQL-only timings and plans are
diagnostics; public API timings are retained separately by sqlite_benchmark.py.
"""
import argparse,json,sqlite3,statistics,tempfile,time
from contextlib import closing
from copy import deepcopy
from pathlib import Path
from knowledge.store import Store,candidate
from knowledge.util import canonical_json,digest,fingerprint,loads


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    info=json.loads((a.root.parent/(a.root.name+'.fixture.json')).read_text())
    cases=[('queue',"SELECT id,payload FROM queue WHERE status='pending' ORDER BY id",(),
        'CREATE INDEX ix_lab ON queue(status,id)',"CREATE INDEX ix_lab ON queue(id) WHERE status='pending'"),
        ('plans',"SELECT id FROM plans WHERE status='COMMITTED' ORDER BY id",(),
        'CREATE INDEX ix_lab ON plans(status,id)',"CREATE INDEX ix_lab ON plans(id) WHERE status='COMMITTED'")]
    if info['kind']=='journal':cases=[('outbox','SELECT id,payload FROM outbox WHERE run=?',('selected',),'CREATE INDEX ix_lab ON outbox(run)',"CREATE INDEX ix_lab ON outbox(run) WHERE run='selected'")]
    output=[]
    for table,sql,args,ordinary,partial in cases:
        relative='.harness/runs.sqlite3' if table=='outbox' else '.knowledge/store.sqlite3'
        number=list(info['databases']).index(relative)
        original=(a.root.parent/(a.root.name+'.snapshot')/str(number)).read_bytes()
        assert __import__('hashlib').sha256(original).hexdigest()==info['snapshot_sha256'][relative]
        for label,ddl in [('none',None),('ordinary',ordinary),('partial',partial)]:
            with tempfile.TemporaryDirectory(prefix='sqlite-index-lab-') as tmp:
                path=Path(tmp)/'experiment.sqlite3';path.write_bytes(original)
                with closing(sqlite3.connect(path)) as db, db:
                    db.execute('PRAGMA synchronous=FULL')
                    if ddl:db.execute(ddl);db.commit()
                    plan=list(db.execute('EXPLAIN QUERY PLAN '+sql,args));size=path.stat().st_size
                    samples=[]
                    for _ in range(21):
                        start=time.perf_counter();rows=list(db.execute(sql,args));samples.append(time.perf_counter()-start)
                    if table=='plans':
                        identifier=db.execute("SELECT id FROM plans WHERE status='ACKNOWLEDGED' LIMIT 1").fetchone()[0]
                    else:identifier=db.execute('SELECT id FROM '+table+' LIMIT 1').fetchone()[0]
                    updates=[]
                    for i in range(20):
                        start=time.perf_counter();db.execute('BEGIN IMMEDIATE')
                        if table=='outbox':db.execute('UPDATE outbox SET run=? WHERE id=?',('selected' if i%2 else 'other',identifier))
                        else:db.execute('UPDATE '+table+' SET status=? WHERE id=?',('pending' if i%2 else 'deferred',identifier)) if table=='queue' else db.execute('UPDATE plans SET status=? WHERE id=?',('COMMITTED' if i%2 else 'ACKNOWLEDGED',identifier))
                        db.commit();updates.append(time.perf_counter()-start)
                    inserts=[]
                    if table=='plans':
                        used={cid for payload, in db.execute('SELECT payload FROM plans') for cid in loads(payload)['candidates']}
                        choices=iter((cid,payload) for cid,payload in db.execute('SELECT id,payload FROM queue') if cid not in used)
                        chosen=[next(choices) for _ in range(20)]
                    for i in range(20):
                        # Prepare valid payloads before the physical INSERT timer.
                        if table=='queue':
                            item=loads(db.execute('SELECT payload FROM queue LIMIT 1').fetchone()[0]);item=deepcopy(item)
                            item['reason']='Valid index lab insert '+str(i)
                            item['operations'][0]['id']='lab.evidence.'+str(i)
                            item['operations'][0]['payload']['id']='lab.evidence.'+str(i)
                            item=candidate(item);parameters=(digest(item),canonical_json(item),'pending')
                        elif table=='plans':
                            cid,payload=chosen[i]
                            prepared_plan=loads(db.execute('SELECT payload FROM plans WHERE id=?',(identifier,)).fetchone()[0]);prepared_plan.update(candidates={cid:loads(payload)},included=[cid])
                            parameters=(fingerprint(prepared_plan),canonical_json(prepared_plan),'PREPARED')
                        else:parameters=('insert-'+str(i),'other',canonical_json({'version':1,'state':'delivered','attempts':1}))
                        start=time.perf_counter();db.execute('BEGIN IMMEDIATE')
                        if table=='outbox':db.execute('INSERT INTO outbox VALUES (?,?,?)',parameters)
                        elif table=='queue':db.execute('INSERT INTO queue VALUES (?,?,?,NULL)',parameters)
                        else:db.execute('INSERT INTO plans VALUES (?,?,?)',parameters)
                        db.commit();inserts.append(time.perf_counter()-start)
                    if table!='outbox':
                        store=Store(a.root);store._check_control(db);store._records(db)
                    else:
                        assert db.execute('PRAGMA quick_check').fetchone()==('ok',)
                        assert all(loads(p)['state'] in ('pending','delivered') for p, in db.execute('SELECT payload FROM outbox'))
                    output.append(dict(table=table,index=label,ddl=ddl,sql=sql,parameters=args,rows=len(rows),plan=plan,bytes=size,select_seconds=samples[1:],select_median=statistics.median(samples[1:]),update_seconds=updates,insert_seconds=inserts,valid_after_dml=True,indexes=list(db.execute('PRAGMA index_list('+table+')')),index_xinfo=list(db.execute('PRAGMA index_xinfo(ix_lab)')) if ddl else []))
    a.output.write_text(json.dumps(dict(sqlite=sqlite3.sqlite_version,dataset=info,experiments=output),indent=2)+'\n')
if __name__=='__main__':main()
