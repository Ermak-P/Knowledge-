# Reproduction (Linux performance; native Windows correctness in CI)

Use Python 3.12 and the pinned development requirements. Work in place. No worktree,
live model, real service/container or user database is required. All roots below
must be new disposable absolute directories. Do not relocate/rewrite existing IDs.

## Install baseline and candidate outside the checkout

The measured baseline used the retained accepted kit, whose 53 installed source
assets were independently matched against commit
`73a3fc70c5fde17536568baae2a03b1b8be8b8a1` with the official wheel LF normalization.
See `baseline-install.json`. To rebuild from that exact pinned commit instead:

```sh
mkdir /tmp/sqlite-baseline-source
git archive 73a3fc70c5fde17536568baae2a03b1b8be8b8a1 packages scripts docs/P4 release/p4-kit examples/p4 inputs | tar -x -C /tmp/sqlite-baseline-source
.venv/bin/python /tmp/sqlite-baseline-source/scripts/build_p4.py --output /tmp/sqlite-baseline-kit --source-id 73a3fc70c5fde17536568baae2a03b1b8be8b8a1
python3 /tmp/sqlite-baseline-kit/knowledge-harness-0.5.0rc1/install.py install --env /tmp/sqlite-baseline-runtime
```

Use the delivered final kit (verify its SHA-256 against `distribution/package.json`):

```sh
mkdir /tmp/sqlite-review-kit
unzip reports/SQLiteOptimization/distribution/knowledge-harness-0.5.0rc1.zip -d /tmp/sqlite-review-kit
python3 /tmp/sqlite-review-kit/install.py install --env /tmp/sqlite-candidate-runtime
```

Both environments must import from their own site-packages. The driver asserts
this with `-I`; the final `candidate-install.json` verifies all 55 installed source
assets against the qualified Git source. Core measurements need no MCP dependency.

## Valid fixture generation and interleaved public APIs

```sh
python3 scripts/sqlite_run_benchmarks.py \
  --baseline-python /tmp/sqlite-baseline-runtime/bin/python \
  --candidate-python /tmp/sqlite-candidate-runtime/bin/python \
  --work-root /tmp/sqlite-review-fixtures \
  --output /tmp/sqlite-review-results \
  --only op-32-0 op-32-1k op-32-10k op-256-10k op-256-100k op-long-history \
         queue-1k-1 queue-10k-1 queue-10k-10 queue-10k-100 queue-10k-committed \
         legacy
```

For the final journal fixture, use the complete owned-run generator (not the common
sampler's provisional journal seed). It creates 1,000/10,000/30,000 outbox entries,
complete historical runs/events and a real queued payload/receipt, validates every
owner with Journal.load, and measures complete write records:

```sh
python3 reports/SQLiteOptimization/journal_profile_probe.py \
  --baseline /tmp/sqlite-baseline-runtime/bin/python \
  --candidate /tmp/sqlite-candidate-runtime/bin/python \
  --work-root /tmp/sqlite-review-journals --output /tmp/sqlite-journal-default
```

Repeat with a different output directory and `--index-profile ordinary` for the
explicit opt-in comparison, reusing the same generated roots. Fixture manifest
and snapshot hashes are checked before every reset. Generation uses the baseline,
normal validators and actual empty-plan commits/receipts; it is not timed. Public
operation samples remain fully validated. State-changing samples reset quiescent
bytes at the original root. No database identity is transplanted or rewritten.

For one case or separate instrumentation:

```sh
/tmp/sqlite-candidate-runtime/bin/python -I scripts/sqlite_benchmark.py sample --root /tmp/sqlite-review-fixtures/op-32-1k --operation records --count 20 --output /tmp/records.json
/tmp/sqlite-candidate-runtime/bin/python -I scripts/sqlite_benchmark.py profile --root /tmp/sqlite-review-fixtures/op-32-1k --operation records --output /tmp/records-profile.json
```

Final experiments omit the optional 100,000-row queue matrix for bounded runtime;
the runner can generate it when requested. The report explains this reduction.
Do not call warm connections/processes a cold disk-cache experiment.

## SQL diagnostic and complete CLI probes

After public benchmarks finish, SQL diagnostics copy hash-verified snapshots,
retain the original identity and validate all rows again after DML. They do not
execute project effects or substitute SELECT timing for a public operation:

```sh
/tmp/sqlite-candidate-runtime/bin/python -I scripts/sqlite_index_lab.py --root /tmp/sqlite-review-fixtures/queue-10k-1 --output /tmp/queue-indexes.json
python3 reports/SQLiteOptimization/outbox_index_reads.py --root /tmp/sqlite-review-journals/journal-30k --output /tmp/outbox-indexes.json
python3 reports/SQLiteOptimization/cli_context_probe.py --baseline /tmp/sqlite-baseline-runtime/bin/python --candidate /tmp/sqlite-candidate-runtime/bin/python --root /tmp/sqlite-review-fixtures/op-32-1k --count 20 --output /tmp/context-cli-small.json
```

Repeat queue DML diagnostics for 10%/100% pending. For the rare-COMMITTED fixture,
use `plan_index_reads.py` with the same root/output arguments; it never changes
approval states. The common DML lab expects an acknowledged empty receipt and
does not support that rare fixture (the attempted error is retained).
`inventory_probe.py` records schema, PK/secondary index details, page/freelist and
opt-in outbox index allocation. No EXPLAIN text is asserted as a stable API.

## Integrity, predecessor and complete qualification

```sh
python scripts/setup_p3.py
.venv/bin/python -B -m unittest discover -s tests -v
.venv/bin/python -B scripts/verify_p4.py

# Native Windows / Windows PowerShell 5.1
powershell -NoProfile -File scripts/verify-p4-windows.ps1
```

The retained final CI runs execute these existing installed-kit qualification
routes. `collect_ci.py` reads the data-only `p4-ci-evidence` branch, validates exact
source/log/package hashes and preserves failures; it never executes artifact code.

For actual installed predecessor writes, same-root upgrade/recovery/rollback,
canonical equality, hard process exits and bounded process contention:

```sh
python3 reports/SQLiteOptimization/compatibility_probe.py --baseline /tmp/sqlite-baseline-runtime/bin/python --candidate /tmp/sqlite-candidate-runtime/bin/python --root /tmp/sqlite-compat-new/project --output /tmp/sqlite-compat.json
```

For standalone Knowledge, install the same kit with `--profile knowledge` into a
new environment and run `standalone_probe.py` there with `-I`, a new root and output.
It asserts Harness/MCP are absent and exercises project/shared isolation plus the
explicit backed-up no-journal maintenance path.

Upgrade/recovery/rollback operator commands and limits are in the packaged
`docs/SQLITE-OPTIMIZATION.md`. Do not apply these fixture commands to user stores.
