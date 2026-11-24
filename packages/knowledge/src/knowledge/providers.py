"""Resolve an explicit shared provider; effective bytes participate in authority.

Inline providers remain a legacy Harness contract. Shared configurations must
specify evidence explicitly: demo settings can never silently become live.
"""
import copy
import re
from pathlib import Path
from urllib.parse import urlsplit
from .project import safe_path
from .util import require, loads, digest


def validate(provider, shared=False):
    require(isinstance(provider, dict) and {'endpoint', 'model'} <= set(provider)
            <= {'endpoint', 'model', 'key_env', 'evidence'}, 'invalid-provider-config')
    require(not shared or 'evidence' in provider, 'shared-provider-evidence-required')
    require(isinstance(provider['endpoint'], str) and 0 < len(provider['endpoint']) <= 2000, 'invalid-provider-endpoint')
    endpoint = urlsplit(provider['endpoint'])
    require(endpoint.scheme in ('http', 'https') and endpoint.hostname and not endpoint.username
            and not endpoint.password and not endpoint.query and not endpoint.fragment
            and endpoint.path.endswith('/chat/completions'), 'invalid-provider-endpoint')
    require(isinstance(provider['model'], str) and 0 < len(provider['model']) <= 200, 'invalid-model')
    require(provider.get('evidence', 'live') in ('test-double', 'live'), 'invalid-provider-evidence')
    if 'key_env' in provider:
        require(isinstance(provider['key_env'], str) and re.fullmatch('[A-Za-z_][A-Za-z0-9_]*', provider['key_env']), 'invalid-key-binding')
        require(endpoint.scheme == 'https' or endpoint.hostname in ('localhost', '127.0.0.1', '::1'), 'credentials-require-tls')
    return provider


def shared(path):
    path = Path(path)
    require(path.is_absolute(), 'provider-reference-must-be-absolute')
    safe_path(path)
    value = loads(path.read_text(encoding='utf-8'))
    require(isinstance(value, dict) and set(value) == {'provider'}, 'invalid-shared-provider')
    validate(value['provider'], shared=True)
    return value['provider'], {'path': str(path), 'hash': digest(value)}


def semantic_preflight(provider, allow_test_double=False, proposals=None):
    require(type(allow_test_double) is bool, 'invalid-test-mode-authorization')
    test=provider.get('evidence')=='test-double'
    require(not test or allow_test_double, 'test-double-semantic-authorization-required',
            {'provider':provider['endpoint'],'model':provider['model'],'evidence':provider.get('evidence'),
             'next_action':'Correct the shared provider for production, or explicitly authorize test mode. Lexical scanning does not call this provider.'})
    if test and proposals is not None:
        require(isinstance(proposals,list) and all(isinstance(proposal,dict) for proposal in proposals),'invalid-candidate-batch')
        for proposal in proposals:
            for change in proposal.get('operations',[]):
                payload=change.get('payload')
                require(not (change.get('kind')=='claims' and payload and payload.get('status')=='CONFIRMED'),
                        'test-double-cannot-produce-confirmed-semantic-claims')
    return {'ok':True,'provider':provider['endpoint'],'model':provider['model'],'evidence':provider.get('evidence','live'),
            'test_mode':test,'production_verified':False,'provider_contacted':False}


SEMANTIC_PREFIX='semantic-provider-v1:'


def validate_semantic_binding(binding):
    require(isinstance(binding,dict) and set(binding)=={'version','provider_ref','model','evidence','contract'}
            and binding['version']==1 and binding['evidence'] in ('live','test-double')
            and isinstance(binding['model'],str) and binding['contract']=='reviewed-v2-v1','invalid-semantic-binding')
    reference=binding['provider_ref']
    require(isinstance(reference,dict) and set(reference)=={'path','hash'} and isinstance(reference['path'],str)
            and Path(reference['path']).is_absolute() and isinstance(reference['hash'],str)
            and re.fullmatch('[a-f0-9]{64}',reference['hash']),'invalid-semantic-provider-reference')
    return binding


def semantic_bindings(db):
    result={}
    for key,payload in db.execute("SELECT key,value FROM metadata WHERE key LIKE 'semantic-provider-v1:%'"):
        cid=key[len(SEMANTIC_PREFIX):]
        require(re.fullmatch('[a-f0-9]{64}',cid) and db.execute('SELECT 1 FROM queue WHERE id=?',(cid,)).fetchone(),'corrupt-semantic-binding')
        result[cid]=validate_semantic_binding(loads(payload))
    return result


def verify_semantic_bindings(db,candidates):
    bindings={cid:binding for cid,binding in semantic_bindings(db).items() if cid in candidates}
    checked={}
    for binding in bindings.values():
        reference=binding['provider_ref'];path=reference['path']
        if path not in checked:checked[path]=shared(path)
        provider,current=checked[path]
        require(current==reference and provider['model']==binding['model'] and provider['evidence']==binding['evidence'],
                'semantic-provider-drift-reanalysis-required',{'provider_ref':path,'next_action':'Reanalyze under the current provider; preserve previous decisions and do not transfer approval.'})
    return bindings


def resolve_runner(value):
    require(isinstance(value, dict), 'invalid-runner-config')
    if 'provider_ref' in value:
        require('provider' not in value and 'provider_reference' not in value, 'ambiguous-provider-configuration')
        provider, binding = shared(value['provider_ref'])
        value = copy.deepcopy(value)
        del value['provider_ref']
        value.update(provider=provider, provider_reference=binding)
    elif 'provider_reference' in value:
        binding = value['provider_reference']
        require(isinstance(binding, dict) and set(binding) == {'path', 'hash'}, 'invalid-provider-reference')
        provider, current = shared(binding['path'])
        require(current == binding and provider == value.get('provider'), 'provider-configuration-drift')
    return value
