"""Local deterministic demonstration, not a live model or quality benchmark."""
import argparse,json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
EXPECTED='public static class Feature { public static string Value => "fixed"; }\n'
class Decisions:
 def __init__(self):self.turns={};self.requests=0
 def decide(self,body):
  self.requests+=1;s=json.loads(body['messages'][0]['content']);role=s['runtime_role'];n=self.turns.get(s['agent'],0);self.turns[s['agent']]=n+1
  results=[json.loads(m['content']) for m in body['messages'] if m['role']=='tool']
  def tool(name,args):return dict(role='assistant',content=None,tool_calls=[dict(id='demo-'+str(self.requests),type='function',function=dict(name=name,arguments=json.dumps(args)))])
  def done():return dict(role='assistant',content=json.dumps(dict(version=1,status='done',summary='Controlled fixture stage completed.')))
  if role=='Main':
   if any(i['status']!='done' for i in s['ledger']['items']):return tool('delegate',dict(role='Coding',assignment='Implement the authorized Feature.Value change'))
   if s['progress']['gates'].get('review',{}).get('verdict')!='approve':return tool('delegate',dict(role='Reviewing',assignment='Independently read and verify final Feature.cs'))
   return done()
  if role=='Coding':
   if n==0:return tool('read',dict(path='Feature.cs'))
   if n==1:return tool('patch',dict(files=[dict(path='Feature.cs',before=results[-1]['sha256'],after=EXPECTED)]))
   return done()
  if role=='Reviewing':
   if n==0:return tool('read',dict(path='Feature.cs'))
   if n==1:
    good=results[-1].get('ok') and results[-1].get('text')==EXPECTED
    return tool('review',dict(verdict='approve' if good else 'reject',findings=[] if good else ['Feature.cs does not implement the required value.']))
   return done()
  return done()
def main():
 p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=9000);p.add_argument('--ready-file',type=Path);p.add_argument('--counts-file',type=Path);a=p.parse_args();d=Decisions()
 class Handler(BaseHTTPRequestHandler):
  def do_POST(self):
   body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));message=d.decide(body);payload=json.dumps(dict(choices=[dict(message=message)],usage=dict(prompt_tokens=11,completion_tokens=7,total_tokens=18))).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
   if a.counts_file:a.counts_file.write_text(json.dumps(dict(requests=d.requests))+'\n',encoding='utf-8')
  def log_message(self,*args):pass
 server=ThreadingHTTPServer(('127.0.0.1',a.port),Handler);endpoint='http://127.0.0.1:'+str(server.server_port)+'/v1/chat/completions'
 if a.ready_file:a.ready_file.write_text(endpoint,encoding='utf-8')
 print(endpoint,flush=True)
 try:server.serve_forever()
 finally:server.server_close()
if __name__=='__main__':main()
