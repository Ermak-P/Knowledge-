"""All fixture statements/history are synthetic, never production records."""
import json
from pathlib import Path
from knowledge.store import empty
from knowledge.util import digest


def addition(name='synthetic.rule', statement='Synthetic basket preserves quantities.',status='CONFIRMED'):
    eid='evidence.'+name
    return {'version':1,'operation':'add','records':{
        'claims':[{'id':name,'statement':statement,'type':'technical_fact','status':status,
                   'evidence':[eid],'provenance':{'actor':'synthetic-test','method':'fixture-source'},
                   'last_verified':'2026-11-14' if status=='CONFIRMED' else None,'depends_on':[],'conflicts_with':[]}],
        'evidence':[{'id':eid,'type':'direct-technical','status':'active','source':'Fixture.cs',
                     'provenance':{'actor':'synthetic-test','method':'fixture-source'},
                     'captured_at':'2026-11-14T00:00:00Z','location':'Fixture.cs#L1',
                     'description':'Synthetic source fixture supports the statement.','substantiates':[name]}],
        'relationships':[]}}


def legacy_fixture(root):
    base=Path(root)/'.ai'
    a=addition('synthetic.confirmed'); b=addition('synthetic.inferred','Synthetic alternative interpretation.','INFERRED')
    a['records']['claims'][0]['conflicts_with']=['synthetic.inferred']
    b['records']['claims'][0]['conflicts_with']=['synthetic.confirmed']
    b['records']['claims'][0]['depends_on']=['synthetic.confirmed']
    records={g:a['records'][g]+b['records'][g] for g in a['records']}
    records['relationships']=[{'id':'synthetic.conflict','type':'conflicts_with','from':'synthetic.confirmed',
                               'to':'synthetic.inferred','provenance':{'actor':'synthetic-test','method':'fixture'}},
                              {'id':'synthetic.dependency','type':'depends_on','from':'synthetic.inferred',
                               'to':'synthetic.confirmed','provenance':{'actor':'synthetic-test','method':'fixture'}}]
    groups={'claims':'knowledge/claims','evidence':'evidence','relationships':'knowledge/relationships'}
    for g,items in records.items():
        d=base/groups[g]; d.mkdir(parents=True,exist_ok=True)
        for i,item in enumerate(items): (d/f'{i}.json').write_text(json.dumps(item))
    state=base/'state'; state.mkdir()
    pending=addition('synthetic.pending','Synthetic pending item.')
    queue=[{'id':'legacy-pending','payload':pending,'status':'pending','history':[{'event':'captured','synthetic':True}]},
           {'id':'legacy-imported','payload':a,'status':'imported','history':[{'event':'imported','synthetic':True}]}]
    (state/'candidates.json').write_text(json.dumps(queue))
    (state/'population/plans').mkdir(parents=True)
    def seal(value):
        import hashlib
        value=dict(value)
        value['fingerprint']='sha256:'+hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()
        return value
    plan=seal({'format':'population-plan-v1','synthetic':True,'records':records})
    pid=plan['fingerprint']
    (state/'population/plans'/f'{pid[7:]}.json').write_text(json.dumps(plan))
    transaction=state/'population/transactions'/pid[7:];transaction.mkdir(parents=True)
    journal=seal({'plan':pid,'state':'COMMITTED','installed':6,'attempt':1,
                  'history':[{'state':'COMMITTED','at':'2026-11-14T00:00:00Z'}]})
    (transaction/'journal.json').write_text(json.dumps(journal))
    from knowledge.legacy_validator import MANIFEST
    (base/'manifest.yaml').write_text(json.dumps(MANIFEST))
    import shutil
    from knowledge.store import SCHEMAS
    shutil.copytree(SCHEMAS,base/'schema')
    return records,queue
