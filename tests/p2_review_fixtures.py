"""P2 review reproductions. Only HTTP decisions are scripted; effects are production."""
from pathlib import Path
import hashlib,json,sys,threading,os,shutil
from unittest.mock import patch
from knowledge import lifecycle as life,discovery as disc
from knowledge.store import Store
from knowledge.util import canonical_json,digest
from harness import engine,runtime
from p2_fixtures import project,configuration,task,http_provider,FixtureProvider


def approve(store):
    plan=store.prepare();assert plan['ok'],plan
    store.apply(plan['fingerprint'],plan['fingerprint']);store.acknowledge(plan['fingerprint'])
    return plan


def expected_test(root,expected):
    (root/'test_feature.py').write_text('import unittest\nfrom pathlib import Path\nclass Behavior(unittest.TestCase):\n def test_expected_source(self):\n  self.assertEqual(Path("Feature.cs").read_text(),'+repr(expected)+')\nif __name__=="__main__":unittest.main()\n')


def session(root,expected):
    expected_test(root,expected) # Independently authored user fixture setup before run.
    provider=FixtureProvider(desired=expected)
    with http_provider(provider) as endpoint:
        runtime.configure(root,configuration(endpoint),True);outcome=engine.start(root,task())
    report=engine.status(root,outcome['run_id'])
    assert {r['id'] for r in report['run']['requests']}==set(provider.transport_ids)
    return outcome,report


def learning(root):
    first='public class ImprovedFeature {}\n';project(root,first);store=Store(root);stages=[];identifier=None
    sources=[first,'public class ImprovedFeature : System.Object {}\n','public class ImprovedFeature : System.MarshalByRefObject {}\n']
    for index,expected in enumerate(sources):
        before=store.export() if store.path.exists() else None
        outcome,report=session(root,expected);assert outcome['ok'],outcome
        queue=[q for q in store.export()['queue'] if q['status']=='pending'];assert len(queue)==1
        candidate=queue[0];ops=candidate['payload']['operations'];claim=next(o for o in ops if o['kind']=='claims')
        identifier=identifier or claim['id'];assert claim['id']==identifier and claim['expected']==index
        assert claim['action']==('add' if index==0 else 'update')
        evidence=next(o for o in ops if o['kind']=='evidence')['payload']
        assert evidence['content_hash']=='sha256:'+hashlib.sha256((root/'Feature.cs').read_bytes()).hexdigest()
        if before:
            assert store.export()['records']==before['records']
            assert len(life.history(store,identifier)['revisions'])==index
        else:assert not store.export()['records']['claims']
        plan=approve(store);history=life.history(store,identifier);assert len(history['revisions'])==index+1
        with store.connection() as db:assert db.execute('SELECT count(*) FROM scans').fetchone()[0]==0
        stages.append(dict(expected=expected,report=report,candidate=candidate,approval=plan,history=history))
    # Deliberate user removal and exact retirement approval are setup, not auto-retirement.
    (root/'Feature.cs').write_text('public class RemovedFeature {}\n')
    store.submit(life.batch([life.op('retire','claims',identifier,3)],'Explicit fixture retirement'))
    retirement=approve(store);assert life.history(store,identifier)['revisions'][-1]['lifecycle']=='retired'
    before=store.export()['records'];outcome,report=session(root,sources[-1]);assert outcome['ok'],outcome
    candidate=next(q for q in store.export()['queue'] if q['status']=='pending')
    op=next(o for o in candidate['payload']['operations'] if o['kind']=='claims')
    assert op['id']==identifier and op['action']=='reactivate' and op['expected']==4
    assert store.export()['records']==before and life.history(store,identifier)['revisions'][-1]['lifecycle']=='retired'
    plan=approve(store);history=life.history(store,identifier);assert history['revisions'][-1]['revision']==5 and history['revisions'][-1]['lifecycle']=='active'
    ownership=disc.capture_observation_receipts(store);assert ownership['positive_observations_only'] and len(ownership['receipts'])==4
    assert {r['candidate'] for r in ownership['receipts']}=={s['candidate']['id'] for s in stages}|{candidate['id']}
    return dict(ownership_receipts=ownership,stages=stages,retirement=retirement,returning=dict(report=report,candidate=candidate,approval=plan,history=history),no_completed_scans=True)


