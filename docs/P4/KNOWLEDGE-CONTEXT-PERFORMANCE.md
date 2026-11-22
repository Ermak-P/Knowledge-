# Knowledge context performance on large repositories

A Knowledge context request on a large native Windows checkout timed out while
validating source paths. The captured stack was
Store.context -> lifecycle.active -> analysis_scope -> inventory -> safe_path
-> linked -> pathlib.lstat/stat. A separate SQLite quick check completed
immediately; this correction addresses source-analysis overhead, not database
repair or a schema migration.

## Changes

- Inspect each path component with one fresh lstat. Use that result to check
  symbolic links, Windows reparse attributes and the target's type/link count.
  Every ancestor is still checked on each call. No persistent path-trust cache,
  new path exclusion or antivirus exemption is introduced.
- Resolve source-file partitions by nearest project directory instead of
  comparing every file against every project. Nested projects, same-directory
  ambiguity, deterministic ordering and inventory identity retain their rules.
- Run complete ambiguity-sensitive analysis only when an active claim references
  evidence from a discovery extractor. Reviewed/migrated evidence still has its
  own source contents checked. Discovery evidence still requires complete scope;
  newly introduced duplicate declarations remain untrusted.
- Keep SQLite formats, lifecycle transitions, graph checks and writer authority
  unchanged. No reinitialization, migration or candidate approval is required.

The shared Knowledge package also supplies Harness retrieval. Rebuilding the
repository distributions carries the correction into both consumers; previously
installed copies are not rewritten automatically.

## Regression coverage

tests/test_context_path_performance.py adds ten cases covering per-call metadata
work, missing targets below links, broken links, hardlinks and special objects,
fresh detection after a path becomes a link, Windows reparse attributes,
unchanged project partitioning, reviewed/empty/retired-only retrieval and
complete discovery analysis after a new ambiguity appears.

Local Python 3.12 regression execution:
- 249 tests: 238 passed, 11 existing native-Windows-only checks skipped.
- No failures or errors.
- Separate portable CLI/MCP and rename/reinstall checks: 5 passed, including
  unchanged project database bytes, preserved old installation and stable MCP
  command after upgrade.

These local results do not qualify native Windows. The repository's normal
installed Linux/Windows CI must validate the GitHub revision.

## Local before/after measurements

A synthetic local Linux tree contained 180 projects and 5,400 generated C# files.
Two runs per variant alternated before/after against the same project root and
canonical database. The reviewed case had 199 evidence-backed claims; the
discovered case used a small discovered dataset before adding the larger tree.
The request returned up to eight items within a 16,000-byte budget.

| Dataset | Before median | After median |
| --- | ---: | ---: |
| Reviewed claims | 24.725 s | 0.167 s |
| Discovery-backed claims, full analysis retained | 24.591 s | 0.916 s |

Both variants returned exactly equal context JSON, including source identity.
The canonical database bytes were unchanged. Raw samples are retained in
reports/KnowledgeContextPerformance/local/benchmark.json. The baseline used the
previous standalone 0.4.0rc4 implementation; the three affected core files matched
the pre-correction repository implementation.

These are synthetic Linux measurements, not Windows/IPM latency claims. Request
time on the actual affected checkout remains to be measured after updating.


Current audit-stage contracts: [AUDIT-STAGES-1-2.md](AUDIT-STAGES-1-2.md) covers source gaps, transfer/degraded recovery, bounded graph diagnostics and automatic P4 delivery.
