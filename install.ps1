param([Parameter(Mandatory=$true)][string]$McpDir)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$SelectedPython = $null
$PythonArgs = @()
foreach ($Name in @('python3.12', 'python', 'python3')) {
  $Candidate = Get-Command $Name -ErrorAction SilentlyContinue
  if ($Candidate) {
    & $Candidate.Source -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)'
    if ($LASTEXITCODE -eq 0) { $SelectedPython = $Candidate.Source; break }
  }
}
if (-not $SelectedPython) {
  $Launcher = Get-Command py -ErrorAction SilentlyContinue
  if ($Launcher) {
    & $Launcher.Source -3.12 -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)'
    if ($LASTEXITCODE -eq 0) { $SelectedPython = $Launcher.Source; $PythonArgs = @('-3.12') }
  }
}
if (-not $SelectedPython) { throw 'Python 3.12 is required. Install Python 3.12 from python.org, then rerun this command.' }
& $SelectedPython @PythonArgs -I -X utf8 (Join-Path $PSScriptRoot 'install.py') --mcp-dir $McpDir
exit $LASTEXITCODE
