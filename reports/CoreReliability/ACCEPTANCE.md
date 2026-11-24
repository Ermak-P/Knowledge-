# Acceptance and local deployment handoff

Implementation: 9eef0842478bcdcd7d719678d66a27259d7bcda8, branch codex/core-reliability-fix.
Final source identity: e3fdcb2dbbff5bdd241ade24a214a35548372716d980cde359e465c5f327ddfd.

| Area | Verdict | Evidence / scope |
|---|---|---|
| Core implementation | GO for local deployment validation | Implemented, installed regressions and actual native machine route verified |
| Automated regressions | PASS | Installed product: Windows 450/450; Linux 437 passed + 13 native-only skips |
| Windows runtime | PASS | Actual native bootstrap/stdio/lifecycle and worker tests; not owner installation |
| OpenCode integration | PASS | Actual official 2.4.0 execute/search/MCP and host permissions with controlled provider |
| Installer upgrade | PASS | Actual archived-generation upgrade and preservation; final native fixture rerun passed |
| Production IPM | DELEGATED | No owner installation/provider/IPM changes; separate local validation required |

These verdicts are deliberately separate. Unit PASS does not turn a failed full
CI route into PASS. local-full/run.json records all 28 installed qualification
commands PASS_PORTABLE with unchanged inputs; local-machine/run.json records all
seven installed machine checks PASS_PORTABLE. Windows ci/f8-full/tests.json
records 450 passes without skips, while that full CI route failed later in the
archived installer fixture. The fixture invocation was corrected in 9eef0842.
The f8 Linux CI full route's audit-stage assertion also failed; its source-bound
trace remains retained rather than being relabelled a passing route.

product-equivalence.json proves that every delivered release asset hash equals
the tested f8 product. The last change affects only the upgrade test invocation,
not the installed source/helper/plugin/templates/docs. Source-bound final CI
receipts, when present under ci/final-machine, take precedence for that route.
No mock Windows execution or live-model semantic quality is claimed.

Review [findings](FINDINGS.md), [raw performance comparison](PERFORMANCE.md),
[changed-file inventory](changed-files.json), and [local handoff](../../docs/P4/Knowledge-IPM-Integration-Validation.md).
Full raw measurements, failed investigation attempts, CI logs/manifests and the
ready kit are included. ARTIFACT-SHA256.json hashes retained files.

Repeat installation from the new source or extracted verified kit:

```powershell
.\install.ps1 -McpDir 'C:\LLM\mcp\knowledge'
```

No manual TEMP/TMP edits, McpDir deletion or site-packages patch is needed. Back
up and obtain local deployment authorization according to the handoff. Restart
OpenCode after upgrade. Physical completion remains semantic PARTIAL; review
source-bound candidates and obtain separate exact approval before applying.

Final exact-source machine CI: Windows PASS_NATIVE and Linux PASS_PORTABLE, seven checks each, including 49 installed machine tests, actual archived-generation upgrade, Code Mode search/calls and permission enforcement. Evidence: ci/final-machine/validation.json; Actions https://github.com/Ermak-P/Knowledge-/actions/runs/45394901309. The final full CI workflow may still be running; this report does not claim that entire final workflow passed. Full installed local qualification passed on the identical delivered product, with 450 unit tests; native Windows independently passed all 450 product regressions at f8.
