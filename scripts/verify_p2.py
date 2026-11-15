"""Fresh coherent P2 attempt; any failure invalidates previous current success."""
import sys
from p2_evidence import Attempt,validate_current

def main():
    a=Attempt()
    try:
        a.command('setup',['bash','scripts/setup.sh'])
        for name,script in [('baseline','p2_baseline.py'),('packaging','p2_packaging.py'),('product-tests','p2_tests.py'),('evaluation','evaluate_p2.py'),('sessions','p2_sessions.py'),('corrections','p2_corrections.py')]:
            a.command(name,[sys.executable,'-B','scripts/'+script,'--output',str(a.dir/name)])
        a.finish('PASS');validate_current()
    except BaseException:
        a.finish('FAILED');raise
    print('P2 verification PASS: '+a.id)
if __name__=='__main__':main()
