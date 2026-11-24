# Audit stages 1–2: review R1 corrections

This focused correction addresses the three reproducible review findings against
7eb3c8089 / product source 74b2dee16. It keeps the existing SQLite/journal formats,
CLI signatures, independent allowlists, role authority and execution receipts.
Current evidence and source/package hashes are under `reports/AuditStages12/R1/`.
The previous packet remains historical, not current acceptance.

## R1: a closed authorization message

`startup-en-ru-v2` validates the whole current trusted source before a new startup
grant. Every clause must be representable. The independent check does not trust a
model's positive quote, even when its schema is valid. Explicit startup denials win
before any teaching-header interpretation, including the reviewed English adverb
and Russian prohibition. Other unsupported clauses are not erased by normalization.

The positive EN/RU grant grammar and exact selected container/deictic-resource
checks remain. Bounded topic/shared-scope wrappers remain supported. Grant messages
may also contain only these already supported statements:

- `Only if stopped` / `только если он остановлен` (including the existing variants);
- `never restart a running container/service` / its supported Russian equivalent;
- `check readiness`, optionally `before required [integration] tests`;
- explicit `Remember <literal catalog alias> container <selected name> and port
  <1..65535>` resource teaching data used by the existing binding path.

These are data/guards the existing execution contract can represent; they cannot
add a command or allowlist entry. Other prose in a message attempting authorization
blocks a new grant, even when it uses no keyword from the earlier limiter list.
For example, a positive sentence followed by `Management signoff precedes
launching` or `An exception applies on maintenance days` cannot authorize startup.
This is a narrow grammar, not a claim of arbitrary natural-language understanding.

Ordinary same-resource clarification without a new authorization change can retain
its previous grant. Unsupported authorization-related/limiting prose cannot retain
an inherited executable grant by disappearing. Resource/binding changes still need
their existing exact checks and a new valid permission. Readiness remains usable;
an unconditional supported stopped-resource grant still starts once, never restarts.

Authentic historical source replay uses this same current boundary without model
inference. A weaker historical natural-language grant may receive a revocation
revision while retaining its original record ID, wording, provenance and history.
The host's resolved-envelope shortcut also revalidates such durable receipts.
Replay retains template aliases by stored template ID as well as concrete binding
identity; a valid stopped-template grant survives host/CLI replay. The current
catalog supplies the independent resource count.
No bulk migration or background reinterpretation of operator stores occurs.

## R2: clearing current denial is an authorization change

The same whole-source scrutiny applies when a normalizer proposes `clear-denial`,
including `intent=none`. This path accepts only complete unconditional CLEAR
clauses (and the already supported bounded headers). It has no mechanism for
approvals, tickets or conditional session-wide clearance. Consequently a clear
sentence plus any unsupported condition leaves the current restriction unchanged.
A known denial still returns `deny` regardless of the model proposal.

A retry/restart of the same source cannot clear a newer restriction or apply old
controls. A later genuinely unconditional clear remains supported. A durable
historical receipt's saved clear control is rechecked from its authentic source
before replay; the old control field alone is insufficient. Existing format
controls and source hashes/order remain authoritative. Existing operator grants
are preserved while the stronger current no-start blocks startup.

## R3: one current-fact view for all P4 paths

`harness.tools.current_knowledge` is the shared P4-facing validation used by:

- automatic delivery;
- ordinary Knowledge tool results for Main, Coding, Planning and Reviewing;
- cached finished Knowledge tool receipts;
- paired historical Knowledge tool messages projected into a new provider request.

A P0 confidence flag with no lifecycle revision/current freshness proof is withheld
with `available=false`, `partial=true`, `knowledge-lifecycle-upgrade-required` and
an upgrade/review next step. No withheld statement is returned through the ordinary
P4 Knowledge tool. A separate implicit historical-view permission is not created.

The history projection uses each assistant turn's actual tool names and call IDs;
IDs may repeat between turns. Stored receipts/history and previously begun
provider requests are not rewritten. A cached tool result is validated without
repeating retrieval or effects. Existing unknown-inflight refusal and saved-response
recovery remain. Whole provider-body byte caps still apply after projection.
The helper dependency points tools -> core Knowledge and delivery -> tools; there
is no tools/delivery cycle or new inference component.

Fresh P1 facts retain revisions, dependencies, evidence, diagnostics and budgets.
Standalone Knowledge and task-v1 retain their supported legacy read contracts.
Reading an old store does not upgrade it or rewrite its history.

## Verification and operational boundary

`tests/test_audit_review_r1.py` uses actual installed CLI/SQLite/session state,
HTTP-provider requests, fresh-process resume and explicit normalizer/Docker doubles.
It covers both original review cases and clauses outside the old vocabulary,
conditional and unconditional clear, historical replay, all four P4 roles,
cached receipts/history, fresh P1 and task-v1 compatibility. No real Docker resource
or user/IPM store is used. The full installed portable/native qualification remains
`scripts/verify_p4.py` / `scripts/verify-p4-windows.ps1`.

The previous real-host boundary remains: controlled providers prove delivery and
broker behavior, not live-model quality or enforcement of arbitrary host shell/edit.
No merge, deployment or user rollout is part of this correction. Use the matching
store/journal backups and current kit hashes for rollout/rollback as documented in
[AUDIT-STAGES-1-2.md](AUDIT-STAGES-1-2.md).
