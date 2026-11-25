"""Nonempty accepted-format state from real APIs, HTTP and killed subprocesses."""
import json,sys,subprocess
from pathlib import Path
from p2_fixtures import project,configuration,task,http_provider,FixtureProvider
from p2_review_fixtures import expected_test,approve
from fixtures import legacy_fixture,addition
from knowledge import migration,lifecycle as life,discovery as disc
from knowledge.store import Store
from harness.runtime import configure,Journal
from harness.engine import start

def killed(root,phase):
    code='''from harness import runtime,engine
from knowledge.util import loads
import os
def die(p):
 if p==PHASE:os._exit(73)
runtime.fault=die
engine.start(ROOT,loads(TASK))
'''.replace('PHASE',repr(phase)).replace('ROOT',repr(str(root))).replace('TASK',repr(json.dumps(task())))
    p=subprocess.run([sys.executable,'-c',code],timeout=30);assert p.returncode==73,p.returncode

def rich(root):
    root=project(root);legacy_fixture(root);migration.apply(root,migration.preview(root)['fingerprint'])
    store=Store(root);life.upgrade(store,life.upgrade_preview(store)['fingerprint'])
    with http_provider(FixtureProvider()) as endpoint:
        configure(root,configuration(endpoint),True);run=start(root,task());assert run['ok'],run
    approve(store)
    with http_provider(FixtureProvider()) as endpoint:
        configure(root,configuration(endpoint),True);killed(root,'provider-intent')
    desired='public class LaterFeature {}\n';expected_test(root,desired)
    with http_provider(FixtureProvider(desired=desired)) as endpoint:
        configure(root,configuration(endpoint),True);killed(root,'capture-after-submit')
    # Approval is explicit fixture setup. Preserve the accepted-but-unacknowledged
    # Harness outbox while adding the canonical commit/ack split independently.
    approve(store)
    for disposition in ('rejected','deferred'):
        result=store.submit(addition('fixture.'+disposition,'Synthetic '+disposition+' pending meaning.'))
        life.dispose(store,result['candidate'],disposition,'Fixture human disposition')
    store.submit(addition('fixture.prepared','Synthetic prepared operation.'));prepared=store.prepare()
    store.submit(addition('fixture.commit','Synthetic committed without acknowledgement.'));commit=store.prepare();assert commit['ok'];store.apply(commit['fingerprint'],commit['fingerprint'])
    store.submit(addition('fixture.pending','Synthetic new pending operation.'))
    return dict(prepared=prepared['fingerprint'],committed=commit['fingerprint'],snapshot=logical(root))

def logical(root):
    store=Store(root);j=Journal(root)
    knowledge=store.export()
    # P3 predates this optional read-side field; None represents no migration
    # history, not a change to persisted state. Preserve every nonempty archive
    # and every other export field in the same-root upgrade/restore comparison.
    if knowledge.get('identity_history') is None:knowledge.pop('identity_history',None)
    return dict(knowledge=knowledge,observations=disc.capture_observation_receipts(store),runs=j.runs(),events={r['id']:j.events(r['id']) for r in j.runs()},actions={r['id']:j.actions(r['id']) for r in j.runs()},outbox={r['id']:j.outbox(r['id']) for r in j.runs()})
