"""Small repeatable synthetic extraction, resume and real stdio startup timings."""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from knowledge import discovery as d,lifecycle
from knowledge.auto_init import run,ScanError
from knowledge.store import Store

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from core_wire import Wire


def timed(fn,count=5):
    values=[]
    for _ in range(count):
        before=time.perf_counter();fn();values.append(time.perf_counter()-before)
    return {'seconds':values,'median_seconds':statistics.median(values)}


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--installation',type=Path);a=p.parse_args()
    result={'synthetic_only':True,'platform':platform.platform(),'python':sys.version,'knowledge_file':str(d.__file__)}
    with tempfile.TemporaryDirectory(prefix='core-metrics-') as tmp:
        base=Path(tmp);root=base/'source';root.mkdir()
        for n in range(30):(root/('Type%d.cs'%n)).write_text('public class Type%d {}\n'%n,encoding='utf-8')
        store=Store(root);store.init();lifecycle.upgrade(store,lifecycle.upgrade_preview(store)['fingerprint'])
        entry=d.inventory(root)['files']['Type0.cs']
        result['utf8_extraction_100_files']=timed(lambda:[d.extract(root,'Type0.cs',entry) for _ in range(100)])
        # Identical mixed raw bytes in both revisions; unsupported encodings
        # remain failures in baseline rather than being silently converted.
        mixed=base/'encodings';mixed.mkdir()
        for name,encoding,text in [('utf8.md','utf-8','Пример'),('bom.md','utf-8-sig','Пример'),('le.xml','utf-16','<r>Пример</r>'),('be.xml','utf-16-be','\ufeff<r>Пример</r>'),('legacy.xml','cp1251','<?xml version="1.0" encoding="windows-1251"?><r>Пример</r>')]:
            (mixed/name).write_bytes(text.encode(encoding))
        result['mixed_encoding_inventory']=timed(lambda:d.inventory(mixed))
        large=base/'large';large.mkdir();(large/'large.json').write_text(json.dumps({'data':'x'*1100000}),encoding='utf-8')
        result['large_json_inventory']=timed(lambda:d.inventory(large))
        output=base/'progress'
        with contextlib.redirect_stdout(io.StringIO()):
            before=time.perf_counter()
            try:run(root,output,max_files=10,max_calls=1)
            except ScanError:pass
            result['first_chunk_seconds']=time.perf_counter()-before
            checkpoint=json.loads((output/'checkpoint.json').read_text());before=time.perf_counter();code=run(root,output,max_files=10)
            result['resume']={'seconds':time.perf_counter()-before,'exit_code':code,'same_scan_id':json.loads((output/'checkpoint.json').read_text())['scan_id']==checkpoint['scan_id']}
        before=time.perf_counter();plan=store.prepare();result['prepare']={'seconds':time.perf_counter()-before,'ok':plan['ok']}
    if a.installation:
        install=a.installation;current=json.loads((install/'current.json').read_text());python=install/current['runtime']/('Scripts/python.exe' if os.name=='nt' else 'bin/python');bootstrap=install/'bootstrap'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        def startup(argv):
            wire=Wire(argv)
            try:wire.initialize();tools=wire.request(102,'tools/list')['tools'];result['catalog_tools']=len(tools)
            finally:wire.close()
            if wire.process.returncode:raise RuntimeError('MCP startup/shutdown failed')
        result['direct_mcp_handshake_catalog_shutdown']=timed(lambda:startup([python,'-I','-B','-m','knowledge.machine_mcp','--installation',install]))
        result['bootstrap_mcp_handshake_catalog_shutdown']=timed(lambda:startup([bootstrap,'-I','-B',install/'launch.py','mcp']))
        result['bootstrap_delta_median_seconds']=result['bootstrap_mcp_handshake_catalog_shutdown']['median_seconds']-result['direct_mcp_handshake_catalog_shutdown']['median_seconds']
        result['mcp_requests']=20  # initialize + tools/list for 10 actual sessions.
        result['installation_source_identity']=current.get('source_identity')
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
