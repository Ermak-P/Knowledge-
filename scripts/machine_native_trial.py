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
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.kit:
        with tempfile.TemporaryDirectory(prefix='knowledge-native-machine-') as temporary:
            base = Path(temporary); machine = base / 'installed runtime'
            env = {**os.environ, 'XDG_CONFIG_HOME': str(base / 'config'), 'XDG_DATA_HOME': str(base / 'data'), 'XDG_CACHE_HOME': str(base / 'cache'), 'XDG_STATE_HOME': str(base / 'state')}
            process = subprocess.run([sys.executable, '-I', '-X', 'utf8', str(args.kit.absolute() / 'machine-install.py'), '--mcp-dir', str(machine)], env=env, capture_output=True, text=True, encoding='utf-8')
            (args.output / 'machine-install.log').write_text(process.stdout + process.stderr, encoding='utf-8')
            if process.returncode: raise RuntimeError('Private native fixture installation failed; inspect machine-install.log')
            process = subprocess.run([sys.executable, '-I', '-X', 'utf8', str(Path(__file__).resolve()), '--installation', str(machine), '--host', str(args.host.absolute()), '--output', str(args.output.absolute())], env=env)
            shutil.copytree(machine / 'logs', args.output / 'installation-logs', dirs_exist_ok=True)
            if process.returncode: raise RuntimeError('Native host acceptance failed; inspect diagnostics')
        return
    installation = args.installation.absolute()
    marker = json.loads((installation / 'knowledge-machine-install.json').read_text(encoding='utf-8'))
    config_home = Path(marker['host_home']).parent
    python = installation / ('bootstrap/Scripts/python.exe' if os.name == 'nt' else 'bootstrap/bin/python')
    requests = []
    class Provider(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            value = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append({'model': value.get('model'), 'stream': value.get('stream')})
            text = 'Controlled host transport fixture. Inspect the durable Knowledge result; no live-model quality claim.'
            chunk = {'id': 'fixture', 'object': 'chat.completion.chunk', 'created': 0, 'model': 'fixture', 'choices': [{'index': 0, 'delta': {'role': 'assistant', 'content': text}, 'finish_reason': None}]}
            ending = {**chunk, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]}
            body = ('data: ' + json.dumps(chunk) + '\n\ndata: ' + json.dumps(ending) + '\n\ndata: [DONE]\n\n').encode()
            self.send_response(200); self.send_header('Content-Type', 'text/event-stream'); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
    provider = ThreadingHTTPServer(('127.0.0.1', 0), Provider)
    threading.Thread(target=provider.serve_forever, daemon=True).start()
    result = {'installation': json.loads((installation / 'current.json').read_text(encoding='utf-8')), 'profile': 'native-opencode-2.4.0-controlled-provider', 'live_model': False, 'checks': {}}
    with tempfile.TemporaryDirectory(prefix='knowledge-native-') as tmp:
        base = Path(tmp); root = base / 'проект Ω'; root.mkdir()
        (root / 'Example.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>')
        (root / 'Example.cs').write_text('public class Example {}\n')
        for argv in (['git', 'init', str(root)], ['git', '-C', str(root), 'add', '.'], ['git', '-C', str(root), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'fixture']):
            subprocess.run(argv, check=True, capture_output=True)
        (root / 'opencode.json').write_text(json.dumps({'$schema': 'https://opencode.ai/config.json', 'update': 'disable', 'model': 'fixture/fixture', 'providers': {'fixture': {'package': '@opencode/ai/providers/openai-compatible', 'name': 'Controlled fixture', 'settings': {'baseURL': f'http://127.0.0.1:{provider.server_port}/v1', 'apiKey': 'fixture-not-a-secret'}, 'models': {'fixture': {'name': 'fixture', 'limit': {'context': 64000, 'output': 2048}}}}}}))
        subprocess.run(['git', '-C', str(root), 'add', 'opencode.json'], check=True, capture_output=True)
        subprocess.run(['git', '-C', str(root), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'controlled host configuration'], check=True, capture_output=True)
        env = {**os.environ, 'XDG_CONFIG_HOME': str(config_home), 'XDG_DATA_HOME': str(base / 'data'), 'XDG_STATE_HOME': str(base / 'state'), 'XDG_CACHE_HOME': str(base / 'cache'), 'npm_config_cache': str(base / 'npm'), 'NPM_CONFIG_CACHE': str(base / 'npm'), 'OPENCODE_DISABLE_AUTOUPDATE': '1', 'OPENCODE_DISABLE_MODELS_FETCH': '1'}
        env.pop('OPENCODE_DISABLE_DEFAULT_PLUGINS', None)
        result['version'] = subprocess.check_output([str(args.host), '--version'], env=env, text=True).strip().removeprefix('opencode v')
        assert result['version'] == '2.4.0'
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
            required = {'knowledge-init', 'knowledge-candidates-update', 'knowledge-candidates-push'}
            for _ in range(100):
                if required <= names: break
                time.sleep(.1)
                registered = api('/api/command' + location_query)['data']
                names = {value['name'] for value in registered}
            assert required <= names, names
            result['registration'] = [value for value in registered if value['name'] in required]
            result['checks']['global_commands_discovered'] = 'PASS'
            result['mcp'] = api('/api/mcp' + location_query)['data']
            knowledge = next(value for value in result['mcp'] if value['name'] == 'knowledge_machine')
            for _ in range(100):
                if knowledge['status']['status'] != 'pending': break
                time.sleep(.1)
                result['mcp'] = api('/api/mcp' + location_query)['data']
                knowledge = next(value for value in result['mcp'] if value['name'] == 'knowledge_machine')
            assert knowledge['status']['status'] == 'connected', result['mcp']
            result['checks']['global_mcp_connected'] = 'PASS'
            session = api('/api/session', {'location': {'directory': str(root)}, 'model': {'providerID': 'fixture', 'id': 'fixture'}})['data']
            def command(name, arguments=''):
                return api('/api/session/' + session['id'] + '/command', {'name': name, 'text': arguments})
            command('knowledge-init')
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
            messages = api('/api/session/' + session['id'] + '/message')
            (args.output / 'messages.json').write_text(json.dumps(messages, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            result['checks']['no_project_command_copy'] = 'PASS'
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
