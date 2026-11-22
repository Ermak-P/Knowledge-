"""Explicit source traversal failures shared by strict identity consumers."""
from contextlib import contextmanager
from pathlib import Path
from .util import KnowledgeError


def enumeration_error(error):
    raise error


@contextmanager
def strict_source(root,code):
    try:yield
    except OSError as error:
        try:path=Path(error.filename).relative_to(root).as_posix() if error.filename else '.'
        except ValueError:path='.'
        raise KnowledgeError(code,{'path':path,'errno':error.errno,'coverage':'incomplete'}) from error
