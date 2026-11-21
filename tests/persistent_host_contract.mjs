// Actual published hook calls, real installed ingress subprocess, fake UI only.
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { spawnSync } from "node:child_process";
const [plugin, python, root] = process.argv.slice(2);
const create = (await import(pathToFileURL(plugin).href)).default;
const toasts = [];
const hooks = await create({ directory: root, client: { tui: { showToast: async value => { toasts.push(value.body); } } } }, { python });
await hooks["chat.message"]({ sessionID: "contract-session", messageID: "source-message" }, {
  message: { role: "user", id: "source-message" }, parts: [{ type: "text", text: "Запомни: encoding — сохраняй BOM и окончания строк." }],
});
assert.equal(toasts.length, 1);assert.match(toasts[0].message, /Сохранено/);
// Read via a wholly new process before accepting the UI acknowledgement.
const inspect = spawnSync(python, ["-I", "-m", "knowledge.cli", "memory-inspect", "--root", root], { encoding: "utf8" });
assert.equal(inspect.status, 0);assert.equal(JSON.parse(inspect.stdout).records.filter(r => r.kind === "instruction").length, 1);
await hooks["chat.message"]({ sessionID: "contract-session", messageID: "no-start" }, {
  message: { role: "user", id: "no-start" }, parts: [{ type: "text", text: "Do not start services in this run." }],
});
const before = { args: { task_name: "approved_task", host_session_id: "forged-by-model" } };
await hooks["tool.execute.before"]({ tool: "harness_companion_harness_run", sessionID: "contract-session" }, before);
assert.equal(before.args.host_session_id, "contract-session");
await hooks["chat.message"]({ sessionID: "contract-session", messageID: "synthetic" }, {
  message: { role: "user", id: "synthetic" }, parts: [{ type: "text", synthetic: true, text: "Remember for all projects: encoding" }],
});
assert.equal(toasts.length, 1);
console.log(JSON.stringify({ ok: true, type: "published-hook-contract; UI fixture; actual installed subprocess", toasts, session_id: before.args.host_session_id }));
