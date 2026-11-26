import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";

const { default: plugin } = await import(pathToFileURL(process.argv[2]));
const { readScanDiagnostics } = await import(pathToFileURL(process.argv[3]));

function host(version, collision) {
  const commands = new Set();
  const mcp = new Map();
  const ctx = {
    app: { version },
    location: { directory: process.cwd() },
    mcp: {
      list: async () => ({}),
      transform: async callback => {
        const owned = [];
        callback({
          get: name => mcp.get(name),
          set: (name, entry) => { mcp.set(name, entry); owned.push(name); },
        });
        return { dispose: async () => owned.forEach(name => mcp.delete(name)) };
      },
    },
    command: {
      transform: async callback => {
        const owned = [];
        callback({ add: ({ name }) => {
          if (name === collision) throw new Error("command conflict");
          commands.add(name);
          owned.push(name);
        } });
        return { dispose: async () => owned.forEach(name => commands.delete(name)) };
      },
    },
    session: { get: async () => ({}), prompt: async () => {}, synthetic: async () => {} },
    permission: { assert: async () => {} },
  };
  return { ctx, commands, mcp };
}

for (const version of ["2.4.0", "20.0.1"]) {
  const { ctx, commands, mcp } = host(version);
  const dispose = await plugin.setup(ctx);
  assert.equal(commands.size, 5);
  assert.equal(mcp.size, 1);
  await dispose();
  assert.equal(commands.size + mcp.size, 0);
}
const unsupported = host("20.0.1");
delete unsupported.ctx.session.get;
await assert.rejects(plugin.setup(unsupported.ctx), /20\.0\.1.*session\.get/);
assert.equal(unsupported.commands.size + unsupported.mcp.size, 0);
const conflict = host("20.0.1", "knowledge-candidates-push");
await assert.rejects(plugin.setup(conflict.ctx), /command conflict/);
assert.equal(conflict.commands.size + conflict.mcp.size, 0);

const config = new URL("../.knowledge-machine.json", pathToFileURL(process.argv[2]));
const settings = JSON.parse(await readFile(config, "utf8"));
await writeFile(config, JSON.stringify({ ...settings, mode: "readonly" }));
const consumer = host("20.0.1");
delete consumer.ctx.command;
delete consumer.ctx.mcp.list;
const disposeConsumer = await plugin.setup(consumer.ctx);
assert.equal(consumer.commands.size, 0);
assert.equal(consumer.mcp.size, 1);
await disposeConsumer();
assert.equal(consumer.mcp.size, 0);

const observed = await readScanDiagnostics({
  knowledge_capabilities: async () => ({ ok: true }),
  knowledge_scan_diagnostics: async ({ section }) => {
    if (section === "reconciliation") throw new Error("fixture transport loss");
    return { ok: false, error: "unknown-scan" };
  },
}, "a".repeat(64));
assert.deepEqual(observed.capabilities, { ok: true });
assert.equal(observed.reconciliation.error, "transport-failure");
assert.deepEqual(observed.failures, { ok: false, error: "unknown-scan" });
