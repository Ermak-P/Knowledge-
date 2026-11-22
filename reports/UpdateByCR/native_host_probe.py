"""Real OpenCode 1.19.6 registration/command API with a controlled test provider.

All host configuration/XDG/processes are isolated. No live model quality claim.
"""
import argparse,json,os,socket,subprocess,tempfile,threading,time,urllib.request,urllib.error
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--python',type=Path,required=True);p.add_argument('--opencode',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);requests=[]
    class Provider(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            value=json.loads(self.rfile.read(int(self.headers['Content-Length'])));requests.append(value)
            serialized=json.dumps(value,ensure_ascii=False);question='Пришлите ссылку на CR и ссылку на pull request, который его реализует.'
            if '\\"missing\\":[]' in serialized:question='Ссылки получены; следующий шаг — чтение источников. Knowledge ещё не сохранено.'
            elif '\\"missing\\":[\\"pr\\"]' in serialized:question='Пришлите ссылку на pull request, который реализует CR.'
            elif '\\"missing\\":[\\"cr\\"]' in serialized:question='Пришлите ссылку на CR.'
            # Also handle a non-double-encoded message serialization.
            for message in value.get('messages',[]):
                content=message.get('content','');content=content if isinstance(content,str) else '\n'.join(p.get('text','') for p in content if isinstance(p,dict))
                for marker in ['Knowledge /update-by-CR durable workflow: ','CR link progress: ']:
                    if marker in content:
                        state=json.JSONDecoder().raw_decode(content.rsplit(marker,1)[1])[0]
                        question=state.get('question') or 'Ссылки получены; требуется чтение источников. Knowledge ещё не сохранено.'
            if value.get('stream'):
                chunks=[dict(id='controlled',object='chat.completion.chunk',created=0,model='fixture',choices=[dict(index=0,delta={'role':'assistant','content':question},finish_reason=None)]),dict(id='controlled',object='chat.completion.chunk',created=0,model='fixture',choices=[dict(index=0,delta={},finish_reason='stop')])]
                body=(''.join('data: '+json.dumps(v,ensure_ascii=False)+'\n\n' for v in chunks)+'data: [DONE]\n\n').encode()
                self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            else:
                body=json.dumps(dict(id='controlled',object='chat.completion',created=0,model='fixture',choices=[dict(index=0,message={'role':'assistant','content':question},finish_reason='stop')],usage={'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}),ensure_ascii=False).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    provider=ThreadingHTTPServer(('127.0.0.1',0),Provider);thread=threading.Thread(target=provider.serve_forever,daemon=True);thread.start()
    result={'profile':'native-opencode-controlled-provider','live_model':False,'checks':{},'commands':[]}
    with tempfile.TemporaryDirectory(prefix='ucr-native-') as tmp:
        root=Path(tmp)/'project';root.mkdir();xdg=Path(tmp)/'xdg';env={**os.environ,'XDG_DATA_HOME':str(xdg/'data'),'XDG_CONFIG_HOME':str(xdg/'config'),'XDG_CACHE_HOME':str(xdg/'cache'),'XDG_STATE_HOME':str(xdg/'state'),'npm_config_cache':str(xdg/'npm-cache'),'NPM_CONFIG_CACHE':str(xdg/'npm-cache'),'OPENCODE_DISABLE_AUTOUPDATE':'1','OPENCODE_DISABLE_MODELS_FETCH':'1','OPENCODE_DISABLE_DEFAULT_PLUGINS':'1'}
        install=subprocess.run([str(a.python),'-I','-m','knowledge.cr_cli','install','--root',str(root)],input=json.dumps({'python':str(a.python),'language':'ru'}),text=True,capture_output=True);assert install.returncode==0,install.stdout+install.stderr
        configuration={'$schema':'https://opencode.ai/config.json','model':'fixture/fixture','provider':{'fixture':{'npm':'@ai-sdk/openai-compatible','name':'Controlled fixture only','options':{'baseURL':f'http://127.0.0.1:{provider.server_port}/v1','apiKey':'controlled-fixture-not-a-credential'},'models':{'fixture':{'name':'fixture','limit':{'context':64000,'output':2048}}}}}}
        (root/'opencode.json').write_text(json.dumps(configuration))
        version=subprocess.check_output([str(a.opencode),'--version'],cwd=root,env=env,text=True).strip();assert version=='1.19.6',version;result['version']=version
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        log=(a.output/'host.log').open('wb');host=subprocess.Popen([str(a.opencode),'serve','--print-logs','--hostname','127.0.0.1','--port',str(port)],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
        def api(path,value=None):
            request=urllib.request.Request(f'http://127.0.0.1:{port}'+path,data=json.dumps(value).encode() if value is not None else None,headers={'Content-Type':'application/json'})
            try:
                with urllib.request.urlopen(request,timeout=35) as response:return json.load(response)
            except urllib.error.HTTPError as e:raise RuntimeError('native HTTP '+str(e.code)+': '+e.read(3000).decode()) from e
        try:
            for _ in range(100):
                try:health=api('/global/health');break
                except (OSError,urllib.error.URLError):time.sleep(.1)
            else:raise AssertionError('native host did not start')
            commands=api('/command');registered=next(v for v in commands if v['name']=='update-by-CR');assert registered.get('subtask') is not True
            result['checks']['native_registration']='PASS';result['registration']=registered
            for label,arguments,missing in [('none','',['cr','pr']),('one','https://github.com/synthetic/project/issues/7',['pr']),('both','https://github.com/synthetic/project/issues/7 https://github.com/synthetic/project/pull/8',[])]:
                session=api('/session',{});answer=api('/session/'+session['id']+'/command',{'command':'update-by-CR','arguments':arguments})
                messages=api('/session/'+session['id']+'/message');(a.output/(label+'-messages.json')).write_text(json.dumps(messages,ensure_ascii=False,indent=2)+'\n')
                # Inspect the genuine backend durable receipt, not a simulated
                # parser result or arbitrary model wording.
                state=subprocess.run([str(a.python),'-I','-m','knowledge.cr_cli','start','--root',str(root)],input=json.dumps({'host_session':session['id'],'language':'ru'}),text=True,capture_output=True);assert state.returncode==0,state.stdout+state.stderr
                value=json.loads(state.stdout);assert value['missing']==missing,(label,value)
                result['commands'].append(dict(case=label,arguments=arguments,response=answer,backend=value));result['checks'][label]='PASS'
                if label=='none':empty_session=session
            # Actual foreground user messages complete the missing links; a
            # second command/chat must reuse the known pair, not create facts.
            for index,text in enumerate(['https://github.com/synthetic/project/issues/7','https://github.com/synthetic/project/pull/8']):
                answer=api('/session/'+empty_session['id']+'/message',{'parts':[{'type':'text','text':text}]})
                result['commands'].append(dict(case='conversation-link-'+str(index+1),response=answer))
            messages=api('/session/'+empty_session['id']+'/message');(a.output/'conversation-messages.json').write_text(json.dumps(messages,ensure_ascii=False,indent=2)+'\n')
            state=subprocess.run([str(a.python),'-I','-m','knowledge.cr_cli','start','--root',str(root)],input=json.dumps({'host_session':empty_session['id'],'language':'ru'}),text=True,capture_output=True)
            assert state.returncode==0,state.stdout;known=json.loads(state.stdout);assert known['missing']==[]
            assert known['session']==result['commands'][2]['backend']['session'];result['checks']['conversation_link_reuse']='PASS'
            new=api('/session',{});answer=api('/session/'+new['id']+'/command',{'command':'update-by-CR','arguments':'--resume '+known['session']})
            resumed=subprocess.run([str(a.python),'-I','-m','knowledge.cr_cli','start','--root',str(root)],input=json.dumps({'host_session':new['id'],'language':'ru'}),text=True,capture_output=True)
            assert resumed.returncode==0,resumed.stdout;resumed=json.loads(resumed.stdout);assert resumed['session']==known['session'] and resumed['missing']==[]
            result['commands'].append(dict(case='new-chat-resume',response=answer,backend=resumed));result['checks']['new_chat_resume']='PASS'
        except Exception as error:
            result.update(status='FAIL',error=str(error));raise
        finally:
            host.terminate()
            try:host.wait(timeout=10)
            except subprocess.TimeoutExpired:host.kill();host.wait()
            log.close();provider.shutdown();provider.server_close()
            for source in (xdg/'data/opencode/log').glob('*'):
                if source.is_file():(a.output/('runtime-'+source.name)).write_bytes(source.read_bytes())
            result.setdefault('status','PASS');(a.output/'requests.json').write_text(json.dumps(requests,ensure_ascii=False,indent=2)+'\n');(a.output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'version':version,'profile':result['profile'],'live_model':False}))
if __name__=='__main__':main()
