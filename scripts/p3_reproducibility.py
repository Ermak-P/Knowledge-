import argparse,json,subprocess,sys
from pathlib import Path
from p3_evidence import ROOT,sha

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--first',type=Path,required=True);p.add_argument('--source-id',required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    subprocess.run([sys.executable,'-B',str(ROOT/'scripts/build_p3.py'),'--output',str(a.output/'repeat'),'--source-id',a.source_id],check=True)
    original=a.first/'knowledge-harness-0.3.0rc1.zip';repeat=a.output/'repeat/knowledge-harness-0.3.0rc1.zip';assert sha(original)==sha(repeat),'distribution is not reproducible'
    (a.output/'reproducibility.json').write_text(json.dumps(dict(status='PASS',sha256=sha(original),second_sha256=sha(repeat),fixed_epoch='2025-01-01',normalized_wheel_records=True,zip_encoding='stored; fixed timestamps/modes independent of host umask/zlib'))+'\n',encoding='utf-8')
if __name__=='__main__':main()
