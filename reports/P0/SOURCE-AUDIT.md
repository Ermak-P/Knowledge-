# Source audit and delivered map

Input archive SHA-256: `734aa3f4b5231d96f82638c634d41eec445d61ae1eb47c91d076af9a13a81ee4`.
All 22 source/metadata checksums were verified before disposable extraction.
The archive remains unchanged. `LegacyReferenceTests` repeats checksum checks
and executes the original lexical assemble implementation for differential
ranking/status/no-answer comparisons. No unavailable historical files are claimed inspected.

## Actual input inventory

- `.ai/.gitignore` — `b92876e9cbdc04bebe2e7b17d6644181694c984e6489441f93b4a5e10264d43d`
- `.ai/README.md` — `f2d014857cdf474f6b333916922bdf9c2d4c74dac0713194985be7f2ded44539`
- `.ai/deployment-profile.json` — `29f441ee64e0c38a21965f1ef5f855a0a6b753f97049c5b20d8b77353026d3e0`
- `.ai/manifest.yaml` — `cf66deb83a7c1503ee0b9a26bebe8ffe64a0d4ff8a3690b8040e4c3a1d4ab239`
- `.ai/schema/claim.schema.json` — `3d2da5e68c7fddc313659519bdcbf428e155187fb8700536787abee3e47a219b`
- `.ai/schema/evidence.schema.json` — `7190729b6178480f5ffa3dbb8765982a3679952cba2a1756dd1f46d481bfa68d`
- `.ai/schema/relationship.schema.json` — `8823f8243c107a9c03778c382a78bea33c99fb203333694fc5a14add67433036`
- `.ai/tools/compatibility_adapter.py` — `df3c6b3b9c1a14de111b08342a2d18849607dbca2ea7ea78011e151684f9ec7b`
- `.ai/tools/compatibility_inspector.py` — `5b2062e68ae3e5d7f3f376e070d28fd5c41419ae26e5c00e5481c6ffcad636fc`
- `.ai/tools/context_engine.py` — `f84e8b7c4cf1f9965a74972c1269beef3996e240d8cc3eb8fc9e27e3cc2afac5`
- `.ai/tools/context_eval.py` — `6fe27da106df5d40b6b8708ecf664bec4b960003658e9513537cb4d9374e71aa`
- `.ai/tools/kb.py` — `e14626ef46791df144e290338004bbbfbe8e0ff87c6c97ca97777ee99ad35bcb`
- `.ai/tools/kb_mcp.py` — `26d2ff7e054391c20fdcc66e37e185840a4a385cb1e67459592b9664ec7a3ec2`
- `.ai/tools/knowledge_graph.py` — `61edf32a425a3fa25aa03c68f2c3800eed6dea43d9dbdecfe6e99fe37076a2d3`
- `.ai/tools/population_dotnet.py` — `49ae4789311467ed428bc56b5adf23727d6502a432883a81cb62b28c05780690`
- `.ai/tools/population_normalize.py` — `eef720fcb3b6062edd4e1734f4fe6af36d345752c3de2ad29ca984779c5c35e1`
- `.ai/tools/population_scan.py` — `d5e867f0b3411c262e4abbefb92369c9d1944f3669a8c71436cfcf0ec9800c10`
- `.ai/tools/population_transaction.py` — `4b17a2a7c657b020067bb182b5b9d6a743c8cb0481ca60ab1b79e29d1c07c1f3`
- `.ai/tools/tests/test_context_engine.py` — `ed1f9f16e4fe91c5955313f9fa06c9f4a9315feb1db20b6534dc641f1144e7e5`
- `.ai/tools/tests/test_context_engine_bridge.py` — `cdae37dfd6232fa3f5ea0ad6b8f4d034019630cc6e4a956b90bdeb41fc198282`
- `.ai/tools/tests/test_kb_mcp.py` — `aa117a710c2cfc3a37a7090a84cffd8a8abd77533b56086ebf496fbd0f72f650`
- `.ai/tools/tests/test_population_proposal.py` — `5aebd972cc6661f52cd40356ef26fc92250c9d9207c8ff7ceeb431ab408bb84a`

