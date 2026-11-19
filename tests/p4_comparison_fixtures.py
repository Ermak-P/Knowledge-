"""A common scripted provider policy, with evidence-dependent discoveries and independent tests."""
from knowledge.util import loads
from p2_fixtures import calls,final
class Scenario:
    def __init__(self,name,legacy=False):self.name=name;self.legacy=legacy;self.bodies=[];self.turns={};self.pressure=0;self.coding_starts=set()
    def decide(self,b):
        self.bodies.append(b);s=loads(b['messages'][0]['content']);role=s['runtime_role'];agent=s['agent'];n=self.turns.get(agent,0);self.turns[agent]=n+1
        tools=[loads(m['content']) for m in b['messages'] if m['role']=='tool'];gates=s['progress']['gates'];pressure=self.name=='multi-pressure'
        if role=='Main':
            if self.legacy:
                good=all(gates.get(k,{}).get('ok') for k in ('build','test')) and gates.get('review',{}).get('verdict')=='approve'
                if good:return final()
                if len(self.coding_starts)>=3:return final('Finite scripted legacy allowance exhausted',status='failed')
                roles=('Planning','Coding','Building','Testing','Reviewing') if n==0 else ('Coding','Building','Testing','Reviewing')
                return calls(*[('delegate',dict(role=r,assignment='Implement all files from the authorized criteria')) for r in roles])
            if any(i['status']!='done' for i in s['ledger']['items']):return calls(('delegate',dict(role='Coding',assignment='Complete active item')))
            return final() if gates.get('review',{}).get('verdict')=='approve' else calls(('delegate',dict(role='Reviewing',assignment='Check all final outputs and actual gates')))
        if role=='Coding':
            self.coding_starts.add(agent)
            observations=[]
            if s.get('continuation'):observations+=s['continuation'].get('observations',[])
            for item in s.get('ledger',{}).get('items',[]):observations+=(item.get('handoff') or {}).get('continuation',{}).get('observations',[])
            note=next((x['text'].strip() for x in reversed(tools) if x.get('path')=='Notes.md' and x.get('text')),None)
            if not note:note=next((x['excerpt_untrusted'].strip() for x in observations if x.get('path')=='Notes.md'),None)
            if pressure and note is None:
                if s.get('epoch',0):return final('Discovered value was lost',status='failed')
                return calls(('read',dict(path='Notes.md')))
            if pressure and self.pressure<8:
                self.pressure+=1;return calls(('read',dict(path='Large.py')))
            value=int(note) if pressure else 2
            if self.name=='persistent-failure':value=-1
            desired={'Feature.py':'def value():\n    return '+str(value)+'\n'}
            if self.name in ('multi-file','multi-pressure'):
                desired['Other.py']='def value():\n    return '+str(value*2)+'\n'
                desired['test_created.py']='import unittest,Feature,Other\nclass AddedRegression(unittest.TestCase):\n def test_pair(self):self.assertEqual(Other.value(),Feature.value()*2)\n'
            if not self.legacy:
                allowed=s['writable'];desired={p:v for p,v in desired.items() if p in allowed}
            if tools and ('written' in tools[-1] or 'reconciled' in tools[-1]):return calls(*[('read',dict(path=p)) for p in desired])
            reads={x['path']:x for x in tools if x.get('path') in desired and 'sha256' in x}
            if any(p not in reads for p in desired if p!='test_created.py'):return calls(*[('read',dict(path=p)) for p in desired])
            if all(p in reads and reads[p]['text']==text for p,text in desired.items()):return final('Implemented using observed working state')
            return calls(('patch',dict(files=[dict(path=p,before=reads[p]['sha256'] if p in reads else None,after=text) for p,text in desired.items()])))
        if role in ('Building','Testing'):return calls(('recipe',dict(name='build' if role=='Building' else 'test'))) if n==0 else final()
        if role=='Reviewing':
            if n==0:return calls(('read',dict(path='Feature.py')),('read',dict(path='Other.py')),('read',dict(path='Notes.md')))
            if n==1:
                reads={x['path']:x['text'] for x in tools if 'path' in x and 'text' in x};value=int(reads['Notes.md'].strip()) if pressure else 2
                good=('return '+str(value)+'\n') in reads['Feature.py'] and all(gates.get(k,{}).get('ok') for k in ('build','test'))
                if self.name in ('multi-file','multi-pressure'):good=good and ('return '+str(value*2)+'\n') in reads['Other.py']
                return calls(('review',dict(verdict='approve' if good else 'reject',findings=[] if good else ['Feature.py or Other.py violates expected behavior or current verification'])))
            return final()
        return final('Read-only diagnosis: compare actual output, fixed test oracle and environment receipts')
