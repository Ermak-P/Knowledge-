# Knowledge + Harness - P4 independent review R2

Date: 2026-11-19.

Reviewed branch/commit: `p4` / `48a00bf55c57292876429c83c1ae6e631f0b4694`.

Tested implementation/CI commit: `7488de8c92e2f608c50fad828bc7222be2fc15f0`. Its recorded executable and verification inputs match the delivered revision.

Candidate: **0.4.0rc2**. Source identity: `9ba88b5fad87cd723a57e4aac114b7f5337465e6b427779047b67890865181aa`.

## Decision

**Not accepted yet: one remaining reproducible repair-routing case must be fixed.** The previous failures have substantially been corrected. This is a focused follow-up to P4-R3, not a request to redesign the agent architecture or repeat already completed implementation work.

Keep the completed corrections and verified guards. Fix the absent-but-authorized target case below, add its positive and negative regressions, self-review, and submit a fresh source/package-bound verification packet. Do not merge into main yet.

## Closure of the previous review

| Previous finding | Current result |
| --- | --- |
| P4-R1: P3 maintenance marker | Original independent probe now permits backup/upgrade/restore preview. Marked, unmarked and interrupted-prior-operation lifecycle evidence is supplied. Closed for the reproduced failure. |
| P4-R2: lost working state on rotation | Original discovered marker is present in the fresh context with a continuation reference. The new installed regression actually uses a discovered fact after rotation/process death. Closed for the reproduced failure. |
| P4-R3: final review forced into last item | Original two-existing-file probe now completes. Repair receives only Feature.cs; Other.cs is preserved. The absent-file variant below remains open. |
| P4-R4: Windows checkout/qualification | Real native CI now passes checkout and all required jobs. Closed for the reported checkout failure. |
| P4-R5: missing verification/evidence | All 15 IDs, real pinned .NET/TRX evidence, four comparison scenarios, lifecycle/concurrency and complete source inventories are supplied and checked. Closed for the previously reported omissions. |

## Independent verification

- Independently ran the complete installed suite: **206 discovered tests, 196 PASS, 10 native-Windows-only SKIP, zero failures/errors**, approximately 136 seconds on Linux.

