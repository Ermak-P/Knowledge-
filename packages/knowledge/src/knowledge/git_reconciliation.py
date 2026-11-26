"""Revalidate pending lexical candidates without rewriting their source bindings."""
from collections import defaultdict

from . import discovery, discovery_cache, discovery_history
from .confluence import is_binding
from .persistence_identity import POLICY


def local(item):
    source = item.get('source')
    return source is not None and not is_binding(source)


def lexical_paths(item):
    # Scan-produced positive additions can be proven by the old observation,
    # the same input bytes and a check for new lexical ambiguity. Reviewed
    # assertions, updates and operations on the dependency graph use their
    # exact snapshot until independently refreshed.
    provenance = {'actor': 'deterministic-discovery', 'method': discovery.VERSION}
    evidence = {}
    claims = []
    for operation in item['operations']:
        payload = operation['payload']
        if (operation['action'] != 'add' or operation['kind'] not in ('claims', 'evidence')
                or payload['provenance'] != provenance):
            return None
        if operation['kind'] == 'claims':
            if payload['depends_on'] or payload['conflicts_with']:
                return None
            claims.append(payload)
        else:
            if not isinstance(payload['source'], str) or not discovery_cache.code_file(payload['source']):
                return None
            evidence[payload['id']] = (payload['source'], payload.get('content_hash'))
    if not claims or any(not set(claim['evidence']) <= evidence.keys() for claim in claims):
        return None
    return set(evidence.values()), {claim['id'] for claim in claims}


def source_key(entry):
    return (entry['hash'], entry['partition'], entry.get('partition_ambiguous', False), entry['status'] == 'blocked')


def changed_code(previous, current):
    changes = defaultdict(set)
    for path in previous.keys() | current.keys():
        if not discovery_cache.code_file(path):
            continue
        old, new = previous.get(path), current.get(path)
        if old is not None and new is not None and source_key(old) == source_key(new):
            continue
        for entry in (old, new):
            if entry is not None:
                changes[entry['partition']].add(path)
    return changes


def partition(db, root, pending, snapshot, progress):
    """Return safe inputs and the explicit disposition of each deferred input."""
    groups = defaultdict(dict)
    deferred = {}
    for cid, item in pending.items():
        if local(item) and item['source']['identity'] != snapshot['identity']:
            groups[item['source']['identity']][cid] = item

    if not groups:
        return pending, []

    files = snapshot['files']
    context = discovery_cache.configuration(snapshot)
    checked = {}
    total = sum(len(group) for group in groups.values())

    def defer(cid, item, reason, paths=(), broader=False, action=None):
        deferred[cid] = {'candidate': cid, 'reason': reason, 'details': {
            'paths': sorted(paths)[:8], 'base': item['source']['revision'], 'head': snapshot['revision'],
            'broader_scan_required': broader,
            'next_action': action or ('Refresh discovery for the affected scope and review its coverage before preparing again.'
                            if broader else 'Run incremental discovery for the recorded range, or explicitly reanalyze the affected candidate.')}}

    def observe(path):
        if path not in checked:
            entry = dict(files[path])
            probe = {'snapshot': snapshot, 'identity_policy': POLICY, 'coverage': {path: entry}}
            observations = discovery._extract_path(root, probe, path)
            checked[path] = [item['id'] for item in observations] if discovery_cache.verified(entry) else None
        return checked[path]

    for identity, group in list(groups.items()):
        for cid, item in list(group.items()):
            proof = lexical_paths(item)
            if proof is None:
                defer(cid, item, 'git-reviewed-or-dependent-source-needs-reanalysis',
                      action='Reanalyze the exact reviewed source and its dependencies before submitting a fresh candidate.')
                del group[cid]
            else:
                group[cid] = (item, proof)
        if not group:
            del groups[identity]

    processed = len(deferred)
    progress('reconciling-git-sources', processed_candidates=processed, total_candidates=total)
    if not groups:
        return {cid: item for cid, item in pending.items() if cid not in deferred}, [
            deferred[cid] for cid in pending if cid in deferred]

    for _, scan in discovery_history.scan_rows(db, sources=set(groups), complete=True,
                                              extractor=discovery.VERSION, newest=True):
        if scan.get('identity_policy') != POLICY or (scan.get('incremental') and
                not (scan.get('identity_verification') or {}).get('complete')):
            continue
        old = scan['snapshot']
        candidates = groups.get(old['identity'], {})
        eligible = set(scan['candidates']) & candidates.keys()
        if not eligible:
            continue
        discovery._validate_snapshot(old)
        old_files = old['files']
        changes = changed_code(old_files, files)
        configuration_changed = discovery_cache.configuration(old) != context
        project_checks = {}

        def inspect_project(project):
            if project not in project_checks:
                collisions = {}
                blocker = None
                for path in sorted(changes.get(project, set()) & files.keys()):
                    identities = observe(path)
                    if identities is None:
                        blocker = path
                        break
                    for identifier in identities:
                        collisions.setdefault(identifier, path)
                project_checks[project] = (collisions, blocker)
            return project_checks[project]

        for cid in sorted(eligible):
            item, proof = candidates.pop(cid)
            processed += 1
            if processed % 256 == 0:
                progress('reconciling-git-sources', processed_candidates=processed, total_candidates=total)
            paths, identifiers = proof
            removed = [path for path, _ in paths if path not in files]
            modified = [path for path, content in paths if path in files and (
                path not in old_files or files[path]['hash'] != content or old_files[path]['hash'] != content
                or source_key(files[path]) != source_key(old_files[path]))]
            if removed or modified:
                defer(cid, item, 'git-source-deleted-or-renamed' if removed else 'git-source-content-changed',
                      removed + modified)
                continue
            projects = {files[path]['partition'] for path, _ in paths}
            if configuration_changed or any(project in changes.get(project, ()) for project in projects):
                defer(cid, item, 'git-discovery-configuration-changed', projects, broader=True)
                continue
            if snapshot.get('coverage_errors'):
                defer(cid, item, 'git-source-inventory-incomplete', broader=True)
                continue

            for project in sorted(projects):
                collisions, blocker = inspect_project(project)
                if blocker is not None:
                    defer(cid, item, 'git-dependency-coverage-unverified', [blocker], broader=True)
                    break
                if paths := {collisions[identifier] for identifier in identifiers & collisions.keys()}:
                    defer(cid, item, 'git-lexical-identity-needs-review', paths)
                    break
        if not candidates:
            groups.pop(old['identity'], None)
        if not groups:
            break

    for group in groups.values():
        for cid, (item, _) in group.items():
            defer(cid, item, 'git-source-proof-unavailable', broader=True)
    progress('reconciling-git-sources', processed_candidates=total, total_candidates=total)
    return {cid: item for cid, item in pending.items() if cid not in deferred}, [
        deferred[cid] for cid in pending if cid in deferred]
