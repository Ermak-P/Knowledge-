"""Refuse incomplete/stale evidence; build one allowlisted SHA-verified P2 review ZIP."""
import hashlib,json,re,subprocess,zipfile
from pathlib import Path
from p2_evidence import ROOT,OUT,DOCS,save,sha,validate_current,sources,fingerprint

TESTS={
 '01':[],
 '02':['RunnerTests.test_provider_malformed_oversized_missing_usage_and_limits','BoundaryTests.test_provider_surrogates_usage_subsets_and_final_version_refuse'],
 '03':['RunnerTests.test_context_isolation_actual_bytes_and_shared_history_comparison','RunnerTests.test_long_history_unicode_tool_budget_and_role_spoofing'],
 '04':['BoundaryTests.test_protected_tests_recipes_paths_and_typed_spoof_denied','BoundaryTests.test_supervisor_imports_cannot_be_replaced_by_application_package'],
 '05':['RunnerTests.test_real_http_execution_roles_gates_capture','RecoveryTests.test_real_worker_death_recipe_keeps_lease_and_recovery_cleans_it'],
 '06':['BoundaryTests.test_durable_versions_project_identity_and_corruption_refuse_without_reset','BoundaryTests.test_cli_backend_and_legacy_configuration_compatibility'],
 '07':['BoundaryTests.test_missing_stale_fake_gates_and_configuration_drift','BoundaryTests.test_concurrent_source_edit_during_recipe_invalidates_gate','RunnerTests.test_permissions_and_review_failure_prevent_false_success'],
 '08':['RunnerTests.test_actual_failure_repair','RunnerTests.test_provider_malformed_oversized_missing_usage_and_limits'],
 '09':['RecoveryTests.test_real_edit_intent_write_and_receipt_crashes_resume_without_double_edit','RecoveryTests.test_recovery_preserves_intervening_user_bytes_and_unknown_provider'],
 '10':['RecoveryTests.test_timeout_cleans_real_descendants_and_cancellation_stops_provider','RecoveryTests.test_real_worker_death_recipe_keeps_lease_and_recovery_cleans_it'],
 '11':['RunnerTests.test_real_http_execution_roles_gates_capture'],
 '12':['RunnerTests.test_capture_five_sessions_no_facts_reject_dedup_and_no_auto_apply','BoundaryTests.test_terminal_window_and_unchanged_deferred_candidate_are_idempotent'],
 '13':['RecoveryTests.test_capture_commit_ack_crash_and_concurrent_delivery_retry','RecoveryTests.test_busy_and_corrupt_capture_are_explicit_and_recover_without_code_replay'],
 '14':['RecoveryTests.test_busy_and_corrupt_capture_are_explicit_and_recover_without_code_replay','BoundaryTests.test_terminal_window_and_unchanged_deferred_candidate_are_idempotent'],
 '15':['RunnerTests.test_real_http_execution_roles_gates_capture','BoundaryTests.test_provider_surrogates_usage_subsets_and_final_version_refuse'],
 '16':['RunnerTests.test_long_history_unicode_tool_budget_and_role_spoofing','RunnerTests.test_provider_malformed_oversized_missing_usage_and_limits','RecoveryTests.test_timeout_cleans_real_descendants_and_cancellation_stops_provider'],
 '17':['RunnerTests.test_context_isolation_actual_bytes_and_shared_history_comparison'],
 '18':['BoundaryTests.test_cli_backend_and_legacy_configuration_compatibility','RunnerTests.test_readonly_absence_and_legacy_consumer_are_explicit'],
 '19':[],
 '20':['RecoveryTests.test_capture_commit_ack_crash_and_concurrent_delivery_retry','RunnerTests.test_actual_failure_repair','RunnerTests.test_capture_five_sessions_no_facts_reject_dedup_and_no_auto_apply'],
 '21':['EvidenceGate.test_failed_interrupted_stale_mixed_missing_and_modified_artifacts_refuse'],
 '22':[]}
EVIDENCE={
 '01':['baseline/baseline.json','packaging/command.log','product-tests/product-tests.json'],
 '02':['product-tests/product-tests.json'], '03':['evaluation/comparison.json'], '04':['evaluation/denied.json'],
 '05':['evaluation/application-run.json'], '06':['product-tests/product-tests.json'], '07':['evaluation/application-run.json'],
 '08':['evaluation/repair-run.json'], '09':['product-tests/command.log'], '10':['product-tests/command.log'],
 '11':['sessions/capture-sessions.json'], '12':['sessions/capture-sessions.json'], '13':['product-tests/command.log'],
 '14':['product-tests/product-tests.json'], '15':['evaluation/comparison.json','evaluation/application-run.json'],
 '16':['product-tests/product-tests.json'], '17':['evaluation/comparison.json'], '18':['packaging/command.log'],
 '19':['evaluation/application.json','evaluation/baseline.trx','evaluation/original-immutability.json'],
 '20':['evaluation/repair.json','evaluation/denied.json','sessions/capture-sessions.json'],
 '21':['run.json','product-tests/product-tests.json'], '22':['run.json']}

