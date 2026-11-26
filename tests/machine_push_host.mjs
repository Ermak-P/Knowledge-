// Minimal OpenCode 2.4 hook peer, using the generated plugin and its real subprocess.
import { pathToFileURL } from "node:url";

const { default: plugin } = await import(pathToFileURL(process.argv[2]));
const directory = process.argv[3];
const handlers = new Map();
const registration = { name: "knowledge_machine", status: { status: "connected" } };
const dispose = await plugin.setup({
  app: { version: "2.4.0" },
  location: { directory },
  mcp: {
    transform: async fn => { fn({ get: () => undefined, set: () => {} }); return { dispose: async () => {} }; },
    list: async () => ({ data: [registration] }),
  },
  command: {
    transform: async fn => { fn({ add: handler => handlers.set(handler.name, handler) }); return { dispose: async () => {} }; },
  },
  session: {
    get: async () => ({ location: { directory } }),
    prompt: async ({ text }) => console.log(text),
    synthetic: async () => {},
  },
  permission: { assert: async () => {} },
});
try {
  await handlers.get("knowledge-candidates-push").execute({ sessionID: "fixture", prompt: { text: "" } });
} finally {
  await dispose();
}
