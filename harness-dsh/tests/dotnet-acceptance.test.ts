import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { cpSync, existsSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from 'node:fs'
import { setTimeout } from 'node:timers/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { Context } from '@deepseek-ai/cordis'
import LocalBash from '@deepseek-ai/dsh-bash-local'
import LocalPowerShell from '@deepseek-ai/dsh-pwsh-local'
import LocalSubprocess from '@deepseek-ai/dsh-subprocess-local'
import * as xml from 'fast-xml-parser'
import * as stalegreen from 'stalegreen'
import { createTrxParser, createWorkspaceFingerprint, discoverTests, runCheck } from '../src/dotnet.ts'

test('real DSH shell, SDK build/test, discovery and TRX with a Unicode workspace', {timeout:180000}, async t=>{
  const root=realpathSync(mkdtempSync(join(tmpdir(),'DSH vérification ')))
  const ctx=new Context()
  t.after(async()=>{try{await ctx.fiber.dispose()}finally{rmSync(root,{recursive:true,force:true})}})
  cpSync(new URL('../fixtures/dotnet/',import.meta.url),root,{recursive:true,filter:path=>!/[\\/](bin|obj|TestResults)$/.test(path)})
  execFileSync('git',['init','-q'],{cwd:root})
  const projects=discoverTests(root)
  assert.deepEqual(projects,['ArithmeticTests/ArithmeticTests.csproj','BehaviorTests/BehaviorTests.csproj'])
  await ctx.plugin(LocalSubprocess)
  await ctx.plugin(process.platform==='win32'?LocalPowerShell:LocalBash)
  const parser=createTrxParser(xml)
  const fresh=createWorkspaceFingerprint(root,stalegreen)
  const check=(kind,target,options={})=>runCheck(ctx,{session:{}},root,{kind,target},fresh,stalegreen.compareFingerprints,options.parser??parser,options.signal??new AbortController().signal,options.timeout??120000)
  const solution='Acceptance.sln'
  const arithmetic=projects[0]
  const production=join(root,'App','Calculator.cs')
  const testFile=join(root,'ArithmeticTests','SumTests.cs')
  const originalCode=readFileSync(production,'utf8')
  const originalTest=readFileSync(testFile,'utf8')
  function expect(result,outcome,exitCode){
    assert.equal(result.outcome,outcome,result.summary)
    if(exitCode!==undefined)assert.equal(result.exitCode,exitCode,result.summary)
  }

  expect(await check('build',solution),'pass',0)
  for(const target of projects){
    const green=await check('test',target)
    expect(green,'pass',0)
    assert.ok(green.passed>0)
  }
  writeFileSync(production,'this does not compile')
  const buildFailure=await check('build',solution)
  expect(buildFailure,'fail')
  assert.notEqual(buildFailure.exitCode,0)
  writeFileSync(production,originalCode)
  expect(await check('build',solution),'pass',0)

  writeFileSync(testFile,originalTest.replace('Equal(5','Equal(6'))
  expect(await check('build',solution),'pass',0)
  const testFailure=await check('test',arithmetic)
  expect(testFailure,'fail')
  assert.notEqual(testFailure.exitCode,0)
  assert.match(testFailure.failures[0].name,/AddsTwoNumbers/)
  writeFileSync(testFile,originalTest.replace('[Fact]','[Fact(Skip = "Acceptance fixture")]'))
  const skip=await check('test',arithmetic)
  expect(skip,'unverified')
  assert.equal(skip.skipped,1)
  writeFileSync(testFile,originalTest)
  expect(await check('test',arithmetic),'pass',0)

  assert.throws(()=>parser('<TestRun><Broken></TestRun>'),/invalid or unsafe/)
  expect(await check('test',arithmetic,{parser:()=>parser('<TestRun><Broken></TestRun>')}),'unverified')
  const empty=await check('test','App/App.csproj')
  expect(empty,'unverified')
  assert.match(empty.summary,/no fresh TRX/)
  const timed=await check('test',arithmetic,{timeout:30})
  expect(timed,'unverified')
  assert.equal(timed.classifier,'timed_out',timed.summary)
  const markerDir=mkdtempSync(join(tmpdir(),'dsh-child-'))
  t.after(()=>{delete process.env.HARNESS_FIXTURE_SIGNAL_FILE;rmSync(markerDir,{recursive:true,force:true})})
  async function whileTestRuns(markerName,action){
    const marker=join(markerDir,markerName)
    process.env.HARNESS_FIXTURE_SIGNAL_FILE=marker
    const controller=new AbortController()
    const pending=check('test',projects[1],{signal:controller.signal})
    try{
      for(let attempt=0;attempt<300&&!existsSync(marker);attempt++)await setTimeout(50)
      assert.ok(existsSync(marker),'the live test host did not write its PID')
      await action(marker,controller)
      return {result:await pending,pid:Number(readFileSync(marker,'utf8'))}
    }finally{
      controller.abort()
      await pending
    }
  }
  const stale=await whileTestRuns('stale',marker=>{
    writeFileSync(production,originalCode+'\n// Edited while the test host ran.\n')
    writeFileSync(marker+'.release','')
  })
  expect(stale.result,'unverified')
  assert.match(stale.result.summary,/workspace changed/)
  writeFileSync(production,originalCode)

  const {result,pid}=await whileTestRuns('cancel',(_marker,controller)=>controller.abort())
  expect(result,'unverified')
  assert.ok(Number.isInteger(pid)&&pid>0)
  let state='exited'
  try{
    process.kill(pid,0)
    state=process.platform==='linux'
      ?readFileSync('/proc/'+pid+'/stat','utf8').split(') ').at(-1).split(' ')[0]
      :'running'
  }catch(error){
    if(!['ESRCH','ENOENT'].includes(error.code))throw error
  }
  // This container's PID 1 can retain a zombie after the DSH process group exits.
  if(state==='Z')t.diagnostic('test host exited; PID 1 retained its zombie record')
  else assert.equal(state,'exited','test host remained live after cancellation')

})
