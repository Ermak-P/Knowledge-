"""Current P3 review packet; unavailable native evidence cannot become Windows GO."""
import argparse,hashlib,json,re,subprocess,zipfile
from pathlib import Path
from p3_evidence import ROOT,OUT,save,sha,sources,validate_current,qualification,require_native,validate

def main():
    p=argparse.ArgumentParser();p.add_argument('--native-dir',type=Path);a=p.parse_args();v=validate_current();run=v['run_id'];base=OUT/'runs'/run
    tests=json.loads((base/'regressions/tests.json').read_text(encoding='utf-8'));assert tests['success'] and tests['preserved'] and tests['accepted_regressions']==138
    native=None;ci_files={};ci_status='NOT_RUN'
    if a.native_dir:
        collection=json.loads((a.native_dir/'collection.json').read_text(encoding='utf-8'));ci_status=collection['status']
        if ci_status=='PASS':
            native=json.loads((a.native_dir/'native.json').read_text(encoding='utf-8'));require_native(v,native)
            assert sha(a.native_dir/'native.json')==collection['receipt_sha256']
            native_root=Path(collection['native_root']);assert native_root.is_relative_to(a.native_dir)
            assert sha(native_root/'verification-summary.json')==collection['native_summary_sha256']
            native_ledger=json.loads((native_root/'verification-summary.json').read_text(encoding='utf-8'));validate(native_ledger,v['source_identity'],native_root)
            assert json.loads((native_root/'runs'/native_ledger['run_id']/'native/native.json').read_text(encoding='utf-8'))==native
        for path in a.native_dir.rglob('*'):
            if path.is_file() and path.suffix!='.tar':
                assert path.is_relative_to(OUT),'collected CI evidence must be under reports/P3';ci_files[path.relative_to(ROOT).as_posix()]=sha(path)
    if v['platform']['os']=='Windows':native=json.loads((base/'native/native.json').read_text(encoding='utf-8'))
    q=qualification(v,native);q['run_id']=run;q['ci_collection']=ci_status;save(OUT/'QUALIFICATION.json',q)
    native_links=[path for path in sorted(ci_files) if '/collected/'+v['commit']+'/Windows/' in path and (path.endswith('/native/native.json') or path.endswith('/verification-summary.json'))]
    spec={}
    for line in (ROOT/'tasks/Knowledge-Harness-P3-Codex-Task.md').read_text(encoding='utf-8').splitlines():
        if re.match(r'\| P3-A\d\d \|',line):parts=line.split('|');spec[parts[1].strip()]=parts[2].strip()
    mapping={
       1:['baseline/baseline.json','regressions/tests.json'],2:['distribution/knowledge-harness-0.3.0rc1/RELEASE.json','packaging/packaging.json'],3:['packaging/packaging.json'],4:['packaging/command.log','native/native.json'],5:['native/native.json','regressions/tests.json'],6:['native/native.json'],7:['native/native.json'],8:['regressions/tests.json'],9:['prior-upgrade/prior-upgrade.json'],10:['regressions/tests.json','prior-upgrade/prior-upgrade.json'],11:['prior-upgrade/prior-upgrade.json'],12:['regressions/tests.json','prior-upgrade/prior-upgrade.json'],13:['packaging/packaging.json','rehearsal/rehearsal.json'],14:['packaging/packaging.json','prior-upgrade/prior-upgrade.json'],15:['rehearsal/rehearsal.json'],16:['rehearsal/rehearsal.json'],17:['rehearsal/rehearsal.json'],18:['rehearsal/rehearsal.json','prior-upgrade/prior-upgrade.json'],19:['native/native.json'],20:['application/application.json','application/baseline.trx','application/original-immutability.json'],21:['native/native.json','regressions/tests.json'],22:['bounded/bounded.json','rehearsal/comparison.json','regressions/tests.json'],23:['native/native.json'],24:['regressions/tests.json','run.json'],25:['distribution/knowledge-harness-0.3.0rc1/RELEASE.json','reproducibility/reproducibility.json']}
    native_only={6,7,19};mixed={4,5,21}
    rows=[]
    for n in range(1,26):
        identifier=f'P3-A{n:02}';evidence=['runs/'+run+'/'+rel for rel in mapping[n]]
        for path in evidence:assert (OUT/path).is_file(),path
        windows='PASS' if q['profiles']['windows-3.12-x64-ntfs-ps51']['verdict']=='GO' else 'FAIL' if ci_status=='FAIL' else 'NOT_RUN'
        status=windows if n in native_only else 'PARTIAL' if n in mixed and windows!='PASS' else 'PASS'
        relevant=[r['test'] for r in tests['results'] if r['status']=='PASS' and ((n in (9,10,11,12,14) and 'test_p3_lifecycle.' in r['test']) or (n in (4,5,6,7,8,21) and 'test_p3_platform.' in r['test']) or (n==15 and 'test_p3_host.' in r['test']) or (n==24 and 'test_p3_evidence.' in r['test']))]
        rows.append(dict(id=identifier,requirement=spec[identifier],status=status,implementation='submitted for review',profiles={'linux':'NOT_APPLICABLE' if n in native_only else 'PASS','windows':windows},evidence=evidence,windows_evidence=native_links,tests=relevant))
    save(OUT/'ACCEPTANCE.json',dict(version=1,phase='P3',submission='submitted for external review',source_identity=v['source_identity'],run_id=run,product=v['product'],conditions=rows,qualification=q,unexecuted={'native_windows':q['profiles']['windows-3.12-x64-ntfs-ps51']['verdict']!='GO','live_model':'NOT_RUN','OpenCode':'NOT_RUN','PS7':'NOT_CLAIMED','private_MCP':'NOT_RUN','production_migration':'NOT_AUTHORIZED'}))
    app=json.loads((base/'application/application.json').read_text(encoding='utf-8'));assert app['outcome']['ok'] and int(app['before']['total'])==49 and app['after']['total']==50
    rehearsal=json.loads((base/'rehearsal/rehearsal.json').read_text(encoding='utf-8'));assert rehearsal['metadata_roundtrip_exact'] and rehearsal['conflict_preserved']
    native_detail=(f"Executed native profile: {native['platform']}; CI {native['ci']}. Exact-source/package receipts and raw native logs: {native_links}." if native else "No successful native receipt exists for this exact source/package. Missing native evidence blocks P3-A06/A07/A19 and the Windows portions of A04/A05/A21.")
    report=f'''# P3 submitted for external review

Accepted P2 `{ '91689475a283a2cdc654cfb6090074f0251f895d' }`, accepted source `4bb5fdfc0dabe64fee7087a29565549b40da6f2a8f32e203ed46f58883110416`; ordinary p3 branch from merged main `0245afda6ecf7b873839adba4be4772611717210`. Tested implementation commit `{v['commit']}`. The containing delivery Git commit identifies the final evidence submission; a file cannot embed its own commit hash. No dependency on a deleted p2 branch. Product version 0.3.0rc1; source `{v['source_identity']}`, current run `{run}`.

Implementation includes transferable reproducible core wheels/installers (same distribution names), independent Knowledge, native Windows file-lock/Job Object backend, Linux pidfd/group recovery, exact-approved consistent backup/restore/upgrade, staged fenced recovery, prior binary/data rollback, product-only uninstall/reinstall and project-local OpenCode v2 companion with enrolled tasks. Record/envelope schemas, Knowledge extension and Harness config/run versions stay distinct and unchanged. Unsupported root/state relocation and unverifiable process ownership refuse. No canonical approval is performed by the ordinary runner/maintenance.

Executed `.venv/bin/python -B scripts/verify_p3.py`: {tests['passed']} tests passed of {tests['tests_run']} discovered; {tests['skipped']} explicit native-only skips on this host. All 138 accepted logical regressions passed; five fork fixture setups choose native Windows spawn with the same assertions. Fresh wheels built twice yield identical normalized bytes. Core Knowledge/full installation transferred outside the checkout and ran with kernel connect denial on Linux; optional MCP installed from pinned online requirements and real configured stdio calls passed. Nonempty accepted P2 wheels generated records/relationships, histories, dispositions, prepared/committed-unacknowledged work, positive ownership, interrupted/completed runs and outbox. Current install/upgrade/restore, old code/data rollback and reinstall preserve those values; deliberate source drift delivers outbox but correctly blocks old final success.

Fresh installed-product UMUH-like rehearsal uses a distinct three-project domain/application/check layout and a new Unicode/spaced root, no development product imports/PYTHONPATH. Three independent .NET assertions fail before the Coding clamp fix and pass afterward. First capture, same-ID approved update/history, rejected/deferred repeat delivery, read-only abstention, actual edit/outbox process death, preserved user conflict, exact metadata restore/reinstall and two-root isolation passed. Shared-history versus isolated contexts include every role/attempt and synthetic usage; live efficiency/quality benefits NOT_ESTABLISHED. Larger fixture: 183 source files across three projects, bounded actual extraction and zero completed-resume duplication.

Pinned eShopOnWeb `{app['pin']}` with SDK `{app['sdk']}`: fresh restore/build, 49/49 baseline, the independent new regression fails before repair, then 50/50. Existing test source and original checkout are preserved; actual license, logs and TRX are included. No previous P2 application artifact is reused.

Implementation review: {q['implementation_review']}. Linux standalone profile: {q['profiles']['linux-3.12-x64']['verdict']}. Native Windows/NTFS/PowerShell 5.1 profile: **{q['profiles']['windows-3.12-x64-ntfs-ps51']['verdict']}**; CI evidence collection: {ci_status}. A workflow file/Linux result is not native proof. {native_detail} Exact native handoff: `powershell -NoProfile -File scripts/verify-windows.ps1`; ordinary task-branch workflow `.github/workflows/p3.yml`. Collected CI evidence must match exact source/wheel/check/runtime identities and every artifact hash. No required native skip is accepted as GO.

Optional live model/llama-server, live OpenCode, PS7 and private MCP are unexecuted/not claimed; synthetic HTTP decisions do not certify them. Real production IPM/UMUH migration, merge, registry publication and deployment were not performed. Package publication/license decisions remain owner-controlled; no new public license grant is invented. Practical limits: trusted host programs, lexical source coverage, root-bound state and explicit unsupported active cross-OS migration. Expected negative failures/conflicts are retained separately from passing mandatory checks.

Distribution: `runs/{run}/distribution/knowledge-harness-0.3.0rc1.zip` and its external SHA-256/RELEASE.json. Review: P3-review.zip, external checksum, ZIP-INVENTORY.json and packet-check.json. All 25 conditions and per-profile status: ACCEPTANCE.json/QUALIFICATION.json. Operational docs/runbook are included. P0/P1/P2 historical receipts remain unchanged.
'''
    (OUT/'P3-REPORT.md').write_text(report,encoding='utf-8')
    for path in (ROOT/'docs/P3').glob('*.md'):
        target=OUT/path.name
        if path.name not in ('P3-REPORT.md',):target.write_bytes(path.read_bytes())
    files=sources()
    for path in (OUT/'P3-REPORT.md',OUT/'ACCEPTANCE.json',OUT/'QUALIFICATION.json',OUT/'verification-summary.json',base/'run.json'):files[path.relative_to(ROOT).as_posix()]=sha(path)
    for path in (ROOT/'docs/P3').glob('*.md'):files['reports/P3/'+path.name]=sha(OUT/path.name)
    for c in v['checks'].values():
        for rel,h in c['artifacts'].items():files['reports/P3/'+rel]=h
    files.update(ci_files)
    inventory=dict(version=1,run_id=run,source_identity=v['source_identity'],product=v['product'],files=dict(sorted(files.items())))
    archive=OUT/'P3-review.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        def member(name,data):
            info=zipfile.ZipInfo(name,(2025,1,1,0,0,0));info.create_system=3;info.external_attr=0o100644<<16;info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,data,compresslevel=9)
        for rel,h in sorted(files.items()):assert sha(ROOT/rel)==h;member(rel,(ROOT/rel).read_bytes())
        member('ZIP-INVENTORY.json',(json.dumps(inventory,indent=2,ensure_ascii=False)+'\n').encode('utf-8'))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and set(z.namelist())==set(files)|{'ZIP-INVENTORY.json'}
        assert json.loads(z.read('ZIP-INVENTORY.json'))==inventory
        for rel,h in files.items():assert hashlib.sha256(z.read(rel)).hexdigest()==h,rel
    validate_current();(OUT/'P3-review.zip.sha256').write_text(sha(archive)+'  P3-review.zip\n',encoding='utf-8')
    save(OUT/'packet-check.json',dict(status='PASS',run_id=run,source_identity=v['source_identity'],archive_sha256=sha(archive),members_verified=len(files)+1,qualified_profiles=q['profiles']))
    print('PASS: 25 conditions/profile verdicts; '+str(len(files)+1)+' verified ZIP members. Windows '+q['profiles']['windows-3.12-x64-ntfs-ps51']['verdict'])
if __name__=='__main__':main()
