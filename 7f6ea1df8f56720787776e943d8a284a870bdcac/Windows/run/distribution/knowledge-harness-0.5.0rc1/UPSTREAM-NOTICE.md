# Knowledge framework source input

`ai-source.zip` contains only the framework source from `AL/IPM/.ai` in the user-provided `AL.zip`.
It is the legacy implementation input for the standalone Knowledge project.

Included: Python tools, existing tests, JSON schemas, manifest, deployment metadata and README.
Excluded: all machine/OpenCode/MSSQL configurations, Harness files, transaction journals/plans, project claims/evidence/sources, generated output and caches.
Empty data/scaffold directories are retained. The original source bytes are unchanged.

SHA-256: `734aa3f4b5231d96f82638c634d41eec445d61ae1eb47c91d076af9a13a81ee4`

See `ai-source-manifest.json` for the exact file list and checksums.

## Completeness

This is source input, not a complete or accepted release. Operational docs are absent
from the original snapshot, and the source installer expects them. The project-specific
canonical knowledge and candidate queue were not supplied. The P0 implementation must
repair packaging and use synthetic data for legacy migration/recovery verification.

This narrow package does not contain the separate Harness implementation from the original AL archive.
