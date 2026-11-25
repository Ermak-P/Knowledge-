import argparse
import sqlite3
from pathlib import Path
from . import maintenance as m
from .util import KnowledgeError,loads,read_text,canonical_json,emit_json

def main():
    p=argparse.ArgumentParser(description='Approved Knowledge/Harness maintenance')
    p.add_argument('command',choices=['identity-inventory','identity-preview','identity-apply','identity-recover','identity-rollback-preview','identity-rollback','identity-history','backup-preview','upgrade-preview','restore-preview','index-upgrade-preview','index-rollback-preview','apply','status','recover','doctor'])
    p.add_argument('--root',required=True);p.add_argument('--destination');p.add_argument('--archive');p.add_argument('--recovery');p.add_argument('--input',type=Path);p.add_argument('--approve')
    p.add_argument('--old-identity');p.add_argument('--workspace');p.add_argument('--transaction')
    p.add_argument('--table');p.add_argument('--cursor',type=int,default=0);p.add_argument('--limit',type=int,default=20);p.add_argument('--contents',action='store_true')
    a=p.parse_args()
    try:
        if a.command.startswith('identity-'):
            from . import identity_migration as im
            if a.command=='identity-inventory':value=im.inventory(a.root,a.old_identity)
            elif a.command=='identity-preview':value=im.preview(a.root,a.old_identity,a.workspace)
            elif a.command=='identity-apply':value=im.apply(a.root,loads(read_text(a.input)),a.approve)
            elif a.command=='identity-history':value=im.history(a.root,a.table,a.cursor,a.limit,a.contents)
            elif a.command=='identity-rollback-preview':value=im.rollback_preview(a.root,a.transaction)
            else:value=im.recover(a.root,a.transaction,a.command=='identity-rollback',a.approve)
        elif a.command.endswith('-preview'):value=m.preview(a.root,a.command.removesuffix('-preview'),a.destination,a.archive,a.recovery)
        elif a.command=='apply':value=m.apply(a.root,loads(read_text(a.input)),a.approve)
        elif a.command in ('status','recover'):value=getattr(m,a.command)(a.root)
        else:
            from . import __version__
            from .project import Project
            from .store import Store
            project=Project(a.root);store=Store(a.root)
            value=dict(ok=True,version=__version__,root=project.describe(),knowledge=store.validate() if store.path.exists() else {'available':False,'reason':'knowledge-absent'},maintenance=m.status(a.root),platform=m.profile())
    except (KnowledgeError,OSError,TypeError,ValueError,KeyError,sqlite3.DatabaseError) as e:value=dict(ok=False,error=getattr(e,'code','maintenance-input-filesystem-or-database-error'),details=getattr(e,'details',None))
    emit_json(value);return 0 if value['ok'] else 1
if __name__=='__main__':raise SystemExit(main())
