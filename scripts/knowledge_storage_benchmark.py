"""Measure repeated prepare and approved cleanup with 25,000 pending candidates."""
import argparse
import json
from pathlib import Path
import tempfile
import time

from knowledge import lifecycle, plan_storage
from knowledge.store import Store
from knowledge.util import canonical_json, digest
from plan_deduplication_benchmark import claim, evidence


def elapsed(fn):
    start = time.perf_counter()
    value = fn()
    return value, round(time.perf_counter() - start, 3)


def candidate(number):
    record = claim(f'new.{number}', f'Synthetic storage benchmark assertion {number}.')
    return {'version': 1, 'operation': 'add',
            'records': {'claims': [record], 'evidence': [evidence(record, f'file{number}.cs')], 'relationships': []}}


def snapshot(value):
    return {key: value[key] for key in ('file_bytes', 'allocated_bytes', 'freelist_bytes', 'allocated_by_category', 'payload')}


def benchmark(count):
    with tempfile.TemporaryDirectory(prefix='knowledge-storage-benchmark-') as temporary:
        store = Store(temporary)
        store.init()
        lifecycle.upgrade(store, lifecycle.upgrade_preview(store)['fingerprint'])
        with store.connection(True) as db:
            for index in range(count):
                payload = candidate(index)
                db.execute('INSERT INTO queue VALUES (?,?,?,NULL)', (digest(payload), canonical_json(payload), 'pending'))
        initial = snapshot(plan_storage.statistics(temporary))
        first, first_seconds = elapsed(store.prepare)
        assert first['ok'] and len(first['included']) == count
        after_first = snapshot(plan_storage.statistics(temporary))
        store.submit(candidate(count))
        second, second_seconds = elapsed(store.prepare)
        assert second['ok'] and len(second['included']) == count + 1
        assert first['base'] == second['base']
        preview, preview_seconds = elapsed(lambda: plan_storage.preview(temporary, keep_recent=0, older_than_days=0, vacuum=True))
        assert [row['fingerprint'] for row in preview['preview']['obsolete']] == [first['fingerprint']]
        cleaned, cleanup_seconds = elapsed(lambda: plan_storage.clean(temporary, preview['preview'], preview['fingerprint']))
        counts = store.scan_counts()
        assert counts == {'records': 0, 'queue': count + 1, 'plans': 1}
        assert cleaned['validated']
        return {'synthetic': True, 'pending_before': count, 'pending_after': counts['queue'],
                'initial': initial, 'after_first_prepare': after_first,
                'before_cleanup': snapshot({'file_bytes': cleaned['file_bytes_before'], **preview['storage']}),
                'after_cleanup': snapshot(cleaned['storage']), 'removed_plans': cleaned['removed'],
                'removed_payload_bytes': cleaned['payload_bytes_reclaimed'],
                'seconds': {'first_prepare': first_seconds, 'second_prepare': second_seconds,
                            'preview': preview_seconds, 'cleanup_and_vacuum': cleanup_seconds}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count', type=int, default=25000)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(benchmark(args.count), indent=2) + '\n', encoding='utf-8')