## Capability map

| Capability | Classification | Delivery/evidence |
|---|---|---|
| Three v1 record schemas | Provided/reused unchanged | knowledge/schemas; hash-pinned semantic regression |
| Schema and graph validator | Provided/refactored | legacy_validator.py; legacy installer/CLI removed; semantic validation reused through staged snapshots |
| Lexical ranking, confidence/status policy, conflicts | Provided/refactored | retrieval.py assemble retained; provenance and actual byte cap added by Store; executable differential reference test |
| Archived MCP | Provided input, adapter replaced | new optional mcp.py delegates to Store/resolver; real client sessions test two roots and conflicts |
| Population transaction workflow | Provided input, storage mechanism replaced | SQLite canonical+queue+plan+journal replaces multi-file staging/ownership rollback; exact approval and immutable binding retained; process crash/ambiguity tests |
| Scanner/.NET analyzer/normalizer | Provided input, audited/not exposed | P1 full/incremental discovery deferred; P0 uses curated source anchors and hashes |
| Compatibility inspector/adapter/graphs/eval | Provided input, not public P0 interfaces | v1 record migration supports observed schema and sealed transaction layout; no claimed private adapter parity |
| Original four test modules | Provided reference | original unmodified baseline failed at missing installer docs; new contract tests and differential ranking checks replace packaging-coupled fixture execution |
| Canonical candidate writer, manual/automatic facades | Newly implemented | Store.submit, submit_manual, submit_automatic; one BEGIN IMMEDIATE protocol, normalized dedup |
| Queue acknowledgment/recovery | Newly implemented | exact payload and canonical-value binding, durable state, idempotence, process-crash tests |
| Project resolver | Newly implemented | explicit root/OS path identity, links/escape/copied-store refusal |
| Standalone CLI/package | Newly implemented packaging | no runtime dependency; fresh dependency-free venv/wheel check |
| Offline migration and backup restore | Newly implemented | synthetic semantic/byte-preservation fixtures; actual legacy journal layout; explicit queue interchange |
| Harness read-only consumer | Newly implemented | no executor or shell capability; missing/busy degradation, corruption error, response bound |
| Original Harness/manual/automatic writer files | Omitted/unverified legacy | intentionally absent; not repaired in place, no compatibility promise |
| Full discovery/lifecycle, agent orchestration, portable release | Future milestones P1/P2/P3 | not implemented or prerequisites for P0 |

## Confirmed input issues and decisions

The supplied installer registry requires absent operational docs, starting with
`docs/contract-v1.md`. The unmodified archived suite reached 49 failed fixtures
and one MCP class setup error at this prerequisite. No fake historical docs or
fixtures were introduced. New package installation uses real shipped package
data and documents its actual behavior, independently of that registry.

The old project-local `.ai/tools` installer copied executable tools into each
store. New reusable packages install separately and `.knowledge` contains only
state. The supplied transaction implementation already validates seals, exact
approval and ownership; those useful contracts informed the new implementation.
SQLite replaces cross-file writes because canonical import, journal and queue
coordination can be tested with real atomic transactions and crash rollback.
The source map does not claim the old mechanism was defective in every case.

The old MCP/context query read `.ai`; the new adapter reads a Store snapshot.
Retained ranking still passes differential source checks. Hard serialized byte
bounding corrects the legacy envelope-budget limitation; claim/evidence
provenance is included in context. Confidence schemas/hashes are not changed.

## Complete delivered call graph

Curated/manual/future automatic capture → candidate-operation v1 →
submit_manual/submit_automatic/CLI submit → Store.submit under BEGIN IMMEDIATE →
immutable durable queue → prepare (shared validator + root/canonical/payload
fingerprint) → exact-fingerprint approved apply → atomic canonical/journal commit
→ separate payload-bound acknowledge (or recover) → validated read snapshot →
retained lexical assembly → bounded CLI/MCP/Harness result with provenance.

Offline migration → verified v1 records + terminal sealed plan/journal assessment
→ semantic/byte manifest → staged SQLite store → atomic directory publication →
same validator/read/writer pipeline. No dual-write `.ai` compatibility path.
