# Dependency audit

[DEPENDENCIES.csv](DEPENDENCIES.csv) covers all 343 non-root lock entries. It records dependency roles, lock paths, sources, licenses, lifecycle flags, platform and engine requirements, and declared peers. The 29 production lock entries resolve to 28 unique local archives (two Apache-2.0 and 26 MIT). The remaining 314 entries are development-only and use the configured default or scoped npm registry. The 0.2.3 source lockfile preserves the original versions, nested paths and SHA-512 digests. [.npmrc](.npmrc) sets `omit-lockfile-registry-resolved=true` to keep the development registry configurable. See [archive provenance](vendor/UPSTREAM.md) and [SHA-256 checksums](vendor/SHA256SUMS).

The exact verification archive declares legacy Goal plugin peers. npm's default peer resolver would try to fetch incompatible or unavailable releases, including the legacy Goal package. Alternative D uses the library entry, and the Harness manifest declares the DSH packages used at runtime or in its test suites. The inventory lists peer ranges even where the resolver skips the peer. Keep `legacy-peer-deps=true` for the source installation and use the same setting when installing as an npm consumer.

## Installation and runtime paths

| Lifecycle entry | Inspected behavior |
| --- | --- |
| `@deepseek-ai/dsh-subprocess-local` postinstall | Sets the executable bit on a local node-pty helper when present. |
| `koffi` install | Selects a platform-specific registry optional package. If absent, CNoke can fall back to a local native build. The lock records the Windows x64 optional package. |
| `node-pty` install and postinstall | Checks registry tarball prebuilds and arranges local ConPTY files on Windows. The selected tarball ships Windows x64 and Linux x64 prebuilds. Missing prebuilds or forced source builds fall back to node-gyp, which may require compiler tools or an external Node headers download absent local headers. Keep optional packages and the prebuild path enabled. |
| `protobufjs` postinstall | Reads local package metadata for compatibility checks. |

The plugin loads Verification, Evidence, stalegreen and fast-xml-parser from production dependencies. DSH and the native shell are supplied by the deployed host. The development tree supplies the standalone Cordis loader, DSH runtime and testkit components, native shell adapters and c8. Optional binaries for other operating systems or architectures are skipped by npm. The .NET tests restore .NET fixture packages from the configured NuGet source. This is separate from npm installation. Knowledge acceptance starts the supplied Python executable with the existing Knowledge MCP package and a disposable database. Live model inference is supplied by DSH and llama.cpp.

The test installation requires registry access for development-only packages. The inventory provides package and version data for registry administrators. Registry and TLS settings come from npm or Node configuration. See [Windows installation](INSTALL-WINDOWS.md).
