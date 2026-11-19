# First use from the transferred 0.4.0rc4 ZIP

Extract the ZIP to a normal local path outside the source checkout. Every path below is relative to that extracted kit. Core prerequisites: Python **3.12**; for the C# demo, the **.NET 10.0.404 SDK** on x64 Linux or native Windows/NTFS with PowerShell **5.1**. The demo has no NuGet test-framework dependency: a Python standard-library regression executes the compiled C# assembly. Installation of the two core wheels is offline; SDK acquisition/restore is separate. Use a disposable copy of `examples/demo`, since the task edits its source.

## Linux

From the extracted kit, set absolute paths for the installed Python 3.12 and trusted .NET SDK. Spaces in paths are supported when quoted.

```sh
PYTHON=/absolute/path/to/python3.12
DOTNET=/absolute/path/to/dotnet
"$PYTHON" install.py install --env "$PWD/knowledge-only" --profile knowledge
"$PWD/knowledge-only/bin/python" -I -m knowledge.cli version --root "$PWD/examples/demo"
"$PYTHON" install.py install --env "$PWD/runtime" --profile full
RUNTIME="$PWD/runtime/bin/python"
cp -R examples/demo /absolute/disposable-demo
PROJECT=/absolute/disposable-demo
(cd "$PROJECT" && "$DOTNET" restore Project.csproj --disable-parallel)
"$RUNTIME" examples/controlled_provider.py --port 9000
```

Leave that terminal running. In a second terminal at the same extracted kit, set `RUNTIME`, `DOTNET`, and `PROJECT` to those same absolute paths, then:

```sh
"$RUNTIME" examples/configure.py --python "$RUNTIME" --dotnet "$DOTNET" --output runner.local.json
"$RUNTIME" -I -m harness.run_cli configure --root "$PROJECT" --input runner.local.json --init-knowledge
"$RUNTIME" -I -m harness.run_cli run --root "$PROJECT" --input examples/task.json
"$RUNTIME" -I -m knowledge.cli status --root "$PROJECT"
```

The run builds the real C# executable, executes the independent regression, obtains a separate reviewing context and delivers candidates. Canonical facts remain empty until explicit review/approval. Stop the local fixture with Ctrl+C.

## Windows PowerShell 5.1

Open PowerShell at the extracted kit and choose normal-spelling absolute local paths. No PowerShell 7, WSL, remote share or 8.3 alias is required.

```powershell
$Python = 'C:\Absolute\Python312\python.exe'
$Dotnet = 'C:\Absolute\dotnet\dotnet.exe'
$Kit = (Get-Location).Path
& $Python .\install.py install --env "$Kit\knowledge-only" --profile knowledge
& "$Kit\knowledge-only\Scripts\python.exe" -I -m knowledge.cli version --root "$Kit\examples\demo"
& $Python .\install.py install --env "$Kit\runtime" --profile full
$Runtime = "$Kit\runtime\Scripts\python.exe"
$Project = 'C:\Absolute\disposable-demo'
Copy-Item -Recurse .\examples\demo $Project
Push-Location $Project
& $Dotnet restore .\Project.csproj --disable-parallel
Pop-Location
& $Runtime .\examples\controlled_provider.py --port 9000
```

Leave the fixture running. In another PowerShell window at the kit, set `$Runtime`, `$Dotnet` and `$Project` to the same absolute paths:

```powershell
& $Runtime .\examples\configure.py --python $Runtime --dotnet $Dotnet --output .\runner.local.json
& $Runtime -I -m harness.run_cli configure --root $Project --input .\runner.local.json --init-knowledge
& $Runtime -I -m harness.run_cli run --root $Project --input .\examples\task.json
& $Runtime -I -m knowledge.cli status --root $Project
```

## Adapt to an actual project/provider

`examples/runner.json` is runner configuration v1. Its two executable placeholders must be replaced by existing absolute trusted paths; `examples/configure.py` does that for the demo. `examples/task.json` is task v2. The project root is the `--root` argument, never a path inside the task. Update the goal, acceptance and writable scope before using a different project. Keep build/test definitions under operator control: the model cannot change the project/recipe policy. Arguments are an argv array, without shell expansion. `{artifacts}` is a broker-owned output directory. Build results use `exit`; real test results use `unittest`, `trx` or the documented JSON format. The demo uses real compiled behavior plus `unittest`; for an existing .NET test project, an alternative trusted test argv is:

```json
["C:\\Absolute\\dotnet\\dotnet.exe", "test", "tests/Tests.csproj", "--no-restore", "--logger", "trx;LogFileName=tests.trx", "--results-directory", "{artifacts}"]
```

