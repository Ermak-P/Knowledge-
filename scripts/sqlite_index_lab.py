"""Index experiment on synthetic fixture copies; never accepts a live root.

Fixture companion manifest/snapshot is required. SQL-only timings and plans are
diagnostics; public API timings are retained separately by sqlite_benchmark.py.
"""
import argparse,json,sqlite3,statistics,tempfile,time
from pathlib import Path


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
        original=(a.root/('.harness/runs.sqlite3' if table=='outbox' else '.knowledge/store.sqlite3')).read_bytes()
        for label,ddl in [('none',None),('ordinary',ordinary),('partial',partial)]:
            with tempfile.TemporaryDirectory(prefix='sqlite-index-lab-') as tmp:
                path=Path(tmp)/'experiment.sqlite3';path.write_bytes(original)
                with sqlite3.connect(path) as db:
                    db.execute('PRAGMA synchronous=FULL')
                    if ddl:db.execute(ddl);db.commit()
                    plan=list(db.execute('EXPLAIN QUERY PLAN '+sql,args));size=path.stat().st_size
                    samples=[]
                    for _ in range(21):
                        start=time.perf_counter();rows=list(db.execute(sql,args));samples.append(time.perf_counter()-start)
                    identifier=db.execute('SELECT id FROM '+table+' LIMIT 1').fetchone()[0]
                    updates=[]
                    for i in range(20):
                        start=time.perf_counter();db.execute('BEGIN IMMEDIATE')
                        if table=='outbox':db.execute('UPDATE outbox SET run=? WHERE id=?',('selected' if i%2 else 'other',identifier))
                        else:db.execute('UPDATE '+table+' SET status=? WHERE id=?',('pending' if i%2 else 'deferred',identifier)) if table=='queue' else db.execute('UPDATE plans SET status=? WHERE id=?',('COMMITTED' if i%2 else 'PREPARED',identifier))
                        db.commit();updates.append(time.perf_counter()-start)
                    inserts=[]
                    for i in range(20):
                        start=time.perf_counter();db.execute('BEGIN IMMEDIATE')
                        if table=='outbox':db.execute('INSERT INTO outbox VALUES (?,?,?)',('insert-'+str(i),'other','{}'))
                        elif table=='queue':db.execute('INSERT INTO queue VALUES (?,?,?,NULL)',('insert-'+str(i),'{}','pending'))
                        else:db.execute('INSERT INTO plans VALUES (?,?,?)',('insert-'+str(i),'{}','PREPARED'))
                        db.commit();inserts.append(time.perf_counter()-start)
                    output.append(dict(table=table,index=label,ddl=ddl,sql=sql,parameters=args,rows=len(rows),plan=plan,bytes=size,select_seconds=samples[1:],select_median=statistics.median(samples[1:]),update_seconds=updates,insert_seconds=inserts,indexes=list(db.execute('PRAGMA index_list('+table+')')),index_xinfo=list(db.execute('PRAGMA index_xinfo(ix_lab)')) if ddl else []))
    a.output.write_text(json.dumps(dict(sqlite=sqlite3.sqlite_version,dataset=info,experiments=output),indent=2)+'\n')
if __name__=='__main__':main()
