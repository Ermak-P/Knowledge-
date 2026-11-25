"""Provided Contract v1 validator; retained for semantic compatibility. Filesystem installer removed; semantic validation retained."""
import argparse
from contextlib import ExitStack
import hashlib
from datetime import date, datetime
import json
from pathlib import Path
import re
import sys


VERSION = '1.0.0'
MANIFEST = {
    'format': 'universal-architecture-kb', 'format_version': '1.0.0',
    'schema_versions': {'claim': '1.0.0', 'evidence': '1.0.0', 'relationship': '1.0.0'},
    'capabilities': ['init', 'validate', 'check-scaffold', 'version'],
    'storage': {'manifest': 'JSON-compatible YAML 1.2', 'records': 'UTF-8 JSON, one object per file',
                'documentation': 'Markdown'},
}
SCHEMA_HASHES = {
    'claim': '43c3c811e9a9f2b32dfcbeba1519d5a4f0024ca36378b457aeafcbf63da9d2cc',
    'evidence': '984f980ab218359871f4fc8424b748cc093688c42b762d07e0e225170c768bcf',
    'relationship': '31ee6cb31d25adca58ece3bf8c6db08660f910c8eb040b84f24c39740be5d95a',
}
CONFLUENCE_EVIDENCE_SCHEMA='c3dbbcd09efd0f82e979b1a047c9941590f0b5d7d1a7838c65ce13eefca9c2c8'


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result

    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('invalid JSON: ' + value)))


def linked(path):
    return path.is_symlink() or path.is_junction()


def check_paths(base):
    if linked(base):
        raise ValueError('.ai must not be a symbolic link or junction')
    if base.exists():
        if not base.is_dir():
            raise ValueError('.ai must be a directory')
        for path in sorted(base.rglob('*')):
            if linked(path):
                raise ValueError('symbolic links and junctions are not allowed: ' + str(path.relative_to(base)))


def schema_errors(value, schema, location='$'):
    errors = []
    if 'anyOf' in schema:
        if not any(not schema_errors(value, option, location) for option in schema['anyOf']):
            errors.append(location + ': no allowed alternative matches')
        return errors
    types = {'object': dict, 'array': list, 'string': str, 'null': type(None),'integer':int}
    if schema.get('type')=='integer' and type(value) is not int:return [location+': expected integer']
    if 'type' in schema and not isinstance(value, types[schema['type']]):
        return [location + ': expected ' + schema['type']]
    if 'enum' in schema and value not in schema['enum']:
        errors.append(location + ': value outside enumeration')
    if type(value) is int and 'minimum' in schema and value<schema['minimum']:errors.append(location+': below minimum')
    if isinstance(value, dict):
        for key in schema.get('required', []):
            if key not in value:
                errors.append(location + ': missing ' + key)
        properties = schema.get('properties', {})
        for key in sorted(value):
            if key in properties:
                errors.extend(schema_errors(value[key], properties[key], location + '.' + key))
            elif schema.get('additionalProperties') is False:
                errors.append(location + ': unknown field ' + key)
    if isinstance(value, list):
        if schema.get('uniqueItems') and len({json.dumps(item, sort_keys=True) for item in value}) != len(value):
            errors.append(location + ': duplicate array entries')
        for index, item in enumerate(value):
            errors.extend(schema_errors(item, schema.get('items', {}), f'{location}[{index}]'))
    if isinstance(value, str):
        if len(value) < schema.get('minLength', 0):
            errors.append(location + ': string too short')
        if 'pattern' in schema and not re.search(schema['pattern'], value):
            errors.append(location + ': invalid string pattern')
        try:
            if schema.get('format') == 'date':
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                    raise ValueError()
                date.fromisoformat(value)
            if schema.get('format') == 'date-time':
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})', value):
                    raise ValueError()
                datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            errors.append(location + ': invalid ' + schema['format'])
    return errors


def check_schema(schema):
    if not isinstance(schema, dict):
        raise ValueError('schema must be an object')
    supported = {'$schema', 'type', 'required', 'properties', 'additionalProperties', 'enum',
                 'anyOf', 'items', 'uniqueItems', 'minLength', 'pattern', 'format','minimum'}
    if set(schema) - supported:
        raise ValueError('unsupported schema keywords: ' + ', '.join(sorted(set(schema) - supported)))
    if 'type' in schema and schema['type'] not in ['object', 'array', 'string', 'null','integer']:
        raise ValueError('unsupported schema type')
    if 'pattern' in schema:
        re.compile(schema['pattern'])
    for child in schema.get('properties', {}).values():
        check_schema(child)
    for child in schema.get('anyOf', []):
        check_schema(child)
    if 'items' in schema:
        check_schema(schema['items'])


