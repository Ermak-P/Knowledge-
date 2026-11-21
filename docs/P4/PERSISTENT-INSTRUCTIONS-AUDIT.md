# Persistent instructions: capability audit

Initial baseline: `ebc909a164b0408e656d29e334b0a2cb982eb5da`; implementation was
fast-forwarded to published `37a280da38d913b6fef7867e0f988ad40026947f`
(context path optimization) before qualification. No applicable AGENTS.md
was present in the supplied checkout. Work is in place, without worktrees.

| Boundary | Existing capability | Gap / integration decision |
|---|---|---|
| Knowledge `project.py`, `store.py`, `coordination.py` | Explicit project resolver, SQLite FULL transactions, maintenance gate, canonical claims/queue/history | No shared root or operational rules. Add a compatible operational extension in the same SQLite database, with a shared resolver; leave architecture records and promotion unchanged. |
| `lifecycle.py`, `discovery.py` | Revisioned architectural facts, evidence, exact promotion, capture receipts | Operational instructions and uncertain recovery candidates need separate kinds and authority. Reuse transactions and history conventions, not architecture claims. |
| `knowledge/cli.py`, `mcp.py` | Local operator writes; read-only MCP | Add local trusted ingress/maintenance and bounded read-only operational MCP. Never expose a model-writable "user" teaching tool. |
| `harness/tools.py` owned broker | Typed tools, pre-effect intents, source/config binding, supervised processes, idempotent receipts | Add deterministic preconditions before recipe/patch effects and targeted error lookup. Recovery uses the same owned process supervisor, with separately configured capabilities. |
| `runtime.py`, `companion.py` | Validated runner config; immutable enrolled MCP tasks; execution lease; existing role/delegation paths reach broker | Extend optional runner memory policy and protect its command inputs. Preserve existing roles and enrollment authority. |
| `build_p4.py`, installer | Offline core wheels, installed-source verification, optional MCP | Include operational modules and host plugin in the normal kit, with an opt-in configuration guide. |

Actual command names are `knowledge-init`, `knowledge-candidates-update`, and
`knowledge-candidates-push`. The latter prepares/applies architectural candidates.
There is no `knowledge-candidates-append` or `knowledge-update` command to extend;
no deprecated aliases will be restored.

Cold-session gap: the baseline Knowledge CLI accepts no instruction ingress, its
MCP has only architectural context/get tools, and broker recipe/patch execution
does not query operational memory. A teaching sentence in a departed transcript
therefore has no durable record that a fresh process could retrieve. This is a
source/API reproduction, not a measured local-model behavioral trial.

Host discovery: neither `opencode` nor `ollama` is installed and no local model
service was found. The existing integration targets OpenCode v2 MCP configuration.
Separately inspected npm `@opencode-ai/plugin` **1.19.6** declares `chat.message`
(UserMessage plus Parts), `tool.execute.before`, and system-transform hooks; its
SDK declares `tui.showToast`. A plugin for this published hook contract is an
opt-in adapter, **not proof of compatibility with the v2 host in prior docs**.
Real OpenCode/local-model acceptance remains BLOCKED until tested on that host.
The narrow supported execution route is enrolled Harness tasks; arbitrary native
host shell/edit tools cannot inherit Harness's owned-process guarantees.

Docker daemon 29.9.2 and Node/npm are available. No user Kafka binding or Kafka
image was supplied. Tests must create explicitly named isolated fixtures, never
discover/start a user's service by guessing a container name.

The final ingress also uses `normalizer.py` (loopback-only semantic classification),
`semantic_ingress.py` (quoted resource/scope binding, incomplete intent and CAS),
`procedure_templates.py` (independently permitted typed Docker/Kafka factory), and
`text_format.py` (pure byte codec and explicit current-session exceptions).
The model returns catalog selections/data, never executable argv. An unsupported
condition blocks before effects rather than being dropped. Real model quality
remains unqualified; HTTP protocol doubles are labelled separately from actual
Python processes, durable SQLite commits, broker effects and Docker protocol tests.
