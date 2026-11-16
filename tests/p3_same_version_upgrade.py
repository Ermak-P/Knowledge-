"""Actual original P3 wheels -> corrected same-version owned installation."""
import argparse,json,sys
from pathlib import Path
import harness,knowledge

def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['before','after']);p.add_argument('--root',type=Path,required=True);p.add_argument('--state',type=Path,required=True);a=p.parse_args()
    for module in (harness,knowledge):
        path=Path(module.__file__);assert path.is_relative_to(Path(sys.prefix)) and not path.is_relative_to(Path(__file__).resolve().parents[1])
    sys.path.insert(0,str(Path(__file__).parent))
    from p2_fixtures import project,configuration,task
    from fixtures import addition
    from harness.runtime import configure
    from harness import companion
    from knowledge.store import Store
    root=a.root
    original=b'{\r\n  "model": "prior-approved"\r\n}\r\n'
    if a.phase=='before':
        root=project(root);configure(root,configuration('http://127.0.0.1/v1/chat/completions'),True)
        (root/'Fixture.cs').write_bytes(b'public class RetainedFixture {}\n')
        store=Store(root);store.submit(addition('prior.retained','Synthetic source declares RetainedFixture.'));approval=store.prepare();store.apply(approval['fingerprint'],approval['fingerprint']);store.acknowledge(approval['fingerprint'])
        store.submit(addition('prior.pending','Synthetic retained pending observation.'))
        (root/'opencode.json').write_bytes(original);(root/'task.json').write_bytes(json.dumps(task(kind='read-only')).encode('utf-8'))
        plan=companion.preview(root,'task.json');assert plan['preview']['version']==1 and not hasattr(companion,'validate_entry')
        companion.apply(root,plan['preview'],plan['fingerprint'])
        value={'versions':[knowledge.__version__,harness.__version__],'preview_version':1,'knowledge':store.export(),'marker_hex':(root/'.harness/companion.json').read_bytes().hex(),'feature_hex':(root/'Feature.cs').read_bytes().hex()}
        a.state.write_bytes((json.dumps(value,indent=2)+'\n').encode('utf-8'))
    else:
        before=json.loads(a.state.read_bytes());store=Store(root)
        assert before['versions']==[knowledge.__version__,harness.__version__]==['0.3.0rc1','0.3.0rc1']
        assert hasattr(companion,'validate_entry') and companion.doctor(root)['ok']
        assert store.export()==before['knowledge']
        plan=companion.preview(root,remove=True);assert plan['preview']['version']==2
        companion.apply(root,plan['preview'],plan['fingerprint'])
        assert (root/'opencode.json').read_bytes()==original
        assert bytes.fromhex(before['marker_hex']) in [p.read_bytes() for p in (root/'.harness').glob('companion-removed-*')]
        assert store.export()==before['knowledge'] and (root/'Feature.cs').read_bytes().hex()==before['feature_hex']
        value={'same_version_candidate_refresh':True,'prior_preview_version':1,'current_preview_version':2,'actual_new_authority_code_imported':True,'nonempty_knowledge_and_pending_preserved':True,'legacy_marker_exact_removal':True,'application_preserved':True,'versions':[knowledge.__version__,harness.__version__],'prefix':sys.prefix}
    print(json.dumps(value))

if __name__=='__main__':main()
