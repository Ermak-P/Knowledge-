import argparse,faulthandler,sys,unittest
from pathlib import Path
from p3_evidence import ROOT,save
from p3_baseline import accepted_tests

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();sys.path.insert(0,str(ROOT/'tests'));rows=[]
    class Result(unittest.TextTestResult):
        def addSuccess(self,test):super().addSuccess(test);rows.append({'test':test.id(),'status':'PASS'})
        def addFailure(self,test,error):super().addFailure(test,error);rows.append({'test':test.id(),'status':'FAIL'})
        def addError(self,test,error):super().addError(test,error);rows.append({'test':test.id(),'status':'ERROR'})
        def addSkip(self,test,reason):super().addSkip(test,reason);rows.append({'test':test.id(),'status':'SKIP','reason':reason})
    faulthandler.enable();faulthandler.dump_traceback_later(60,repeat=True)
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'));result=unittest.TextTestRunner(verbosity=2,resultclass=Result).run(suite)
    faulthandler.cancel_dump_traceback_later()
    old=accepted_tests();seen={r['test']:r['status'] for r in rows};preserved=all(seen.get(r['test'])=='PASS' for r in old)
    allowed=[r for r in rows if r['status']=='SKIP' and sys.platform!='win32' and '.NativeWindowsSafety.' in r['test']]
    save(a.output/'tests.json',dict(tests_run=result.testsRun,passed=sum(r['status']=='PASS' for r in rows),skipped=len(result.skipped),accepted_regressions=138,preserved=preserved,results=rows,success=result.wasSuccessful() and preserved and len(allowed)==len(result.skipped)))
    assert preserved and result.wasSuccessful() and len(allowed)==len(result.skipped),'required regression missing/failed/skipped'
if __name__=='__main__':main()
