"""Verify accepted historical bytes in Git, not by rerunning P1 against changed P2."""
import hashlib,json,subprocess
from pathlib import Path
from p2_evidence import ROOT,save
ACCEPTED='c62cad5aabbc47b43ef59fcf3ff975dd405eb42d'
EXPECTED='f6fbbd3dc18cfe085c3694bd6ab529f23e5eb7ac7b0c54bb450083bb33069954'
def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    def git(*argv):return subprocess.check_output(['git',*argv],cwd=ROOT)
    subprocess.run(['git','merge-base','--is-ancestor',ACCEPTED,'HEAD'],cwd=ROOT,check=True)
    accepted=json.loads(git('show',ACCEPTED+':reports/P1/SOURCE-REVISION.json'));assert accepted['source_identity']==EXPECTED
    for relative,expected in accepted['files'].items():assert hashlib.sha256(git('show',ACCEPTED+':'+relative)).hexdigest()==expected,relative
    # Keep all accepted regression bodies byte-for-byte; adding P2 tests is separate.
    tests=[p for p in git('ls-tree','-r','--name-only',ACCEPTED,'tests').decode().splitlines() if p.endswith('.py')]
    for relative in tests:assert (ROOT/relative).read_bytes()==git('show',ACCEPTED+':'+relative),relative
    reviewed='413bb196d58ca050e9be0bd05bd92cda129da70b'
    original_p2_tests=[p for p in git('ls-tree','-r','--name-only',reviewed,'tests').decode().splitlines() if Path(p).name.startswith('test_') and p.endswith('.py')]
    for relative in original_p2_tests:assert (ROOT/relative).read_bytes()==git('show',reviewed+':'+relative),relative
    value=dict(reviewed_P2_commit=reviewed,unchanged_reviewed_test_bodies=original_p2_tests,accepted_commit=ACCEPTED,accepted_source_identity=EXPECTED,accepted_files_verified=len(accepted['files']),unchanged_regression_files=tests,ancestry=True,development_base='5e6f33da5758c30418df490840c76c1946c84545',head_at_verification=git('rev-parse','HEAD').decode().strip(),branch=git('branch','--show-current').decode().strip(),historical_P1_reports_not_rewritten=True)
    save(a.output/'baseline.json',value);print('PASS: accepted P1 ancestry/inventory; all historical test bodies unchanged')
if __name__=='__main__':main()
