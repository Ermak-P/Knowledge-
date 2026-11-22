"""Optional physical indexes; no canonical format or dependency-direction change.

Only outbox(run) earned a product-level gain. Knowledge's all-row audit dominates
queue/plan subset reads; those indexes are intentionally absent. This module is
also usable by standalone maintenance without importing Harness.
"""
from contextlib import closing
import hashlib
import sqlite3
from pathlib import Path
from .util import canonical_json,require

PATH='.harness/runs.sqlite3'
NAME='ix_outbox_run'
SQL='CREATE INDEX ix_outbox_run ON outbox(run)'


def check(db):
    row=db.execute('SELECT tbl_name,sql FROM sqlite_schema WHERE name=?',(NAME,)).fetchone()
    require(row is None or (row[0]=='outbox' and ' '.join(row[1].split()).upper()==SQL.upper()),'index-definition-conflict')
    return row is not None


def create(db):
    if not check(db):db.execute(SQL)


def identity(project):
    """Full schema + canonical row fingerprint, excluding ONLY our derived index.

    This is maintenance-only, not a cheaper public corruption contract. The
    normal validated backup snapshot still runs before this physical comparison.
    """
    path=project.root/PATH
    if not path.exists():return None
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=.15)) as db:
        db.execute('BEGIN');check(db);h=hashlib.sha256()
        def add(value):
            data=canonical_json(value).encode();h.update(str(len(data)).encode()+b':'+data)
        for row in db.execute('SELECT type,name,tbl_name,sql FROM sqlite_schema WHERE name!=? ORDER BY type,name',(NAME,)):add(row)
        for table, in db.execute("SELECT name FROM sqlite_schema WHERE type='table' ORDER BY name"):
            require(table.replace('_','').isalnum(),'unsafe-database-table');add(table)
            columns=len(db.execute('PRAGMA table_info("'+table+'")').fetchall())
            for row in db.execute('SELECT * FROM "'+table+'" ORDER BY '+','.join(str(i+1) for i in range(columns))):add(row)
        return h.hexdigest()


def unchanged(project,value):
    from . import maintenance as m
    state,_=m.snapshot(project)
    before=dict(value['state']);after=dict(state)
    before['files']={k:v for k,v in before['files'].items() if k!=PATH}
    after['files']={k:v for k,v in after['files'].items() if k!=PATH}
    require(before==after and identity(project)==value['index_state'],'index-maintenance-intervening-state-conflict')


def finish(project,journal,base):
    from . import maintenance as m
    value=journal['preview'];unchanged(project,value)
    path=project.root/PATH
    if path.exists():
        db=next(c for c in project._maintenance_reservations if Path(c.execute('PRAGMA database_list').fetchone()[2])==path)
        present=check(db)
        if journal['operation']=='index-upgrade':create(db)
        elif present:db.execute('DROP INDEX '+NAME)
        m.fault('index-before-commit');db.commit();m.fault('index-after-commit')
        db.execute('BEGIN IMMEDIATE')
    unchanged(project,value)
    journal['status']='COMPLETED';m.write(base/'journal.json',journal)
    m.fault('maintenance-committed')
    (project.root/'.maintenance/active.json').unlink()
    return dict(ok=True,operation=journal['operation'],transaction=journal['id'],status='COMPLETED',backup=journal['backup'],canonical_approval='unchanged; physical indexes only')
