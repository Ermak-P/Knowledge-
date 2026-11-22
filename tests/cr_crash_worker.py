"""Internal subprocess crash seam; no production activation/configuration."""
import os,sys
from knowledge import cr_workflow as cr
root,sid,action,phase=sys.argv[1:]
def fault(at):
    if at==phase:os._exit(83)
cr.fault=fault
w=cr.Workflow(root);s=w.get(sid)
if action=='prepare':w.prepare(sid,s['revision'])
else:w.apply(sid,s['proposal']['plan'],s['revision'])
raise AssertionError('crash seam not reached')
