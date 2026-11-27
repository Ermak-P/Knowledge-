# DSH Harness 0.2.0 distribution validation

Implementation under test was commit `c98320d761d60c98267d47ade8906d2017218c7e` on `codex/dsh-registry-independent-distribution`, based on hardened commit `13c6cd7d07177be6abef3862cd83f4ab05ffe276`. The following commit records this report and the tested implementation. All changes are under `harness-dsh/`.

## Dependency installation

Linux x64 used Node.js 24.22.3 and npm 11.13.0. Each install started in a new directory with no `node_modules` and a separate empty cache. Both source installs ran lifecycle scripts. The lab proxy served the default npm registry and a separate `@deepseek-ai` scope route. The proxy fetched ordinary packages from the official registry and rewrote their registry metadata to the appropriate lab route.

The npm processes and lifecycle children inherited a process-local socket guard that rejects non-loopback Internet connections. A control request verified the guard rejected a non-loopback attempt. A separate `strace -f -e trace=connect` audit observed only loopback Internet socket destinations across the installs. The guard was scoped to the test processes, and the proxy had its own upstream access. The managed environment does not provide an independent network namespace. The test used `--no-audit --no-fund` for the minimal proxy and `--foreground-scripts --loglevel=http` for source install evidence. The released configuration leaves these options at npm's defaults.

| Check | Result |
| --- | --- |
| Fresh `npm ci` | PASS. Installed 319 packages. The scoped registry served 91 tarball requests. |
| Fresh `npm ci --omit=dev` | PASS. Installed 29 packages. The scoped registry served 14 tarball requests. |
| Production imports | PASS. Loaded the engineering entry, Verification, Evidence, stalegreen and fast-xml-parser. |
| Packed package plus two original companion tarballs | PASS. Fresh npm consumer installation and runtime imports through the release script. |
| Registry-style `npm install --legacy-peer-deps harness-dsh@0.2.0` | PASS. A controlled registry fixture served the main package and both exact companions. Engineering and observer exports loaded. No publication was performed. |
| Packed plugin under the native Cordis loader | PASS. Native DSH registered and ran `harness_run` through a real read-only Knowledge MCP, including review and final acceptance. |
| TLS certificate trust | PASS. A local HTTPS registry failed verification without the test CA. `NODE_EXTRA_CA_CERTS` and npm `cafile` each passed independently with certificate verification enabled. Corporate Windows system CA and forward proxy settings remain to be qualified on site. |

The npm consumer needs `legacy-peer-deps` for the same upstream legacy peer declarations as source install. `npm ls --all` with npm's normal peer diagnostics reports those explicitly unresolved or incompatible peers. The upstream tarballs retain their exact metadata and the application exercises the supported library entry points instead of activating the legacy Goal plugin. See [the dependency audit](DEPENDENCY-AUDIT.md).

## Regression results

| Command | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| `npm test` | 7 | 0 | 0 |
| `npm run test:library` | 2 | 0 | 0 |
| `npm run test:native` | 16 | 0 | 0 |
| `npm run test:acceptance` | 1 | 0 | 0 |
| `npm run test:provider` | 1 | 0 | 0 |

Native tests ran with `DSH_DOTNET_ACCEPTANCE=1`, SDK 10.0.404 and the preinstalled Knowledge MCP Python environment. They exercised actual DSH tool registration and dispatch, task isolation, stale-evidence handling, repair, TDD RED, GREEN and refactor, and read-only MCP. The .NET acceptance suite exercised the real Bash adapter, failed and successful builds/tests, test project discovery, TRX parsing, cancellation and a Unicode workspace. The initial SDK run hit a read-only-home NuGet migration mutex error. The successful rerun used a disposable NuGet migration marker and SDK home under the workspace. The test runner noted that the cancelled test host exited and PID 1 kept its zombie record. The native suites use scripted model responses. The provider suite uses a local scripted wire endpoint.

## Readiness

| Area | Verdict | Basis |
| --- | --- | --- |
| GitHub-independent dependencies | GO | Only two local archives and configured registries were needed in the isolated tests. |
| Corporate registry compatibility | CONDITIONAL GO | Default and scoped registry routing and private-CA trust worked in the lab. Corporate Artifactory and its complete package inventory were unavailable. |
| Source distribution | GO | Full and production installs, vendor integrity and source archive contents verified. |
| npm package distribution | CONDITIONAL GO | Tarball and registry-style installs passed. Registry distribution requires access to the two companion packages and approval of their names. |
| Native DSH integration | CONDITIONAL GO | Linux native DSH and the packed loader path passed. The deployed Desktop UI, sandbox and live Qwen/llama.cpp were unavailable. |
| Windows deployment | NO-GO | Windows execution was BLOCKED. Follow [local acceptance](DSH_LOCAL_VALIDATION.md) before production rollout. |
