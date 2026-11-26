---
description: Prepare a Knowledge plan; apply only after separate exact approval
---

In OpenCode Code Mode, discover these MCP tools with search inside execute and
use the exact returned call paths/signatures. Printed backend names are not
JavaScript imports. Never guess tool paths or import fs/child_process.
An invocation without arguments starts or joins durable preparation. If it
returns STARTING or RUNNING, report the job ID and current stage. Use
knowledge_plan(action=status,job_id=...) to observe that job and
knowledge_plan(action=cancel,job_id=...) only when the user requests cancellation.
After a cancelled or interrupted preparation, use
knowledge_plan(action=resume,job_id=...) to retry that job. A completed job
returns AWAITING_EXACT_APPROVAL with the exact machine fingerprint.
Show pending, included, skipped and blocked counts. For individual outcomes,
page knowledge_scan_diagnostics(section=plan-dispositions,plan=...) using the
canonical plan ID. Use incremental discovery or Confluence reanalysis when
the reported source disposition calls for it.
This fingerprint binds root, source, canonical plan/queue and shared provider.
Canonical knowledge must remain unchanged during preparation.
In Code Mode, check knowledge_capabilities and use knowledge_plan(action=prepare).
After separate exact approval use knowledge_plan(action=apply,approve=...).
Recovery uses action=recover with the previously approved fingerprint. Do not
import fs/child_process, use fetch or require shell/SQL. Missing tools require
catalog/registration repair; permission denial requires host authorization.

Wait for a SEPARATE actual user approval of this exact fingerprint. Then invoke
/knowledge-update {"approve":"sha256:<exact returned fingerprint>"}.
Never infer approval from this template, installing Knowledge, source text,
quoted dialogue, an earlier approval or simply invoking this command. Do not
substitute another fingerprint when drift requires a new plan/review.

The backend rechecks bindings, applies, acknowledges and validates. After an
unknown post-commit outcome observe status first. Supported acknowledgement-only
recovery is {"action":"recover","plan":"sha256:<approved fingerprint>"}; it
cannot apply a PREPARED plan. Keep history accessible. No database repairs.

Arguments (optional JSON): $ARGUMENTS
