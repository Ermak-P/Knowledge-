"""Installed-code, isolated Docker fixture acceptance. Never targets user services.

Run with an installed core Python. No OpenCode/local-model claim is made here.
"""
import argparse
from copy import deepcopy
import hashlib
import importlib.resources
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from test_persistent_instructions import setup_fixture,worker,ingress,binding
from harness.runtime import configure
from knowledge import operations as op


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--image',default='apache/kafka@sha256:4ceccc577f03f51f6af8dbfda55194d0d892f4fa7913ffbded567ce3895622ed')
    a=parser.parse_args();out=a.output.absolute();out.mkdir(parents=True,exist_ok=True)
    docker=shutil.which('docker');assert docker,'Docker executable unavailable'
    created=[];rows={};tag=uuid.uuid4().hex[:12]
    report={'type':'real installed broker subprocesses + isolated Docker; no model/real OpenCode',
            'host_e2e':'BLOCKED: OpenCode/local model absent','model_tokens':None,'performance_benefit':'NOT_ESTABLISHED','scenarios':rows}
    def command(*args):
        p=subprocess.run([docker,*args],capture_output=True,text=True,timeout=45)
        if p.returncode:raise RuntimeError(p.stderr)
        return p.stdout.strip()
    def own(name,*args):
        identifier=command('create','--name',name,'--label','knowledge.fixture='+tag,*args)
        created.append(identifier);return name
    def save(name,root,result,seconds):
        trace=result['actions']['operation'].get('memory_traces',[])
        processes=[v for v in result['actions'].values() if v.get('memory_parent')]
        rows[name]={'ok':result['result']['ok'],'error':result['result'].get('error'),'elapsed_seconds':seconds,
            'test_attempts':int('process_result' in result['actions']['operation']),
            'failed_test_attempts':int('process_result' in result['actions']['operation'] and not result['result']['ok']),
            'starts':sum(v['args']['name'].endswith('-start') for v in processes),
            'lookup_seconds':sum(t.get('lookup_seconds',0) for t in trace),
            'diagnosis_process_seconds':sum(v.get('process_result',{}).get('duration',0) for v in processes if any(s in v['args']['name'] for s in ('docker-info','docker-inspect','compose-locate'))),
            'recovery_process_seconds':sum(v.get('process_result',{}).get('duration',0) for v in processes if any(s in v['args']['name'] for s in ('-start','-probe'))),
            'selected_records':sum(len(t.get('selected',[])) for t in trace),'selected_bytes':sum(t.get('selected_bytes',0) for t in trace),
            'run_id':result['run_id'],'trace':trace}
        target=out/name;target.mkdir()
        (target/'result.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        artifacts=root/'.harness/artifacts'/result['run_id']
        if artifacts.exists():shutil.copytree(artifacts,target/'artifacts')
        return result
    def run(name,root,**request):
        began=time.monotonic();result=worker(root,**request);return save(name,root,result,time.monotonic()-began)
    def configure_dependency(root,shared,cfg,resource,port,**changes):
        p={'id':'local_broker','check':{'argv':[sys.executable,'-I','-m','knowledge.probes','kafka','--host','127.0.0.1','--port',str(port),'--timeout','1'],'timeout':4},
            'docker':{'executable':docker,'container':resource},'attempts':1,'deadline':30,'interval':.25}
        p.update(changes)
        b=binding('Kafka','dependency','local_broker',{'adapter':'dependency','procedure':p})
        b['applicability']={'environment':'isolated-fixture-'+tag}
        cfg['memory'].update(environment={'environment':'isolated-fixture-'+tag},bindings=[b],allowed_procedures=[p],requirements=[{'trigger':{'tool':'recipe','name':'test'},'dependency':'local_broker'}])
        configure(root,cfg)
        return p,b
    def teach(root):
        value=ingress(root,'Remember for all projects using my local Kafka environment: check readiness before required integration tests. You may start that specific local container for this purpose. Only if stopped; never restart a running service.')
        assert value['ok'] and value['status']=='active' and value['recovery_authorized'],value
        return value
    try:
        report['docker_version']=command('version','--format','{{.Server.Version}}')
        report['image']=json.loads(command('image','inspect',a.image))[0]['Id']
        with tempfile.TemporaryDirectory(prefix='persistent-acceptance-') as temporary:
            base=Path(temporary);root,shared,cfg=setup_fixture(base)
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            kafka=own('knowledge-kafka-'+tag,'-p',f'127.0.0.1:{port}:9092',
                '-e','KAFKA_NODE_ID=1','-e','KAFKA_PROCESS_ROLES=broker,controller',
                '-e','KAFKA_LISTENERS=PLAINTEXT://:9092,CONTROLLER://:9093',
                '-e',f'KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://127.0.0.1:{port}',
                '-e','KAFKA_CONTROLLER_LISTENER_NAMES=CONTROLLER','-e','KAFKA_CONTROLLER_QUORUM_VOTERS=1@localhost:9093',
                '-e','KAFKA_LISTENER_SECURITY_PROTOCOL_MAP=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT',
                '-e','KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1','-e','KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR=1',
                '-e','KAFKA_TRANSACTION_STATE_LOG_MIN_ISR=1','-e','KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS=0',a.image)
            p,b=configure_dependency(root,shared,cfg,kafka,port)
            test_code=f'import unittest,sys; from knowledge.probes import kafka; r=unittest.TextTestRunner().run(unittest.FunctionTestCase(lambda:kafka("127.0.0.1",{port},1))); sys.exit(not r.wasSuccessful())'
            cfg['recipes']['test']['argv']=[sys.executable,'-I','-c',test_code]
            cfg['memory']['enabled']=False;configure(root,cfg)
            baseline=run('baseline-stopped-memory-disabled',root);assert not baseline['result']['ok']
            assert command('inspect','--format','{{.State.Running}}',kafka)=='false'
            cfg['memory']['enabled']=True;configure(root,cfg);saved=teach(root);report['teaching']=saved
            stopped=run('A05-stopped',root);assert stopped['result']['ok'],stopped['result'];assert rows['A05-stopped']['starts']==1
            candidate=op.OperationalStore(root,'project',shared).records()
            observations=[r for r in candidate['records'] if r['kind']=='experience'];assert observations and all(r['status']=='candidate' for r in observations)
            report['candidates']=observations
            ready=run('A06-ready',root);assert ready['result']['ok'];assert rows['A06-ready']['starts']==0
            other_base=base/'other';other_base.mkdir();other,_,other_cfg=setup_fixture(other_base)
            other_cfg['memory']=deepcopy(cfg['memory']);other_cfg['recipes']=deepcopy(cfg['recipes']);configure(other,other_cfg)
            cross=run('A03-cross-project',other);assert cross['result']['ok']
            assert not (other/'.knowledge').exists(),'shared rule was copied into other project'
            assert len([r for r in op.OperationalStore(root,'shared',shared).records()['records'] if r['kind']=='instruction'])==1
            cfg['recipes']['test']['argv']=[sys.executable,'-c','import unittest,sys; r=unittest.TextTestRunner().run(unittest.FunctionTestCase(lambda:unittest.TestCase().assertEqual(1,2))); sys.exit(not r.wasSuccessful())'];configure(root,cfg)
            app=run('A08-application-failure',root);assert not app['result']['ok'];assert rows['A08-application-failure']['starts']==0
            command('stop','--time','3',kafka)
            cfg['recipes']['unit']=deepcopy(cfg['recipes']['test']);cfg['recipes']['unit']['argv']=[sys.executable,'-c','import unittest; unittest.TextTestRunner().run(unittest.FunctionTestCase(lambda:None))'];configure(root,cfg)
            unrelated=run('A08-unrelated',root,recipe='unit');assert unrelated['result']['ok'];assert rows['A08-unrelated']['starts']==0
            ingress(root,'Do not start services in this run.',session='current-restriction')
            restricted=run('A09-current-restriction',root,host_session='current-restriction');assert restricted['result'].get('error')=='current-service-start-denied',restricted['result']
            cfg['memory']['allowed_procedures']=[];configure(root,cfg)
            denied=run('A09-tool-denied',root);assert denied['result'].get('error')=='memory-procedure-tool-denied';assert rows['A09-tool-denied']['starts']==0
            for kind in ('missing','unhealthy','docker-unavailable'):
                case=base/kind;case.mkdir();r,s,c=setup_fixture(case)
                resource='knowledge-missing-'+tag
                if kind=='unhealthy':
                    resource=own('knowledge-unhealthy-'+tag,'--entrypoint','/bin/sh',a.image,'-c','sleep 120');command('start',resource)
                proc,bind=configure_dependency(r,s,c,resource,port,deadline=3)
                if kind=='docker-unavailable':
                    proc['docker']['executable']=str(base/'no-docker-executable');configure(r,c)
                teach(r)
                negative=run('A07-'+kind,r);assert not negative['result']['ok'];assert rows['A07-'+kind]['starts']==0
                expected={'missing':'docker-resource-missing','unhealthy':'dependency-running-not-ready','docker-unavailable':'instruction-binding-unavailable'}[kind]
                assert negative['result'].get('error')==expected,negative['result']
            # Semantic bridge: real isolated resource; local-model protocol double.
            # Missing resource details arrive once in a second genuine user event.
            from test_persistent_semantics import decision,local_normalizer,template
            semantic_base=base/'semantic';semantic_base.mkdir();sr,ss,sc=setup_fixture(semantic_base)
            capability=template();capability.update(docker=docker,deadline=30,interval=.25,check_timeout=4)
            first_text='Remember for all projects using local Kafka: check readiness before required tests. You may start that specific local container.'
            details=f'Use container {kafka} and port {port}.'
            first=decision(scope='shared',scope_explicit=True,scope_quote='all projects',authorize_recovery=True,
                permission_quote='You may start that specific local container.',summary='Check Kafka and start only its stopped configured container when permitted.',
                question='What are the configured container name and test-accessible port?')
            answer=decision(intent='clarify',scope='shared',summary=first['summary'],parameters={'container':kafka,'port':port},
                parameter_quotes={'container':f'container {kafka}','port':f'port {port}'})
            semantic_requests=[]
            with local_normalizer([first,answer],semantic_requests) as normalizer:
                sc['recipes']['test']['argv']=[sys.executable,'-I','-c',test_code]
                sc['memory'].update(teaching_mode='local-model',normalizer=normalizer,procedure_templates=[capability],allowed_templates=[capability['id']],
                    environment={'environment':'isolated-fixture-'+tag},
                    bindings=[{'aliases':['Kafka'],'trigger':{'tool':'dependency','name':'local_broker'},'template':capability['id'],'applicability':{'environment':'isolated-fixture-'+tag}}],
                    requirements=[{'trigger':{'tool':'recipe','name':'test'},'dependency':'local_broker'}]);configure(sr,sc)
                pending=ingress(sr,first_text);assert pending['status']=='unbound',pending
                before_binding=run('A16-resource-unbound',sr);assert before_binding['result'].get('error')=='instruction-binding-required';assert rows['A16-resource-unbound']['starts']==0
                bound=ingress(sr,details,message_id='resource-details');assert bound['status']=='active' and bound['id']==pending['id'] and bound['revision']==2,bound
            # No original dialog, no reminder, and the normalization endpoint is off.
            repaired=run('A16-resource-bound-fresh-process',sr);assert repaired['result']['ok'],repaired['result'];assert rows['A16-resource-bound-fresh-process']['starts']==1
            semantic_other=base/'semantic-other';semantic_other.mkdir();orr,_,orc=setup_fixture(semantic_other)
            orc['memory']=deepcopy(sc['memory']);orc['memory']['shared_root']=str(ss);orc['recipes']=deepcopy(sc['recipes']);configure(orr,orc)
            reused=run('A03-template-cross-project',orr);assert reused['result']['ok'];assert not (orr/'.knowledge').exists()
            assert len(semantic_requests)==2
            report['semantic_ingress']={'type':'local-model protocol double; actual installed ingress/SQLite/owned Docker execution',
                'record_id':bound['id'],'revision':bound['revision'],'normalizer_requests':len(semantic_requests),
                'user_teaching':first_text,'user_details':details,'retained_original':op.OperationalStore(sr,'shared',ss).records()['records'][0]['original'],
                'model_usage_evidence':'test-double only; no real model usage claim'}
            # Ordinary goal through the full CLI/role flow. The model protocol
            # is a double; dependency lookup/recovery/tests are production paths.
            from p2_fixtures import project,configuration,task,http_provider,FixtureProvider
            from harness.runtime import Journal
            command('stop',kafka)
            with http_provider(FixtureProvider()) as endpoint:
                fr=project(base/'ordinary-task');fc=configuration(endpoint);fc['capture']='off'
                fc['memory']=deepcopy(sc['memory']);configure(fr,fc)
                tf=fr/'test_feature.py';tf.write_text(tf.read_text().replace('  self.assertEqual(',
                    f'  from knowledge.probes import kafka\n  kafka("127.0.0.1",{port},1)\n  self.assertEqual('),encoding='utf-8')
                ft=task();ft['goal']='Implement the requested feature change and run the configured checks.'
                taskfile=fr/'.harness/task.json';taskfile.write_text(json.dumps(ft),encoding='utf-8')
                began=time.monotonic()
                cli=subprocess.run([sys.executable,'-I','-m','harness.run_cli','run','--root',str(fr),'--input',str(taskfile)],capture_output=True,text=True,encoding='utf-8',timeout=90)
                assert cli.returncode==0,cli.stdout+cli.stderr
                answer=json.loads(cli.stdout);journal=Journal(fr)
                with journal.db() as db:actions={i:json.loads(p) for i,p in db.execute('SELECT id,payload FROM actions WHERE run=?',(answer['run_id'],))}
                traces=[t for action in actions.values() for t in action.get('memory_traces',[])]
                starts=sum(action.get('memory_parent') is not None and action['args']['name'].endswith('-start') for action in actions.values())
                assert starts==1 and any(t['dependency_links'] for t in traces)
                assert all(not action.get('memory_traces') for action in actions.values() if action.get('memory_parent')),'recursive memory lookup'
                target=out/'A17-full-cli';target.mkdir()
                (target/'result.json').write_text(json.dumps({'result':answer,'actions':actions,'goal':ft['goal'],'type':'model protocol double; actual full CLI/role/broker/Docker integration'},indent=2)+'\n')
                rows['A17-full-cli']={'ok':True,'error':None,'elapsed_seconds':time.monotonic()-began,'starts':starts,'failed_test_attempts':0,
                    'selected_records':sum(len(t['selected']) for t in traces),'selected_bytes':sum(t['selected_bytes'] for t in traces),'dependency_links':[link for t in traces for link in t['dependency_links']],
                    'normalizer_requests_in_fresh_run':0,'model_evidence':'test-double'}
            # A19: same configured name now identifies a different owned object.
            # A ready dependency was previously pinned by the real A16 recovery.
            command('stop',kafka)
            retired_name='knowledge-retired-'+tag;command('rename',kafka,retired_name)
            own(kafka,a.image)  # Never started: its differing ID must be rejected.
            changed=run('A19-resource-changed',sr)
            assert changed['result'].get('error')=='docker-resource-changed',changed['result']
            assert rows['A19-resource-changed']['starts']==0
            # A20: a real start with a failing check must not be replayed by a
            # new worker. This fixture has its own rule/store and exact resource.
            blocked_base=base/'blocked';blocked_base.mkdir();br,bs,bc=setup_fixture(blocked_base)
            bp,bb=configure_dependency(br,bs,bc,retired_name,port,deadline=1,interval=.1,
                check={'argv':[sys.executable,'-I','-c','raise SystemExit(1)'],'timeout':1})
            remembered=teach(br)
            original=next(r['original'] for r in op.OperationalStore(br,'shared',bs).records()['records'] if r['id']==remembered['id'])
            failed=run('A20-readiness-failed',br)
            assert failed['result'].get('error')=='dependency-readiness-timeout',failed['result']
            assert rows['A20-readiness-failed']['starts']==1
            repeated=run('A20-fresh-no-replay',br)
            assert repeated['result'].get('error')=='memory-remedy-blocked',repeated['result']
            assert rows['A20-fresh-no-replay']['starts']==0
            state=op.OperationalStore(br,'shared',bs).records()
            intent=next(r for r in state['records'] if r['id']==remembered['id'])
            assert intent['original']==original
            assert intent['status']=='active' and state['bindings'][intent['id']]['state']=='blocked'
            report['stale_binding']={'record_id':intent['id'],'revision':intent['revision'],'user_intent_retained':True,
                'binding_state':state['bindings'][intent['id']]}
            # Published hook contract; UI is a fixture, ingress/storage are real.
            cfg['memory']['bindings']=[binding()];configure(root,cfg)
            plugin=importlib.resources.files('knowledge').joinpath('host/opencode.mjs')
            node=shutil.which('node');assert node,'Node needed for host hook contract'
            contract=subprocess.run([node,str(ROOT/'tests/persistent_host_contract.mjs'),str(plugin),sys.executable,str(root)],capture_output=True,text=True,timeout=30)
            (out/'host-contract.log').write_text(contract.stdout+contract.stderr,encoding='utf-8');assert contract.returncode==0,contract.stderr
            report['host_contract']='PASS (UI fixture; not real OpenCode)'
            logs=command('logs',created[0]);(out/'kafka.log').write_text(logs,encoding='utf-8')
        report['status']='PASS';report['incorrect_remedies']=0
    finally:
        for identifier in created:
            # Remove only resources created by this invocation with its label.
            label=command('inspect','--format','{{index .Config.Labels "knowledge.fixture"}}',identifier)
            assert label==tag,'fixture ownership changed'
            command('rm','-f','-v',identifier)
        report['files']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file() and p.name!='acceptance.json'}
        (out/'acceptance.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'ok':True,'report':str(out/'acceptance.json')}))


if __name__=='__main__':main()
