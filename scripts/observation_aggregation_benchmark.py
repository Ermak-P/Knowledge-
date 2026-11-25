"""Execute the actual scan aggregation block (or helper), with virtual observations."""
import argparse,ast,cProfile,hashlib,io,json,pstats,time,tracemalloc
from pathlib import Path
from knowledge import discovery


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--observations',type=int,default=12507);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    raw=a.source.read_bytes();tree=ast.parse(raw);scope=dict(vars(discovery))
    helper=next((n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='aggregate_observations'),None)
    if helper:module=ast.Module(body=[helper],type_ignores=[]);name='aggregate_observations'
    else:
        scan=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='scan')
        nodes=next(n for n in ast.walk(scan) if isinstance(n,ast.For) and isinstance(n.target,ast.Name) and n.target.id=='path' and any(isinstance(v,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='existing' for t in v.targets) for v in n.body)).body
        start=next(i for i,n in enumerate(nodes) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='existing' for t in n.targets))
        end=next(i for i,n in enumerate(nodes[start:],start) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Subscript) and isinstance(t.slice,ast.Constant) and t.slice.value=='ambiguous' for t in n.targets))
        name='aggregate_observations';fn=ast.FunctionDef(name=name,args=ast.arguments(posonlyargs=[],args=[ast.arg(arg=v) for v in ('state','observations','path','index')],kwonlyargs=[],kw_defaults=[],defaults=[ast.Constant(value=None)]),body=nodes[start:end+1],decorator_list=[]);module=ast.Module(body=[fn],type_ignores=[])
    exec(compile(ast.fix_missing_locations(module),str(a.source),'exec'),scope);aggregate=scope[name]
    def run(n):
        state={'observations':[],'ambiguous':[]};index={}
        for i in range(n):
            path='source'+str(i)+'.cs';o=dict(id='scan.'+str(i),project='.',category='declaration',statement='Synthetic declaration '+str(i),subject=str(i),path=path,line=1,anchor='class '+str(i),content_hash='synthetic')
            aggregate(state,[o],path,index)
        assert len(state['observations'])==n
        return state
    start=time.perf_counter();run(a.observations);elapsed=time.perf_counter()-start
    tracemalloc.start();run(min(3000,a.observations));peak=tracemalloc.get_traced_memory()[1];tracemalloc.stop()
    profile=cProfile.Profile();profile.runcall(run,min(3000,a.observations));profile.dump_stats(str(a.output/'profile.pstats'))
    stream=io.StringIO();pstats.Stats(profile,stream=stream).sort_stats('cumulative').print_stats(20);(a.output/'profile.txt').write_text(stream.getvalue())
    value=dict(synthetic_microbenchmark=True,actual_aggregation_ast=True,source_sha256=hashlib.sha256(raw).hexdigest(),observations=a.observations,seconds=elapsed,peak_tracemalloc_3000_bytes=peak,profile_observations=min(3000,a.observations))
    (a.output/'result.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value))


if __name__=='__main__':main()
