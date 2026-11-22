The first full installed-suite pass (327 tests) found three failures: two old
read-only facade absence assertions, and recovery of a committed unbound intent
whose host pending pointer was lost. All three are retained in
`interim-full-failed.log`. The facade now maps structured store-absent back to its
existing degraded contract. Authentic same-source unbound redelivery can complete
binding while preserving source order; completed bindings still replay without
inference. The final source-bound qualification runs the complete enlarged suite.
The early six-test baseline stage-2 log contains expected failures on the old code;
focused-pass.log covers the completed stage-2 behavior including Node hook, fresh
processes, diagnosis/repair, two items, dependency/conflict and byte boundaries.
