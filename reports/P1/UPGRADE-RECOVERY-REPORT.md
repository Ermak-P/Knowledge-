# Nonempty P0 upgrade and transaction recovery

Run `fe11fd6fd62e4372b5d6e830889775be`; source `f6fbbd3dc18cfe085c3694bd6ab529f23e5eb7ac7b0c54bb450083bb33069954`. Raw evidence: `runs/fe11fd6fd62e4372b5d6e830889775be/`.

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
