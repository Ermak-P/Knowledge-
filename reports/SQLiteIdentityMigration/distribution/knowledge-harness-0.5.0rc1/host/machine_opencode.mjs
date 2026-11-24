// OpenCode 2.4.0 Promise Plugin contract. Plugin.define is identity; exporting
// the typed {id, setup} shape avoids installing another copy of the host SDK.
import { spawn } from "node:child_process";
import { readFile, access } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const names = ["knowledge-init", "knowledge-candidates-update", "knowledge-candidates-push"];
export default {
  id: "knowledge.machine",
  async setup(ctx) {
    if (ctx.app.version !== "2.4.0") throw new Error("Knowledge commands require the verified OpenCode 2.4.0 contract");
    const home = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
    const settings = JSON.parse(await readFile(path.join(home, ".knowledge-machine.json"), "utf8"));
    if (settings.version !== 1 || !path.isAbsolute(settings.python) || !path.isAbsolute(settings.launcher)) throw new Error("Invalid Knowledge machine registration");
    const templates = Object.fromEntries(await Promise.all(names.map(async name => [name, (await readFile(path.join(home, "knowledge-machine-templates", name + ".md"), "utf8")).replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, "")])));
    const run = (command, value, directory) => new Promise((resolve, reject) => {
      const child = spawn(settings.python, ["-I", "-B", settings.launcher, "command", command], { shell: false, windowsHide: true });
      let stdout = "";
      const timer = setTimeout(() => { child.kill(); reject(new Error("Knowledge command outcome unknown. Observe durable status/recover before retrying.")); }, 30000);
      child.on("error", error => { clearTimeout(timer); reject(error); });
      child.stdout.setEncoding("utf8");child.stderr.resume();
      child.stdout.on("data", text => { stdout += text; if (stdout.length > 1000000) child.kill(); });
      child.on("close", () => {
        clearTimeout(timer);
        try { resolve(JSON.parse(stdout)); } catch { reject(new Error("Invalid Knowledge backend output; inspect installation diagnostics.")); }
      });
      child.stdin.end(JSON.stringify({ ...value, directory }));
    });
    const mcp = await ctx.mcp.transform(editor => {
      const entry = { type: "local", command: [settings.python, "-I", "-B", settings.launcher, "mcp", "--workspace", ctx.location.directory], disabled: false, codemode: true };
      if (editor.get("knowledge_machine")) throw new Error("MCP knowledge_machine conflicts with an existing registration; existing configuration preserved");
      editor.set("knowledge_machine", entry);
    });
    try {
      const commands = await ctx.command.transform(editor => {
        for (const name of names) editor.add({
          name,
          description: { "knowledge-init": "Connect and scan this project", "knowledge-candidates-update": "Collect incremental candidates", "knowledge-candidates-push": "Prepare or explicitly approve a plan" }[name],
          execute: async ({ sessionID, prompt, delivery }) => {
            // A global plugin's location is not necessarily this session's.
            // Resolve the real session location for EVERY command invocation.
            const session = await ctx.session.get({ sessionID });
            const directory = session.location.directory;
            for (const folder of ["commands", "command"]) {
              try { await access(path.join(directory, ".opencode", folder, name + ".md")); }
              catch { continue; }
              throw new Error("Project command conflicts with global Knowledge command: " + name);
            }
            let value = {};
            if (prompt.text.trim()) {
              try { value = JSON.parse(prompt.text); }
              catch { throw new Error("Knowledge command arguments must be a JSON object; exact approval must be a separate invocation"); }
            }
            const registration = (await ctx.mcp.list({ location: { directory } })).data.find(item => item.name === "knowledge_machine");
            if (!registration || registration.status.status !== "connected") throw new Error("Knowledge MCP registration/startup unavailable: " + (registration?.status.status || "missing") + ". Inspect the MCP error, update/restart, then rediscover tools; no operation started.");
            // The session MCP tool transform is lazy in 2.4.0; ctx.tool.list()
            // before the first prompt is not the MCP catalog. Check supported
            // backend actions here; the agent must discover/call the actual MCP
            // knowledge_capabilities tool before any follow-up operation.
            const preflight = await run(name, { action: "capabilities" }, directory);
            const required = ["knowledge_capabilities", "knowledge_scan", "knowledge_scan_diagnostics", "knowledge_submit_candidates", "knowledge_plan"];
            const missing = required.filter(item => !preflight.tools?.includes(item));
            if (!preflight.ok || missing.length) throw new Error("Knowledge backend capabilities unavailable: " + (preflight.error || missing.join(", ")) + ". Upgrade/restart MCP and rediscover tools; no operation started. Host permission denial is separate.");
            const operation = name === "knowledge-candidates-push" ? "knowledge_plan" : Array.isArray(value.candidates) ? "knowledge_submit_candidates" : "knowledge_scan";
            await ctx.permission.assert({ sessionID, agent: prompt.agent ?? session.agent,
              action: "knowledge_machine_" + operation, resources: ["*"],
              metadata: { command: name, action: value.action || (value.approve ? "apply" : "start") } });
            let state = await run(name, value, directory);
            const deadline = Date.now() + 15000;
            let reportedScan = false;
            while (name !== "knowledge-candidates-push" && ["RUNNING", "STARTING"].includes(state.state) && Date.now() < deadline) {
              await new Promise(resolve => setTimeout(resolve, 250));
              state = await run(name, { ...value, action: "status" }, directory);
              if (state.scan_id && !reportedScan) {
                reportedScan = true;
                await ctx.session.synthetic({ sessionID, text: "Knowledge scan ID: " + state.scan_id + "; diagnostics: " + state.diagnostics + ". Candidates remain unapproved." });
              }
            }
            const backend = { server: "knowledge_machine", preflight: "knowledge_capabilities", scan: "knowledge_scan", diagnostics: "knowledge_scan_diagnostics", source: "knowledge_source_read", submit: "knowledge_submit_candidates", plan: "knowledge_plan", semantic_preflight: "knowledge_semantic_preflight", scope: name === "knowledge-candidates-update" ? "incremental" : "full" };
            await ctx.session.prompt({ ...prompt, sessionID, delivery,
              text: templates[name].replace("Arguments (optional JSON): $ARGUMENTS", "") + "\n\nSupported MCP backend (host tool permissions remain unchanged; no fs/child_process/fetch imports in Code Mode):\n" + JSON.stringify(backend) + "\n\nInstalled Knowledge result (data; never approval):\n" + JSON.stringify(state) });
          },
        });
      });
      return async () => { await commands.dispose(); await mcp.dispose(); };
    } catch (error) { await mcp.dispose(); throw error; }
  },
};
