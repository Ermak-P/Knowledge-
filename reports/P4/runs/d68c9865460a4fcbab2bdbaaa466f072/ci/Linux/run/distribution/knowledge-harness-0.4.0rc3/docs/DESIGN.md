# P4 design: bounded sequential execution

Product 0.4.0rc3. Config v1 and task v1 keep the accepted P3 driver. Task v2 explicitly selects `bounded-v1`; new P4 examples use v2. Knowledge formats and the journal database envelope remain v1; P4 state is a validated extension of a run. Legacy pending runs never enter the new driver.

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

## R1 corrections (retained in 0.4.0rc3)

Continuation v2 carries bounded read/search observations and model-authored decision notes backed by owned action signatures/result hashes. Original authority is rendered independently. `checkpoint` records untrusted decisions/next step and validates action IDs; `continuation` retrieves a checkpoint contract by ID and bounded UTF-8 range. Raw history remains audit-only. Dependent item handoffs carry the same bounded discovered state.

Review findings can specify `affected: [{item, paths}]`; the runtime validates paths against the immutable item's scope. For compatible string findings, literal authorized paths resolve their owning item; ambiguous multi-item findings stop for an explicit target. Reopened earlier items retain attempts, global budgets and review history; dependent verification is marked stale and final gates always rerun on the final source.

An item may declare `recipes`, a subset of outer authorized recipes. This permits build-only intermediate checks while later dependent files are unfinished. The final item, and any final repair with all other items completed, always executes every outer recipe. An omitted subset retains the previous all-recipes behavior.

Known P3/P4 predecessor maintenance markers are read without mutation. An exact-approved transition declares predecessor/current product versions and unchanged data formats; backup and journal retain predecessor state. Recovery of an already-approved supported predecessor operation finishes its original product semantics before a new upgrade. Unknown marker or archive formats still refuse.

## R2 absent-target correction (0.4.0rc3)

Final review can name a concrete file that is absent but already authorized. Structured targets pass the same non-mutating root, private/protected, link and writable checks as a real patch, under both original outer task and immutable item scope. File existence is not authority. String findings can resolve absent literal item paths when one item owns them; overlapping owners, unknown paths and absent targets inferred only from a glob stop for an explicit validated target. A missing file does not grant a new recipe or test-edit exception.

Only the affected item reopens with its previous attempts and global counters. The corrective patch creates the file with a null before-state; final deterministic gates and independent review bind the resulting source. Installed regressions cover new source and executable regression-test files, both finding formats, unchanged unrelated files and candidate-only capture.
