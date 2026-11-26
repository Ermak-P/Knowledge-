# Final review refinement: keep original provider binding

Confluence same-body refresh now copies and verifies the original optional
semantic provider binding. A changed provider file/model still blocks the new
candidate with semantic-provider-drift-reanalysis-required. Source version
refresh is not renewed provider authority. A new regression test exercises the
complete same-body refresh and provider drift refusal through installed APIs.

The test also exposed a no-op extraction against an identical pending factory
claim: no duplicate claim-only operation should be emitted when its proof is
already pending. This now remains a duplicate observation with zero operations,
without changing the original candidate or provider metadata.

The first final local qualification began at f37578c7; its immutable inputs were
superseded during this review, so it cannot certify the refined final source.
Keep its ledger as intermediate evidence and use only a later exact-source run
for final qualification. Previous Windows reliability failures remain separately
retained under ci/stage3-machine; no filesystem validation was weakened.
