import argparse
from pathlib import Path
from . import maintenance as m
from .util import KnowledgeError,loads,read_text,canonical_json

def main():
    p=argparse.ArgumentParser(description='Approved Knowledge/Harness maintenance')
    p.add_argument('command',choices=['backup-preview','upgrade-preview','restore-preview','apply','status','recover','doctor'])
    p.add_argument('--root',required=True);p.add_argument('--destination');p.add_argument('--archive');p.add_argument('--recovery');p.add_argument('--input',type=Path);p.add_argument('--approve')
    a=p.parse_args()
    try:
        if a.command.endswith('-preview'):value=m.preview(a.root,a.command.removesuffix('-preview'),a.destination,a.archive,a.recovery)
        elif a.command=='apply':value=m.apply(a.root,loads(read_text(a.input)),a.approve)
        elif a.command in ('status','recover'):value=getattr(m,a.command)(a.root)
        else:
            from . import __version__
            from .project import Project
            from .store import Store
            project=Project(a.root);store=Store(a.root)
            value=dict(ok=True,version=__version__,root=project.describe(),knowledge=store.validate() if store.path.exists() else {'available':False,'reason':'knowledge-absent'},maintenance=m.status(a.root),platform=m.profile())
    except (KnowledgeError,OSError,TypeError,ValueError,KeyError) as e:value=dict(ok=False,error=getattr(e,'code','maintenance-input-or-filesystem-error'),details=getattr(e,'details',None))
    print(canonical_json(value));return 0 if value['ok'] else 1
if __name__=='__main__':raise SystemExit(main())
