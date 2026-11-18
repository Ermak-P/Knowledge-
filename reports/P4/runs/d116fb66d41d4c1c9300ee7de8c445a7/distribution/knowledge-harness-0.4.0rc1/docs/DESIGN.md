# P4 design: bounded sequential execution

Product 0.4.0rc1. Config v1 and task v1 keep the accepted P3 driver. Task v2 explicitly selects `bounded-v1`; new P4 examples use v2. Knowledge formats and the journal database envelope remain v1; P4 state is a validated extension of a run. Legacy pending runs never enter the new driver.

## Authority and state

A v2 task adds acceptance criteria and optional ordered items to the existing authority envelope. Omitted items produce one item. Item paths are literal paths contained in the outer patterns (no wildcard subset guessing), recipes and test exceptions are subsets, and dependencies refer only to earlier items. Every item carries the full original acceptance criteria; decomposition cannot weaken them. The initial ordered plan is immutable. Main coordinates with `advance`, with no patch/process authority; runtime transitions Coding -> deterministic verification -> next item -> independent Reviewing -> Main final -> capture. Only Coding writes, through the existing broker. Read-only tasks have no items/verifiers and use Main alone.

P4 stores plan, active index, stage, item attempts, epochs, receipts, findings and repair families in the run payload. Intent IDs derive from persisted item/attempt/stage, not wall time. Broker patch and process journals remain the only effect path. All transitions save before the next effect. Existing unknown provider/process outcomes retain their recovery semantics. Source/config/companion entry checks repeat at every safe boundary. Capture runs once after final source-bound completion.

## Contexts and handoffs

Each item/repair gets a fresh Coding frame. Ordinary Main requests reconstruct the ledger without transcripts. A hard serialized request cap includes schemas and policy. At 80% of that cap or after four complete tool rounds, a child rotates at a protocol boundary; old frames are archived and retained in the journal, never concatenated into the new context. A checkpoint records source/config, all required criteria, unresolved findings and owned action IDs. Narratives are untrusted, capped at 1000 UTF-8 bytes; references are reconstructed by runtime, never approved by summary text. An irreducible checkpoint exceeding the cap stops before HTTP with `split-required`. Aggregate requests, elapsed time and token limits never reset. Tool pairs are kept intact; P4 never silently trims them. Tools offer bounded receipt/diff/log ranges with action identity and file hash.

## Verification and repair

Verifiers call the existing Broker with Building/Testing capability but no model frame/session. Records explicitly identify deterministic verifier events and authorizing item/attempt. All final gates require the current source/config identity; patches clear gates. Recipe process ownership, cancellation, parsers and artifacts are reused. Final review has independent context, criteria, changed paths and broker receipt IDs. A rejected review enters the same finite repair path.

At most two failed cycles per normalized diagnostic family, at most one read-only diagnosis, and at most three Coding attempts per item / six failures per run. Diagnosis classifies uncertainty and can suggest a hypothesis, but cannot change the immutable plan, recipes, criteria or budgets. After diagnosis one last bounded attempt is permitted; exhausted allowances stop with `repair-exhausted`. Families remove timestamps/numbers/addresses and use recipe/parser identity plus normalized failure diagnostics. Resume and rotation preserve all counters.

## Compatibility and lifecycle

New code loads P3 runs using the legacy driver. P4 runs include a non-v1 task, so old P3 runtime validation must refuse pending P4 execution; rollback requires restoring a pre-P4 maintenance snapshot before installing retained accepted P3 wheels. Stop runtime/MCP processes before replacement. No cross-root restore. All new authoritative data is inside existing .harness/runs.sqlite3 and owned artifacts, covered by maintenance snapshots. P4 keeps the platform backends and native path checks; native Windows qualification remains separate evidence.
