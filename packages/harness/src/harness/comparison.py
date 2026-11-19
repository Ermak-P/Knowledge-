"""One shared-history baseline versus isolated role contexts; guarded tools in both."""
from pathlib import Path
from knowledge.util import require,canonical_json
from .runtime import Journal,config,configure,source_snapshot,local_path,DEFAULT_LIMITS
from .engine import start,status


def compare(root,task,destination):
    original=Journal(root);configuration=config(root);snapshot=source_snapshot(original.project,{**DEFAULT_LIMITS,**configuration['limits']}['file_bytes'])
    output=Path(destination).absolute();require(not output.exists(),'comparison-destination-must-be-absent')
    from knowledge.project import safe_path
    safe_path(output);output.mkdir(parents=True)
    runs={}
    for mode in ('single','multi'):
        target=output/mode;target.mkdir()
        for relative,value in snapshot.items():
            if not isinstance(value,str):continue
            source=original.project.root/relative;safe_path(source);dest=target/relative;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(source.read_bytes())
        configure(target,configuration,True);outcome=start(target,task,mode);report=status(target,outcome['run_id'])
        runs[mode]={'outcome':outcome,'metrics':report['metrics'],'agents':report['run']['agents'],'source_before':snapshot,'source_after':report['run']['source']}
    value={'version':1,'runs':runs,'provider_configuration':configuration['provider'],'same_task':task,
           'interpretation':'Shared reasoning history baseline and isolated role contexts, identical runtime role/tool/gate policies; all calls and reviews counted. Empty independent Knowledge bootstrap in both ordinary source copies.',
           'quality_speed_token_benefit':'NOT_ESTABLISHED','cache_condition':'provider-dependent; fixture usage synthetic; no live warm/cold claim'}
    (output/'comparison.json').write_text(canonical_json(value),encoding='utf-8')
    return {'ok':all(r['outcome']['ok'] for r in runs.values()),'comparison':value}
