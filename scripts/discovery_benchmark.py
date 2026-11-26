"""Measure synthetic Git discovery using the selected checkout on PYTHONPATH."""
import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack, redirect_stdout
from functools import wraps
import contextlib
import hashlib
import io
import json
import os
import math
from pathlib import Path
import platform
import sqlite3
import statistics
import subprocess
import tempfile
import threading
import time
from unittest.mock import patch

from knowledge import discovery, lifecycle, source_reader, util
from knowledge.store import Store
from knowledge.util import KnowledgeError


def git(root, *args):
    environment = {**os.environ, 'GIT_AUTHOR_DATE': '2026-11-01T12:00:00+00:00',
                   'GIT_COMMITTER_DATE': '2026-11-01T12:00:00+00:00'}
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE,
                                   text=True, env=environment).strip()


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
            if index % 911 == 0:
                declaration = 'partial class SyntheticDuplicate { }'
            path.write_text(f'namespace Example;\n{declaration}\n{wiring}' + '// synthetic source\n' * (index % 97), encoding='utf-8')
            files.append(path)
    (root / '.gitignore').write_text('.knowledge/\n.knowledge-control.lock\n.harness/\n', encoding='utf-8')
    git(root, 'init', '-q', '-b', 'fixture')
    git(root, 'config', 'core.autocrlf', 'false')
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
    real_popen = subprocess.Popen
    real_walk = os.walk

    class CountedProcess(real_popen):
        def __init__(self, command, *args, **kwargs):
            if isinstance(command, (list, tuple)):
                program = Path(command[0]).name.casefold()
                if program.startswith('python'):
                    counts['python_process'] += 1
            super().__init__(command, *args, **kwargs)

    def walk(*args, **kwargs):
        iterator = real_walk(*args, **kwargs)
        while True:
            start = time.perf_counter()
            try:
                item = next(iterator)
            except StopIteration:
                return
            finally:
                durations['directory_enumeration'] += time.perf_counter() - start
            yield item

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
            if sql.startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE')) and started is None:
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
            (util, 'canonical_json', 'utility_serialization'), (util, 'loads', 'utility_deserialization'),
        ):
            stack.enter_context(instrument(module, name, key))
        if hasattr(discovery, '_reconcile'):
            stack.enter_context(instrument(discovery, '_reconcile', 'reconciliation'))
            stack.enter_context(instrument(discovery, '_scan_impact', 'dependency_impact'))
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
        stack.enter_context(patch.object(subprocess, 'Popen', CountedProcess))
        stack.enter_context(patch.object(os, 'walk', walk))
        start = time.perf_counter()
        try:
            result = action()
        except KnowledgeError as error:
            result = {'error': error.code, 'details': error.details}
        elapsed = time.perf_counter() - start
    for name in ('inventory', 'extraction', 'python_process', 'git_process'):
        counts.setdefault(name, 0)
    return {'wall_seconds': elapsed, 'counts': counts, 'phase_seconds': durations,
            'write_transactions': len(writes), 'write_seconds': quantiles(writes), 'write_sample_seconds': writes,
            'peak_process_rss_bytes': peak_rss(),
            'payload_bytes': payload_bytes, 'result': result}


def run(store, chunk, steps=None, **options):
    session = discovery.ScanSession(store) if hasattr(discovery, 'ScanSession') else None
    scan = (lambda **kw: session.scan(reconcile_result=True, **kw)) if session else lambda **kw: discovery.scan(store, **kw)
    scan_id = options.pop('scan_id', None)
    for _ in range(steps or 10000):
        state = scan(scan_id=scan_id, max_files=chunk, **options)
        scan_id = state['id']
        if state['processing_complete']:
            if not session:
                discovery.reconcile(store, scan_id)
            break
    return {**{k: state[k] for k in ('id', 'complete', 'counters')},
            'candidate_count': len(state.get('candidates', [])),
            **({'identity_cache_complete': state['identity_verification']['complete']} if 'identity_verification' in state else {})}


def peak_rss():
    if os.name != 'nt':
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1024 if platform.system() == 'Linux' else 1)
    import ctypes
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ('peak_rss', 'rss', 'paged_peak', 'paged',
                                               'nonpaged_peak', 'nonpaged', 'commit', 'commit_peak')]
    kernel = ctypes.WinDLL('kernel32')
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    get_memory = ctypes.WinDLL('psapi').GetProcessMemoryInfo
    get_memory.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    item = Counters()
    item.size = ctypes.sizeof(item)
    if get_memory(kernel.GetCurrentProcess(), ctypes.byref(item), item.size):
        return item.peak_rss
    return None


