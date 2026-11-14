$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
py -3.12 -m venv .venv
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& .venv\Scripts\python.exe -m pip install -r requirements-dev.lock
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& .venv\Scripts\python.exe -m pip install --no-build-isolation ./packages/knowledge ./packages/harness
if ($LASTEXITCODE) { exit $LASTEXITCODE }
# Install the official native .NET 10 SDK first. This script has NOT been run on Windows.
& .venv\Scripts\python.exe scripts/setup_benchmark.py
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& .venv\Scripts\python.exe scripts/verify.py
exit $LASTEXITCODE
