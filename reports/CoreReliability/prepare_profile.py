import cProfile,contextlib,io,pstats,runpy,sys,tempfile,json,time,statistics
from pathlib import Path
from knowledge.store import Store
from knowledge import lifecycle,discovery
source=Path(sys.argv[1]); namespace=runpy.run_path(str(source/"scripts/core_reliability_workload.py"))
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp)/"source";namespace["populate"](root,300)
 for name in ("00-invalid.json","01-utf16.xml","02-cp1251.xml","03-large.json"):(root/name).unlink()
 store=Store(root);store.init();lifecycle.upgrade(store,lifecycle.upgrade_preview(store)["fingerprint"])
 discovery.scan(store,max_files=1000)
 profiler=cProfile.Profile();profiler.enable();result=store.prepare();profiler.disable()
 assert result["ok"]
 samples=[]
 for _ in range(5):
  began=time.perf_counter();assert store.prepare()["ok"];samples.append(time.perf_counter()-began)
 with open(sys.argv[2],"w") as out:
  out.write(json.dumps({"prepare_seconds":samples,"median_seconds":statistics.median(samples)})+"\n")
  pstats.Stats(profiler,stream=out).strip_dirs().sort_stats("cumtime").print_stats(45)
