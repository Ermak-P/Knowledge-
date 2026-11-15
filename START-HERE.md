# Knowledge + Harness: P2

Knowledge is independently installable. Harness 0.2 adds controlled agent execution with a configurable OpenAI-compatible HTTP provider, five role contexts, scoped edits, real recipe checks, durable recovery and automatic reviewable Knowledge candidates. P2 is submitted for external review; live model/host effectiveness is not certified.

```bash
bash scripts/setup.sh
# Local llama-server: enable an appropriate tool-capable chat template / --jinja.
# Set model/endpoint and absolute recipe executable in your copy of this file.
cp -R examples/p2-project /tmp/p2-demo
.venv/bin/harness-run configure --root /tmp/p2-demo --input examples/p2-provider.json --init-knowledge
.venv/bin/harness-run validate-config --root /tmp/p2-demo
.venv/bin/harness-run run --root /tmp/p2-demo --input examples/p2-task.json
.venv/bin/harness-run status --root /tmp/p2-demo
# Use the returned run ID:
.venv/bin/harness-run metrics --root /tmp/p2-demo --run-id RUN_ID
.venv/bin/harness-run resume --root /tmp/p2-demo --run-id RUN_ID
.venv/bin/harness-run capture-status --root /tmp/p2-demo --run-id RUN_ID
.venv/bin/harness-run capture-retry --root /tmp/p2-demo --run-id RUN_ID
.venv/bin/harness-run cancel --root /tmp/p2-demo --run-id RUN_ID
```

The demo intentionally starts with VALUE=1 and an independent expected VALUE=2 test; the task authorizes only Feature.py. Python edits have no supported .NET discovery fact, so automatic capture honestly reports no candidate. For .NET source behavior/capture examples see the executed evaluation and generators. Endpoint credentials, if needed, use provider `key_env` naming your environment variable, never JSON secrets. Only configure recipes you trust: role checks are not an OS sandbox for build hooks.

The original `harness --root ROOT --task TEXT` is still read-only. Knowledge retains its CLI, subprocess JSON and MCP adapters and explicit prepare/review/apply lifecycle. Run independent Knowledge using `pip install ./packages/knowledge`; Harness/model services are unnecessary.

Verify everything: `.venv/bin/python -B scripts/verify_p2.py` (requires the pinned benchmark and SDK; `scripts/setup_benchmark.py` provisions the documented baseline). Generate packet: `.venv/bin/python -B scripts/make_review_p2.py`. See [P2 contracts](reports/P2/P2-CONTRACTS.md) and [report](reports/P2/P2-REPORT.md). P0/P1 tasks and reports remain historical evidence. No P3 work is included.
