"""Seal current-source evidence without claiming unavailable native qualification."""
import hashlib,json,re,sys,zipfile
from pathlib import Path
from verify_p4 import ROOT,source

def main():
 folder=ROOT/'reports/P4';rid=sys.argv[1];run=folder/'runs'/rid;v=json.loads((run/'run.json').read_text())
 assert v['status']=='PASS_PORTABLE' and v['unchanged'] and v['source']==source(),'final source evidence required'
 log=(run/'regressions.log').read_text();count=re.search(r'Ran (\d+) tests',log).group(1)
 (folder/'IMPLEMENTATION.md').write_text('# P4 implementation\n\nProduct 0.4.0rc1; task v2/bounded-v1, run state v2; legacy v1 semantics retained. Plans, sequential Coding scopes, deterministic broker verifiers, source-bound independent review, fresh contexts and durable checkpoints/repair budgets are implemented in harness.p4 and engine. Complete new state remains inside the existing maintenance snapshot boundary.\n\nValidation: installed wheels outside checkout; '+count+' tests. See raw regression log for exact outcomes. Linux qualification only. No merge, push, release publication or production adoption performed.\n\nLimitations: post-start plan changes are refused rather than automatically replanned. Repair policy caps attempts across all failure families, a stricter bound than separate per-family budgets. Complete new crash-window and hostile-boundary coverage remains incomplete; this is not a fully qualified P4 release.\n')
 (folder/'ACCEPTANCE-MATRIX.md').write_text('''# Acceptance matrix

PASS means the named fixture or check executed, not production qualification.

| ID | Status | Evidence / limit |
|---|---|---|
| P4-01 | PASS | installed scoped edit, real build/test, independent fixture review; no attendance calls |
| P4-02 | PASS | two ordered items, separate Coding contexts, final gates |
| P4-03 | PASS | long fixture rotates, early acceptance retained, serialized cap enforced |
| P4-04 | PASS | irreducible input stops before HTTP |
| P4-05 | PASS | pressure fixture and owned real log range/hash retrieval |
| P4-06 | PASS | reviewer rejection and fake summary; accepted stale/source/parser regressions retained |
| P4-07 | PASS | three real failed attempts with one diagnosis; global counters retained |
| P4-08 | NOT_RUN | edit/receipt recovery tested; exhaustive new interruption windows not fully exercised |
| P4-09 | PASS | unknown request blocked without replay, one accounted attempt |
| P4-10 | NOT_RUN | scope/dependency/fake-summary checks pass; complete P4 hostile-input matrix not executed |
| P4-11 | NOT_RUN | P3 companion corrections pass; full P4 crossing-boundary matrix not executed |
| P4-12 | PASS | checksum-pinned accepted P3 package -> P4 -> same-root restore -> actual old code/data rollback |
| P4-13 | NOT_RUN | Linux processes/locks executed; native Windows unavailable; no CI run URL |
| P4-14 | NOT_RUN | no such scenario defined in task |

Release verdict: NO_GO pending missing required coverage and native qualification. Live model/OpenCode validation NOT_RUN. Post-start model replanning is unsupported (new task authorization required). No production readiness claim.
''')
 ev=json.loads((folder/'evaluation-final/results.json').read_text());rows=ev['rows'];text='# Synthetic evaluation\n\nExact accepted P3 archive versus installed P4. Reported tokens are fixture constants, not measured live-model use. Time is local wall time, not a general performance claim. Three repeats per positive scenario; raw rows retained.\n\n| Policy | Scenario | Correct runs | max Coding/Main bytes | calls | total input bytes | reported tokens | unknown usage | rotations | wall seconds |\n|---|---|---|---|---|---|---|---|---|---|\n'
 for policy in ('P3','P4'):
  for scenario in ('simple','pressure','failure'):
   rs=[r for r in rows if r['policy']==policy and r['scenario']==scenario];r=rs[0]
   text+=f"| {policy} | {scenario} | {sum(x['correct'] for x in rs)}/{len(rs)} | {max(x['max_coding'] for x in rs)}/{max(x['max_main'] for x in rs)} | {r['calls']} | {r['input_bytes']} | {r['reported_tokens']} | {r['unknown_usage']} | {r['rotations']} | {r['elapsed']:.3f} |\n"
 text+='\nFailure rows must remain non-success. Aggregate input/call values and elapsed time show the first repeat; maxima cover all repeats. Software fixtures establish bounded orchestration, not model quality. Live token/speed benefit NOT_ESTABLISHED.\n';(folder/'EVALUATION.md').write_text(text)
 (folder/'REVIEW-INDEX.md').write_text('# External review index\n\nFinal installed verification: runs/'+rid+'/run.json and regressions.log. Product distribution and SHA-256: same run/distribution/. Design and usage: docs/P4/. Accepted-package lifecycle: reports/P4/lifecycle-latest/. Synthetic comparison: reports/P4/evaluation-final/. Starting revision: STARTING-COMMIT.txt.\n\nThe manifest binds every included byte. Required native and adversarial/crash coverage gaps are explicit in ACCEPTANCE-MATRIX.md. This packet is for implementation review, not release approval.\n')
 files=[]
 for foldername in ('packages','tests','scripts','docs/P4','examples/p4','release/p4-kit','reports/P4'):
  for p in (ROOT/foldername).rglob('*'):
   if p.is_file() and not any(x in p.parts for x in ('__pycache__','build')) and not any(x.endswith('.egg-info') for x in p.parts) and p.name not in ('P4-review.zip','P4-review.zip.sha256','REVIEW-MANIFEST.json'):files.append(p)
 manifest={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(files))}
 (folder/'REVIEW-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n');files.append(folder/'REVIEW-MANIFEST.json')
 archive=folder/'P4-review.zip'
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
  for p in sorted(set(files)):z.write(p,p.relative_to(ROOT))
 (folder/'P4-review.zip.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  P4-review.zip\n')
 print(archive)
if __name__=='__main__':main()