def manual_review(root,legacy=False):
    first='public class ImprovedFeature {}\n';project(root,first)
    if legacy:
        runtime.configure(root,configuration('http://127.0.0.1:1/v1/chat/completions'),True)
        (root/'Feature.cs').write_text(first)
        preview=disc.candidate_preview(Store(root),['Feature.cs'])
        for decision in preview['decisions']:
            if decision['decision']=='submit':Store(root).submit(decision['payload'])
    else:
        outcome,_=session(root,first);assert outcome['ok']
    store=Store(root);approve(store);claim=store.export()['records']['claims'][0]
    if not legacy:
        claim=dict(claim,statement=claim['statement']+' Reviewed historical meaning.')
        store.submit(life.batch([life.op('update','claims',claim['id'],1,claim)],'Explicitly reviewed meaning'))
        approve(store)
    before=store.export()['records'];outcome,report=session(root,'public class ImprovedFeature : System.Object {}\n')
    assert outcome['execution']=='passed' and outcome['status']=='awaiting-capture' and outcome['capture']['state']=='manual-review',outcome
    assert store.export()['records']==before and not any(q['status']=='pending' for q in store.export()['queue'])
    assert any(i['decision'].get('reason') for i in report['outbox'].values() if i['state']=='manual-review')
    return dict(legacy_without_receipt=legacy,outcome=outcome,report=report,canonical_preserved=True)


def verifier(root,absolute=True,executable=False,exception=False):
    root=project(root);path=root/'verify.py'
    original='raise RuntimeError("real verifier rejects this task")\n'
    if executable:original='#!'+sys.executable+'\n'+original
    path.write_text(original);path.chmod(0o700)
    expected='print("Ran 1 test in 0.001s\\n\\nOK")\n'
    if executable:expected='#!'+sys.executable+'\n'+expected
    scenario=FixtureProvider(path='verify.py',desired=expected)
    with http_provider(scenario) as endpoint:
        c=configuration(endpoint);entry=str(path) if absolute else 'verify.py'
        c['recipes']['test']['argv']=[str(path)] if executable else [sys.executable,entry]
        if executable and os.name=='nt':
            # Windows does not execute a POSIX shebang. Use a genuine project PE
            # interpreter and retain the same protected verifier script/content.
            native=root/'project-verifier.exe';shutil.copyfile(sys._base_executable,native)
            c['recipes']['test']['argv']=[str(native),entry]
            c['recipes']['test']['env']={'PATH':str(Path(sys._base_executable).parent)+os.pathsep+os.environ.get('PATH','')}

        runtime.configure(root,c,True);t=task();t['writable']=['*']
        if exception:t['existing_test_edits']=['verify.py']
        outcome=engine.start(root,t)
    report=engine.status(root,outcome['run_id']);recipes=[a for a in report['actions'].values() if a['tool']=='recipe' and a['args']['name']=='test'];assert recipes
    if exception and not executable:
        assert outcome['ok'],outcome
        assert any(e['kind']=='explicit-test-edit-authorized' and e['paths']==['verify.py'] for e in report['events'])
    else:
        assert not outcome['ok'] and path.read_text()==original
        assert 'verify.py' in report['run']['protected_paths']
        assert any(a.get('result',{}).get('error')=='recipe-input-edit-denied' for a in report['actions'].values())
        assert all(not a['result']['ok'] and a['result']['returncode']!=0 for a in recipes)
    return dict(absolute=absolute,project_executable=executable,explicit_exception=exception,outcome=outcome,report=report,original_preserved=path.read_text()==original)


