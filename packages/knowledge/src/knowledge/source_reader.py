"""Deterministic source policy, streaming identity and bounded strict decoding.

No model, encoding guessing, external entity resolution or repository writes.
Physical extraction coverage is distinct from lexical/semantic completeness.
"""
import codecs
import fnmatch
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from .project import safe_path
from .util import KnowledgeError, loads, require

VERSION = 'source-reader-v1'
CONFIG = '.knowledge/discovery.json'
ENCODINGS = {'utf-8', 'utf-8-sig', 'utf-16', 'utf-16-le', 'utf-16-be', 'cp1251', 'cp1252', 'iso8859-1'}
STRUCTURED = {'.json', '.xml', '.config', '.yaml', '.yml', '.md'}


def matches(path, pattern):
    return fnmatch.fnmatchcase(path, pattern) or (pattern.startswith('**/') and fnmatch.fnmatchcase(path, pattern[3:]))


def policy(root, limit):
    path = safe_path(Path(root) / CONFIG)
    if path.exists():
        with path.open('rb') as stream: data=stream.read(65537)
        require(len(data)<=65536,'discovery-policy-too-large');raw=loads(data.decode('utf-8'))
    else: raw={'version':1}
    require(isinstance(raw, dict) and raw.get('version') == 1 and set(raw) <=
            {'version', 'exclude', 'include', 'legacy_encodings', 'max_file_bytes', 'format_limits', 'max_hash_bytes'}, 'invalid-discovery-policy')
    value = {'version': 1, 'reader': VERSION, 'exclude': raw.get('exclude', []), 'include': raw.get('include', []),
             'legacy_encodings': raw.get('legacy_encodings', {}), 'max_file_bytes': raw.get('max_file_bytes', limit),
             'format_limits': raw.get('format_limits', {}), 'max_hash_bytes': raw.get('max_hash_bytes', 128 * 1024 * 1024)}
    require(type(value['max_file_bytes']) is int and 1024 <= value['max_file_bytes'] <= 8 * 1024 * 1024, 'invalid-source-byte-limit')
    require(type(value['max_hash_bytes']) is int and value['max_file_bytes'] <= value['max_hash_bytes'] <= 1024 * 1024 * 1024, 'invalid-source-hash-limit')
    require(isinstance(value['exclude'], list) and len(value['exclude']) <= 200, 'invalid-exclusion-policy')
    require(isinstance(value['include'], list) and len(value['include']) <= 200, 'invalid-inclusion-policy')
    def glob(pattern):
        require(isinstance(pattern, str) and 0 < len(pattern) <= 256 and not pattern.startswith(('/', '\\'))
                and '..' not in pattern.split('/') and '\\' not in pattern and ':' not in pattern, 'invalid-policy-glob')
    for rule in value['exclude']:
        require(isinstance(rule, dict) and set(rule) == {'glob', 'reason'} and isinstance(rule['reason'], str)
                and 0 < len(rule['reason']) <= 300, 'invalid-exclusion-rule'); glob(rule['glob'])
    for pattern in value['include']: glob(pattern)
    require(isinstance(value['legacy_encodings'], dict) and len(value['legacy_encodings']) <= 100, 'invalid-encoding-policy')
    for pattern, encoding in value['legacy_encodings'].items():
        glob(pattern)
        try: canonical = codecs.lookup(encoding).name
        except (LookupError, TypeError): raise KnowledgeError('unsupported-policy-encoding')
        require(canonical in ENCODINGS, 'unsupported-policy-encoding')
    require(isinstance(value['format_limits'], dict), 'invalid-format-limits')
    for suffix, size in value['format_limits'].items():
        require(isinstance(suffix, str) and re.fullmatch(r'\.[a-z0-9]+', suffix) and type(size) is int
                and 1024 <= size <= 8 * 1024 * 1024, 'invalid-format-limit')
    return value


def exclusion(path, config):
    if any(matches(path, pattern) for pattern in config['include']): return None
    return next(({'reason': 'EXCLUDED_BY_POLICY', 'rule': rule['glob'], 'description': rule['reason']}
                 for rule in config['exclude'] if matches(path, rule['glob'])), None)


def failure(code, stage, **metadata):
    raise KnowledgeError(code, {**metadata, 'reason_code': code, 'stage': stage})


