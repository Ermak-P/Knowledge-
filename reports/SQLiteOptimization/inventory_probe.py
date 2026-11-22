"""Diagnostic schema/page inventory on same-root validated benchmark snapshots."""
import argparse,hashlib,json,sqlite3,tempfile
from contextlib import closing
from pathlib import Path


def inspect(db):
    tables=[t for t, in db.execute("SELECT name FROM sqlite_schema WHERE type='table' ORDER BY name")]
    indexes={}
    for table in tables:
        indexes[table]=[]
        for row in db.execute('PRAGMA index_list("'+table+'")'):
            name=row[1];indexes[table].append(dict(index_list=row,index_xinfo=list(db.execute('PRAGMA index_xinfo("'+name+'")'))))
    return dict(sqlite=sqlite3.sqlite_version,page_size=db.execute('PRAGMA page_size').fetchone()[0],page_count=db.execute('PRAGMA page_count').fetchone()[0],freelist_count=db.execute('PRAGMA freelist_count').fetchone()[0],journal_mode=db.execute('PRAGMA journal_mode').fetchone()[0],synchronous=db.execute('PRAGMA synchronous').fetchone()[0],schema=list(db.execute('SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name')),indexes=indexes)


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    info=json.loads((a.root.parent/(a.root.name+'.fixture.json')).read_text());result={}
    for i,relative in enumerate(info['databases']):
        data=(a.root.parent/(a.root.name+'.snapshot')/str(i)).read_bytes();assert hashlib.sha256(data).hexdigest()==info['snapshot_sha256'][relative]
        with tempfile.TemporaryDirectory(prefix='sqlite-inventory-') as tmp:
            path=Path(tmp)/'snapshot.sqlite3';path.write_bytes(data)
            with closing(sqlite3.connect(path)) as db,db:
                result[relative]={'baseline':inspect(db)}
                if relative.startswith('.harness/'):
                    db.execute('CREATE INDEX ix_outbox_run ON outbox(run)');db.commit();result[relative]['opt_in']=inspect(db)
                    try:result[relative]['index_allocated_bytes']=db.execute("SELECT sum(pgsize) FROM dbstat WHERE name='ix_outbox_run'").fetchone()[0]
                    except sqlite3.OperationalError:result[relative]['index_allocated_bytes']=None
    a.output.write_text(json.dumps(dict(dataset=info,inventory=result,policy='raw SQL diagnostics; copied snapshots retain original identity; no product effects'),indent=2)+'\n')
if __name__=='__main__':main()
