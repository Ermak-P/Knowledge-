# Pinned eShopOnWeb baseline

- Remote: https://github.com/NimblePros/eShopOnWeb
- Full revision: `0c2c95d9d450d07fcd4e96e95e1cd48c20834e99`
- Ordinary checkout: `benchmarks/eShopOnWeb`, initially clean tracked/untracked state.
- `global.json`: SDK `10.0.0`, rollForward `latestFeature`.
- `Directory.Packages.props`: `net10.0`.
- Executed SDK: .NET **10.0.404**, Linux x64, verified against Microsoft's
  release metadata SHA-512. Exact URL/checksum: `scripts/dotnet-sdk.json`.
- Unit project: `tests/UnitTests/UnitTests.csproj`, xunit.v3 3.2.2,
  xunit.runner.visualstudio 3.1.5, Microsoft.NET.Test.Sdk 18.7.0.
  References ApplicationCore and Web (and their transitive project graph).

## Exact reproducible commands

From the product root:

```sh
bash scripts/setup.sh
.venv/bin/python scripts/setup_benchmark.py
.venv/bin/python scripts/verify.py
```

The verifier runs these commands in `benchmarks/eShopOnWeb` (the workspace used
`/workspace/dotnet/dotnet`; a fresh setup defaults to `.local/dotnet/dotnet`):

```sh
dotnet restore tests/UnitTests/UnitTests.csproj --disable-parallel -m:1
dotnet build tests/UnitTests/UnitTests.csproj --no-restore -m:1 -p:UseSharedCompilation=false -p:LibraryRestore=false
dotnet test tests/UnitTests/UnitTests.csproj --no-build --no-restore -m:1 -p:LibraryRestore=false --logger 'trx;LogFileName=without-knowledge.trx' --results-directory ABSOLUTE_PRODUCT_ROOT/reports/P0/dotnet-results
dotnet test tests/UnitTests/UnitTests.csproj --no-build --no-restore -m:1 -p:LibraryRestore=false --logger 'trx;LogFileName=after-knowledge.trx' --results-directory ABSOLUTE_PRODUCT_ROOT/reports/P0/dotnet-results
```

Environment initialization is explicit in `scripts/verify.py`: DOTNET_ROOT,
workspace-local DOTNET_CLI_HOME/NUGET_PACKAGES/TMPDIR, telemetry opt-out and
node reuse disabled. One MSBuild node and no compiler sharing avoid the initial
worker-node failure and keep resource use bounded (5 CPUs available).

Initial sandboxed restore failed to create `NuGet-Migrations` OS mutex.
Execution with the required OS permission succeeded. Initial Web build attempted
LibMan cdnjs downloads and failed on proxy HTTP 403. The installed upstream
`Microsoft.Web.LibraryManager.Build.targets` exposes `LibraryRestore=False`.
The .NET baseline uses this supported switch; it does not change source or
assert that browser assets/UI work. Package signature/TLS/checksum verification
was never disabled. NuGet warnings include upstream vulnerable/transitive
packages; no retargeting or package upgrade was made to the pinned application.

## Source trace and dataset

ApplicationCore BasketService creates missing baskets, manages quantities and
transfers anonymous baskets. Basket merges matching catalog items and removes
zero quantities. OrderService guards checkout, constructs item snapshots,
persists an order then publishes through Mediator. Infrastructure EfRepository
implements core repository interfaces using CatalogContext; CatalogContext
applies entity configurations. Web's AddCoreServices binds services/repositories.
PublicApi registers and uses FastEndpoints. These are verified source-level
statements; source declarations do not establish business rationale.

All 15 claims have exact source anchors, file SHA-256, revision identity and
project-relative line locations. One rationale remains INFERRED and derived;
it is never promoted to confirmed. `benchmark-provenance.json` contains the
anchor inventory; `benchmark-candidates.json` is the reproducible capture input.
`benchmark-store-export.json` records the generated canonical data and queue
history. `BENCHMARK-RESULTS.json` contains nine source-reviewed question
expectations and full CLI/MCP/Harness results, including no-answer and inferred
cases. This is a small lexical regression, not a broad retrieval accuracy claim.

## Retention and optional checks

`verify.py` runs the unit tests with integration absent, restores/creates
`.knowledge`, runs the real pipeline, then reruns the tests. It checks current-run
TRX counters, not an old file or an empty test run. Tracked application diff must
be exactly empty; `benchmark-application.diff` records it. Only `.knowledge`
was added to the benchmark; source/tests are unchanged. A separate synthetic
project cannot resolve these claims. Builds reuse restored dependencies.

SQL Server, browser UI, external identity, full Aspire/container workloads and
Azure deployment are NOT RUN and not required for the curated P0 dataset.
In-memory configuration observations do not prove real SQL Server behavior.
Upstream license is retained as `eShopOnWeb-LICENSE`; no upstream application
source is embedded in the review ZIP. Use the pinned fetch script to reconstruct.
