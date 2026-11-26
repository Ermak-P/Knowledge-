"""Measure plan storage and apply explicitly approved retention in one database."""
from collections import defaultdict
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
import sqlite3
import time

from . import lifecycle, plan_receipts
from .access import consumer_scope, require_maintainer
from .coordination import gate
from .execution_lock import ProjectExecutionLock
from .providers import semantic_bindings
from .store import Store
from .util import canonical_json, fingerprint, loads, require

PREPARED_PREFIX = 'plan-prepared-at-v1:'
SERIES_PREFIX = 'plan-preparation-series-v1:'
APPROVAL_PREFIX = 'plan-approval-intent-v1:'
MAINTENANCE_PREFIX = 'plan-maintenance-v1:'
TABLE_CATEGORIES = {
    'records': 'canonical', 'queue': 'candidates', 'plans': 'plans', 'receipts': 'receipts',
    'revisions': 'revisions', 'scans': 'scan_history', 'discovery_runs': 'scan_history',
    'discovery_chunks': 'scan_history', 'discovery_snapshot_blocks': 'scan_history',
    'discovery_file_cache': 'scan_history',
}


@contextmanager
def own(store):
    require_maintainer()
    lease = ProjectExecutionLock(store.project.root).acquire()
    try:
        with gate(store.project.root, exclusive=True):
            yield
    finally:
        lease.close()


def _statistics(db):
    def groups(query):
        return {key: {'rows': count, 'payload_bytes': size} for key, count, size in db.execute(query)}

    page_size, = db.execute('PRAGMA page_size').fetchone()
    pages, = db.execute('PRAGMA page_count').fetchone()
    free, = db.execute('PRAGMA freelist_count').fetchone()
    tables = {name for name, in db.execute("SELECT name FROM sqlite_schema WHERE type='table'")}
    categories = defaultdict(int)
    page_details = {}
    if any('ENABLE_DBSTAT_VTAB' in option for option, in db.execute('PRAGMA compile_options')):
        for name, allocated, unused in db.execute('SELECT name,sum(pgsize),sum(unused) FROM dbstat GROUP BY name'):
            category = TABLE_CATEGORIES.get(name, 'other_tables') if name in tables or name == 'sqlite_schema' else 'indexes'
            categories[category] += allocated
            page_details[name] = {'allocated_bytes': allocated, 'unused_in_allocated_bytes': unused}
    payload = {
        'canonical': groups('SELECT kind,count(*),sum(length(CAST(payload AS BLOB))) FROM records GROUP BY kind'),
        'candidates': groups('SELECT status,count(*),sum(length(CAST(payload AS BLOB))) FROM queue GROUP BY status'),
        'plans': groups('SELECT status,count(*),sum(length(CAST(payload AS BLOB))) FROM plans GROUP BY status'),
    }
    for table in ('receipts', 'revisions', 'scans', 'discovery_runs', 'discovery_chunks', 'discovery_snapshot_blocks'):
        if table in tables:
            columns = {column[1] for column in db.execute('PRAGMA table_info(' + table + ')')}
            col = 'payload' if 'payload' in columns else 'initial'
            count, size = db.execute(f'SELECT count(*),coalesce(sum(length(CAST({col} AS BLOB))),0) FROM {table}').fetchone()
            payload[table] = {'rows': count, 'payload_bytes': size}
    return {'page_size': page_size, 'page_count': pages, 'allocated_bytes': pages * page_size,
            'freelist_bytes': free * page_size, 'allocated_by_category': dict(categories),
            'btree_allocation_available': bool(page_details), 'btrees': page_details, 'payload': payload}


def statistics(root):
    store = Store(root)
    with consumer_scope(), store.connection() as db:
        return {'ok': True, 'database': str(store.path), 'file_bytes': store.path.stat().st_size, **_statistics(db)}


