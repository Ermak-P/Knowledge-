import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createServer } from 'node:http'
import { once } from 'node:events'
import { createHandoffJournal } from '../src/handoff-state.ts'
import { mountHandoffs } from '../src/handoffs.ts'

test('handoffs preserve actual order, repair reasons, task attempts and final host authority',()=>{
  let time=1000
  const j=createHandoffJournal({clock:()=>time++})
  j.start({runId:'r',sessionId:'lead',workspace:'repo'})
  j.enter('r',{agentId:'coding-1',role:'coding',taskId:'t',attempt:1})
  j.leave('r','coding-1',{status:'pass',detail:'code written'})
  j.enter('r',{agentId:'verify-1',role:'verification',taskId:'t',attempt:1})
  j.leave('r','verify-1',{status:'rework',detail:'assertion fails'})
  j.phase('r',{phase:'repair',taskId:'t',detail:'assertion fails'})
  j.enter('r',{agentId:'coding-2',role:'coding',taskId:'t',attempt:2,reason:'assertion fails'})
  let r=j.snapshot().runs[0]
  assert.equal(r.status,'running')
  assert.deepEqual(r.steps.map(s=>s.role),['coding','verification','coding'])
  assert.deepEqual(r.steps.map(s=>s.from),['lead','coding-1','verify-1'])
  assert.equal(r.steps[2].reason,'assertion fails');assert.equal(r.steps[2].attempt,2)
  j.finish('r','cancelled','user stopped')
  r=j.snapshot().runs[0]
  assert.equal(r.status,'cancelled');assert.equal(r.steps[2].status,'cancelled')
  assert.equal(r.steps[0].status,'pass')
  r.steps[0].role='mutated'
  assert.equal(j.snapshot().runs[0].steps[0].role,'coding')
})

test('history is bounded and failed cleanup cannot become completed',()=>{
  const j=createHandoffJournal({maxRuns:2,maxSteps:2})
  for(let n=0;n<3;n++)j.start({runId:'r'+n,sessionId:'lead',workspace:'repo'})
  assert.deepEqual(j.snapshot().runs.map(r=>r.id),['r2','r1'])
  for(let n=0;n<3;n++){j.enter('r2',{agentId:'a'+n,role:'coding'});j.leave('r2','a'+n,{status:n===2?'blocked':'pass',detail:n===2?'cleanup failed':''})}
  j.finish('r2','blocked','cleanup failed')
  const r=j.snapshot().runs[0]
  assert.equal(r.steps.length,2);assert.equal(r.totalSteps,3);assert.equal(r.truncated,true)
  assert.equal(r.status,'blocked');assert.equal(r.steps[1].status,'blocked')
})

test('observer serves only bounded read facts with a page capability and removes its route on unload',async t=>{
  const routes=new Map(),listeners=new Map(),cleanups=[]
  const ctx={effect(fn){const d=fn();if(d)cleanups.push(d)},on(name,fn){listeners.set(name,fn)},webServer:{register(route){routes.set(route.path,route);return ()=>routes.delete(route.path)}}}
  const j=createHandoffJournal();j.start({runId:'r',sessionId:'lead',workspace:'repo'})
  mountHandoffs(ctx,j)
  const table=[];listeners.get('webserver/index-inject')(table)
  assert.equal(table.length,1);assert.equal(table[0].kind,'script')
  assert.doesNotThrow(()=>new Function(table[0].text))
  const options=JSON.parse(table[0].text.slice(table[0].text.lastIndexOf(')(')+2,-2))
  const server=createServer((req,res)=>{const route=routes.get(req.url);if(!route){res.writeHead(404);res.end();return}route.handler(req,res)})
  server.listen(0,'127.0.0.1');await once(server,'listening')
  t.after(()=>{server.closeAllConnections();server.close()})
  const url='http://127.0.0.1:'+server.address().port+options.path
  assert.equal((await fetch(url)).status,403)
  assert.equal((await fetch(url,{headers:{'x-harness-handoff-token':'a'.repeat(63)+'x'}})).status,403)
  const headers={'x-harness-handoff-token':options.token}
  const response=await fetch(url,{headers})
  assert.equal(response.status,200);assert.equal(response.headers.get('cache-control'),'no-store')
  assert.equal((await response.json()).runs[0].id,'r')
  const etag=response.headers.get('etag')
  assert.equal((await fetch(url,{headers:{...headers,'If-None-Match':etag}})).status,304)
  j.phase('r',{phase:'planning',taskId:null})
  assert.equal((await fetch(url,{headers:{...headers,'If-None-Match':etag}})).status,200)
  assert.equal((await fetch(url,{method:'POST',headers})).status,405)
  for(const cleanup of cleanups.reverse())cleanup()
  assert.equal((await fetch(url,{headers})).status,404)
})
