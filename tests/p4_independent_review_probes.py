import sys,json,tempfile,subprocess,argparse
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--checkout',type=Path,required=True)
parser.add_argument('--prior-python',required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
sys.path.insert(0,str(args.checkout.absolute()/'tests'))
from test_p4 import Decisions,p4task
from p2_fixtures import project,configuration,http_provider,calls,final
from harness.runtime import configure,Journal
from harness.engine import start,status
from knowledge.util import loads,canonical_json

OUT=args.output.absolute()
results={}

class Memory(Decisions):
    marker='DISCOVERED_INVARIANT_DO_NOT_DROP_89F1'
    def __init__(self):super().__init__();self.steps=0;self.coding_bodies=[]
    def decide(self,b):
        s=loads(b['messages'][0]['content'])
        if s['runtime_role']=='Coding':
            self.coding_bodies.append(b);self.steps+=1
            if self.steps==1:return calls(('read',{'path':'Notes.md'}))
            if self.steps<=5:return calls(('read',{'path':'Feature.cs'}))
        return super().decide(b)

with tempfile.TemporaryDirectory() as tmp,http_provider(d:=Memory()) as endpoint:
    root=project(tmp);(root/'Notes.md').write_text('Investigation: '+d.marker+'\n')
    configure(root,configuration(endpoint),True);r=start(root,p4task());s=status(root,r['run_id'])
    rotated=[b for b in d.coding_bodies if loads(b['messages'][0]['content']).get('epoch',0)>0]
    first=rotated[0]
    results['rotation_memory']={'result':r,'rotations':s['run']['p4']['rotations'],
      'marker_in_archived_checkpoint':d.marker in canonical_json(s['run']['p4']['checkpoints']),
      'marker_in_first_rotated_request':d.marker in canonical_json(first),
      'checkpoint_retrieval_reference_in_rotated_request':'checkpoints' in loads(first['messages'][0]['content']),
      'new_context_message_roles':[m['role'] for m in first['messages']]}

class EarlierItem:
    def __init__(self):self.turns={};self.rejected=False;self.repair_scopes=[]
    def decide(self,b):
        s=loads(b['messages'][0]['content']);role=s['runtime_role'];n=self.turns.get(s['agent'],0);self.turns[s['agent']]=n+1
        if role=='Main':
            if any(i['status']!='done' for i in s['ledger']['items']):return calls(('delegate',{'role':'Coding','assignment':'Do the active item'}))
            return calls(('delegate',{'role':'Reviewing','assignment':'Review all criteria'}))
        if role=='Coding':
            if self.rejected:
                self.repair_scopes.append(s['writable'])
                path='Feature.cs'
            else:path='Other.cs' if s['assignment']=='Create Other' else 'Feature.cs'
            if n==0:return calls(('read',{'path':path}))
            if n==1:
                ts=[loads(m['content']) for m in b['messages'] if m['role']=='tool']
                content='public class Other {}\n' if path=='Other.cs' else 'public class ImprovedFeature {}\n'+('// APPROVED_MARKER\n' if self.rejected else '')
                return calls(('patch',{'files':[{'path':path,'before':ts[-1]['sha256'],'after':content}]}))
            return final()
        if role=='Reviewing':
            if n==0:return calls(('read',{'path':'Feature.cs'}))
            if n==1:
                ts=[loads(m['content']) for m in b['messages'] if m['role']=='tool'];ok='APPROVED_MARKER' in ts[-1]['text'];self.rejected=not ok
                return calls(('review',{'verdict':'approve' if ok else 'reject','findings':[] if ok else ['Feature.cs must retain APPROVED_MARKER']}))
            return final()
        return final()

with tempfile.TemporaryDirectory() as tmp,http_provider(d:=EarlierItem()) as endpoint:
    root=project(tmp);(root/'Other.cs').write_text('public class InitialOther {}\n')
    (root/'test_feature.py').write_text('import unittest\nfrom pathlib import Path\nclass Behavior(unittest.TestCase):\n def test_class(self):self.assertIn("class ImprovedFeature",Path("Feature.cs").read_text())\nif __name__=="__main__":unittest.main()\n')
    t=p4task();t['writable']=['Feature.cs','Other.cs'];t['acceptance']=['ImprovedFeature exists and Feature.cs includes APPROVED_MARKER.']
    t['items']=[dict(id='first',objective='Implement Feature',depends=[],writable=['Feature.cs']),dict(id='last',objective='Create Other',depends=['first'],writable=['Other.cs'])]
    configure(root,configuration(endpoint),True);r=start(root,t);s=status(root,r['run_id'])
    denied=[{'path':a['args']['files'][0]['path'],'result':a['result']} for a in s['actions'].values() if a['tool']=='patch' and not a.get('result',{}).get('ok',False)]
    results['review_earlier_item']={'result':r,'repair_scopes':d.repair_scopes,'denied_patches':denied,'items':[{k:i[k] for k in ('id','status','attempts','issues')} for i in s['run']['p4']['items']],'final_feature':(root/'Feature.cs').read_text()}

with tempfile.TemporaryDirectory() as tmp:
    base=Path(tmp);root=base/'project';root.mkdir()
    old=args.prior_python
    script='''from pathlib import Path
from knowledge.store import Store
from knowledge import lifecycle as l,maintenance as m
root=Path(ROOT)
s=Store(root);s.init();l.upgrade(s,l.upgrade_preview(s)['fingerprint'])
p=m.preview(root,'upgrade',root.parent/'old-upgrade.zip');print(m.apply(root,p['preview'],p['fingerprint']))
'''.replace('ROOT',repr(str(root)))
    p=subprocess.run([old,'-I','-c',script],capture_output=True,text=True)
    from knowledge import maintenance as m
    from knowledge.util import KnowledgeError
    errors={}
    for op in ('backup','upgrade','restore'):
        try:m.preview(root,op,base/('next-'+op+'.zip'),base/'old-upgrade.zip',base/'recovery')
        except Exception as e:errors[op]={'type':type(e).__name__,'code':getattr(e,'code',str(e))}
    results['p3_maintenance_marker']={'old_exit':p.returncode,'old_stdout':p.stdout,'old_stderr':p.stderr,'marker':json.loads((root/'.maintenance/product-state.json').read_text()) if (root/'.maintenance/product-state.json').exists() else None,'p4_errors':errors}

OUT.write_text(json.dumps(results,indent=2)+'\n')
print(OUT.read_text())
