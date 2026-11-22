"""Run using the official knowledge-only installation, with -I."""
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
from knowledge import operations as op,maintenance as m,sqlite_snapshot,sqlite_indexes


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert importlib.util.find_spec('harness') is None and importlib.util.find_spec('mcp') is None
    a.root.mkdir(parents=True,exist_ok=False);other=a.root.parent/'other';other.mkdir();shared=a.root.parent/'shared'
    (a.root/'Fixture.cs').write_text('class Fixture {}\n')
    binding={'trigger':{'tool':'patch','name':'Fixture.cs'},'behavior':{'adapter':'preserve-format'}}
    project=op.teach(a.root,'Remember project formatting',{'type':'user-message','id':'project'},binding=binding)
    common=op.teach(a.root,'Remember shared formatting',{'type':'user-message','id':'shared'},scope='shared',shared=shared,binding=binding)
    got=op.lookup(other,{'tool':'patch','name':'Fixture.cs'},{},shared=shared)
    assert [r['id'] for r in got['records']]==[common['id']]
    local=op.lookup(a.root,{'tool':'patch','name':'Fixture.cs'},{},shared=shared)
    assert [r['id'] for r in local['records']]==[project['id']]
    store=op.OperationalStore(a.root);before=hashlib.sha256(store.path.read_bytes()).hexdigest()
    preview=m.preview(a.root,'index-upgrade',a.root.parent/'backup.zip');result=m.apply(a.root,preview['preview'],preview['fingerprint'])
    assert before==hashlib.sha256(store.path.read_bytes()).hexdigest()
    assert 'harness' not in sys.modules and 'mcp' not in sys.modules
    value=dict(status='PASS',python=sys.executable,knowledge_import=str(Path(sqlite_snapshot.__file__)),harness_absent=True,mcp_absent=True,project_shared_isolation=True,core_canonical_bytes_unchanged=True,index_no_journal=result['status'])
    a.output.write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value))
if __name__=='__main__':main()
