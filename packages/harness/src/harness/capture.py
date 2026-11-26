"""Durable payload-bound delivery; no canonical Knowledge approval or alternate writer."""
from knowledge.store import Store, GIT_BATCH_LIMIT
from knowledge.discovery import candidate_observe
from knowledge.util import KnowledgeError,digest
from . import runtime as rt
from .runtime import stamp,source_snapshot,DEFAULT_LIMITS


def deliver(journal,run,configuration):
    policy=configuration['capture']
    if policy=='off':run['capture']={'state':'disabled','reason':'explicit task configuration'};return
    try:
        current=source_snapshot(journal.project,{**DEFAULT_LIMITS,**configuration['limits']}['file_bytes'])
        if digest(current)!=run['final_source']:raise KnowledgeError('source-changed-before-capture')
        if not run.get('capture_prepared'):
            initial=run['task']['initial_source']
            changed=sorted(p for p in current.keys() | initial.keys() if initial.get(p)!=current.get(p))
            if not changed:
                run['capture_prepared']=True;run['capture']={'state':'no-candidate','reason':'no changed source; no invented reusable facts'};journal.save(run);return
            preview=candidate_observe(Store(journal.project.root),changed,run['capture_time'])
            # Publish all payloads plus the preparation flag in one Harness transaction.
            coding_actions=[i for i,a in journal.actions(run['id']).items() if a['tool']=='patch' and a['status']=='FINISHED' and a['result']['ok']]
            with journal.db() as db:
                from knowledge.util import canonical_json
                for index,decision in enumerate(preview['decisions']):
                    identifier=digest([run['id'],'capture',index,decision])
                    value={'version':1,'event':run['capture_event'],'run':run['id'],'at':run['capture_time'],'decision':decision,
                           'state':'pending' if decision['decision']=='submit' else decision['decision'],'attempts':0,'coding_actions':coding_actions}
                    db.execute('INSERT OR IGNORE INTO outbox VALUES (?,?,?)',(identifier,run['id'],canonical_json(value)))
                run['capture_prepared']=True;run['capture']={'state':'pending' if preview['decisions'] else 'no-candidate','reason':preview['reason']}
                db.execute('UPDATE runs SET payload=? WHERE id=?',(canonical_json(run),run['id']))
            rt.fault('capture-outbox')
        pending = [(identifier,item) for identifier,item in journal.outbox(run['id']).items() if item['state']=='pending']
        store = Store(journal.project.root)
        for batch in _delivery_batches(pending):
            for identifier,item in batch:
                item['attempts']+=1
                journal.update_outbox(identifier,item)
            payloads = [item['decision']['payload'] for _,item in batch]
            try:
                receipts = [store.submit(payloads[0])] if len(batch)==1 else store.submit_git_batch(payloads)
            except KnowledgeError as error:
                for identifier,item in batch:
                    item['error']=error.code
                    journal.update_outbox(identifier,item)
                raise
            for (identifier,item),receipt in zip(batch,receipts,strict=True):
                rt.fault('capture-after-submit')
                item.pop('error',None)
                item.update(state='delivered',receipt=receipt,delivered_at=stamp())
                journal.update_outbox(identifier,item)
                journal.event(run['id'],'capture-delivered',outbox=identifier,candidate=receipt.get('candidate'))
        items=journal.outbox(run['id'])
        pending=any(i['state']=='pending' for i in items.values());manual=any(i['state']=='manual-review' for i in items.values())
        run['capture']={'state':'pending' if pending else 'manual-review' if manual else 'delivered' if items else 'no-candidate','outbox':list(items)}
    except KnowledgeError as e:
        run['capture']={'state':'pending','error':e.code,**({'details':e.details} if e.details is not None else {})}
    journal.save(run)


def _delivery_batches(pending):
    batch = []
    identity = None
    for row in pending:
        value = row[1]['decision']['payload']
        source = value.get('source') if isinstance(value, dict) else None
        key = (source.get('identity') if isinstance(source, dict) and source.get('kind') in
               ('committed','working-tree-with-hashes','filesystem-no-history') and value.get('version')==2 else None)
        if batch and (key is None or key!=identity or len(batch)==GIT_BATCH_LIMIT):
            yield batch
            batch = []
        if key is None:
            yield [row]
        else:
            identity = key
            batch.append(row)
    if batch:
        yield batch
