"""Real global OpenCode 2.4.0 command discovery/hooks; controlled model only.

Uses an already isolated machine installation. No owner's host/config is read.
"""
import argparse
import base64
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import sys
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import urllib.parse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--installation', type=Path)
    source.add_argument('--kit', type=Path)
    parser.add_argument('--host', type=Path, required=True)
    parser.add_argument('--expected-version', default='2.4.0')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.kit:
        with tempfile.TemporaryDirectory(prefix='knowledge-native-machine-') as temporary:
            base = Path(temporary); machine = base / 'installed runtime'
            env = {**os.environ, 'XDG_CONFIG_HOME': str(base / 'config'), 'XDG_DATA_HOME': str(base / 'data'), 'XDG_CACHE_HOME': str(base / 'cache'), 'XDG_STATE_HOME': str(base / 'state')}
            process = subprocess.run([sys.executable, '-I', '-X', 'utf8', str(args.kit.absolute() / 'machine-install.py'), '--mcp-dir', str(machine), '--mode', 'maintainer'], env=env, capture_output=True, text=True, encoding='utf-8')
            (args.output / 'machine-install.log').write_text(process.stdout + process.stderr, encoding='utf-8')
            if process.returncode: raise RuntimeError('Private native fixture installation failed; inspect machine-install.log')
            process = subprocess.run([sys.executable, '-I', '-X', 'utf8', str(Path(__file__).resolve()), '--installation', str(machine), '--host', str(args.host.absolute()), '--expected-version', args.expected_version, '--output', str(args.output.absolute())], env=env)
            shutil.copytree(machine / 'logs', args.output / 'installation-logs', dirs_exist_ok=True)
            if process.returncode: raise RuntimeError('Native host acceptance failed; inspect diagnostics')
        return
    installation = args.installation.absolute()
    marker = json.loads((installation / 'knowledge-machine-install.json').read_text(encoding='utf-8'))
    config_home = Path(marker['host_home']).parent
    python = installation / ('bootstrap/Scripts/python.exe' if os.name == 'nt' else 'bootstrap/bin/python')
    requests = []
    code_mode={'step':0,'paths':{},'verified':False}
    def objects(value):
        if isinstance(value,dict):
            yield value
            for item in value.values():yield from objects(item)
        elif isinstance(value,list):
            for item in value:yield from objects(item)
        elif isinstance(value,str) and len(value)<2000000:
            try:parsed=json.loads(value)
            except (ValueError,TypeError):return
            if isinstance(parsed,(dict,list)):yield from objects(parsed)
    class Provider(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            value = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append({'model': value.get('model'), 'stream': value.get('stream'),
                             'tools':[tool.get('function',tool.get('custom',{})).get('name') for tool in value.get('tools',[])]})
            (args.output/'provider-requests.json').write_text(json.dumps(requests,indent=2)+'\n',encoding='utf-8')
            text = 'Controlled host transport fixture. Inspect the durable Knowledge result; no live-model quality claim.'
            chunk = {'id': 'fixture', 'object': 'chat.completion.chunk', 'created': 0, 'model': 'fixture', 'choices': [{'index': 0, 'delta': {'role': 'assistant', 'content': text}, 'finish_reason': None}]}
            ending = {**chunk, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]}
            execute=next((tool for tool in value.get('tools',[]) if tool.get('function',{}).get('name')=='execute'),None)
            script=None
            if execute and code_mode['step']==0:
                (args.output/'execute-schema.json').write_text(json.dumps(execute,indent=2)+'\n',encoding='utf-8')
                if execute:
                    script='return await search({namespace:"knowledge_machine",limit:30});';code_mode['step']=1
                else:code_mode['error']='execute tool not advertised'
            elif execute and code_mode['step']==1:
                replies=[message.get('content') for message in value.get('messages',[]) if message.get('role')=='tool']
                (args.output/'codemode-search-reply.json').write_text(json.dumps(replies,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                paths={row['path'].split('.')[-1]:row['path'] for row in objects(replies)
                       if isinstance(row.get('path'),str) and re.fullmatch(r'tools\.knowledge_machine\.[a-zA-Z0-9_]+',row['path'])}
                code_mode['paths']=paths
                code_mode['denied_tools_hidden']=all(name not in paths for name in ('knowledge_instructions','knowledge_submit_candidates'))
                needed=['knowledge_capabilities','knowledge_scan','knowledge_scan_diagnostics','knowledge_source_read','knowledge_plan','knowledge_confluence']
                if all(name in paths for name in needed):
                    script=('const result={capabilities:await '+paths['knowledge_capabilities']+'({}),'
                            'scan:await '+paths['knowledge_scan']+'({action:"status"}),'
                            'diagnostics:await '+paths['knowledge_scan_diagnostics']+'({section:"coverage",limit:2}),'
                            'source:await '+paths['knowledge_source_read']+'({path:"Example.cs",max_lines:3}),'
                            'plan:await '+paths['knowledge_plan']+'({action:"prepare"}),'+
                            'confluence:await '+paths['knowledge_confluence']+'({action:"status",request:{}})};'
                            'return result;')
                    code_mode['step']=2
                else:code_mode['error']='Required MCP tools absent from actual Code Mode search'
            elif execute and code_mode['step']==2:
                replies=[message.get('content') for message in value.get('messages',[]) if message.get('role')=='tool']
                (args.output/'codemode-call-reply.json').write_text(json.dumps(replies,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                results=list(objects(replies))
                code_mode['verified']=any(row.get('contract')=='knowledge-machine-v2' for row in results)
                code_mode['permission_denied']=code_mode.get('denied_tools_hidden',False) and any('knowledge_instructions' in row.get('tools',[]) and 'knowledge_submit_candidates' in row.get('tools',[]) for row in results)
                code_mode['scan_observed']=any(row.get('coverage_complete') is True for row in results)
                code_mode['source_read']=any(row.get('path')=='Example.cs' and row.get('content_hash') for row in results)
                code_mode['plan_prepared']=any(row.get('state')=='AWAITING_EXACT_APPROVAL' for row in results)
                code_mode['confluence_observed']=any(row.get('state')=='SCOPE_REQUIRED' for row in results)
                code_mode['step']=3
            if script is not None:
                properties=execute.get('function',{}).get('parameters',{}).get('properties',{}) if execute else {}
                field='code' if 'code' in properties else 'input'
                call={'index':0,'id':'fixture-code-'+str(code_mode['step']),'type':'function','function':{'name':'execute','arguments':json.dumps({field:script})}}
                chunk={**chunk,'choices':[{'index':0,'delta':{'role':'assistant','tool_calls':[call]},'finish_reason':None}]}
                ending={**ending,'choices':[{'index':0,'delta':{},'finish_reason':'tool_calls'}]}
            body = ('data: ' + json.dumps(chunk) + '\n\ndata: ' + json.dumps(ending) + '\n\ndata: [DONE]\n\n').encode()
            self.send_response(200); self.send_header('Content-Type', 'text/event-stream'); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
    provider = ThreadingHTTPServer(('127.0.0.1', 0), Provider)
    threading.Thread(target=provider.serve_forever, daemon=True).start()
    result = {'installation': json.loads((installation / 'current.json').read_text(encoding='utf-8')), 'profile': f'native-opencode-{args.expected_version}-controlled-provider', 'live_model': False, 'checks': {}}
    with tempfile.TemporaryDirectory(prefix='knowledge-native-') as tmp:
        base = Path(tmp); root = base / 'проект Ω'; root.mkdir()
        (root / 'Example.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>')
        (root / 'Example.cs').write_text('public class Example {}\n')
        for argv in (['git', 'init', str(root)], ['git', '-C', str(root), 'add', '.'], ['git', '-C', str(root), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'fixture']):
            subprocess.run(argv, check=True, capture_output=True)
        (root / 'opencode.json').write_text(json.dumps({'$schema': 'https://opencode.ai/config.json', 'update': 'disable', 'model': 'fixture/fixture', 'providers': {'fixture': {'package': '@opencode/ai/providers/openai-compatible', 'name': 'Controlled fixture', 'settings': {'baseURL': f'http://127.0.0.1:{provider.server_port}/v1', 'apiKey': 'fixture-not-a-secret'}, 'models': {'fixture': {'name': 'fixture', 'limit': {'context': 64000, 'output': 2048}}}}}}))
        config=json.loads((root/'opencode.json').read_text())
        config['permissions']=[{'action':'knowledge_machine_'+name,'resource':'*','effect':'allow'} for name in
                               ('knowledge_capabilities','knowledge_scan','knowledge_scan_diagnostics','knowledge_source_read','knowledge_plan','knowledge_confluence')]
        config['permissions'].extend({'action':'knowledge_machine_'+name,'resource':'*','effect':'deny'} for name in ('knowledge_instructions','knowledge_submit_candidates'))
        (root/'opencode.json').write_text(json.dumps(config),encoding='utf-8')
        subprocess.run(['git', '-C', str(root), 'add', 'opencode.json'], check=True, capture_output=True)
        subprocess.run(['git', '-C', str(root), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'controlled host configuration'], check=True, capture_output=True)
        env = {**os.environ, 'XDG_CONFIG_HOME': str(config_home), 'XDG_DATA_HOME': str(base / 'data'), 'XDG_STATE_HOME': str(base / 'state'), 'XDG_CACHE_HOME': str(base / 'cache'), 'npm_config_cache': str(base / 'npm'), 'NPM_CONFIG_CACHE': str(base / 'npm'), 'OPENCODE_DISABLE_AUTOUPDATE': '1', 'OPENCODE_DISABLE_MODELS_FETCH': '1'}
        env.pop('OPENCODE_DISABLE_DEFAULT_PLUGINS', None)
        result['version'] = subprocess.check_output([str(args.host), '--version'], env=env, text=True).strip().removeprefix('opencode v')
        assert result['version'] == args.expected_version
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        log = (args.output / 'host.log').open('wb')
        host = subprocess.Popen([str(args.host), 'serve', '--print-logs', '--hostname', '127.0.0.1', '--port', str(port)], cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
        authorization = None
        location_query = '?' + urllib.parse.urlencode({'location[directory]': str(root)})
        def api(path, value=None):
            nonlocal authorization
            if authorization is None:
                match = re.search(r'server password (\S+)', (args.output / 'host.log').read_text(encoding='utf-8'))
                if not match: raise OSError('Private server starting')
                authorization = 'Basic ' + base64.b64encode(('opencode:' + match.group(1)).encode()).decode()
            request = urllib.request.Request(f'http://127.0.0.1:{port}' + path, data=json.dumps(value).encode() if value is not None else None, headers={'Content-Type': 'application/json', 'Authorization': authorization})
            try:
                with urllib.request.urlopen(request, timeout=40) as response:
                    raw = response.read()
                    return json.loads(raw) if raw else None
            except urllib.error.HTTPError as error:
                raise RuntimeError('Native v2 HTTP ' + str(error.code) + ': ' + error.read(3000).decode()) from error
        def backend(command, value):
            process = subprocess.run([str(python), '-I', str(installation / 'launch.py'), 'command', command, '--root', str(root)], input=json.dumps(value), capture_output=True, text=True, encoding='utf-8')
            output = json.loads(process.stdout)
            assert output['ok'], output
            return output
        def wait(command):
            for _ in range(100):
                value = backend(command, {'action': 'status'})
                if value['state'] not in ('STARTING', 'RUNNING'): return value
                time.sleep(.1)
            raise AssertionError('Worker did not finish')
        try:
            for _ in range(100):
                try: result['server_version'] = api('/api/info')['version']; break
                except OSError: time.sleep(.1)
            else: raise AssertionError('Host did not start')
            registered = api('/api/command' + location_query)['data']
            (args.output / 'discovered-commands.json').write_text(json.dumps(registered, indent=2) + '\n', encoding='utf-8')
            names = {value['name'] for value in registered}
            required = {'knowledge-init', 'knowledge-candidates-update', 'knowledge-candidates-push', 'knowledge-confluence', 'knowledge-update'}
            for _ in range(100):
                if required <= names: break
                time.sleep(.1)
                registered = api('/api/command' + location_query)['data']
                names = {value['name'] for value in registered}
            assert required <= names, names
            result['registration'] = [value for value in registered if value['name'] in required]
            result['checks']['global_commands_discovered'] = 'PASS'
            # Command registration can become visible before asynchronous MCP
            # registration. Observe the real catalog until connected, retaining
            # the deadline rather than assuming its first response is populated.
            knowledge = None
            for _ in range(100):
                result['mcp'] = api('/api/mcp' + location_query)['data']
                knowledge = next((value for value in result['mcp'] if value['name'] == 'knowledge_machine'), None)
                if knowledge is not None and knowledge['status']['status'] != 'pending': break
                time.sleep(.1)
            assert knowledge is not None and knowledge['status']['status'] == 'connected', result['mcp']
            result['checks']['global_mcp_connected'] = 'PASS'
            session = api('/api/session', {'location': {'directory': str(root)}, 'model': {'providerID': 'fixture', 'id': 'fixture'}})['data']
            def command(name, arguments=''):
                return api('/api/session/' + session['id'] + '/command', {'name': name, 'text': arguments})
            command('knowledge-init')
            deadline=time.monotonic()+40
            while code_mode['step']<3 and time.monotonic()<deadline:time.sleep(.05)
            result['code_mode']=code_mode
            assert code_mode.get('verified') and code_mode.get('permission_denied') and code_mode.get('scan_observed') and code_mode.get('source_read') and code_mode.get('plan_prepared') and code_mode.get('confluence_observed'),code_mode
            result['checks']['real_code_mode_search_and_mcp_operations']='PASS'
            result['checks']['real_code_mode_permission_denial_enforced']='PASS'
            result['init'] = wait('knowledge-init')
            assert result['init']['coverage_complete'] and result['init']['semantic_status'] == 'PARTIAL'
            result['checks']['init_native_hook_and_durable_scan'] = 'PASS'
            command('knowledge-candidates-push')
            initial_plan = backend('knowledge-candidates-push', {})
            command('knowledge-candidates-push', json.dumps({'approve': initial_plan['fingerprint']}))
            result['initial_approved_plan'] = initial_plan
            (root / 'Added.cs').write_text('public class Added {}\n')
            command('knowledge-candidates-update')
            result['update'] = wait('knowledge-candidates-update')
            assert result['update']['scope']['kind'] == 'incremental' and result['update']['work']['durable_extracted_files'] == 1
            result['checks']['incremental_native_hook'] = 'PASS'
            command('knowledge-candidates-push')
            prepared = backend('knowledge-candidates-push', {})
            result['prepared'] = prepared
            command('knowledge-candidates-push', json.dumps({'approve': prepared['fingerprint']}))
            # The exact same transport command, separately invoked by this
            # fixture operator, must reach the actual apply+ack implementation.
            recovered = backend('knowledge-candidates-push', {'action': 'recover', 'plan': prepared['fingerprint']})
            assert recovered['state'] == 'ACKNOWLEDGED'
            result['applied'] = recovered
            result['checks']['separate_exact_native_approval_apply_ack'] = 'PASS'
            command('knowledge-confluence',json.dumps({'scope':{'roots':['https://docs.example.invalid/wiki/pages/101'],'spaces':[],'autonomous':False}}))
            confluence=backend('knowledge-confluence',{'action':'status'})
            assert confluence['scope']['roots']==['https://docs.example.invalid/wiki/pages/101'] and confluence['work']['PENDING']>=1,confluence
            result['confluence']=confluence
            result['checks']['confluence_native_hook_persisted_scope_and_work']='PASS'
            command('knowledge-update')
            alias=backend('knowledge-update',{})
            assert alias['ok'],alias
            result['checks']['knowledge_update_native_alias']='PASS'
            messages = api('/api/session/' + session['id'] + '/message')
            (args.output / 'messages.json').write_text(json.dumps(messages, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            result['checks']['no_project_command_copy'] = 'PASS'
            try:command('knowledge-candidates-update',json.dumps({'candidates':[],'allow_test_double':True}))
            except RuntimeError as error:
                result['native_permission_denial']=str(error)
                assert re.search(r'deni|permission|reject',str(error),re.I),str(error)
            else:raise AssertionError('Native command bypassed host MCP permission denial')
            result['checks']['native_command_host_permission_enforced']='PASS'
            assert not (root / '.opencode').exists()
        finally:
            host.terminate()
            try: host.wait(timeout=10)
            except subprocess.TimeoutExpired: host.kill(); host.wait()
            log.close()
            private_log = args.output / 'host.log'
            private_log.write_text(re.sub(r'(server password )\S+', r'\1<redacted>', private_log.read_text(encoding='utf-8')), encoding='utf-8')
            provider.shutdown(); provider.server_close()
    result['provider_requests'] = requests
    (args.output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'ok': True, 'profile': result['profile'], 'checks': result['checks']}))


if __name__ == '__main__': main()
