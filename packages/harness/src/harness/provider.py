"""Non-streaming OpenAI-compatible HTTP tool calling; no external agent executable."""
import os
import socket
import time
import urllib.request
import urllib.error
from knowledge.util import canonical_json,loads,require,KnowledgeError


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def _complete(configuration,body,request_id,limits):
    data=canonical_json(body).encode();require(len(data)<=limits['context_bytes'],'context-budget-exceeded')
    headers={'Content-Type':'application/json','X-Harness-Request-ID':request_id}
    if configuration.get('key_env'):
        value=os.environ.get(configuration['key_env']);require(bool(value),'provider-credential-missing')
        headers['Authorization']='Bearer '+value
    req=urllib.request.Request(configuration['endpoint'],data=data,headers=headers,method='POST')
    started=time.monotonic()
    try:
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=limits['provider_seconds']) as response:
            raw=response.read(limits['response_bytes']+1)
        require(len(raw)<=limits['response_bytes'],'provider-response-too-large')
        value=loads(raw.decode('utf-8'))
        try:canonical_json(value)
        except KnowledgeError as e:raise KnowledgeError('invalid-provider-response') from e
        require(isinstance(value,dict),'invalid-provider-response')
        choices=value.get('choices');require(isinstance(choices,list) and len(choices)==1,'invalid-provider-choices')
        message=choices[0].get('message');require(isinstance(message,dict) and message.get('role')=='assistant','invalid-provider-message')
        require(set(message)<= {'role','content','tool_calls','reasoning_content','refusal'},'unsupported-provider-message-fields')
        calls=message.get('tool_calls',[]);require(isinstance(calls,list) and len(calls)<=12,'invalid-tool-call-list')
        content=message.get('content');require(content is None or isinstance(content,str),'invalid-provider-content')
        identifiers=set()
        for call in calls:
            require(isinstance(call,dict) and set(call)=={'id','type','function'} and call['type']=='function','invalid-tool-call')
            require(isinstance(call['id'],str) and 0<len(call['id'])<=120 and call['id'] not in identifiers,'duplicate-or-invalid-tool-id');identifiers.add(call['id'])
            f=call['function'];require(isinstance(f,dict) and set(f)=={'name','arguments'} and isinstance(f['name'],str) and isinstance(f['arguments'],str),'invalid-tool-function')
            args=loads(f['arguments']);require(isinstance(args,dict),'invalid-tool-arguments')
        clean={'role':'assistant','content':content}
        if calls:clean['tool_calls']=calls
        return dict(message=clean,usage=usage(value.get('usage')),duration=time.monotonic()-started,response_bytes=len(raw),response_id=value.get('id'))
    except (urllib.error.URLError,socket.timeout,TimeoutError,OSError) as e:
        raise KnowledgeError('provider-outcome-unknown') from e
    except (UnicodeError,TypeError,KeyError) as e:raise KnowledgeError('invalid-provider-response') from e


def usage(raw):
    if not isinstance(raw,dict):return {'coverage':'unknown','raw':None}
    prompt=raw.get('prompt_tokens');output=raw.get('completion_tokens')
    if type(prompt) is not int or prompt<0 or type(output) is not int or output<0:return {'coverage':'unknown','raw':raw}
    total=prompt+output
    if raw.get('total_tokens',total)!=total:return {'coverage':'unknown','raw':raw,'reason':'inconsistent-total'}
    # Cache/reasoning are subsets, never added to prompt+completion again.
    for group,key,maximum in (('prompt_tokens_details','cached_tokens',prompt),('completion_tokens_details','reasoning_tokens',output)):
        subset=raw.get(group,{});subset=subset.get(key) if isinstance(subset,dict) else None
        if subset is not None and (type(subset) is not int or not 0<=subset<=maximum):return {'coverage':'unknown','raw':raw,'reason':'invalid-subset'}
    return {'coverage':'reported','input':prompt,'output':output,'total':total,'cached_input':(raw.get('prompt_tokens_details') if isinstance(raw.get('prompt_tokens_details'),dict) else {}).get('cached_tokens'),
            'reasoning_output':(raw.get('completion_tokens_details') if isinstance(raw.get('completion_tokens_details'),dict) else {}).get('reasoning_tokens'),'raw':raw}


def complete(configuration,body,request_id,limits,cancelled=lambda:False):
    """An absolute client deadline; remote inference cancellation is not promised.

    A timed-out daemon request can only discard a late response. It cannot execute
    tools or change durable state. Its usage/outcome remains unknown and charged.
    """
    import threading
    done=threading.Event();box={}
    def request():
        try:box['value']=_complete(configuration,body,request_id,limits)
        except BaseException as error:box['error']=error
        finally:done.set()
    threading.Thread(target=request,daemon=True).start();deadline=time.monotonic()+limits['provider_seconds']
    while not done.wait(.02):
        if cancelled():raise KnowledgeError('cancelled')
        if time.monotonic()>=deadline:raise KnowledgeError('provider-outcome-unknown')
    if 'error' in box:
        error=box['error']
        if isinstance(error,KnowledgeError):raise error
        raise KnowledgeError('provider-parser-error') from error
    return box['value']
