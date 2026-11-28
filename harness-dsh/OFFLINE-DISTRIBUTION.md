# Production-offline distribution candidate 0.2.3

Keep the existing 0.2.2 development source, manifest, registry lockfile and standard npm release process unchanged. The offline builder generates a separate 0.2.3 source ZIP, with all non-dev lock entries resolved to original local tarballs. Distinct nested versions and original SHA-512 integrity are preserved; dev-only entries remain registry based.

From the harness-dsh directory, with Python 3, Node/npm and original packages available:

    python scripts/build-offline.py . C:/Temp/DSH-release --archives C:/Temp/npm-archives

Repeat --archives for multiple directories. Optionally use --registry https://registry.npmjs.org/ on an authorized network to fetch missing originals. No TLS bypass. All missing or mismatched archives block output, as do unreviewed licenses, install scripts or native builds. The builder checks package identities, original integrity, license files, an empty-cache offline production npm ci, installed versions and engineering/library imports before generating the ZIP and SHA-256 sidecar. It does not bundle node_modules or publish to npm.

Extract the offline ZIP and run:

    npm ci --omit=dev --offline --no-audit --no-fund

The offline artifact is a source deployment, not an npm publication package. The standard source and npm publishing routes remain separate. The real 28 unique production archives have not been acquired or qualified in this environment. Synthetic npm 10 / Node 22 testing exercised local nested versions, an unavailable dev-only dependency, empty-cache npm ci and ZIP generation; Windows and supported Node/npm versions, full real package tree, native DSH and IPM2 are still unverified.
