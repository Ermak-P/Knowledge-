# Reproduce the delivered bytes

Use Python 3.12, Node for host-contract tests, Git and the existing .NET 10 SDK.
For native Windows use Windows PowerShell 5.1 and the existing qualification route;
WSL does not establish the Windows profile.

```text
git checkout 1a4999fa62a0d78a9d331d4f6f9396a0bef73995
python scripts/setup_p3.py
.venv/bin/python -B -m unittest discover -s tests -p 'test_update*cr*.py' -v
.venv/bin/python -B scripts/verify_p4.py
powershell -NoProfile -File scripts/verify-p4-windows.ps1
```

The normal qualification builds/transfers the kit, installs outside the checkout,
runs the full regressions and existing lifecycle/upgrade/maintenance/native routes,
and now includes both `update-by-cr-dialogue-replay` and
`update-by-cr-knowledge-only`. It does not downgrade existing checks.

The delivered [ZIP](distribution/knowledge-harness-0.5.0rc1.zip) has SHA-256
`b1b7eac4aa0d4d950f0613986ff223cb2de482ba708327f3813b3add617a34e0`.
The companion `RELEASE.json` seals every asset. Rebuild with:

```text
.venv/bin/python scripts/build_p4.py --output /tmp/ucr-dist --source-id a09c9364beaa434d5ab35e3af97f396ad8b7fdfd9ba5c2c5167aff7747b0e0ab
python /tmp/ucr-dist/knowledge-harness-0.5.0rc1/install.py install --env /tmp/ucr-runtime
python /tmp/ucr-dist/knowledge-harness-0.5.0rc1/install.py install --env /tmp/ucr-independent --profile knowledge
/tmp/ucr-runtime/bin/python -I -B /absolute/repo/scripts/update_cr_trial.py --output /tmp/ucr-trial
/tmp/ucr-independent/bin/python -I -B /absolute/repo/scripts/update_cr_independent.py --output /tmp/ucr-independent-result
```

Verify all retained review bytes and their Git/ZIP source chain without executing
any ZIP/CI artifact contents:

```text
python reports/UpdateByCR/verify_packet.py
```

Use `Scripts/python.exe` on Windows. Paths above are explicit examples; preserve
existing unrelated environments. `trial/*-dialogue.json` contains the exact plan
and simulated fixture-user approval, actual canonical receipt and fresh context;
`*-replay.json` contains the fresh planner input, retrieval and compared plan;
`*-dotnet.log` contains the observed .NET behavior result. The oracle is
`tests/data/update-cr-oracle.json`, separate from the replay worker.

To activate only in an isolated fixture, use installed Python:

```text
python -I -m knowledge.cr_cli install --root FIXTURE
python -I -m knowledge.cr_cli installation-status --root FIXTURE
python -I -m knowledge.cr_cli uninstall --root FIXTURE
```

Options/requests are JSON stdin or `--input` with a temporary file outside source.
Set `language` to `ru` to force Russian; otherwise the foreground agent uses the
user's language. Start OpenCode 1.19.6 in the fixture and run `/update-by-CR`.
Provide missing links, inspect sources, answer material questions and review the
concrete exact plan. Approve that plan explicitly; an unapproved candidate is not
a canonical saved result. Resume with `/update-by-CR --resume SESSION_ID`.

Optional native controlled-host reproduction (download the supported official
OpenCode 1.19.6 Linux binary and verify `native/provenance.json` first):

```text
/tmp/ucr-runtime/bin/python -I reports/UpdateByCR/native_host_probe.py --python /tmp/ucr-runtime/bin/python --opencode /absolute/opencode --output /tmp/ucr-native
/tmp/ucr-runtime/bin/python -I reports/UpdateByCR/fault_profiles.py --output /tmp/ucr-provider
/tmp/ucr-runtime/bin/python -I reports/UpdateByCR/reuse_existing_profile.py --output /tmp/ucr-existing
```

The native probe creates only temporary project/XDG/npm configuration and a
loopback controlled responder; it is not a live-model test. Real-model replay
requires an already authorized configured model and remains NOT_RUN here.

CI evidence is transported as data from `p4-ci-evidence`. The collector verifies
the requested Git commit, all source hashes, all command-log hashes and every
release asset; it executes no artifact code:

```text
git fetch origin p4-ci-evidence
python reports/UpdateByCR/collect_ci.py --commit 1a4999fa62a0d78a9d331d4f6f9396a0bef73995 --source reports/UpdateByCR/source.json --output reports/UpdateByCR/ci
```

If no matching evidence exists yet the platform map is empty, not PASS. Refer to
the run/receipt URL and retained failed attempts when comparing later executions.
