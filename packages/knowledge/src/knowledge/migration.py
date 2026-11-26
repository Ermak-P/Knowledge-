"""Explicit, add-only migration of a documented legacy snapshot.

Original source files are preserved byte-for-byte in the migration manifest,
including legacy queue/history. Canonical records retain original values.
A complete private staging database is atomically linked into an absent target.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from .project import Project, safe_tree
from .store import Store, GROUPS, SCHEMAS, legacy, validate_records, candidate, create_tables, checkpoint, publish_directory
from .util import canonical_json, loads, fingerprint, digest, require, read_text, read_document


def snapshot(root):
    project = Project(root)
    source = project.root/'.ai'
    require(source.is_dir(), 'legacy-source-absent')
    safe_tree(source)
    external=project.root/'.harness/knowledge/candidates/queue.jsonl'
    interchange=source/'state/candidates.json'
    discovery=[]
    for path,role in ((interchange,'interchange'),(external,'external-jsonl')):
        safe_tree(path)
        discovery.append({'path':path.relative_to(project.root).as_posix(),'role':role,
                          'state':('unsupported' if role=='external-jsonl' else 'selected') if path.exists() else 'absent',
                          'bytes':path.stat().st_size if path.is_file() else None,
                          'sha256':hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None})
    require(not external.exists(), 'ambiguous-legacy-queues' if interchange.exists() else 'unsupported-external-legacy-queue',
            {'discovery':discovery,'action':'Stop legacy writers. Convert the external queue losslessly to state/candidates.json (id/payload/status/history), preserve a backup outside discovery locations, then remove the external queue from this offline migration input. Empty external files must also be explicitly resolved.'})
    require((source/'manifest.yaml').is_file() and
            read_document(source/'manifest.yaml',dict,'invalid-legacy-manifest')==legacy.MANIFEST, 'unsupported-legacy-manifest')
    for schema in SCHEMAS.glob('*.json'):
        actual=source/'schema'/schema.name
        require(actual.is_file() and read_document(actual,dict,'invalid-legacy-schema')==read_document(schema,dict,'invalid-legacy-schema'), 'unsupported-legacy-schema')
    files = {}
    for p in sorted(source.rglob('*')):
        if p.is_file():
            require(p.stat().st_size<=16*1024*1024, 'legacy-file-too-large')
            files[p.relative_to(source).as_posix()] = base64.b64encode(p.read_bytes()).decode()
    records = {g:[] for g in GROUPS}
    for group,directory in GROUPS.items():
        require((source/directory).is_dir(), 'incomplete-legacy-record-directories')
        for path in sorted((source/directory).rglob('*')):
            if path.is_file() and path.name!='.gitkeep':
                require(path.suffix=='.json', 'unsupported-legacy-record')
                records[group].append(read_document(path,dict,'invalid-legacy-record'))
    validate_records(records)
    # Actual supplied transaction layout: transactions/<plan-sha>/journal.json.
    transactions = source/'state/population/transactions'
    if transactions.exists():
        for directory in sorted(transactions.iterdir()):
            require(directory.is_dir(), 'unsupported-legacy-transaction-layout')
            journal_path = directory/'journal.json'
            require(journal_path.is_file(), 'incomplete-legacy-journal')
            journal = read_document(journal_path,dict,'invalid-legacy-journal')
            pid = journal.get('plan')
            require(isinstance(pid,str) and pid == 'sha256:'+directory.name, 'incomplete-legacy-journal')
            plan_path = source/'state/population/plans'/(directory.name+'.json')
            require(plan_path.is_file(), 'incomplete-legacy-journal-missing-plan')
            plan = read_document(plan_path,dict,'invalid-legacy-plan')
            for document in (plan,journal):
                sealed = dict(document)
                seal = sealed.pop('fingerprint',None)
                # Preserve the legacy seal encoding exactly (ensure_ascii=True).
                encoded = json.dumps(sealed,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
                require(seal == 'sha256:'+hashlib.sha256(encoded).hexdigest(), 'invalid-legacy-seal')
            require(plan.get('fingerprint')==pid and plan.get('format')=='population-plan-v1', 'unsupported-legacy-plan')
            require(journal.get('state') in ('COMMITTED','ROLLED_BACK'), 'legacy-recovery-required')
    queue_path = source/'state/candidates.json'
    queue = read_document(queue_path,list,'unsupported-legacy-queue') if queue_path.exists() else []
    require(isinstance(queue,list), 'unsupported-legacy-queue')
    for q in queue:
        require(isinstance(q,dict) and set(q)=={'id','payload','status','history'}, 'unsupported-legacy-queue-item')
        require(isinstance(q['id'],str) and q['id'] and q['status'] in ('pending','imported') and isinstance(q['history'],list), 'unsupported-legacy-queue-item')
        candidate(q['payload'])
        if q['status']=='imported':
            for g,items in q['payload']['records'].items():
                require(all(item in records[g] for item in items), 'legacy-imported-candidate-not-canonical')
    require(len({q['id'] for q in queue})==len(queue), 'duplicate-legacy-candidate-id')
    require(len({digest(q['payload']) for q in queue})==len(queue), 'ambiguous-duplicate-legacy-payload')
    return {'discovery':discovery,'version':1,'records':records,'legacy_queue':queue,'source_files':files,
            'source_fingerprint':fingerprint(files)}


def preview(root):
    value = snapshot(root)
    project = Project(root)
    value['project'] = project.identity
    value['semantic_diff'] = {'removed':[], 'modified':[], 'added':[],
                              'preserved_record_counts':{g:len(v) for g,v in value['records'].items()},
                              'preserved_candidate_count':len(value['legacy_queue'])}
    return {'ok':True,'fingerprint':fingerprint(value),'manifest':value}


def apply(root,approval):
    from .coordination import gate
    require(preview(root)['fingerprint'] == approval, 'exact-migration-approval-required')
    with gate(Project(root).root, exclusive=True):return _apply(root,approval)


def _apply(root, approval):
    plan = preview(root)
    require(plan['fingerprint']==approval, 'exact-migration-approval-required')
    project = Project(root)
    if project.db.exists():
        with Store(root).connection() as db:
            row = db.execute("SELECT value FROM metadata WHERE key='migration'").fetchone()
            require(row is not None and loads(row[0])==plan['manifest'], 'migration-target-conflict')
        return {'ok':True,'result':'already-migrated','fingerprint':approval}
    from .runtime_paths import data_entries, ignore_runtime
    require(not data_entries(project.base), 'migration-target-not-empty')
    ignore_runtime(project.runtime)
    project.runtime.temp.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='knowledge-migrate-',dir=project.runtime.temp) as tmp:
        staged = Path(tmp)/'store.sqlite3'
        db = sqlite3.connect(staged)
        try:
            db.execute('PRAGMA synchronous=FULL')
            create_tables(db,project.identity)
            for group,items in plan['manifest']['records'].items():
                for item in items:
                    db.execute('INSERT INTO records VALUES (?,?,?)',(item['id'],group,canonical_json(item)))
                    checkpoint('migration-record-written')
            # Retain the original queue identifiers/status/history in the manifest;
            # the migrated queue retains original IDs and binds imported items to sealed plans.
            for item in plan['manifest']['legacy_queue']:
                payload = item['payload']
                cid = item['id']
                binding = None
                if item['status']=='imported':
                    imported = {'version':1,'project':project.identity,'base':'legacy-migration',
                                'candidates':{cid:payload},'included':[cid],'skipped':[],'blocked':[]}
                    binding = fingerprint(imported)
                    db.execute('INSERT OR IGNORE INTO plans VALUES (?,?,?)',
                               (binding,canonical_json(imported),'ACKNOWLEDGED'))
                existing = db.execute('SELECT payload,status FROM queue WHERE id=?',(cid,)).fetchone()
                require(existing is None, 'ambiguous-duplicate-legacy-candidate')
                db.execute('INSERT INTO queue VALUES (?,?,?,?)',
                           (cid,canonical_json(payload),item['status'],binding))
            db.execute('INSERT INTO metadata VALUES (?,?)',('migration',canonical_json(plan['manifest'])))
            db.execute('INSERT INTO history(payload) VALUES (?)',(canonical_json({'event':'migration','fingerprint':approval,'legacy_queue':plan['manifest']['legacy_queue']}),))
            db.commit()
        finally:
            db.close()
        checkpoint('migration-before-publish')
        require(preview(root)==plan, 'legacy-source-changed')
        safe_tree(project.base)
        require(not project.db.exists(), 'migration-target-conflict')
        publish_directory(Path(tmp),project)
        checkpoint('migration-after-publish')
    return {'ok':True,'result':'migrated','fingerprint':approval,'semantic_diff':plan['manifest']['semantic_diff']}


def restore_legacy(root, destination):
    """Restore the immutable captured legacy input to a NEW empty directory."""
    with Store(root).connection() as db:
        row=db.execute("SELECT value FROM metadata WHERE key='migration'").fetchone()
        require(row is not None,'no-migration-backup')
        manifest=loads(row[0])
    dest=Path(destination)
    require(dest.is_absolute() and '..' not in dest.parts, 'unsafe-restore-destination')
    safe_tree(dest)
    require(not dest.exists(), 'restore-destination-must-be-absent')
    # Validate the whole map before writes.
    decoded={}
    for name,data in manifest['source_files'].items():
        parts=Path(name)
        require(not parts.is_absolute() and '..' not in parts.parts and '\\' not in name, 'unsafe-backup-path')
        decoded[name]=base64.b64decode(data,validate=True)
    dest.mkdir()
    for name,data in decoded.items():
        p=dest/name
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(data)
    return {'ok':True,'restored_files':len(decoded),'destination':str(dest)}
