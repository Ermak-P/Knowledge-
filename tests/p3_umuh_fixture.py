"""Synthetic independent UMUH-like host. No production UMUH source or claims."""
from pathlib import Path
DOMAIN='components/Casebook.Domain/AdmissionRule.cs'
EVIDENCE='components/Casebook.Domain/RuleEvidence.cs'
ORIGINAL='''namespace Umuh.Rehearsal.Domain;
public class AdmissionRule
{
    public static int Clamp(int count) => count;
}
'''
EXPECTED=ORIGINAL.replace('=> count;','=> System.Math.Clamp(count, 0, 2);')
FIRST='namespace Umuh.Rehearsal.Domain;\npublic class RuleEvidence : System.Object {}\n'
SECOND='namespace Umuh.Rehearsal.Domain;\npublic class RuleEvidence : System.MarshalByRefObject {}\n'
THIRD='namespace Umuh.Rehearsal.Domain;\npublic class RuleEvidence : System.Exception {}\n'

def create(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    files={'global.json':'{"sdk":{"version":"10.0.404","rollForward":"disable","allowPrerelease":false}}',DOMAIN:ORIGINAL,
      'components/Casebook.Domain/Casebook.Domain.csproj':'<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>',
      'workflows/Intake.Application/Intake.Application.csproj':'<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup><ItemGroup><ProjectReference Include="../../components/Casebook.Domain/Casebook.Domain.csproj" /></ItemGroup></Project>',
      'workflows/Intake.Application/IntakePolicy.cs':'namespace Umuh.Rehearsal.Application;\npublic class IntakePolicy { public static int Accepted(int count) => Umuh.Rehearsal.Domain.AdmissionRule.Clamp(count); }\n',
      'checks/Acceptance.Probe/Acceptance.Probe.csproj':'<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net10.0</TargetFramework><OutputType>Exe</OutputType></PropertyGroup><ItemGroup><ProjectReference Include="../../workflows/Intake.Application/Intake.Application.csproj" /></ItemGroup></Project>',
      'checks/Acceptance.Probe/Program.cs':'''int failed = 0;
if (Umuh.Rehearsal.Application.IntakePolicy.Accepted(5) != 2) failed++;
if (Umuh.Rehearsal.Application.IntakePolicy.Accepted(-1) != 0) failed++;
if (Umuh.Rehearsal.Application.IntakePolicy.Accepted(1) != 1) failed++;
System.IO.File.WriteAllText(args[0], System.Text.Json.JsonSerializer.Serialize(new { action = System.Environment.GetEnvironmentVariable("HARNESS_ACTION_ID"), executed=3, failed }));
return failed == 0 ? 0 : 1;
''',
      'README.md':'Synthetic UMUH-like rehearsal only. Independent expected behavior: clamp counts into [0,2].\n'}
    for relative,text in files.items():
        path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')
    return root
