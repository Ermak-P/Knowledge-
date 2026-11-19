"""Count and forward every real extraction in the entire installed public CLI."""
import argparse,json,sys
from pathlib import Path
from knowledge import cli,discovery

def main():
 p=argparse.ArgumentParser();p.add_argument('--count',required=True);p.add_argument('argv',nargs=argparse.REMAINDER);a=p.parse_args();calls=[];real=discovery.extract
 def counted(*args,**kwargs):calls.append(args[1]);return real(*args,**kwargs)
 discovery.extract=counted;sys.argv=['knowledge',*(a.argv[1:] if a.argv[:1]==['--'] else a.argv)]
 try:return cli.main()
 finally:Path(a.count).write_text(json.dumps(calls),encoding='utf-8')
if __name__=='__main__':raise SystemExit(main())
