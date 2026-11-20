// Opt-in published @opencode-ai/plugin 1.19.6 hook contract. No remote inference.
// Existing v2 MCP configuration alone does NOT establish plugin compatibility.
import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { randomUUID } from "node:crypto";

export default async function KnowledgeInstructions({ directory, client }, options = {}) {
  const settings = options.python ? options : JSON.parse(await readFile(path.join(directory, ".knowledge-host.json"), "utf8"));
  if (!path.isAbsolute(settings.python)) throw new Error("Knowledge requires an absolute installed Python path");
  const toast = async body => { try { await client.tui.showToast({ body }); } catch { /* CLI may have no TUI; the durable receipt remains in parts. */ } };
  const call = (module, args, value) => new Promise((resolve, reject) => {
    const proc = spawn(settings.python, ["-I", "-m", module, ...args, "--root", directory], { shell: false, windowsHide: true });
    let out = "", err = "";
    const timer = setTimeout(() => { proc.kill(); reject(new Error("Knowledge ingress deadline; save outcome unknown, inspect before retry")); }, 15000);
    proc.stdout.on("data", b => { out += b; if (out.length > 65536) proc.kill(); });
    proc.stderr.on("data", b => { if (err.length < 2000) err += b; });
    proc.on("error", e => { clearTimeout(timer); reject(e); });
    proc.on("close", code => {
      clearTimeout(timer);
      try { const r = JSON.parse(out); if (code || !r.ok) reject(new Error(r.error || "Knowledge failed")); else resolve(r); }
      catch (e) { reject(e); }
    });
    proc.stdin.end(JSON.stringify(value));
  });
  return {
    "chat.message": async (input, output) => {
      if (output.message.role !== "user") return;
      const text = output.parts.filter(p => p.type === "text" && !p.synthetic && !p.ignored).map(p => p.text).join("\n");
      const id = input.messageID || output.message.id;
      if (!id) throw new Error("Knowledge cannot acknowledge a message without a durable source ID");
      try {
        const r = settings.backend === "knowledge"
          ? await call("knowledge.cli", ["memory-ingest"], { text, message_id: input.sessionID + "/" + id, policy: settings.policy || {} })
          : await call("harness.host_ingress", [], { text, message_id: id, session_id: input.sessionID });
        if (r.saved) {
          const detail = r.status === "unbound" ? (r.question ? " " + r.question : " Привязка ещё не задана.") : ` Триггер: ${r.trigger.tool}/${r.trigger.name}; восстановление: ${r.recovery_authorized}.`;
          // CLI hosts may have no visible toast. Supply a receipt to the current
          // reply too; synthetic parts are excluded from subsequent capture.
          output.parts.push({ type: "text", id: "prt_" + randomUUID().replaceAll("-", ""), sessionID: input.sessionID,
            messageID: output.message.id, synthetic: true,
            text: "Knowledge durable receipt (external memory, not model training): " + JSON.stringify({ id: r.id, revision: r.revision,
              scope: r.scope, status: r.status, behavior: r.behavior, trigger: r.trigger, recovery_authorized: r.recovery_authorized,
              question: r.question }) + ". Report this saved scope and behavior briefly; configured does not mean technically verified." });
          await toast({ title: "Knowledge", message: r.message + detail, variant: "success", duration: 12000 });
        }
      } catch (e) {
        await toast({ title: "Knowledge: сохранение не подтверждено", message: String(e), variant: "error" });
        throw e;
      }
    },
    "tool.execute.before": async (input, output) => {
      // The model cannot drop a trusted session restriction from an enrolled run.
      if (settings.backend !== "knowledge" && input.tool.endsWith("harness_run")) output.args.host_session_id = input.sessionID;
    },
  };
}
