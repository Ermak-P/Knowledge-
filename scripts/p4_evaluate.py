"""Predeclared four-scenario comparison against the exact accepted P3 package."""
import hashlib,json,os,subprocess,sys,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from p2_fixtures import http_provider,configuration,task
from p4_comparison_fixtures import Scenario
SCENARIOS=[dict(name='simple',items=1,repeat=3,expected=True),dict(name='multi-file',items=2,repeat=3,expected=True),dict(name='multi-pressure',items=2,repeat=3,expected=True),dict(name='persistent-failure',items=1,repeat=1,expected=False)]
def save(path,v):path.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')
def main():
    kit=Path(sys.argv[1]).absolute();out=Path(sys.argv[2]).absolute();out.mkdir(parents=True,exist_ok=True)
    manifest=dict(version=2,scenarios=SCENARIOS,defined_before_execution=True,limits=dict(requests=64,context_bytes=24000,elapsed_seconds=600,turns_per_agent=16),pressure=dict(read_rounds=8,discovered_value=137,retained_across_items=True),provider='same synthetic HTTP policy; actual installed P3/P4; no model efficiency claim',differences='P3 has no item policy and delegates all files together; P4 narrows sequential items. Both retain the same final verification oracle and three-attempt bound. P4 explicitly declares build-only intermediate verification before the dependent file exists; the final item and any final repair must run all outer checks.')
    save(out/'scenario-manifest.json',manifest);rows=[]
    with tempfile.TemporaryDirectory(prefix='p4-comparison-') as tmp:
        base=Path(tmp);old=base/'old';old.mkdir();archive=ROOT/'reports/P3/runs/c72e6b4fcb41419cb5ff40a61a506466/distribution/knowledge-harness-0.3.0rc1.zip'
        assert hashlib.sha256(archive.read_bytes()).hexdigest()=='cf108d6ba7b49b42c8a81831abd9f72cdc999552cbd500cbef07ada9b0349338'
        with zipfile.ZipFile(archive) as z:z.extractall(old)
        oldkit=next(old.rglob('install.py')).parent
        for policy,bundle in [('P3',oldkit),('P4',kit)]:
            env=base/policy;p=subprocess.run([sys.executable,str(bundle/'install.py'),'install','--env',str(env)],capture_output=True);assert p.returncode==0,p.stdout
            py=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python');subprocess.run([str(py),'-m','pip','install','-r',str(ROOT/'requirements-dev.lock')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
            for scenario in SCENARIOS:
                name=scenario['name']
                for repeat in range(scenario['repeat']):
                    root=base/(policy+name+str(repeat));root.mkdir();(root/'Feature.py').write_text('def value():\n    return 0\n');(root/'Other.py').write_text('def value():\n    return 0\n');(root/'Notes.md').write_text('137\n');(root/'Large.py').write_text('# investigation evidence '+('x'*5000)+'\n')
                    (root/'build.py').write_text('import py_compile\npy_compile.compile("Feature.py",doraise=True)\npy_compile.compile("Other.py",doraise=True)\n')
                    expected=137 if name=='multi-pressure' else 2;multi=scenario['items']==2
                    (root/'test_independent.py').write_text('import unittest,Feature,Other\nclass IndependentBehavior(unittest.TestCase):\n def test_feature(self):self.assertEqual(Feature.value(),'+str(expected)+')\n'+(' def test_other(self):self.assertEqual(Other.value(),'+str(expected*2)+')\n' if multi else ''))
                    (root/'check.py').write_text('import unittest,json,os,sys\ns=unittest.defaultTestLoader.discover(".",pattern="test_*.py")\nr=unittest.TextTestRunner(verbosity=2).run(s)\nopen(sys.argv[1],"w").write(json.dumps(dict(action=os.environ["HARNESS_ACTION_ID"],executed=r.testsRun,failed=len(r.failures)+len(r.errors),skipped=len(r.skipped))))\nraise SystemExit(not r.wasSuccessful())\n')
                    d=Scenario(name,legacy=policy=='P3')
                    with http_provider(d) as endpoint:
                        c=configuration(endpoint);c['recipes']['build']['argv']=[str(py),'build.py'];c['recipes']['test'].update(argv=[str(py),'check.py','{artifacts}/checks.json'],result=dict(format='json',path='{artifacts}/checks.json'))
                        t=task('Feature.py');t['goal']='Implement Feature.value and Other.value according to the independent behavior oracle; preserve a value discovered by reading Notes.md.' if name=='multi-pressure' else 'Implement the independent behavior oracle without weakening existing tests.'
                        t['writable']=['Feature.py']+(['Other.py','test_created.py'] if multi else [])
                        if policy=='P4':
                            t.update(version=2,acceptance=[t['goal'],'All fixed verification and independent review must pass.'],items=[])
                            if multi:t['items']=[dict(id='feature',objective='Implement Feature',depends=[],writable=['Feature.py','test_created.py'],recipes=['build']),dict(id='other',objective='Implement Other',depends=['feature'],writable=['Other.py'])]
                        driver=base/'driver.py';driver.write_text('import json\nfrom harness.runtime import configure\nfrom harness.engine import start,status\nr='+repr(str(root))+'\nconfigure(r,'+repr(c)+',True)\nx=start(r,'+repr(t)+')\ns=status(r,x["run_id"])\nprint(json.dumps({"result":x,"run":s["run"],"metrics":s["metrics"]}))\n')
                        p=subprocess.run([str(py),'-I','-X','utf8',str(driver)],cwd=base,capture_output=True,text=True);assert p.returncode==0,p.stdout+p.stderr;v=json.loads(p.stdout)
                    requests=v['run']['requests'];m=v['metrics'];row=dict(policy=policy,scenario=name,repeat=repeat,correct=v['result']['ok'],expected=scenario['expected'],status=v['result']['status'],calls=m['requests'],input_bytes=sum(q['input_bytes'] for q in requests),max_coding=max((q['input_bytes'] for q in requests if q['role']=='Coding'),default=0),max_main=max(q['input_bytes'] for q in requests if q['role']=='Main'),reported_tokens=m['reported_tokens'],unknown_usage=m['unknown_usage_requests'],rotations=v['run'].get('p4',{}).get('rotations',0),elapsed=m['wall_seconds']);rows.append(row)
                    save(out/(policy+'-'+name+'-'+str(repeat)+'.json'),v)
                    # Retain failed results before asserting candidate correctness.
                    save(out/'results.json',dict(manifest_sha256=hashlib.sha256((out/'scenario-manifest.json').read_bytes()).hexdigest(),evidence='synthetic provider usage',rows=rows))
                    if policy=='P4':assert row['correct']==scenario['expected'],row
        oldmax=max(r['max_coding'] for r in rows if r['policy']=='P3' and r['scenario']=='multi-pressure');newmax=max(r['max_coding'] for r in rows if r['policy']=='P4' and r['scenario']=='multi-pressure');assert newmax<oldmax,dict(old=oldmax,new=newmax)
if __name__=='__main__':main()
