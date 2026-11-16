"""Portable, offline core installer/uninstaller. Python 3.12, no product imports."""
import argparse,hashlib,json,os,platform,subprocess,sys,venv,zipfile
from pathlib import Path

VERSION='0.3.0rc1'
def python_at(env):return env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
def require(value,reason):
    if not value:raise RuntimeError(reason)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def call(args,**kwargs):subprocess.run([str(a) for a in args],check=True,**kwargs)
def manifest(base):
    m=json.loads((base/'RELEASE.json').read_text(encoding='utf-8'))
    require(m['version']==1 and m['product']==VERSION,'unsupported release manifest')
    for name,expected in m['files'].items():
        path=Path(name);require(not path.is_absolute() and '..' not in path.parts and '\\' not in name and ':' not in name,'unsafe release path')
        require(not any(part.is_symlink() or (hasattr(part,'is_junction') and part.is_junction()) for part in [base/path,*(base/path).parents]),'linked release artifact')
        require(sha(base/path)==expected,'release checksum mismatch: '+name)
    return m

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['install','uninstall','doctor']);p.add_argument('--env',type=Path,required=True);p.add_argument('--profile',choices=['knowledge','full'],default='full');p.add_argument('--adopt',action='store_true');p.add_argument('--mcp-online',action='store_true');a=p.parse_args()
    require(sys.version_info[:2]==(3,12),'supported Python is 3.12; preserve other environments')
    base=Path(__file__).resolve().parent;m=manifest(base);env=a.env.absolute();marker=env/'knowledge-release-install.json';python=python_at(env)
    require('..' not in env.parts and not any(part.is_symlink() or (hasattr(part,'is_junction') and part.is_junction()) for part in [env,*env.parents]),'linked or escaping installation path')
    require(not marker.is_symlink(),'linked installation marker')
    previous=json.loads(marker.read_text(encoding='utf-8')) if marker.exists() else None
    if previous is not None:
        require(previous.get('version')==1 and previous.get('product')==VERSION and os.path.normcase(previous.get('environment',''))==os.path.normcase(str(env)),'unsupported or mismatched installation marker')
        require(isinstance(previous.get('owned_packages'),list) and set(previous['owned_packages'])<={'knowledge-p0','harness-p0'},'invalid installation ownership')
    if a.command=='install':
        if env.exists():
            require(previous is not None or a.adopt,'existing environment is not owned; explicit --adopt required')
            require(python.is_file() and (env/'pyvenv.cfg').is_file(),'target is not an isolated venv')
        else:venv.EnvBuilder(with_pip=True).create(env)
        versions=json.loads(subprocess.check_output([str(python),'-I','-c','import sys,json;print(json.dumps(list(sys.version_info[:2])))'],text=True));require(versions==[3,12],'incompatible existing Python')
        installed=json.loads(subprocess.check_output([str(python),'-I','-c','import importlib.metadata as m,json;names=("knowledge-p0","harness-p0");p=m.packages_distributions();print(json.dumps({"imports":{n:p.get(n,[]) for n in ("knowledge","harness")},"versions":{n:m.version(n) for n in names if any(d.metadata["Name"]==n for d in m.distributions())}}))'],text=True))
        require(set(installed['imports']['knowledge'])<={'knowledge-p0'} and set(installed['imports']['harness'])<={'harness-p0'},'competing import distribution; preserve environment and resolve explicitly')
        require(installed['versions'].get('knowledge-p0') in (None,'0.1.0',VERSION) and installed['versions'].get('harness-p0') in (None,'0.2.0',VERSION),'unsupported installed product version')
        require(a.profile!='knowledge' or not installed['imports']['harness'],'profile downgrade requires product uninstall or a fresh environment')
        wheels=[base/name for name in m['files'] if name.endswith('.whl') and (a.profile=='full' or Path(name).name.startswith('knowledge_p0-'))]
        require(len(wheels)==(2 if a.profile=='full' else 1),'incomplete core wheel set')
        call([python,'-I','-m','pip','install','--no-index','--no-deps','--disable-pip-version-check',*wheels])
        if a.mcp_online:call([python,'-I','-m','pip','install','--disable-pip-version-check','-r',base/'optional-mcp.lock'])
        call([python,'-I','-m','pip','check'])
        owned=['knowledge-p0']+(['harness-p0'] if a.profile=='full' else [])
        if previous:owned=sorted(set(owned)|set(previous['owned_packages']))
        value=dict(version=1,product=VERSION,profile=a.profile,owned_packages=owned,environment=str(env),release_sha256=sha(base/'RELEASE.json'),adopted=bool(a.adopt),mcp_online=a.mcp_online)
        marker.write_text(json.dumps(value,indent=2),encoding='utf-8')
    elif a.command=='uninstall':
        require(previous is not None,'installation ownership marker required')
        require(previous['version']==1 and previous['environment']==str(env),'installation marker mismatch')
        call([python,'-I','-m','pip','uninstall','--yes',*previous['owned_packages']])
        value={**previous,'owned_packages':[],'profile':'uninstalled'};marker.write_text(json.dumps(value,indent=2),encoding='utf-8')
    else:
        require(previous is not None,'installation marker absent')
        code='import importlib.metadata as m,json,sys; print(json.dumps({"python":sys.version,"prefix":sys.prefix,"packages":{n:m.version(n) for n in '+repr(previous['owned_packages'])+'}}))'
        value=json.loads(subprocess.check_output([str(python),'-I','-c',code],text=True));value['marker']=previous
    print(json.dumps(dict(ok=True,result=value,platform=platform.platform())));return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except (RuntimeError,OSError,ValueError,subprocess.CalledProcessError) as error:print(json.dumps(dict(ok=False,error=str(error))));raise SystemExit(1)