CORRECTION_TESTS={
 'P2-R1':['test_r1_automatic_add_approve_two_updates_and_retired_return','test_r1_reviewed_meaning_and_legacy_capture_require_explicit_manual_review','test_r1_update_crash_and_rejected_deferred_retry_preserve_ownership','test_r1_malformed_observation_metadata_refuses_without_reset'],
 'P2-R2':['test_r2_absolute_relative_and_project_entrypoint_cannot_replace_verifier','test_r2_exact_explicit_script_edit_exception_is_observable','test_r2_recipe_input_resolver_rejects_links_and_hardlinks'],
 'P2-R3':['test_r3_prelease_race_retains_terminal_readonly_coding_and_capture','test_r3_configuration_is_reloaded_under_ownership_before_capture']}
AFFECTED={'P2-R1':('11','12','13','14'),'P2-R2':('04','05','07','20'),'P2-R3':('05','06','09','13','15','20')}

def main():
    value=validate_current();run=value['run_id'];directory=OUT/'runs'/run
    tests=json.loads((directory/'product-tests/product-tests.json').read_text());assert tests['success'] and tests['legacy_tests']==104
    statuses={r['test']:r['status'] for r in tests['results']}
    application=json.loads((directory/'evaluation/application.json').read_text());assert application['outcome']['ok'] and int(application['before']['total'])==49 and application['after']['total']==50
    comparison=json.loads((directory/'evaluation/comparison.json').read_text());assert comparison['ok'] and comparison['comparison']['quality_speed_token_benefit']=='NOT_ESTABLISHED'
    sessions=json.loads((directory/'sessions/capture-sessions.json').read_text());assert len(sessions['sessions'])==5 and all(len(s['candidates'])==1 and s['canonical_claims']==0 for s in sessions['sessions'])
    corrections=json.loads((directory/'corrections/corrections.json').read_text());assert all(v=='PASS' for v in corrections['findings'].values())
    correction_rows=[]
    for finding,names in CORRECTION_TESTS.items():
        ids=['test_p2_r1.ReviewCorrections.'+name for name in names]
        assert all(statuses.get(name)=='PASS' for name in ids)
        correction_rows.append(dict(id=finding,status='PASS',tests=ids,evidence='runs/'+run+'/corrections/',external_acceptance='pending'))
    specs={}
    for line in (ROOT/'tasks/Knowledge-Harness-P2-Codex-Task.md').read_text().splitlines():
        if re.match(r'\| P2-A\d\d \|',line):
            parts=line.split('|');specs[parts[1].strip()]=parts[2].strip()
    rows=[]
    for n in range(1,23):
        number=f'{n:02}';identifier='P2-A'+number;names=[]
        for name in TESTS[number]:
            test=('test_p2_evidence.' if name.startswith('EvidenceGate.') else 'test_p2.')+name
            assert statuses.get(test)=='PASS',(identifier,test);names.append(test)
        for finding,conditions in AFFECTED.items():
            if number in conditions:names.extend('test_p2_r1.ReviewCorrections.'+name for name in CORRECTION_TESTS[finding])
        artifacts=['runs/'+run+'/'+p for p in EVIDENCE[number]]
        if any(number in conditions for conditions in AFFECTED.values()):artifacts.append('runs/'+run+'/corrections/corrections.json')
        for path in artifacts:assert (OUT/path).is_file(),path
        rows.append(dict(id=identifier,requirement=specs[identifier],status='PASS',interpretation='implementation evidence submitted, external acceptance pending',tests=names,evidence=artifacts))
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip();assert branch=='p2'
    optional=dict(live_model='NOT_RUN: no configured authorized provider endpoint/model',OpenCode='NOT_RUN',Windows_NTFS='NOT_RUN',private_MCP='NOT_RUN',live_quality_speed_token_benefit='NOT_ESTABLISHED')
    acceptance=dict(version=1,phase='P2',submission='submitted for external review',run_id=run,source_identity=value['source_identity'],branch=branch,head_at_packet_creation=head,revision_binding='Containing Git commit identifies delivery; source inventory is authoritative. A commit cannot include its own hash.',conditions=rows,review_corrections=correction_rows,optional=optional)
    save(OUT/'ACCEPTANCE.json',acceptance)
    report=f'''# P2 implementation submitted for external review

Branch `{branch}`; accepted P1 `c62cad5aabbc47b43ef59fcf3ff975dd405eb42d`, merged base `5e6f33da5758c30418df490840c76c1946c84545`. Head before packet commit: `{head}`. The containing delivery commit is the final Git revision; this report does not embed its own commit hash. Source identity `{value['source_identity']}`, current run `{run}`. Historical P0/P1 evidence and every accepted test body were preserved.

Harness 0.2 implements actual HTTP model transport, immutable runtime roles, sequential isolated contexts, constrained in-place patches, configured argv recipes, final-source/config build/test/review gates, durable crash recovery, capture outbox and all-role accounting. Knowledge remains independently installable and canonical changes require explicit approval. Live model decisions were unavailable; all provider decisions below are deterministic test inputs sent through actual HTTP, production tools/stores/processes.

Executed `.venv/bin/python -B scripts/verify_p2.py`: fresh setup and isolated wheels; **{tests['tests_run']} tests passed, including all 104 accepted regressions**, no skips. Existing adapter stdio/API cases remain in that suite. Accepted historical source inventory/ancestry verified. Fresh eShop restore/build/test at the required pin: **49/49 baseline, 50/50 after** checked-overflow behavior plus independently specified new xUnit test; all previous test source bytes preserved. Two-project real C# failure -> repair -> fresh gates passed. Denied source/isolation scenario failed honestly without forbidden changes. Five eligible capture sessions automatically submitted one candidate each, canonical remained empty. Actual worker deaths, process timeout/cleanup, writer contention, unknown provider outcome, corrupt/busy Knowledge and concurrent accepted-before-ack replay were executed. Source/evidence gate negative cases reject failed/incomplete/stale/mixed/missing/tampered evidence.

Comparison: same .NET repair task, provider and guarded policy in ordinary shared-history and isolated-context copies. Both succeed; complete costs include Main, every role, failed checks and repair. Fixture token counters are synthetic; no live efficiency/quality benefit is established. SDK version `{application['sdk']}`; upstream dependency/security and SDK warnings are retained in raw logs, baseline dependencies were preserved.

P2 review correction round: R1 records verified positive observations through Knowledge's coordinated writer and ties later ownership to exact approved candidates; unowned/reviewed meanings require manual review. R2 protects canonical absolute/relative argv, script/module and project executable inputs; exact script exceptions are explicit events. R3 reloads all mutable run/config state under the lease and rechecks terminal state before execution. All three are reproduced with fresh raw artifacts in `corrections/`; the original 129 tests and their bodies are preserved. See P2-R1-RESPONSE.md.

Self-review repaired invalid Unicode response handling, stale fixture review selection, module recipe-input protection, test-directory casing, fixed supervisor imports against project package/PYTHONPATH shadowing, and stricter durable-state/config validation. Final verification follows these repairs. Practical limits: trusted host build hooks, Linux process groups, conservative source profile, per-file filesystem transactions and uncertain remote request billing; see contracts/recovery documents. Failed/cancelled runs retain evidence and cannot be converted into success by reset. Main is unchanged by the delivery; application edits are not committed automatically.

Unexecuted optional checks: live model/llama-server, OpenCode, native Windows/NTFS and private MCP. Model quality/speed/token benefit NOT_ESTABLISHED. No mandatory portable check is omitted from the current run. P3 was not started.

Review packet: `reports/P2/P2-review.zip`, external `.sha256`, per-member `ZIP-INVENTORY.json`, and `packet-check.json`. Reproduce with setup, `scripts/setup_benchmark.py`, `scripts/verify_p2.py`, then `scripts/make_review_p2.py`. Full 22-row mapping: ACCEPTANCE.json. Raw current evidence: `runs/{run}/`; all check artifacts bind their hashes to one source/run ledger. The submitted matrix is not independent acceptance.
'''
    (OUT/'P2-REPORT.md').write_text(report,encoding='utf-8')
    files=dict(sources())
    for p in (OUT/'ACCEPTANCE.json',OUT/'P2-REPORT.md',OUT/'verification-summary.json',directory/'run.json'):files[str(p.relative_to(ROOT))]=sha(p)
    for check in value['checks'].values():
        for relative,digest in check['artifacts'].items():files['reports/P2/'+relative]=digest
    # Retain the accepted baseline receipt/inventory without unrelated historical ZIPs.
    for relative in ('reports/P1/SOURCE-REVISION.json','reports/P1/ACCEPTANCE.json'):
        if (ROOT/relative).is_file():files[relative]=sha(ROOT/relative)
    inventory=dict(version=1,run_id=run,source_identity=value['source_identity'],files=dict(sorted(files.items())))
    archive=OUT/'P2-review.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for relative,expected in sorted(files.items()):
            assert sha(ROOT/relative)==expected,relative;z.write(ROOT/relative,relative)
        z.writestr('ZIP-INVENTORY.json',json.dumps(inventory,indent=2,ensure_ascii=False)+'\n')
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert set(z.namelist())==set(files)|{'ZIP-INVENTORY.json'} and len(z.namelist())==len(files)+1
        for relative,expected in files.items():assert hashlib.sha256(z.read(relative)).hexdigest()==expected,relative
    # Recheck the source and current attempt after reading all archive inputs.
    assert validate_current()==value
    (OUT/'P2-review.zip.sha256').write_text(sha(archive)+'  P2-review.zip\n')
    save(OUT/'packet-check.json',dict(status='PASS',run_id=run,source_identity=value['source_identity'],archive_sha256=sha(archive),members_verified=len(files)+1,inventory_sha256=fingerprint(inventory),checksums_per_member=True,excluded='credentials, SDK/model/dependency caches, private settings, benchmark checkout, unrelated runs'))
    print(f'PASS: {len(rows)} conditions mapped; {len(files)+1} ZIP members verified; {archive}')
if __name__=='__main__':main()
