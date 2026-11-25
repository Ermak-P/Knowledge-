"""Virtual-source production-shape fixture. Never a substitute for real-file tests."""
from knowledge import lifecycle as life
from knowledge.util import canonical_json,digest
METHOD='dotnet-lexical-v3'


def populate(store):
    files={'source%05d.cs'%n:{'hash':'sha256:'+digest(['source',n]),'partition':'.','status':'analyzed'} for n in range(40000)}
    for n in range(78):files['source%05d.cs'%n].update(status='blocked',processing_status='failed',retry_eligible=False)
    for n in range(78,93):files['source%05d.cs'%n].update(processing_status='partial')
    hashed={p:{k:v for k,v in e.items() if k!='status'} for p,e in files.items()}
    core=dict(extractor=METHOD,files=hashed,policy={'synthetic_virtual_source':True},revision=None,exclusions=[],dirty=[])
    snapshot=dict(core,files=files,identity=digest(core),delta=None,snapshot_kind='filesystem-no-history')
    # Six triples and four pairs: 26 claims, 10 groups, 16 redundant claims.
    grouping=[g for g,size in enumerate([3]*6+[2]*4+[1]*23) for _ in range(size)]
    pending={};observations=[]
    def rows(name,statement,path,provenance):
        c=dict(id=name,statement=statement,type='technical_fact',status='CONFIRMED',evidence=['e.'+name],provenance=provenance,last_verified='2026-11-01',depends_on=[],conflicts_with=[])
        e=dict(id='e.'+name,type='direct-technical',status='active',source=path,location=path+'#L1',content_hash=files[path]['hash'],description='Synthetic source occurrence.',substantiates=[name],captured_at='2026-11-01T00:00:00Z',provenance=provenance)
        return c,e
    for n in range(12507):
        path='source%05d.cs'%(n+100);provenance={'actor':'synthetic','method':'fixture'}
        name='new.'+str(n);statement='Synthetic structural fact '+str(n)+'.'
        if n<49:
            argument='Context'+str(grouping[n]);statement='root [.] contains AddDbContext<'+argument+'> persistence/configuration syntax.'
            name='scan.'+digest(['identity-v3','.','persistence',path[:-3]+':AddDbContext:'+argument])[:32]
            provenance={'actor':'deterministic-discovery','method':METHOD}
            observations.append(dict(id=name,category='persistence',project='.',path=path,line=1,anchor='Synthetic source occurrence.',statement=statement,subject=argument,method=METHOD,content_hash=files[path]['hash'],unsupported=False))
        c,e=rows(name,statement,path,provenance)
        value=life.batch([life.op('add','evidence',e['id'],0,e),life.op('add','claims',c['id'],0,c)],'Synthetic production shape',{'identity':snapshot['identity'],'revision':None,'kind':snapshot['snapshot_kind']})
        pending[digest(value)]=value
    state=dict(id=digest(['fixture',snapshot['identity']]),extractor=METHOD,snapshot=snapshot,coverage=files,observations=observations,candidates=list(pending),complete=False,processing_complete=True,state='COMPLETED_WITH_GAPS',ambiguous=['ambiguous.'+str(i) for i in range(451)],gaps=[{'reason':'synthetic gap','index':i} for i in range(460)],work={'remaining_files':0})
    with store.connection(True) as db:
        for n in range(697):
            c,e=rows('canonical.'+str(n),'Canonical fixture fact '+str(n)+'.','source%05d.cs'%(n+20000),{'actor':'synthetic','method':'fixture'})
            for kind,record in (('claims',c),('evidence',e)):
                db.execute('INSERT INTO records VALUES (?,?,?)',(record['id'],kind,canonical_json(record)))
                revision=dict(id=record['id'],kind=kind,revision=1,record=record,lifecycle='active',successor=None,plan='synthetic-fixture',reason='fixture',source=None,captured_at='2026-11-01T00:00:00Z',verified_at=None)
                db.execute('INSERT INTO revisions VALUES (?,?,?)',(record['id'],1,canonical_json(revision)))
        for cid,value in pending.items():db.execute('INSERT INTO queue VALUES (?,?,?,NULL)',(cid,canonical_json(value),'pending'))
        db.execute('INSERT INTO scans VALUES (?,?)',(state['id'],canonical_json(state)))
    return state,pending
