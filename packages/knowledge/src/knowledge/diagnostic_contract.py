"""Section-specific arguments shared by diagnostics and operational help."""
import re
from typing import Literal

from .util import require

Section = Literal['failures', 'coverage', 'reconciliation', 'impact', 'policy', 'identity', 'scans',
                  'checkpoint', 'duplicates', 'candidates', 'candidate', 'plan-progress', 'plan-dispositions']
SECTIONS = {
    'failures': ('Extraction failures and source exclusions', ('scan_id',)),
    'coverage': ('Per-file extraction coverage', ('scan_id',)),
    'reconciliation': ('Claim freshness and negative evidence gaps for a current source snapshot', ('scan_id',)),
    'impact': ('Changes and affected claims', ('scan_id', 'collection')),
    'policy': ('Effective source extraction policy', ('scan_id',)),
    'identity': ('Missing compatible analysis and ambiguous identities', ('scan_id',)),
    'scans': ('Durable scan history and scan IDs', ('scan_id',)),
    'checkpoint': ('Current job and checkpoint compatibility', ()),
    'duplicates': ('Duplicate groups or the candidates in a selected group', ('group',)),
    'candidates': ('Discover candidate IDs in the project queue, a scan, or a plan', ('scan_id', 'plan')),
    'candidate': ('Read a candidate or one operation as paged JSON text', ('candidate', 'operation', 'plan')),
    'plan-progress': ('Current plan job progress', ()),
    'plan-dispositions': ('Candidate dispositions in a prepared plan', ('plan',)),
}
IDENTIFIERS = {
    'scan_id': ('64 lowercase hexadecimal scan ID', {'section': 'scans'}),
    'candidate': ('candidate ID returned by candidate discovery', {'section': 'candidates'}),
    'plan': ('sha256: fingerprint of a canonical plan', {'section': 'plan-progress'}),
    'group': ('duplicate group ID', {'section': 'duplicates'}),
    'operation': ('zero-based candidate operation index', {'section': 'candidate', 'candidate': '<candidate ID>'}),
}


def example(section):
    return {'section': section, **({'candidate': '<candidate ID>'} if section == 'candidate' else {})}


def contracts():
    return {section: {'purpose': purpose, 'required': ['candidate'] if section == 'candidate' else [],
                      'optional': ['scope', 'cursor', 'limit', 'max_bytes', *(key for key in fields if key != 'candidate')],
                      'forbidden': sorted((set(IDENTIFIERS) | {'collection'}) - set(fields)),
                      'identifiers': {key: {'type': IDENTIFIERS[key][0], 'discover': IDENTIFIERS[key][1]}
                                      for key in fields if key in IDENTIFIERS},
                      'pagination': 'character offset, limit unused' if section == 'candidate' else 'row offset',
                      'example': example(section)}
            for section, (purpose, fields) in SECTIONS.items()}


def validate(scope, section, cursor, limit, max_bytes, **arguments):
    require(scope in ('full', 'incremental'), 'invalid-diagnostic-section',
            {'argument': 'scope', 'supported_values': ['full', 'incremental']})
    require(section in SECTIONS, 'invalid-diagnostic-section',
            {'argument': 'section', 'supported_values': list(SECTIONS)})
    hint = {'section': section, 'example': example(section), 'retryable_with_corrected_arguments': True}
    require(type(cursor) is int and cursor >= 0 and type(limit) is int and 1 <= limit <= 100,
            'invalid-diagnostic-page', {**hint, 'expected': 'cursor >= 0 and 1 <= limit <= 100'})
    require(type(max_bytes) is int and 256 <= max_bytes <= 1000000, 'invalid-byte-budget',
            {'argument': 'max_bytes', 'minimum': 256, 'maximum': 1000000})
    allowed = SECTIONS[section][1]
    supplied = {key for key, value in arguments.items() if value is not None}
    unexpected = supplied - set(allowed)
    if section == 'candidates' and {'scan_id', 'plan'} <= supplied:
        unexpected.add('plan')
    require(not unexpected, 'invalid-diagnostic-arguments',
            {**hint, 'unexpected_arguments': sorted(unexpected), 'optional_arguments': list(allowed),
             **({'next_invocation': {'section': 'candidates', 'scan_id': arguments['scan_id']}}
                if section == 'candidate' and 'scan_id' in unexpected else {})})
    if section == 'candidate':
        require('candidate' in supplied, 'invalid-candidate-identifier',
                {**hint, 'missing_arguments': ['candidate'], 'expected_identifier': IDENTIFIERS['candidate'][0],
                 'next_invocation': {'section': 'candidates'}})
    for key, value in arguments.items():
        if value is None:
            continue
        if key == 'operation':
            valid = type(value) is int and value >= 0
        elif key == 'scan_id':
            valid = isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value)
        elif key == 'plan':
            valid = isinstance(value, str) and re.fullmatch('sha256:[0-9a-f]{64}', value)
        else:
            valid = isinstance(value, str) and 0 < len(value) <= 256
        expected, discover = IDENTIFIERS.get(key, ('impact collection name', {'section': 'impact'}))
        require(valid, {'candidate': 'invalid-candidate-identifier', 'operation': 'invalid-candidate-operation',
                        'plan': 'invalid-fingerprint'}.get(key, 'invalid-diagnostic-' + key.replace('_', '-')),
                {**hint, 'argument': key, 'expected_identifier': expected, 'next_invocation': discover})
