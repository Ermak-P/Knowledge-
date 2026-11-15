# Opt-in OpenCode v2 companion

The kit targets documented OpenCode v2 project config `mcp.servers` (local server command arrays, optional disabled field), not the historical v1 enabled layout. Authoritative source/provenance is in the review references. Actual OpenCode version/config smoke is separate; if no executable exists, it remains NOT_RUN.

`harness-host preview --root ROOT --task tasks/approved.json` produces a merge preview. Exact approved `apply --input PREVIEW.json --approve FINGERPRINT` preserves current project opencode.json bytes/backups and adds knowledge_local plus harness_companion. JSONC or conflicting/v1 layouts refuse with manual merge guidance; no global config is touched. `doctor` checks root/runtime/config/task identities and optional MCP availability. `remove-preview` plus exact apply restores original bytes, refusing intervening host changes.

Knowledge MCP retains bounded context/current and explicit history. Companion MCP offers doctor/status and execution only by enrolled task name. Its hidden project config binds the task payload digest, so a model cannot replace a source task JSON with broader scope and silently run it. Normal Harness runtime roles/tools/final gates remain authority. There is no arbitrary shell/MCP proxy or native OpenCode subagent permission claim. Optional MCP requires the pinned online extra; offline core remains independent.

Tests launch the real configured stdio server commands from an isolated installation and exercise MCP tools against the active root. Missing optional specialists and real model/host integration are explicit. A project-local wrapper cannot certify the host's own plugins/global policy; inspect active host precedence before adoption. No private MCP service is installed.
