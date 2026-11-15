import hashlib
import json


def canonical_json(value):
    try:
        text=json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        text.encode('utf-8')  # Reject unpaired surrogates before hashing/writes/output.
        return text
    except (UnicodeError,TypeError,ValueError) as e:
        raise KnowledgeError('invalid-json-value') from e


def digest(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def fingerprint(value):
    return 'sha256:' + digest(value)


def canonical_source(record):
    value = record['source']
    return value.get('reference') if isinstance(value, dict) else value


class KnowledgeError(ValueError):
    def __init__(self, code, details=None):
        self.code, self.details = code, details
        super().__init__(code)


def require(condition, code, details=None):
    if not condition:
        raise KnowledgeError(code, details)


def loads(text):
    def pairs(items):
        result = {}
        for k, v in items:
            require(k not in result, 'duplicate-json-key')
            result[k] = v
        return result
    try:
        return json.loads(text, object_pairs_hook=pairs,
                          parse_constant=lambda _: require(False, 'nonfinite-json'))
    except (json.JSONDecodeError, UnicodeError) as e:
        raise KnowledgeError('invalid-json') from e


def read_text(path):
    """Persisted JSON is UTF-8, independent of the process locale."""
    try:
        return path.read_text(encoding='utf-8')
    except UnicodeError as e:
        raise KnowledgeError('invalid-utf8') from e


def read_document(path, expected, code):
    value=loads(read_text(path))
    require(isinstance(value,expected),code)
    return value
