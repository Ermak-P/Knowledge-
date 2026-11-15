"""Real unittest execution with exact IDs/outcomes for the acceptance evidence map."""
import argparse,json,sys,unittest
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
    legacy=[row for row in rows if not row['test'].startswith('test_p2.') and not row['test'].startswith('test_p2_evidence.')]
    save(a.output/'product-tests.json',dict(tests_run=r.testsRun,legacy_tests=len(legacy),results=rows,success=r.wasSuccessful() and not r.skipped))
    assert len(legacy)==104,len(legacy);assert r.wasSuccessful() and not r.skipped
if __name__=='__main__':main()
