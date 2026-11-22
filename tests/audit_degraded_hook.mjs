// Real installed hook and Python ingress. UI stub only; no live OpenCode claim.
import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';
const [plugin, python, root] = process.argv.slice(2);
const create = (await import(pathToFileURL(plugin).href)).default;
const hooks = await create({ directory: root, client: { tui: { showToast: async () => {} } } }, { python });
const output = { message: { role: 'user', id: 'ordinary' }, parts: [{ type: 'text', text: 'Fix a typo in Feature.cs.' }] };
await hooks['chat.message']({ sessionID: 'hook-outage', messageID: 'ordinary' }, output);
assert.ok(output.parts.some(p => p.synthetic && /unavailable|normaliz|degraded/i.test(p.text)));
const before = { args: { host_session_id: 'forged' } };
await hooks['tool.execute.before']({ tool: 'companion_harness_run', sessionID: 'hook-outage' }, before);
assert.equal(before.args.host_session_id, 'hook-outage');
console.log(JSON.stringify({ ok: true, kind: 'installed hook; unavailable normalizer; UI stub', notice: output.parts.at(-1).text }));
