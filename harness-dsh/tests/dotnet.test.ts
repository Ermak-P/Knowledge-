import assert from 'node:assert/strict'
import { test } from 'node:test'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync, symlinkSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { execFileSync } from 'node:child_process'
import { summarizeTrx, classifyTest, safePath, discoverTests, validateTaskPaths, runCheck } from '../src/dotnet.ts'
import { verifyRed } from '../src/reprolab/red-verifier.ts'
import { verifyGreen } from '../src/reprolab/green-verifier.ts'
import { verifyRegression } from '../src/reprolab/regression-verifier.ts'

function trxCases(api,assert){
  const row=(name,outcome,message='')=>({'@_testName':name,'@_outcome':outcome,Output:{ErrorInfo:{Message:message}}})
  const doc=(rows,counters={})=>({TestRun:{Results:{UnitTestResult:rows},ResultSummary:{Counters:{'@_total':String(rows.length),'@_passed':String(rows.filter(r=>r['@_outcome']==='Passed').length),'@_failed':String(rows.filter(r=>r['@_outcome']==='Failed').length),...counters}}}})
  const ok={exitCode:0,timedOut:false,aborted:false,signal:null}
  const out=[]
  const run=(name,fn)=>{try{fn();out.push({name,pass:true})}catch(e){out.push({name,pass:false,error:String(e)})}}
  run('actual TRX rows and counters, multi-target aggregation',()=>{
    const r=api.summarizeTrx([doc([row('A','Passed')]),doc([row('B','Passed'),row('C','Failed','expected')])])
    assert.equal(r.total,3);assert.equal(r.passed,2);assert.equal(r.failed,1);assert.equal(r.failures[0].name,'C');assert.equal(r.failures[0].message,'expected')
    assert.equal(api.classifyTest({...ok,exitCode:1},r),'test_failure')
  })
  run('zero test results are not pass',()=>assert.equal(api.classifyTest(ok,api.summarizeTrx([doc([])])),'not_discovered'))
  run('skipped required tests are unverified',()=>assert.equal(api.classifyTest(ok,api.summarizeTrx([doc([row('A','Passed'),row('B','NotExecuted')])])),'infra_failure'))
  run('no TRX and invalid counters fail closed',()=>{assert.throws(()=>api.summarizeTrx([]));assert.throws(()=>api.summarizeTrx([doc([row('A','Passed')],{'@_total':'2'})]));assert.throws(()=>api.summarizeTrx([doc([row('A','Passed')],{'@_timeout':'1'})]))})
  run('cancel, timeout, sandbox denial override exit zero',()=>{
    const t=api.summarizeTrx([doc([row('A','Passed')])])
    assert.equal(api.classifyTest({...ok,aborted:true},t),'cancelled')
    assert.equal(api.classifyTest({...ok,timedOut:true},t),'timed_out')
    assert.equal(api.classifyTest({...ok,sandbox:{denied:true}},t),'infra_failure')
    assert.equal(api.classifyTest({...ok,exitCode:1},t),'infra_failure')
    assert.equal(api.classifyTest(ok,t),'test_pass')
  })
  run('failed test with exit zero is inconsistent and blocked',()=>assert.equal(api.classifyTest(ok,api.summarizeTrx([doc([row('A','Failed')])])),'infra_failure'))
  return out
}

test('TRX interpretation and process outcome policy',()=>{for(const r of trxCases({summarizeTrx,classifyTest},assert))assert.equal(r.pass,true,r.name+': '+(r.error??''))})

test('discovery includes untracked and out-of-solution test projects, and denies escape/test mutation', t=>{
  const root=mkdtempSync(join(tmpdir(),'harness-dsh-test-'));t.after(()=>rmSync(root,{recursive:true,force:true}))
  execFileSync('git',['init','-q'],{cwd:root})
  mkdirSync(join(root,'Src'));mkdirSync(join(root,'ExtraTests'))
  writeFileSync(join(root,'Src','App.csproj'),'<Project/>');writeFileSync(join(root,'ExtraTests','ExtraTests.csproj'),'<Project/>')
  assert.deepEqual(discoverTests(root),['ExtraTests/ExtraTests.csproj'])
  assert.throws(()=>safePath(root,'../outside.cs'));assert.throws(()=>safePath(root,'.git/config'))
  if(process.platform!=='win32'){symlinkSync(tmpdir(),join(root,'link'),'dir');assert.throws(()=>safePath(root,'link/outside.cs'))}
  const task={id:'a',codingFiles:['ExtraTests/Foo.cs'],testFiles:[],criteria:[]}
  assert.throws(()=>validateTaskPaths(root,[task],discoverTests(root)))
})

test('native shell interface double: timeout cannot pass; valid TRX succeeds',async t=>{
  const root=mkdtempSync(join(tmpdir(),'harness-dsh-run-'));t.after(()=>rmSync(root,{recursive:true,force:true}))
  execFileSync('git',['init','-q'],{cwd:root})
  writeFileSync(join(root,'AppTests.csproj'),'<Project/>')
  const fp=()=>({available:true,tree:'unchanged'}),compare=(a,b)=>a.tree===b.tree?'same':'different'
  let timedOut=true
  const doc={TestRun:{Results:{UnitTestResult:[{'@_testName':'A','@_outcome':'Passed'}]},ResultSummary:{Counters:{'@_total':'1','@_passed':'1','@_failed':'0'}}}}
  const ctx={shell:{resolve:x=>x,async execute(spec){const resultDir=spec.command.match(/--results-directory "([^"]+)"/)[1];writeFileSync(join(resultDir,'result.trx'),'mock xml');return {result:async()=>({exitCode:0,timedOut,aborted:false,signal:null,stdout:{text:''},stderr:{text:''}})}}}}
  const c={kind:'test',target:'AppTests.csproj'},signal=new AbortController().signal
  const check=()=>runCheck(ctx,{session:{}},root,c,fp,compare,()=>doc,signal)
  assert.equal((await check()).outcome,'unverified');timedOut=false;assert.equal((await check()).outcome,'pass')
})

test('reused ReproLab verifiers distinguish RED, GREEN, changed tests and regression',()=>{
  const classifier=(kind)=>({kind,matchedTests:['A'],summary:kind,fingerprint:kind==='test_failure'?'failure':null})
  const red={testPatchHash:'tests',commandHash:'command',fixFrozen:false,classifier:classifier('test_failure')}
  assert.equal(verifyRed(red).verdict,'valid_red')
  assert.equal(verifyRed({...red,classifier:classifier('timed_out')}).verdict,'insufficient')
  assert.equal(verifyRed({...red,fixFrozen:true}).verdict,'insufficient')
  const green={testPatchHash:'tests',commandHash:'command',classifier:classifier('test_pass')}
  assert.equal(verifyGreen({red:{...red,fingerprint:'failure'},green}).verdict,'valid_green')
  assert.equal(verifyGreen({red:{...red,fingerprint:'failure'},green:{...green,testPatchHash:'changed'}}).verdict,'insufficient')
  assert.equal(verifyRegression({baseline:{ran:true,failures:['old']},candidate:{comparable:true,failures:['new']}}).verdict,'regression')
  assert.equal(verifyRegression({baseline:{ran:true,failures:[]},candidate:{comparable:false,failures:[]}}).verdict,'inconclusive')
})