def fingerprint(path, config, object_format='sha1', relative=None, classify=False):
    """Hash complete original bytes in bounded blocks; never call a prefix a hash."""
    safe_path(path); before = path.stat()
    if before.st_size > config['max_hash_bytes']:
        return {'hash': None, 'bytes': before.st_size, 'status': 'blocked', 'reason': 'FILE_TOO_LARGE',
                'reason_code': 'FILE_TOO_LARGE', 'limit_bytes': config['max_hash_bytes'], 'stage': 'inventory',
                'retry_eligible': False, 'unhashed_mtime_ns': before.st_mtime_ns}
    sha = hashlib.sha256(); blob = hashlib.new(object_format) if object_format else None; normalized = hashlib.new(object_format) if object_format else None
    if blob: blob.update(b'blob ' + str(before.st_size).encode() + b'\0')
    # The normalized Git blob needs its normalized length. Only keep bounded
    # source bytes; large files use raw Git identity and conservative dirty state.
    small = bytearray() if blob and before.st_size <= config['max_file_bytes'] else None
    header=bytearray()
    with path.open('rb') as stream:
        seen=0
        while block := stream.read(min(65536,before.st_size+1-seen)):
            seen+=len(block)
            if seen>before.st_size:failure('FILE_CHANGED_DURING_SCAN','inventory',retry_eligible=True)
            sha.update(block)
            if blob: blob.update(block)
            if small is not None: small.extend(block)
            if len(header)<4096:header.extend(block[:4096-len(header)])
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != \
       (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        failure('FILE_CHANGED_DURING_SCAN', 'inventory', retry_eligible=True)
    raw_blob = blob.hexdigest() if blob else None; lf_blob = raw_blob
    if small is not None:
        data = small.replace(b'\r\n', b'\n')
        normalized.update(b'blob ' + str(len(data)).encode() + b'\0'); normalized.update(data); lf_blob = normalized.hexdigest()
    value={'hash': 'sha256:' + sha.hexdigest(), 'bytes': before.st_size, 'status': 'not-analyzed',
           'working_blob': raw_blob, 'lf_blob': lf_blob}
    if classify:
        try:
            selected=encoding(bytes(header),relative or path.name,config);value['encoding']=selected
            codecs.getincrementaldecoder(selected)(errors='strict').decode(header,final=before.st_size<=len(header))
        except UnicodeError:
            value.update(status='blocked',reason='INVALID_ENCODING',reason_code='INVALID_ENCODING',stage='inventory-decode',retry_eligible=False)
        except KnowledgeError as error:
            value.update(error.details or {},status='excluded' if error.code=='EXCLUDED_BINARY' else 'blocked',reason=error.code,reason_code=error.code)
    return value


def encoding(data, path, config):
    if data.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)): failure('UNSUPPORTED_ENCODING', 'decode', encoding='utf-32', retry_eligible=False)
    if data.startswith(codecs.BOM_UTF8): return 'utf-8-sig'
    if data.startswith(codecs.BOM_UTF16_LE): return 'utf-16'
    if data.startswith(codecs.BOM_UTF16_BE): return 'utf-16'
    if data.startswith(b'\x00<\x00?'): return 'utf-16-be'
    if data.startswith(b'<\x00?\x00'): return 'utf-16-le'
    if data.startswith((b'PK\x03\x04', b'\x89PNG', b'%PDF-')): failure('EXCLUDED_BINARY', 'classify', retry_eligible=False)
    if Path(path).suffix.lower() in ('.xml', '.config', '.csproj', '.props', '.targets'):
        declaration = re.match(br'\s*<\?xml\b[^>]*\bencoding\s*=\s*[\'"]([^\'"]+)[\'"]', data[:1024], re.I)
        if declaration:
            try: found = codecs.lookup(declaration[1].decode('ascii')).name
            except (LookupError, UnicodeError): failure('UNSUPPORTED_ENCODING', 'decode', retry_eligible=False)
            if found not in ENCODINGS: failure('UNSUPPORTED_ENCODING', 'decode', encoding=found, retry_eligible=False)
            return found
    for pattern, selected in sorted(config['legacy_encodings'].items()):
        if matches(path, pattern): return codecs.lookup(selected).name
    if b'\0' in data[:4096]: failure('EXCLUDED_BINARY', 'classify', retry_eligible=False)
    return 'utf-8'


def read(root, relative, entry, config):
    path = safe_path(Path(root) / relative); size = path.stat().st_size
    limit = config['format_limits'].get(path.suffix.lower(), config['max_file_bytes'])
    meta = {'path': relative, 'bytes': size, 'limit_bytes': limit, 'stage': 'extract', 'retry_eligible': False}
    if size > limit and path.suffix.lower() not in STRUCTURED: failure('FILE_TOO_LARGE', **meta)
    with path.open('rb') as stream: raw = stream.read(limit + 1)
    partial = len(raw) > limit; raw = raw[:limit]
    selected = encoding(raw, relative, config); meta['encoding'] = selected
    try:
        decoder = codecs.getincrementaldecoder(selected)(errors='strict')
        text = decoder.decode(raw, final=not partial)
    except UnicodeError: failure('INVALID_ENCODING', **meta)
    if not partial and 'sha256:' + hashlib.sha256(raw).hexdigest() != entry['hash']:
        failure('FILE_CHANGED_DURING_SCAN', **{**meta, 'retry_eligible': True})
    if any(ord(char) < 9 or 13 < ord(char) < 32 for char in text[:4096]): failure('EXCLUDED_BINARY', **meta)
    meta.update(analyzed_bytes=len(raw) - len(decoder.getstate()[0]), partial=partial,
                reason_code='PARTIAL_EXTRACTION' if partial else None,
                structure_validation='not-run-partial' if partial else 'content-only')
    if not partial:
        try:
            if path.suffix.lower() == '.json':
                loads(text); meta['structure_validation'] = 'json'
            elif path.suffix.lower() in ('.xml', '.config', '.csproj', '.props', '.targets') and text.lstrip().startswith('<'):
                if re.search(r'<!\s*(DOCTYPE|ENTITY)\b', text, re.I): failure('EXTRACTION_FAILED', **{**meta, 'stage': 'xml-external-resources-disabled'})
                ET.fromstring(text); meta['structure_validation'] = 'xml-no-dtd'
        except KnowledgeError as error:
            if error.code == 'EXTRACTION_FAILED': raise
            failure('EXTRACTION_FAILED', **{**meta, 'stage': 'structured-syntax'})
        except (ValueError, ET.ParseError,RecursionError) as error:
            failure('EXTRACTION_FAILED', **{**meta, 'stage': 'structured-syntax','exception':type(error).__name__})
    return text, meta
