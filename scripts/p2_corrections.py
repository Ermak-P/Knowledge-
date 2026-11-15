"""Fresh production reproductions for the three P2 independent review findings."""
import argparse,sys,tempfile
from pathlib import Path
from p2_evidence import ROOT,save
sys.path.insert(0,str(ROOT/'tests'))
from p2_review_fixtures import learning,manual_review,verifier,overlap,update_retry

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    def run(name,fn,*args,**kwargs):
        with tempfile.TemporaryDirectory(prefix='P2 review путь ') as tmp:value=fn(Path(tmp),*args,**kwargs)
        save(a.output/(name+'.json'),value);print(name+': PASS',flush=True)
    run('repeated-learning',learning)
    run('manual-meaning',manual_review)
    run('legacy-manual-review',manual_review,legacy=True)
    run('update-accepted-before-ack',update_retry)
    for disposition in ('rejected','deferred'):run('update-'+disposition,update_retry,disposition)
    for absolute,executable in ((False,False),(True,False),(True,True)):run('verifier-'+str(absolute)+'-'+str(executable),verifier,absolute,executable)
    run('verifier-explicit-exception',verifier,exception=True)
    for window in ('read-only','coding','capture'):run('resume-'+window,overlap,window)
    run('resume-config-change',overlap,'capture',True)
    save(a.output/'corrections.json',dict(reviewed_revision='413bb196d58ca050e9be0bd05bd92cda129da70b',provider='synthetic decisions via actual HTTP; files/processes/state/Knowledge APIs actual',findings={k:'PASS' for k in ('P2-R1','P2-R2','P2-R3')}))
if __name__=='__main__':main()
