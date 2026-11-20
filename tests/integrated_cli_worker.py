"""Installed CLI with explicit test-only death/failure seams; no product monkeypatches."""
import argparse,os,sys
from harness import runtime,run_cli
from knowledge.store import Store
from knowledge.util import KnowledgeError

def main():
 p=argparse.ArgumentParser();p.add_argument('--die');p.add_argument('--fail-submit',action='store_true');p.add_argument('argv',nargs=argparse.REMAINDER);a=p.parse_args();argv=a.argv[1:] if a.argv[:1]==['--'] else a.argv
 if a.fail_submit:
  def fail(self,value):raise KnowledgeError('synthetic-transient-submit')
  Store.submit=fail
 root=argv[argv.index('--root')+1]
 def fault(phase):
  if a.die=='before-first-patch' and phase=='provider-response':
   for r in runtime.Journal(root).runs():
    if r['frames'] and any(c['function']['name']=='patch' for c in (r['frames'][-1].get('pending') or {}).get('tool_calls',[])):os._exit(73)
  if a.die=='legacy-build-receipt' and phase=='automatic-verifier-receipt':
   for r in runtime.Journal(root).runs():
    if r.get('p4',{}).get('verifiers') and r['p4']['verifiers'][-1].get('phase')=='legacy-build':os._exit(73)
  if phase==a.die:os._exit(73)
 runtime.fault=fault;sys.argv=['harness-run',*argv];return run_cli.main()
if __name__=='__main__':raise SystemExit(main())
