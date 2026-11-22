"""Actual installed Knowledge-only CR persistence, no Harness/MCP dependency."""
import argparse,importlib.util,json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    import knowledge
    from knowledge.cr_workflow import Workflow
    assert Path(knowledge.__file__).is_relative_to(Path(sys.prefix))
    assert importlib.util.find_spec('harness') is None and importlib.util.find_spec('mcp') is None
    spec=importlib.util.spec_from_file_location('independent_cr_fixture',ROOT/'tests/cr_fixtures.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
    with tempfile.TemporaryDirectory(prefix='ucr-independent-') as tmp:
        root,snapshot=f.project(tmp);w=Workflow(root);state=f.ready(w,snapshot,f.decisions(snapshot));prepared=w.prepare(state['session'],state['revision']);saved=w.apply(state['session'],prepared['proposal']['plan'],prepared['revision'])
        assert saved['receipt']['records'] and w.store.context('retry transport deadline')['claims']
        assert 'harness' not in sys.modules and 'mcp' not in sys.modules
        value=dict(status='PASS',profile='knowledge-only-actual-persistence',harness_absent=True,mcp_absent=True,receipt=saved,knowledge_import=knowledge.__file__)
        (a.output/'result.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':'PASS','profile':value['profile']}))
if __name__=='__main__':main()
