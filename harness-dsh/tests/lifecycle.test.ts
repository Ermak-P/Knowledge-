// Test doubles only. These do not validate npm/DSH compatibility or upstream algorithms.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import * as core from '../src/lifecycle.ts'

import { mockLibraries } from './mock-libraries.ts'

function fixture(core){
  let version=1,available=true
  const fingerprint=()=>({available,tree:available?'tree-'+version:null})
  const lib=mockLibraries(),book=new core.EvidenceBook(lib,fingerprint)
  const task=(id,kind='build',tdd=false)=>({id,objective:'implement '+id,codingFiles:[id+'.cs'],testFiles:tdd?['Tests/'+id+'Tests.cs']:[],tdd,criteria:[{id:'ac',desc:'expected result',kind,target:kind==='test'?'Tests/UnitTests.csproj':kind==='review'?id+'.cs':'App.csproj'}]})
  const add=(t)=>book.add(t,'run','root',[{kind:'user-message',eventRef:'root:1',seq:1,text:'request'}])
  const capture=(s,outcome='pass',options={})=>{
    const kind=s.task.criteria[0].kind
    const value={kind,outcome,exitCode:outcome==='pass'?0:1,passed:outcome==='pass'?1:0,failed:outcome==='fail'?1:0,skipped:0,exists:outcome==='pass',summary:outcome,fingerprint:fingerprint(),...options.value}
    return book.capture({role:options.role??'coding',taskId:s.task.id,agentId:options.agent??'coder',sessionId:options.session??'child-A'},{callId:'call-'+(book.seq+1),name:'harness_run_check',arguments:options.args??{criterion_id:'ac'},isError:options.isError??false,value})
  }
  return {book,lib,task,add,capture,fingerprint,edit:()=>version++,unavailable:()=>{available=false},available:()=>{available=true}}
}

