"""Git snapshots, review recovery and public-command extraction effects."""
import copy,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from knowledge import discovery as disc,lifecycle as life
from knowledge.store import Store
from knowledge.util import KnowledgeError,digest,canonical_json
from test_p1 import git,upgraded
from p2_fixtures import project,configuration,http_provider,FixtureProvider,task
from harness.runtime import configure
from harness.engine import start
from p2_review_fixtures import expected_test

class KnowledgeIntegration(unittest.TestCase):
 def checkout(self,root,policy='lf'):
  root=Path(root);root.mkdir(parents=True,exist_ok=True);(root/'Project.csproj').write_bytes(b'<Project Sdk="Microsoft.NET.Sdk">\n<PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup>\n</Project>\n');(root/'EM.cs').write_bytes(b'public class EM {}\n');(root/'.gitattributes').write_bytes(('*.cs text eol='+policy+'\n').encode());(root/'.gitignore').write_bytes(b'.knowledge/\n.harness/\n.knowledge-control.lock\n')
  git(root,'init');git(root,'config','core.autocrlf','false');git(root,'config','user.name','Synthetic');git(root,'config','user.email','synthetic@example.invalid');git(root,'add','.');git(root,'commit','-m','Initial source');(root/'EM.cs').unlink();git(root,'checkout','HEAD','--','EM.cs');self.assertEqual((root/'EM.cs').read_bytes(),b'public class EM {}\r\n' if policy=='crlf' else b'public class EM {}\n');return root
 def approve(self,s):
  p=s.prepare();self.assertTrue(p['ok'],p);s.apply(p['fingerprint'],p['fingerprint']);s.acknowledge(p['fingerprint']);return p
 def test_lf_and_crlf_clean_checkout_retirement_with_real_commit_ranges(self):
  for policy in ('lf','crlf'):
   with self.subTest(policy=policy),tempfile.TemporaryDirectory() as tmp:
    root=self.checkout(tmp,policy);s=upgraded(root);initial=disc.scan(s,max_files=100);self.assertEqual(initial['snapshot']['snapshot_kind'],'committed');self.assertFalse(initial['snapshot']['dirty']);self.approve(s);fact=next(o for o in initial['observations'] if o['subject']=='EM');base=git(root,'rev-parse','HEAD');self.assertNotEqual(fact['content_hash'],'sha256:'+__import__('hashlib').sha256(subprocess.check_output(['git','-C',str(root),'show','HEAD:EM.cs'])).hexdigest()) if policy=='crlf' else None
    (root/'EM.cs').write_bytes((root/'EM.cs').read_bytes()+b'// unstaged\n');self.assertEqual(disc.inventory(root)['snapshot_kind'],'working-tree-with-hashes');git(root,'add','EM.cs');self.assertTrue(disc.inventory(root)['dirty']);git(root,'reset','--hard','HEAD')
    (root/'EM.cs').unlink();git(root,'add','-u');git(root,'commit','-m','Remove EM');after=disc.scan(s,max_files=100,base=base,head='HEAD');self.assertFalse(after['snapshot']['dirty']);review=disc.reconcile(s,after['id']);self.assertIsNotNone(review['proposal'],review);s.submit(review['proposal']);self.approve(s);history=life.history(s,fact['id'])['revisions'];self.assertEqual([i['lifecycle'] for i in history],['active','retired'])
 def test_crlf_prior_release_raw_evidence_can_prove_retirement(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=self.checkout(tmp,'crlf');s=upgraded(root);initial=disc.scan(s,max_files=100);self.approve(s);base=git(root,'rev-parse','HEAD')
   # Equivalent prior-release persisted scan: old snapshots have raw working hashes
   # and HEAD blob identity, without the additive normalized blob proof fields.
   with s.connection(True) as db:
    old=copy.deepcopy(initial)
    for entry in old['snapshot']['files'].values():
     for key in ('git_blob','working_blob'):entry.pop(key,None)
    db.execute('UPDATE scans SET payload=? WHERE id=?',(canonical_json(old),initial['id']))
   (root/'EM.cs').unlink();git(root,'add','-u');git(root,'commit','-m','Remove EM');after=disc.scan(s,max_files=100,base=base,head='HEAD');self.assertIsNotNone(disc.reconcile(s,after['id'])['proposal'])
 def test_partial_or_referenced_removal_still_refuses_retirement(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=self.checkout(tmp,'crlf');s=upgraded(root);initial=disc.scan(s,max_files=100);self.approve(s);base=git(root,'rev-parse','HEAD');(root/'EM.cs').unlink();(root/'Consumer.cs').write_bytes(b'public class Consumer { EM field; }\r\n');git(root,'add','.');git(root,'commit','-m','Referenced removal');partial=disc.scan(s,max_files=1,base=base,head='HEAD');self.assertFalse(partial['complete']);self.assertIsNone(disc.reconcile(s,partial['id'])['proposal']);done=disc.scan(s,partial['id'],100);self.assertIsNone(disc.reconcile(s,done['id'])['proposal'])
 def public_init(self,root,tmp,scan=None,budget=1):
  count=Path(tmp)/'count.json';argv=[sys.executable,'-I','-X','utf8','-B',str(Path(__file__).with_name('integrated_knowledge_cli.py')),'--count',str(count),'--','knowledge-init','--root',str(root),'--max-files',str(budget)]
  if scan:argv+=['--scan-id',scan]
  p=subprocess.run(argv,capture_output=True,timeout=45);self.assertEqual(p.returncode,0,p.stdout+p.stderr);calls=json.loads(count.read_text());self.assertLessEqual(len(calls),budget,calls);return json.loads(p.stdout),calls
 def test_public_init_bounds_real_extraction_first_partial_and_completion(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=self.checkout(Path(tmp)/'source');s=upgraded(root);disc.scan(s,max_files=100);self.approve(s);(root/'A.cs').write_text('public class Same {}\n');(root/'Z.cs').write_text('public class Same {}\n');(root/'Note.md').write_text('Inventory only\n')
   first,calls=self.public_init(root,tmp,budget=1);self.assertEqual(len(calls),1);self.assertFalse(first['complete']);second,calls=self.public_init(root,tmp,first['id'],1);self.assertEqual(len(calls),1);self.assertFalse(second['complete']);done,calls=self.public_init(root,tmp,first['id'],100);self.assertTrue(done['complete']);self.assertLess(len(calls),100);self.assertFalse(any(o['subject']=='Same' for o in done['observations']));self.assertTrue(done['ambiguous']);again,calls=self.public_init(root,tmp,first['id'],1);self.assertFalse(calls)
   full=disc.scan(s,max_files=100,restart=True);self.assertEqual(done['observations'],full['observations']);self.assertEqual(done['ambiguous'],full['ambiguous']);(root/'A.cs').write_text('public class Changed {}\n')
   with self.assertRaisesRegex(KnowledgeError,'stale-scan'):disc.scan(s,first['id'],1)
 def test_two_harness_tasks_commit_refresh_exact_approval_and_dispositions(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=self.checkout(Path(tmp)/'project');project(root);git(root,'add','.');git(root,'commit','-m','Harness fixture');s=upgraded(root);plans=[];old=[]
   # Exercise automatic capture with an explicitly verified baseline. Retain
   # the setup candidates and their dispositions without applying any claims.
   baseline=disc.scan(s,max_files=100)
   self.assertTrue(baseline['complete'])
   for candidate_id in baseline['candidates']:
    life.dispose(s,candidate_id,'deferred','Fixture baseline review')
   for n,desired in enumerate(('public class ImprovedFeature {}\n','public class ImprovedFeature : System.Object {}\n')):
    expected_test(root,desired)
    with http_provider(FixtureProvider(desired=desired)) as endpoint:
     configure(root,configuration(endpoint),True);r=start(root,task());self.assertTrue(r['ok'],r)
    if n==0:
     from fixtures import addition
     unrelated=s.submit(addition('synthetic.unrelated'))['candidate']
    old.append(next(q['id'] for q in s.export()['queue'] if q['status']=='pending' and q['id'] not in old and q['id']!=unrelated));plans.append(s.prepare());self.assertTrue(plans[-1]['ok'],plans[-1]);git(root,'add','Feature.cs','test_feature.py');git(root,'commit','-m','Harness task '+str(n));refreshed=disc.scan(s,max_files=100)
    self.assertFalse(s.export()['records']['claims']) if n==0 else None
    p=s.prepare();self.assertTrue(p['ok'],p)
    if n==0:self.assertIn(unrelated,p['included'])
    with self.assertRaises(KnowledgeError):s.apply(plans[-1]['fingerprint'],plans[-1]['fingerprint'])
    s.apply(p['fingerprint'],p['fingerprint']);s.acknowledge(p['fingerprint']);fact=next(o for o in refreshed['observations'] if o['subject']=='ImprovedFeature');found=s.lookup('claims',fact['id']);self.assertEqual(found['record']['id'],fact['id']);self.assertEqual(found['revision']['lifecycle'],'active');self.assertTrue(found['freshness']['trusted']);self.assertEqual(life.history(s,fact['id'])['revisions'][-1]['lifecycle'],'active');self.assertFalse(s.prepare()['included'])
   self.assertEqual(sum(c['id']==fact['id'] for c in s.export()['records']['claims']),1)
 def test_prior_candidate_refresh_preserves_manual_dispositions_and_changed_meaning(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=self.checkout(tmp);(root/'Prior.cs').write_bytes(b'public class PriorReleaseFact {}\n');s=upgraded(root);fixture=json.loads(Path(__file__).with_name('data').joinpath('integrated-prior-candidate.json').read_text());self.assertEqual(fixture['product'],'0.4.0rc3');original=s.submit(fixture['payload'])['candidate'];self.assertFalse(s.export()['records']['claims']);disc.scan(s,max_files=100);fresh=s.prepare();self.assertTrue(fresh['ok'],fresh);self.assertNotIn(original,fresh['included']);self.assertIn(original,{q['id'] for q in s.export()['queue']});self.assertTrue(s.status()['candidate_refreshes'])
   # An unrelated deferred candidate remains an intentional human decision.
   for disposition in ('rejected','deferred'):
    (root/'Decision.cs').write_text('public class '+disposition.title()+'Observation {}\n');scan=disc.scan(s,max_files=100);candidate=next(q for q in s.export()['queue'] if q['id'] in scan['candidates'] and any(o['kind']=='claims' and disposition.title()+'Observation' in o['payload']['statement'] for o in q['payload']['operations']));life.dispose(s,candidate['id'],disposition,'Deliberate human decision');git(root,'add','.');git(root,'commit','-m','Snapshot changed '+disposition);disc.scan(s,max_files=100);self.assertEqual(next(q for q in s.status()['queue'] if q['id']==candidate['id'])['status'],disposition);self.assertFalse(any(q['id']!=candidate['id'] and disc.proposal_identity(q['payload'])==disc.proposal_identity(candidate['payload']) for q in s.export()['queue']))
   (root/'Decision.cs').write_text('public class DeferredObservation : System.Object {}\n');scan=disc.scan(s,max_files=100);self.assertTrue(any(q['id'] in scan['candidates'] and any(o['kind']=='claims' and 'System.Object' in o['payload']['statement'] for o in q['payload']['operations']) for q in s.export()['queue']))
 def test_refresh_links_cannot_hide_unrelated_meaning_or_form_cycles(self):
  for corruption in ('meaning','cycle'):
   with self.subTest(corruption=corruption),tempfile.TemporaryDirectory() as tmp:
    root=self.checkout(tmp);(root/'Prior.cs').write_bytes(b'public class PriorReleaseFact {}\n');s=upgraded(root);fixture=json.loads(Path(__file__).with_name('data').joinpath('integrated-prior-candidate.json').read_text());s.submit(fixture['payload']);disc.scan(s,max_files=100);link=s.status()['candidate_refreshes'][0]
    with s.connection(True) as db:
     if corruption=='meaning':
      from fixtures import addition
      payload=addition('synthetic.unrelated.corruption');cid=digest(payload);db.execute('INSERT INTO queue VALUES (?,?,?,NULL)',(cid,canonical_json(payload),'pending'));bad=dict(link,replacement=cid);db.execute('UPDATE metadata SET value=? WHERE key=?',(canonical_json(bad),disc.REFRESH_PREFIX+link['previous']))
     else:
      bad=dict(link,previous=link['replacement'],replacement=link['previous']);db.execute('INSERT INTO metadata VALUES (?,?)',(disc.REFRESH_PREFIX+bad['previous'],canonical_json(bad)))
    with self.assertRaisesRegex(KnowledgeError,'corrupt-candidate-refresh'):s.prepare()