def manifest_errors(base):
    value = read_json(base / 'manifest.yaml')
    if value != MANIFEST:
        return ['manifest.yaml: unsupported or malformed manifest; expected format and schema versions 1.0.0']
    return []


def validate(base):
    errors = manifest_errors(base)
    if errors:
        return errors, []
    groups = {'claim': 'knowledge/claims', 'evidence': 'evidence', 'relationship': 'knowledge/relationships'}
    records = {kind: {} for kind in groups}
    all_ids = {}
    for kind, directory in groups.items():
        schema_path = base / 'schema' / (kind + '.schema.json')
        schema = read_json(schema_path)
        check_schema(schema)
        digest = hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()
        supported_hashes={SCHEMA_HASHES[kind]}
        if kind=='evidence':supported_hashes.add(CONFLUENCE_EVIDENCE_SCHEMA)
        if digest not in supported_hashes:
            errors.append(str(schema_path.relative_to(base)) + ': schema differs from supported v1 schema')
            continue
        if not (base / directory).is_dir():
            errors.append(directory + ': missing record directory')
            continue
        for path in sorted((base / directory).rglob('*')):
            if path.is_dir() or path.name == '.gitkeep':
                continue
            name = path.relative_to(base).as_posix()
            if path.suffix != '.json':
                errors.append(name + ': records must use .json')
                continue
            try:
                value = read_json(path)
                issues = schema_errors(value, schema)
            except (ValueError, OSError) as error:
                errors.append(name + ': ' + str(error))
                continue
            if issues:
                errors.extend(name + ': ' + issue for issue in issues)
                continue
            identifier = value['id']
            if identifier in all_ids:
                errors.append(f'{name}: duplicate identifier {identifier}; also in {all_ids[identifier]}')
            else:
                all_ids[identifier] = name
                records[kind][identifier] = value
    claims, evidence, relationships = (records[kind] for kind in groups)

    def issue(identifier, message):
        errors.append(f'{all_ids[identifier]}: {identifier}: {message}')

    for identifier, item in evidence.items():
        for target in item['substantiates']:
            if target not in claims:
                issue(identifier, 'substantiates missing claim ' + target)
    for identifier, claim in claims.items():
        for field, targets in [('evidence', evidence), ('depends_on', claims), ('conflicts_with', claims)]:
            for target in claim[field]:
                if target not in targets:
                    issue(identifier, field + ' references missing identifier ' + target)
                elif field != 'evidence' and target == identifier:
                    issue(identifier, field + ' prohibits self-reference ' + target)
                elif field == 'conflicts_with' and identifier not in claims[target]['conflicts_with']:
                    issue(identifier, 'asymmetric conflict with ' + target)
        if claim['status'] == 'CONFIRMED':
            allowed = ['direct-authoritative'] if claim['type'] == 'business_rule' else ['direct-authoritative', 'direct-technical']
            sufficient = [item for key in claim['evidence'] if (item := evidence.get(key))
                          and item['status'] == 'active' and item['type'] in allowed
                          and identifier in item['substantiates'] and item.get('location')]
            if not sufficient:
                issue(identifier, 'CONFIRMED requires active, appropriate direct evidence with location and explicit substantiates link')
            if claim['last_verified'] is None:
                issue(identifier, 'CONFIRMED requires last_verified date')
    edges = set()
    for identifier, relation in relationships.items():
        start, end, kind = relation['from'], relation['to'], relation['type']
        if start not in claims or end not in claims:
            issue(identifier, f'relationship has missing claim: {start} -> {end}')
        elif start == end:
            issue(identifier, 'relationship prohibits self-reference ' + start)
        elif end not in claims[start][kind]:
            issue(identifier, f'relationship must match claim {start}.{kind}: {end}')
        edge = (kind, *sorted([start, end])) if kind == 'conflicts_with' else (kind, start, end)
        if edge in edges:
            issue(identifier, f'duplicate relationship {start} -> {end}')
        edges.add(edge)
    pending = {key: set(value['depends_on']) & claims.keys() for key, value in claims.items()}
    while pending:
        ready = {key for key, dependencies in pending.items() if not dependencies}
        if not ready:
            errors.append('knowledge/claims: dependency cycle involving ' + ', '.join(sorted(pending)))
            break
        pending = {key: dependencies - ready for key, dependencies in pending.items() if key not in ready}
    warnings = ['Structural validation does not prove claim truth, source authority, or evidence freshness; human review is required.']
    for identifier, claim in claims.items():
        for target in claim['conflicts_with']:
            if target in claims and identifier < target:
                warnings.append(f'{all_ids[identifier]}: unresolved conflict {identifier} <-> {target} ({all_ids[target]})')
    return errors, warnings