async function lifecycleCases(core,check){
  const cases=[]
  const run=async(name,fn)=>{try{await fn();cases.push({name,pass:true})}catch(e){cases.push({name,pass:false,error:String(e)})}}
  const status=async(f,s,expected)=>check.equal((await f.book.evaluate(s)).status,expected)
  await run('plan rejects duplicates, overlap, empty plan and invalid TDD',()=>{
    const f=fixture(core),t=f.task('one')
    check.throws(()=>core.validatePlan({tasks:[]}));check.throws(()=>core.validatePlan({tasks:[t,t]}))
    check.throws(()=>core.validatePlan({tasks:[{...t,testFiles:t.codingFiles}]}))
    check.throws(()=>core.validatePlan({tasks:[{...t,tdd:true}]}))
    check.equal(Object.isFrozen(core.validatePlan({tasks:[t]})[0].criteria),true)
  })
  await run('independent immutable contracts; missing and cross-task evidence blocked',async()=>{
    const f=fixture(core),a=f.add(f.task('a')),b=f.add(f.task('b'))
    check.notEqual(a.identity.contractId,b.identity.contractId);check.equal(Object.isFrozen(a.contract),true)
    await f.capture(a);await status(f,a,'pass');await status(f,b,'blocked')
    b.refs.push(...a.refs);await status(f,b,'blocked')
  })
  await run('wrong tool args and unauthorised role cannot satisfy selector',async()=>{
    const f=fixture(core),a=f.add(f.task('a'))
    await f.capture(a,'pass',{args:{criterion_id:'ac',extra:'different'}});await status(f,a,'blocked')
    await f.capture(a,'pass',{role:'planning'});await status(f,a,'blocked')
    await f.capture(a);await status(f,a,'pass')
  })
  await run('later failed result in another session supersedes older pass',async()=>{
    const f=fixture(core),a=f.add(f.task('a'))
    await f.capture(a,'pass',{session:'one',agent:'coder'});await status(f,a,'pass')
    await f.capture(a,'fail',{session:'two',agent:'verifier',role:'verification'});await status(f,a,'fail')
    check.equal(a.refs.at(-1).producerSessionId,'two')
    await f.capture(a,'pass',{session:'three'});await status(f,a,'pass')
  })
  await run('capture failure overrides previous success',async()=>{
    const f=fixture(core),a=f.add(f.task('a'))
    await f.capture(a);await f.capture(a,'pass',{isError:true});await status(f,a,'blocked')
  })
  await run('stale or unavailable fingerprint fails closed',async()=>{
    const f=fixture(core),a=f.add(f.task('a'))
    await f.capture(a);await status(f,a,'pass');f.edit();await status(f,a,'blocked')
    await f.capture(a);await status(f,a,'pass');f.unavailable();await status(f,a,'blocked')
  })
  await run('zero tests, skips and inconsistent exit cannot pass',async()=>{
    const f=fixture(core),a=f.add(f.task('a','test'))
    await f.capture(a,'pass',{value:{passed:0,failed:0}});await status(f,a,'blocked')
    await f.capture(a,'pass',{value:{skipped:1}});await status(f,a,'blocked')
    await f.capture(a,'pass',{value:{exitCode:3}});await status(f,a,'blocked')
    await f.capture(a);await status(f,a,'pass')
  })
  await run('missing blob does not fall back to previous success',async()=>{
    const f=fixture(core),a=f.add(f.task('a'))
    await f.capture(a);await f.capture(a);await f.book.store.delete(a.refs.at(-1).blobHash);await status(f,a,'blocked')
  })
  await run('semantic judgement requires independent observed target and freshness',async()=>{
    const f=fixture(core),a=f.add(f.task('a','review'))
    await status(f,a,'blocked')
    const r={criteria:[{id:'ac',verdict:'pass',detail:'actual behavior meets expected',paths:['a.cs']}]}
    check.throws(()=>f.book.recordSemantic(a,r,[],f.fingerprint(),{agentId:'v'}))
    f.book.recordSemantic(a,r,['a.cs'],f.fingerprint(),{agentId:'v'});await status(f,a,'pass')
    f.edit();await status(f,a,'blocked')
  })
  function scenario(opts={}){
    const f=fixture(core),events=[],calls=[],signal={aborted:false},counts=new Map()
    const tasks=opts.tasks??[f.task('a'),f.task('b')]
    const host={
      progress:e=>events.push(e),validate:async()=>{},changes:async()=>({paths:[],diff:''}),
      async check(s,c){calls.push('check:'+s.task.id);await f.capture(s,opts.checkOutcome?.(s)??'pass',{role:'host'})},
      async spawn(role,s,extra){
        calls.push(role+':'+(s?.task.id??'root'))
        const key=role+':'+(s?.task.id??'root');counts.set(key,(counts.get(key)??0)+1)
        if(role==='planning')return {structured:{tasks}}
        if(role==='coding'){if(opts.cancel){signal.aborted=true;return {structured:{verdict:'pass',detail:'cancelled'}}}f.edit()}
        if(role==='verification')return {structured:{verdict:'pass',detail:'reviewed',criteria:s.task.criteria.filter(c=>c.kind==='review').map(c=>({id:c.id,verdict:'pass',detail:'expected matches actual',paths:[c.target]}))},observedPaths:s.task.criteria.map(c=>c.target),fingerprint:f.fingerprint(),producer:{agentId:'verifier'}}
        if(role==='reviewing'){const verdict=opts.review?.(counts.get(key),f)??{verdict:'pass',detail:'approved',issues:[]};return {structured:verdict,fingerprint:f.fingerprint()}}
        return {structured:{verdict:'pass',detail:'ok',expectedFailures:[{name:'T',message:'expected'}]}}
      },
      baseline:async()=>({comparable:true}),red:async()=>({valid:opts.red!==false,reason:'invalid RED'}),green:async(s)=>({status:opts.green?.(s)??'pass',reason:'green'}),checkTdd:()=>opts.tddCurrent!==false
    }
    const execute=()=>core.runEngineering(host,f.book,'request',[{kind:'user-message',eventRef:'root:1',seq:1,text:'request'}],'r','root',signal,opts.maxAttempts??3)
    return {f,events,calls,counts,execute}
  }
  await run('two tasks, deterministic checks, stale earlier task refreshed, no redundant verifier LLM',async()=>{
    const x=scenario();const r=await x.execute();check.equal(r.status,'completed')
    check.equal(x.counts.get('coding:a'),1);check.equal(x.counts.get('coding:b'),1)
    check.equal(x.calls.filter(c=>c==='check:a').length,2)
    check.equal(x.calls.filter(c=>c.startsWith('verification:')).length,0)
    check.equal(x.counts.get('reviewing:root'),1)
  })
  await run('targeted failed task repair and bounded attempts',async()=>{
    const x=scenario({checkOutcome:s=>s.task.id==='b'&&s.attempts===1?'fail':'pass'});const r=await x.execute()
    check.equal(r.status,'completed');check.equal(x.counts.get('coding:a'),1);check.equal(x.counts.get('coding:b'),2)
  })
  await run('persistent failure stops at repair cap, no false review',async()=>{
    const x=scenario({checkOutcome:()=> 'fail',maxAttempts:2});const r=await x.execute()
    check.equal(r.status,'blocked');check.equal(x.counts.get('coding:a'),2);check.equal(x.counts.get('reviewing:root'),undefined)
  })
  await run('infrastructure failure blocks instead of success or repair loop',async()=>{
    const x=scenario({checkOutcome:()=> 'unverified'});const r=await x.execute()
    check.equal(r.status,'blocked');check.equal(x.counts.get('coding:a'),1);check.equal(x.counts.get('reviewing:root'),undefined)
  })
  await run('final review returns only affected task for repair',async()=>{
    const x=scenario({review:n=>n===1?{verdict:'rework',detail:'defect',issues:[{taskId:'b',detail:'fix issue'}]}:{verdict:'pass',detail:'ok',issues:[]}})
    check.equal((await x.execute()).status,'completed');check.equal(x.counts.get('coding:a'),1);check.equal(x.counts.get('coding:b'),2);check.equal(x.counts.get('reviewing:root'),2)
  })
  await run('cancellation interrupts before verification',async()=>{
    const x=scenario({cancel:true});check.equal((await x.execute()).status,'cancelled');check.equal(x.calls.filter(c=>c.startsWith('check:')).length,0)
  })
  await run('semantic criterion launches independent verifier',async()=>{
    const f=fixture(core),x=scenario({tasks:[f.task('a','review')]});check.equal((await x.execute()).status,'completed');check.equal(x.counts.get('verification:a'),1)
  })
  await run('invalid RED blocks before Coding; valid RED precedes GREEN',async()=>{
    const f=fixture(core),tasks=[f.task('a','test',true)]
    const invalid=scenario({tasks,red:false});check.equal((await invalid.execute()).status,'blocked');check.equal(invalid.counts.get('coding:a'),undefined)
    const valid=scenario({tasks});check.equal((await valid.execute()).status,'completed');check.equal(valid.calls.indexOf('testing:a')<valid.calls.indexOf('coding:a'),true)
  })
  await run('changed frozen TDD inputs block final acceptance',async()=>{
    const f=fixture(core),x=scenario({tasks:[f.task('a','test',true)],tddCurrent:false});check.equal((await x.execute()).status,'blocked');check.equal(x.counts.get('reviewing:root'),undefined)
  })
  return cases
}

export { fixture, lifecycleCases }

test('isolated lifecycle scenarios (mock libraries and native host)', async () => {
  const results = await lifecycleCases(core, assert)
  for (const r of results) assert.equal(r.pass, true, r.name + ': ' + (r.error ?? ''))
})
