"""Only a completed, identity-bound P1 run can produce the review archive."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from p1_evidence import ROOT,OUT,validate_current,save,sha

MAPPINGS=[
 ('Accepted baseline, standalone packaging and P0 regressions','packaging','tests/test_core.py; test_corrections.py; test_mcp.py; check_packaging.py'),
 ('Generic real-source discovery: independent anchors, categories and areas','evaluation','evaluate_p1.py: EXPECTATIONS, observation/source checks'),
 ('Truthful lexical versus semantic coverage and blocked/incomplete scan refusal','product-tests','test_scan_resume_source_drift_and_idempotence; test_incomplete_blocked_and_changed_evidence_refuse_absence'),
 ('Killed process scan checkpoint recovery and stale source refusal','product-tests','test_scan_interruption_preserves_completed_checkpoint; test_scan_resume_source_drift_and_idempotence'),
 ('Verified range, rename/add/change/delete, full consumer reanalysis and deduplication','product-tests','test_incremental_rename_add_delete_dirty_and_range; test_removed_component_complete_pipeline; test_rejected_proposal_remains_rejected_on_new_snapshot'),
 ('Versioned mixed add/update/retire/supersede and relationship operations','product-tests','test_update_old_ack_supersede_and_history; test_mixed_add_update_retire_ack_crash_and_competing_approval; HistoricalGraphTests'),
 ('Preview is noncanonical; exact approval and stale source/revision refusal','product-tests','test_stale_source_expected_approval_and_conflicting_ops; test_stale_and_wrong_approval (P0)'),
 ('Nonempty P0/migrated store upgrade, backup, interrupted upgrade and prepared approval compatibility','product-tests','test_nonempty_upgrade_preserves_pending_and_old_receipts; test_prepared_p0_approval_survives_upgrade; test_lock_contention_and_upgrade_crash; UpgradeLegacyTests'),
 ('Immutable payload/revision history and old approval/ack retries after updates','product-tests','test_update_old_ack_supersede_and_history; test_real_crash_mixed_batch_and_pending_ack'),
 ('Full removed-component pipeline and dependent graph closure','product-tests','test_removed_component_complete_pipeline; test_graph_dependent_retirement_requires_reviewed_closure; HistoricalGraphTests'),
 ('Historical/external/independent facts and insufficient evidence cannot auto-retire','product-tests','test_freshness_no_false_retirement_and_no_promotion; test_incomplete_blocked_and_changed_evidence_refuse_absence'),
 ('Unrelated anchor edits, drift/missing/rename and changed confidence separation','product-tests','test_freshness_no_false_retirement_and_no_promotion; test_incremental_rename_add_delete_dirty_and_range'),
 ('Current/history graph consistency and trusted retrieval filtering','product-tests','HistoricalGraphTests; P1StdioTests; test_update_old_ack_supersede_and_history'),
 ('Persisted reject/defer payload/reason; refused unchanged proposals remain deduplicated','product-tests','test_disposition_and_valid_batch; test_rejected_proposal_remains_rejected_on_new_snapshot'),
 ('Actual competing processes and killed mixed apply/ack/upgrade transactions','product-tests','test_mixed_add_update_retire_ack_crash_and_competing_approval; test_real_crash_mixed_batch_and_pending_ack; accepted test_crash_boundaries'),
 ('Functional CLI adapters, real stdio, bounded UTF-8, shared Harness and isolation','product-tests','P1StdioTests; test_scan_resume_source_drift_and_idempotence; accepted McpTests and ErrorContract'),
 ('Pinned uncurated source questions, controlled changes and tracked-source immutability','evaluation','evaluate_p1.py; discovery.json; questions.json; controlled.json; source-immutability.json'),
 ('Current-run source/artifact identity and negative evidence gate tests','product-tests','test_p1_evidence.py; p1_evidence.validate_current'),
 ('Fresh 43 accepted regressions plus P1 tests, standalone wheels, real stdio and 49/49 app tests','evaluation','verify_p1.py; benchmark.json; current product-tests.log and packaging.log'),
 ('Source/test/contracts/run packet with verified members and external SHA-256','evaluation','make_review_p1.py; REVIEW-INVENTORY.json; packet-check.json'),
]


def main():
    v=validate_current()
    if '--validate-only' in sys.argv:return
    directory=OUT/'runs'/v['run_id'];test_count=v['checks']['product-tests']['test_count']
    discovery=json.loads((directory/'discovery.json').read_text());questions=json.loads((directory/'questions.json').read_text());benchmark=json.loads((directory/'benchmark.json').read_text())
    assert len(questions['questions'])==5 and all(q['status']=='PASS' for q in questions['questions'])
    assert all(int(benchmark[phase]['passed'])==49 for phase in ('before','after'))
    rev=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
    subprocess.run(['git','merge-base','--is-ancestor','a3c7ac7afd7cff6137b916832cf40019ca8b8c87','HEAD'],cwd=ROOT,check=True)
    rows=[dict(id=f'P1-A{i:02}',status=v['checks'][check]['status'],run_id=v['run_id'],source_identity=v['source_identity'],command='.venv/bin/python scripts/verify_p1.py',checks=commands,evidence=str((directory/(check+'.log')).relative_to(ROOT)),explanation=description) for i,(description,check,commands) in enumerate(MAPPINGS,1)]
    save(OUT/'ACCEPTANCE.json',dict(run_id=v['run_id'],source_identity=v['source_identity'],conditions=rows,optional=[dict(name=n,status='NOT_RUN') for n in ('native Windows/NTFS','live OpenCode/model/tool-provider host','browser/SQL Server/Aspire deployment')]))
    save(OUT/'SOURCE-REVISION.json',dict(baseline='a3c7ac7afd7cff6137b916832cf40019ca8b8c87',head=rev,branch=branch,delivery='uncommitted working tree; no automatic commit/push',run_id=v['run_id'],source_identity=v['source_identity'],files=v['source_files']))
    scan=discovery['scan'];categories={k:sum(o['category']==k for o in scan['observations']) for k in sorted({o['category'] for o in scan['observations']})}
    def report(name,text):(OUT/name).write_text(text,encoding='utf-8')
    common=f'Run `{v["run_id"]}`; source `{v["source_identity"]}`. Raw evidence: `runs/{v["run_id"]}/`.\n'
    report('P1-REPORT.md',f'''# P1 implementation submitted for independent review

{common}
Branch `{branch}`; baseline/HEAD `{rev}`, with uncommitted P1 changes identified
by SOURCE-REVISION.json. Not externally accepted. P2 was not started.

## Actual verification

`bash scripts/setup.sh`, then `.venv/bin/python scripts/setup_benchmark.py`,
`.venv/bin/python scripts/verify_p1.py`, `.venv/bin/python scripts/make_review_p1.py`.
Python 3.12.14, pinned SDK {benchmark['sdk']}, SQLite, MCP 1.30.0 on Linux x64.
{test_count} product tests passed, including all 43 accepted P0 regressions;
no skips. Both wheels built and Knowledge ran in a dependency-free environment.
Pinned application build and 49 unit tests passed before and 49 after P1
integration, with zero failed or skipped tests. Real stdio sessions, killed
processes and competing writers executed; no live model was used.

## Concrete result

A full scan now persists inventory/coverage/observations, generates source-backed
proposals, resumes bounded work, and refuses stale source. Versioned batches
update the same logical claim, retire/supersede assertions and change graph edges
through exact approved transactions. Old payloads/receipts remain readable and
retries do not revert later revisions. Retired or stale facts disappear from
trusted context while explicit lookup/history/export retains their explanation.

A synthetic ExternalManagement removal produced retirement proposals after
verified before/after source and consumer checks; approved application removed
old active assertions. Independent claims remained. Missing evidence without
corroboration, blocked/incomplete scans and external/historical statements did
not cause automatic retirement. Reviewed dependency closure can retain a still
valid dependent while retiring its old relationship, without deleting history.

## Review choices, repairs and limits

Source schemas retain confidence semantics; lifecycle/freshness/review are separate.
Self-review repaired a real history/current graph interaction: retired edges must
not force a newly independent current payload to retain an obsolete dependency.
It also tightened historical receipt ownership, upgrade backup binding, P0
prepared-approval compatibility and scan identity exclusion of store journals.
The final run was executed after these changes.

Discovery is deliberately lexical. It proves source syntax, not business rationale,
runtime dispatch, deployment availability or complete semantic analysis. Unsupported
files, ambiguous identities, gaps, returned lexical extras and partial coverage
are exposed in raw evidence. Retirement is narrow and conservative; unresolved
consumer changes can block a proposal until reviewed. Old unacknowledged commits
must be recovered/acknowledged before preparing later canonical changes.
NuGet emits upstream vulnerability warnings; pinned dependencies/tests were not
changed or weakened. .NET requires host synchronization-object access and uses
single-node builds, no shared compilation and LibraryRestore=false for unit
baseline (no browser assets). Native Windows, live OpenCode/model/provider host,
browser/database/Aspire deployment are NOT_RUN. No portable required check remains
failed or blocked in this run.

## Delivery

P1-CONTRACTS.md defines exact operations, commands, policies and recovery.
ACCEPTANCE.json maps all 20 rows to executed tests/evidence. Discovery, lifecycle
and upgrade reports link to raw generated results. The ZIP contains source,
tests, task, setup/verification, licenses and the current run, excluding SDKs,
caches, credentials, synthetic databases and old verification artifacts.
''')
    report('DISCOVERY-REPORT.md',f'''# Automatically generated discovery evaluation

{common}
Pinned eShopOnWeb {benchmark['pin']}; ordinary disposable copy, no worktree.
No curated benchmark dataset was read as discovery input.
{len(scan['observations'])} observations; categories: {json.dumps(categories)}.
{len({o['project'] for o in scan['observations']})} partitions with observations.
Inventory completion: {scan['complete']}; semantic completeness:
{scan['semantic_coverage_complete']}. Coverage/exclusions/source manifest,
ambiguous identities and gap reasons: discovery.json in this run.

Five expected answers were anchored directly to source before discovery, then
checked against generated/imported data using natural questions, not claim IDs.
All five passed; all returned claims, including lexical extras, remain visible
in questions.json. No-answer abstained. A synthetic unconfirmed external claim
remained excluded from trusted source context; no confidence promotion occurred.
Repeating unchanged discovery added zero candidates. These observations establish
usefulness for this sample, not broad business/domain accuracy.

Controlled source change provenance is explicitly synthetic: removal/replacement,
DI/route changes, additions and rename are committed only in a temporary fixture.
controlled.json retains before/after snapshots, operations, exact preview,
current/history results and source-delta evidence. Product tests additionally
exercise dirty staged/unstaged/untracked handling, process restart and drift.
''')
    report('LIFECYCLE-REPORT.md',f'''# Lifecycle and reconciliation

{common}
controlled.json contains the generated synthetic ExternalManagement fixture,
complete before/after discovery, corroborated removal preview, exact approved
mixed additions/revisions/retirements, acknowledgment and resulting queries.
The old source-syntax assertions are inactive with retrievable revisions;
NewService is current and independently anchored.

Executed tests cover explicit update/supersede, active successor checks,
dependent closure, retired relationship history, retained independent dependent,
old apply/ack retries, unknown inputs, stale approvals/source, review dispositions,
and actual process deaths during mixed write/after commit/acknowledgment.
External/historical statements and unrelated valid anchors are retained; missing
files, blocked coverage or unavailable semantics alone do not retire anything.
See product-tests.log and P1-CONTRACTS.md for the exact policy and test names.
''')
    report('UPGRADE-RECOVERY-REPORT.md',f'''# Nonempty P0 upgrade and transaction recovery

{common}
upgrade.json records a nonempty accepted-format fixture with canonical data,
a committed but unacknowledged transaction and a second pending candidate.
All P0 export fields compare equal before/after schema extension. The backup is
a consistent SQLite snapshot, bound to the preview including metadata/plans,
and cannot silently substitute another database. Existing migration/queue IDs
and imported bindings are separately exercised by UpgradeLegacyTests.

Actual subprocess interruption before upgrade commit leaves P0 fully usable;
repeat upgrade succeeds. Unknown versions refuse. Prepared P0 approvals survive
metadata-only upgrade; wrong/stale approvals refuse. Interrupted mixed updates
roll back, committed batches recover acknowledgment, and old acknowledged
receipts remain safe after later updates. Competing P1 processes never produce
partial revisions. No record deletion or reset is used for recovery.

To restore an upgrade backup, stop all participating processes, preserve the
current .knowledge directory with its journals separately, restore the retained
backup SQLite file at the same project's store.sqlite3, validate with P0/P1
software, then preview a fresh upgrade. Do not move a store to another root,
delete hot journals, or overwrite unrelated edits. See the contract for bounds.
''')
    report('CHANGE-SUMMARY.md','''# P1 changes

- Add lifecycle/revision, receipt, disposition and upgrade metadata to the shared SQLite store.
- Add deterministic bounded .NET discovery, durable checkpoints, verified Git/dirty snapshots and conservative reconciliation.
- Extend CLI and existing read-only MCP/Harness paths with current/history/freshness semantics and byte budgets.
- Add source-independent fixtures, crash/concurrency/upgrade/graph tests and uncurated pinned application evaluation.
- Add a separate strict P1 run ledger and checksum-verified review packet; retain accepted P0 evidence unchanged.
''')
    # Snapshot only allowlisted source and this completed run; never old/diagnostic runs/caches.
    files=[ROOT/p for p in v['source_files']]
    files.extend(p for p in directory.rglob('*') if p.is_file() and not p.name.startswith('previous-'))
    files.extend(OUT/n for n in ('P1-REPORT.md','P1-CONTRACTS.md','ACCEPTANCE.json','SOURCE-REVISION.json','DISCOVERY-REPORT.md','LIFECYCLE-REPORT.md','UPGRADE-RECOVERY-REPORT.md','CHANGE-SUMMARY.md','verification-summary.json','STATUS.json'))
    files=sorted(set(files));inventory={str(p.relative_to(ROOT)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in files}
    save(OUT/'REVIEW-INVENTORY.json',inventory)
    packet=OUT/'P1-review.zip'
    with zipfile.ZipFile(packet,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files+[OUT/'REVIEW-INVENTORY.json']:
            info=zipfile.ZipInfo(str(p.relative_to(ROOT)),(2026,11,15,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,p.read_bytes())
    with zipfile.ZipFile(packet) as z:
        assert z.testzip() is None
        assert set(z.namelist())==set(inventory)|{'reports/P1/REVIEW-INVENTORY.json'}
        for name,item in inventory.items():
            data=z.read(name);assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256']
    (OUT/'P1-review.zip.sha256').write_text(sha(packet)+'  P1-review.zip\n')
    save(OUT/'packet-check.json',dict(status='PASS',run_id=v['run_id'],source_identity=v['source_identity'],members=len(files)+1,archive_sha256=sha(packet),inventory_verified=True))
    print(f'PASS: {test_count} product tests, 49/49 application tests, 20 acceptance rows, verified {len(files)+1} ZIP members')


if __name__=='__main__':main()
