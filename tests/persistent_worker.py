"""Independent installed-code broker fixture, no transcript or model reminder."""
import json
from pathlib import Path
import sys
import time
import uuid
from harness.runtime import Journal,Lease,config,source_snapshot,recipe_inputs,blob
from harness.tools import Broker
from knowledge.util import digest


def main():
    request=json.load(sys.stdin);root=Path(sys.argv[1]);journal=Journal(root);configuration=config(root)
    source=source_snapshot(journal.project)
    task={'version':1,'kind':'coding','goal':'fixture','writable':['Feature.cs'],'existing_test_edits':[],
          'recipes':list(configuration['recipes']),'initial_source':source}
    protected,executables=recipe_inputs(journal.project,configuration,task)
    run={'version':1,'id':uuid.uuid4().hex,'project':journal.project.identity,'status':'running','started':time.time(),
         'task':task,'source':source,'config_hash':digest(configuration),'gates':{},'agents':[],'frames':[],'requests':[],
         'capture':{},'protected_paths':protected,'protected_executables':executables,
         'current_restrictions':request.get('restrictions',[])}
    if request.get('host_session'):run['host_session']=request['host_session']
    journal.save(run)
    with Lease(journal) as lease:
        broker=Broker(journal,configuration,run,lease)
        if request.get('patch'):
            result=broker.execute('Coding','operation','patch',{'files':[{'path':'Feature.cs','before':source.get('Feature.cs'),'after':request['patch']}]})
        else:result=broker.execute('Testing','operation','recipe',{'name':request.get('recipe','test')})
    with journal.db() as db:actions={i:json.loads(p) for i,p in db.execute('SELECT id,payload FROM actions WHERE run=?',(run['id'],))}
    print(json.dumps({'result':result,'actions':actions,'run_id':run['id']}))


if __name__=='__main__':main()
