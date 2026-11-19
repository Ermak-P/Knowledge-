import sys,tempfile,json,argparse
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--checkout',type=Path,required=True);p.add_argument('--output',type=Path,required=True);opts=p.parse_args()
sys.path.insert(0,str(opts.checkout.absolute()/'tests'))
from p2_fixtures import project,configuration,http_provider,calls,final
from test_p4 import p4task
from knowledge.util import loads
from harness.runtime import configure
from harness.engine import start,status

class MissingFile:
    def __init__(self,structured):self.turns={};self.structured=structured;self.seen=[]
    def decide(self,b):
        s=loads(b['messages'][0]['content']);role=s['runtime_role'];n=self.turns.get(s['agent'],0);self.turns[s['agent']]=n+1
        if role=='Main':
            if any(i['status']!='done' for i in s['ledger']['items']):return calls(('delegate',dict(role='Coding',assignment='Complete the active item')))
            if s['progress']['gates'].get('review',{}).get('verdict')=='approve':return final()
            return calls(('delegate',dict(role='Reviewing',assignment='Verify all acceptance criteria')))
        if role=='Coding':
            if s['writable']==['Missing.cs']:
                # Simulate an implementation omission that final review must repair.
                item=next(i for i in s['ledger']['items'] if i['id']=='missing')
                if item['attempts']==1:return final('Work item completed')
                if n==0:return calls(('read',dict(path='Missing.cs')))
                if n==1:
                    t=[loads(m['content']) for m in b['messages'] if m['role']=='tool'][-1]
                    return calls(('patch',dict(files=[dict(path='Missing.cs',before=t.get('sha256'),after='public class RequiredFeature {}\n')])))
                return final('Created the omitted authorized source file')
            if n==0:return calls(('read',dict(path='Feature.cs')))
            if n==1:
                t=[loads(m['content']) for m in b['messages'] if m['role']=='tool'][-1]
                return calls(('patch',dict(files=[dict(path='Feature.cs',before=t['sha256'],after='public class ImprovedFeature {}\n')])))
            return final()
        if role=='Reviewing':
            if n==0:return calls(('read',dict(path='Missing.cs')))
            if n==1:
                t=[loads(m['content']) for m in b['messages'] if m['role']=='tool'][-1]
                good=t.get('ok') and 'class RequiredFeature' in t.get('text','')
                args=dict(verdict='approve' if good else 'reject',findings=[] if good else ['Missing.cs is missing; create the already authorized required source file.'])
                if self.structured:args['affected']=[] if good else [dict(item='missing',paths=['Missing.cs'])]
                return calls(('review',args))
            self.seen.extend(loads(m['content']) for m in b['messages'] if m['role']=='tool')
            return final()
        return final()

rows=[]
for structured in (False,True):
    with tempfile.TemporaryDirectory() as tmp,http_provider(d:=MissingFile(structured)) as endpoint:
        root=project(tmp);task=p4task();task['writable']=['Feature.cs','Missing.cs'];task['acceptance']=['Feature.cs contains ImprovedFeature. Missing.cs must exist and declare RequiredFeature.'];task['items']=[dict(id='first',objective='Implement Feature',depends=[],writable=['Feature.cs']),dict(id='missing',objective='Create required Missing.cs',depends=['first'],writable=['Missing.cs'])]
        configure(root,configuration(endpoint),True);r=start(root,task);s=status(root,r['run_id'])
        rows.append(dict(structured=structured,result=r,file_exists=(root/'Missing.cs').exists(),items=[{k:i[k] for k in ('id','status','attempts','issues')} for i in s['run']['p4']['items']],review_actions=[a.get('result') for a in s['actions'].values() if a['tool']=='review']))
p=opts.output.absolute();p.write_text(json.dumps(rows,indent=2)+'\n');print(p.read_text())
