# Knowledge + Harness — P4 implementation candidate (0.5.0rc1)

New tasks use the task-v2 bounded pipeline in [P4 usage](docs/P4/USAGE.md) and [the P4 example](examples/p4/task.json). Main coordinates sequential Coding items, build/test run as trusted runtime recipes, and independent Reviewing remains mandatory. Task-v1 inputs retain the accepted legacy policy.

Build with Python 3.12: `python scripts/setup_p3.py`, then `.venv/bin/python scripts/build_p4.py --output .local/p4-release`. Verify the installed product with `.venv/bin/python scripts/verify_p4.py`. Read [P4 acceptance](reports/P4/ACCEPTANCE-MATRIX.md) before adoption; native qualification and live-model results remain separate.

## Retained P3 and historical documentation

# Knowledge + Harness — P3 release candidate

Version 0.3.0rc1 keeps the existing knowledge-p0/harness-p0 distribution and CLI/import names. P3 adds a transferable offline core bundle, a native Windows execution backend, approved upgrade/backup/restore/rollback tooling and an opt-in OpenCode v2 MCP companion. See the current [P3 report](reports/P3/P3-REPORT.md) and [qualification matrix](reports/P3/QUALIFICATION.json) for executed OS profiles. Implementation review, native qualification, live-host/model validation and production migration are separate claims.

Build the distribution with Python 3.12:

```bash
python scripts/setup_p3.py
.venv/bin/python -B scripts/build_p3.py --output .local/release
# Transfer and verify the bundle's external SHA-256, then extract outside this checkout.
python install.py install --env "/new path/Knowledge Env" --profile knowledge
python install.py doctor --env "/new path/Knowledge Env"
python install.py install --env "/new path/Knowledge Env" --profile full
```

On native Windows, use `powershell -NoProfile -File install.ps1 install --env "C:\new path\Knowledge Env" --profile full` with Python 3.12 installed. Windows PowerShell 5.1 is the claimed launcher; PS7 is not certified. The product launcher discovers native executable locations. Core uses local wheels only; optional MCP is a pinned online add-on (`--mcp-online`), not an offline complete wheelhouse.

Installed commands: `knowledge --root ROOT` plus its existing subcommands; `harness` remains read-only; `harness-run version|doctor|configure|run|status|resume|cancel|capture-status|capture-retry|metrics|compare --root ROOT`; `knowledge-maintain backup-preview|upgrade-preview|restore-preview|apply|status|recover|doctor --root ROOT`; `harness-host preview|apply|remove-preview|doctor|run --root ROOT`. Use the selected environment's Python with `-m knowledge.cli`, `-m knowledge.maintain_cli`, `-m harness.run_cli` or `-m harness.companion` on either OS. Initialization and discovery are distinct; all canonical updates retain exact explicit approval/apply/ack.

Run the full verification on Linux with `.venv/bin/python -B scripts/setup_benchmark.py` then `.venv/bin/python -B scripts/verify_p3.py`. Native Windows uses `powershell -NoProfile -File scripts/verify-windows.ps1` and native .NET 10.0.404. Standard task-branch Actions jobs exercise both profiles and retain raw evidence even on failure. Generate the final review packet with `scripts/make_review_p3.py`; missing/mismatched native evidence keeps Windows NO_GO.

Read [install](docs/P3/INSTALL.md), [upgrade](docs/P3/UPGRADE.md), [backup/restore/rollback](docs/P3/BACKUP-RESTORE-ROLLBACK.md), [uninstall](docs/P3/UNINSTALL.md), [Windows](docs/P3/WINDOWS-VALIDATION.md), [companion](docs/P3/OPENCODE-INTEGRATION.md), [rehearsal](docs/P3/UMUH-ONBOARDING-REHEARSAL.md) and [adoption runbook](docs/P3/ADOPTION-RUNBOOK.md). Existing root-bound stores are not relocated by copying directories; new projects get fresh identities. Canonical knowledge is never silently applied by Harness or maintenance. P0/P1/P2 reports remain historical evidence. No production cutover, merge or publication is performed automatically.

Automatic .NET testing (runner v2): [contract](docs/P4/AUTOMATIC-TESTS.md), [machine installation (RU)](docs/P4/INSTALL-RU.md), [project setup (RU)](docs/P4/PROJECT-SETUP-RU.md). Normal .NET templates have only trusted build recipes; every case-insensitive `*Tests.csproj` is a mandatory automatic gate.
