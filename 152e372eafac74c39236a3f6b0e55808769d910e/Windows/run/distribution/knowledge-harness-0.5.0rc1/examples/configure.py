"""Adapt the shipped runner template without storing credentials."""
import argparse,json
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--dotnet',type=Path,required=True);p.add_argument('--endpoint',default='http://127.0.0.1:9000/v1/chat/completions');p.add_argument('--model',default='controlled-demo');p.add_argument('--live',action='store_true');p.add_argument('--key-env');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 for executable in (a.dotnet,):
  if not executable.is_absolute() or not executable.is_file():p.error('Trusted executable must be an existing absolute path: '+str(executable))
 value=json.loads(Path(__file__).with_name('runner.json').read_text(encoding='utf-8'));value['recipes']['build']['argv'][0]=str(a.dotnet);value['provider'].update(endpoint=a.endpoint,model=a.model,evidence='live' if a.live else 'test-double')
 for recipe in value['recipes'].values():recipe['env']=dict(DOTNET_ROOT=str(a.dotnet.parent),DOTNET_CLI_HOME=str(a.output.absolute().parent/'.dotnet-home'),DOTNET_CLI_TELEMETRY_OPTOUT='1',MSBUILDDISABLENODEREUSE='1')
 if a.key_env:value['provider']['key_env']=a.key_env
 a.output.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');print(a.output.absolute())
if __name__=='__main__':main()
