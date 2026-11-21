# Persistent Instructions R2: Preserve Startup Denials During Parsing

## Scope and reviewed baseline

Fix one remaining startup-authorization defect found during independent review of R1. Implement the fix and regressions in the supplied checkout. Preserve the working R1 resume controls; do not reopen the whole persistent-memory architecture.

Repository: https://github.com/Ermak-P/Knowledge-

Branch: `codex/persistent-instructions`.

Reviewed HEAD: `a193463313e2965fac38ed854dded5b2230b3027`.

R1 product-source commit: `287a6a8aa976b40a0117684a213ee46310df27bc`.

Inspect current HEAD, applicable AGENTS.md, and intervening changes without resetting or overwriting other work. Work in place, without worktrees. Keep Knowledge standalone, shared memory at `~/.local/share/knowledge`, project memory in `.knowledge`, current permissions, and existing lifecycle/history. No unrelated refactor, merge, release publication, or improvement-register edit.

Reference documents:

- `tasks/Knowledge-Harness-Persistent-Instructions-R1-Fixes-Codex-Task.md`
- `reports/PersistentInstructions/R1-287a6a8a/REVIEW.md`
- `docs/P4/PERSISTENT-INSTRUCTIONS.md`
- `docs/P4/PERSISTENT-INSTRUCTIONS-LIVE-HOST.md`

## Finding: explicit denial is discarded by teaching-prefix removal

In `packages/knowledge/src/knowledge/startup_authorization.py`, `clauses()` removes the prefix matched by:

```python
r'^(?:remember|запомни)(?:\s+[^:]{0,180})?:\s*'
```

The optional arbitrary text includes actual user conditions and prohibitions. Both `startup()` and `restriction()` scan the resulting clauses, so they can no longer see a denial that was removed before the colon.

Source: https://github.com/Ermak-P/Knowledge-/blob/a193463313e2965fac38ed854dded5b2230b3027/packages/knowledge/src/knowledge/startup_authorization.py#L11-L18

Independent reproduction at the reviewed source:

| Trusted user input | Permission quote proposed by the model double | Observed result |
|---|---|---|
| `Remember you may not start the container: You may start it.` | `You may start it.` | Parsed clauses contain only the affirmative clause; `granted=True`, `denied=False`. |
| `Запомни не запускай контейнер: Разрешаю запуск этого контейнера.` | `Разрешаю запуск этого контейнера.` | Same loss of the explicit denial and affirmative grant. |

These inputs are deliberately contradictory. Under the declared R1 deny-wins contract, contradictory source must not produce an executable startup grant merely because one part was erased. No claim is made that ordinary users write these phrases frequently or that a real model necessarily misclassifies them.

The English case was also reproduced through actual host ingress and SQLite storage, with an intentionally incorrect but schema-valid local normalizer response and the existing `DockerContract` double:

```json
{
  "saved_recovery_authorized": true,
  "contract_start_calls": 1,
  "real_docker_effects": false
}
```

No real Docker container was started. This is a parser/authorization regression, not a real-host acceptance result.

## Required correction

1. Preserve authorization-relevant source text. A denial must not disappear because of normalization or removal of a teaching wrapper.
2. Check denials against a lossless representation, or restrict removable wrappers to a validated harmless grammar. Do not remove arbitrary prose between a teaching keyword and a colon. Apply the same invariant to startup-grant validation and current-restriction handling.
3. Retain the deny-wins rule for contradictory startup instructions. Do not silently adopt the final affirmative clause or rely on the model to recover discarded content.
4. Keep the action distinction: `start if stopped; never restart a running container` remains a valid startup grant with restart prohibited. Do not reject all negation indiscriminately.
5. Preserve supported ordinary teaching and scoped wrappers such as `Remember Kafka: ...`, `Запомни Kafka: ...`, and the documented shared-teaching examples where their meaning can be represented. If a wrapper is unknown, preserve the source and fail safely rather than deleting conditions.
6. Keep resource binding, current policy allowlists, current no-start controls, durable receipts, and the original user instruction intact. Do not add a confirmation requirement to every teaching message.
7. Document the bounded recognition contract accurately. This task does not require a perfect natural-language parser or new inference services. A model-only prompt change is not a fix for the deterministic loss of source text.

## Tests and acceptance

Add focused regressions that fail on the reviewed revision, then implement the fix.

- **Direct parsing/authorization:** both EN/RU examples above cannot issue a startup grant. The prohibition remains observable by the restriction/denial checks.
- **Real ingress and durable state:** use an intentionally wrong schema-valid normalizer response, actual ingress, and an actual temporary SQLite store. The effective saved instruction must not authorize startup; its original source remains intact.
- **Effect boundary:** the existing command/broker contract records zero startup calls for these cases. State explicitly that Docker/model doubles are used.
- **Current controls:** a current startup prohibition in such a prefix cannot be cleared by a conflicting affirmative proposal.
- **Positive controls:** ordinary EN/RU positive permission for the correct stopped container still works; `never restart` does not become a startup denial; original-name/resource checks remain effective.
- **Regression:** run the full `test_persistent*.py` suite, including the 12 R1 tests. Preserve additive no-start on resume, persisted restrictions, and deterministic byte-intent recovery.

Use temporary roots and existing isolated fixtures. Do not mutate the user's real shared memory or services for automated testing.

Report commands, source SHA, counts, failures/skips, and before/after results. Run the relevant installed/native CI route for changed product source where available; an earlier successful R1 CI does not qualify new changes. Mark unavailable platform checks explicitly.

## Existing host-validation boundary

The R1 report still states `IMPLEMENTED / HOST VALIDATION PENDING`: real OpenCode/local-model A01/A02/A05/A17 were not run because the host/model was absent. Keep this boundary explicit.

If the actual host is available, execute the existing isolated live guide after fixing this defect: teach once, terminate that session, request ordinary tests in a fresh session without a Kafka/memory reminder, verify the remembered revision and permitted recovery, and run the applicable negatives. Otherwise complete the code fix and tests and give the exact prerequisite/command for the user's host. Do not represent a Docker contract or protocol double as successful live validation.

## Deliverables and verdict

Deliver:

1. The narrow source fix and regression tests, with a commit/diff reference.
2. Updated acceptance evidence that preserves earlier review failures and distinguishes real processes/storage from doubles.
3. A short Russian report separating `R2 parser fix` from `real-host validation`, including supported execution paths and remaining limitations.

Completion requires zero startup effects for the EN/RU conflicting-prefix regressions and passing applicable regressions. Full feature acceptance still requires the independent real-host evidence from the parent assignment. Do not weaken guards or mark unrun host checks PASS.
