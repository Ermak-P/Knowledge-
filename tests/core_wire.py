"""Independent bidirectional stdio peer. No SDK teardown can mask an RPC result."""
import json
import queue
import subprocess
import tempfile
import threading
import time


class Wire:
    def __init__(self, argv, roots=None):
        self.errors=tempfile.TemporaryFile();self.messages=queue.Queue();self.roots=roots;self.received=[]
        self.process=subprocess.Popen([str(x) for x in argv],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.errors)
        def read():
            for line in self.process.stdout:self.messages.put(line)
            self.messages.put(None)
        self.thread=threading.Thread(target=read,daemon=True);self.thread.start()
    def send(self,value):
        self.process.stdin.write((json.dumps({'jsonrpc':'2.0',**value})+'\n').encode('utf-8'));self.process.stdin.flush()
    def request(self,identifier,method,params=None,timeout=30):
        self.send({'id':identifier,'method':method,'params':params or {}});deadline=time.monotonic()+timeout
        while True:
            raw=self.messages.get(timeout=max(.001,deadline-time.monotonic()))
            if raw is None:raise AssertionError('Server exited before '+method)
            value=json.loads(raw);self.received.append(value)
            if value.get('method')=='roots/list':
                self.send({'id':value['id'],'result':{'roots':[{'uri':p.as_uri()} for p in self.roots()]}})
            elif value.get('id')==identifier:
                if 'error' in value:raise AssertionError(value['error'])
                return value['result']
            elif 'id' in value:raise AssertionError('Unexpected protocol request: '+str(value))
    def initialize(self):
        value=self.request(101,'initialize',{'protocolVersion':'2025-11-25','clientInfo':{'name':'knowledge-reliability-peer','version':'1'},'capabilities':{'roots':{}} if self.roots else {}})
        self.send({'method':'notifications/initialized'});return value
    def tool(self,name,/,**args):
        value=self.request(200+len(self.received),'tools/call',{'name':name,'arguments':args})
        return json.loads(value['content'][0]['text'])
    def close(self):
        if not self.process.stdin.closed:self.process.stdin.close()
        try:self.process.wait(timeout=8)
        except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=8)
        self.thread.join(timeout=3);self.process.stdout.close();self.errors.seek(0)
        error=self.errors.read().decode('utf-8',errors='replace');self.errors.close();return error
