"""Verify a new draft's uploaded bytes; emit only compact asset metadata."""
import argparse,hashlib,json,subprocess,tempfile
from pathlib import Path


def verify(tag,commit,directory):
    value=json.loads(subprocess.check_output(['gh','release','view',tag,'--json','isDraft,url,tagName,targetCommitish,assets'],text=True))
    tagged=subprocess.check_output(['git','rev-parse','--verify',tag+'^{commit}'],text=True).strip()
    assert value['isDraft'] and value['tagName']==tag and tagged==commit,'Unexpected release identity or public publication'
    expected={p.name:p for p in directory.iterdir() if p.is_file() and (p.suffix=='.zip' or p.name.endswith('.zip.sha256'))}
    assert expected and any(n.endswith('.zip') for n in expected),'Missing distributable kit'
    assert set(expected)=={a['name'] for a in value['assets']},'Unexpected/missing release assets'
    assets={}
    with tempfile.TemporaryDirectory(prefix='knowledge-release-check-') as tmp:
        subprocess.run(['gh','release','download',tag,'--dir',tmp],check=True)
        for name,local in expected.items():
            actual=hashlib.sha256((Path(tmp)/name).read_bytes()).hexdigest()
            assert actual==hashlib.sha256(local.read_bytes()).hexdigest(),'Uploaded asset mismatch: '+name
            assets[name]=dict(sha256=actual,bytes=local.stat().st_size)
    return dict(kind='draft-release-assets',commit=commit,tag=tag,url=value['url'],draft=True,uploaded_bytes_verified=True,assets=assets)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tag',required=True);parser.add_argument('--commit',required=True);parser.add_argument('--directory',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    args.output.write_text(json.dumps(verify(args.tag,args.commit,args.directory),indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
