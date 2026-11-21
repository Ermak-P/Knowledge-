"""Installation binding fingerprints, independent of any agent or executor.

Only known files are read. No repository scan, model call, subprocess, credential
capture or daemon startup is performed here. User intent stays in operations.py.
"""
import hashlib
import os
from pathlib import Path
import platform
import sys
from .project import safe_path
from .util import digest,loads,require,KnowledgeError


def host():
    identity={'machine':platform.node(),'os':sys.platform}
    # UTS namespaces distinguish a container from its host without binding to a
    # short-lived process/mount namespace. Keep raw machine identifiers private.
    if sys.platform.startswith('linux'):
        for name in ('/etc/machine-id','/proc/self/ns/uts'):
            p=Path(name)
            if p.exists():identity[name]=os.readlink(p) if p.is_symlink() else p.read_text().strip()
    elif os.name=='nt':
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Cryptography') as key:
            identity['machine_guid']=winreg.QueryValueEx(key,'MachineGuid')[0]
    return {'machine':platform.node(),'os':sys.platform,'context':digest(identity)}


def fingerprint(path):
    # Approved tools may be OS-managed symlinks/hardlinks (notably venv Python).
    # We only read the resolved regular file and compare its bytes before use.
    p=Path(path).resolve(strict=True);require(p.is_file(),'binding-input-unavailable',str(p))
    require(p.stat().st_size<=128*1024*1024,'binding-input-too-large',str(p))
    value=hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):value.update(block)
    return value.hexdigest()


def read_object(path):
    safe_path(path)
    if not path.exists():return None
    require(path.is_file() and path.stat().st_size<=1024*1024,'invalid-docker-context-config')
    value=loads(path.read_text(encoding='utf-8'));require(isinstance(value,dict),'invalid-docker-context-config')
    return value


def docker_selection(docker):
    base=Path.home()/'.docker'
    # Broker commands pass --config/--context explicitly and never inherit
    # DOCKER_HOST/DOCKER_CONTEXT/DOCKER_CONFIG from a model or ambient shell.
    config=read_object(base/'config.json') or {}
    context=docker.get('context') or config.get('currentContext') or 'default'
    require(isinstance(context,str) and 0<len(context)<=128 and not context.startswith('-'),'invalid-docker-context')
    scheme='npipe' if os.name=='nt' else 'unix'
    endpoint='npipe:////./pipe/docker_engine' if os.name=='nt' else 'unix:///var/run/docker.sock'
    if context!='default':
        key=hashlib.sha256(context.encode()).hexdigest()
        meta=read_object(base/'contexts/meta'/key/'meta.json')
        require(meta and meta.get('Name')==context,'docker-context-unavailable')
        endpoints=meta.get('Endpoints',{});require(isinstance(endpoints,dict) and isinstance(endpoints.get('docker'),dict),'invalid-docker-context-config')
        endpoint=endpoints['docker'].get('Host','');require(isinstance(endpoint,str),'invalid-docker-context-config')
        scheme=endpoint.split(':',1)[0]
        require(scheme in ('unix','npipe'),'remote-docker-binding-unsupported')
        require(endpoint.startswith('unix:///') if scheme=='unix' else endpoint.lower().startswith(('npipe:////./pipe/','npipe:////localhost/pipe/')),'remote-docker-binding-unsupported')
    return {'config_root':str(base),'context':context,'endpoint_hash':digest(endpoint),'transport':scheme}


def snapshot(behavior,root):
    if behavior['adapter']=='preserve-format':return {'version':1,'state':'portable','files':{}}
    try:
        procedure=behavior['procedure'];argv=procedure['check']['argv'];files={}
        paths=[argv[0]]
        for arg in argv[1:]:
            p=Path(arg)
            if p.is_absolute() and p.is_file():paths.append(str(p))
            elif not arg.startswith('-') and p.suffix.lower() in ('.py','.ps1','.sh'):
                paths.append(str(Path(root)/p))
        value={'version':1,'state':'bound','host':host(),'files':files,'procedure':digest(procedure)}
        if 'docker' in procedure:
            docker=procedure['docker'];paths.append(docker['executable'])
            value['docker']=docker_selection(docker)
            if 'compose_file' in docker:
                require({'project_name','env_file'}<=set(docker),'compose-identity-required')
                paths.extend((docker['compose_file'],docker['env_file']))
        for path in dict.fromkeys(paths):files[str(Path(path).absolute())]=fingerprint(path)
        return value
    except (KnowledgeError,OSError,ValueError) as error:
        return {'version':1,'state':'unavailable','reason':getattr(error,'code','binding-input-unavailable')}


def validate_saved(saved,behavior,root):
    require(isinstance(saved,dict),'instruction-binding-revalidation-required')
    current=snapshot(behavior,root)
    require(saved.get('state') in ('bound','portable'),'instruction-binding-unavailable',saved.get('reason'))
    require(current.get('state')==saved.get('state'),'instruction-binding-stale',current.get('reason'))
    require(current.get('host')==saved.get('host'),'instruction-binding-environment-changed')
    require(current==saved,'instruction-binding-stale')
    return current
