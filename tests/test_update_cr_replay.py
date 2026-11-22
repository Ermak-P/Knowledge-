from pathlib import Path
import json,subprocess,sys,tempfile,unittest
from knowledge.cr_workflow import Workflow
from cr_fixtures import project,decisions,ready

HERE=Path(__file__).parent


class UpdateCRReplay(unittest.TestCase):
    def test_two_domains_retrieve_reasons_and_critical_nonchanges_in_fresh_process(self):
        oracle=json.loads((HERE/'data/update-cr-oracle.json').read_text())
        for scenario,query in [('retry','Bound transient operation failures with independent transport retries and caller deadline'),('cache','Кэш справочника: ёмкость память интерфейс ILookup Find совместимость')]:
            with self.subTest(scenario=scenario),tempfile.TemporaryDirectory() as tmp:
                root,snapshot=project(tmp,scenario=scenario);workflow=Workflow(root)
                answers={'retry-limit':'max_attempts=4 fits the bounded transient operation budget.',
                         'transport-owner':'packet_attempts=2 remains an independent packet recovery policy; changing it would multiply work.',
                         'deadline':'caller_deadline_ms=120 preserves the public caller budget.',
                         'capacity':'cache_capacity=32 ограничивает расход памяти и сохраняет поведение при промахе.',
                         'contract':'Сохранена совместимость потребителей ILookup; не менять сигнатуру Find.'}
                s=ready(workflow,snapshot,decisions(snapshot,scenario),language='ru' if scenario=='cache' else 'en',answers=answers)
                p=workflow.prepare(s['session'],s['revision']);workflow.apply(s['session'],p['proposal']['plan'],p['revision'])
                child=subprocess.run([sys.executable,'-I',str(HERE/'cr_replay_worker.py'),str(root),query],capture_output=True,text=True)
                self.assertEqual(child.returncode,0,child.stdout+child.stderr);result=json.loads(child.stdout);plan=result['plan'];expected=oracle[scenario]
                self.assertEqual(plan['parameters'],expected['parameters'])
                for condition in expected['preserve']:self.assertIn(condition,' '.join(plan['preserve']))
                for reason in expected['reasons']:self.assertIn(reason,' '.join(plan['reasons']))
                # The independent oracle rejects loss of a critical nonchange,
                # even if all numeric implementation facts were recovered.
                censored={**plan,'preserve':[]}
                self.assertFalse(all(x in ' '.join(censored['preserve']) for x in expected['preserve']))
