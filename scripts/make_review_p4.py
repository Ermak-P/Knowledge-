"""Derive every acceptance row from the current installed run, never manually promote evidence."""
import argparse,hashlib,json,zipfile
from pathlib import Path
from verify_p4 import ROOT,source
from build_p4 import VERSION
CASES={
 'P4-01':['test_real_pipeline_and_no_attendance'],
 'P4-02':['test_sequential_fresh_items_final_gates','test_final_review_repairs_first_item_without_last_scope'],
 'P4-03':['test_discovered_fact_survives_real_rotation_process_death'],
 'P4-04':['test_oversized_irreducible_no_call'],
 'P4-05':['test_owned_artifact_range_recovers_real_log'],
 'P4-06':['test_reviewer_rejection_cannot_complete','test_empty_test_report_never_passes'],
 'P4-07':['test_noise_does_not_escape_finite_repair','test_finite_real_failed_checks'],
 'P4-08':['test_discovered_fact_survives_real_rotation_process_death','test_real_process_death_after_edit_and_verifier_receipt','test_checkpoint_and_receipt_recovery'],
 'P4-09':['test_unknown_provider_never_replayed'],
 'P4-10':['test_scope_and_cycle_rejected_before_http','test_fake_summary_and_zero_tests_do_not_pass','test_plan_proposal_is_validated'],
 'P4-11':['test_p4_companion_crossing_rejects_before_effect'],
 'P4-15':['test_cancellation_and_competing_resume_during_automatic_verification','test_competing_resume_after_rotation_keeps_single_source_effect']}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('run');p.add_argument('--native',type=Path);a=p.parse_args();folder=ROOT/'reports/P4';run=folder/'runs'/a.run;v=json.loads((run/'run.json').read_text());assert v['source']==source() and v['unchanged'] and v['status'] in ('PASS_PORTABLE','PASS_NATIVE')
 tests=json.loads((run/'tests.json').read_text());assert tests['run']==a.run and tests['success']
 passed={r['test'].split('.')[-1] for r in tests['results'] if r['status']=='PASS'};matrix={key:dict(status='PASS' if all(n in passed for n in names) else 'FAIL',evidence=names) for key,names in CASES.items()}
 matrix['P4-12']=dict(status='PASS' if all(v['checks'].get('accepted-p3-lifecycle-'+k)=='PASS' for k in ('marked','unmarked')) and v['checks'].get('accepted-p3-maintenance-recovery')=='PASS' else 'FAIL',evidence=['lifecycle-marked/result.json','lifecycle-unmarked/result.json','lifecycle-pending/result.json'])
 matrix['P4-14']=dict(status='PASS' if v['checks'].get('knowledge-only-smoke')=='PASS' else 'FAIL',evidence=['knowledge-only-install.log','knowledge-only-smoke.log'])
 native=None
 if a.native:
  native=json.loads(a.native.read_text());assert native['platform']=='Windows' and native['status']=='PASS_NATIVE' and native['source_identity']==v['source_identity'],'native receipt must bind these exact source inputs'
 matrix['P4-13']=dict(status='PASS' if v['status']=='PASS_NATIVE' or native else 'NOT_RUN',evidence=[native['url']] if native else ['.github/workflows/p4.yml; prior run 44384715030 failed checkout before tests; new exact-source native receipt pending'])
 verdict='GO_FOR_REVIEW' if all(x['status']=='PASS' for x in matrix.values()) else 'NO_GO'
 (folder/'acceptance.json').write_text(json.dumps(dict(run=a.run,source_identity=v['source_identity'],verdict=verdict,matrix=matrix,native=native),indent=2)+'\n')
 (folder/'ACCEPTANCE-MATRIX.md').write_text('# P4 acceptance\n\nGenerated from installed run '+a.run+'. Verdict: **'+verdict+'**. PASS is executed software evidence, not live model or production certification.\n\n| ID | Status | Executed evidence |\n|---|---|---|\n'+''.join('| '+key+' | '+val['status']+' | '+', '.join(val['evidence'])+' |\n' for key,val in sorted(matrix.items()))+'\nThe original Windows job had an available runner but failed checkout (filename too long), not missing infrastructure. Active checkout settings now enable process-local long paths. A YAML file alone is not native evidence.\n')
 (folder/'IMPLEMENTATION.md').write_text('# P4 R1 implementation\n\nCandidate '+VERSION+'; final installed run '+a.run+'; source identity '+v['source_identity']+'.\n\nR1: known predecessor maintenance markers remain readable without mutation; exact-approved upgrades retain old state/markers in backup and transaction history, and recovery completes the originally approved version. Real accepted P3 fixtures cover marked and unmarked nonempty/pending states and actual code/data rollback.\n\nR2: safe rotations publish version-2 continuation contracts with owned read/search/action receipts, bounded observations, explicit untrusted decision notes, unresolved issues and next step. Fresh contexts receive this contract and range retrieval, rather than an inherited transcript. A fact learned from Notes.md drives a real patch after process death and rotation.\n\nR3: final findings map to their affected immutable item scopes; structured affected item/path references are validated. Earlier items can reopen without broadening authority, losing attempts, replaying unrelated source edits or reusing final gates. Ambiguous findings stop for an explicit target.\n\nR4: native checkout restores process-local core.longpaths. CI emits exact-source/package qualification receipts through the dedicated p4-ci-evidence branch as well as Actions artifacts.\n\nR5: all fifteen acceptance IDs are derived from actual tests/checks; .NET application, comparison manifests, independent install, concurrency, workflow and lockfile inventories are part of the single verification route. No manual PASS promotion.\n\nTests: '+str(tests['tests'])+' discovered, '+str(tests['passed'])+' PASS, '+str(tests['skipped'])+' SKIP, '+str(tests['failed']+tests['errors'])+' failures/errors. Native status and remaining gaps: ACCEPTANCE-MATRIX.md. No merge, deployment or release publication.\n')
 rows=json.loads((run/'comparison/results.json').read_text())['rows'];text='# Synthetic P3/P4 comparison\n\nPredeclared manifest: runs/'+a.run+'/comparison/scenario-manifest.json. Exact accepted P3 package; independent source copies and fixed tests; three repeats for positive cases. Provider usage is synthetic, live quality/benefit NOT_ESTABLISHED. Raw failures are retained.\n\n| Policy | Scenario | Successful runs | max Coding/Main bytes | calls | input bytes | reported tokens | unknown | rotations | seconds |\n|---|---|---|---|---|---|---|---|---|---|\n'
 for policy in ('P3','P4'):
  for name in ('simple','multi-file','multi-pressure','persistent-failure'):
   rs=[r for r in rows if r['policy']==policy and r['scenario']==name];r=rs[0];text+=f"| {policy} | {name} | {sum(x['correct'] for x in rs)}/{len(rs)} | {max(x['max_coding'] for x in rs)}/{max(x['max_main'] for x in rs)} | {r['calls']} | {r['input_bytes']} | {r['reported_tokens']} | {r['unknown_usage']} | {r['rotations']} | {r['elapsed']:.3f} |\n"
 (folder/'EVALUATION.md').write_text(text+'\nMaxima cover all repetitions; other table totals show the first repeat. Persistent failure is expected to remain non-success. Complete per-repeat totals and attempted calls are retained in the raw results.\n')
 (folder/'REVIEW-INDEX.md').write_text('# P4 R1 review index\n\nCurrent source-bound run: runs/'+a.run+'/run.json. Package: runs/'+a.run+'/distribution/. Tests: tests.json and regressions.log. Real pinned eShop behavior/failed-before-fix TRX and review inputs: application/. Marked/unmarked prior package round trips: lifecycle-marked/, lifecycle-unmarked/. Full four-scenario comparison: comparison/. Native receipt and acceptance: acceptance.json. Source inventory includes active workflows, locked dependencies, SDK pin, review task and every executed helper. Historical runs are historical only.\n')
 files={ROOT/path for path in v['source']};files.update(p for p in run.rglob('*') if p.is_file());files.update(folder/n for n in ('acceptance.json','ACCEPTANCE-MATRIX.md','IMPLEMENTATION.md','EVALUATION.md','REVIEW-INDEX.md'))
 if a.native:files.add(a.native)
 files={p for p in files if p.name not in ('P4-review.zip','P4-review.zip.sha256','REVIEW-MANIFEST.json') and p.is_relative_to(ROOT)}
 manifest={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files)};(folder/'REVIEW-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n');files.add(folder/'REVIEW-MANIFEST.json')
 with zipfile.ZipFile(folder/'P4-review.zip','w',zipfile.ZIP_DEFLATED) as z:
  for path in sorted(files):z.write(path,path.relative_to(ROOT))
 with zipfile.ZipFile(folder/'P4-review.zip') as z:
  assert z.testzip() is None
  for name,h in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==h
 (folder/'P4-review.zip.sha256').write_text(sha(folder/'P4-review.zip')+'  P4-review.zip\n');print(json.dumps(dict(run=a.run,verdict=verdict,archive_sha256=sha(folder/'P4-review.zip'))))
if __name__=='__main__':main()
