"""Actual installed predecessor/candidate, same-root upgrade/crash/rollback probe.

No product code is imported by the orchestrator. Worker imports are isolated and
asserted under the supplied environment prefix. Only a new temporary root is used.
"""
import argparse,hashlib,json,os,sqlite3,subprocess,sys,time
from contextlib import closing
from pathlib import Path


def worker(root,command):
    import knowledge,harness
    from knowledge.store import Store
    from knowledge import operations as op,lifecycle as life,maintenance as m
    from knowledge.util import canonical_json,KnowledgeError
    from harness.runtime import Journal
    assert Path(knowledge.__file__).is_relative_to(Path(sys.prefix))
    assert Path(harness.__file__).is_relative_to(Path(sys.prefix))
    s=Store(root)
    if command=='init':
        assert not any(root.iterdir()),'initialization requires a new empty synthetic root'
        (root/'Fixture.cs').write_text('class Fixture {}\n');s=Store(root);s.init();life.upgrade(s,life.upgrade_preview(s)['fingerprint'])
        def addition(name):
            eid='evidence.'+name
            return dict(version=1,operation='add',records={'claims':[dict(id=name,statement='Synthetic '+name,type='technical_fact',status='CONFIRMED',evidence=[eid],provenance={'actor':'fixture','method':'fixture'},last_verified='2026-11-22',depends_on=[],conflicts_with=[])],
                'evidence':[dict(id=eid,type='direct-technical',status='active',source='Fixture.cs',provenance={'actor':'fixture','method':'fixture'},captured_at='2026-11-22T00:00:00Z',location='Fixture.cs#L1',description='Fixture.',substantiates=[name])],'relationships':[]})
        s.submit(addition('imported'));p=s.prepare();s.apply(p['fingerprint'],p['fingerprint']);s.acknowledge(p['fingerprint'])
        s.submit(addition('committed'));p=s.prepare();s.apply(p['fingerprint'],p['fingerprint'])
        for name in ('pending','rejected','deferred'):
            value=s.submit(addition(name))
            if name!='pending':
                with s.connection(True) as db:db.execute('UPDATE queue SET status=? WHERE id=?',(name,value['candidate']))
        s.prepare()
        op.teach(root,'Remember encoding',{'type':'user-message','id':'fixture'},binding={'trigger':{'tool':'patch','name':'Fixture.cs'},'behavior':{'adapter':'preserve-format'}})
        j=Journal(root);j.save(dict(version=1,id='pending',project=j.project.identity,status='running',agents=[],frames=[],requests=[],source={},task={'version':1},gates={},capture={},config_hash='fixture'))
        j.action('pending','accepted',{'status':'PREPARED','tool':'patch','payload':{'path':'Fixture.cs'}})
        j.put_outbox('pending','pending',{'state':'pending','attempts':0});j.put_outbox('delivered','other',{'state':'delivered','attempts':1})
        return {'ok':s.validate()['ok'],'status':s.status(),'outbox':j.outbox('pending')}
    if command=='read':return {'status':s.status(),'memory':op.OperationalStore(root).records(),'run':Journal(root).load('pending'),'outbox':Journal(root).outbox('pending')}
    if command=='old-write':
        j=Journal(root);j.put_outbox('old-writer','pending',{'state':'pending'});j.update_outbox('old-writer',{'state':'delivered'});j.event('pending','old-writer');return {'ok':True,'outbox':j.outbox('pending')}
    if command.startswith('index-'):
        operation=command.split(':')[0]
        name=command.replace(':','-')+('-'+str(time.time_ns()) if operation=='index-rollback' else '')
        dest=root.parent/(name+'.zip');p=m.preview(root,operation,dest)
        if ':' in command:
            phase=command.split(':')[1]
            def fault(at):
                if at==phase:os._exit(77)
            m.fault=fault
        return m.apply(root,p['preview'],p['fingerprint'])
    if command=='recover':return m.recover(root)
    if command=='event-crash':
        import knowledge.store as st
        record=op.OperationalStore(root).records()['records'][0]
        def fault(at):
            if at=='before-commit':os._exit(78)
        st.checkpoint=fault;return op.binding_event(root,record,None,'blocked')
    if command=='write-busy':
        record=op.OperationalStore(root).records()['records'][0]
        try:op.binding_event(root,record,None,'verified')
        except KnowledgeError as e:return {'error':e.code}
        raise AssertionError('writer unexpectedly succeeded')
    if command=='restore':
        p=m.preview(root,'restore',archive=root.parent/'index-upgrade.zip',recovery=root.parent/'saved');return m.apply(root,p['preview'],p['fingerprint'])
    raise ValueError(command)


def main():
    p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path);p.add_argument('--candidate',type=Path);p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path);p.add_argument('--worker');a=p.parse_args()
    if a.worker:
        # Project must exist when constructing Store; initialization owns mkdir.
        print(json.dumps(worker(a.root,a.worker)));return
    rows=[]
    def call(py,command,expected=0):
        argv=[str(py),'-I','-B',str(Path(__file__).resolve()),'--root',str(a.root),'--worker',command]
        start=time.monotonic();r=subprocess.run(argv,capture_output=True,text=True)
        rows.append(dict(command=argv,returncode=r.returncode,seconds=time.monotonic()-start,stdout=r.stdout,stderr=r.stderr))
        a.output.write_text(json.dumps({'status':'RUNNING','steps':rows},indent=2)+'\n')
        assert r.returncode==expected,rows[-1]
        return json.loads(r.stdout) if expected==0 else None
    # Init worker constructs Project early; own the new root in the orchestrator.
    a.root.mkdir(parents=True,exist_ok=False)
    # worker init needs an empty existing root, never an existing user database.
    baseline=call(a.baseline,'init');before=call(a.baseline,'read')
    kpath=a.root/'.knowledge/store.sqlite3';khash=hashlib.sha256(kpath.read_bytes()).hexdigest()
    installed=call(a.candidate,'index-upgrade');assert khash==hashlib.sha256(kpath.read_bytes()).hexdigest()
    assert call(a.baseline,'read')==before
    call(a.baseline,'old-write');after=call(a.candidate,'read');assert after['outbox']['old-writer']['state']=='delivered'
    call(a.candidate,'index-rollback');assert call(a.baseline,'read')==after
    for phase in ('index-before-commit','index-after-commit'):
        call(a.candidate,'index-upgrade:'+phase,77)
        call(a.candidate,'recover');assert call(a.baseline,'read')==after
        call(a.candidate,'index-rollback')
    call(a.candidate,'event-crash',78);assert call(a.baseline,'read')==after
    with closing(sqlite3.connect(kpath)) as db, db:
        db.execute('BEGIN IMMEDIATE');start=time.monotonic();busy=call(a.candidate,'write-busy');elapsed=time.monotonic()-start
        assert busy['error']=='store-busy-retry' and elapsed<2
    call(a.candidate,'restore');assert call(a.baseline,'read')==before
    a.output.write_text(json.dumps(dict(status='PASS',baseline=baseline,canonical_knowledge_bytes_preserved=True,bounded_busy_seconds=elapsed,same_root=str(a.root),steps=rows),indent=2)+'\n')
    print('PASS',len(rows),'installed predecessor/candidate steps')
if __name__=='__main__':main()
