"""Bounded, reproducible lexical observations keyed by exact sources."""
from pathlib import PurePosixPath

from .persistence_identity import POLICY, describe, identifier
from .util import canonical_json, digest, loads, require


def code_file(path):
    return path.endswith(('.cs', '.csproj'))


def exists(db):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='discovery_file_cache'").fetchone() is not None


def configuration(snapshot):
    shared = [[p, e['hash']] for p, e in sorted(snapshot['files'].items())
              if PurePosixPath(p).suffix.lower() in ('.props', '.targets', '.sln', '.config')]
    return digest([snapshot['policy'], snapshot['extractor'], POLICY, shared])


def binding(project, snapshot, path, context):
    entry = snapshot['files'][path]
    partition = entry['partition']
    return digest([project, context, path, entry['hash'], partition, entry.get('partition_ambiguous', False),
                   snapshot['files'].get(partition, {}).get('hash')])


def compatible(db, project, snapshot, paths, context, legacy):
    if not paths:
        return {}
    result = {}
    if exists(db):
        for path, key, payload, checksum in db.execute('SELECT path,binding,payload,checksum FROM discovery_file_cache'):
            if path not in paths or key != binding(project, snapshot, path, context):
                continue
            require(digest([key, payload]) == checksum, 'corrupt-discovery-observation-cache', {'path': path})
            observations = loads(payload)
            require(isinstance(observations, list) and all(o.get('path') == path
                    and o.get('content_hash') == snapshot['files'][path]['hash']
                    and o.get('project') == snapshot['files'][path]['partition']
                    and o.get('method') == snapshot['extractor'] for o in observations),
                    'corrupt-discovery-observation-cache', {'path': path})
            result[path] = observations
        return result
    prior = legacy()
    if prior is None:
        return {}
    old = prior['snapshot']
    available = historical_observations(prior)
    old_context = configuration(old)
    for path in paths & available.keys():
        if binding(project, old, path, old_context) == binding(project, snapshot, path, context):
            result[path] = available[path]
    return result


def normalized(item):
    data = describe(item)
    if data is not None and item.get('identity_policy') != POLICY:
        return {**item, 'id': identifier(*data), 'identity_policy': POLICY}
    return item


def historical_observations(state):
    """Rehydrate legacy occurrences only when aggregation retained all members."""
    if state.get('ambiguous'):
        return {}
    available = {p: [] for p, e in state['coverage'].items() if code_file(p) and verified(e)}
    for observation in state['observations']:
        body = {k: v for k, v in observation.items() if k != 'occurrences'}
        for location in observation.get('occurrences', [observation]):
            path = location['path']
            if path not in available:
                continue
            item = {**body, **location}
            require(item['content_hash'] == state['snapshot']['files'][path]['hash'], 'corrupt-persistence-observation')
            available[path].append(normalized(item))
    return available


def verified(entry):
    return entry.get('processing_status') == 'processed' and entry['status'] not in ('blocked','excluded','not-analyzed')


def rows(db, project, snapshot, context, observations):
    obsolete = ([(path,) for path, in db.execute('SELECT path FROM discovery_file_cache') if path not in snapshot['files']]
                if exists(db) else [])
    values = []
    for path, entries in observations.items():
        key = binding(project, snapshot, path, context)
        payload = canonical_json([normalized(item) for item in entries])
        values.append((path, key, payload, digest([key, payload])))
    return obsolete, values


def save(db, obsolete, values):
    db.execute('CREATE TABLE IF NOT EXISTS discovery_file_cache (path TEXT PRIMARY KEY, binding TEXT NOT NULL, payload TEXT NOT NULL, checksum TEXT NOT NULL)')
    db.executemany('DELETE FROM discovery_file_cache WHERE path=?', obsolete)
    db.executemany('INSERT INTO discovery_file_cache VALUES (?,?,?,?) ON CONFLICT(path) DO UPDATE SET '
                   'binding=excluded.binding,payload=excluded.payload,checksum=excluded.checksum '
                   'WHERE discovery_file_cache.checksum<>excluded.checksum', values)
