"""Versioned terminal artifacts share immutable, checksummed inventory blocks."""
import base64
import hashlib
import zlib

from .util import KnowledgeError, canonical_json, digest, loads, require

FORMAT = 'scan-manifest-v1'
TABLE = 'discovery_snapshot_blocks'
TABLE_SQL = ('CREATE TABLE discovery_snapshot_blocks (digest TEXT PRIMARY KEY, payload TEXT NOT NULL) WITHOUT ROWID')
BUCKETS = 1024


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _encode(raw):
    return base64.b64encode(zlib.compress(raw, level=1)).decode('ascii')


def _decode(payload):
    try:
        return zlib.decompress(base64.b64decode(payload, validate=True))
    except (ValueError, TypeError, zlib.error) as error:
        raise KnowledgeError('corrupt-discovery-history') from error


def _raw(value):
    return canonical_json(value).encode('utf-8')


def _json(raw):
    try:
        return loads(raw.decode('utf-8'))
    except (UnicodeError, ValueError, KnowledgeError) as error:
        raise KnowledgeError('corrupt-discovery-history') from error


def exists(db):
    return db.execute("SELECT 1 FROM sqlite_schema WHERE type='table' AND name=?", (TABLE,)).fetchone() is not None


def _blocks(keys):
    keys = list(keys)
    for offset in range(0, len(keys), 256):
        yield keys[offset:offset+256]


def _select(db, fields, keys):
    for chunk in _blocks(keys):
        yield from db.execute(f'SELECT {fields} FROM {TABLE} WHERE digest IN (' + ','.join('?' for _ in chunk) + ')', chunk)


def prepare(db, state):
    snapshot = state['snapshot']
    maps = {name: snapshot[name] for name in ('files','index_blobs') if name in snapshot}
    buckets = {}
    for name, mapping in maps.items():
        for path, entry in mapping.items():
            bucket = zlib.crc32(path.encode('utf-8')) % BUCKETS
            buckets.setdefault(bucket, {}).setdefault(name, {})[path] = entry

    # Paths never move between buckets when unrelated paths are added or removed.
    # The new manifest only writes buckets whose exact content has changed.
    raw_blocks = {}
    refs = []
    for bucket in buckets.values():
        raw = _raw(bucket)
        key = _sha(raw)
        refs.append(key)
        raw_blocks[key] = raw
    exclusions = _raw(snapshot['exclusions'])
    exclusion_ref = _sha(exclusions)
    raw_blocks[exclusion_ref] = exclusions
    saved = {key for key, in _select(db, 'digest', raw_blocks)} if exists(db) else set()
    inserts = [(key, _encode(raw)) for key, raw in raw_blocks.items() if key not in saved]
    header = {k: v for k, v in snapshot.items() if k not in maps and k != 'exclusions'}
    body = {**state, 'snapshot': header}
    packed = _encode(_raw({'state': body, 'maps': sorted(maps), 'blocks': sorted(refs), 'exclusions': exclusion_ref}))
    envelope = {'format': FORMAT, 'id': state['id'], 'source': snapshot['identity'],
                'revision': snapshot.get('revision'), 'extractor': state['extractor'],
                'full': not state.get('incremental', False), 'complete': state['complete'], 'body': packed,
                'summary': {'state':state.get('state'), 'counters':state.get('counters')}}
    return canonical_json({**envelope, 'checksum': digest(envelope)}), inserts


def write_blocks(db, rows):
    if not exists(db):
        db.execute(TABLE_SQL)
    db.executemany(f'INSERT INTO {TABLE} VALUES (?,?)', rows)


def _envelope(scan_id, payload):
    value = loads(payload)
    require(isinstance(value, dict), 'corrupt-discovery-history')
    if 'format' not in value:
        return value
    fields = {'format','id','source','revision','extractor','full','complete','body','summary','checksum'}
    require(isinstance(value, dict) and set(value)==fields and value['format']==FORMAT
            and value['id']==scan_id and digest({k:v for k,v in value.items() if k!='checksum'})==value['checksum'],
            'corrupt-discovery-history')
    return value


def _materialize(db, envelope):
    if 'format' not in envelope:
        return envelope
    value = _json(_decode(envelope['body']))
    state = value['state']
    snapshot = state['snapshot']
    require(state['id']==envelope['id'] and snapshot['identity']==envelope['source']
            and snapshot.get('revision')==envelope['revision'] and state['extractor']==envelope['extractor']
            and state['complete']==envelope['complete'] and (not state.get('incremental', False))==envelope['full']
            and envelope['summary']=={'state':state.get('state'),'counters':state.get('counters')},
            'corrupt-discovery-history')
    require(value['maps'] in (['files'], ['files','index_blobs']), 'corrupt-discovery-history')
    refs = value['blocks']
    exclusion_ref = value['exclusions']
    require(isinstance(refs,list) and all(isinstance(key,str) for key in refs)
            and len(set(refs))==len(refs) and len(refs)<=BUCKETS and isinstance(exclusion_ref,str)
            and exclusion_ref not in refs, 'corrupt-discovery-history')
    mappings = {name: {} for name in value['maps']}
    require(exists(db), 'missing-discovery-snapshot-block')
    found = 0
    for key, block in _select(db,'digest,payload',[*refs, exclusion_ref]):
        raw = _decode(block)
        require(_sha(raw)==key, 'corrupt-discovery-snapshot-block')
        items = _json(raw)
        found += 1
        if key == exclusion_ref:
            require(isinstance(items, list), 'corrupt-discovery-snapshot-block')
            snapshot['exclusions'] = items
            continue
        require(isinstance(items,dict) and set(items)<=set(mappings), 'corrupt-discovery-snapshot-block')
        for name, entries in items.items():
            require(isinstance(entries,dict) and not (entries.keys() & mappings[name].keys()),
                    'corrupt-discovery-snapshot-block')
            mappings[name].update(entries)
    require(found==len(refs)+1, 'missing-discovery-snapshot-block')
    snapshot.update((name, dict(sorted(entries.items()))) for name, entries in mappings.items())
    return state


def decode(db, scan_id, payload):
    return _materialize(db, _envelope(scan_id, payload))


def scan_rows(db, scan_id=None, *, sources=None, revision=None, full=False, complete=False,
              extractor=None, newest=False, summaries=False):
    """Pre-filter compact manifests so unrelated history never loads its inventory."""
    sql = 'SELECT id,payload FROM scans'
    if scan_id is not None:
        sql += ' WHERE id=?'
    if newest:
        sql += ' ORDER BY rowid DESC'
    for identifier, payload in db.execute(sql,(scan_id,) if scan_id is not None else ()):
        value = _envelope(identifier,payload)
        compact = 'format' in value
        snap = value if compact else value.get('snapshot', {})
        if sources is not None and snap.get('source' if compact else 'identity') not in sources:
            continue
        if revision is not None and snap.get('revision') != revision:
            continue
        if full and (not value['full'] if compact else value.get('incremental',False)):
            continue
        if complete and not value.get('complete'):
            continue
        if extractor is not None and value.get('extractor') != extractor:
            continue
        if summaries and compact:
            yield identifier, {'id':identifier,'snapshot':{'identity':value['source'],'revision':value['revision']},
                               'complete':value['complete'],'incremental':not value['full'],**value['summary']}
        else:
            yield identifier, _materialize(db,value)
