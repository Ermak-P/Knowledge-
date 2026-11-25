# Stage 3 — inventory, incremental synchronization and independent evidence

Native metadata observation drives FETCH_CONTENT / RESUME_ANALYSIS / SKIP.
Analyzed and applied versions are separate; empty analysis is persisted. Same-body
new versions reuse analysis and create validated pending-candidate refresh links,
without reusing old approval. Interrupted candidate submission has a durable
outbox and an explicit resume checkpoint; incomplete batches cannot be applied.
Partial analysis chunks are buffered until one complete page projection is ready.

Exact statements and matching semantic roles share canonical identities across
pages and Git. Evidence enrichment and controlled source-specific proof supersession/removal
can be reconciled across multiple pending native batches. Every original source
is independently validated; meaning/graph-changing concurrent updates require
explicit resolution. Loss of all independent proofs demotes confidence safely. Source classifications and canonical confidence
are preserved. Unverified documentation-only implementation remains INFERRED.
Actual contradictions keep symmetric conflicts and explicit clarification questions.
Different scopes block for clarification. Page changes/deletions affect only
that page's proofs; remaining independent evidence survives. No proof remaining
means NEEDS_HUMAN_CONFIRMATION with historical provenance retained. A timeout,
permission failure, 404 or search omission never confirms deletion.

Schema 1 -> 2 is additive/transactional/idempotent. Content-addressed body storage
removes repeated bodies across versions/pages; native snapshot identities do not
change. Body cache is limited to 8 MiB. Retention runs every 64 new registrations
and explicitly at batch boundaries, preserving active/historical evidence,
pending candidates, plans and unfinished outboxes. Obsolete unreferenced cache
revisions and their compact completed outboxes are removed. Indexed page/version,
related-candidate, outbox and event tables support resume and diagnostics.

Evidence: stage3-focused.log (88 installed focused tests), stage3-cr-regressions.log
(39 existing CR tests), stage3-final-source.log (35 final sync + existing dedup tests,
including 1000-page inventory, bounded body cache, migration rollback, fault after
persisted submission, same-body refresh, source sharing, source-specific deletion,
partial chunks and conflict scopes). stage3-scalability.log records the earlier
15 sync cases. All these final checks pass. Python AST / JSON and diff whitespace
checks pass. Full installed regression evidence is recorded separately below.

Limitations: synthetic MCP metadata/content, no private/live Confluence or native
Windows execution in this stage. The existing core validates its queue and plans
on each transaction; that global cost remains and no unrelated SQLite redesign
was introduced. Ordinary Confluence-only synchronization/retrieval does not scan
Git or make network/model calls. Full installer/OpenCode qualification follows
Stage 4 and binds its logs to the final source and distributable.

Full intermediate installed regression: 511 tests, PASS with 13 Windows-only
skips (stage3-regressions.log). The final native-source refinements were then
checked together with existing dedup and CR cases from the refreshed installed
package: 115 tests PASS (stage3-final-installed.log); no Windows/live Confluence claim is made.
