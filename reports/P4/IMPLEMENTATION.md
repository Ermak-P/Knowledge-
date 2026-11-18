# P4 implementation

Product 0.4.0rc1; task v2/bounded-v1, run state v2; legacy v1 semantics retained. Plans, sequential Coding scopes, deterministic broker verifiers, source-bound independent review, fresh contexts and durable checkpoints/repair budgets are implemented in harness.p4 and engine. Complete new state remains inside the existing maintenance snapshot boundary.

Validation: installed wheels outside checkout; 199 tests. See raw regression log for exact outcomes. Linux qualification only. No merge, push, release publication or production adoption performed.

Limitations: post-start plan changes are refused rather than automatically replanned. Repair policy caps attempts across all failure families, a stricter bound than separate per-family budgets. Complete new crash-window and hostile-boundary coverage remains incomplete; this is not a fully qualified P4 release.