Pair that with `"result": {"format":"trx","path":"{artifacts}/tests.trx"}`. Restore dependencies explicitly before the run. Do not grant edits to existing tests unless a reviewed task explicitly lists the exception.

For a real compatible HTTP provider, use `examples/configure.py --live --endpoint https://provider.example/v1/chat/completions --model YOUR_MODEL --key-env PROVIDER_API_KEY ...`. Set the named environment variable privately in the invoking shell. Never put credential values in JSON, task text, recipe environment, logs or commits. The provider must support non-streaming OpenAI-compatible tool calls. The shipped loopback provider is a deterministic fixture with synthetic usage; it establishes software execution, not live model quality or pilot correctness.

Optional MCP is a separate online dependency profile: add `--mcp-online` to the full installer only when required. `optional-mcp.lock` pins the adapter dependency. The core and Knowledge-only profile need no MCP service, host enrollment or agent executable.

## Commit, refresh and explicitly approve candidates

Run the commands below using the installed full runtime. Commit the intended application source with ordinary Git first; committing changes the Knowledge snapshot even when file bytes stay identical. Then refresh before preparing a plan:

```sh
python -I -m knowledge.cli knowledge-candidates-update --root /absolute/project --max-files 100
python -I -m knowledge.cli knowledge-candidates-update --root /absolute/project --scan-id SCAN_ID --max-files 100
python -I -m knowledge.cli knowledge-candidates-push --root /absolute/project
python -I -m knowledge.cli apply --root /absolute/project --plan FINGERPRINT --approve FINGERPRINT
python -I -m knowledge.cli acknowledge --root /absolute/project --plan FINGERPRINT
python -I -m knowledge.cli lookup --root /absolute/project --kind claims --id EXACT_CLAIM_ID
```

Resume scan chunks until `complete=true`. Inspect the **fresh** plan and its included payloads before supplying its exact fingerprint. An earlier approval is never carried over to refreshed source. Old equivalent pending payloads remain in the queue with additive `candidate_refreshes` audit links and appear in the plan's skipped list; original IDs, payloads and review history remain intact. Rejected/deferred observations keep their deliberate disposition across equivalent rescans. A changed meaning is a new review; explicitly reject/defer any obsolete competing pending meaning through `knowledge ... review --id CANDIDATE --disposition deferred --reason "..."` rather than reusing its approval. Unrelated pending work remains in the fresh plan for review. Acknowledge committed work before further review; the next plan omits acknowledged candidates.

## Interrupted execution versus interrupted delivery

```sh
python -I -m harness.run_cli status --root /absolute/project --run-id RUN_ID
python -I -m harness.run_cli resume --root /absolute/project --run-id RUN_ID
python -I -m harness.run_cli capture-status --root /absolute/project --run-id RUN_ID
python -I -m harness.run_cli capture-retry --root /absolute/project --run-id RUN_ID
```

`resume` recovers application execution. `capture-retry` only delivers a run whose durable execution already passed, under project ownership, without provider calls, edits or recipes. An unfinished execution returns `capture-retry-ineligible`; use `resume`. A completed optional-capture run may still be `completed-degraded` with a pending outbox; delivery retry updates it to `completed` when delivery succeeds. Retries preserve the original candidate/event/payload/time and deduplicate an accepted payload even if the delivery receipt was lost. Source or configuration drift still refuses. The configured `file_bytes` policy is used at start, resume, capture, retry and finalization.

## Bounds, scans and native evidence

Each public `knowledge-init --max-files N` invocation spends at most N real extractor calls over scan **and reconciliation**, including the final chunk. Durable observations and ambiguity state are reused. Inventory enumeration, content hashing, Git status/index inspection and freshness hashing remain proportional to repository size; this is not a constant-time initialization promise. Partial coverage never proves absence; stale snapshots require restart. Working-file SHA-256 and Git's normalized blob identities are different domains; CRLF checkout conversion does not make a clean tracked file dirty. Older raw evidence can be compared to a committed blob only when its exact LF/CRLF correspondence is proved.

Task v1 remains the accepted legacy five-role policy. Task v2 is bounded sequential execution: each item/repair gets a fresh Coding context, rotations preserve owned observations, final gates and review bind the final source/configuration, and attempts/request/time/token budgets never reset. Unknown provider/process outcomes retain explicit recovery rules. `metrics` exposes whole-system accounting, without claiming universal token/speed savings.

`.github/workflows/p4.yml` qualifies pushes to `main`/development branches and pull requests to `main` on Linux and native Windows. PR validation has read permissions; evidence publication and correction-PR creation are confined to trusted events. Reports-only publication does not recursively qualify. The owner merges and cleans branches after independent review.
