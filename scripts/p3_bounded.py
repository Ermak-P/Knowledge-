"""Modest larger installed-Knowledge fixture measures extraction, output and dedup."""
import argparse,json,sys,time
from pathlib import Path
from tempfile import TemporaryDirectory
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    import knowledge
    from knowledge import discovery as disc,lifecycle as life
    from knowledge.store import Store
    assert Path(knowledge.__file__).is_relative_to(Path(sys.prefix))
    with TemporaryDirectory(prefix='P3 bounded ') as tmp:
        root=Path(tmp)
        for partition in range(3):
            folder=root/('Layer'+str(partition));folder.mkdir();(folder/'Layer.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>',encoding='utf-8')
            for index in range(60):(folder/(f'Type{index}.cs')).write_text(f'namespace Bounded.Layer{partition};\npublic class Type{index} {{}}\n',encoding='utf-8')
        s=Store(root);s.init();life.upgrade(s,life.upgrade_preview(s)['fingerprint']);seen=[];original=disc.extract
        def counted(*args,**kwargs):seen.append(args[1]);return original(*args,**kwargs)
        disc.extract=counted;rows=[];began=time.monotonic();r=disc.scan(s,max_files=7);last=0
        while True:
            work=len(seen)-last;last=len(seen);rows.append(dict(extracted=work,output_bytes=len(json.dumps(r,ensure_ascii=False).encode()),remaining=r['work']['remaining_files']));assert work<=7
            if r['complete']:break
            r=disc.scan(s,r['id'],7)
        assert len(seen)==183 and len(set(seen))==183
        pending=len(s.status()['queue']);plan=s.prepare();assert plan['ok'];s.apply(plan['fingerprint'],plan['fingerprint']);s.acknowledge(plan['fingerprint']);record_count=s.validate()['counts']['claims']
        before=len(seen);again=disc.scan(s,r['id'],7);assert len(seen)==before and len(s.status()['queue'])==pending
        value=dict(version=1,source_files=183,chunks=len(rows),max_files=7,work=rows,actual_extractions=len(seen),repeat_extractions=0,duplicate_candidates=0,canonical_claims=record_count,wall_seconds=time.monotonic()-began,limitation='whole inventory/hashing per chunk remains distinct from bounded extraction; returned progress state grows with source inventory')
    (a.output/'bounded.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');print('PASS: 183 files across three projects, actual bounded extraction and zero duplicate work/candidates on completed resume.')
if __name__=='__main__':main()
