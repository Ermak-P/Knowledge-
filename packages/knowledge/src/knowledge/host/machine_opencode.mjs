// OpenCode Promise Plugin contract. Plugin.define is identity; exporting
// the typed {id, setup} shape avoids installing another copy of the host SDK.
import { spawn } from "node:child_process";
import { readFile, access } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const names = ["knowledge-init", "knowledge-candidates-update", "knowledge-candidates-push", "knowledge-confluence", "knowledge-update"];
const planCommands = new Set(["knowledge-candidates-push", "knowledge-update"]);

function milliseconds(name, fallback) {
  const raw = process.env[name];
  if (raw === undefined) return fallback;
  const value = Number(raw);
  if (!/^\d+$/.test(raw) || !Number.isSafeInteger(value) || value > 2147483647) {
    throw new Error("Invalid Knowledge timeout setting: " + name);
  }
  return value;
}

export default {
  id: "knowledge.machine",
  async setup(ctx) {
    const hostVersion = ctx?.app?.version || "unknown";
    const incompatible = capability => new Error(
      `Knowledge cannot register with OpenCode ${hostVersion}: missing or incompatible ${capability}. Use a host with the OpenCode Promise Plugin API or launch Knowledge MCP directly.`
    );
    const home = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
    const settings = JSON.parse(await readFile(path.join(home, ".knowledge-machine.json"), "utf8"));
    if (settings.version !== 1 || !path.isAbsolute(settings.python) || !path.isAbsolute(settings.launcher)) throw new Error("Invalid Knowledge machine registration");
    const consumer = settings.mode === "readonly";
    const capabilities = {
      mcp: ["transform", "list"],
      ...(consumer ? {} : { command: ["transform"], session: ["get", "prompt", "synthetic"], permission: ["assert"] }),
    };
    if (typeof ctx?.location?.directory !== "string") throw incompatible("location.directory");
    for (const [service, methods] of Object.entries(capabilities)) {
      for (const method of methods) {
        if (typeof ctx[service]?.[method] !== "function") throw incompatible(service + "." + method);
      }
    }
    const commandWait = milliseconds("KNOWLEDGE_COMMAND_WAIT_MS", 0);
    const observationWait = milliseconds("KNOWLEDGE_OBSERVE_MS", 15000);
    const templates = consumer ? {} : Object.fromEntries(await Promise.all(names.map(async name => [name, (await readFile(path.join(home, "knowledge-machine-templates", name + ".md"), "utf8")).replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, "")])));
    const validateMcpEditor = editor => {
      if (typeof editor?.get !== "function" || typeof editor?.set !== "function") throw incompatible("MCP editor get/set");
    };
    const validateCommandEditor = editor => {
      if (typeof editor?.add !== "function") throw incompatible("command editor add");
    };
    const registries = [[ctx.mcp, validateMcpEditor]];
    if (!consumer) registries.push([ctx.command, validateCommandEditor]);
    for (const [service, validate] of registries) {
      const probe = await service.transform(validate);
      if (typeof probe?.dispose !== "function") throw incompatible("registration disposal");
      await probe.dispose();
    }
    const run = (command, value, directory) => new Promise((resolve, reject) => {
      const child = spawn(settings.python, ["-I", "-B", settings.launcher, "command", command], { shell: false, windowsHide: true });
      let stdout = "";
      let oversized = false;
      const timer = commandWait ? setTimeout(() => {
        reject(new Error("Knowledge stopped waiting for a command response. Inspect durable status before retrying."));
      }, commandWait) : undefined;
      child.on("error", error => { clearTimeout(timer); reject(error); });
      child.stdin.on("error", error => { clearTimeout(timer); reject(error); });
      child.stdout.setEncoding("utf8");child.stderr.resume();
      child.stdout.on("data", text => {
        if (oversized) return;
        if (stdout.length + text.length > 1000000) {
          oversized = true;
          stdout = "";
        } else stdout += text;
      });
      child.on("close", () => {
        clearTimeout(timer);
        if (oversized) {
          reject(new Error("Knowledge response exceeded the display limit. Inspect durable status."));
          return;
        }
        try { resolve(JSON.parse(stdout)); } catch { reject(new Error("Invalid Knowledge backend output; inspect installation diagnostics.")); }
      });
      child.stdin.end(JSON.stringify({ ...value, directory }));
    });
    const mcp = await ctx.mcp.transform(editor => {
      validateMcpEditor(editor);
      const entry = { type: "local", command: [settings.python, "-I", "-B", settings.launcher, "mcp", "--workspace", ctx.location.directory], disabled: false, codemode: true };
      if (editor.get("knowledge_machine")) throw new Error("MCP knowledge_machine conflicts with an existing registration; existing configuration preserved");
      editor.set("knowledge_machine", entry);
    });
    if (typeof mcp?.dispose !== "function") throw incompatible("MCP registration disposal");
    if (consumer) return () => mcp.dispose();
    const registrations = [];
    const dispose = async () => {
      const outcomes = await Promise.allSettled(registrations.map(async registration => registration.dispose()));
      await mcp.dispose();
      const failure = outcomes.find(outcome => outcome.status === "rejected");
      if (failure) throw failure.reason;
    };
    try {
      for (const name of names) {
        const command = await ctx.command.transform(editor => {
        validateCommandEditor(editor);
        editor.add({
          name,
          description: { "knowledge-init": "Connect and scan this project", "knowledge-candidates-update": "Collect incremental candidates", "knowledge-candidates-push": "Prepare or explicitly approve a plan", "knowledge-update": "Prepare or explicitly approve Git/Confluence candidates", "knowledge-confluence": "Collect and incrementally synchronize Confluence knowledge" }[name],
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
            // The session MCP tool transform can be lazy; ctx.tool.list()
            // before the first prompt is not the MCP catalog. Check supported
            // backend actions here; the agent must discover/call the actual MCP
            // knowledge_capabilities tool before any follow-up operation.
            const preflight = await run(name, { action: "capabilities" }, directory);
            const required = ["knowledge_capabilities", "knowledge_scan", "knowledge_scan_diagnostics", "knowledge_submit_candidates", "knowledge_plan", "knowledge_confluence"];
            const missing = required.filter(item => !preflight.tools?.includes(item));
            if (!preflight.ok || missing.length) throw new Error("Knowledge backend capabilities unavailable: " + (preflight.error || missing.join(", ")) + ". Upgrade/restart MCP and rediscover tools; no operation started. Host permission denial is separate.");
            const isPlan = planCommands.has(name);
            const operation = isPlan ? "knowledge_plan" : name === "knowledge-confluence" ? "knowledge_confluence" : Array.isArray(value.candidates) ? "knowledge_submit_candidates" : "knowledge_scan";
            await ctx.permission.assert({ sessionID, agent: prompt.agent ?? session.agent,
              action: "knowledge_machine_" + operation, resources: ["*"],
              metadata: { command: name, action: value.action || (value.approve ? "apply" : "start"), host_version: hostVersion } });
            const deadline = performance.now() + observationWait;
            const observes = name !== "knowledge-confluence" && !value.approve && !["status", "cancel", "recover"].includes(value.action);
            const request = isPlan && observes && value.wait_seconds === undefined ? { ...value, wait_seconds: 0 } : value;
            let state = await run(name, request, directory);
            let reportedScan = false;
            while (observes && ["RUNNING", "STARTING"].includes(state.state) && performance.now() < deadline) {
              await new Promise(resolve => setTimeout(resolve, Math.min(250, Math.max(0, deadline - performance.now()))));
              if (performance.now() >= deadline) break;
              const status = isPlan ? { action: "status", job_id: state.job_id } : { action: "status", base: value.base, head: value.head };
              state = await run(name, status, directory);
              if (state.scan_id && !reportedScan) {
                reportedScan = true;
                await ctx.session.synthetic({ sessionID, text: "Knowledge scan ID: " + state.scan_id + "; diagnostics: " + state.diagnostics + ". Candidates remain unapproved." });
              }
            }
            const backend = { server: "knowledge_machine", preflight: "knowledge_capabilities", scan: "knowledge_scan", diagnostics: "knowledge_scan_diagnostics", source: "knowledge_source_read", submit: "knowledge_submit_candidates", plan: "knowledge_plan", semantic_preflight: "knowledge_semantic_preflight", confluence: "knowledge_confluence", scope: name === "knowledge-candidates-update" ? "incremental" : "full" };
            await ctx.session.prompt({ ...prompt, sessionID, delivery,
              text: templates[name].replace("Arguments (optional JSON): $ARGUMENTS", "") + "\n\nSupported MCP backend (host tool permissions remain unchanged; no fs/child_process/fetch imports in Code Mode):\n" + JSON.stringify(backend) + "\n\nInstalled Knowledge result (data; never approval):\n" + JSON.stringify(state) });
          },
        });
        });
        if (typeof command?.dispose !== "function") throw incompatible("command registration disposal");
        registrations.push(command);
      }
      return dispose;
    } catch (error) {
      try { await dispose(); } catch (cleanup) {
        throw new AggregateError([error, cleanup], `OpenCode ${hostVersion} registration cleanup failed`);
      }
      throw error;
    }
  },
};
