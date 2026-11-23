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
