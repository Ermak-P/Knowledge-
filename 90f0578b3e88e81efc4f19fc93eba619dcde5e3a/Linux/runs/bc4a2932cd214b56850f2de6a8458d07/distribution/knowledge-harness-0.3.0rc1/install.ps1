param([Parameter(ValueFromRemainingArguments=$true)][string[]]$InstallArgs)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$Launcher = Get-Command py -ErrorAction SilentlyContinue
if ($Launcher) {
  & $Launcher.Source -3.12 (Join-Path $PSScriptRoot 'install.py') @InstallArgs
} else {
  $Python = Get-Command python -ErrorAction Stop
  & $Python.Source (Join-Path $PSScriptRoot 'install.py') @InstallArgs
}
exit $LASTEXITCODE
