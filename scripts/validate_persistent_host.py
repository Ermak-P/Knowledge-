"""Opt-in real OpenCode/local-model A02 trial, isolated project/shared stores.

This is intentionally separate from the deterministic hook-contract test. No
--continue, --session, transcript replay, remote model, or permission expansion.
"""
import argparse
import importlib.resources
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--opencode',default='opencode')
    parser.add_argument('--endpoint',default='http://127.0.0.1:11434/v1/chat/completions')
    parser.add_argument('--model',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.absolute();out.mkdir(parents=True,exist_ok=True)
    result={'status':'BLOCKED','kind':'real OpenCode + local model','scenario':'encoding','reason':'not run',
        'host_executable':shutil.which(args.opencode),'host_version':None,'model':args.model,'endpoint':args.endpoint,
        'compatibility':{'plugin_contract':'@opencode-ai/plugin 1.19.6','mcp_layout':'OpenCode v2 companion',
            'actual_combination_validated':False},
        'verdict':'IMPLEMENTED / HOST VALIDATION PENDING',
        'real_host_checks':{'A01':'BLOCKED','A02':'BLOCKED','A05':'NOT RUN: follow Kafka host guide','A17':'NOT RUN: follow Kafka host guide'}}
    executable=shutil.which(args.opencode)
    if not executable:
        result['reason']='OpenCode executable unavailable; no host session was simulated'
        (out/'host-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return 2
    endpoint=urlsplit(args.endpoint)
    assert endpoint.scheme in ('http','https') and endpoint.hostname in ('127.0.0.1','localhost','::1') and not endpoint.username and not endpoint.password and endpoint.path.endswith('/chat/completions') and not endpoint.query and not endpoint.fragment,'only a loopback local-model endpoint is supported'
    from p2_fixtures import project,configuration,task
    from test_persistent_instructions import binding
    from harness.runtime import configure,Journal
    from harness import companion
    from knowledge.operations import OperationalStore
    try:
        result['host_version']=subprocess.check_output([executable,'--version'],text=True,timeout=15).strip()
        with tempfile.TemporaryDirectory(prefix='knowledge-real-host-') as temporary:
            base=Path(temporary);root=project(base/'project');shared=base/'home/.local/share/knowledge'
            cfg=configuration(args.endpoint);cfg['provider']={'endpoint':args.endpoint,'model':args.model,'evidence':'live'}
            cfg['memory']={'shared_root':str(shared),'bindings':[binding()]};configure(root,cfg,True)
            (root/'Feature.cs').write_bytes(b'\xef\xbb\xbfpublic class InitialFeature {}\r\n')
            test=root/'test_feature.py';test.write_text(test.read_text().replace('read_text()','read_text(encoding="utf-8-sig")'))
            goal=task();goal['goal']='Change Feature.cs to public class ImprovedFeature {} and run configured build/test/review through Harness.'
            (root/'task.json').write_text(json.dumps(goal),encoding='utf-8')
            plugin=importlib.resources.files('knowledge').joinpath('host/opencode.mjs')
            host={'provider':{'local':{'npm':'@ai-sdk/openai-compatible','options':{'baseURL':args.endpoint.rsplit('/chat/completions',1)[0]},'models':{args.model:{'name':args.model}}}},
                  'enabled_providers':['local'],'model':'local/'+args.model,'small_model':'local/'+args.model,
                  'plugin':[Path(str(plugin)).as_uri()],'autoupdate':False,'share':'disabled'}
            (root/'opencode.json').write_text(json.dumps(host,ensure_ascii=False),encoding='utf-8')
            (root/'.knowledge-host.json').write_text(json.dumps({'python':sys.executable}),encoding='utf-8')
            # Plugin/provider/config MUST precede enrollment. Later host-config
            # mutation is rejected by the original digest guard, not repaired here.
            preview=companion.preview(root,'task.json');companion.apply(root,preview['preview'],preview['fingerprint'])
            assert companion.doctor(root)['ok'],'enrolled host configuration is inconsistent'
            def host_run(name,text):
                with (out/(name+'.jsonl')).open('wb') as log:
                    proc=subprocess.run([executable,'run','--format','json','--model','local/'+args.model,text],cwd=root,stdout=log,stderr=subprocess.STDOUT,timeout=240)
                assert proc.returncode==0,'host run failed; inspect '+name+'.jsonl'
            host_run('teaching','Remember encoding: preserve existing encoding, BOM presence and line endings when editing files.')
            records=OperationalStore(root,'project',shared).records()['records'];assert len(records)==1 and records[0]['status']=='active','actual host did not durably capture teaching'
            remembered=records[0];teaching_session=remembered['provenance']['id'].split('/')[0]
            assert (root/'Feature.cs').read_bytes()==b'\xef\xbb\xbfpublic class InitialFeature {}\r\n','teaching session unexpectedly edited the fixture'
            # First process has terminated. This prompt contains no encoding rule.
            host_run('fresh-session','Change Feature.cs to public class ImprovedFeature {} and run the configured checks.')
            runs=Journal(root).runs();assert runs and any(run.get('status')=='completed' for run in runs),'fresh host did not execute the guarded task'
            run=next(r for r in runs if r.get('status')=='completed')
            assert run.get('host_session') and run['host_session']!=teaching_session,'independent host session not established'
            actions=Journal(root).actions(run['id'])
            assert any(s['id']==remembered['id'] for a in actions.values() for t in a.get('memory_traces',[]) for s in t.get('selected',[])),'broker did not retrieve remembered revision'
            assert (root/'Feature.cs').read_bytes()==b'\xef\xbb\xbfpublic class ImprovedFeature {}\r\n','byte preservation failed'
            (out/'run.json').write_text(json.dumps({'run':run,'actions':actions},indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
            result.update(status='PASS',reason=None,teaching_session=teaching_session,fresh_session=run['host_session'],record={'id':remembered['id'],'revision':remembered['revision']},model=args.model)
            assert companion.doctor(root)['ok'],'host configuration changed after enrollment'
            result['compatibility']['actual_combination_validated']=True
            result['real_host_checks'].update(A01='PASS: encoding host trial',A02='PASS: encoding host trial')
    except (AssertionError,OSError,ValueError,subprocess.SubprocessError) as error:
        result.update(status='FAIL',reason=str(error))
    (out/'host-validation.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print(json.dumps(result));return 0 if result['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
