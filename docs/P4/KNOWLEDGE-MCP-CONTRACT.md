# Knowledge MCP contracts and structured inputs

## JSON source configuration

Knowledge selects one syntax policy per included JSON file. It parses
`appsettings.json`, `appsettings.*.json`, and `launchSettings.json` as
`dotnet-json`, accepting comments and trailing commas. The .NET configuration
provider and CLI launch settings parser both enable these features.
[Configuration provider](https://github.com/dotnet/runtime/blob/main/src/libraries/Microsoft.Extensions.Configuration.Json/src/JsonConfigurationFileParser.cs)
[Launch settings parser](https://github.com/dotnet/sdk/blob/v9.0.300/src/Cli/dotnet/commands/dotnet-run/LaunchSettings/LaunchSettingsManager.cs)

`*.jsonc` accepts line and block comments with trailing commas disabled.
Other `*.json` files use `strict-json`. UTF-8 with or without a BOM is
supported. Escaped quotes and comment-like text inside strings stay intact.
Diagnostic line and column numbers refer to the original source, and reads
return original text and the original content hash. Filename, linked-path,
encoding, and byte limits still apply. Keep sensitive sources excluded under
the project policy.

Add overrides in the existing `.knowledge/discovery.json`. Patterns refer to
project-relative paths and are evaluated in lexicographic order. An override
changes parsing for already eligible files.

```json
{
  "version": 1,
  "json_dialects": {
    "**/settings-with-comments.json": "jsonc",
    "**/settings-with-trailing-comma.jsonc": "dotnet-json"
  }
}
```

## Recover extraction gaps

Call `knowledge_scan_diagnostics` with `section: "scans"` to find the terminal
scan ID. Correct the failed source or configure its dialect, then call
`knowledge_scan` with `action: "recover"`, the original `scan_id`, and the
original scope. Use the same Git range for an incremental scan, or reuse the
current incremental job's recorded range. Poll `knowledge_scan` with
`action: "status"`. The successful worker outcome appears as
`worker_state: "COMPLETED"`. The linked scan and original ID remain in history.

Recovery rechecks source identity and scope, reuses verified work, and analyzes
eligible failed paths. Repeating recovery against the same source and policy
reuses the linked result. Use `resume` for a compatible interrupted checkpoint
or a transient retry. If the Git revision, otherwise successful source, or
extraction context has changed incompatibly, the backend returns a reason and
may require an explicit fresh scan. Recovery can enqueue candidates through the
usual reconciliation. Applying them still requires a separately approved exact
plan fingerprint.

## Diagnostic sections

Call `knowledge_scan_diagnostics` with the arguments in the table.
`scope` accepts `full` or `incremental`. `max_bytes` bounds the payload.
Most sections page by row using `cursor`, `limit` from 1 to 100, and the
returned `next_cursor`. Individual candidate text pages by character offset
using `cursor`. The existing `limit` argument is accepted for candidate text.
Omit all section-specific arguments outside their listed section.

| Section | Purpose | Section-specific arguments and discovery | Minimal invocation |
| --- | --- | --- | --- |
| `failures` | Extraction failures and exclusions | Optional `scan_id` from `scans` | `{"section":"failures"}` |
| `coverage` | Per-file coverage | Optional `scan_id` from `scans` | `{"section":"coverage"}` |
| `reconciliation` | Claim freshness and negative evidence gaps | Optional `scan_id` for a current source snapshot | `{"section":"reconciliation"}` |
| `impact` | Changes and affected claims | Optional `scan_id` and `collection` from `impact_summary` | `{"section":"impact"}` |
| `policy` | Effective source policy | Optional `scan_id` from `scans` | `{"section":"policy"}` |
| `identity` | Missing analysis and ambiguous identities | Optional `scan_id` from `scans` | `{"section":"identity"}` |
| `scans` | Scan history and linked recovery IDs | Optional `scan_id` for one entry | `{"section":"scans"}` |
| `checkpoint` | Current job checkpoint and compatibility | Uses the current job in `scope` | `{"section":"checkpoint"}` |
| `duplicates` | Duplicate groups or member operations | Optional `group` from rows of the unfiltered section | `{"section":"duplicates"}` |
| `candidates` | Candidate IDs in the queue, a scan, or a plan | Optional `scan_id` from `scans` or `plan` from plan status | `{"section":"candidates"}` |
| `candidate` | One candidate or one operation as paged JSON text | Required `candidate` from discovery. Optional `operation` zero-based index and `plan` to inspect the resolved plan candidate | `{"section":"candidate","candidate":"<candidate ID>"}` |
| `plan-progress` | Current preparation progress | Uses the current plan job | `{"section":"plan-progress"}` |
| `plan-dispositions` | Candidate dispositions in a plan | Optional canonical `plan` fingerprint. Defaults to the prepared plan in the current job | `{"section":"plan-dispositions","plan":"sha256:<canonical plan>"}` |

Scan IDs are 64 lowercase hexadecimal characters. A canonical plan
fingerprint has the `sha256:` prefix and 64 lowercase hexadecimal characters.
Candidate IDs are opaque strings returned by candidate discovery.
`plan-dispositions` and the diagnostic `plan` parameter use the canonical
fingerprint. Applying a plan through the machine adapter requires the separate
approval fingerprint returned by the plan workflow.

## Built-in help and execution examples

`knowledge_instructions({})` lists packaged help. Pass only `tool` for its
overview and examples, including the reviewed, source-bound candidate batch
schema. For diagnostics, pass `name: "sections"` for the machine-readable
argument matrix. To look up a project or shared instruction, pass its configured
tool and instruction name. Packaged help has its own source and is available
before any project or shared store exists.

Use [the JavaScript example](../../examples/knowledge-parallel-reads.mjs) to run
independent read-only operations together. Each destructured value from
`Promise.allSettled` is one settled result. Inspect its status and keep the
other successful results if a request rejects. A fulfilled MCP request can
still contain `ok: false`. Read its `error` and `details`, using the supplied
discovery invocation where available. An unknown resource requires observation
or discovery. Permanent extraction failures require a source or policy change.
Transient failures and configuration drift use the documented recovery paths.
After a timeout or unknown mutating outcome, observe the durable job or
approval status before sending another mutation. Run scan control, plan
preparation, and approval sequentially.
