"""Evidence-driven omission and repair decisions over real HTTP/tools."""
from knowledge.util import loads
from p2_fixtures import calls,final
class MissingFile:
    def __init__(self,path,body,structured):
        self.path=path;self.body=body;self.structured=structured;self.turns={};self.repair_scopes=[];self.omission_read=None
    def decide(self,b):
        s=loads(b['messages'][0]['content']);role=s['runtime_role'];agent=s['agent'];n=self.turns.get(agent,0);self.turns[agent]=n+1
        results=[loads(m['content']) for m in b['messages'] if m['role']=='tool']
        if role=='Main':
            if any(i['status']!='done' for i in s['ledger']['items']):return calls(('delegate',dict(role='Coding',assignment='Complete active item')))
            if s['progress']['gates'].get('review',{}).get('verdict')=='approve':return final()
            return calls(('delegate',dict(role='Reviewing',assignment='Independently check the required file and actual content')))
        if role=='Coding':
            if s['writable']==[self.path]:
                active=next(i for i in s['ledger']['items'] if i['id']=='missing')
                if active['attempts']==1:return final('Omission: model mistakenly considers item complete')
                self.repair_scopes.append(s['writable'])
                if n==0:return calls(('read',dict(path=self.path)))
                if n==1:return calls(('patch',dict(files=[dict(path=self.path,before=results[-1].get('sha256'),after=self.body)])))
                return final('Created the already authorized omitted file')
            if n==0:return calls(('read',dict(path='Feature.cs')))
            if n==1:return calls(('patch',dict(files=[dict(path='Feature.cs',before=results[-1]['sha256'],after='public class ImprovedFeature {}\n')])))
            return final()
        if role=='Reviewing':
            if n==0:return calls(('read',dict(path=self.path)))
            if n==1:
                observation=results[-1];good=observation.get('ok') is True and observation.get('text')==self.body
                if not good:self.omission_read=observation
                args=dict(verdict='approve' if good else 'reject',findings=[] if good else [self.path+' is absent; create the already authorized required file.'])
                if self.structured:args['affected']=[] if good else [dict(item='missing',paths=[self.path])]
                return calls(('review',args))
            return final()
        return final()
