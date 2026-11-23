"""JSON/stdin API for the foreground command. No source string becomes argv code."""
import argparse,sys
from pathlib import Path
from .util import loads,read_text,emit_json,KnowledgeError,require


def execute(root,action,value):
    from .cr_workflow import Workflow
    from . import cr_sources as sources
    require(isinstance(value,dict),'ucr-input-object-required');workflow=Workflow(root)
    if action=='start':
        require(set(value)<={'arguments','cr','pr','session','host_session','language'},'ucr-unexpected-start-field')
        return workflow.start(**value)
    if action=='fetch-github':return dict(ok=True,snapshot=sources.resolve_comparison(root,sources.github_snapshot(value['cr'],value['pr'],value['target_commit'])))
    if action in ('install','uninstall','installation-status'):
        from .cr_install import install,uninstall,status
        return {'install':install,'uninstall':uninstall,'installation-status':status}[action](root,**value)
    sid=value['session']
    if action=='resume':return workflow.resume(sid)
    if action=='inspect':return workflow.inspect(sid,value.get('paths',[]))
    if action=='sources':return workflow.sources(sid,value['snapshot'],value['expected_revision'])
    if action=='analyze':return workflow.analyze(sid,value['items'],value['expected_revision'])
    if action=='answer':return workflow.answer(sid,value['question'],value['text'],value['delivery_id'],value['expected_revision'],value.get('kind','historical_reason'),value.get('turn'))
    if action=='user-turn':return workflow.user_turn(sid,value['host_session'],value['message_id'],value['text'])
    if action=='finish':return workflow.finish(sid,value['expected_revision'])
    if action=='prepare':return workflow.prepare(sid,value['expected_revision'])
    if action=='apply':return workflow.apply(sid,value['approve'],value['expected_revision'])
    if action=='recover':return workflow.recover(sid)
    raise KnowledgeError('ucr-unsupported-action')


def main():
    p=argparse.ArgumentParser(description='Durable architectural /update-by-CR workflow')
    p.add_argument('action',choices=['start','fetch-github','sources','inspect','analyze','answer','user-turn','finish','prepare','apply','recover','resume','install','uninstall','installation-status'])
    p.add_argument('--root',required=True);p.add_argument('--input',type=Path);a=p.parse_args()
    try:
        raw=read_text(a.input) if a.input else sys.stdin.buffer.read(1024001).decode('utf-8')
        require(len(raw.encode())<=1024000,'ucr-input-too-large');value=execute(a.root,a.action,loads(raw or '{}'))
    except (KnowledgeError,OSError,ValueError,KeyError,TypeError) as e:
        value=dict(ok=False,error=getattr(e,'code','ucr-input-or-filesystem-error'),details=getattr(e,'details',None),persistence='not confirmed; resume the durable session')
    emit_json(value);return 0 if value.get('ok') else 1
if __name__=='__main__':raise SystemExit(main())
