# Nonempty P0 upgrade and transaction recovery

Run `7c567e88b6b54922bcc21a8ae3a6ae3f`; source `e20dbd2635d808ce19366d90a0bb96b56ffbd730e5ed14b14e2fa1cfe8d3e96e`. Raw evidence: `runs/7c567e88b6b54922bcc21a8ae3a6ae3f/`.

upgrade.json records a nonempty accepted-format fixture with canonical data,
a committed but unacknowledged transaction and a second pending candidate.
All P0 export fields compare equal before/after schema extension. The backup is
a consistent SQLite snapshot, bound to the preview including metadata/plans,
and cannot silently substitute another database. Existing migration/queue IDs
and imported bindings are separately exercised by UpgradeLegacyTests.

Actual subprocess interruption before upgrade commit leaves P0 fully usable;
repeat upgrade succeeds. Unknown versions refuse. Prepared P0 approvals survive
metadata-only upgrade; wrong/stale approvals refuse. Interrupted mixed updates
roll back, committed batches recover acknowledgment, and old acknowledged
receipts remain safe after later updates. Competing P1 processes never produce
partial revisions. No record deletion or reset is used for recovery.

To restore an upgrade backup, stop all participating processes, preserve the
current .knowledge directory with its journals separately, restore the retained
backup SQLite file at the same project's store.sqlite3, validate with P0/P1
software, then preview a fresh upgrade. Do not move a store to another root,
delete hot journals, or overwrite unrelated edits. See the contract for bounds.
