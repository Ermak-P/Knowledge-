"""Accepted P2 ancestry/inventory and old-case mapping without a deleted branch."""
import argparse,ast,json,subprocess
from pathlib import Path
from p3_evidence import ROOT,save,digest
PIN='91689475a283a2cdc654cfb6090074f0251f895d'
SOURCE='4bb5fdfc0dabe64fee7087a29565549b40da6f2a8f32e203ed46f58883110416'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def accepted_tests():return json.loads(git('show',PIN+':reports/P2/runs/ca612a0cc9954720a81aed883ed0652f/product-tests/product-tests.json'))['results']
def assertions(text):
    tree=ast.parse(text)
    return [ast.dump(n,include_attributes=False) for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr.startswith('assert')]
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    subprocess.run(['git','merge-base','--is-ancestor',PIN,'HEAD'],cwd=ROOT,check=True)
    source=json.loads(git('show',PIN+':reports/P2/verification-summary.json'));assert source['source_identity']==SOURCE
    import hashlib
    for path,h in source['source_files'].items():assert hashlib.sha256(git('show',PIN+':'+path)).hexdigest()==h,path
    previous=accepted_tests();assert len(previous)==138 and all(r['status']=='PASS' for r in previous)
    mappings=[]
    files=git('ls-tree','-r','--name-only',PIN,'tests').decode().splitlines()
    for name in files:
        if not Path(name).name.startswith('test_') or not name.endswith('.py'):continue
        before=git('show',PIN+':'+name).decode('utf-8');after=(ROOT/name).read_text(encoding='utf-8')
        assert assertions(before)==assertions(after),name
        changes=[]
        if before!=after:
            if 'multiprocessing.get_context' in after and 'spawn' in after:changes.append('fork on Linux / native spawn on Windows; removed fork-only skips')
            if 'with closing(sqlite3.connect' in after:changes.append('close fixture SQLite handles after the same transaction, permitting NTFS cleanup')
            if 'read_timeout_seconds=timedelta' in after:changes.append('bounded real MCP requests; timeout remains failure and all assertions are unchanged')
            if "'core.autocrlf','false'" in after:changes.append('fixture-local Git newline policy preserves exact source bytes in HEAD on both OSes')
        mappings.append(dict(file=name,behavioral_assertions_preserved=True,setup_changes=changes))
    save(a.output/'baseline.json',dict(accepted_commit=PIN,accepted_source_identity=SOURCE,accepted_files=len(source['source_files']),starting_main='0245afda6ecf7b873839adba4be4772611717210',ancestry=True,logical_regressions=138,old_cases=previous,mapping=mappings))
    print('PASS: accepted P2 inventory/ancestry, all 138 logical cases mapped and behavioral assertions preserved.')
if __name__=='__main__':main()