def _selection(store, db, policy):
    records = store._records(db)
    canonical_v0 = fingerprint(records)
    upgraded = lifecycle.enabled(db)
    canonical = fingerprint({'records': records, 'revisions': lifecycle.latest(db)}) if upgraded else canonical_v0
    bindings = semantic_bindings(db) if upgraded else {}
    timestamps = {key[len(PREPARED_PREFIX):]: value for key, value in db.execute(
        "SELECT key,value FROM metadata WHERE key LIKE ?", (PREPARED_PREFIX + '%',))}
    latest = {value for value, in db.execute("SELECT value FROM metadata WHERE key LIKE ?", (SERIES_PREFIX + '%',))}
    protected = {key[len(APPROVAL_PREFIX):] for key, in db.execute(
        "SELECT key FROM metadata WHERE key LIKE ?", (APPROVAL_PREFIX + '%',))}
    from .cr_workflow import PREFIX as CR_PREFIX
    for payload, in db.execute("SELECT value FROM metadata WHERE key LIKE ?", (CR_PREFIX + '%',)):
        review = loads(payload)
        if review['state'] in ('preparing', 'awaiting_approval', 'persisting') and review['proposal']:
            protected.add(review['proposal']['plan'])
    eligible = []
    for pid, payload in db.execute("SELECT id,payload FROM plans WHERE status='PREPARED' ORDER BY id"):
        if pid in protected:
            continue
        plan = loads(payload)
        used = {cid: bindings[cid] for cid in plan['candidates'] if cid in bindings}
        current = {canonical}
        if used:
            current.add(fingerprint({'canonical': canonical, 'semantic_bindings': used}))
        if plan['version'] == 1 and all(item['version'] == 1 for item in plan['candidates'].values()):
            current.add(canonical_v0)
        reason = ('obsolete-canonical-base' if plan['base'] not in current else
                  'superseded-preparation' if pid in timestamps and pid not in latest else None)
        if reason:
            eligible.append({'fingerprint': pid, 'reason': reason,
                             'last_prepared_at': timestamps.get(pid), 'payload_bytes': len(payload.encode('utf-8'))})
    eligible.sort(key=lambda row: (row['last_prepared_at'] or '', row['fingerprint']), reverse=True)
    obsolete = [row for row in eligible[policy['keep_recent']:]
                if (not row['last_prepared_at'] and policy['include_undated']) or
                (row['last_prepared_at'] and row['last_prepared_at'] <= policy['cutoff'])]
    compact = []
    if policy['compact_receipts'] and upgraded:
        for pid, payload in db.execute("SELECT plan,receipts.payload FROM receipts JOIN plans ON id=plan "
                                       "WHERE status='ACKNOWLEDGED' ORDER BY plan"):
            saved = len(payload.encode('utf-8')) - len(plan_receipts.reference(pid).encode('utf-8'))
            if saved > 0:
                compact.append({'fingerprint': pid, 'payload_bytes_saved': saved})
    return {'version': 1, 'project': store.project.identity, 'policy': policy, 'obsolete': obsolete,
            'compact_receipts': compact, 'eligible_obsolete_count': len(eligible),
            'reclaimable_payload_bytes': sum(row['payload_bytes'] for row in obsolete) +
                sum(row['payload_bytes_saved'] for row in compact)}


def preview(root, keep_recent=2, older_than_days=30, include_undated=False, compact_receipts=False, vacuum=False):
    require(type(keep_recent) is int and 0 <= keep_recent <= 1000 and
            type(older_than_days) is int and 0 <= older_than_days <= 36500, 'invalid-plan-retention-policy')
    policy = {'keep_recent': keep_recent, 'cutoff': (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat(),
              'include_undated': include_undated, 'compact_receipts': compact_receipts, 'vacuum': vacuum}
    store = Store(root)
    with own(store), store.connection() as db:
        value = _selection(store, db, policy)
        return {'ok': True, 'preview': value, 'fingerprint': fingerprint(value), 'storage': _statistics(db)}


def fault(phase):
    pass


def pin_approval(store, pid):
    with store.connection(True) as db:
        store._plan(db, pid)
        db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)', (APPROVAL_PREFIX + pid, 'approved'))


def clean(root, value, approval):
    require(isinstance(value, dict) and approval == fingerprint(value), 'exact-plan-maintenance-approval-required')
    store = Store(root)
    started = time.monotonic()
    with own(store):
        before = store.path.stat().st_size
        key = MAINTENANCE_PREFIX + approval
        with store.connection(True) as db:
            receipt = db.execute('SELECT value FROM metadata WHERE key=?', (key,)).fetchone()
            if receipt:
                report = loads(receipt[0])
            else:
                require(_selection(store, db, value['policy']) == value, 'stale-plan-maintenance-preview')
                obsolete = [(row['fingerprint'],) for row in value['obsolete']]
                db.executemany("DELETE FROM plans WHERE id=? AND status='PREPARED'", obsolete)
                db.executemany('DELETE FROM metadata WHERE key=?', ((PREPARED_PREFIX + pid,) for pid, in obsolete))
                db.executemany('DELETE FROM metadata WHERE key LIKE ? AND value=?',
                               ((SERIES_PREFIX + '%', pid) for pid, in obsolete))
                db.executemany('UPDATE receipts SET payload=? WHERE plan=?',
                               ((plan_receipts.reference(row['fingerprint']), row['fingerprint']) for row in value['compact_receipts']))
                store._check_control(db)
                require(db.execute('PRAGMA integrity_check').fetchall() == [('ok',)], 'plan-maintenance-integrity-failed')
                report = {'removed': len(obsolete), 'compacted_receipts': len(value['compact_receipts']),
                          'removed_fingerprints': [pid for pid, in obsolete],
                          'compacted_fingerprints': [row['fingerprint'] for row in value['compact_receipts']],
                          'payload_bytes_reclaimed': value['reclaimable_payload_bytes'], 'file_bytes_before': before}
                db.execute('INSERT INTO metadata VALUES (?,?)', (key, canonical_json(report)))
                fault('before-cleanup-commit')
        fault('after-cleanup-commit')
        if value['policy']['vacuum']:
            with closing(sqlite3.connect(store.path.as_uri() + '?mode=rw', uri=True, timeout=0.15)) as db:
                if db.execute('PRAGMA freelist_count').fetchone()[0]:
                    db.execute('VACUUM')
        validated = store.validate()
        storage = statistics(root)
    return {'ok': True, 'approval': approval, **report, 'file_bytes_after': storage['file_bytes'],
            'elapsed_seconds': round(time.monotonic() - started, 3), 'validated': validated['ok'], 'storage': storage}
