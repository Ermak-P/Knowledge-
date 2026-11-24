"""Interleaved runs of identical immutable synthetic inputs; no owner project access."""
import hashlib,json,subprocess,sys
from pathlib import Path
repo=Path(__file__).resolve().parents[2];report=repo/"reports/CoreReliability";install=Path("/tmp/core-after-machine");current=json.loads((install/"current.json").read_text());after=install/current["runtime"]/"bin/python";before=Path("/tmp/knowledge-core-baseline-runtime/bin/python")
workload=repo/"scripts/core_reliability_workload.py"
records=[]
for number in range(1,4):
 for name,python in (("before",before),("after",after)):
  output=report/"benchmarks"/(name+"-final-clean-"+str(number));process=subprocess.run([str(python),str(workload),"--clean","--output",str(output)],cwd=repo,capture_output=True,text=True);(output/"driver.log").write_text(process.stdout+process.stderr);assert process.returncode==0;records.append({"profile":name,"run":number,"python":str(python),"result":str(output.relative_to(report)/"result.json")})
for name,python in (("before",before),("after",after)):
 output=report/"benchmarks"/(name+"-final-mixed");process=subprocess.run([str(python),str(workload),"--output",str(output)],cwd=repo,capture_output=True,text=True);(output/"driver.log").write_text(process.stdout+process.stderr);assert process.returncode==0;records.append({"profile":name,"run":"mixed","python":str(python),"result":str(output.relative_to(report)/"result.json")})
(report/"benchmarks/repetitions.json").write_text(json.dumps({"after_installation":current,"driver_sha256":hashlib.sha256(workload.read_bytes()).hexdigest(),"runs":records},indent=2)+"\n")
