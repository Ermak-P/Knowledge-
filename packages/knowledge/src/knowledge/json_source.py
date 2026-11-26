"""Validate JSON dialects while keeping offsets in the original source."""
import re
from pathlib import PurePosixPath

from .util import KnowledgeError, loads

STRICT = 'strict-json'
JSONC = 'jsonc'
DOTNET = 'dotnet-json'
DIALECTS = {STRICT, JSONC, DOTNET}
TOKENS = re.compile(r'"(?:[^"\\]|\\[\s\S])*(?:"|$)|//[^\r\n]*|/\*[\s\S]*?(?:\*/|$)|[,\[\]{}]|[^\s]', re.ASCII)


def dialect(path, config):
    from .source_reader import matches

    for pattern, selected in sorted(config.get('json_dialects', {}).items()):
        if matches(path, pattern):
            return selected
    name = PurePosixPath(path).name.casefold()
    if name in ('appsettings.json', 'launchsettings.json') or (name.startswith('appsettings.') and name.endswith('.json')):
        return DOTNET if config.get('reader') != 'source-reader-v1' else STRICT
    return JSONC if name.endswith('.jsonc') else STRICT


def syntax_error(text, position, reason):
    # The standard JSON decoder counts LF. Include bare CR from older files.
    lines = re.split(r'\r\n|\r|\n', text[:position])
    return KnowledgeError(reason, {'line': len(lines), 'column': len(lines[-1]) + 1})


def validate(text, selected):
    sanitized = list(text) if selected != STRICT else None
    previous = None
    before_comma = None
    first_extension = None
    for token in TOKENS.finditer(text):
        value = token.group()
        if value.startswith(('//', '/*')):
            if value.startswith('/*') and (len(value) < 4 or not value.endswith('*/')):
                raise syntax_error(text, token.start(), 'unterminated-json-comment')
            if sanitized is None:
                first_extension = first_extension or (token.start(), 'unsupported-json-comments')
            else:
                sanitized[token.start():token.end()] = [
                    ch if ch in '\r\n' else ' ' for ch in value]
            continue
        if value == ',':
            before_comma = previous
        if value in (']', '}') and previous is not None and previous.group() == ',':
            # Leave leading and doubled commas intact so malformed arrays
            # and objects cannot become valid after replacing the comma.
            if before_comma is not None and before_comma.group() not in ('[', '{', ','):
                if selected == DOTNET:
                    sanitized[previous.start()] = ' '
                else:
                    first_extension = first_extension or (previous.start(), 'unsupported-json-trailing-comma')
        previous = token
    try:
        loads(text if sanitized is None else ''.join(sanitized))
    except KnowledgeError as error:
        if first_extension:
            raise syntax_error(text, *first_extension) from error
        position = getattr(error.__cause__, 'pos', None)
        if position is not None:
            raise syntax_error(text, position, error.code) from error
        raise
