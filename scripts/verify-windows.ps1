$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSEdition -ne 'Desktop' -or $PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1) {
  throw 'This qualification entry requires native Windows PowerShell 5.1. PS7 is not claimed.'
}
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Set-Location (Split-Path $PSScriptRoot -Parent)
$Py = Get-Command py -ErrorAction SilentlyContinue
if ($Py) {
  & $Py.Source -3.12 scripts/setup_p3.py
} else {
  & python scripts/setup_p3.py
}
if ($LASTEXITCODE) { exit $LASTEXITCODE }
$Python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
& $Python -X utf8 -B scripts/setup_benchmark.py
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& $Python -X utf8 -B scripts/verify_p3.py
exit $LASTEXITCODE
