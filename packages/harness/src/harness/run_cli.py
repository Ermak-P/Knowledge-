"""Explicit P2 execution CLI; the original harness context command stays read-only."""
import argparse
import sys
from pathlib import Path
from knowledge.util import emit_json, canonical_json,loads,read_text,KnowledgeError
from .runtime import configure,config,Journal
from .engine import start,resume,status


def main():
    parser=argparse.ArgumentParser(description='Controlled Harness execution')
    parser.add_argument('command',choices=['version','doctor','configure','validate-config','run','status','resume','cancel','capture-status','capture-retry','metrics','compare'])
    parser.add_argument('--output',type=Path);parser.add_argument('--root',required=True);parser.add_argument('--input',type=Path);parser.add_argument('--run-id');parser.add_argument('--mode',choices=['multi','single'],default='multi');parser.add_argument('--init-knowledge',action='store_true')
    args=parser.parse_args()
    try:
        if args.command=='version':
            from . import __version__
            from .platform import KIND
            value={'ok':True,'version':__version__,'execution_policies':['legacy-v1','bounded-v2'],'task_versions':[1,2],'runner_config':1,'run_state':1,'execution_backend':KIND,'provider':'OpenAI-compatible HTTP','qualification':'separate exact-profile evidence required'}
        elif args.command=='doctor':
            from knowledge.project import Project
            project=Project(args.root);path=project.root/'.harness/runner.json'
            value={'ok':True,'project':project.describe(),'configured':path.exists(),'configuration':config(args.root) if path.exists() else None}
        elif args.command=='configure':value=configure(args.root,loads(read_text(args.input)),args.init_knowledge)
        elif args.command=='validate-config':value={'ok':True,'configuration':config(args.root)}
        elif args.command=='compare':
            from .comparison import compare
            value=compare(args.root,loads(read_text(args.input)),args.output)
        elif args.command=='run':value=start(args.root,loads(read_text(args.input)),args.mode)
        elif args.command in ('resume','capture-retry'):value=resume(args.root,args.run_id)
        elif args.command=='cancel':Journal(args.root).cancel(args.run_id);value={'ok':True,'run_id':args.run_id,'cancellation_requested':True}
        elif args.command=='status' and not args.run_id:value={'ok':True,'runs':[{'id':r['id'],'status':r['status'],'started':r['started']} for r in Journal(args.root).runs()]}
        else:
            report=status(args.root,args.run_id)
            value=report if args.command=='status' else {'ok':True,'metrics':report['metrics']} if args.command=='metrics' else {'ok':True,'capture':report['run']['capture'],'outbox':report['outbox']}
    except (KnowledgeError,OSError,TypeError,AttributeError,ValueError) as e:
        value={'ok':False,'error':getattr(e,'code','input-or-filesystem-error'),'details':getattr(e,'details',None)}
    emit_json(value);return 0 if value['ok'] else 1


if __name__=='__main__':raise SystemExit(main())
