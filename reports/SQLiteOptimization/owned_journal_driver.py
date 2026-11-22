"""Qualified common sampler with complete journal write fixtures.

Public methods and validation are untouched. Written actions/outbox include the
normal fields needed by subsequent status/capture reads, with owned delivery
events and run capture state; no execution effect is performed.
"""
from copy import deepcopy
import importlib.util
from pathlib import Path

common=Path(__file__).resolve().parents[2]/'scripts/sqlite_benchmark.py'
spec=importlib.util.spec_from_file_location('common_sqlite_sampler',common);base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
original=base.operation


def operation(root,name,info):
    if name not in ('journal-writes','outbox-write'):return original(root,name,info)
    from harness.runtime import Journal
    from knowledge.util import digest
    journal=Journal(root)
    if name=='journal-writes':
        def written():
            journal.event('selected','write')
            journal.action('selected','new',{'tool':'read','status':'FINISHED','at':0,'finished':1,'role':'Main','agent':'main','result':{'ok':True}})
            journal.cancel('selected');return journal.cancelled('selected')
        return written
    value=deepcopy(next(iter(journal.outbox('selected').values())))
    identifier=digest(['selected','capture',3,value['decision']]);run=journal.load('selected')
    pending=deepcopy(value);pending.update(state='pending',attempts=0);pending.pop('receipt');pending.pop('delivered_at')
    value['receipt']['result']='duplicate'
    def captured():
        journal.put_outbox(identifier,'selected',deepcopy(pending));journal.update_outbox(identifier,deepcopy(value))
        journal.event('selected','capture-delivered',outbox=identifier,candidate=value['receipt']['candidate'])
        updated=deepcopy(run);updated['capture']['outbox'].append(identifier);journal.save(updated)
        return journal.outbox('selected')
    return captured


if __name__=='__main__':
    base.operation=operation
    base.main()
