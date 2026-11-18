# Knowledge + Harness - P4 independent review R1

Date: 2026-11-18.

Repository: <https://github.com/Ermak-P/Knowledge->.

Reviewed branch/commit: `p4` / `293babd8dcec048272ec571d1805be8eae0fc3ae`.

Product: `0.4.0rc1`.

## Decision

**P4 is not accepted. Repair the blocking findings below and complete the required verification before requesting the next review. Do not merge to main.**

The implementation contains useful working progress: task-v2 work items, separate Coding contexts, real automatic recipe execution, independent review, finite retries, installed packages and preserved legacy paths. Its own regression suite passes. Those successes do not cover the independently reproduced failures or complete the original P4 assignment.

Continue on the P4 branch, implement the corrections autonomously, self-review them and submit one coherent fresh package/evidence packet. Preserve the accepted guards; do not solve a repair-routing problem by giving Coding the whole outer write scope or solve a maintenance refusal by deleting version markers.

## Independent verification completed

- Installed the submitted P4 wheels from the distribution kit into a separate Python 3.12 environment outside the implementation checkout. Imports resolve to the installed `0.4.0rc1` packages.
- Ran all **199 discovered tests: 189 PASS, 10 native-Windows-only SKIP, zero failures**, approximately 152 seconds on Linux. The 17 added P4 test methods pass along with the retained tests.
- Independently rebuilt the distribution with the submitted source identity. The release ZIP and RELEASE.json are byte-identical to the submitted artifacts.
- Verified review ZIP external SHA-256 and all **363 manifest entries** against archive content and checkout bytes; 364 archive members include the manifest. No mismatch found.
- Verified the final verification ledger's source entries against the checkout; no recorded-input mismatch found.
- Executed an independent clean Knowledge-only installation: Knowledge is usable and Harness is absent. This is positive independent evidence, not evidence that the submitted P4-14/P4-15 acceptance reporting is complete.
- Executed the independent HTTP/real-tool probes in Appendix A against the installed P4 package and the exact accepted P3 package. They reproduce R1-R3 below without patching product behavior.
- Inspected actual GitHub Actions run [44384715030](https://github.com/Ermak-P/Knowledge-/actions/runs/44384715030): Ubuntu job **success**; Windows job **failure during checkout**, before native tests. See R4.

Artifact identities:

| Artifact | SHA-256 |
| --- | --- |
| Distribution ZIP | `a36a363537c82709fb5b1c433971d82932ca5e6e29c62973898a86c7cb911ff8` |
| RELEASE.json | `1c55b82499552e89b441fe586c953fc4a8c4b65eb77c31d2b7bd52c2fa3f2218` |

Distribution: `reports/P4/runs/1048f54e8c134631b06bb69894063668/distribution/knowledge-harness-0.4.0rc1.zip`.

Submitted source identity: `cadeb2302f5a3dc6f19e5e16a58bad0f3f7494f448e8a81fc1a896ec3f5094cc`.

These fixture results establish software behavior. No live local model, real OpenCode session, private UMUH/IPM deployment or independent native Windows run was performed by the reviewer.

## P4-R1 - HIGH: a valid P3 maintenance marker blocks P4 backup, upgrade and restore

Location: [knowledge/maintenance.py, snapshot, line 125](https://github.com/Ermak-P/Knowledge-/blob/293babd8dcec048272ec571d1805be8eae0fc3ae/packages/knowledge/src/knowledge/maintenance.py#L125).

`snapshot()` accepts `.maintenance/product-state.json` only when its `product` equals the currently imported `__version__`. The package update changed that version to 0.4.0rc1 without adding a supported path for a valid 0.3.0rc1 marker.

Independent reproduction:

1. With the exact accepted P3 binaries, initialize/upgrade a Knowledge store.
2. Execute the supported P3 maintenance `upgrade` preview/apply. It creates a valid product-state marker with `product: 0.3.0rc1`.
3. Open the same root using the installed P4 maintenance implementation.
4. `backup-preview`, `upgrade-preview` and `restore-preview` all refuse with **`unsupported-maintenance-version`**.

The existing P4 lifecycle fixture covers a pre-P4 backup without this established product-state marker, so it does not catch the failure. This is a supported-predecessor compatibility gap, not an unsupported relocation request. The probe does not show data deletion; it shows loss of maintenance access on an otherwise valid upgrade.

Required correction:

- Implement an explicit version-aware supported P3 -> P4 maintenance transition and matching recovery/rollback semantics.
- Preserve marker/history bytes until the declared approved transition; unknown formats must still refuse safely.
- Test real prior binaries and stores both with and without prior completed maintenance operations/markers, including nonempty histories and pending state.
- Demonstrate backup, approved upgrade, restore and old-code/data rollback after the correction. Do not instruct users to delete the marker to bypass validation.

## P4-R2 - HIGH: rotation archives history but does not hand off the discovered working state

Location: [harness/p4.py, context, lines 54-74](https://github.com/Ermak-P/Knowledge-/blob/293babd8dcec048272ec571d1805be8eae0fc3ae/packages/harness/src/harness/p4.py#L54).

The context rotation stores `history` in an internal checkpoint, clears the live history and recursively builds a new request. That request carries original criteria/ledger and selected patch/recipe/review references, but no compact handoff of the active investigation, no checkpoint reference/retrieval interface and no references to earlier read/search results. The active-item handoff is written only after the item finishes.

Independent reproduction reads a unique discovered fact from Notes.md, then reaches rotation through ordinary read calls:

```json
{
  "rotations": 1,
  "marker_in_archived_checkpoint": true,
  "marker_in_first_rotated_request": false,
  "checkpoint_retrieval_reference_in_rotated_request": false,
  "new_context_message_roles": ["system"]
}
```

The original acceptance array does survive. The defect is the missing working-state handoff for facts, decisions and open investigation accumulated after task start. A raw archived transcript is not a usable continuation contract. The current early-requirement test checks a criterion already present in every system seed, so it does not establish preservation of newly discovered working state.

Required correction:

- At a safe boundary, persist a bounded continuation record describing the active objective, discovered facts/decisions, unresolved issues, next step and verified evidence references.
- Make that record and bounded authorized retrieval available to the fresh context. Preserve original criteria and runtime authority independently of untrusted narrative.
- Keep full transcripts as optional audit artifacts, not automatically concatenated context.
- Add a regression that depends on a fact/decision discovered during execution, survives rotation and interruption, and checks the actual behavior after continuation. A fixture hardcoded to succeed after rotation is insufficient.
- Measure boundedness and total accounting, including any checkpoint calls.

## P4-R3 - HIGH: final review repairs are forced into the last item's scope

Locations: [harness/p4.py, item/bind/scope](https://github.com/Ermak-P/Knowledge-/blob/293babd8dcec048272ec571d1805be8eae0fc3ae/packages/harness/src/harness/p4.py#L30), [engine.py, finish_p4_child, lines 320-338](https://github.com/Ermak-P/Knowledge-/blob/293babd8dcec048272ec571d1805be8eae0fc3ae/packages/harness/src/harness/engine.py#L320).

When all items are done, `item()` falls back to the last item. The final Reviewing frame is bound to that item. Any final rejection reopens that item and creates a Coding repair with its write scope, regardless of which earlier item/file needs correction.

Independent reproduction:

- First item owns Feature.cs; last item owns Other.cs. Both scopes are subsets of the originally authorized outer task.
- Final review correctly identifies missing behavior in Feature.cs.
- Every repair context receives only `writable: ["Other.cs"]`.
- The existing broker correctly rejects attempts to fix Feature.cs with **`edit-outside-task-scope`**.
- The run eventually fails with **`repair-exhausted`** while the affected first item remains marked done.

This is a routing defect. The write guard is doing the right thing and must not be weakened.

Required correction:

- Associate findings with the affected work item/paths and reopen the appropriate authorized item or a validated repair item with a strictly bounded subset of existing outer authority.
- Retain global attempt/no-progress limits, dependent-item validity and complete plan/review history.
- Invalidate/re-run final verification and independent review for the repaired final source.
- Demonstrate a two-item, two-file task where final review finds a problem in the first item and the bounded repair succeeds without touching the second item's unrelated files or requiring new scope authorization.
- If a finding genuinely requires new authority, stop explicitly; do not use that exception for an already authorized earlier file.

## P4-R4 - HIGH: native Windows CI regressed before execution

Workflow: [.github/workflows/p4.yml](https://github.com/Ermak-P/Knowledge-/blob/293babd8dcec048272ec571d1805be8eae0fc3ae/.github/workflows/p4.yml).

Actual run: [44384715030](https://github.com/Ermak-P/Knowledge-/actions/runs/44384715030).

- Ubuntu job 135085982927: success.
- Windows job 135085983458: failure at `Run actions/checkout@v4`.
- Log: **`Filename too long`**, followed by checkout exit code **128**, for tracked P3 evidence paths.

The accepted P3 workflow already supplied process-local Git long-path settings before checkout using `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_0=core.longpaths` and `GIT_CONFIG_VALUE_0=true`. The P4 workflow omitted that protection.

Required correction:

- Restore an equivalent safe checkout configuration without changing user/global Git settings.
- Run the installed P4 tests and required new process/checkpoint/repair/recovery scenarios on the actual native Windows runner.
- Include the new CI URL and exact package/source-bound results. A green Linux run or existence of YAML does not qualify Windows.
- Update the reports: a native runner was available and attempted the job; the observed condition is a checkout failure, not simply unavailable infrastructure.

## P4-R5 - HIGH: required validation and reproducible reporting are incomplete

The original assignment requires all P4-01 through P4-15 scenarios plus a real .NET behavioral rehearsal and an explicitly defined comparison matrix.

Observed gaps:

1. The delivered acceptance matrix stops at P4-13. P4-14 (independent Knowledge-only install) and P4-15 (cancellation/competing resume during new automatic verification/rotation) are required and must be tracked. The reviewer's independent Knowledge-only smoke is positive, but does not substitute for the missing installed-release verification route.
2. `scripts/make_review_p4.py` incorrectly emits **"P4-14 ... no such scenario defined in task"**, omits P4-15 and regenerates older NOT_RUN rows inconsistent with the checked-in matrix. Correct the generator as well as the generated documents.
3. No fresh real .NET application rehearsal evidence was found under reports/P4; `verify_p4.py` only builds/installs/runs Python regressions/doctor/uninstall. The accepted P3 .NET reports are historical and cannot qualify the changed P4 orchestration.
4. The submitted comparison has only `simple`, `pressure` and `failure`. It lacks the required distinct multi-file/test-related scenario and a genuinely multi-item context-pressure scenario with a retained discovered requirement/decision. Merely reading Large.cs repeatedly on one item is not that complete comparison.
5. P4-08 is explicitly incomplete. Finish the introduced interruption/ownership boundaries, including actual process death and the required competing resume/cancellation behavior. Retained P3 coverage does not automatically exercise new P4 transitions.
6. The source/evidence inventory omits active `.github/workflows/p4.yml` and `requirements-dev.lock`; the review archive also omits those inputs. Bind the active workflow/locked test dependencies and all other executed verification inputs to the final packet.

Required correction:

- Complete these original requirements and preserve the currently passing checks.
- Generate one consistent, final-source-bound run/acceptance matrix/review packet with all 15 IDs and exact executed evidence, without manual promotion of weaker tests to broader PASS claims.
- Keep synthetic provider decisions/usage clearly separated from live-model quality and token/speed claims.
- A qualification gap must remain NOT_RUN/NO_GO when genuinely blocked; do not label incomplete implementation verification as an accepted milestone.

## Required resubmission

1. Repair R1-R4 and add focused regressions using real installed product effects.
2. Complete R5, including the fresh .NET scenario, native CI and missing lifecycle/concurrency coverage.
3. Preserve independent source-bound review, scoped writes, recipe protection, unknown-outcome handling, all usage/budget counters and candidate-only capture.
4. Rebuild the package; rerun verification against the final executable inputs. Clearly identify the new candidate bytes, using a new candidate version or an explicitly tracked corrected unpublished candidate with exact hashes.
5. Regenerate the complete review packet, including fixed generators and scenario manifests. Report exact branch/commit, package hash, test counts, CI links, measured comparison and remaining explicit limits.

Do not delete data or old receipts to make compatibility tests pass. Do not weaken the write guard to fix R3, preload full histories to fix R2 or replace native execution with mocks to fix R4. No merge, publication or production adoption is authorized by this review.

## Appendix A - executable independent probes

Save the following block as `p4-review-probes.py` **outside the source checkout**. It uses the repository's fixture helpers to drive real installed effects; it does not import the product from source or patch the product into success.

Prerequisites:

- A Python 3.12 environment containing the submitted P4 wheels.
- A separate Python 3.12 environment containing the exact accepted P3 wheels from the checksum-pinned P3 archive in the P4 task.
- A checkout of the reviewed revision for test fixtures.

Run with the P4 environment's Python:

```sh
python -I -B p4-review-probes.py \
  --checkout /absolute/Knowledge-checkout \
  --prior-python /absolute/P3-runtime/bin/python \
  --output /absolute/p4-independent-probes.json
```

On Windows use its native `Scripts/python.exe` paths and PowerShell command syntax. The script was independently executed on Linux; native Windows execution is not claimed here.

Expected defective results before correction: R1 returns unsupported-maintenance-version for all three operations; R2 has a marker in the archived checkpoint but not in the rotated request; R3 denies Feature.cs repairs while repeatedly assigning Other.cs and stops repair-exhausted.

```python
import sys,json,tempfile,subprocess,argparse
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--checkout',type=Path,required=True)
parser.add_argument('--prior-python',required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
sys.path.insert(0,str(args.checkout.absolute()/'tests'))
from test_p4 import Decisions,p4task
from p2_fixtures import project,configuration,http_provider,calls,final
from harness.runtime import configure,Journal
from harness.engine import start,status
from knowledge.util import loads,canonical_json

OUT=args.output.absolute()
results={}

class Memory(Decisions):
    marker='DISCOVERED_INVARIANT_DO_NOT_DROP_89F1'
    def __init__(self):super().__init__();self.steps=0;self.coding_bodies=[]
    def decide(self,b):
        s=loads(b['messages'][0]['content'])
        if s['runtime_role']=='Coding':
            self.coding_bodies.append(b);self.steps+=1
            if self.steps==1:return calls(('read',{'path':'Notes.md'}))
            if self.steps<=5:return calls(('read',{'path':'Feature.cs'}))
        return super().decide(b)

with tempfile.TemporaryDirectory() as tmp,http_provider(d:=Memory()) as endpoint:
    root=project(tmp);(root/'Notes.md').write_text('Investigation: '+d.marker+'\n')
    configure(root,configuration(endpoint),True);r=start(root,p4task());s=status(root,r['run_id'])
    rotated=[b for b in d.coding_bodies if loads(b['messages'][0]['content']).get('epoch',0)>0]
    first=rotated[0]
    results['rotation_memory']={'result':r,'rotations':s['run']['p4']['rotations'],
      'marker_in_archived_checkpoint':d.marker in canonical_json(s['run']['p4']['checkpoints']),
      'marker_in_first_rotated_request':d.marker in canonical_json(first),
      'checkpoint_retrieval_reference_in_rotated_request':'checkpoints' in loads(first['messages'][0]['content']),
      'new_context_message_roles':[m['role'] for m in first['messages']]}

class EarlierItem:
    def __init__(self):self.turns={};self.rejected=False;self.repair_scopes=[]
    def decide(self,b):
        s=loads(b['messages'][0]['content']);role=s['runtime_role'];n=self.turns.get(s['agent'],0);self.turns[s['agent']]=n+1
        if role=='Main':
            if any(i['status']!='done' for i in s['ledger']['items']):return calls(('delegate',{'role':'Coding','assignment':'Do the active item'}))
            return calls(('delegate',{'role':'Reviewing','assignment':'Review all criteria'}))
        if role=='Coding':
            if self.rejected:
                self.repair_scopes.append(s['writable'])
                path='Feature.cs'
            else:path='Other.cs' if s['assignment']=='Create Other' else 'Feature.cs'
            if n==0:return calls(('read',{'path':path}))
            if n==1:
                ts=[loads(m['content']) for m in b['messages'] if m['role']=='tool']
                content='public class Other {}\n' if path=='Other.cs' else 'public class ImprovedFeature {}\n'+('// APPROVED_MARKER\n' if self.rejected else '')
                return calls(('patch',{'files':[{'path':path,'before':ts[-1]['sha256'],'after':content}]}))
            return final()
        if role=='Reviewing':
            if n==0:return calls(('read',{'path':'Feature.cs'}))
            if n==1:
                ts=[loads(m['content']) for m in b['messages'] if m['role']=='tool'];ok='APPROVED_MARKER' in ts[-1]['text'];self.rejected=not ok
                return calls(('review',{'verdict':'approve' if ok else 'reject','findings':[] if ok else ['Feature.cs must retain APPROVED_MARKER']}))
            return final()
        return final()

with tempfile.TemporaryDirectory() as tmp,http_provider(d:=EarlierItem()) as endpoint:
    root=project(tmp);(root/'Other.cs').write_text('public class InitialOther {}\n')
    (root/'test_feature.py').write_text('import unittest\nfrom pathlib import Path\nclass Behavior(unittest.TestCase):\n def test_class(self):self.assertIn("class ImprovedFeature",Path("Feature.cs").read_text())\nif __name__=="__main__":unittest.main()\n')
    t=p4task();t['writable']=['Feature.cs','Other.cs'];t['acceptance']=['ImprovedFeature exists and Feature.cs includes APPROVED_MARKER.']
    t['items']=[dict(id='first',objective='Implement Feature',depends=[],writable=['Feature.cs']),dict(id='last',objective='Create Other',depends=['first'],writable=['Other.cs'])]
    configure(root,configuration(endpoint),True);r=start(root,t);s=status(root,r['run_id'])
    denied=[{'path':a['args']['files'][0]['path'],'result':a['result']} for a in s['actions'].values() if a['tool']=='patch' and not a.get('result',{}).get('ok',False)]
    results['review_earlier_item']={'result':r,'repair_scopes':d.repair_scopes,'denied_patches':denied,'items':[{k:i[k] for k in ('id','status','attempts','issues')} for i in s['run']['p4']['items']],'final_feature':(root/'Feature.cs').read_text()}

with tempfile.TemporaryDirectory() as tmp:
    base=Path(tmp);root=base/'project';root.mkdir()
    old=args.prior_python
    script='''from pathlib import Path
from knowledge.store import Store
from knowledge import lifecycle as l,maintenance as m
root=Path(ROOT)
s=Store(root);s.init();l.upgrade(s,l.upgrade_preview(s)['fingerprint'])
p=m.preview(root,'upgrade',root.parent/'old-upgrade.zip');print(m.apply(root,p['preview'],p['fingerprint']))
'''.replace('ROOT',repr(str(root)))
    p=subprocess.run([old,'-I','-c',script],capture_output=True,text=True)
    from knowledge import maintenance as m
    from knowledge.util import KnowledgeError
    errors={}
    for op in ('backup','upgrade','restore'):
        try:m.preview(root,op,base/('next-'+op+'.zip'),base/'old-upgrade.zip',base/'recovery')
        except Exception as e:errors[op]={'type':type(e).__name__,'code':getattr(e,'code',str(e))}
    results['p3_maintenance_marker']={'old_exit':p.returncode,'old_stdout':p.stdout,'old_stderr':p.stderr,'marker':json.loads((root/'.maintenance/product-state.json').read_text()) if (root/'.maintenance/product-state.json').exists() else None,'p4_errors':errors}

OUT.write_text(json.dumps(results,indent=2)+'\n')
print(OUT.read_text())
```
