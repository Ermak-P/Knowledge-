# SQLite identity migration delivery

Implementation and static review only. Automated tests and Windows execution:
**NOT_RUN**, as explicitly required. Actual IPM inventory/migration: **NOT_RUN**
by Codex; delegated to the local agent and separately exact-approved cutover.

* [Implementation review and future regression cases](STATIC-REVIEW.md)
* [English/Russian local runbook](../../docs/P4/SQLITE-IDENTITY-MIGRATION.md)
* [Changed files](changed-files.json), [static checks](static.json), [packaged assets](assets.json)
* Ready kit: distribution/knowledge-harness-0.5.0rc1.zip and adjacent SHA256.

Canonical records/revisions remain active with exact IDs/payloads/lifecycle.
Every original row, including all queue dispositions and plan/receipt bindings,
is also readable through supported identity-history. Historical candidates,
operational memory and old sessions/grants are not live execution authority in
the new root. This explicit preservation/quarantine rule must be reviewed in
local preview. No private database/source/log was uploaded into this packet.

The observed 1394 records / 697 queue items / 1 plan are incident inputs, not a
Codex-confirmed inventory and not 1394 claims. The implementation does not force
these counts. Backup, staged/source equality and integrity/product validation
are mandatory runtime gates, not checks claimed to have run here. CI tests are
skipped for this delivery to honor the no-tests instruction.
