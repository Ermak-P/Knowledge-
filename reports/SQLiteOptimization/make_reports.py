"""Build review tables from retained, verified evidence, never invented results."""
import hashlib,json,statistics
from pathlib import Path

P=Path(__file__).resolve().parent
def read(name):return json.loads((P/name).read_text())
def save(name,value):(P/name).write_text(json.dumps(value,indent=2)+'\n')
def ms(x):return f'{1000*x:.2f}'


def main():
    source=read('source.json');package=read('distribution/package.json');ci=read('ci/validation.json');bench=read('benchmarks/results.json');indexed=read('indexed-benchmarks/results.json')
    assert ci['commit']==package['commit']==source['commit']
    assert ci['platforms']['Linux']['status']=='PASS_PORTABLE' and ci['platforms']['Windows']['status']=='PASS_NATIVE'
    assert all(r['equivalent_results'] for r in bench['results']+indexed['results'])
    for profile in ('Linux','Windows'):
        run=read(f'ci/{profile}/run.json');assert run['source']==source['source'] and run['source_identity']==source['source_identity']
    rows={(r['dataset'],r['operation']):r for r in bench['results']}
    lines=['# Installed baseline → candidate benchmark','',
        f"Baseline `73a3fc70c5fde17536568baae2a03b1b8be8b8a1`; final source `{source['commit']}`. Both official core kits were installed outside the checkout; [baseline byte proof](baseline-install.json), [candidate byte proof](candidate-install.json). No editable/source fallback imports.",
        '', 'All paired operation results match. This is a Linux/Python 3.12.14/SQLite 3.53.1 measurement, with runtime details in every raw sample. Native Windows correctness is qualified separately; no Windows speedup is claimed.',
        '', '## Method and limits','',
        'Warm public API calls use fresh connections and full normal validation. Small read cases have 20 samples after warm-up; medium reads 5, large reads 3. Expensive/state-changing calls have 3 repetitions with same-root quiescent snapshot resets. Baseline/candidate halves are interleaved; raw samples and commands are retained. Median is the usual middle/mean-of-two; p95 is nearest rank `ceil(.95*n)` (therefore the maximum for small n). Three samples establish a bounded observation, not a stable tail-latency guarantee.',
        '', 'Generation, validation of fixtures, reset, index DDL, imports and instrumentation are outside public API timings. Profiles separately count traced SQL, approximate VM steps (1000-step callbacks), `knowledge.util.loads` aliases, record/candidate validators, canonical validation, and Path reads; these are supporting counters, not exclusive CPU-time allocations. No check, sync, lock, journal mode or timeout is disabled. OS disk caches and CPU scheduling were not controlled; fresh processes are not cold disks.',
        '', 'Fixtures are synthetic and validated through normal APIs. Rules have 3 revisions, with a separate 128-revision history; binding counters are revision scoped and predecessor links agree. Queues use valid add-evidence envelopes and historical PREPARED snapshots, real empty acknowledged/committed receipts, and 1/10/100% pending. The rare-COMMITTED fixture has one real committed empty plan. No data/history is deleted for speed, no root identity is rewritten, and baseline/candidate restore identical input hashes at the same temporary root.',
        '', 'The requested matrix is reduced at 100,000 queue rows: fully audited 10,000-row calls already take about 3 seconds on the baseline, with schema/filesystem work for every candidate; repeating all 100,000-row queue variants would multiply that cost. Queue coverage is 1,000/10,000 rows at all requested pending fractions, plus legacy and rare/zero COMMITTED cases. Operational events reach 100,000. Outbox uses 1,000/10,000/30,000 entries with complete owner runs, queued-payload receipts and delivery events; the large case has 10,000 historical runs and only three entries for the selected run. No constant-time queue/current-state claim follows.',
        '', 'Logical comparisons preserve IDs/revisions/authority and compare returned outcomes. Only explicitly volatile `at`, wall_seconds and timing fields are removed from API result hashes. Raw database hashes are also retained; event IDs derived from actual wall clocks can legitimately differ across writes. Integrity/atomicity and complete canonical preservation are independently covered by the tests and [installed compatibility probe](compatibility/result.json).',
        '', '## Complete operation timings','',
        '| Dataset | Operation | n | Baseline median / p95 ms | Default candidate median / p95 ms | Ratio |',
        '| --- | --- | ---: | ---: | ---: | ---: |']
    for r in bench['results']:
        b=r['baseline'];c=r['candidate'];lines.append(f"| {r['dataset']} | {r['operation']} | {r['count_each']} | {ms(b['median'])} / {ms(b['p95'])} | {ms(c['median'])} / {ms(c['p95'])} | {r['speedup']:.2f}× |")
    lines+=['','`records`, `lookup`, `binding-read` and `application-read` include the full corruption audit. `prepare`, `recover`, duplicate/new submission are real Store APIs. `status` includes Journal construction; journal reads/writes are grouped sequences of public methods; outbox-write inserts/updates a complete delivery payload, records its delivery event and run capture state, then reads through actual APIs. Capture retry uses already delivered outbox entries and performs no new execution effects. Every outbox owner is validated by the normal Journal.load method at generation time; all candidate receipts agree. `context` is the complete facade including source/freshness/dependency/budget work; `filesystem` is an unchanged inventory/analysis component, not a product operation or a claimed SQL gain. Default Journal.outbox/events/action read bodies are unchanged; ratios for those paths include sampling/noise and are not claimed algorithmic gains.',
        '', 'Fresh complete CLI processes (including imports/JSON transport and source checks):','', '| Dataset | n | Baseline median / p95 ms | Candidate median / p95 ms |','| --- | ---: | ---: | ---: |']
    for name in ('small','large'):
        d=read('cli/'+name+'.json');b=d['results']['baseline'];c=d['results']['candidate'];lines.append(f"| {name} | {d['count']} | {ms(b['median'])} / {ms(b['p95'])} | {ms(c['median'])} / {ms(c['p95'])} |")
    lines+=['','## Index tradeoff and write costs','',
        'The default creates no additional indexes. The `outbox(run)` profile is opt-in: subset reads improve, but its additional quick_check pages slow unrelated journal calls. The implementation supports normal new-journal initialization with `index_outbox=True` and exact-approved, backed-up upgrade/rollback for existing journals. A run-specific partial index cannot serve arbitrary other/absent runs. Queue/status and plan/status ordinary/partial candidates are excluded: faster subset SQL is dominated by the mandatory full audit.',
        '', '| Dataset | Operation | Default candidate ms | Opt-in candidate ms | Opt-in / default |','| --- | --- | ---: | ---: | ---: |']
    for r in indexed['results']:
        default=rows[(r['dataset'],r['operation'])]['candidate']['median'];chosen=r['candidate']['median'];lines.append(f"| {r['dataset']} | {r['operation']} | {ms(default)} | {ms(chosen)} | {chosen/default:.2f} |")
    lines+=['','These are separate interleaved runs, so small differences include scheduling/fsync noise. The primary write costs appear above (`new`, `prepare`, binding/application-read, journal-writes and outbox-write), with identical initial states. The opt-in index occupies 483,328 bytes on the fully owned 30,000-entry fixture (118 additional 4KiB pages); default storage adds zero index pages. In bounded samples, some indexed write sequences cost more; no universal read/write benefit is claimed. Storage, PRAGMA index_list/index_xinfo, exact plans, valid-row queue/plan INSERT/status UPDATE samples and post-DML validator checks are in [indexes](indexes/); page/freelist/index allocation is in [inventory](inventory/). Outbox INSERT/payload UPDATE costs use the public API scenarios, and its SQL diagnostic is read-only. SQL-only timings do not replace API results.',
        '', 'Full history audits remain linear. FS hashing/extraction is unchanged and independently timed. No inference, real Docker/IPM service, or whole-agent productivity gain is measured. No projection/retention/trust-boundary change is used.',
        '', 'Reproduce with [REPRODUCE.md](REPRODUCE.md). All machine-readable samples are in [benchmarks/results.json](benchmarks/results.json) and [indexed-benchmarks/results.json](indexed-benchmarks/results.json); per-dataset raw files and separate profiles are adjacent. Exploratory/superseded data is excluded from these final tables.']
    lines+=['','Additional complete prepare calls on the valid 10,000-row / 1%-pending fixture (3 timed repetitions each):','', '| Variant | Median ms |','| --- | ---: |',f"| no extra index (main interleaved run) | {ms(rows['queue-10k-1','prepare']['candidate']['median'])} |"]
    for name in ('ordinary','partial'):
        d=read('indexes/prepare-'+name+'.json');lines.append(f"| {name} | {ms(d['median'])} |")
    lines+=['','These short runs are not evidence that the subset index improves the full audit: JSON/schema work remains identical, and the subset SELECT budget is small relative to the complete call. The rare-COMMITTED SQL probe is read-only; an unsupported DML-lab attempt (no acknowledged target in that fixture) is preserved with its actual failure log and replaced by this separate probe. No product/qualification result was rewritten.']
    (P/'BENCHMARK.md').write_text('\n'.join(lines)+'\n')
    tests={k:read(f'ci/{k}/tests.json') for k in ('Linux','Windows')}
    baseline=json.loads((P.parent/'AuditStages12/R1/ci/Windows/tests.json').read_text())
    previous={r['test'] for r in baseline['results']};assert len(previous)==343
    assert all(previous<={r['test'] for r in t['results']} for t in tests.values())
    # Explicit IDs bind criteria to actual qualified results, not just counts.
    new=lambda suffix:'test_sqlite_optimization.SQLiteOptimization.test_'+suffix
    criteria={
        'DB-01':['new_journal_index_and_existing_reads_do_not_migrate','nonempty_index_upgrade_repeat_rollback_backup_restore'],
        'DB-02':['nonempty_index_upgrade_repeat_rollback_backup_restore'],
        'DB-03':['nonempty_index_upgrade_repeat_rollback_backup_restore','older_writer_preserves_index_and_journal_rows'],
        'DB-04':['dedup_exact_payload_legacy_id_and_mismatched_identity'],
        'DB-05':['unselected_current_history_and_orphan_history_corruption','corrupt_older_history_detected_after_valid_current_cache','fresh_process_roots_shared_and_external_corruption'],
        'DB-06':['invalid_and_orphan_events_are_not_no_match'],
        'DB-07':[],
        'DB-08':['fault_before_commit_rolls_back_event_and_invalidates_view','interrupted_index_upgrade_recovery_before_and_after_commit'],
        'DB-09':['binding_sequences_application_row_order_and_old_revision'],
        'DB-10':['fresh_process_roots_shared_and_external_corruption','nonempty_index_upgrade_repeat_rollback_backup_restore'],
        'DB-11':['concurrent_sequences_and_bounded_busy'],
        'DB-12':[],
        'DB-13':['interrupted_index_upgrade_recovery_before_and_after_commit','index_stale_preview_and_conflicting_definition'],
        'DB-14':['nonempty_index_upgrade_repeat_rollback_backup_restore','older_writer_preserves_index_and_journal_rows'],
        'DB-15':[], 'DB-16':[],
        'DB-17':['pure_read_database_bytes_and_sql'],
        'DB-18':['standalone_no_journal_index_cli_is_an_explicit_backed_up_noop'],
        'DB-19':[], 'DB-20':[]}
    filters={'DB-12':('test_p3_platform.','test_p2.','test_automatic_discovery.'),'DB-15':('test_audit_stage1.','test_audit_stage2.','test_persistent_r'),'DB-16':('test_audit_review_r1.','test_p4'),'DB-20':('test_',)}
    checks=[]
    for identifier,suffixes in criteria.items():
        item={'id':identifier,'profiles':{},'evidence':[]}
        for profile,t in tests.items():
            actual={r['test']:r['status'] for r in t['results']};ids=[new(s) for s in suffixes]
            if identifier in filters:ids=[name for name in actual if name.startswith(filters[identifier])]
            status='SKIP' if identifier=='DB-07' or identifier=='DB-19' and profile=='Windows' else 'PASS'
            assert all(actual[name]=='PASS' or profile=='Linux' and actual[name]=='SKIP' and '.NativeWindowsSafety.' in name for name in ids)
            item['profiles'][profile]={'status':status,'tests':ids,'evidence':f'ci/{profile}/tests.json'}
        if identifier=='DB-07':item['reason']='No projection or auxiliary key introduced.'
        if identifier=='DB-19':item['reason']='Growing valid public-operation timings measured on Linux only; Windows correctness qualified separately.';item['evidence']=['BENCHMARK.md','benchmarks/results.json','indexed-benchmarks/results.json','cli/small.json','cli/large.json']
        if identifier in ('DB-01','DB-02','DB-08','DB-10','DB-11','DB-13','DB-14'):item['evidence']+=['compatibility/result.json']
        if identifier=='DB-18':item['evidence']+=['standalone/result.json','distribution/package.json','candidate-install.json']
        checks.append(item)
    value=dict(source_commit=source['commit'],source_identity=source['source_identity'],package=package['zip_sha256'],ready_for_review=True,baseline_343_test_ids_retained=True,profiles=ci['platforms'],criteria=checks,earlier_failed_native_attempts=['ci-attempts/3bb83fa6b/validation.json','ci-attempts/ffa64ea98/validation.json'],native_performance='NOT_MEASURED',live_host_or_model='NOT_USED')
    save('ACCEPTANCE.json',value)
    big=rows['op-256-100k','records'];context=rows['op-256-100k','context']
    text=f'''# SQLite optimization review

Full audited operational reads on 256 rules / 100,000 events improved from {ms(big['baseline']['median'])} to {ms(big['candidate']['median'])} ms ({big['speedup']:.2f}×). Complete context API improved from {ms(context['baseline']['median'])} to {ms(context['candidate']['median'])} ms ({context['speedup']:.2f}×). These are Linux observations, not a whole-agent or Windows performance claim. All {len(bench['results'])+len(indexed['results'])} final paired API scenarios returned equivalent logical outcomes; raw samples, p95, writes, unchanged FS work and limits are in [BENCHMARK.md](BENCHMARK.md).

The selected outbox index is **opt-in**. Its extra quick_check pages slow unrelated journal reads/writes, so new journals default to no extra indexes. The normal initialization API can explicitly select it; existing journals require backed-up, exact-approved maintenance. Queue/status and plan/status indexes (ordinary and partial) were measured and excluded; existing primary keys already serve ID/composite-prefix lookups. [Index diagnostics](indexes/) use valid rows and validate after INSERT/UPDATE; SQL plan changes are not substituted for product results.

Operational history is read in bulk; records are mapped by ID; every authoritative event is validated and reduced once in rowid order. Current revisions reuse the already validated byte-identical last history entry. The view lives only inside one owned SQLite transaction, is invalidated before mutation and at transaction boundaries (including raw cursors/savepoints), and never trusts process-global file time/counts. Ordinary sqlite3 connections rebuild. Public records are detached copies. Queue identity hashes the already validated candidate once and duplicate lookup reuses audited exact TEXT/object comparisons, including predecessor IDs. Status reuses actions; capture reuses its final outbox. Existing Journal opening validates without DDL. All transaction modes, FULL sync, quick_check, foreign-key policy, leases/gates/fences and 150ms SQLite timeout are retained.

Arbitrary corruption detection remains linear in history/events/queues. Bulk history and queue reuse retain O(history + queue) data only within the transaction; events stream while only current signals/bindings are retained. RSS was not measured, so no memory-reduction claim is made. No history is shortened; no authoritative projection, model reinterpretation, new database, grants or auto-approvals are introduced. Project/shared isolation, revision-scoped binding sequences, insertion-ordered application signals, old-revision exclusion, current denials, scope transfer, P4 freshness/dependencies/diagnostic budgets and replay contracts remain covered. [ACCEPTANCE.json](ACCEPTANCE.json) maps DB-01…DB-20 to actual qualified tests/evidence.

## Exact source and qualification

Code commit: `{source['commit']}`. Source identity: `{source['source_identity']}`. Product stays 0.5.0rc1 with unchanged canonical formats; source and package hashes distinguish these bytes. ZIP SHA-256: `{package['zip_sha256']}`. [Kit](distribution/knowledge-harness-0.5.0rc1.zip), [RELEASE](distribution/RELEASE.json), [installed byte proof](candidate-install.json), [source map](source.json).

Linux: {tests['Linux']['passed']} PASS / {tests['Linux']['skipped']} native-only SKIP, {ci['platforms']['Linux']['commands']} qualification commands. Windows / native PowerShell 5.1: {tests['Windows']['passed']} PASS / {tests['Windows']['skipped']} SKIP, {ci['platforms']['Windows']['commands']} commands. These are installed full-kit runs from this exact source; every log/source/distribution asset hash is verified by [collect_ci.py](collect_ci.py) against Git and the delivered kit. [CI validation](ci/validation.json). No artifact code is executed during collection. The same existing setup/verify entrypoints run the full suite, predecessor migrations/recovery, automatic tests, SDK application, P4 delivery, standalone install, uninstall/reinstall and doctor contracts.

Earlier native attempts reported eight WinError 32 cleanup errors in new test fixtures: sqlite3 connection contexts commit but do not close handles. They are retained under [ci-attempts](ci-attempts/). The fixtures now close connections explicitly; no skip, GC/sleep workaround or weakened assertion was added. Superseded exploratory measurements are documented in [attempts.json](attempts.json) and excluded from final claims.

The [installed predecessor/candidate probe](compatibility/result.json) covers nonempty imported/pending/rejected/deferred candidates, prepared/committed/acknowledged plans, history, receipts and pending Harness state, actual older-writer index maintenance, same-root rollback/restore, hard process exits before/after index commit and before event commit, and bounded cross-process contention. [Knowledge-only probe](standalone/result.json) exercises project/shared reads and no-journal maintenance without Harness or MCP installed.

## Upgrade and rollback

Use the installed `knowledge-maintain index-upgrade-preview` / `index-rollback-preview`, inspect and save its preview object, then `apply` with its exact fingerprint. Both use the normal execution lease, exclusive gate, backup, canonical/source fingerprint, SQLite reservations and durable maintenance fence. `recover` idempotently finishes an interrupted operation; ordinary clients refuse the fence. Only the owned index is created/dropped; all canonical rows and source bytes are preserved. Older writers automatically maintain it. Dropping an index frees pages for reuse, not an automatic VACUUM. Normal same-root/same-OS restore of the retained backup is also verified. Shared Knowledge needs no schema/index migration. Full commands and compatibility limits: [packaged documentation](../../docs/P4/SQLITE-OPTIMIZATION.md).

Native performance, real OpenCode/model execution and real IPM/container deployment were not measured. The implementation, kit and independent checks do not require those services. No merge or deployment is included.
'''
    (P/'REVIEW.md').write_text(text)


if __name__=='__main__':main()
