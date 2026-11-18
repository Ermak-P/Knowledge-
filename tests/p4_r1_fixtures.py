"""R1 decisions consume only actual HTTP tool evidence, never project filesystem."""
from p2_fixtures import calls,final
from knowledge.util import loads

class Discovery:
    def __init__(self,legacy=False):
        self.legacy=legacy;self.turns={};self.known={};self.bodies=[];self.approved=False
    def decide(self,body):
        self.bodies.append(body);s=loads(body['messages'][0]['content']);role=s['runtime_role'];aid=s['agent'];n=self.turns.get(aid,0);self.turns[aid]=n+1
        results=[loads(m['content']) for m in body['messages'] if m['role']=='tool']
        if role=='Main':
            if self.legacy:
                return calls(*[('delegate',dict(role=r,assignment='Preserve the discovered value and verify')) for r in ('Planning','Coding','Building','Testing','Reviewing')]) if n==0 else final()
            if any(i['status']!='done' for i in s['ledger']['items']):return calls(('delegate',dict(role='Coding',assignment='Discover the target value and implement it')))
            return final() if self.approved else calls(('delegate',dict(role='Reviewing',assignment='Check final behavior independently')))
        if role=='Coding':
            # Learn from actual reads, or from the runtime continuation's owned observations.
            for result in results:
                if result.get('path')=='Notes.md' and 'text' in result:self.known[aid]=result['text'].strip()
            for observation in (s.get('continuation') or {}).get('observations',[]):
                if observation.get('path')=='Notes.md':self.known[aid]=observation['excerpt_untrusted'].strip()
            if aid not in self.known:
                # A resumed context must receive discovery data or a retrievable reference.
                if s.get('epoch',0)>0:return final('Lost discovered working state',status='failed')
                return calls(('read',{'path':'Notes.md'}))
            # Four successful tool rounds force rotation; the fresh context uses only its handoff.
            if not s.get('epoch',0) and n<5:return calls(('read',{'path':'Feature.cs'}))
            if results and 'after_source' in results[-1]:return calls(('read',{'path':'Feature.cs'}))
            if results and any(k in results[-1] for k in ('written','reconciled')):return calls(('read',{'path':'Feature.cs'}))
            read=next((x for x in reversed(results) if x.get('path')=='Feature.cs' and 'sha256' in x),None)
            if read is None:return calls(('read',{'path':'Feature.cs'}))
            desired='public class ImprovedFeature {}\n// '+self.known[aid]+'\n'
            if read['text']!=desired:return calls(('patch',{'files':[dict(path='Feature.cs',before=read['sha256'],after=desired)]}))
            return final('Implemented value discovered from owned Notes.md evidence')
        if role in ('Building','Testing'):return calls(('recipe',{'name':'build' if role=='Building' else 'test'})) if n==0 else final()
        if role=='Reviewing':
            if n==0:return calls(('read',{'path':'Notes.md'}),('read',{'path':'Feature.cs'}))
            if n==1:
                note=next(x['text'].strip() for x in results if x.get('path')=='Notes.md');source=next(x['text'] for x in results if x.get('path')=='Feature.cs');self.approved=('// '+note+'\n') in source
                return calls(('review',dict(verdict='approve' if self.approved else 'reject',findings=[] if self.approved else ['Feature.cs lost the discovered value'])))
            return final()
        return final()

class EarlierItem:
    def __init__(self):self.turns={};self.rejected=False;self.approved=False;self.scopes=[];self.bodies=[]
    def decide(self,b):
        self.bodies.append(b);s=loads(b['messages'][0]['content']);role=s['runtime_role'];n=self.turns.get(s['agent'],0);self.turns[s['agent']]=n+1
        results=[loads(m['content']) for m in b['messages'] if m['role']=='tool']
        if role=='Main':
            if any(i['status']!='done' for i in s['ledger']['items']):return calls(('delegate',dict(role='Coding',assignment='Complete the active authorized item')))
            return final() if self.approved else calls(('delegate',dict(role='Reviewing',assignment='Check both files against all original criteria')))
        if role=='Coding':
            path='Feature.cs' if self.rejected or s['assignment']=='Implement Feature' else 'Other.cs'
            if self.rejected:self.scopes.append(s['writable'])
            if n==0:return calls(('read',dict(path=path)))
            if n==1:
                read=results[-1];after='public class Other {}\n' if path=='Other.cs' else 'public class ImprovedFeature {}\n'+('// APPROVED_MARKER\n' if self.rejected else '')
                return calls(('patch',dict(files=[dict(path=path,before=read['sha256'],after=after)])))
            return final()
        if role=='Reviewing':
            if n==0:return calls(('read',dict(path='Feature.cs')))
            if n==1:
                self.approved='APPROVED_MARKER' in results[-1]['text'];self.rejected=not self.approved
                return calls(('review',dict(verdict='approve' if self.approved else 'reject',findings=[] if self.approved else ['Feature.cs must retain APPROVED_MARKER'])))
            return final()
        return final()
