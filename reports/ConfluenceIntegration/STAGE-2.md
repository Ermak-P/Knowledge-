# Stage 2 — native source binding

Implemented stable instance/page identity, native version/revision binding,
immutable normalized snapshots, independent hash/checksum/quote verification,
additive transactional schema creation, native evidence, offline retrieval,
integrity/export, and existing submit/prepare/apply integration. Confluence-only
plans avoid Git inventory; unrelated Git work survives page registration/change.
Stale page candidates retain their queue entries and actionable diagnostics.

The explicit SQLite identity migration recognizes only the exact trusted
Confluence table/index definitions and preserves source caches needed by canonical
evidence. Existing old-root queue/plan authority still becomes historical, per
that migration's established policy; no old approvals are revived.

`knowledge_confluence` is a new source-data MCP tool. It does not fetch Confluence,
store credentials or attest live access. The development tool catalog contains
no Confluence MCP server. Tests use synthetic `example.invalid` documentation.
Incremental synchronization and the OpenCode command are subsequent stages.

Verification: 14 native-source tests plus 27 existing core tests pass from the
installed package (41 total), including actual stdio MCP submission/apply,
Git-change independence, stale native versions, metadata/body corruption, schema
rollback and explicit identity migration. The first full installed regression
run executed 497 tests: only the old single-schema-hash assertion failed because
the evidence schema was intentionally extended. That test now pins the new schema
and reconstructs/verifies the exact original schema by removing only the native
alternative. Confidence validation is unchanged. All other tests passed, with
13 native Windows-only skips on Linux. The final combined suite will run again
after the remaining stages. Native Windows/live Confluence are not asserted here.

Python AST/schema parsing and `git diff --check` pass. Protocol and normalization:
`docs/P4/CONFLUENCE.md`. Task: `tasks/Knowledge-Native-Confluence-Integration.md`.
