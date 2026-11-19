$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSEdition -ne 'Desktop' -or $PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1) {
  throw 'Native P4 qualification requires Windows PowerShell 5.1.'
}
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
# Retain the accepted path policy: select normal spelling, never allow RUNNER~1.
$FixtureParent = $env:RUNNER_TEMP
if (-not $FixtureParent) { $FixtureParent = Join-Path $env:LOCALAPPDATA 'KnowledgeP4' }
$FixtureTemp = Join-Path $FixtureParent 'knowledge-p4-native-fixtures'
if ($FixtureTemp.Contains('~')) { throw 'Select a normal-spelling native temporary directory.' }
New-Item -ItemType Directory -Force -Path $FixtureTemp | Out-Null
$env:TEMP = $FixtureTemp
$env:TMP = $FixtureTemp
$env:TMPDIR = $FixtureTemp
Set-Location (Split-Path $PSScriptRoot -Parent)
python scripts/setup_p3.py
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& .venv/Scripts/python.exe -X utf8 -B scripts/verify_p4.py
exit $LASTEXITCODE
