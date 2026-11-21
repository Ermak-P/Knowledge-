"""Pure byte-format adapter; consumers retain file-write authority."""
from pathlib import PurePosixPath
import re
from .util import require

SIGNATURES=[(b'\xff\xfe\x00\x00','utf-32-le'),(b'\x00\x00\xfe\xff','utf-32-be'),
    (b'\xef\xbb\xbf','utf-8'),(b'\xff\xfe','utf-16-le'),(b'\xfe\xff','utf-16-be')]
BOMS={encoding:bom for bom,encoding in SIGNATURES}
EOLS={'lf':'\n','crlf':'\r\n','cr':'\r'}


def validate_changes(changes):
    require(isinstance(changes,list) and len(changes)<=20,'invalid-current-format-changes')
    seen=set()
    for change in changes:
        require(isinstance(change,dict) and 'path' in change and set(change)<={'path','encoding','bom','eol','final_newline','reset'},'invalid-current-format-change')
        path=change['path'];require(isinstance(path,str) and 0<len(path)<=1024 and '\0' not in path and ':' not in path,'invalid-format-path')
        parsed=PurePosixPath(path.replace('\\','/'))
        require(not parsed.is_absolute() and parsed.parts and all(not p.startswith('.') for p in parsed.parts),'invalid-format-path')
        require(path not in seen,'duplicate-current-format-path');seen.add(path)
        if 'reset' in change:
            require(change['reset'] is True and set(change)=={'path','reset'},'invalid-format-reset');continue
        require(len(change)>1,'empty-current-format-change')
        if 'encoding' in change:require(change['encoding'] in BOMS,'unsupported-current-encoding')
        if 'bom' in change:require(type(change['bom']) is bool,'invalid-current-bom')
        if 'eol' in change:require(change['eol'] in EOLS,'invalid-current-eol')
        if 'final_newline' in change:require(type(change['final_newline']) is bool,'invalid-current-final-newline')
        require(not (change.get('encoding','utf-8')!='utf-8' and change.get('bom') is False),'unmarked-wide-encoding-unsupported')
    return changes


def decode(raw):
    bom,encoding=next(((bom,enc) for bom,enc in SIGNATURES if raw.startswith(bom)),(b'','utf-8'))
    return raw[len(bom):].decode(encoding).replace('\r\n','\n').replace('\r','\n')


def encode(raw,text,change=None,exists=True):
    change=change or {}
    if change:validate_changes([{'path':'content',**change}])
    bom,encoding=next(((bom,enc) for bom,enc in SIGNATURES if raw.startswith(bom)),(b'','utf-8'))
    before=raw[len(bom):].decode(encoding)
    endings=set(re.findall(r'\r\n|\r|\n',before))
    require(len(endings)<=1 or 'eol' in change,'mixed-line-endings-preservation-unsupported')
    target=change.get('encoding',encoding)
    has_bom=change.get('bom',True if target!=encoding and target!='utf-8' else bool(bom))
    require(target=='utf-8' or has_bom,'unmarked-wide-encoding-unsupported')
    eol=EOLS[change['eol']] if 'eol' in change else next(iter(endings),'\n')
    after=text.replace('\r\n','\n').replace('\r','\n')
    final=change.get('final_newline',before.endswith(('\r','\n')) if exists else text.endswith(('\r','\n')))
    if not final:after=after.rstrip('\n')
    elif not after.endswith('\n'):after+='\n'
    require(has_bom or not after.startswith('\ufeff'),'unexpected-leading-encoding-signature')
    return (BOMS[target] if has_bom else b'')+after.replace('\n',eol).encode(target)
