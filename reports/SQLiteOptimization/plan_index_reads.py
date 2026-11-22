"""Rare/zero COMMITTED index diagnostics without changing plan approvals."""
import argparse,hashlib,json,sqlite3,statistics,tempfile,time
from contextlib import closing
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    info=json.loads((a.root.parent/(a.root.name+'.fixture.json')).read_text());relative='.knowledge/store.sqlite3';i=list(info['databases']).index(relative)
    raw=(a.root.parent/(a.root.name+'.snapshot')/str(i)).read_bytes();assert hashlib.sha256(raw).hexdigest()==info['snapshot_sha256'][relative];rows=[]
    for name,ddl in [('none',None),('ordinary','CREATE INDEX ix_lab ON plans(status,id)'),('partial',"CREATE INDEX ix_lab ON plans(id) WHERE status='COMMITTED'")]:
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.sqlite3';path.write_bytes(raw)
            with closing(sqlite3.connect(path)) as db,db:
                if ddl:db.execute(ddl);db.commit()
                query="SELECT id FROM plans WHERE status='COMMITTED' ORDER BY id";plan=list(db.execute('EXPLAIN QUERY PLAN '+query));samples=[]
                for _ in range(21):
                    start=time.perf_counter();values=list(db.execute(query));samples.append(time.perf_counter()-start)
                assert db.execute('PRAGMA quick_check').fetchone()==('ok',)
                rows.append(dict(index=name,ddl=ddl,rows=len(values),plan=plan,samples_seconds=samples[1:],median=statistics.median(samples[1:]),bytes=path.stat().st_size))
    a.output.write_text(json.dumps(dict(sqlite=sqlite3.sqlite_version,dataset=info,experiments=rows,canonical_rows_changed=False),indent=2)+'\n')
if __name__=='__main__':main()
