# Compatibility and recovery

Product: 0.4.0rc2. Runner configuration: v1 unchanged. Task v1: legacy mandatory five-role policy. Task v2: bounded-v1 policy. P3 run state remains v1; P4 run state is v2 with p4 extension v1. Unknown versions refuse. SQLite container and Knowledge schemas remain unchanged. No silent conversion or canonical approval.

P3 binaries reject P4 run state v2. For rollback, stop all runtime/MCP processes, restore the pre-P4 maintenance backup in the same root, uninstall the P4 owned distributions, preserve the P4 installation marker outside the environment, then use the checksum-verified accepted P3 installer with --adopt. No project source/user bytes are removed. Do not resume P4 pending work under P3. Restart installed processes after replacement. scripts/p4_lifecycle.py executes this sequence against the pinned accepted P3 archive, nonempty canonical state, pending requests and capture outbox.

Maintenance snapshots already include runs.sqlite3, actions, outbox and owned artifacts; checkpoints and repair counters live in this database. There is no new external authoritative store. Corruption or conflicting source edits require recovery/restore, never deleting journals. A dead provider intent remains uncertain; no epoch or item renaming authorizes a repeated call. Process recovery uses the original platform ownership receipts and rerun-safe declarations.

Native Windows/NTFS/PowerShell 5.1 is a separate qualification. Linux results do not establish native Windows behavior. OpenCode v2 enrollment remains exact task/config/runtime bound. A live host/model integration is not established by fixture tests.
