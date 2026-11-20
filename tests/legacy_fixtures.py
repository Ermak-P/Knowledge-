"""Non-SDK C# projects: preserve evaluated .NET Framework metadata and imports."""
import os
from pathlib import Path
from automatic_fixtures import create,PROJECTS,FEATURE
MINIMAL='''<Project ToolsVersion="15.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <Import Project="$(MSBuildExtensionsPath)/$(MSBuildToolsVersion)/Microsoft.Common.props" Condition="Exists('$(MSBuildExtensionsPath)/$(MSBuildToolsVersion)/Microsoft.Common.props')" />
  <PropertyGroup><OutputType>Library</OutputType><AssemblyName>LegacyTests</AssemblyName><TargetFrameworkVersion>v4.7.1</TargetFrameworkVersion><OutputPath>bin/Debug/</OutputPath></PropertyGroup>
  <Import Project="$(MSBuildToolsPath)/Microsoft.CSharp.targets" />
</Project>'''
def mixed(root):
 root=create(root);(root/'global.json').write_text('{"sdk":{"version":"8.0.408","rollForward":"disable"}}',encoding='utf-8')
 for project in [root/'src/App/App.csproj',*[root/x for x in PROJECTS[:2]]]:project.write_text(project.read_text().replace('net10.0','net8.0'),encoding='utf-8')
 p=root/PROJECTS[2];feature=os.path.relpath(root/FEATURE,p.parent).replace('\\','/')
 p.write_text('''<Project ToolsVersion="15.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <Import Project="$(MSBuildExtensionsPath)/$(MSBuildToolsVersion)/Microsoft.Common.props" Condition="Exists('$(MSBuildExtensionsPath)/$(MSBuildToolsVersion)/Microsoft.Common.props')" />
  <PropertyGroup>
    <ProjectGuid>{C547A8D8-341F-4A74-AC07-312DFBDE5873}</ProjectGuid><OutputType>Library</OutputType><AssemblyName>ZZZTests</AssemblyName>
    <TargetFrameworkVersion>v4.8</TargetFrameworkVersion><OutputPath>bin/Debug/</OutputPath><LangVersion>latest</LangVersion><RestoreProjectStyle>PackageReference</RestoreProjectStyle>
  </PropertyGroup>
  <ItemGroup><Reference Include="System"/><Reference Include="System.Core"/>
    <Compile Include="Test.cs"/><Compile Include="'''+feature+'''"><Link>Feature.cs</Link></Compile>
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="18.7.0"/>
    <PackageReference Include="xunit" Version="2.9.3"/>
    <PackageReference Include="xunit.runner.visualstudio" Version="3.1.5"/>
  </ItemGroup>
  <Import Project="$(MSBuildToolsPath)/Microsoft.CSharp.targets" />
</Project>''',encoding='utf-8')
 return root
