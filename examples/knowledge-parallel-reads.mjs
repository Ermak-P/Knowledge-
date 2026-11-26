export async function readScanDiagnostics(knowledge, scanId) {
  const [capabilities, reconciliation, failures] = await Promise.allSettled([
    knowledge.knowledge_capabilities({}),
    knowledge.knowledge_scan_diagnostics({ section: "reconciliation", scan_id: scanId, limit: 5 }),
    knowledge.knowledge_scan_diagnostics({ section: "failures", scan_id: scanId, limit: 5 }),
  ]);
  const format = outcome => outcome.status === "fulfilled"
    ? outcome.value
    : { ok: false, error: "transport-failure", message: String(outcome.reason) };
  return {
    capabilities: format(capabilities),
    reconciliation: format(reconciliation),
    failures: format(failures),
  };
}
