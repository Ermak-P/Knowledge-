# Nonempty P0 upgrade and transaction recovery

Run `776dcec359fe4b60abe9556eeb06722e`; source `7d604fc63ec0e5b28f9b55a6ed2d475bc9514d614d84a9af24760c9bf5c17e4b`. Raw evidence: `runs/776dcec359fe4b60abe9556eeb06722e/`.

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
