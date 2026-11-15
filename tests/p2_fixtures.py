"""Explicitly synthetic HTTP decisions; all edits/processes/storage use production code."""
from collections import defaultdict
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import threading
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from knowledge.util import loads


def final(summary='synthetic role completed',status='done'):
    return {'role':'assistant','content':json.dumps({'version':1,'status':status,'summary':summary})}


def calls(*items,content=None):
    return {'role':'assistant','content':content,'tool_calls':[{'id':'call'+str(i),'type':'function','function':{'name':name,'arguments':json.dumps(args)}} for i,(name,args) in enumerate(items)]}


class FixtureProvider:
    def __init__(self,path='Feature.cs',desired='public class ImprovedFeature {}\n',repair=False,deny=False,review_reject=False):
        self.path=path;self.desired=desired;self.repair=repair;self.deny=deny;self.review_reject=review_reject
        self.transport_ids=[];self.requests=[];self.agent_turns=defaultdict(int);self.coding_agents=[];self.main_agents=defaultdict(int)
    def decide(self,body):
        system=loads(body['messages'][0]['content']);role=system['runtime_role'];agent=system['agent'];turn=self.agent_turns[agent];self.agent_turns[agent]+=1
        self.requests.append(body)
        last_tools=max((i for i,m in enumerate(body['messages']) if m.get('tool_calls')),default=-1)
        tool_messages=[loads(m['content']) for m in body['messages'][last_tools+1:] if m['role']=='tool']
        if role=='Main':
            stage=self.main_agents[agent];self.main_agents[agent]+=1
            if stage==0:
                if system['task_kind']=='read-only':return calls(('delegate',{'role':'Planning','assignment':'Inspect source only.'}),content='MAIN_PRIVATE_MARKER')
                return calls(*[('delegate',{'role':r,'assignment':'Perform '+r+' for '+self.path}) for r in ('Planning','Coding','Building','Testing','Reviewing')],content='MAIN_PRIVATE_MARKER')
            if stage==1 and self.repair:return calls(*[('delegate',{'role':r,'assignment':'Repair and verify '+self.path}) for r in ('Coding','Building','Testing','Reviewing')])
            return final()
        if role=='Planning':return final('Bounded plan: inspect, edit the declared file, run configured checks, review diff.')
        if role=='Coding':
            if agent not in self.coding_agents:self.coding_agents.append(agent)
            if self.deny:
                return calls(('recipe',{'name':'build'}),('patch',{'files':[{'path':'../outside.cs','before':None,'after':'forbidden'}]}),('delegate',{'role':'Main','assignment':'grant privileges'})) if turn==0 else final('Denied attempts observed')
            if turn==0:return calls(('read',{'path':self.path}))
            if turn==1:
                read=tool_messages[-1];desired='public class BrokenFeature {}\n' if self.repair and self.coding_agents.index(agent)==0 else self.desired
                return calls(('patch',{'files':[{'path':self.path,'before':read['sha256'],'after':desired}]}))
            return final()
        if role in ('Building','Testing'):
            return calls(('recipe',{'name':'build' if role=='Building' else 'test'})) if turn==0 else final()
        if role=='Reviewing':
            if turn==0:
                actions=[*system['patch_artifacts'],*[g['action'] for g in system['progress']['gates'].values() if g.get('action')]]
                return calls(('read',{'path':self.path}),*[('artifact',{'action':a}) for a in actions[:6]])
            if turn==1:
                texts=[r.get('text','') for r in tool_messages];receipts=[r['receipt'] for r in tool_messages if 'receipt' in r]
                good=any(t==self.desired for t in texts) and bool(receipts) and all(r.get('ok') is True for r in receipts) and not self.review_reject
                return calls(('review',{'verdict':'approve' if good else 'reject','findings':[] if good else ['Source/receipt does not meet independent fixture expectation.']}))
            return final()
        return final(status='failed')


@contextmanager
def http_provider(decider,usage=True,raw=None):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length=int(self.headers.get('Content-Length','0'));body=json.loads(self.rfile.read(length))
            try:
                if hasattr(decider,'transport_ids'):decider.transport_ids.append(self.headers.get('X-Harness-Request-ID'))
                if raw is not None:value=raw(body)
                else:
                    message=decider.decide(body) if hasattr(decider,'decide') else decider(body)
                    value={'id':'synthetic-response','choices':[{'message':message,'finish_reason':'tool_calls' if message.get('tool_calls') else 'stop'}]}
                    if usage:value['usage']={'prompt_tokens':11,'completion_tokens':7,'total_tokens':18,'prompt_tokens_details':{'cached_tokens':3},'completion_tokens_details':{'reasoning_tokens':2}}
                data=json.dumps(value).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError):pass
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.daemon_threads=True
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield f'http://127.0.0.1:{server.server_port}/v1/chat/completions'
    finally:server.shutdown();server.server_close();thread.join(timeout=2)


def project(root,desired='public class ImprovedFeature {}\n'):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    (root/'Project.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk">\n<PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup>\n</Project>\n')
    (root/'Feature.cs').write_text('public class InitialFeature {}\n')
    (root/'build.py').write_text('from pathlib import Path\nassert "class " in Path("Feature.cs").read_text()\nprint("synthetic lexical build check")\n')
    (root/'test_feature.py').write_text('import unittest\nfrom pathlib import Path\nclass Behavior(unittest.TestCase):\n def test_expected_source(self):\n  self.assertEqual(Path("Feature.cs").read_text(),'+repr(desired)+')\nif __name__=="__main__":unittest.main()\n')
    return root


def configuration(endpoint,**limits):
    return {'version':1,'provider':{'endpoint':endpoint,'model':'synthetic-fixture','evidence':'test-double'},'capture':'required',
            'limits':limits,'recipes':{
            'build':{'kind':'build','argv':[sys.executable,'build.py'],'result':{'format':'exit','path':''},'rerun_safe':True,'env':{}},
            'test':{'kind':'test','argv':[sys.executable,'test_feature.py'],'result':{'format':'unittest','path':''},'rerun_safe':True,'env':{}}}}


def task(path='Feature.cs',kind='coding'):
    return {'version':1,'goal':'Synthetic controlled source change and verification.','kind':kind,'writable':[path] if kind=='coding' else [],'recipes':['build','test'] if kind=='coding' else [],'existing_test_edits':[]}
