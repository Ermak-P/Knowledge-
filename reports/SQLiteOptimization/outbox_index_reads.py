"""Read-only index diagnostics on owned, validated historical-run snapshots.

Writes are measured through real Journal APIs in journal_profile_probe.py.
"""
import argparse,hashlib,json,sqlite3,statistics,tempfile,time
from contextlib import closing
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    info=json.loads((a.root.parent/(a.root.name+'.fixture.json')).read_text());assert info['all_owners_validated']
    relative='.harness/runs.sqlite3';i=list(info['databases']).index(relative);raw=(a.root.parent/(a.root.name+'.snapshot')/str(i)).read_bytes();assert hashlib.sha256(raw).hexdigest()==info['snapshot_sha256'][relative]
    rows=[]
    for name,sql in [('none',None),('ordinary','CREATE INDEX ix_lab ON outbox(run)'),('partial-selected',"CREATE INDEX ix_lab ON outbox(run) WHERE run='selected'")]:
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'snapshot.sqlite3';path.write_bytes(raw)
            with closing(sqlite3.connect(path)) as db,db:
                if sql:db.execute(sql);db.commit()
                for run in ('selected','run-1','absent'):
                    query='SELECT id,payload FROM outbox WHERE run=?';plan=list(db.execute('EXPLAIN QUERY PLAN '+query,(run,)));samples=[]
                    for _ in range(21):
                        start=time.perf_counter();values=list(db.execute(query,(run,)));samples.append(time.perf_counter()-start)
                    rows.append(dict(index=name,ddl=sql,run=run,rows=len(values),plan=plan,samples_seconds=samples[1:],median=statistics.median(samples[1:]),bytes=path.stat().st_size,page_count=db.execute('PRAGMA page_count').fetchone()[0],freelist_count=db.execute('PRAGMA freelist_count').fetchone()[0],index_xinfo=list(db.execute('PRAGMA index_xinfo(ix_lab)')) if sql else []))
                assert db.execute('PRAGMA quick_check').fetchone()==('ok',)
    a.output.write_text(json.dumps(dict(sqlite=sqlite3.sqlite_version,dataset=info,experiments=rows,writes='See public Journal INSERT/payload UPDATE measurements for default/opt-in, not unvalidated SQL writes.'),indent=2)+'\n')
if __name__=='__main__':main()
