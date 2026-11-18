"""Executed NTFS, PowerShell 5.1 and clean native launcher qualification."""
import ctypes,json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
from build_p4 import VERSION

def main():
    assert os.name=='nt','native Windows only'
    kit=Path(sys.argv[1]).absolute();out=Path(sys.argv[2]).absolute();out.mkdir(parents=True,exist_ok=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);fs=ctypes.create_unicode_buffer(64)
    kernel.GetVolumeInformationW.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_uint32]
    assert kernel.GetVolumeInformationW(Path.cwd().anchor,None,0,None,None,None,fs,64) and fs.value=='NTFS'
    ps=shutil.which('powershell.exe');assert ps
    shell=json.loads(subprocess.check_output([ps,'-NoProfile','-Command','[pscustomobject]@{PSEdition=$PSVersionTable.PSEdition;Version=$PSVersionTable.PSVersion.ToString()} | ConvertTo-Json -Compress'],text=True,encoding='utf-8-sig'));assert shell['PSEdition']=='Desktop' and shell['Version'].startswith('5.1.')
    with tempfile.TemporaryDirectory(prefix='p4-native-PS51-') as tmp:
        env=Path(tmp)/'Native Env'
        for label,args in [('install',['install','--env',env,'--profile','knowledge']),('doctor',['doctor','--env',env]),('uninstall',['uninstall','--env',env])]:
            p=subprocess.run([ps,'-NoProfile','-File',str(kit/'install.ps1'),*[str(x) for x in args]],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            (out/(label+'.log')).write_bytes(p.stdout);assert p.returncode==0,p.stdout.decode('utf-8',errors='replace')[-2000:]
    (out/'result.json').write_text(json.dumps(dict(status='PASS',product=VERSION,filesystem=fs.value,shell='Windows PowerShell 5.1',shell_version=shell['Version']),indent=2)+'\n')
if __name__=='__main__':main()