def seed_populated(root, stress=False):
    from confluence_r2_benchmark import seed
    from knowledge import confluence

    store = seed(root, (10000, 20000, 12500, 1) if stress else (1000, 2000, 12500, 1))
    text = 'Synthetic business requirement.'
    source = confluence.register(store, dict(instance='fixture', page_id='123', version=1, title='Fixture',
        url='https://docs.example.invalid/wiki/pages/123', content=text, retrieved_at='2026-11-01T12:00:00Z',
        representation='text'))['source']
    with store.connection(True) as db:
        for n in range(1, 10000 if stress else 1000, 10):
            identifier = f'canonical.{n}'
            dependency = f'canonical.{n - 1}'
            row = db.execute('SELECT payload FROM records WHERE id=?', (identifier,)).fetchone()
            item = util.loads(row[0])
            item['depends_on'] = [dependency]
            db.execute('UPDATE records SET payload=? WHERE id=?', (util.canonical_json(item), identifier))
            revised = util.loads(db.execute('SELECT payload FROM revisions WHERE id=? AND revision=1', (identifier,)).fetchone()[0])
            revised['record'] = item
            db.execute('UPDATE revisions SET payload=? WHERE id=? AND revision=1', (util.canonical_json(revised), identifier))
            relation = {'id': f'fixture.relationship.{n}', 'type': 'depends_on', 'from': identifier,
                        'to': dependency, 'provenance': item['provenance']}
            db.execute('INSERT INTO records VALUES (?,?,?)', (relation['id'], 'relationships', util.canonical_json(relation)))
            lifecycle.append(db, relation['id'], 'relationships', relation, 'active', 'fixture', 'Synthetic dependency', None)
        registered = confluence.verify_binding(db, source)
        provenance = {'actor': 'fixture', 'method': 'confluence-documentation-v1'}
        evidence = dict(id='independent.evidence', type='direct-authoritative', status='active',
                        source={**source, 'reference': registered['url']}, location='normalized-text#L1',
                        content_hash=registered['content_hash'], description=text, substantiates=['independent.claim'],
                        captured_at=registered['retrieved_at'], provenance=provenance)
        claim = dict(id='independent.claim', statement=text, type='business_rule', status='CONFIRMED',
                     evidence=[evidence['id']], provenance=provenance, last_verified='2026-11-01',
                     depends_on=[], conflicts_with=[])
        for kind, item in (('claims', claim), ('evidence', evidence)):
            db.execute('INSERT INTO records VALUES (?,?,?)', (item['id'], kind, util.canonical_json(item)))
            lifecycle.append(db, item['id'], kind, item, 'active', 'fixture', 'Independent documentation', source)
    history = root / 'Historical.cs'
    history.write_text('class Historical { }', encoding='utf-8')
    discovery.scan(store, max_files=100)
    history.unlink()
    return store


def worker(store, folder, chunk, worker_python):
    from knowledge import auto_init, scan_jobs
    from knowledge.machine_mcp import result as mcp_result
    from knowledge.project_commands import job_summary

    folder.mkdir()
    root = str(store.project.root)
    owner = store.project.describe()
    reference = {'path': 'synthetic', 'hash': 'synthetic'}
    binding = {'root': owner, 'provider_reference': reference, 'runtime_release': 'synthetic'}
    folder = folder / 'full'
    folder.mkdir()
    auto_init.write_json(folder / 'job.json', {'version': 1, 'job': 'benchmark', 'pid': os.getpid(),
        'process_stamp': scan_jobs.process_stamp(os.getpid()), 'root': root,
        'state': 'RUNNING', 'binding': binding, 'scope': {'kind': 'full'}})
    stopped = threading.Event()
    latencies = []
    sizes = []

    def poll():
        while not stopped.wait(.025):
            start = time.perf_counter()
            summary = job_summary(folder, binding, {'evidence': 'synthetic'})
            wire = mcp_result(summary)
            latencies.append(time.perf_counter() - start)
            sizes.append(len(wire.content[0].text.encode('utf-8')))

    observer = threading.Thread(target=poll)
    observer.start()
    try:
        options = {'persistent': True} if hasattr(discovery, 'ScanSession') else {}
        runtime = (patch.object(auto_init.sys, 'executable', str(worker_python)) if worker_python else
                   contextlib.nullcontext())
        with redirect_stdout(io.StringIO()), runtime:
            auto_init.run(root, folder, max_files=chunk, cancel_job='benchmark', **options)
    finally:
        stopped.set()
        observer.join()
    final = auto_init.read_json(folder / 'last-result.json')
    return {'complete': final['complete'], 'candidate_count': len(final['candidates']),
            'progress_samples': len(latencies), 'progress_seconds': quantiles(latencies),
            'progress_max_bytes': max(sizes, default=0), 'progress_sample_seconds': latencies}


