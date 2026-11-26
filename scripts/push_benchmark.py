"""Measure machine plan preparation against a synthetic source-bound queue."""
import argparse
from collections import Counter
from contextlib import ExitStack
from functools import wraps
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from unittest.mock import patch

from confluence_r2_benchmark import record
from discovery_benchmark import fixture, git
from knowledge import discovery, lifecycle
from knowledge import plan_deduplication, project_commands, source_reader, store as storage, util
from knowledge.sqlite_snapshot import Cursor
from knowledge.store import Store
from knowledge.util import canonical_json, digest


def seed(root, files, candidates, excluded):
    fixture(root, files)
    if excluded:
        folder = root / 'non-source'
        folder.mkdir()
        for index in range(excluded):
            (folder / f'{index:05}.bin').write_bytes(b'fixture')
        git(root, 'add', '.')
        git(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Excluded inputs')
    store = Store(root)
    store.init()
    lifecycle.upgrade(store, lifecycle.upgrade_preview(store)['fingerprint'])
    snapshot = discovery.inventory(root)
    source = dict(identity=snapshot['identity'], revision=snapshot['revision'], kind=snapshot['snapshot_kind'])
    with store.connection(True) as db:
        for index in range(697):
            claim, evidence = record(f'canonical.{index}', 1)
            for kind, item in [('claims', claim), ('evidence', evidence[0])]:
                db.execute('INSERT INTO records VALUES (?,?,?)', (item['id'], kind, canonical_json(item)))
                lifecycle.append(db, item['id'], kind, item, 'active', 'fixture', 'Benchmark fixture', None)
        for index in range(candidates):
            claim, evidence = record(f'pending.{index}', 1)
            operations = [lifecycle.op('add', 'claims', claim['id'], 0, claim),
                          lifecycle.op('add', 'evidence', evidence[0]['id'], 0, evidence[0])]
            item = dict(version=2, operation='batch', operations=operations, reason='Synthetic reviewed input', source=source)
            db.execute("INSERT INTO queue VALUES (?,?,'pending',NULL)", (digest(item), canonical_json(item)))
    return store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--files', type=int, default=38000)
    parser.add_argument('--excluded', type=int, default=6000)
    parser.add_argument('--candidates', type=int, default=25006)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    elapsed, calls = Counter(), Counter()

    def profile(module, name, label=None):
        key = label or name
        function = getattr(module, name)

        @wraps(function)
        def instrument(*params, **controls):
            started = perf_counter()
            calls[key] += 1
            try:
                return function(*params, **controls)
            finally:
                elapsed[key] += perf_counter() - started
        return patch.object(module, name, instrument)

    real_execute = Cursor.execute

    def sql(cursor, statement, parameters=()):
        operation = statement.split(None, 1)[0]
        label = 'sqlite_' + ('select' if operation == 'SELECT' else 'write'
                             if operation in ('INSERT', 'UPDATE', 'DELETE') else 'other')
        started = perf_counter()
        calls[label] += 1
        try:
            return real_execute(cursor, statement, parameters)
        finally:
            elapsed[label] += perf_counter() - started

    with TemporaryDirectory(prefix='knowledge-push-benchmark-') as tmp:
        project = Path(tmp) / 'repository'
        project.mkdir()
        store = seed(project, args.files, args.candidates, args.excluded)
        state = Path(tmp) / 'machine-state'
        binding = {'root': store.project.describe(), 'provider_reference': {'path': 'fixture', 'hash': 'fixture'},
                   'runtime_release': 'benchmark'}
        with ExitStack() as instrumentation:
            for module, name, label in (
                (discovery, 'inventory', 'inventory'), (source_reader, 'fingerprint', 'source_hashing'),
                (Store, '_check_control', 'sqlite_control_validation'), (Store, '_preview', 'preview'),
                (storage, 'candidate', 'candidate_validation'), (plan_deduplication, 'reconcile', 'deduplication'),
                (lifecycle, 'verify_source_bindings', 'source_validation'), (lifecycle, 'simulate', 'simulation'),
                (util, 'canonical_json', 'fingerprint_serialization'),
                (storage, 'canonical_json', 'store_serialization'), (project_commands, '_write', 'machine_artifacts'),
            ):
                instrumentation.enter_context(profile(module, name, label))
            instrumentation.enter_context(patch.object(Cursor, 'execute', sql))
            started = perf_counter()
            project_commands.ready(store)
            result = project_commands.push(store, project, state, binding, {})
            seconds = perf_counter() - started
        assert result['ok'] and result['included'] == args.candidates, result
        import sqlite3
        with sqlite3.connect(store.path) as db:
            pending, = db.execute("SELECT count(*) FROM queue WHERE status='pending'").fetchone()
            records, = db.execute('SELECT count(*) FROM records').fetchone()
            plans = dict(db.execute('SELECT status,count(*) FROM plans GROUP BY status'))
            plan_bytes, = db.execute('SELECT max(length(cast(payload AS blob))) FROM plans').fetchone()
        assert (pending, records, plans) == (args.candidates, 1394, {'PREPARED': 1})
        output = dict(seconds=seconds, calls=dict(calls), phase_seconds=dict(elapsed), files=args.files,
                      excluded=args.excluded, pending=pending, records=records, plan_bytes=plan_bytes,
                      last_plan_bytes=(state / 'last-plan.json').stat().st_size, database_bytes=store.path.stat().st_size)
        try:
            import resource
            output['peak_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        except ImportError:
            pass
        args.output.write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(output))


if __name__ == '__main__':
    main()
