"""Installed Confluence regression gate for a review distribution."""
import argparse,json,os,platform,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    import knowledge
    assert Path(knowledge.__file__).is_relative_to(Path(sys.prefix)),'Test the installed package'
    sys.path.insert(0,str(ROOT/'tests'))
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_confluence*.py'))
    value=dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),platform=platform.system(),tests=result.testsRun,failed=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),success=result.wasSuccessful() and result.testsRun>=62 and (os.name!='nt' or not result.skipped),nonpassing=[dict(test=t.id(),status=status) for status,items in (('FAIL',result.failures),('ERROR',result.errors)) for t,error in items])
    if os.environ.get('GITHUB_RUN_ID'):value['url']='https://github.com/'+os.environ['GITHUB_REPOSITORY']+'/actions/runs/'+os.environ['GITHUB_RUN_ID']
    if os.environ.get('GITHUB_RUN_ID'):
        value.update(url='https://github.com/'+os.environ['GITHUB_REPOSITORY']+'/actions/runs/'+os.environ['GITHUB_RUN_ID'],run_attempt=os.environ.get('GITHUB_RUN_ATTEMPT','1'))
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    raise SystemExit(not value['success'])


if __name__=='__main__':main()
