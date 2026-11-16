"""Execute every P3-R1/R2 regression using only fresh installed product imports."""
import argparse,json,sys,unittest
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    import harness,knowledge
    checkout=Path(__file__).resolve().parents[1]
    for module in (harness,knowledge):
        path=Path(module.__file__);assert path.is_relative_to(Path(sys.prefix)) and not path.is_relative_to(checkout),str(path)
    sys.path.insert(0,str(Path(__file__).parent))
    import test_p3_companion_review as scenarios
    rows=[]
    class Result(unittest.TextTestResult):
        def addSuccess(self,test):super().addSuccess(test);rows.append({'test':test.id(),'status':'PASS'})
        def addFailure(self,test,error):super().addFailure(test,error);rows.append({'test':test.id(),'status':'FAIL'})
        def addError(self,test,error):super().addError(test,error);rows.append({'test':test.id(),'status':'ERROR'})
    result=unittest.TextTestRunner(verbosity=2,resultclass=Result).run(unittest.defaultTestLoader.loadTestsFromModule(scenarios))
    value={'status':'PASS' if result.wasSuccessful() else 'FAIL','fresh_installed_product':True,'prefix':sys.prefix,'product_paths':{'knowledge':knowledge.__file__,'harness':harness.__file__},'results':rows,'effects':scenarios.OBSERVATIONS,'configured_mcp':'real stdio module/arguments with deterministic filesystem scheduling probes; no mocked provider/tools/processes'}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    assert result.wasSuccessful() and not result.skipped and len(rows)==11,'required installed companion regression failed/skipped'

if __name__=='__main__':main()
