"""Validated objects live only in one owned SQLite transaction.

No file metadata, row counts, or cross-connection trust. Invalidate BEFORE every
possibly mutating statement, even a rolled-back write/DDL/savepoint. total_changes
also catches writes through base-class APIs. Plain sqlite3 connections fall back
to rebuilding. Cached values are internal; public callers receive copies.
"""
import sqlite3


class Cursor(sqlite3.Cursor):
    def execute(self,sql,parameters=()):
        self.connection.invalidate_statement(sql)
        return super().execute(sql,parameters)
    def executemany(self,sql,parameters):
        self.connection.invalidate()
        return super().executemany(sql,parameters)
    def executescript(self,sql):
        self.connection.invalidate()
        return super().executescript(sql)


class Connection(sqlite3.Connection):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self._observer=None
        # sqlite invokes this on EVERY execution (including cached statements,
        # explicitly requested base cursors and C-level transaction boundaries).
        # Preserve instrumentation without replacing the invalidation hook.
        super().set_trace_callback(self._trace)
    def _trace(self,sql):
        self.invalidate_statement(sql)
        if self._observer is not None:self._observer(sql)
    def set_trace_callback(self,callback):self._observer=callback
    def invalidate(self):self._snapshot={};self._snapshot_changes=self.total_changes
    def invalidate_statement(self,sql):
        # WITH, PRAGMA, comments, EXPLAIN etc deliberately take the conservative
        # path. Only a simple SELECT is known to be an ordinary product read.
        words=sql.lstrip().split(None,1)
        if not words or words[0].upper()!='SELECT':self.invalidate()
    def cursor(self,factory=Cursor):return super().cursor(factory)
    def execute(self,sql,parameters=()):
        return self.cursor().execute(sql,parameters)
    def executemany(self,sql,parameters):
        return self.cursor().executemany(sql,parameters)
    def executescript(self,sql):
        return self.cursor().executescript(sql)
    def commit(self):self.invalidate();return super().commit()
    def rollback(self):self.invalidate();return super().rollback()
    def close(self):self.invalidate();return super().close()
    def __exit__(self,*args):
        self.invalidate();return super().__exit__(*args)


def view(db,key,build):
    if not isinstance(db,Connection) or not db.in_transaction:return build()
    if getattr(db,'_snapshot_changes',None)!=db.total_changes:db.invalidate()
    cache=getattr(db,'_snapshot',{})
    if key not in cache:
        value=build()
        # build is read-only. Re-fetch because conservative statements can clear
        # the cache during construction; never cache a partially built view.
        cache=getattr(db,'_snapshot',{});cache[key]=value;db._snapshot=cache
    return cache[key]
