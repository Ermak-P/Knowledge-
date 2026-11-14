"""Build an allowlisted reproducible review packet and verify its inventory."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/P0'


def write(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')


def sha(data):return hashlib.sha256(data).hexdigest()


def source_files():
    files=[ROOT/'.gitignore',ROOT/'README.md',ROOT/'requirements-dev.lock',ROOT/'START-HERE.md']
    for folder in ('packages','scripts','tests','tasks','inputs'):
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and not any(part in ('__pycache__','build','dist') or part.endswith('.egg-info') for part in p.parts) and p.suffix!='.pyc':files.append(p)
    return sorted(set(files))


def main():
    summary=json.loads((OUT/'verification-summary.json').read_text());assert summary['status']=='PASS'
    benchmark=json.loads((OUT/'BENCHMARK-RESULTS.json').read_text());assert benchmark['retrieval_status']=='PASS'
    assert benchmark['source_unchanged'] and benchmark['isolation']=='PASS'
    migration=json.loads((OUT/'migration-results.json').read_text());assert migration['status']=='PASS'
    product=(OUT/'product-tests.log').read_text();match=re.search(r'Ran (\d+) tests',product)
    assert match and product.rstrip().endswith('OK') and 'FAILED (' not in product
    count=int(match[1]);assert count>=31
    assert 'standalone Knowledge CLI works without MCP/Harness' in (OUT/'packaging.log').read_text()
    base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    inventory={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in source_files()}
    tree=sha(json.dumps(inventory,sort_keys=True).encode())
    write('SOURCE-REVISION.json',{'base_git_revision':base,'delivery':'uncommitted working tree; no automatic commit/push',
                                'source_tree_sha256':tree,'files':inventory})
    mappings=[
      ('Fresh wheels and dependency-free CLI','scripts/check_packaging.py','packaging.log'),
      ('Clean store and packaged schemas','tests/test_core.py:CoreTests.test_init_and_version_cli','product-tests.log'),
      ('Evidence identity/provenance pipeline','tests/test_core.py:CoreTests.test_end_to_end_identity_provenance','product-tests.log'),
      ('Submission/apply/ack retries and normalized dedup','tests/test_core.py:CoreTests.test_duplicate_retry','product-tests.log'),
      ('Shared-lock exclusion and competing normalized writers','tests/test_core.py:CoreTests.test_busy_all_mutations; CoreTests.test_competing_writers','product-tests.log'),
      ('Malformed, unsafe, corrupt and stale input refusal','tests/test_core.py:CoreTests.test_bad_candidates; test_json_restrictions; test_stale_and_wrong_approval; test_corrupt_queue_refused; test_damaged_plan_refused','product-tests.log'),
      ('Real process crashes, ownership-bound recovery, unrelated edits','tests/test_core.py:CoreTests.test_crash_boundaries; test_changed_committed_payload_preserved; test_ack_payload_not_just_id; test_init_crash_before_and_after_publication','product-tests.log'),
      ('Nonempty semantic/byte migration and queue-ID/status preservation','scripts/migration_evidence.py; tests/test_core.py:MigrationTests','migration-results.json'),
      ('Missing plans, stale migration and dual-store diagnosis','tests/test_core.py:MigrationTests.test_incomplete_and_dual_store; test_stale_and_ambiguous_target','product-tests.log'),
      ('Two roots, spaces/non-ASCII, links/escape and copied identity','tests/test_core.py:CoreTests.test_roots_links_and_escape; test_copied_store_identity; tests/test_mcp.py','product-tests.log'),
      ('Actual CLI/MCP agreement, confidence/conflicts and output bounds','tests/test_mcp.py; tests/test_core.py:CoreTests.test_budget_no_answer_and_unconfirmed','product-tests.log'),
      ('Harness with data, absent store, corruption and configured budget','tests/test_core.py:CoreTests.test_harness_absence_and_corruption; test_harness_configuration_budget; test_end_to_end_identity_provenance','product-tests.log'),
      ('Static active-code machine-default/execution-path check','tests/test_legacy_reference.py:LegacyReferenceTests.test_active_code_has_no_machine_default_or_worktree_execution','product-tests.log'),
      ('Full portable P0 entry point; native/live subchecks separate','scripts/verify.py','verification-summary.json'),
      ('Allowlisted source/review archive and verified per-file hashes','scripts/make_review.py','packet-check.json'),
      ('Pinned build + 49 tests before/after, 15 records + nine queries, source unchanged','scripts/verify.py; scripts/benchmark.py','BENCHMARK-RESULTS.json'),
    ]
    rows=[]
    for i,(explanation,command,evidence) in enumerate(mappings,1):
        rows.append({'id':f'P0-A{i:02}','status':'PASS','command':command,'evidence':f'reports/P0/{evidence}','explanation':explanation})
    rows[13]['platform_subchecks']=[{'name':name,'status':'NOT_RUN','command':'powershell -File scripts/verify-windows.ps1' if name=='native Windows/NTFS' else 'No supported live executor is delivered in P0; external integration acceptance belongs to a separate task.'} for name in ['native Windows/NTFS','live OpenCode/model']]
    rows[15]['optional_subchecks']=[{'name':'browser assets/UI, SQL Server, Aspire/containers, Azure','status':'NOT_RUN','explanation':'Not required by P0; CDN browser downloads blocked. No real identity/database deployment attempted.'}]
    write('ACCEPTANCE.json',rows)
    (OUT/'P0-REPORT.md').write_text(f'''# P0 implementation report

P0 is ready for external review for the tested portable Linux workflow.
All 16 portable acceptance conditions have executable passing evidence.
This is not certification of the complete product or a production Windows release.

## Delivered source and checks

Source: product checkout `/workspace/Knowledge-`, working tree over `{base}`.
Source content identity: `{tree}`; per-file hashes in SOURCE-REVISION.json.
No automatic Git commit, push, publication or production mutation was performed.

```sh
bash scripts/setup.sh
.venv/bin/python scripts/setup_benchmark.py
.venv/bin/python scripts/verify.py
.venv/bin/python scripts/make_review.py
```

This instance reused the verified SDK with
`.venv/bin/python scripts/setup_benchmark.py --sdk-dir /workspace/dotnet`.
The complete verification entry point ran successfully after final product fixes.
Python 3.12.14, SQLite from Python's standard library, MCP 1.30.0, .NET {summary['sdk']}.

- {count} product tests passed, no skips in this Linux run; real MCP stdio sessions
  and controlled subprocess crashes/concurrent writers included.
- Both packages built as wheels; Knowledge installed and initialized/validated
  in a fresh venv without MCP or Harness.
- Synthetic legacy migration preserved exact records, candidate IDs/statuses,
  history and source bytes. Backup restore was byte-equal. Incomplete journal,
  dual-store, repeat and interruption scenarios passed.
- Pinned eShopOnWeb build and 49 existing unit tests passed with integration
  absent, then 49 passed after integration, zero failures/skips. Current-run TRX
  files and counters are retained. Tracked application source diff is empty.
- {benchmark['record_count']} curated source-anchored records traversed the real writer/import/ack
  pipeline. Nine CLI/MCP query expectations passed; Harness retained expected
  first-ranked support and the no-answer case. Full result lists are retained
  so lexical extras can be inspected; this is not a broad accuracy metric.

## Behavior and review decisions

Before: an incomplete project-local legacy installer, no delivered candidate
writer/Harness, and no independent package or supported recovery workflow.
After: reusable Knowledge/Harness packages with explicit project identity;
standalone CLI, optional read-only MCP, coordinated durable candidate queue,
exact-fingerprint approval, atomic canonical/journal commit, payload-bound
acknowledgment/recovery, bounded provenance-bearing retrieval and offline
lossless fixture migration. Project data contains no duplicated executable tools.

Legacy schema bytes and semantic validator/ranking were retained. SQLite
replaced multi-file application transactions to provide testable atomicity
across canonical data and import journal. Full source map/call graph is in
SOURCE-AUDIT.md; storage/permission/error guarantees in CONTRACTS.md.

Self-review traced submission through every shipped public entry point and
checked immutable payload binding, normalized duplicate races, root isolation,
missing-plan assessment, packaging and byte bounds. Review found and fixed a
publication crash gap by replacing a two-link step with atomic directory
publication, and tightened actual legacy journal layout/seal checks. Migrated
candidate IDs now remain stable in the operational queue as well as history.
All affected tests and the full required verification were rerun successfully.

## Limits and diagnosed initial failures

The original ZIP's installer expects missing operational docs. Its unmodified
baseline failed at that packaging prerequisite; the new package has its own
complete documented installation. No historical docs or results were fabricated.
The old transaction/writer interfaces are not blindly promised compatible.

.NET initially needed permission for OS mutexes. A multi-node build failed;
one node/no shared compilation succeeded. Optional LibMan browser downloads
were blocked by proxy HTTP 403. The supported `LibraryRestore=false` switch
omits those assets for the .NET build/unit baseline without modifying upstream
source or tests. Browser/UI behavior is not claimed. Upstream NuGet vulnerability
warnings are retained in raw logs; pinned dependencies were not silently upgraded.
No TLS, signature or checksum verification was disabled.

Native Windows/NTFS, Windows junction/locking behavior, real OpenCode/live model,
browser UI, SQL Server, full Aspire/containers and Azure checks are NOT RUN.
Windows reproduction commands are supplied; portable results do not certify
native behavior. Live executor/provider integration is outside delivered P0;
there is no code-changing runner to validate. No required portable check remains
failed or blocked. P1 lifecycle/discovery and P2/P3 work were not started.

## Review packet

`reports/P0/P0-review.zip` contains source, tests, reproducible setup/verification,
input archive, docs, acceptance results, source checksums, curated generated
artifacts and raw evidence. It excludes credentials, caches, SDK/package files,
private runtime settings and upstream application source. The MIT upstream
license is included. REVIEW-INVENTORY.json lists every archive member/hash;
packet-check.json verifies archive integrity and byte-level inventory equality.
''')
    (OUT/'CHANGE-SUMMARY.md').write_text('''# Meaningful change summary

- Added independently installable Knowledge and minimal read-only Harness packages.
- Retained schema bytes, semantic validation and lexical ranking from supplied source.
- Added explicit root identity, single SQLite writer protocol, versioned candidates,
  fingerprinted approvals, import/ack journal and crash/ownership recovery.
- Added offline migration preserving canonical values and original queue identity/state,
  sealed-history assessment and byte-preserving source restoration.
- Added read-only MCP tools and bounded Harness integration with explicit degradation.
- Added controlled concurrency/crash/migration/isolation tests, dependency-free packaging
  verification and differential checks against archived ranking.
- Added pinned SDK/benchmark setup and source-anchored real application regression.
- Added acceptance/report/inventory/ZIP generation with no automatic commits.

Source identity: SOURCE-REVISION.json. Full source is included in the review ZIP;
its inventory distinguishes new working-tree files from the unchanged input archive.
''')
    (OUT/'STATUS.md').write_text(f'''# P0 status

Complete for external review of tested portable Linux P0. {count} product tests,
49 pinned application unit tests without integration and 49 after integration,
15 source-anchored records and nine retrieval expectations passed.
All 16 portable acceptance rows PASS. Native Windows/live-provider/UI/database
subchecks explicitly NOT RUN. P1 was not started. See P0-REPORT.md and ACCEPTANCE.json.
''')
    # Include only explicit source roots and this public evidence directory.
    files=source_files()
    for p in OUT.rglob('*'):
        if p.is_file() and p.name not in ('P0-review.zip','REVIEW-INVENTORY.json','packet-check.json','P0-review.zip.sha256'):
            files.append(p)
    files=sorted(set(files))
    write('packet-check.json',{'status':'PASS','archive':'reports/P0/P0-review.zip',
        'verification':'Generator verifies CRC and every member against REVIEW-INVENTORY.json before successful exit.',
        'members':len(files)+2,'source_tree_sha256':tree,'archive_checksum_file':'P0-review.zip.sha256'})
    files.append(OUT/'packet-check.json')
    files=sorted(files)
    inventory=[{'path':str(p.relative_to(ROOT)),'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size} for p in files]
    write('REVIEW-INVENTORY.json',inventory)
    packet=OUT/'P0-review.zip'
    with zipfile.ZipFile(packet,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in files+[OUT/'REVIEW-INVENTORY.json']:
            info=zipfile.ZipInfo(str(p.relative_to(ROOT)),date_time=(2026,11,14,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            z.writestr(info,p.read_bytes())
    with zipfile.ZipFile(packet) as z:
        assert z.testzip() is None
        expected={e['path']:e for e in inventory}
        assert set(z.namelist())==set(expected)|{'reports/P0/REVIEW-INVENTORY.json'}
        for path,item in expected.items():
            data=z.read(path);assert sha(data)==item['sha256'] and len(data)==item['bytes']
    (OUT/'P0-review.zip.sha256').write_text(sha(packet.read_bytes())+'  P0-review.zip\n')
    print(f'PASS: {count} product tests; 16 acceptance rows; verified review ZIP ({len(files)+1} members)')


if __name__=='__main__':main()
