import { pathToFileURL } from "node:url";
const [asset, root, previous] = process.argv.slice(2);
const plugin = (await import(pathToFileURL(asset))).default;
const invoke = async (hook, args) => {
  const output = { parts: [] };
  await hook["command.execute.before"]({ command: "update-by-CR", sessionID: "same-native-chat", arguments: args }, output);
  return JSON.parse(output.parts[0].text.split("Knowledge /update-by-CR durable workflow: ")[1].split(". Reuse links")[0]);
};
let hook = await plugin({ directory: root });
const second = await invoke(hook, "https://github.com/synthetic/project/issues/10 https://github.com/synthetic/project/pull/11");
if (second.session === previous) throw new Error("Second CR reused the historical workflow");
if ((await invoke(hook, "")).session !== second.session) throw new Error("No-argument invocation lost the active workflow");
hook = await plugin({ directory: root });
if ((await invoke(hook, "")).session !== second.session) throw new Error("Plugin restart lost the active workflow");
if ((await invoke(hook, "--resume " + second.session)).session !== second.session) throw new Error("Explicit resume conflicted");
console.log(JSON.stringify({ profile: "native-hook-sequential-cr-contract", second: second.session, restart_resume: true }));
