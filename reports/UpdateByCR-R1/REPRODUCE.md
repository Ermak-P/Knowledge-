# Reproduce R1

Use implementation revision `b57f5e8c26992c5bd95cf8d22b46f1a9f485187d`,
Python 3.12, Git, Node and the existing .NET SDKs from the normal qualification.

```text
python scripts/setup_p3.py
.venv/bin/python -B -m unittest discover -s tests -p 'test_update*cr*.py' -v
.venv/bin/python -B scripts/verify_p4.py
powershell -NoProfile -File scripts/verify-p4-windows.ps1
```

The existing official route runs the full regression suite against transferred,
installed packages, lifecycle/upgrade/recovery, .NET behavior, uninstall/reinstall
and Knowledge-only checks. The R1 methods are part of full test discovery.
Do not reinstall an environment while its tests are running.

The delivered [ZIP](distribution/knowledge-harness-0.5.0rc1.zip) has SHA-256
`7cb633e1823e36e3436dd43a19529ca36002717a922850d4e657ba4fbd121090`.
`distribution/RELEASE.json` seals every asset. Rebuild and install outside checkout:

```text
.venv/bin/python scripts/build_p4.py --output /tmp/ucr-r1-kit --source-id 4ce84bd346cad8fa0bd3177617c7b718984372524556b37360ebf3fddb34a0b0
python /tmp/ucr-r1-kit/knowledge-harness-0.5.0rc1/install.py install --env /tmp/ucr-r1-independent --profile knowledge
/tmp/ucr-r1-independent/bin/python -I -B /absolute/repo/reports/UpdateByCR-R1/fixed_probes.py --output /tmp/ucr-r1-probes
```

Use `Scripts/python.exe` on Windows and `-X utf8` for the report driver. That
driver runs the behavioral R1 tests against the installed Knowledge package and
captures actual Store exports, canonical receipts, normal context and queue state.
Only test drivers/fixtures are loaded from checkout; product imports must resolve
inside the isolated environment. Harness and MCP must be absent.

The supplied independent audit archive remains unchanged. Its original probes
assert the old bugs, so they are not corrected-product PASS tests. Refer to its
own reproduction instructions for the reviewed pre-fix revision. `audit-input.json`
records archive/member verification; no downloaded archive program is executed.

CI results are retrieved as data without executing artifact code:

```text
git fetch origin p4-ci-evidence
python reports/UpdateByCR-R1/collect_ci.py --commit b57f5e8c26992c5bd95cf8d22b46f1a9f485187d --source reports/UpdateByCR-R1/source.json --distribution reports/UpdateByCR-R1/distribution --output reports/UpdateByCR-R1/ci
python reports/UpdateByCR-R1/verify_packet.py
```

The collector checks the requested commit, every source hash, each command log
and every package asset. An empty platform map is pending evidence, not PASS.
`ARTIFACTS.json` and `verify_packet.py` verify the complete retained packet.
