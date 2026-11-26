# First collection must preserve independent standalone Git plans

The additional standalone-core -> first-MCP experiment found a real side effect:
creating .harness-writer.lock changed the inventory exclusion list, so an already
prepared unrelated Git plan became stale although no application source changed.
This originated in using an execution lease for new source-cache collection.

Confluence collection now freezes the complete source/outbox/queue action with
the existing exclusive SQLite coordination gate. Knowledge-only enrollment writes
its existing project registration under that gate without creating an execution
artifact or transitioning a Harness runner. Canonical machine prepare/apply keeps
its existing execution lease and every source/approval/filesystem validation.
No lock file is unlinked and no symlink, junction or ownership check is relaxed.

Two installed regressions cover first MCP snapshot registration/version advance
and first command enrollment after a standalone Git plan has already been
prepared. Both assert no root execution artifact, no lost Git facts and successful
application of the original approved plan. Raw pre-fix experiment:
core-plan-before-machine-enrollment.log; final tests: collection-gate-installed.log.
The final qualification must use the new source commit; earlier interrupted local
routes are retained as intermediate evidence, never as final PASS.
