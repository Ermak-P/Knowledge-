# Audit stages 1–2: independent review R1 correction

R1–R3 are corrected for independent review. Real OpenCode/local-model acceptance
remains a separate phase. No user/IPM database, real Docker resource, merge,
deployment or rollout was used. Normalizer/provider/Docker responses are labelled
doubles; SQLite, CLI/session state, provider HTTP, edits and process checks are real.

Reviewed HEAD: `7eb3c8089ddf4a7f6f1434a95d9e307f8e8e6c9b` / product source
`74b2dee16aaf8fd0dfe25854fae47d8bf8bcf016`. Correction source:
`60bb809fe9e586bcc7ae12a995210c49eefa71b9`. Source identity: `390759b7ea7ffdb1043ad460cb11423bee31f4e2f51130bf4cc5b38b2f9fc413`.
The source map is [source.json](source.json); report-only commits do not change it.
[CI run 45005718682](https://github.com/Ermak-P/Knowledge-/actions/runs/45005718682).

## Findings and resulting behavior

| Review | Correction and evidence |
|---|---|
| R1 / AUD-02 | `startup-en-ru-v2` requires representation of every clause before a new grant. Unknown prose alongside permission blocks authorization; it is not just a longer blacklist. Current denials are independent of the model. Host/CLI/catalog/semantic, wrong schema-valid proposals and historical receipts share the boundary. Readiness, explicit stopped grants and ordinary same-binding clarification remain usable. |
| R2 / AUD-02 | Clearing current no-start requires an unconditional whole message, including intent=none. Both reviewed approval forms and RU conditions retain denial. Replay/restart cannot clear it; a later genuinely unconditional clear works. Durable old clear fields are rechecked against the source, not replayed as authority. |
| R3 / AUD-05, AUD-09 | Automatic delivery, all four roles' Knowledge tools, cached receipts and paired history projected into a new request share `current_knowledge`. P0 text remains withheld with an explicit upgrade/review reason. Fresh P1/dependencies/diagnostics and standalone/task-v1 legacy reading remain. No implicit upgrade occurs. |

The closed grammar and supported clauses are documented in
[AUDIT-STAGES-1-2-R1.md](../../../docs/P4/AUDIT-STAGES-1-2-R1.md).
The current source has no tools/delivery import cycle. Historical receipts/history
and already begun provider requests are not rewritten; cached validation/projection
runs without another lookup or inference. Existing provider/tool caps and pairing,
unknown-outcome refusal, scope/resource checks and independent allowlists remain.
No general natural-language understanding or automatic truth promotion is claimed.

## Before → after, public boundaries

[BASELINE.json](BASELINE.json) verifies the installed reviewed-kit module bytes
against its wheel entries, with archive hash
`80ad248a15c8850616deca4b562b0ff08cf6fae22251c021b27ffba1c47f4cb5`.
[reviewed-kit-failed.log](reviewed-kit-failed.log) runs the new regressions using
that external installed Python: 10 test methods, 30 expected failed assertions/
subtests. The same methods pass after correction: [focused-pass.log](focused-pass.log).
They live in [test_audit_review_r1.py](../../../tests/test_audit_review_r1.py).

The methods cover the three review inputs plus phrases outside the previous
limiter vocabulary, in both teaching profiles through actual host/CLI ingress.
They inspect SQLite and the exact Docker boundary: no new grant/zero starts for
unsafe input, readiness available, supported stopped grant exactly one start.
The denial/conditional-clear sequence uses an existing operator grant, actual
host session, fresh CLI processes and replay; start stays blocked until the later
unconditional clear. The operator grant itself is not erased.

For P4, the provider first observes withholding, then calls the ordinary Knowledge
tool. The following actual HTTP requests for Main/Planning/Coding/Reviewing exclude
the unverified statement and retain explicit partial/unavailable diagnostics.
The original read-only R3 wire case is additionally retained as
[before](optional-tool/before/result.json) → [after](optional-tool/after/result.json),
with both actual provider requests and journal hashes. The same message-only
provider reproduces the leak using the reviewed external kit and excludes the
statement using the corrected external kit. Each run preserves its own SQLite
byte hash and core legacy readability. Reproduce with [probe_optional_tool.py](probe_optional_tool.py)
using installed Python, --output NEW_DIRECTORY and --expected current (or legacy
only for the pinned reviewed runtime). This probe is a protocol double, not a live model.
Fresh P1 retrieval retains revisions and parent IDs. Separate task-v1 HTTP/core
checks preserve legacy reads. Store bytes/history are unchanged by those reads.
Fresh-process recovery cases seed a genuine older weak receipt/history and prove
that a new request is filtered while the stored receipt and first provider request
remain unchanged; the completed tool is not executed twice.

The focused correction initially exposed a valid-template replay regression:
template aliases were not retained by stored template ID. The failing reproducer
[template-replay-before.log](template-replay-before.log) is retained. The final
source fixes matching and uses the current catalog resource count. A dedicated
positive host/CLI replay regression keeps the valid grant and revision intact.
The superseded local qualification is retained as FAILED, with its interruption
explained in [superseded-28a7/NOTE.md](superseded-28a7/NOTE.md); it is not final
qualification. The earlier 342-test development suite is historical evidence in
[interim-342-suite.log](interim-342-suite.log). All final-source checks run afresh.

## Installed qualification

| Profile | Status | PASS / SKIP tests | Commands |
|---|---|---|---|
| Local Linux | PASS_PORTABLE | 332 / 11 | 23 |
| CI Linux | PENDING | — / — | — |
| Native Windows | PENDING | — / — | — |

Final local suite: 343 methods, 332 PASS,
0 FAIL, 0 ERROR, 11 native-only SKIP.
The existing 333 tests are retained, with 10 additional R1 regression methods.
The full installed route includes automatic .NET/actual TRX, prior kit upgrades,
maintenance/recovery, transferred first use, application checks, doctor and
uninstall/reinstall. [local/run.json](local/run.json) and [local/tests.json](local/tests.json)
retain every command and its log hash. [ci/validation.json](ci/validation.json)
checks exact source maps, all retained log hashes and every kit file against the
local artifact; artifact content is read as data, not executed by the collector.

[standalone/result.json](standalone/result.json) checks the corrected Knowledge
profile without Harness/MCP against the existing reviewed nonempty store: revision 2,
two receipts, history, pending queue and PREPARED plan are preserved with identical
SQLite byte hash. Native core/upgrade/independence coverage and this additional
Linux-only standalone byte probe are distinguished in [ACCEPTANCE.json](ACCEPTANCE.json).
That file updates all 24 original matrix rows and separately maps R1/R2/R3 to tests.

The [installed delivery trial](installed-trial/result.json) still obtains threshold
37 from approved Knowledge without a Knowledge tool call, changes real code and
passes actual checks plus an independent oracle. Disabled delivery leaves 0 and
fails as the expected negative control. Final Reviewer uses canonical knowledge
independently of Coding's false narrative. This is mechanical delivery evidence,
not live-model quality. Existing [host-validation.json](../host-validation.json)
remains BLOCKED because a compatible real OpenCode executable was unavailable.

## Delivery, reproduction and recovery

Product version remains 0.5.0rc1; select the exact hashes, not the version alone.
[Current kit](distribution/knowledge-harness-0.5.0rc1.zip) SHA-256:
`cc0e852040ffb9e8f70b8e698c49dab5b3ed0d89bda55e6f059f97d2c49239e1`.
Knowledge wheel: `1d34f127c09d0b59e756b2401b90825a1084b814f383a9771a5f804992a396a7`.
Harness wheel: `887b8189593ac680d770af89b3e2ced9e230b8bed43d55f870ca4b3ce184f994`.
[RELEASE.json](distribution/RELEASE.json) and [package.json](distribution/package.json)
contain the actual content map and validated installed-delivery provenance.

```text
python scripts/setup_p3.py
.venv/bin/python -B -m unittest discover -s tests -p test_audit_review_r1.py -v
.venv/bin/python -B -m unittest discover -s tests -v
.venv/bin/python -B scripts/verify_p4.py
# Native Windows / PowerShell 5.1:
powershell -NoProfile -File scripts/verify-p4-windows.ps1
```

To repeat the adversarial cases with an external kit, install it outside checkout
and run its Python with `-I -B -m unittest discover -s ABSOLUTE_REPO/tests -p
test_audit_review_r1.py -v`. Products import from the selected installed Python;
fixtures import from the repository tests. No Docker daemon or real resource is used.
Use an installed runtime for `scripts/audit_stages12_trial.py --output NEW_DIRECTORY`.

No new database, service or permission expansion is introduced. Existing transfer,
degraded-session/operator-resolution and rollout/rollback contracts remain in
[AUDIT-STAGES-1-2.md](../../../docs/P4/AUDIT-STAGES-1-2.md).
Before any later rollout, fence pending effects and keep matching project/shared/
Harness backups; use the matching old kit/backup for rollback. Do not resume new
pending state with incompatible old code or repeat unknown process outcomes.
The prior 74b2 evidence remains historical; this packet supersedes its completion
claim in light of independent R1 and the corrected source above.