def overlap(root,window='read-only',configuration_change=False):
    root=project(root);scenario=FixtureProvider()
    with http_provider(scenario) as endpoint:
        c=configuration(endpoint);runtime.configure(root,c,True)
        if window=='read-only':
            # Expose start's durable normal initial state without executing it.
            with patch.object(engine,'resume',return_value={'created':True}):engine.start(root,task(kind='read-only'))
            run_id=runtime.Journal(root).runs()[0]['id']
        else:
            # Real killed worker: pending edit/capture, same production HTTP server.
            from test_p2 import RecoveryTests
            phase='edit-file-written' if window=='coding' else 'capture-outbox'
            child=RecoveryTests().child_start(root,phase);assert child.wait(timeout=20)==73
            run_id=runtime.Journal(root).runs()[0]['id']
        before=engine.status(root,run_id);entered=threading.Event();release=threading.Event();box={}
        original_enter=runtime.Lease.__enter__
        def delayed(lease):
            if threading.current_thread().name=='stale-resume-A':
                entered.set();assert release.wait(15),'pre-lease scheduling timeout'
            return original_enter(lease)
        def caller():
            try:box['outcome']=engine.resume(root,run_id)
            except BaseException as error:box['error']=repr(error)
        with patch.object(runtime.Lease,'__enter__',delayed):
            a=threading.Thread(target=caller,name='stale-resume-A');a.start();assert entered.wait(5)
            if configuration_change:
                changed=dict(c,capture='off');runtime.configure(root,changed)
                b=engine.status(root,run_id)
            else:
                outcome_b=engine.resume(root,run_id);assert outcome_b['ok'],outcome_b
                b=engine.status(root,run_id)
            release.set();a.join(timeout=10);assert not a.is_alive() and 'error' not in box,box
        after=engine.status(root,run_id)
        if configuration_change:
            assert box['outcome']['error']=='configuration-changed-revalidation-required',box
            assert after['run']['requests']==before['run']['requests']
            assert after['outbox']==before['outbox'] and not Store(root).status()['queue']
        else:
            assert box['outcome']['ok'],box
            assert after==b,'terminal state/events/actions/outbox/accounting regressed'
            assert [r['id'] for r in after['run']['requests']]==scenario.transport_ids
            assert len(after['run']['requests'])==len(scenario.requests)
            assert after['metrics']['reported_tokens']==18*len(scenario.requests)
        return dict(window=window,config_changed_during_wait=configuration_change,before=before,completed_by_b=b,after=after,actual_transport_ids=scenario.transport_ids,actual_http_requests=len(scenario.requests),caller_a=box)


def update_retry(root,disposition=None):
    first='public class ImprovedFeature {}\n';second='public class ImprovedFeature : System.Object {}\n'
    root=project(root,first);outcome,_=session(root,first);assert outcome['ok'];store=Store(root);approve(store)
    if disposition:
        outcome,report=session(root,second);assert outcome['ok'];candidate=next(q for q in store.export()['queue'] if q['status']=='pending')
        life.dispose(store,candidate['id'],disposition,'Explicit fixture disposition on unchanged update')
        (root/'Feature.cs').write_text(first)
        outcome,report=session(root,second);assert outcome['ok']
        assert len(store.export()['queue'])==2 and next(q for q in store.export()['queue'] if q['id']==candidate['id'])['status']==disposition
        assert any(i['state']=='existing' and i['decision']['status']==disposition for i in report['outbox'].values())
        return dict(disposition=disposition,report=report,queue=store.export()['queue'])
    expected_test(root,second);provider=FixtureProvider(desired=second)
    from test_p2 import RecoveryTests
    with http_provider(provider) as endpoint:
        runtime.configure(root,configuration(endpoint),True)
        child=RecoveryTests().child_start(root,'capture-after-submit');assert child.wait(timeout=20)==73
        run=next(r for r in runtime.Journal(root).runs() if r['status']=='running')
        before=store.export()['records'];mtime=(root/'Feature.cs').stat().st_mtime_ns
        outcome=engine.resume(root,run['id']);assert outcome['ok'] and (root/'Feature.cs').stat().st_mtime_ns==mtime
    assert store.export()['records']==before and len(store.export()['queue'])==2
    candidate=next(q for q in store.export()['queue'] if q['status']=='pending');op=next(o for o in candidate['payload']['operations'] if o['kind']=='claims')
    assert op['action']=='update' and op['expected']==1
    approve(store);third='public class ImprovedFeature : System.MarshalByRefObject {}\n'
    outcome,report=session(root,third);assert outcome['ok'];new=next(q for q in store.export()['queue'] if q['status']=='pending');assert next(o for o in new['payload']['operations'] if o['kind']=='claims')['expected']==2
    return dict(crash_exit=73,accepted_update=candidate,following_candidate=new,following_report=report,canonical_before_reapproval=before)