def harness_capture(journal, initial, current, event):
    from harness.capture import deliver

    run = dict(version=1, id='fixture-delivery', project=journal.project.identity,
               task={'initial_source': initial}, final_source=util.digest(current),
               capture_time=lifecycle.now(), capture_event=event)
    journal.save(run)
    deliver(journal, run, {'capture': 'required', 'limits': {}})
    deliveries = journal.outbox(run['id'])
    assert run['capture']['state'] == 'delivered' and deliveries, run['capture']
    deliver(journal, run, {'capture': 'required', 'limits': {}})
    assert deliveries == journal.outbox(run['id'])
    return {'delivery': run['capture'], 'outbox_count': len(deliveries), 'replay_equal': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--sizes', type=int, nargs='+', default=[1000, 10000, 38350])
    parser.add_argument('--samples', type=int, default=3)
    parser.add_argument('--chunk', type=int, default=100)
    parser.add_argument('--baseline-probe', type=int)
    parser.add_argument('--populated', action='store_true')
    parser.add_argument('--stress', action='store_true')
    parser.add_argument('--full-only', action='store_true')
    parser.add_argument('--mode', choices=['core', 'worker'], default='core')
    parser.add_argument('--worker-python', type=Path)
    parser.add_argument('--implementation-commit')
    args = parser.parse_args()
    data = {'commit': args.implementation_commit or git(Path.cwd(), 'rev-parse', 'HEAD'), 'platform': platform.platform(),
            'module_hash': hashlib.sha256(Path(discovery.__file__).read_bytes()).hexdigest(),
            'python': platform.python_version(), 'chunk_size': args.chunk, 'populated': args.populated or args.stress,
            'stress': args.stress, 'mode': args.mode, 'samples': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save(name, size, store, measured):
        row = {'scenario': name, 'eligible_files': size, 'database_bytes': store.path.stat().st_size, **measured}
        data['samples'].append(row)
        args.output.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        print(name, size, round(row['wall_seconds'], 3), row['counts'], flush=True)

    for size in args.sizes:
        for _ in range(args.samples):
            with tempfile.TemporaryDirectory(prefix='discovery-benchmark-') as tmp:
                root = Path(tmp) / 'source'
                root.mkdir()
                if args.populated or args.stress:
                    store = seed_populated(root, args.stress)
                else:
                    store = Store(root)
                    store.init()
                    lifecycle.upgrade(store, lifecycle.upgrade_preview(store)['fingerprint'])
                files = fixture(root, size)
                if args.mode == 'worker':
                    save('worker-full', size, store, measure(lambda: worker(store, Path(tmp) / 'worker', args.chunk, args.worker_python)))
                    continue
                if not args.full_only and not args.baseline_probe and size == 38350:
                    from harness.runtime import Journal, source_snapshot
                    journal = Journal(root)
                    initial = source_snapshot(journal.project)
                full = measure(lambda: run(store, args.chunk, steps=args.baseline_probe))
                save('full' if not args.baseline_probe else 'full-probe', size, store, full)
                if args.full_only or args.baseline_probe or size != 38350 or 'error' in full['result']:
                    continue
                for changes in (0, 4, 100):
                    for path in files[:changes]:
                        with path.open('a', encoding='utf-8') as stream:
                            stream.write(f'\nclass Changed{path.stem} {{ }}\n')
                    if changes == 4:
                        current = source_snapshot(journal.project)
                        save('harness-delivery-4-and-replay', size, store, measure(
                            lambda: harness_capture(journal, initial, current, 1)))
                    save(f'incremental-{changes}', size, store, measure(
                        lambda: run(store, args.chunk, base='HEAD', head='HEAD', incremental=True)))
                    git(root, 'reset', '--hard', 'HEAD')
                first = measure(lambda: run(store, args.chunk, steps=1, restart=True))
                save('recovery-before', size, store, first)
                save('recovery-resume', size, store, measure(lambda: run(store, args.chunk, scan_id=first['result']['id'])))


if __name__ == '__main__':
    main()
