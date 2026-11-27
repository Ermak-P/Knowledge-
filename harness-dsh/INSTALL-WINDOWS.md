# Install and upgrade DSH Harness on Windows x64

Use Node.js 24.22.3 with npm 11.13.0 or a newer compatible release satisfying `package.json`. Keep your existing DSH Desktop, Knowledge MCP and llama.cpp installations. Use Git and the .NET 10 SDK for local acceptance.

## Install from the source ZIP

Extract to a staging location first. The ZIP has a single top-level `harness-dsh` folder.

```powershell
$Target = 'C:\LLM\Plugins\Harness-DSH'
$Stage = Join-Path (Split-Path $Target) ('Harness-DSH-stage-' + [guid]::NewGuid())
Expand-Archive .\Harness-DSH-source.zip -DestinationPath $Stage
$Extracted = Join-Path $Stage 'harness-dsh'
Push-Location $Extracted
npm ci --omit=dev
if ($LASTEXITCODE -ne 0) { Pop-Location; throw 'Harness installation failed' }
Pop-Location
if (Test-Path -LiteralPath $Target) { throw "Use the upgrade procedure for $Target" }
Move-Item -LiteralPath $Extracted -Destination $Target
```

Use `npm ci` in place of `npm ci --omit=dev` for the full development and acceptance installation. The ZIP includes the lockfile, both vendor archives, fixtures and tests. For deployment, copy `overlay.example.yml` to a user-managed location and set the plugin path to `C:/LLM/Plugins/Harness-DSH/src/engineering.ts` and the workspace to a disposable project. Load that overlay through the existing DSH profile procedure. Preserve your current DSH settings and overlay separately from the install directory.

## Install the generated npm package

Use a new or existing npm project at the target path. Install the main tarball and the two untouched companion tarballs from the source ZIP in the same npm command. This resolves the original package names and versions with npm's normal dependency handling.

```powershell
$Target = 'C:\LLM\Plugins\Harness-DSH'
$Downloads = 'C:\Temp\HarnessRelease'
$Vendor = Join-Path $Downloads 'extracted\harness-dsh\vendor'
New-Item -ItemType Directory -Force -Path $Target | Out-Null
Set-Location $Target
npm init -y # Run once in an empty npm project.
npm install --legacy-peer-deps (Join-Path $Downloads 'harness-dsh-0.2.0.tgz') (Join-Path $Vendor 'dsh-evidence-1.0.0.tgz') (Join-Path $Vendor 'dsh-verification-1.0.0.tgz')
if ($LASTEXITCODE -ne 0) { throw 'Harness package installation failed' }
```

Point the overlay to `C:/LLM/Plugins/Harness-DSH/node_modules/harness-dsh/src/engineering.js`. The optional observer entry is `src/index.js` in the same package. For later `npm ci --legacy-peer-deps` runs in this npm project, retain the original companion tarballs at their recorded locations. Use the source ZIP for full acceptance fixtures and tests.

## Corporate registry

Keep your existing npm registry, scoped registry, proxy and credentials in your managed npm settings. For a standard internal registry distribution, a registry administrator should approve the unscoped `harness-dsh` name and Apache-licensed companion names and versions. Configure routing for the `@bpc-oss` scope if required. Verify any versions already present against the release digests before using them.

With the approved registry URL in `$CorporateRegistry` and an authenticated publisher profile, publish the original tarballs and the generated package in this order.

```powershell
npm publish (Join-Path $Vendor 'dsh-evidence-1.0.0.tgz') --registry $CorporateRegistry
npm publish (Join-Path $Vendor 'dsh-verification-1.0.0.tgz') --registry $CorporateRegistry
npm publish (Join-Path $Downloads 'harness-dsh-0.2.0.tgz') --registry $CorporateRegistry
```

Check each command's exit code before moving on. This procedure requires the organization to authorize publishing under the listed names. Consumers can then install with `npm install --legacy-peer-deps harness-dsh@0.2.0` in their own npm project. Preserve the resulting consumer lockfile for subsequent `npm ci --legacy-peer-deps` runs. The npm package itself uses versioned dependencies because source-relative `file:` specs do not resolve against the installed package's source layout.

For the Windows system trust store, set `$env:NODE_USE_SYSTEM_CA = '1'`. If your organization supplies a PEM bundle, use `$env:NODE_EXTRA_CA_CERTS = 'C:\certs\corporate-ca.pem'` or configure npm's `cafile` in your user-level npm settings. Use your organization's configured HTTP/HTTPS proxy. Keep TLS verification enabled. For TLS or 401 errors, check the selected registry, trust chain and credentials in the current shell. For 404s, use [the inventory](DEPENDENCIES.csv) to report the exact missing package and version to the registry administrator. If the install unexpectedly attempts a native build, confirm the Windows x64 prebuild and optional packages are available and source builds are disabled in your npm configuration.

## Upgrade and rollback

Install the replacement in a separate staging directory on the same drive. Copy any user-owned local files to a separate location. Keep the DSH overlay file outside the install tree. Close DSH Desktop before switching versions.

```powershell
$Backup = "$Target-backup-$(Get-Date -Format yyyyMMdd-HHmmss)"
Move-Item -LiteralPath $Target -Destination $Backup
try {
    Move-Item -LiteralPath $Extracted -Destination $Target -ErrorAction Stop
} catch {
    Move-Item -LiteralPath $Backup -Destination $Target -ErrorAction Stop
    throw
}
```

Use the same approach for an npm-project upgrade after installing the replacement package and companion archives into the staging project. Preserve the companion paths that were recorded in that project's lockfile. If switching distribution types, update the user-managed overlay to the corresponding plugin path. To roll back, close DSH, move the new install aside, move the backup back to `$Target`, and restore the previous overlay if it changed.

## Local acceptance and release

Run `npm ci`, `npm test`, `npm run test:library` and the Windows procedures in [DSH_LOCAL_VALIDATION.md](DSH_LOCAL_VALIDATION.md). Qualify the deployed DSH Desktop profile, PowerShell execution, real read-only Knowledge MCP and Qwen/llama.cpp before production rollout.

From the committed Harness directory, developers can run `npm run release -- C:\Temp\HarnessRelease`. The script validates the vendor archives and metadata, performs fresh production and npm-consumer installs with the configured registry, and emits a versioned source ZIP, npm tarball and SHA-256 manifest outside the checkout. It performs no publication.
