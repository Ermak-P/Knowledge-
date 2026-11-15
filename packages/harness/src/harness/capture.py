"""Durable payload-bound delivery; no canonical Knowledge approval or alternate writer."""
from knowledge.store import Store
from knowledge.discovery import candidate_observe
from knowledge.util import KnowledgeError,digest
from . import runtime as rt
from .runtime import stamp,source_snapshot


def deliver(journal,run,configuration):
    policy=configuration['capture']
    if policy=='off':run['capture']={'state':'disabled','reason':'explicit task configuration'};return
    try:
        if not run.get('capture_prepared'):
            current=source_snapshot(journal.project)
            if digest(current)!=run['final_source']:raise KnowledgeError('source-changed-before-capture')
            changed=[p for p,h in current.items() if run['task']['initial_source'].get(p)!=h]
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
        for identifier,item in journal.outbox(run['id']).items():
            if item['state']!='pending':continue
            item['attempts']+=1;journal.update_outbox(identifier,item)
            try:
                receipt=Store(journal.project.root).submit(item['decision']['payload'])
                rt.fault('capture-after-submit')
                item.update(state='delivered',receipt=receipt,delivered_at=stamp());journal.update_outbox(identifier,item)
                journal.event(run['id'],'capture-delivered',outbox=identifier,candidate=receipt.get('candidate'))
            except KnowledgeError as e:
                item['error']=e.code;journal.update_outbox(identifier,item)
                raise
        items=journal.outbox(run['id']).values()
        pending=any(i['state']=='pending' for i in items);manual=any(i['state']=='manual-review' for i in items)
        run['capture']={'state':'pending' if pending else 'manual-review' if manual else 'delivered' if journal.outbox(run['id']) else 'no-candidate','outbox':list(journal.outbox(run['id']))}
    except KnowledgeError as e:
        run['capture']={'state':'pending','error':e.code}
    journal.save(run)
