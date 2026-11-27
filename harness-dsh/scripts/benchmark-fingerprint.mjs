import { performance } from 'node:perf_hooks'
import { createWorkspaceFingerprint, projectRoot, gitFiles } from '../src/dotnet.ts'
import * as stalegreen from 'stalegreen'
import assert from 'node:assert/strict'
const root=projectRoot(process.argv[2]??process.cwd())
const iterations=Number(process.argv[3]??30),budget=Number(process.argv[4]??60000)
assert(Number.isInteger(iterations)&&iterations>=1&&iterations<=1000)
assert(Number.isInteger(budget)&&budget>=150&&budget<=60000)
const samples=[]
let metrics
const fingerprint=createWorkspaceFingerprint(root,stalegreen,budget,value=>{metrics=value})
for(let i=0;i<iterations+1;i++){
  const start=performance.now(),cpu=process.cpuUsage()
  const result=fingerprint()
  samples.push({index:i,elapsedMs:performance.now()-start,cpu:process.cpuUsage(cpu),rssBytes:process.memoryUsage().rss,available:result.available,reason:result.reason,metrics})
}
const warm=samples.slice(1).map(x=>x.elapsedMs).sort((a,b)=>a-b)
const q=p=>warm[Math.max(0,Math.ceil(p*warm.length)-1)]
console.log(JSON.stringify({root,node:process.version,platform:process.platform,paths:gitFiles(root).length,budgetMs:budget,firstMs:samples[0].elapsedMs,minMs:q(0),medianMs:q(.5),p95Ms:q(.95),maxMs:q(1),unavailable:samples.filter(x=>!x.available).length,samples},null,2))
if(samples.some(x=>!x.available))process.exitCode=1
