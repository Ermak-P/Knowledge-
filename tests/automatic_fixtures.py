"""Public synthetic C# projects; real SDK/test adapter, scripted HTTP decisions only."""
import json,os
from pathlib import Path
from p2_fixtures import calls,final
from knowledge.util import loads
FEATURE='src/App/Feature.cs'
INITIAL='public static class Feature { public static string Value => "initial"; }\n'
FIXED='public static class Feature { public static string Value => "fixed"; }\n'
WRONG='public static class Feature { public static string Value => "wrong"; }\n'
PROJECTS=['unconventional/IpmAzureCommon.UnitTests.csproj','integration/IpmAzureAutotests.csproj','zz outside solution/Тесты Ω/ZZZTests.csproj']
PACKAGES='<PackageReference Include="Microsoft.NET.Test.Sdk" Version="18.7.0"/><PackageReference Include="xunit.v3" Version="3.2.2"/><PackageReference Include="xunit.runner.visualstudio" Version="3.1.5"/>'
def create(root,multi=False):
 root=Path(root);(root/'src/App').mkdir(parents=True);(root/'global.json').write_text('{"sdk":{"version":"10.0.404","rollForward":"disable"}}',encoding='utf-8');(root/'src/App/App.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>',encoding='utf-8');(root/FEATURE).write_bytes(INITIAL.encode())
 for n,path in enumerate(PROJECTS):
  p=root/path;p.parent.mkdir(parents=True);rel=os.path.relpath(root/'src/App/App.csproj',p.parent).replace('\\','/');tfm='<TargetFrameworks>net10.0;net10.0-windows</TargetFrameworks>' if multi and n==0 else '<TargetFramework>net10.0</TargetFramework>'
  p.write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup>'+tfm+'<OutputType>Exe</OutputType><IsPackable>false</IsPackable></PropertyGroup><ItemGroup>'+PACKAGES+'<ProjectReference Include="'+rel+'"/></ItemGroup></Project>',encoding='utf-8');(p.parent/'Test.cs').write_text('using Xunit; public class Behavior { [Fact] public void Works() { '+('Assert.Equal("fixed", Feature.Value);' if n==2 else 'Assert.Equal(2,1+1);')+' } }',encoding='utf-8')
 return root
class Decisions:
 def __init__(self,repair=False):self.turns={};self.requests=[];self.repair=repair;self.inventory=[];self.on_review=None
 def decide(self,b):
  self.requests.append(b);s=loads(b['messages'][0]['content']);role=s['runtime_role'];n=self.turns.get(s['agent'],0);self.turns[s['agent']]=n+1
  if role=='Main':
   if any(i['status']!='done' for i in s['ledger']['items']):return calls(('delegate',dict(role='Coding',assignment='Implement the authorized Feature.Value behavior')))
   if s['progress']['gates'].get('review',{}).get('verdict')!='approve':return calls(('delegate',dict(role='Reviewing',assignment='Independently check source and automatic test evidence')))
   return final()
  if role=='Coding':
   if n==0:return calls(('read',dict(path=FEATURE)))
   if n==1:
    last=[loads(m['content']) for m in b['messages'] if m['role']=='tool'][-1];item=next(i for i in s['ledger']['items'] if i['status']!='done');after=WRONG if self.repair and item['attempts']==1 else FIXED;return calls(('patch',dict(files=[dict(path=FEATURE,before=last['sha256'],after=after)])))
   return final()
  if role=='Reviewing':
   if n==0:
    if self.on_review:self.on_review()
    return calls(('read',dict(path=FEATURE)),('test_inventory',dict(offset=0,limit=10)))
   if n==1:
    values=[loads(m['content']) for m in b['messages'] if m['role']=='tool'];src=next(v for v in values if 'text' in v);inv=next(v for v in values if v.get('enabled'));self.inventory.append(inv);good=src['text']==FIXED and inv['status']=='PASS' and inv['completed']==inv['count'];return calls(('review',dict(verdict='approve' if good else 'reject',findings=[] if good else ['Source or test inventory incomplete'])))
   return final()
  return final()
def configuration(endpoint,dotnet,home,cache):
 return dict(version=2,provider=dict(endpoint=endpoint,model='synthetic-auto-tests',evidence='test-double'),capture='required',limits=dict(context_bytes=48000,recipe_seconds=240,elapsed_seconds=1800,tool_bytes=10000,requests=64),recipes=dict(build=dict(kind='build',argv=[str(dotnet),'build','Suite.sln','-m:1','-p:UseSharedCompilation=false'],result=dict(format='exit',path=''),rerun_safe=True,env=dict(DOTNET_ROOT=str(Path(dotnet).parent),DOTNET_CLI_HOME=str(home),NUGET_PACKAGES=str(cache),MSBUILDDISABLENODEREUSE='1'))))
def task():return dict(version=2,goal='Feature.Value must return fixed; all automatically discovered tests must pass.',kind='coding',writable=[FEATURE],recipes=['build'],existing_test_edits=[],acceptance=['Feature.Value returns fixed.','Full automatic test inventory and independent review pass.'],items=[])
