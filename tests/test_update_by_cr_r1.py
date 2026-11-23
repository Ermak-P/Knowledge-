from copy import deepcopy
from pathlib import Path
import json,shutil,subprocess,sys,tempfile,unittest
from knowledge.cr_workflow import Workflow
from knowledge import cr_install,lifecycle as life
from knowledge.util import KnowledgeError
from cr_fixtures import project,decisions,ready,git,item
from fixtures import addition


class UpdateByCRReviewR1(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root,self.snapshot=project(self.tmp.name);self.w=Workflow(self.root)
    def tearDown(self):self.tmp.cleanup()
    def commit(self,state):
        plan=self.w.prepare(state['session'],state['revision']);return self.w.apply(plan['session'],plan['proposal']['plan'],plan['revision'])
    def sourced(self,snapshot,items=None,host=None):
        state=self.w.start(cr=snapshot['cr']['url'],pr=snapshot['pr']['url'],host_session=host)
        state=self.w.sources(state['session'],snapshot,state['revision']);items=deepcopy(items or decisions(snapshot))
        for value in items:value['reason']={'text':'Preserve the reviewed budget and public contract.','refs':['pr:description']}
        return self.w.analyze(state['session'],items,state['revision'])
    def successor(self,status='open',number=9):
        branch=git(self.root,'branch','--show-current');git(self.root,'checkout','-b','proposed-six')
        p=self.root/'Retry.cs';p.write_text(p.read_text().replace('= 4;','= 6;'));git(self.root,'add','.');git(self.root,'commit','-m','proposed six')
        head=git(self.root,'rev-parse','HEAD');git(self.root,'checkout',branch)
        snap=deepcopy(self.snapshot);snap['pr'].update(url=f'https://github.com/synthetic/project/pull/{number}',id=str(number),base=self.snapshot['target']['commit'],head=head,merge=None,status=status)
        return snap
    def proposed_item(self,snapshot):
        value=item(snapshot,'retry-limit','Prefer six total transient operation attempts','Retry.cs',terms=['retry','transient','attempts']);value['anchors'][0]['revision']=snapshot['pr']['head'];return value

    def test_open_closed_successors_preserve_target_then_merge_updates_same_history(self):
        first=self.commit(self.sourced(self.snapshot));cid=first['receipt']['records'][0]['id'];before=self.w.store.lookup('claims',cid)
        proposal=self.successor();b=self.commit(self.sourced(proposal,[self.proposed_item(proposal)]));bid=b['receipt']['records'][0]['id']
        closed=deepcopy(proposal);closed['pr'].update(status='closed',url='https://github.com/synthetic/project/pull/10',id='10')
        c=self.commit(self.sourced(closed,[self.proposed_item(closed)]));self.assertNotEqual(bid,c['receipt']['records'][0]['id'])
        self.assertNotEqual(cid,bid);self.assertEqual(before,self.w.store.lookup('claims',cid))
        self.assertEqual(git(self.root,'rev-parse','HEAD'),self.snapshot['target']['commit']);self.assertIn('= 4;', (self.root/'Retry.cs').read_text())
        normal=self.w.store.context('transient retry attempts',max_items=20);self.assertIn(cid,[r['id'] for r in normal['claims']]);self.assertNotIn(bid,[r['id'] for r in normal['claims']])
        optional=self.w.store.context('transient retry attempts',max_items=20,include_unconfirmed=True);branch=next(r for r in optional['claims'] if r['id']==bid);self.assertIn('not target behavior',branch['statement'])
        git(self.root,'merge','--ff-only',proposal['pr']['head']);merged=deepcopy(proposal);merged['pr'].update(status='merged',merge=proposal['pr']['head']);merged['target']['commit']=proposal['pr']['head']
        value=self.proposed_item(merged);saved=self.commit(self.sourced(merged,[value]));self.assertEqual(saved['receipt']['records'][0]['id'],cid)
        updated=self.w.store.lookup('claims',cid);self.assertEqual(updated['revision']['revision'],2);self.assertEqual(updated['record']['status'],'CONFIRMED');self.assertIn('six total',updated['record']['statement'])
        self.assertEqual(len(life.history(self.w.store,cid)['revisions']),2);self.assertEqual(self.w.store.lookup('claims',bid)['revision']['revision'],1)

    def test_explicit_existing_id_and_retirement_cannot_bypass_proposal_scope(self):
        first=self.commit(self.sourced(self.snapshot));cid=first['receipt']['records'][0]['id'];proposal=self.successor();before=self.w.store.export()['records']
        for status in ('open','closed'):
            for change in ('upsert','retire'):
                with self.subTest(status=status,change=change):
                    snap=deepcopy(proposal);snap['pr']['status']=status;value=self.proposed_item(snap);value.update(existing_id=cid,change=change)
                    state=self.sourced(snap,[value]);queue=self.w.store.status()['queue']
                    with self.assertRaisesRegex(KnowledgeError,'ucr-unmerged-target-mutation-refused'):self.w.prepare(state['session'],state['revision'])
                    self.assertEqual(self.w.store.export()['records'],before);self.assertEqual(self.w.store.status()['queue'],queue)

    def test_merged_retirement_still_uses_supported_revision_history(self):
        first=self.commit(self.sourced(self.snapshot));cid=first['receipt']['records'][0]['id'];snap=self.successor();git(self.root,'merge','--ff-only',snap['pr']['head'])
        snap['pr'].update(status='merged',merge=snap['pr']['head']);snap['target']['commit']=snap['pr']['head'];value=self.proposed_item(snap);value.update(existing_id=cid,change='retire')
        saved=self.commit(self.sourced(snap,[value]));self.assertEqual(saved['receipt']['records'][0]['lifecycle'],'retired');self.assertEqual(saved['receipt']['records'][0]['revision'],2)
        self.assertNotIn(cid,[r['id'] for r in self.w.store.context('transient retry attempts',max_items=20)['claims']])

    def refreshed(self,head_change=False):
        state=ready(self.w,self.snapshot,decisions(self.snapshot));old=self.w.prepare(state['session'],state['revision']);snap=deepcopy(self.snapshot)
        if head_change:
            p=self.root/'Retry.cs';p.write_text(p.read_text().replace('= 4;','= 5;'));git(self.root,'add','.');git(self.root,'commit','-m','updated target')
            head=git(self.root,'rev-parse','HEAD');snap['pr'].update(head=head,merge=head);snap['target']['commit']=head
        else:snap['pr']['discussion'].append(dict(id='refresh',text='New review comment',reference=snap['pr']['url']))
        self.w.sources(state['session'],snap,old['revision']);items=decisions(snap)
        if head_change:items[0]['statement']='Prefer five total transient operation attempts'
        return old,ready(self.w,snap,items)

    def test_refresh_owns_old_candidate_and_recovers_hard_crash_during_disposition(self):
        old,state=self.refreshed();sid=state['session']
        child=subprocess.run([sys.executable,'-I',str(Path(__file__).with_name('cr_crash_worker.py')),str(self.root),sid,'prepare','owned-candidate-deferred'],capture_output=True,text=True)
        self.assertEqual(child.returncode,83,child.stdout+child.stderr);plan=Workflow(self.root).resume(sid);self.assertEqual(plan['state'],'awaiting_approval')
        self.assertNotEqual(old['proposal']['plan'],plan['proposal']['plan'])
        with self.assertRaisesRegex(KnowledgeError,'exact-approval-required'):self.w.apply(sid,old['proposal']['plan'],plan['revision'])
        saved=self.w.apply(sid,plan['proposal']['plan'],plan['revision']);self.assertIn(saved['state'],('saved','partial_saved'))
        queue={r['id']:r['status'] for r in self.w.store.status()['queue']};self.assertEqual(queue[old['proposal']['candidate']],'deferred');self.assertEqual(queue[plan['proposal']['candidate']],'imported')
        self.assertTrue(any(h.get('proposal',{}).get('candidate')==old['proposal']['candidate'] for h in self.w.get(sid)['history'] if h.get('proposal')))

    def test_head_target_refresh_prepares_and_applies_without_manual_queue_repair(self):
        old,state=self.refreshed(True);plan=self.w.prepare(state['session'],state['revision']);saved=self.w.apply(state['session'],plan['proposal']['plan'],plan['revision'])
        self.assertTrue(all(r['revision']==1 for r in saved['receipt']['records']));self.assertIn('five total',' '.join(r['statement'] for r in self.w.store.context('transient retry attempts')['claims']))
        self.assertEqual(next(r for r in self.w.store.status()['queue'] if r['id']==old['proposal']['candidate'])['status'],'deferred')

    def test_refresh_never_disposes_unrelated_pending_candidate(self):
        old,state=self.refreshed();other=self.w.store.submit(addition('unrelated','An independent review candidate.'))['candidate'];before=self.w.store.status()['queue']
        with self.assertRaisesRegex(KnowledgeError,'ucr-unrelated-pending-candidates') as error:self.w.prepare(state['session'],state['revision'])
        self.assertEqual(error.exception.details['candidates'],[other]);self.assertEqual(before,self.w.store.status()['queue'])
        life.dispose(self.w.store,other,'deferred','Explicit independent test-user disposition');saved=self.commit(state);self.assertTrue(saved['receipt']['records'])

    def test_refresh_roundtrip_does_not_reuse_already_deferred_candidate(self):
        original,state=self.refreshed();middle=self.w.prepare(state['session'],state['revision'])
        self.w.sources(state['session'],self.snapshot,middle['revision']);state=ready(self.w,self.snapshot,decisions(self.snapshot));replacement=self.w.prepare(state['session'],state['revision'])
        self.assertNotEqual(replacement['proposal']['candidate'],original['proposal']['candidate'])
        saved=self.w.apply(state['session'],replacement['proposal']['plan'],replacement['revision']);self.assertTrue(saved['receipt']['records'])
        queue={r['id']:r['status'] for r in self.w.store.status()['queue']};self.assertEqual(queue[original['proposal']['candidate']],'deferred');self.assertEqual(queue[middle['proposal']['candidate']],'deferred')

    def member_change(self,changed=False,shifted=False):
        p=self.root/'Retry.cs';p.write_text('public static class Retry {\n  public const int MaxAttempts = 4;\n  public static string PublicName() => "retry";\n}\n');git(self.root,'add','.');git(self.root,'commit','-m','member baseline');base=git(self.root,'rev-parse','HEAD')
        text=p.read_text().replace('= 4;','= 6;')
        if changed:text=text.replace('=> "retry"','=> "changed"')
        if shifted:text=text.replace('  public const','  // Inserted context\n  public const')
        p.write_text(text);git(self.root,'add','.');git(self.root,'commit','-m','member implementation');head=git(self.root,'rev-parse','HEAD')
        snap=deepcopy(self.snapshot);snap['pr'].update(base=base,head=head,merge=head);snap['target']['commit']=head
        value=item(snap,'public-name','Preserve PublicName signature and return value','Retry.cs',category='nonchange');value['anchors'][0].update(start=4 if shifted else 3,end=4 if shifted else 3,role='contract')
        return snap,value

    def test_unchanged_member_in_modified_file_is_saved_and_changed_member_refused(self):
        snap,value=self.member_change();saved=self.commit(self.sourced(snap,[value]));self.assertTrue(saved['receipt']['records'])
        changed=deepcopy(snap);p=self.root/'Retry.cs';p.write_text(p.read_text().replace('=> "retry"','=> "changed"'));git(self.root,'add','.');git(self.root,'commit','-m','changed contract');head=git(self.root,'rev-parse','HEAD')
        changed['pr'].update(head=head,merge=head);changed['target']['commit']=head;value['anchors'][0]['revision']=head
        with self.assertRaisesRegex(KnowledgeError,'ucr-nonchange-not-established'):self.sourced(changed,[value])

    def test_explicit_base_head_ranges_support_shifted_contract_and_reject_wrong_pin(self):
        snap,value=self.member_change(shifted=True);a=value['anchors'][0];a['comparison']={side:dict(path='Retry.cs',revision=snap['pr'][side],start=line,end=line) for side,line in [('base',3),('head',4)]}
        state=self.sourced(snap,[value]);mapped=self.w.get(state['session'])['map'][0]['anchors'][0];self.assertEqual(mapped['comparison']['base']['excerpt'],mapped['excerpt']);saved=self.commit(state);self.assertTrue(saved['receipt']['records'])
        bad=deepcopy(value);bad['anchors'][0]['comparison']['base']['revision']=snap['pr']['head']
        with self.assertRaisesRegex(KnowledgeError,'ucr-invalid-nonchange-comparison'):self.sourced(snap,[bad])

    def test_same_chat_binding_is_unique_with_history_resume_and_active_conflict(self):
        first=self.commit(self.sourced(self.snapshot,host='same-chat'));sid=first['session'];snap=deepcopy(self.snapshot);snap['cr'].update(url='https://github.com/synthetic/project/issues/10',id='10',title='Followup dispatch budget');snap['pr'].update(url='https://github.com/synthetic/project/pull/11',id='11',cr_links=[snap['cr']['url']])
        p=self.root/'Checks.cs';p.write_text(p.read_text()+'// Later local work\n');self.assertEqual(self.w.resume(sid)['state'],'stale')
        second=self.w.start(cr=snap['cr']['url'],pr=snap['pr']['url'],host_session='same-chat');self.assertIsNone(self.w.get(sid)['host_session']);self.assertEqual(self.w.get(sid)['receipt'],first['receipt'])
        self.assertEqual(Workflow(self.root).start(host_session='same-chat')['session'],second['session']);self.assertEqual(self.w.start(session=second['session'],host_session='same-chat')['session'],second['session'])
        # Repair the completed+active binding combination written by pre-R1 builds.
        previous=self.w.get(sid);self.w._change(sid,previous['revision'],lambda s:s.update(host_session='same-chat'))
        self.assertEqual(self.w.start(host_session='same-chat')['session'],second['session']);self.assertIsNone(self.w.get(sid)['host_session'])
        state=self.sourced(snap,host='same-chat')
        with self.assertRaisesRegex(KnowledgeError,'ucr-host-already-has-active-workflow'):self.w.start(cr='https://github.com/synthetic/project/issues/12',pr='https://github.com/synthetic/project/pull/13',host_session='same-chat')
        self.assertEqual(self.w.get(sid)['receipt'],first['receipt']);saved=self.commit(state);self.assertTrue(saved['receipt']['records'])
        self.assertEqual(self.w.start(session=sid,host_session='history-chat')['receipt'],first['receipt'])

    def test_native_hook_sequential_reviews_survive_plugin_restart(self):
        cr_install.install(self.root,python=sys.executable,language='ru');first=self.commit(self.sourced(self.snapshot,host='same-native-chat'))
        import knowledge
        asset=Path(knowledge.__file__).parent/'host/cr_opencode.mjs'
        result=subprocess.run([shutil.which('node'),str(Path(__file__).with_name('cr_host_sequence.mjs')),str(asset),str(self.root),first['session']],capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr);self.assertEqual(self.w.get(first['session'])['receipt'],first['receipt'])
        self.assertTrue(json.loads(result.stdout)['restart_resume'])


if __name__=='__main__':unittest.main()
