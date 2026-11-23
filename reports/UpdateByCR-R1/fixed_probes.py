"""Retain actual installed R1 regression state, not assertions against source code."""
import argparse,hashlib,importlib.util,json,subprocess,sys,unittest
from pathlib import Path


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    repo=Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo/'tests'))
    import knowledge
    from knowledge import cr_workflow
    from test_update_by_cr_r1 import UpdateByCRReviewR1
    assert Path(knowledge.__file__).is_relative_to(Path(sys.prefix))
    assert importlib.util.find_spec('harness') is None and importlib.util.find_spec('mcp') is None
    captures={}
    class Captured(UpdateByCRReviewR1):
        def setUp(self):super().setUp();self.events=[]
        def capture_state(self):
            export=self.w.store.export()
            return dict(target_commit=subprocess.check_output(['git','-C',str(self.root),'rev-parse','HEAD'],text=True).strip(),retry_source=(self.root/'Retry.cs').read_text(),records=export['records'],revisions=export['revisions'],queue=self.w.store.status()['queue'],default_context=self.w.store.context('transient retry attempts public contract',max_items=20),optional_context=self.w.store.context('transient retry attempts public contract',max_items=20,include_unconfirmed=True),workflow_sessions=export.get('update_by_cr'))
        def commit(self,state):
            before=self.capture_state();saved=super().commit(state);self.events.append(dict(before=before,receipt=saved,after=self.capture_state()));return saved
        def tearDown(self):
            try:captures[self._testMethodName]=dict(events=self.events,final=self.capture_state())
            finally:super().tearDown()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Captured))
    for name,value in captures.items():(args.output/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    summary=dict(status='PASS' if result.wasSuccessful() else 'FAIL',profile='installed-knowledge-only-R1-regressions-with-before-after-state',tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),knowledge_import=knowledge.__file__,workflow_module_sha256=hashlib.sha256(Path(cr_workflow.__file__).read_bytes()).hexdigest(),harness_absent=True,mcp_absent=True,scenarios=list(captures))
    (args.output/'result.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary));return not result.wasSuccessful()
if __name__=='__main__':raise SystemExit(main())
