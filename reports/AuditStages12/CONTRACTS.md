# Working contracts — audit stages 1–2

Baseline/current start: `152e372eafac74c39236a3f6b0e55808769d910e`, clean tree,
product 0.5.0rc1. In-place branch `codex/audit-stages-1-2`; no AGENTS.md found.
Linux ordinary identity uid=1000. Changes are limited to the seven assigned AUD IDs.

1. Coverage: enumeration/read/disappearance gaps are snapshot-bound. Unknown
   directory scope conservatively blocks negative proof for all project partitions.
   Discovery may retain partial observations; execution/maintenance source identity
   fails explicitly rather than hashing an incomplete tree as complete.
2. Grants: all natural-language paths share the same full-source authorization
   decision. Contradictions/unknown guards issue no grant; operator structured
   writes remain a separate trusted local API. Existing permission may survive
   ordinary clarification only for the same resource/binding. No daemon startup.
3. Transfer: durable intent in existing project SQLite metadata, deterministic
   source/target IDs and CAS revisions; phases prepared -> target-saved ->
   source-retired -> completed. Gate order: project then shared, then each SQLite
   transaction; bounded nonblocking contention/retry. Pending affects the relevant
   action, not unrelated memory. Recovery/replay never needs a new model call.
4. Degraded session: bounded source-ID/hash/sequence envelope in existing session
   state; expected model outage permits chat/read-only work, preserves controls,
   issues no grant and blocks uncertain recipe/patch effects until trusted recovery.
   Late results cannot overwrite newer controls; integrity errors remain errors.
   Sensitive payload is never saved raw.
5. P4 delivery: deterministic goal/item/role/scope query, bounded current claims,
   durable slice identity and source/store/config binding. Reuse until a relevant
   delivery boundary/invalidation; no extractor/LLM per tool round. Persist enough
   to check exact provider input after resume; do not rewrite inflight requests.
6. Retrieval: compact dependency IDs and bounded closure; all returned records
   count toward limits. Bounded query-related filtered diagnostics never place
   stale/unconfirmed text in trusted claims. Actual UTF-8 CLI/MCP response and the
   full provider body obey hard caps; source authority and task criteria win space.

These are implementation contracts, not a claim of completed tests or live-host
acceptance. Stage 1 is verified before continuing stage 2. The final report and
ACCEPTANCE.json will distinguish installed/native/double/real-host evidence.
