[CmdletBinding(DefaultParameterSetName='Legacy', PositionalBinding=$false)]
param(
  [Parameter(ParameterSetName='Machine', Mandatory=$true)][string]$McpDir,
  [Parameter(ParameterSetName='Machine')][ValidateSet('readonly','maintainer')][string]$Mode,
  [Parameter(ParameterSetName='Legacy', ValueFromRemainingArguments=$true)][string[]]$InstallArgs
)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$SelectedPython = $env:KNOWLEDGE_PYTHON
$PythonArgs = @()
if (-not $SelectedPython) {
  $Candidate = Get-Command python -ErrorAction SilentlyContinue
  if ($Candidate) {
    & $Candidate.Source -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)'
    if ($LASTEXITCODE -eq 0) { $SelectedPython = $Candidate.Source }
  }
  if (-not $SelectedPython) {
    $Launcher = Get-Command py -ErrorAction SilentlyContinue
    if (-not $Launcher) { throw 'Python 3.12 is required; select its executable with KNOWLEDGE_PYTHON.' }
    $SelectedPython = $Launcher.Source
    $PythonArgs = @('-3.12')
  }
}
if ($McpDir) {
  $ModeArgs = @()
  if ($Mode) { $ModeArgs = @('--mode', $Mode) }
  & $SelectedPython @PythonArgs -I -X utf8 (Join-Path $PSScriptRoot 'machine-install.py') --mcp-dir $McpDir @ModeArgs
} else {
  & $SelectedPython @PythonArgs (Join-Path $PSScriptRoot 'install.py') @InstallArgs
}
exit $LASTEXITCODE
