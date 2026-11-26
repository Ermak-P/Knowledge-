"""Append-only provisional scan checkpoints. Terminal artifacts keep their old format."""
import hashlib
import zlib

from .util import KnowledgeError, canonical_json, digest, loads, require


def _hash(payload):
    return hashlib.sha256(payload).hexdigest()


def _pack(value):
    return zlib.compress(canonical_json(value).encode('utf-8'), level=1)


def _unpack(payload):
    try:
        return loads(zlib.decompress(payload).decode('utf-8'))
    except (TypeError, zlib.error, UnicodeError) as error:
        raise KnowledgeError('corrupt-scan-checkpoint') from error



TABLE_SQL = {
    'discovery_runs': 'CREATE TABLE discovery_runs (id TEXT PRIMARY KEY, initial BLOB NOT NULL, initial_hash TEXT NOT NULL, sequence INTEGER NOT NULL, tail TEXT NOT NULL)',
    'discovery_chunks': 'CREATE TABLE discovery_chunks (scan TEXT NOT NULL, sequence INTEGER NOT NULL, payload BLOB NOT NULL, checksum TEXT NOT NULL, PRIMARY KEY(scan,sequence), FOREIGN KEY(scan) REFERENCES discovery_runs(id) ON DELETE CASCADE)',
}


def create(db):
    for sql in TABLE_SQL.values():
        db.execute(sql.replace('CREATE TABLE ', 'CREATE TABLE IF NOT EXISTS ', 1))


def exists(db):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='discovery_runs'").fetchone() is not None


def initial_row(db, scan_id):
    if exists(db):
        return db.execute('SELECT initial,initial_hash,sequence,tail FROM discovery_runs WHERE id=?', (scan_id,)).fetchone()
    return None


def generation(db, scan_id):
    if exists(db):
        row = db.execute('SELECT sequence,tail FROM discovery_runs WHERE id=?', (scan_id,)).fetchone()
        if row:
            return tuple(row)
    return None


def load(db, scan_id, replay):
    row = initial_row(db, scan_id)
    if row is None:
        return None
    initial, checksum, sequence, tail = row
    require(isinstance(initial, bytes) and _hash(initial) == checksum, 'corrupt-scan-checkpoint')
    state = _unpack(initial)
    require(state['id'] == scan_id, 'corrupt-scan-checkpoint')
    expected = 1
    for version, payload, checked in db.execute(
            'SELECT sequence,payload,checksum FROM discovery_chunks WHERE scan=? ORDER BY sequence', (scan_id,)):
        require(isinstance(payload, bytes) and version == expected
                and digest([scan_id, version, checksum, _hash(payload)]) == checked, 'corrupt-scan-checkpoint')
        replay(state, _unpack(payload))
        checksum = checked
        expected += 1
    require(expected == sequence + 1 and checksum == tail, 'corrupt-scan-checkpoint')
    return state, (sequence, tail)


def encode(scan_id, previous, initial, delta):
    packed_initial = _pack(initial) if previous is None else None
    sequence, tail = previous if previous is not None else (0, _hash(packed_initial))
    payload = _pack(delta)
    version = sequence + 1
    return packed_initial, tail, version, payload, digest([scan_id, version, tail, _hash(payload)])


def append(db, scan_id, previous, encoded):
    require(generation(db, scan_id) == previous, 'concurrent-scan-checkpoint-changed')
    initial, tail, version, payload, checked = encoded
    if initial is not None:
        db.execute('INSERT INTO discovery_runs VALUES (?,?,?,0,?)', (scan_id, initial, tail, tail))
    db.execute('INSERT INTO discovery_chunks VALUES (?,?,?,?)', (scan_id, version, payload, checked))
    db.execute('UPDATE discovery_runs SET sequence=?,tail=? WHERE id=?', (version, checked, scan_id))
    return version, checked


def publish(db, scan_id, previous, payload):
    require(generation(db, scan_id) == previous, 'concurrent-scan-checkpoint-changed')
    if previous is not None:
        db.execute('DELETE FROM discovery_runs WHERE id=?', (scan_id,))
    db.execute('INSERT OR REPLACE INTO scans VALUES (?,?)', (scan_id, payload))


def identities(db):
    if exists(db):
        return [row[0] for row in db.execute('SELECT id FROM discovery_runs ORDER BY id')]
    return []
