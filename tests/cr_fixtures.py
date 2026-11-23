"""Synthetic CR/PR sources and two decision domains, never production requests."""
from copy import deepcopy
from pathlib import Path
import subprocess
from knowledge.util import digest
from knowledge.cr_sources import COVERAGE


def git(root,*args):
    return subprocess.check_output(['git','-C',str(root),*args],text=True,stderr=subprocess.DEVNULL).strip()


def project(base,language='en',scenario='retry'):
    root=Path(base)/'project';root.mkdir()
    git(root,'init');git(root,'config','user.email','fixture@example.invalid');git(root,'config','user.name','Synthetic');git(root,'config','core.autocrlf','false')
    git(root,'remote','add','origin','https://github.com/synthetic/project')
    (root/'.gitignore').write_text('.knowledge/\n.harness/\n.knowledge-control.lock\n.harness-writer.lock\n')
    if scenario=='retry':
        files={'Retry.cs':'public static class Retry { public const int MaxAttempts = 1; }\n',
               'Transport.cs':'public static class Transport { public const int PacketAttempts = 2; }\n',
               'Caller.cs':'public static class Caller { public const int DeadlineMs = 120; }\n',
               'Checks.cs':'public static class Checks { public const string Rule = "bounded deadline and independent packet retry"; }\n'}
        title='Transient operation retry bounds';body='Bound transient operation retries; retain caller deadline and independent packet transport recovery.'
    else:
        files={'Cache.cs':'public static class Cache { public const int Capacity = 8; }\n',
               'Contracts.cs':'public interface ILookup { string Find(string key); }\n',
               'Checks.cs':'public static class Checks { public const string Rule = "bounded cache and unchanged public lookup contract"; }\n'}
        title='Ограниченный кэш справочника';body='Увеличить ёмкость кэша; сохранить публичный интерфейс поиска и поведение при промахе.'
    for path,text in files.items():(root/path).write_text(text,encoding='utf-8')
    git(root,'add','.');git(root,'commit','-m','synthetic base');base_sha=git(root,'rev-parse','HEAD')
    changed='Retry.cs' if scenario=='retry' else 'Cache.cs';old=(root/changed).read_text();(root/changed).write_text(old.replace('= 1;','= 4;') if scenario=='retry' else old.replace('= 8;','= 32;'))
    git(root,'add','.');git(root,'commit','-m','synthetic implementation');head=git(root,'rev-parse','HEAD')
    snapshot=dict(version=1,acquisition={'kind':'user-export','reference':'synthetic fixture export, not independently fetched'},observed_at='2026-11-22T12:00:00Z',
        cr=dict(url='https://github.com/synthetic/project/issues/7',id='7',title=title,requirements=[dict(id='body',text=body,reference='https://github.com/synthetic/project/issues/7')],discussion=[],attachments=[]),
        pr=dict(url='https://github.com/synthetic/project/pull/8',id='8',repository='https://github.com/synthetic/project',target_branch=git(root,'branch','--show-current'),base=base_sha,head=head,merge=head,status='merged',description='Implements https://github.com/synthetic/project/issues/7',changed_files=[changed],discussion=[],checks=[] ,cr_links=['https://github.com/synthetic/project/issues/7']),
        target=dict(commit=head,branch=git(root,'branch','--show-current')),coverage={key:'complete' for key in COVERAGE})
    return root,snapshot


def anchor(snapshot,path,role):return dict(path=path,revision=snapshot['target']['commit'],start=1,end=1,role=role)
def item(snapshot,key,statement,path,category='decision',reason=None,preserve='',condition='For this component and reviewed version',terms=None):
    return dict(key=key,category=category,statement=statement,condition=condition,preserve=preserve,reconsider='Reassess when the owning contract or failure model changes',reason=reason,refs=['cr:req:body','pr:description'],anchors=[anchor(snapshot,path,'neighbor' if category=='nonchange' else 'implementation')],terms=terms or [],confidence='CONFIRMED',existing_id=None,change='upsert')


def decisions(snapshot,scenario='retry'):
    if scenario=='retry':return [
        item(snapshot,'retry-limit','Prefer four total transient operation attempts', 'Retry.cs',preserve='Bound work within the caller deadline',terms=['retry','transient','повтор','ошибка']),
        item(snapshot,'transport-owner','Leave the independent packet recovery in Transport unchanged', 'Transport.cs','nonchange',preserve='Do not multiply operation retries by changing packet recovery ownership',terms=['transport','retry','повтор']),
        item(snapshot,'deadline','Preserve the caller deadline of 120 ms','Caller.cs','nonchange',preserve='Do not extend the public caller deadline',terms=['deadline','timeout','срок'])]
    return [
        item(snapshot,'capacity','Для справочника использовать ограниченный кэш ёмкостью 32 записи','Cache.cs',preserve='Ограничение памяти и прежнее поведение при промахе',condition='Для локального справочника с неизменяемыми ключами',terms=['cache','lookup','кэш','поиск']),
        item(snapshot,'contract','Публичный интерфейс ILookup.Find оставить прежним','Contracts.cs','nonchange',preserve='Не менять сигнатуру Find и совместимость потребителей',condition='Пока остаются старые потребители ILookup',terms=['ILookup','Find','интерфейс','контракт'])]


def ready(workflow,snapshot,items,language='en',answers=None):
    state=workflow.start(cr=snapshot['cr']['url'],pr=snapshot['pr']['url'],language=language);sid=state['session']
    state=workflow.sources(sid,snapshot,state['revision']);state=workflow.analyze(sid,items,state['revision'])
    for q in list(workflow.get(sid)['questions']):
        answer=(answers or {}).get(q['item'],'The independently owned contract must remain compatible; this is a contextual constraint, not a universal permission.')
        state=workflow.answer(sid,q['id'],answer,'answer-'+q['id'],state['revision'])
    return state
