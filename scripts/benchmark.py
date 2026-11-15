"""Run the real candidate pipeline and CLI/MCP/Harness query regression."""
import argparse
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from mcp import ClientSession, StdioServerParameters, stdio_client
from knowledge.store import Store
from knowledge.util import loads,canonical_json
from harness.consumer import context
from benchmark_dataset import PIN,QUESTIONS,dataset


def git(root,*args):
    return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()


def cli(root,*args):
    p=subprocess.run([sys.executable,'-m','knowledge.cli',*args,'--root',str(root)],capture_output=True,text=True)
    assert p.returncode==0,(args,p.stdout,p.stderr)
    return loads(p.stdout)


async def run(root,out):
    assert git(root,'rev-parse','HEAD')==PIN
    before=git(root,'diff','--binary','HEAD');assert before=='','Benchmark tracked source must be unchanged'
    out.mkdir(parents=True,exist_ok=True)
    payloads,provenance=dataset(root)
    s=Store(root);s.init()
    writes=[]
    with tempfile.TemporaryDirectory(prefix='knowledge-benchmark-') as tmp:
        for i,item in enumerate(payloads):
            f=Path(tmp)/f'{i}.json';f.write_text(canonical_json(item))
            writes.append(cli(root,'submit','--input',str(f)))
    plan=cli(root,'prepare');assert plan['ok']
    applied=cli(root,'apply','--plan',plan['fingerprint'],'--approve',plan['fingerprint'])
    ack=cli(root,'acknowledge','--plan',plan['fingerprint'])
    # Retry uses the same immutable plan and is a no-op; no duplicate import.
    cli(root,'apply','--plan',plan['fingerprint'],'--approve',plan['fingerprint'])
    cli(root,'acknowledge','--plan',plan['fingerprint'])
    assert s.validate()['counts']['claims']==len(payloads)
    (out/'benchmark-candidates.json').write_text(canonical_json(payloads)+'\n')
    (out/'benchmark-provenance.json').write_text(canonical_json(provenance)+'\n')
    (out/'benchmark-store-export.json').write_text(canonical_json(s.export())+'\n')
    answers=[]
    params=StdioServerParameters(command=sys.executable,args=['-B','-m','knowledge.mcp','--root',str(root)])
    async with stdio_client(params) as (reader,writer):
        async with ClientSession(reader,writer) as session:
            await session.initialize()
            for question,expected,unconfirmed in QUESTIONS:
                args=['context','--task',question,'--max-items','1']
                if unconfirmed: args.append('--include-unconfirmed')
                via_cli=cli(root,*args)
                response=await session.call_tool('knowledge_context',{'task':question,'max_items':1,'include_unconfirmed':unconfirmed})
                via_mcp=loads(response.content[0].text)
                # Harness has a fixed safety cap of 10 items. Compare expected
                # support/ranking rather than asserting identical envelopes/budgets.
                via_harness=context(root,question,include_unconfirmed=unconfirmed)
                got=[c['id'] for c in via_cli['claims']]
                hgot=[c['id'] for c in via_harness['context']['claims']]
                status= got==expected and via_cli==via_mcp and hgot[:len(expected)]==expected
                if not expected:status=status and not hgot
                answers.append({'question':question,'expected_claims':expected,'expected_evidence':['evidence.'+e for e in expected],
                                'actual_claims':got,'missing':sorted(set(expected)-set(got)),
                                'irrelevant':sorted(set(got)-set(expected)),'unsupported':[],
                                'cli_mcp_equal':via_cli==via_mcp,'harness_claims':hgot,
                                'harness_missing':sorted(set(expected)-set(hgot)),
                                'harness_extra_context_under_strict_support_oracle':sorted(set(hgot)-set(expected)),
                                'harness_unsupported':[],
                                'harness_evaluation':'Expected support must rank first; other lexical context is explicitly listed, not claimed relevant.',
                                'status':'PASS' if status else 'FAIL','cli':via_cli,'mcp':via_mcp,'harness':via_harness})
    with tempfile.TemporaryDirectory(prefix='knowledge-isolation-') as other:
        Store(other).init();assert Store(other).lookup('claims','eshop.basket.create')['record'] is None
        assert not context(other,'FastEndpoints')['context']['claims']
    after=git(root,'diff','--binary','HEAD');assert after==before
    (out/'benchmark-application.diff').write_text(after)
    # On repeated verification, retain proof of the original full import rather
    # than presenting the current empty no-op plan as the dataset's first import.
    desired={r['records']['claims'][0]['id'] for r in payloads}
    original_import=None
    with s.connection() as db:
        for pid,payload,state in db.execute('SELECT id,payload,status FROM plans'):
            previous=loads(payload)
            claims={c['id'] for item in previous['candidates'].values() for c in item['records']['claims']}
            if claims==desired and state in ('COMMITTED','ACKNOWLEDGED'):
                s._verify_committed(db,pid,previous)
                original_import={'fingerprint':pid,'state':state,'plan':previous,'payload_binding_verified':True}
                break
    assert original_import is not None,'Dataset must have a proven full pipeline import'
    result={'pin':PIN,'remote':'https://github.com/NimblePros/eShopOnWeb','record_count':len(payloads),'pipeline':{'submissions':writes,'original_full_import':original_import,'this_run_plan':plan,'apply':applied,'acknowledgment':ack},
            'queries':answers,'source_unchanged':True,'isolation':'PASS','retrieval_status':'PASS' if all(a['status']=='PASS' for a in answers) else 'FAIL',
            'scope':'Small curated lexical regression; not a broad accuracy metric. Build results are recorded separately.'}
    (out/'BENCHMARK-RESULTS.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(f"Benchmark: {len(payloads)} records, {sum(a['status']=='PASS' for a in answers)}/{len(answers)} queries pass")
    return 0 if result['retrieval_status']=='PASS' else 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('benchmarks/eShopOnWeb'));p.add_argument('--out',type=Path,default=Path('reports/P0'))
    a=p.parse_args();sys.exit(asyncio.run(run(a.root.resolve(),a.out.resolve())))
