# Remaining local DSH acceptance

## Required for Windows deployment

Run with a supported Windows DSH distribution, Node.js 24.22.3 or another supported release, Git, and the .NET 10 SDK. Start in a clean checkout of `codex/dsh-integration-hardening`.

```powershell
Set-Location .\harness-dsh
node --version
dotnet --version
npm ci
if ($LASTEXITCODE -ne 0) { throw 'npm ci failed' }
npm run test:acceptance
if ($LASTEXITCODE -ne 0) { throw 'Windows .NET acceptance failed' }
$env:DSH_DOTNET_ACCEPTANCE = '1'
npm run test:native
if ($LASTEXITCODE -ne 0) { throw 'Windows native lifecycle acceptance failed' }
Remove-Item Env:\DSH_DOTNET_ACCEPTANCE
```

The acceptance test selects the real PowerShell executor on Windows. Confirm the PowerShell executable required by the deployed DSH build is on PATH. Save the test output with the Windows edition, DSH version and commit, Node version, and SDK version. Verify that native output confirms a Unicode workspace, a running test host terminating on cancellation, and both failed-build and failed-test repair cases.

## Required for production qualification

### Deployed profile, sandbox and native UI

Run these commands from the repository root to prepare a disposable workspace and substitute the overlay paths. Use the actual distribution and its standard native-tool profile.

```powershell
$Harness = (Resolve-Path .\harness-dsh).Path
$Temp = Join-Path ([System.IO.Path]::GetTempPath()) ("DSH acceptance " + [guid]::NewGuid().ToString())
$Workspace = Join-Path $Temp 'Projet vérification'
New-Item -ItemType Directory -Path $Workspace -Force | Out-Null
Copy-Item -Path "$Harness\fixtures\dotnet\*" -Destination $Workspace -Recurse -Force
git -C $Workspace init
git -C $Workspace add .
git -C $Workspace -c user.name='DSH acceptance' -c user.email='acceptance@example.invalid' commit -m 'Disposable baseline'
$Overlay = Join-Path $Temp 'harness-overlay.yml'
$PluginPath = (Join-Path $Harness 'src\engineering.ts').Replace('\', '/')
$WorkspacePath = $Workspace.Replace('\', '/')
(Get-Content "$Harness\overlay.example.yml" -Raw).Replace('C:/Git/Knowledge-/harness-dsh/src/engineering.ts', $PluginPath).Replace('C:/Temp/DSH-Smoke', $WorkspacePath) | Set-Content $Overlay -Encoding utf8
```

From the upstream DSH source checkout, launch the native web profile with the overlay.

```powershell
pnpm dsh web --patch "$Overlay"
```

1. Open a session in `$Workspace`. Request a small Calculator behavior change with `harness_run`. Confirm the actual preset selects native tools and that the desktop or web trajectory shows Planning, Coding, Testing, Verification, the Gate, Reviewing, and the terminal result. Confirm the UI and logs provide a task ID, check result, gate reason, repair attempt, and review outcome without dumping raw output.
2. Test the deployed sandbox with build/test artifacts and the temporary TRX root. Confirm read and write scope, denied build-control or out-of-scope mutations, and correct treatment of the native sandbox policy. Unload the plugin during an active test, then check that the run terminates, the test host exits, and the tool and handlers are removed.
3. Run a live TDD scenario with an expected RED failure, GREEN, and a refactor followed by GREEN. Change an input frozen by RED and confirm acceptance blocks.
4. Validate each additional DSH version selected for deployment. Record its exact tag/commit and repeat the native loader, shell, and lifecycle checks.

### Production Knowledge and local model

1. Use the deployed Knowledge MCP configuration against a disposable database with automatic candidate capture disabled. Confirm that allowlisted reads work, unavailable or timed-out tools cannot supply acceptance evidence, malformed and access-denied responses are visible to the role, and denied writes leave the database unchanged.
2. Configure the actual Qwen model via the deployed llama.cpp OpenAI-compatible endpoint. With reasoning disabled, run the workflow through delegated roles, verify structured tool calls and schema errors, interrupt a generation, and exercise a provider timeout and a context-limit error. Confirm bounded retries and an explicit blocked or cancelled outcome where required. Record the model identifier, llama.cpp revision, and DSH configuration.

## Optional diagnostics

Measure fingerprint time and path count on a disposable copy of the deployment repository. Inspect ignored or external inputs before using that checkout for qualification. If a Windows test fails, collect the DSH shell outcome and the failing test name or compiler code alongside the operating system, SDK, Node, and DSH versions.
