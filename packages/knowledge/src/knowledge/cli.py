import argparse
import sys
from pathlib import Path
from . import __version__
from .store import Store
from .util import loads, canonical_json, KnowledgeError


def parser():
    p=argparse.ArgumentParser(description='Knowledge: explicit project-local evidence store')
    p.add_argument('command',choices=['version','init','validate','submit','prepare','apply','acknowledge','context','lookup','status','recover','export','migrate-preview','migrate-apply','restore-legacy'])
    p.add_argument('--root',required=True)
    p.add_argument('--input',type=Path)
    p.add_argument('--plan')
    p.add_argument('--approve')
    p.add_argument('--task')
    p.add_argument('--kind',choices=['claims','evidence','relationships'],default='claims')
    p.add_argument('--id')
    p.add_argument('--max-bytes',type=int,default=16000)
    p.add_argument('--max-items',type=int,default=10)
    p.add_argument('--include-unconfirmed',action='store_true')
    p.add_argument('--destination')
    return p


def execute(a):
    store=Store(a.root)
    if a.command=='version':
        return {'ok':True,'version':__version__,'candidate_version':1,'store_format':'knowledge-sqlite-v1','operations':['add'],'discovery':False,'runner':False}
    if a.command=='submit':
        if not a.input:
            raise KnowledgeError('input-required')
        return store.submit(loads(a.input.read_text(encoding='utf-8')))
    if a.command=='apply':
        return store.apply(a.plan,a.approve)
    if a.command=='acknowledge':
        return store.acknowledge(a.plan)
    if a.command=='context':
        return store.context(a.task,a.max_bytes,a.max_items,a.include_unconfirmed)
    if a.command=='lookup':
        return store.lookup(a.kind,a.id)
    if a.command.startswith('migrate-') or a.command=='restore-legacy':
        from . import migration
        if a.command=='migrate-preview':
            return migration.preview(a.root)
        if a.command=='migrate-apply':
            return migration.apply(a.root,a.approve)
        return migration.restore_legacy(a.root,a.destination)
    return getattr(store,a.command)()


def main():
    args=parser().parse_args()
    try:
        result=execute(args)
    except (KnowledgeError,OSError,TypeError) as e:
        result={'ok':False,'error':getattr(e,'code','input-or-filesystem-error'),'details':getattr(e,'details',None)}
    print(canonical_json(result))
    return 0 if result['ok'] else 1


if __name__=='__main__':
    sys.exit(main())
