"""Installed optional-provider transport boundary profiles; no live access claim."""
import argparse,json,subprocess,sys,time
from pathlib import Path
from unittest.mock import patch
from knowledge import cr_sources as src
from knowledge.util import KnowledgeError


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    spawn=subprocess.Popen;rows=[]
    for label,code,pages,wanted in [
        ('paginated-slurp','import json;print(json.dumps([[{"id":1}],[{"id":2}]]))',True,None),
        ('bounded-response','print("x"*512001)',False,'ucr-provider-response-too-large'),
        ('provider-timeout','import time;time.sleep(60)',False,'ucr-provider-timeout')]:
        calls=[]
        def controlled(argv,**kwargs):
            calls.append(argv);return spawn([sys.executable,'-I','-c',code],**kwargs)
        started=time.monotonic()
        with patch.object(src.shutil,'which',return_value='controlled-gh'),patch.object(src.subprocess,'Popen',side_effect=controlled):
            try:
                result=src._gh('/controlled/export',pages);assert wanted is None;assert result==[{'id':1},{'id':2}]
                assert calls[0][-2:]==['--paginate','--slurp'];outcome=result
            except KnowledgeError as error:
                assert error.code==wanted,(label,error.code,wanted);outcome=error.code
        rows.append(dict(case=label,status='PASS',seconds=time.monotonic()-started,transport_argv=calls,result=outcome))
    value=dict(status='PASS',profile='installed-real-subprocess-provider-boundaries',live_provider=False,checks=rows)
    (args.output/'result.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value,indent=2))
if __name__=='__main__':main()
