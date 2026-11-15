"""A native qualification receipt, or explicit NOT_RUN on another OS."""
import argparse,ctypes,json,os,platform,shutil,subprocess,sys,tempfile
from pathlib import Path
from p3_evidence import ROOT,save,sha

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--ledger',type=Path,required=True);p.add_argument('--kit',type=Path,required=True);a=p.parse_args();out=a.output.absolute();out.mkdir(parents=True,exist_ok=True)
    ledger=json.loads(a.ledger.read_text(encoding='utf-8'))
    if os.name!='nt':
        save(out/'native.json',dict(status='NOT_RUN',source_identity=ledger['source_identity'],reason='current host is Linux; no native Windows process/NTFS/PowerShell evidence supplied',handoff='powershell -NoProfile -File scripts/verify-windows.ps1; standard windows-latest Actions job',api_access='GitHub Actions API is not assumed available; CI receipts can be retained as ordinary artifacts'))
        print('NOT_RUN: native Windows/NTFS/PowerShell 5.1; Windows release remains NO_GO.');return
    k=ctypes.WinDLL('kernel32',use_last_error=True);fs=ctypes.create_unicode_buffer(64)
    k.GetVolumeInformationW.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_uint32]
    assert k.GetVolumeInformationW(Path.cwd().anchor,None,0,None,None,None,fs,64) and fs.value=='NTFS'
    ps=shutil.which('powershell.exe');assert ps
    version=json.loads(subprocess.check_output([ps,'-NoProfile','-Command','[pscustomobject]@{PSEdition=$PSVersionTable.PSEdition;Version=$PSVersionTable.PSVersion.ToString()} | ConvertTo-Json -Compress'],text=True,encoding='utf-8-sig'))
    save(out/'shell-probe.json',version)
    assert version['PSEdition']=='Desktop' and version['Version'].startswith('5.1.')
    results=json.loads((a.ledger.parent/'regressions/tests.json').read_text(encoding='utf-8'));assert results['preserved'] and results['skipped']==0 and results['success']
    lifecycle=json.loads((a.ledger.parent/'prior-upgrade/prior-upgrade.json').read_text(encoding='utf-8'))
    assert lifecycle['profile']=='windows-prior-knowledge-and-current-harness' and lifecycle['native_metadata_rollback'] and lifecycle['reinstall_preserved']
    assert lifecycle['prior_native_harness_upgrade']=='UNSUPPORTED' and lifecycle['prior_native_probe']['prior_store_preserved'] and lifecycle['prior_native_probe']['root_identity_preserved'] and lifecycle['prior_native_probe']['prior_knowledge_upgrade_and_code_data_rollback']
    native_cases=[r for r in results['results'] if '.NativeWindowsSafety.' in r['test'] or '.PlatformSafety.' in r['test']];assert len(native_cases)>=7 and all(r['status']=='PASS' for r in native_cases)
    with tempfile.TemporaryDirectory(prefix='PS51 путь ') as tmp:
        tmp=Path(tmp);runtime=tmp/'Native Env';kit=a.kit.absolute()
        for label,argv,expected in [('install',['install','--env',runtime,'--profile','knowledge'],0),('doctor',['doctor','--env',runtime],0),('failure',['doctor','--env',tmp/'absent'],1)]:
            p=subprocess.run([ps,'-NoProfile','-File',str(kit/'install.ps1'),*[str(v) for v in argv]],text=True,encoding='utf-8',errors='replace',capture_output=True,timeout=120)
            (out/('ps51-'+label+'.log')).write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==expected,(label,p.stdout,p.stderr)
    manifest=json.loads((a.kit/'RELEASE.json').read_text(encoding='utf-8'));required={'regressions':'PASS','platform':'PASS','offline-core':'PASS','lifecycle':'PASS','rehearsal':'PASS','application':'PASS','launchers':'PASS'}
    assert all(ledger['checks'][n]['status']=='PASS' for n in ('regressions','packaging','prior-upgrade','rehearsal','application'))
    save(out/'native.json',dict(status='PASS',source_identity=ledger['source_identity'],platform={'os':'Windows','version':platform.platform(),'python':platform.python_version(),'architecture':platform.machine(),'filesystem':fs.value,'shell':'Windows PowerShell 5.1','resolved_shell_version':version['Version']},required_checks=required,wheel_sha256={Path(p).name:h for p,h in manifest['files'].items() if p.endswith('.whl')},ci={'commit':os.environ.get('GITHUB_SHA'),'run_id':os.environ.get('GITHUB_RUN_ID'),'run_attempt':os.environ.get('GITHUB_RUN_ATTEMPT'),'workflow':os.environ.get('GITHUB_WORKFLOW'),'url':'https://github.com/'+os.environ.get('GITHUB_REPOSITORY','Ermak-P/Knowledge-')+'/actions/runs/'+os.environ.get('GITHUB_RUN_ID','local-native-run')},native_cases=native_cases))
    print('PASS: actual native Windows/NTFS/PowerShell 5.1 and installed-product suite.')
if __name__=='__main__':main()
