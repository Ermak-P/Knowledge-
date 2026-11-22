import argparse
import sys
from pathlib import Path
from . import __version__
from .store import Store
from .util import loads, emit_json, canonical_json, KnowledgeError, read_text


def parser():
    p=argparse.ArgumentParser(description='Knowledge: explicit project-local evidence store')
    p.add_argument('command',choices=['version','init','validate','submit','prepare','apply','acknowledge','context','lookup','status','recover','export','migrate-preview','migrate-apply','restore-legacy','upgrade-preview','upgrade-apply','scan','scan-status','reconcile','review','history','knowledge-init','knowledge-candidates-update','knowledge-candidates-push','memory-ingest','memory-teach','memory-lookup','memory-inspect','memory-history','memory-retire','memory-rebind','memory-transfer-recover'])
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
    p.add_argument('--scan-id')
    p.add_argument('--max-files',type=int,default=50)
    p.add_argument('--base')
    p.add_argument('--head')
    p.add_argument('--restart',action='store_true')
    p.add_argument('--disposition',choices=['pending','rejected','deferred'])
    p.add_argument('--reason')
    p.add_argument('--shared-root')
    p.add_argument('--scope',choices=['project','shared'],default='project')
    p.add_argument('--expected-revision',type=int)
    return p


def execute(a):
    if a.command.startswith('memory-'):
        from . import operations as op
        if a.command=='memory-transfer-recover':
            from .transfers import recover
            return recover(a.root,a.shared_root)
        if a.command=='memory-inspect':
            from .transfers import intents
            return {'ok':True,**op.OperationalStore(a.root,a.scope,a.shared_root).records(),'transfers':intents(a.root)}
        if a.command=='memory-history':return {'ok':True,'history':op.OperationalStore(a.root,a.scope,a.shared_root).history(a.id)}
        if a.command=='memory-retire':return op.retire(a.root,a.id,scope=a.scope,shared=a.shared_root,expected_revision=a.expected_revision)
        raw=read_text(a.input) if a.input else sys.stdin.buffer.read(65537).decode('utf-8')
        if len(raw)>65536:raise KnowledgeError('memory-input-too-large')
        value=loads(raw)
        if a.command=='memory-ingest':return op.ingest(a.root,value['text'],value['message_id'],{**value.get('policy',{}),**({'shared_root':a.shared_root} if a.shared_root else {})})
        if a.command=='memory-teach':return op.teach(a.root,value['text'],value['source'],scope=a.scope,shared=a.shared_root,binding=value.get('binding'),applicability=value.get('applicability'),identifier=a.id,expected_revision=a.expected_revision,recovery_authorized=value.get('recovery_authorized',False))
        if a.command=='memory-rebind':return op.rebind(a.root,a.id,value['text'],value['source'],scope=a.scope,shared=a.shared_root,expected_revision=a.expected_revision,recovery_authorized=value.get('recovery_authorized',False))
        return op.lookup(a.root,value['action'],value.get('environment',{}),shared=a.shared_root,max_items=a.max_items,max_bytes=a.max_bytes,include_candidates=a.include_unconfirmed)
    store=Store(a.root)
    from . import lifecycle as life, discovery
    if a.command=='upgrade-preview':return life.upgrade_preview(store)
    if a.command=='upgrade-apply':return life.upgrade(store,a.approve)
    if a.command=='review':return life.dispose(store,a.id,a.disposition,a.reason)
    if a.command=='history':return life.history(store,a.id)
    if a.command=='scan-status':return discovery.status(store,a.scan_id)
    if a.command=='reconcile':return discovery.reconcile(store,a.scan_id)
    if a.command=='knowledge-init':
        new=not store.path.exists()
        store.init()
        if new:life.upgrade(store,life.upgrade_preview(store)['fingerprint'])
        preview=life.upgrade_preview(store)
        if not preview['already_upgraded']:
            return {'ok':False,'error':'upgrade-required','preview':preview}
        result=discovery.scan(store,a.scan_id,a.max_files,a.base,a.head,a.restart)
        result['reconciliation']=discovery.reconcile(store,result['id'])
        return result
    if a.command in ('scan','knowledge-candidates-update'):return discovery.scan(store,a.scan_id,a.max_files,a.base,a.head,a.restart)
    if a.command=='knowledge-candidates-push':return store.apply(a.plan,a.approve) if a.approve else store.prepare()
    if a.command=='version':
        return {'ok':True,'version':__version__,'candidate_version':1,'store_format':'knowledge-sqlite-v1','operations':['add'],'v2_operations':['add','update','retire','supersede','reactivate','relationship-change'],'candidate_versions':[1,2],'discovery':True,'runner':False}
    if a.command=='submit':
        if not a.input:
            raise KnowledgeError('input-required')
        return store.submit(loads(read_text(a.input)))
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
    except (KnowledgeError,OSError,TypeError,KeyError,ValueError) as e:
        result={'ok':False,'error':getattr(e,'code','input-or-filesystem-error'),'details':getattr(e,'details',None)}
    emit_json(result)
    return 0 if result['ok'] else 1


if __name__=='__main__':
    sys.exit(main())
