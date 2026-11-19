# P4 usage

Python 3.12. Install the transferred 0.4.0rc3 kit outside this checkout:

```sh
python install.py install --env /absolute/runtime --profile full
python install.py doctor --env /absolute/runtime
```

Use that runtime's Python (Windows: Scripts/python.exe, Linux: bin/python).
Configure the existing runner v1 format with a compatible provider endpoint and absolute trusted build/test executables. Never put credentials in task files. See the P3 installation/provider documentation for recipe formats. Optional MCP remains the pinned online add-on; the core has no mandatory MCP dependency.

```sh
python -I -m harness.run_cli configure --root /absolute/project --input runner.json --init-knowledge
python -I -m harness.run_cli run --root /absolute/project --input task.json
python -I -m harness.run_cli status --root /absolute/project --run-id RUN_ID
python -I -m harness.run_cli metrics --root /absolute/project --run-id RUN_ID
python -I -m harness.run_cli resume --root /absolute/project --run-id RUN_ID
```

`examples/p4/task.json` is the one-item route. Change its goal and criteria to the real authorized task before execution. For multiple items set `items` to an ordered array, for example:

```json
[{"id":"implementation","objective":"Implement Feature.cs","depends":[],"writable":["Feature.cs"]},
 {"id":"verification_fix","objective":"Check and finish Feature.cs against all original criteria","depends":["implementation"],"writable":["Feature.cs"]}]
```

Main may propose this array with `plan` before any Coding attempt. Each scope pattern must exactly match one of the outer patterns; arbitrary glob containment is deliberately unsupported. Plan replacement after execution begins is refused. Task/config changes require a separately authorized new run, never budget resetting inside a pending run.

Status includes run.p4.items (attempts, issues, handoff, epochs), checkpoints with archived complete tool protocol pairs, deterministic verifier references and cycles. Metrics include actual request bytes/hashes and provider usage. Bytes are not tokens. Provider usage is synthetic for fixtures, unknown when absent. The single/multi P2 experiment remains separate from P3/P4 policy.

Continuation rotates after four complete tool rounds or 80% serialized request size. Hard limits include policy/tool schemas. Source and criteria survive in the ledger; use read/search/artifact to retrieve evidence again. Artifact accepts action, offset and limit, bounded by tool_bytes/2, and returns an owned log excerpt and hash. A checkpoint that cannot fit stops with split-required before HTTP.

A failed build/test causes at most three Coding attempts per item and at most one read-only diagnosis across the run. A still-failing final attempt returns repair-exhausted. Final review rejection reopens the final item within the same aggregate repair budget; it cannot complete successfully while findings remain. Unknown provider outcomes remain blocked on resume and are never automatically resent. Tests demonstrate these outcomes with local HTTP fixtures and real processes; no model service is installed or assumed.

R1 continuation: Coding/Planning/Main may use `checkpoint` with a bounded untrusted note, next_step and owned action IDs. After rotation the system includes `checkpoints` and a bounded continuation with discovered facts. `continuation(checkpoint, offset, limit)` retrieves more of that record; `artifact` can retrieve the original read/search receipt. These tools cannot approve checks or expand scope.

For multi-file dependencies, add `"recipes": ["build"]` to an intermediate item if the full tests require later files. Final-source verification still runs all outer build/test recipes. A final reviewer should identify affected item IDs and concrete paths when several owners are possible.

Native validation uses `.github/workflows/p4.yml` with process-local long paths before checkout, native Python 3.12 and .NET 10.0.404. Verification includes all fifteen acceptance IDs and emits receipts/artifacts; prior job 44384715030 failed Windows checkout before executing tests.
