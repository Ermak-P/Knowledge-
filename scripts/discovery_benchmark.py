"""Measure synthetic Git discovery using the selected checkout on PYTHONPATH."""
import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
from functools import wraps
import json
import math
from pathlib import Path
import platform
import sqlite3
import statistics
import subprocess
import tempfile
import time
from unittest.mock import patch

from knowledge import discovery, lifecycle, source_reader, util
from knowledge.store import Store


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE, text=True).strip()


def fixture(root, count):
    files = []
    for index in range(count):
        if index % 1000 == 0:
            folder = root / f'Project{index // 1000:02}'
            folder.mkdir()
            path = folder / 'Project.csproj'
            path.write_text('<Project Sdk="Microsoft.NET.Sdk"><ItemGroup>\n<PackageReference Include="Example" />\n</ItemGroup></Project>\n', encoding='utf-8')
        else:
            path = folder / f'Source{index:05}.cs'
            declaration = f'class Service{index} : IService {{ }}' if index % 17 == 1 else ''
            wiring = 'UseSqlite();\n' if index % 101 == 0 else ''
            path.write_text(f'namespace Example;\n{declaration}\n{wiring}' + '// synthetic source\n' * (index % 97), encoding='utf-8')
            files.append(path)
    git(root, 'init', '-q')
    git(root, 'add', '.')
    git(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Fixture')
    return files


def quantiles(values):
    return {'p50': statistics.median(values), 'p95': sorted(values)[math.ceil(.95 * len(values)) - 1]} if values else {}


def measure(action):
    counts = Counter()
    durations = defaultdict(float)
    writes = []
    payload_bytes = Counter()

    def instrument(module, name, key):
        real = getattr(module, name)

        @wraps(real)
        def measured(*args, **kwargs):
            start = time.perf_counter()
            counts[key] += 1
            try:
                result = real(*args, **kwargs)
                if key == 'fingerprint':
                    counts['hashed_bytes'] += result.get('bytes') or 0
                if key == 'serialize':
                    payload_bytes[key] += len(result.encode('utf-8'))
                return result
            finally:
                durations[key] += time.perf_counter() - start
        return patch.object(module, name, measured)

    real_connect = sqlite3.connect

    def connect(*args, **kwargs):
        counts['sqlite_connections'] += 1
        db = real_connect(*args, **kwargs)
        started = None

        def trace(sql):
            nonlocal started
            counts['sql_statements'] += 1
            if sql.startswith('BEGIN'):
                counts['transactions'] += 1
            if sql.startswith('BEGIN IMMEDIATE'):
                started = time.perf_counter()
            if sql.startswith(('COMMIT', 'ROLLBACK')) and started is not None:
                writes.append(time.perf_counter() - started)
                started = None
            if sql.startswith(('INSERT', 'UPDATE', 'DELETE')):
                payload_bytes['sqlite_write_sql'] += len(sql.encode('utf-8'))
        db.set_trace_callback(trace)
        return db

    from knowledge import auto_init, store as store_module
    with ExitStack() as stack:
        for module, name, key in (
            (discovery, 'inventory', 'inventory'), (source_reader, 'fingerprint', 'fingerprint'),
            (discovery, 'extract', 'extraction'), (discovery, 'git_process', 'git_process'),
            (discovery, 'incremental_scope', 'identity'), (discovery, 'proposal', 'proposal'),
            (discovery, 'fresh_evidence', 'freshness'), (discovery, 'reconcile', 'reconciliation'),
            (discovery, 'equivalent_candidate', 'deduplication'), (discovery, 'canonical_json', 'serialize'),
            (discovery, 'loads', 'deserialize'), (Store, '_check_control', 'control_validation'),
            (auto_init, 'write_json', 'checkpoint_and_diagnostics'),
        ):
            stack.enter_context(instrument(module, name, key))
        if hasattr(store_module.Connection, 'execute'):
            real_execute = store_module.Connection.execute

            def execute(db, sql, *args):
                if sql.startswith('PRAGMA quick_check'):
                    start = time.perf_counter()
                    result = real_execute(db, sql, *args)
                    durations['quick_check'] += time.perf_counter() - start
                    counts['quick_check'] += 1
                    return result
                return real_execute(db, sql, *args)
            stack.enter_context(patch.object(store_module.Connection, 'execute', execute))
        stack.enter_context(patch.object(sqlite3, 'connect', connect))
        start = time.perf_counter()
        result = action()
        elapsed = time.perf_counter() - start
    return {'wall_seconds': elapsed, 'counts': counts, 'phase_seconds': durations,
            'write_transactions': len(writes), 'write_seconds': quantiles(writes),
            'payload_bytes': payload_bytes, 'result': result}


def run(store, chunk, steps=None, **options):
    session = discovery.ScanSession(store) if hasattr(discovery, 'ScanSession') else None
    scan = session.scan if session else lambda **kw: discovery.scan(store, **kw)
    scan_id = options.pop('scan_id', None)
    for _ in range(steps or 10000):
        state = scan(scan_id=scan_id, max_files=chunk, **options)
        scan_id = state['id']
        if state['processing_complete']:
            discovery.reconcile(store, scan_id)
            break
    return {k: state[k] for k in ('id', 'complete', 'counters')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--sizes', type=int, nargs='+', default=[1000, 10000, 38350])
    parser.add_argument('--samples', type=int, default=3)
    parser.add_argument('--chunk', type=int, default=100)
    parser.add_argument('--baseline-probe', type=int)
    parser.add_argument('--populated', action='store_true')
    args = parser.parse_args()
    data = {'commit': git(Path.cwd(), 'rev-parse', 'HEAD'), 'platform': platform.platform(),
            'python': platform.python_version(), 'chunk_size': args.chunk, 'samples': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save(name, size, store, measured):
        row = {'scenario': name, 'eligible_files': size, 'database_bytes': store.path.stat().st_size, **measured}
        data['samples'].append(row)
        args.output.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        print(name, size, round(row['wall_seconds'], 3), row['counts'], flush=True)

    for size in args.sizes:
        for _ in range(args.samples):
            with tempfile.TemporaryDirectory(prefix='discovery-benchmark-') as tmp:
                root = Path(tmp)
                files = fixture(root, size)
                if args.populated:
                    from confluence_r2_benchmark import seed
                    store = seed(root, (1000, 2000, 12500, 1))
                else:
                    store = Store(root)
                    store.init()
                    lifecycle.upgrade(store, lifecycle.upgrade_preview(store)['fingerprint'])
                full = measure(lambda: run(store, args.chunk, steps=args.baseline_probe))
                save('full' if not args.baseline_probe else 'full-probe', size, store, full)
                if args.baseline_probe or size != 38350:
                    continue
                for changes in (0, 4, 100):
                    for path in files[:changes]:
                        with path.open('a', encoding='utf-8') as stream:
                            stream.write(f'\nclass Changed{path.stem} {{ }}\n')
                    save(f'incremental-{changes}', size, store, measure(
                        lambda: run(store, args.chunk, base='HEAD', head='HEAD', incremental=True)))
                    if changes == 4:
                        save('harness-producer-4', size, store, measure(
                            lambda: {'decisions': len(discovery.candidate_observe(store, [p.relative_to(root).as_posix() for p in files[:4]])['decisions'])}))
                    git(root, 'reset', '--hard', 'HEAD')
                first = measure(lambda: run(store, args.chunk, steps=1, restart=True))
                save('recovery-before', size, store, first)
                save('recovery-resume', size, store, measure(lambda: run(store, args.chunk, scan_id=first['result']['id'])))


if __name__ == '__main__':
    main()
