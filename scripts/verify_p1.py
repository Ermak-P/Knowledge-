"""Install first via scripts/setup.sh; no P0 report is overwritten."""
import re
import sys
from p1_evidence import Attempt,ROOT,save


def main():
    a=Attempt()
    try:
        a.command('packaging',[sys.executable,'-B','scripts/check_packaging.py'])
        a.command('product-tests',[sys.executable,'-B','-m','unittest','discover','-s','tests','-v'])
        log=(a.dir/'product-tests.log').read_text();m=re.search(r'Ran (\d+) tests',log)
        assert m and int(m[1])>=60 and log.rstrip().endswith('OK') and 'skipped=' not in log
        a.value['checks']['product-tests']['test_count']=int(m[1]);a.persist()
        a.command('evaluation',[sys.executable,'-B','scripts/evaluate_p1.py','--output',str(a.dir)],
            [a.dir/x for x in ('discovery.json','questions.json','benchmark.json','controlled.json','upgrade.json','source-immutability.json','eShopOnWeb-LICENSE','benchmark-restore.log','benchmark-build.log','before-discovery.log','after-discovery.log','dotnet-results/before-discovery.trx','dotnet-results/after-discovery.trx')])
        a.finish('PASS')
    except BaseException:
        a.finish('FAILED');raise
    print('P1 verified: '+a.id)


if __name__=='__main__':main()
