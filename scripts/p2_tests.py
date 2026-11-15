"""Real unittest execution with exact IDs/outcomes for the acceptance evidence map."""
import argparse,json,sys,unittest,subprocess
from pathlib import Path
from p2_evidence import ROOT,save

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();sys.path.insert(0,str(ROOT/'tests'))
    rows=[]
    class Result(unittest.TextTestResult):
        def addSuccess(self,test):super().addSuccess(test);rows.append({'test':test.id(),'status':'PASS'})
        def addFailure(self,test,err):super().addFailure(test,err);rows.append({'test':test.id(),'status':'FAIL'})
        def addError(self,test,err):super().addError(test,err);rows.append({'test':test.id(),'status':'ERROR'})
        def addSkip(self,test,reason):super().addSkip(test,reason);rows.append({'test':test.id(),'status':'SKIP','reason':reason})
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'));r=unittest.TextTestRunner(verbosity=2,resultclass=Result).run(suite)
    legacy=[row for row in rows if not row['test'].startswith('test_p2')]
    reviewed=json.loads(subprocess.check_output(['git','show','413bb196d58ca050e9be0bd05bd92cda129da70b:reports/P2/runs/5052e81943c54a25929e0eef5df03cb5/product-tests/product-tests.json'],cwd=ROOT,text=True))
    present={r['test']:r['status'] for r in rows}
    assert reviewed['tests_run']==129 and all(present.get(r['test'])=='PASS' for r in reviewed['results']),'original 129 regressions not preserved'
    save(a.output/'product-tests.json',dict(tests_run=r.testsRun,legacy_tests=len(legacy),reviewed_P2_tests_preserved=129,results=rows,success=r.wasSuccessful() and not r.skipped))
    assert len(legacy)==104,len(legacy);assert r.wasSuccessful() and not r.skipped
if __name__=='__main__':main()
