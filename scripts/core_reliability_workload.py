"""Equivalent synthetic before/after workload; never inspects owner projects."""
import argparse
import contextlib
import hashlib
import json
from pathlib import Path
import platform
import sys
import tempfile
import time
import tracemalloc
from knowledge import discovery, lifecycle
from knowledge.store import Store
from knowledge.auto_init import run, ScanError
from knowledge import auto_init
from unittest.mock import patch


def populate(root, count=300):
    root.mkdir()
    (root / 'Project.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"/>\n', encoding='utf-8')
    for n in range(count):
        (root / ('Source%05d.cs' % n)).write_text('namespace Synthetic; public class Type%d {}\n' % n, encoding='utf-8')
    (root / '00-invalid.json').write_bytes(b'{"invalid":"\xff"}')
    (root / '01-utf16.xml').write_bytes('<?xml version="1.0" encoding="UTF-16"?><root>Пример</root>'.encode('utf-16'))
    (root / '02-cp1251.xml').write_bytes('<?xml version="1.0" encoding="windows-1251"?><root>Пример</root>'.encode('cp1251'))
    (root / '03-large.json').write_text(json.dumps({'large': 'x' * 1100000}), encoding='utf-8')
    (root / '04-doc.md').write_text('Синтетическая документация\n', encoding='utf-8-sig')
    (root / '05-deploy.yaml').write_text('apiVersion: v1\nkind: ConfigMap\n', encoding='utf-8')


def main():
    p = argparse.ArgumentParser(); p.add_argument('--output', type=Path, required=True); p.add_argument('--files', type=int, default=300);p.add_argument('--clean',action='store_true')
    a = p.parse_args(); a.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='core-reliability-') as temporary:
        base = Path(temporary); root = base / 'synthetic'; populate(root, a.files)
        if a.clean:
            (root/'00-invalid.json').write_text('{}',encoding='utf-8')
            (root/'01-utf16.xml').write_text('<root>Пример</root>',encoding='utf-8')
            (root/'02-cp1251.xml').write_text('<root>Пример</root>',encoding='utf-8')
            (root/'03-large.json').write_text('{"small":true}',encoding='utf-8')
        workload={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.iterdir())}
        workload_identity=hashlib.sha256(json.dumps(workload,sort_keys=True).encode()).hexdigest()
        store = Store(root); store.init(); lifecycle.upgrade(store, lifecycle.upgrade_preview(store)['fingerprint'])
        tracemalloc.start(); before = time.perf_counter(); inv = discovery.inventory(root); inventory_seconds = time.perf_counter() - before
        before = time.perf_counter(); failure = None;chunks=[];writes=[];original_run=auto_init.subprocess.run;original_write=auto_init.write_json
        def observed_run(*args,**kwargs):
            began=time.perf_counter();value=original_run(*args,**kwargs);chunks.append({'seconds':time.perf_counter()-began,'returncode':value.returncode});return value
        def observed_write(path,value):
            began=time.perf_counter();result=original_write(path,value);writes.append({'file':path.name,'seconds':time.perf_counter()-began});return result
        with (a.output / 'progress.log').open('w', encoding='utf-8') as log, contextlib.redirect_stdout(log),patch.object(auto_init.subprocess,'run',observed_run),patch.object(auto_init,'write_json',observed_write):
            try: exit_code=run(root, base / 'driver', max_files=100)
            except ScanError as error: failure = str(error);exit_code=1
        seconds = time.perf_counter() - before; _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
        states = discovery.status(store)['scans']; final = states[-1]
        counts = {}
        for entry in final['coverage'].values(): counts[entry['status']] = counts.get(entry['status'], 0) + 1
        before=time.perf_counter();plan=store.prepare();prepare_seconds=time.perf_counter()-before
        child_peak=None
        if sys.platform.startswith('linux'):
            import resource
            child_peak=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024
        value = {'profile': 'synthetic-only', 'production_measurement': False, 'platform': platform.platform(), 'python': sys.version,
                 'files': a.files + 7,'clean':a.clean,'workload_identity':workload_identity,
                 'inventory_seconds': inventory_seconds, 'driver_seconds': seconds, 'parent_peak_tracemalloc_bytes': peak,
                 'largest_child_peak_rss_bytes':child_peak,'driver_exit_code':exit_code,'cli_calls':len(chunks),
                 'scan_mcp_call_count':0,'chunks':chunks,'writes':writes,'checkpoint_seconds':sum(row['seconds'] for row in writes if row['file']=='checkpoint.json'),
                 'prepare_seconds':prepare_seconds,'prepared_plan_ok':plan['ok'],
                 'failure': failure, 'complete': final['complete'], 'work': final['work'], 'coverage': counts,
                 'counters': final.get('counters'), 'scan_state': final.get('state'), 'queue_size': len(store.status()['queue']),
                 'reconciliation': discovery.reconcile(store, final['id'])}
        (a.output / 'result.json').write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({key: value[key] for key in ('failure', 'complete', 'coverage', 'inventory_seconds', 'driver_seconds', 'queue_size')}))


if __name__ == '__main__': main()
