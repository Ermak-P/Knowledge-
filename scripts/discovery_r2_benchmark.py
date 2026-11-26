"""Measure R1/R2 against identical synthetic Git fixtures and outboxes."""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
import sqlite3

from discovery_benchmark import fixture, git, measure, run, seed_populated, worker
from harness.capture import deliver
from harness.runtime import Journal, source_snapshot
from knowledge import discovery, lifecycle
from knowledge.store import Store
from knowledge.util import digest


def storage(store):
    with sqlite3.connect(store.path) as db:
        pages = db.execute('PRAGMA page_count').fetchone()[0]
        free = db.execute('PRAGMA freelist_count').fetchone()[0]
        size = db.execute('PRAGMA page_size').fetchone()[0]
        objects = dict(db.execute('SELECT name,sum(pgsize) FROM dbstat GROUP BY name'))
        terminal = db.execute('SELECT coalesce(sum(length(cast(payload AS BLOB))),0) FROM scans').fetchone()[0]
        blocks = objects.get('discovery_snapshot_blocks', 0)
        return dict(physical_bytes=store.path.stat().st_size, logical_bytes=(pages-free)*size,
                    allocated_pages=pages, free_pages=free, page_size=size,
                    terminal_payload_bytes=terminal, shared_snapshot_allocated_bytes=blocks,
                    observation_cache_bytes=objects.get('discovery_file_cache',0),
                    canonical_bytes=objects.get('records',0)+objects.get('revisions',0),
                    candidate_bytes=objects.get('queue',0),
                    index_bytes=sum(size for name,size in objects.items() if name.startswith(('sqlite_autoindex','ix_'))))


def capture(journal, initial, number, *, replay=True):
    current = source_snapshot(journal.project)
    run_state = dict(version=1, id=f'fixture-delivery-{number}', project=journal.project.identity,
                     task={'initial_source': initial}, final_source=digest(current),
                     capture_time=lifecycle.now(), capture_event=number)
    journal.save(run_state)
    deliver(journal, run_state, {'capture':'required','limits':{}})
    first = journal.outbox(run_state['id'])
    if replay:
        deliver(journal, run_state, {'capture':'required','limits':{}})
    return {'state':run_state['capture']['state'], 'error':run_state['capture'].get('error'),
            'outbox':len(first), 'replay_equal':first==journal.outbox(run_state['id'])}


def modified(files, number, size):
    for path in files[:size]:
        with path.open('a', encoding='utf-8') as stream:
            stream.write(f'\nclass R2Change{number}{path.stem} {{}}\n')


def breakdown(store, scan_id):
    start = perf_counter()
    state = discovery.status(store, scan_id)['scans'][0]
    elapsed = perf_counter() - start
    def length(value):
        return len(json.dumps(value, ensure_ascii=False, separators=(',',':')).encode('utf-8'))
    return {'inventory_json':length(state['snapshot']), 'coverage_json':length(state['coverage']),
            'observations_json':length(state['observations']), 'read_seconds':elapsed}


def candidate_batch(root, output, commit):
    from confluence_r2_benchmark import record
    report = {'commit':commit, 'operations':[]}
    for count in (1,5,10,50,100):
        # Independent stores give each size the same queue and canonical graph.
        with TemporaryDirectory(prefix='discovery-r2-batch-', dir=root) as tmp:
            project = Path(tmp)
            store = seed_populated(project)
            fixture(project,100)
            snap = discovery.inventory(project)
            source = dict(identity=snap['identity'], revision=snap['revision'], kind=snap['snapshot_kind'])
            candidates = []
            for n in range(count):
                claim, evidence = record(f'bench.batch.{n}')
                ops = [lifecycle.op('add','evidence',e['id'],0,e) for e in evidence]
                ops.append(lifecycle.op('add','claims',claim['id'],0,claim))
                candidates.append(lifecycle.batch(ops,'Synthetic delivery workload',source))
            if count==1 or not hasattr(store,'submit_git_batch'):
                submit = lambda: [store.submit(value) for value in candidates]
            else:
                submit = lambda: store.submit_git_batch(candidates)
            for phase in ('deliver','replay'):
                row = measure(submit)
                receipts = row.pop('result')
                assert len(receipts)==count
                assert all(r['result']==('submitted' if phase=='deliver' else 'duplicate') for r in receipts)
                assert [r['candidate'] for r in receipts]==[digest(value) for value in candidates]
                row.pop('write_sample_seconds',None)
                report['operations'].append(dict(size=count,phase=phase, **row, storage=storage(store),
                                                 throughput=count/row['wall_seconds']))
                output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
                print(count,phase,round(row['wall_seconds'],2),row['counts'].get('control_validation'),flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--sizes', type=int, default=38350)
    p.add_argument('--implementation-commit', required=True)
    p.add_argument('--counts', type=int, nargs=4, default=(20,20,10,10))
    p.add_argument('--worker', action='store_true')
    p.add_argument('--batch', action='store_true')
    a = p.parse_args()
    report = {'commit':a.implementation_commit,'files':a.sizes,'operations':[]}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory(prefix='discovery-r2-') as tmp:
        if a.batch:
            candidate_batch(tmp, a.output, a.implementation_commit)
            return
        root = Path(tmp)/'source'
        root.mkdir()
        store = seed_populated(root)
        files = fixture(root,a.sizes)
        journal = Journal(root)

        def save(label, operation):
            result = measure(operation)
            result.pop('write_sample_seconds',None)
            row = {'scenario':label, **result, 'storage':storage(store)}
            report['operations'].append(row)
            a.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
            print(label,round(row['wall_seconds'],2),row['storage']['physical_bytes'],row['result'].get('state',''), flush=True)
            return row

        initial = save('full',lambda:run(store,100))
        report['initial_artifact'] = breakdown(store, initial['result']['id'])
        for n in range(a.counts[0]):
            save('no-change',lambda:run(store,100,base='HEAD',head='HEAD',incremental=True, restart=True))
        serial = 0
        for count, repeats in zip((4,100), a.counts[1:3]):
            for n in range(repeats):
                before = git(root,'rev-parse','HEAD')
                modified(files,serial,count)
                serial += 1
                git(root,'add','.')
                git(root,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm',f'Scan {serial}')
                save(f'incremental-{count}',lambda:run(store,100,base=before,head='HEAD',incremental=True))
        for n in range(a.counts[3]):
            before = source_snapshot(journal.project)
            modified(files[100+(n*4):],serial+n,4)
            save('harness-4',lambda:capture(journal,before,n))
            git(root,'add','.')
            git(root,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm',f'Harness {n}')
        if a.worker:
            checkpoint = save('interrupt',lambda:run(store,100,steps=1,restart=True))
            save('resume',lambda:run(store,100,scan_id=checkpoint['result']['id']))
            # Use a separate output folder and the already warmed operating-system cache.
            save('worker',lambda:worker(store,Path(tmp)/'worker',100,None))
        a.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')


if __name__ == '__main__':
    main()