- Installed the submitted 0.4.0rc2 package in a separate Python 3.12 environment outside the implementation checkout. Imported code resolves to that installed environment.
- Reran the previous independent HTTP/real-tool probes. The marker survives rotation, the earlier existing file is repaired under its own scope, and valid P3 maintenance preview no longer refuses the predecessor marker.
- Independently rebuilt the Linux distribution; its ZIP is byte-identical to the submitted Linux ZIP.
- Verified the review archive SHA-256, all **347 manifest entries** against archive/checkout bytes, and the recorded source inventory against the delivered revision. No mismatch found. The archive has 348 members including its manifest.
- Verified native CI [44398761177](https://github.com/Ermak-P/Knowledge-/actions/runs/44398761177) at the tested implementation commit: both Ubuntu and Windows jobs succeeded. Collected native tests show **206/206 PASS, zero skips**, Windows/NTFS, Python 3.12.10 AMD64, Windows PowerShell 5.1. Native source entries and available command-log hashes match.
- Verified fresh Linux and Windows .NET application evidence: pinned eShopOnWeb baseline **49/49**, the independent added regression **49 passed / 1 failed** before repair, final **50/50**, preserved existing tests and candidate-only capture. These are verified submitted/CI application runs, not a claim of a separate reviewer-local .NET application run.
- Independently reproduced the remaining absent-file problem with both compatible string findings and structured affected-item/path references. The product tools/processes/stores are real; no product behavior was patched into a failure or success.

Native and Linux release containers have different ZIP hashes, but their manifest file maps and both core wheel bytes match. The reviewer-local rebuild matches the Linux container. Keep the platform-specific container hashes explicit.

| Artifact | SHA-256 |
| --- | --- |
| Linux distribution ZIP | `4b452330ac4ac4803477cd386aa592352db757adf928b1dced2fee7084b5160e` |
| Native Windows distribution ZIP | `647cdc4a913ef21d3fba03ca4239eea594e5cd51408b61ee8a4216469d38d65a` |
| Knowledge wheel (both platforms) | `f95462a718298b86f31c25d5238416b2e9095632aec5dfbc96b55fac16b7d905` |
| Harness wheel (both platforms) | `debd954e7242c47326371ee9645a8b74e214d1b7c5ecaf39db0700180bf55062` |
| Review ZIP | `3f5ff69575ba7d16b4a6c93ebedaa44639674ba385afcad1af856bff8b5a6962` |

Current submitted run: `reports/P4/runs/718e79cb0dd24bc4a1f240047953dcb5/`.

## P4-R3 follow-up - HIGH: final review cannot request creation of an omitted authorized file

Location: `packages/harness/src/harness/p4.py`, `validate_affected()` and `route_review_repair()`.

Source: <https://github.com/Ermak-P/Knowledge-/blob/48a00bf55c57292876429c83c1ae6e631f0b4694/packages/harness/src/harness/p4.py>.

`validate_affected()` requires every review target path to already exist in `r['source']`. The compatible string-finding path resolver also searches only paths already present in that snapshot.

A target can be **explicitly authorized by the original task and immutable item scope while still absent from the current source tree**. An omitted new test/source file is a normal defect for final review to catch. Its absence is not a request for new authority.

Independent reproduction:

1. The authorized outer task permits Feature.cs and a new Missing.cs.
2. First item owns Feature.cs; second item owns Missing.cs. The second Coding attempt mistakenly finishes without creating its file. Existing tests remain green, which is precisely why independent final review is needed.
3. Final review reads Missing.cs, observes `file-not-found`, and rejects because the required file is absent.
4. With structured `affected: [{item: "missing", paths: ["Missing.cs"]}]`, the review tool returns **`invalid-review-paths`**.
5. With a compatible string finding naming Missing.cs, no owner is resolved because the path is absent from `r['source']`.
6. Both variants terminate with **`review-repair-target-required`**. Both items remain marked done; no corrective Coding attempt is created, and the required file remains absent.

The probe's provider is ready to create Missing.cs through a real scoped patch on the second attempt and to approve only after reading its actual contents. It never reaches that repair attempt on the reviewed candidate.

Observed result:

```json
[
  {
    "structured": false,
    "result": {"ok": false, "status": "failed", "error": "review-repair-target-required"},
    "file_exists": false,
    "item_attempts": [1, 1]
  },
  {
    "structured": true,
    "review_error": "invalid-review-paths",
    "result": {"ok": false, "status": "failed", "error": "review-repair-target-required"},
    "file_exists": false,
    "item_attempts": [1, 1]
  }
]
```

The run honestly fails rather than reporting false success. The remaining defect is inability to recover an ordinary, already-authorized omission through the advertised review/repair cycle.

### Required correction

- Resolve target authority from the original authorized task and immutable item scope, not solely from current file existence.
- Validate a missing path through the same project-root/path/private/protected-file rules used by real patches. Do not accept arbitrary missing paths merely because a reviewer named them.
- For structured findings, permit a validated absent target within that item's existing authority. No widened writable scope, new recipe authority or new user approval is needed for this case.
- For compatible string findings, resolve absent literal authorized paths when ownership is unambiguous. Preserve an explicit actionable stop for genuinely ambiguous ownership, unsupported pattern inference or a request outside the existing authority.
- Reopen only the relevant item. Preserve its prior attempt count and all run-wide repair/request/time/token counters; preserve independent final verification/review and candidate-only capture.
- Add a regression for an omitted new test file as well as the minimal source-file case. Demonstrate one real corrective creation, untouched unrelated item files, final passing gates and an independent approving review.
- Add negative cases for outside-item/new authority, traversal/absolute/private/protected paths and unsafe linked parents. The absence exception must not weaken broker policy.
- Update the acceptance matrix to include this boundary and regenerate exact-source verification/package/review artifacts.

## Measurement interpretation - not an additional blocker

The delivered comparison honestly shows a tradeoff. In the first-repeat multi-pressure fixture, largest Coding input falls from 23,708 to 15,710 bytes and aggregate input from 279,959 to 222,444 bytes, while calls rise from 24 to 25. In the multi-file fixture, calls and input increase. This does not establish universal token or speed savings; the current report correctly labels live benefit NOT_ESTABLISHED.

Do not change this task into a benchmark-tuning exercise. Preserve transparent whole-system accounting and address the concrete remaining repair defect.

## Focused resubmission

Implement this correction and its regressions, preserve the now-working R1-R5 corrections, rebuild the candidate, run the relevant installed checks and final required qualification, then provide one coherent updated review packet with exact commit/version/hashes and native CI provenance.

No merge, publication or production deployment is authorized by this review. No real UMUH/IPM or live-model correctness certification is implied.

## Appendix - executable independent reproduction

Save this block as `p4-missing-file-probe.py` outside the checkout. Run it with the installed candidate's Python 3.12 and the reviewed checkout's fixture directory:

```sh
python -I -B p4-missing-file-probe.py \
  --checkout /absolute/Knowledge-checkout \
  --output /absolute/missing-file-results.json
```

The reviewer executed it on Linux. Windows paths/PowerShell syntax must be supplied on native Windows; no reviewer-local Windows execution is claimed.

```python
import sys,tempfile,json,argparse
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--checkout',type=Path,required=True);p.add_argument('--output',type=Path,required=True);opts=p.parse_args()
sys.path.insert(0,str(opts.checkout.absolute()/'tests'))
from p2_fixtures import project,configuration,http_provider,calls,final
from test_p4 import p4task
from knowledge.util import loads
from harness.runtime import configure
from harness.engine import start,status

class MissingFile:
    def __init__(self,structured):self.turns={};self.structured=structured;self.seen=[]
    def decide(self,b):
        s=loads(b['messages'][0]['content']);role=s['runtime_role'];n=self.turns.get(s['agent'],0);self.turns[s['agent']]=n+1
        if role=='Main':
            if any(i['status']!='done' for i in s['ledger']['items']):return calls(('delegate',dict(role='Coding',assignment='Complete the active item')))
            if s['progress']['gates'].get('review',{}).get('verdict')=='approve':return final()
            return calls(('delegate',dict(role='Reviewing',assignment='Verify all acceptance criteria')))
        if role=='Coding':
            if s['writable']==['Missing.cs']:
                # Simulate an implementation omission that final review must repair.
                item=next(i for i in s['ledger']['items'] if i['id']=='missing')
                if item['attempts']==1:return final('Work item completed')
                if n==0:return calls(('read',dict(path='Missing.cs')))
                if n==1:
                    t=[loads(m['content']) for m in b['messages'] if m['role']=='tool'][-1]
                    return calls(('patch',dict(files=[dict(path='Missing.cs',before=t.get('sha256'),after='public class RequiredFeature {}\n')])))
                return final('Created the omitted authorized source file')
            if n==0:return calls(('read',dict(path='Feature.cs')))
            if n==1:
                t=[loads(m['content']) for m in b['messages'] if m['role']=='tool'][-1]
                return calls(('patch',dict(files=[dict(path='Feature.cs',before=t['sha256'],after='public class ImprovedFeature {}\n')])))
            return final()
        if role=='Reviewing':
            if n==0:return calls(('read',dict(path='Missing.cs')))
            if n==1:
                t=[loads(m['content']) for m in b['messages'] if m['role']=='tool'][-1]
                good=t.get('ok') and 'class RequiredFeature' in t.get('text','')
                args=dict(verdict='approve' if good else 'reject',findings=[] if good else ['Missing.cs is missing; create the already authorized required source file.'])
                if self.structured:args['affected']=[] if good else [dict(item='missing',paths=['Missing.cs'])]
                return calls(('review',args))
            self.seen.extend(loads(m['content']) for m in b['messages'] if m['role']=='tool')
            return final()
        return final()

rows=[]
for structured in (False,True):
    with tempfile.TemporaryDirectory() as tmp,http_provider(d:=MissingFile(structured)) as endpoint:
        root=project(tmp);task=p4task();task['writable']=['Feature.cs','Missing.cs'];task['acceptance']=['Feature.cs contains ImprovedFeature. Missing.cs must exist and declare RequiredFeature.'];task['items']=[dict(id='first',objective='Implement Feature',depends=[],writable=['Feature.cs']),dict(id='missing',objective='Create required Missing.cs',depends=['first'],writable=['Missing.cs'])]
        configure(root,configuration(endpoint),True);r=start(root,task);s=status(root,r['run_id'])
        rows.append(dict(structured=structured,result=r,file_exists=(root/'Missing.cs').exists(),items=[{k:i[k] for k in ('id','status','attempts','issues')} for i in s['run']['p4']['items']],review_actions=[a.get('result') for a in s['actions'].values() if a['tool']=='review']))
p=opts.output.absolute();p.write_text(json.dumps(rows,indent=2)+'\n');print(p.read_text())
```
