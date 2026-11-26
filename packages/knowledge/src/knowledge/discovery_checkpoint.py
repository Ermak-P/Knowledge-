"""Append-only provisional scan checkpoints. Terminal artifacts keep their old format."""
from .util import canonical_json, digest, loads, require


def create(db):
    db.execute('CREATE TABLE IF NOT EXISTS discovery_runs (id TEXT PRIMARY KEY, initial TEXT NOT NULL, initial_hash TEXT NOT NULL, sequence INTEGER NOT NULL, tail TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS discovery_chunks (scan TEXT NOT NULL, sequence INTEGER NOT NULL, payload TEXT NOT NULL, checksum TEXT NOT NULL, PRIMARY KEY(scan,sequence), FOREIGN KEY(scan) REFERENCES discovery_runs(id) ON DELETE CASCADE)')


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
    state = loads(initial)
    require(digest(state) == checksum and state['id'] == scan_id, 'corrupt-scan-checkpoint')
    expected = 1
    for version, payload, checked in db.execute(
            'SELECT sequence,payload,checksum FROM discovery_chunks WHERE scan=? ORDER BY sequence', (scan_id,)):
        delta = loads(payload)
        require(version == expected and digest([scan_id, version, checksum, delta]) == checked,
                'corrupt-scan-checkpoint')
        replay(state, delta)
        checksum = checked
        expected += 1
    require(expected == sequence + 1 and checksum == tail, 'corrupt-scan-checkpoint')
    return state, (sequence, tail)


def append(db, scan_id, previous, initial, delta):
    require(generation(db, scan_id) == previous, 'concurrent-scan-checkpoint-changed')
    if previous is None:
        checksum = digest(initial)
        db.execute('INSERT INTO discovery_runs VALUES (?,?,?,0,?)', (scan_id, canonical_json(initial), checksum, checksum))
        previous = (0, checksum)
    version, checksum = previous
    version += 1
    checked = digest([scan_id, version, checksum, delta])
    db.execute('INSERT INTO discovery_chunks VALUES (?,?,?,?)', (scan_id, version, canonical_json(delta), checked))
    db.execute('UPDATE discovery_runs SET sequence=?,tail=? WHERE id=?', (version, checked, scan_id))
    return version, checked


def publish(db, scan_id, previous, payload):
    require(generation(db, scan_id) == previous, 'concurrent-scan-checkpoint-changed')
    db.execute('INSERT OR REPLACE INTO scans VALUES (?,?)', (scan_id, payload))
    if previous is not None:
        db.execute('DELETE FROM discovery_runs WHERE id=?', (scan_id,))


def identities(db):
    if exists(db):
        return [row[0] for row in db.execute('SELECT id FROM discovery_runs ORDER BY id')]
    return []
