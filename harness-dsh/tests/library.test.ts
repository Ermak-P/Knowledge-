// Real upstream library smoke/negative tests. No fake production imports.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import * as v from '@bpc-oss/dsh-verification'
import * as e from '@bpc-oss/dsh-evidence'
import * as s from 'stalegreen'
import { EvidenceBook } from '../src/lifecycle.ts'

test('actual upstream exports: independent contracts, exact selectors, latest fail and freshness',async()=>{
  let tree='initial',available=true
  const fresh=()=>({available,tree:available?tree:null,head:null,ms:0})
  const book=new EvidenceBook({v,e,s},fresh)
  const add=id=>book.add({id,objective:'build '+id,codingFiles:[],testFiles:[],tdd:false,criteria:[{id:'build',desc:'dotnet build succeeds',kind:'build',target:'App.csproj'}]},'run','root',[{kind:'user-message',eventRef:'root:1',seq:1,text:'build'}])
  const a=add('a'),b=add('b')
  let call=0
  const capture=(state,outcome,args={criterion_id:'build'})=>book.capture({taskId:state.task.id,role:'verification',agentId:'agent-'+call,sessionId:'session-'+call},{callId:'call-'+(++call),name:'harness_run_check',arguments:args,isError:false,value:{kind:'build',outcome,exitCode:outcome==='pass'?0:1,summary:'actual result',fingerprint:fresh()}})
  assert.notEqual(a.identity.contractId,b.identity.contractId)
  assert.equal((await book.evaluate(a)).status,'blocked')
  await capture(a,'pass',{criterion_id:'build',different:true});assert.equal((await book.evaluate(a)).status,'blocked')
  await capture(a,'pass');assert.equal((await book.evaluate(a)).status,'pass')
  assert.equal((await book.evaluate(b)).status,'blocked')
  await capture(a,'fail');assert.equal((await book.evaluate(a)).status,'fail')
  await capture(a,'pass');assert.equal((await book.evaluate(a)).status,'pass')
  tree='changed';assert.equal((await book.evaluate(a)).status,'blocked')
  await capture(a,'pass');assert.equal((await book.evaluate(a)).status,'pass')
  available=false;assert.equal((await book.evaluate(a)).status,'blocked')
})

import { execFileSync } from 'node:child_process'
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createWorkspaceFingerprint, runCheck } from '../src/dotnet.ts'

test('real Git freshness and upstream gate reject old, replaced and interrupted evidence',async t=>{
  const root=mkdtempSync(join(tmpdir(),'dsh-stale-'))
  t.after(()=>rmSync(root,{recursive:true,force:true}))
  const git=(...args)=>execFileSync('git',args,{cwd:root})
  git('init','-q')
  const files=['App.cs','Tests.cs','App.csproj','Directory.Build.props']
  const edit=(name,text)=>writeFileSync(join(root,name),text)
  for(const name of files)edit(name,'initial')
  git('add','.')
  const fresh=createWorkspaceFingerprint(root,s)
  assert.equal(fresh().available,true,fresh().reason)
  const book=new EvidenceBook({v,e,s},fresh)
  const basis=[{kind:'user-message',eventRef:'root:1',seq:1,text:'verify'}]
  const criterion={id:'file',desc:'App.cs exists',kind:'file',target:'App.cs'}
  const add=(book,id,criteria=[criterion])=>book.add({id,objective:'verify source',codingFiles:[],testFiles:[],tdd:false,criteria},'run','root',basis)
  const task=add(book,'one'), other=add(book,'two')
  const capture=async(state,options={})=>{
    const value=await runCheck({shell:{}},{session:{}},root,criterion,fresh,s.compareFingerprints,undefined,options.signal??new AbortController().signal)
    return book.capture({taskId:state.task.id,role:'host',agentId:'host',sessionId:'root'},{callId:'call-'+book.seq,name:'harness_run_check',arguments:{criterion_id:'file'},isError:false,value})
  }
  const gate=async(state,status)=>assert.equal((await book.evaluate(state)).status,status)
  await capture(task)
  await gate(task,'pass')
  await gate(other,'blocked')
  for(const name of files){
    edit(name,'changed')
    await gate(task,'blocked')
    await capture(task)
    await gate(task,'pass')
  }
  // A new run cannot trust a previous session's evidence, even if copied into memory.
  const restart=new EvidenceBook({v,e,s},fresh)
  const newTask=add(restart,'one',[{...criterion,desc:'revised requirement'}])
  newTask.refs.push(...task.refs)
  assert.equal((await restart.evaluate(newTask)).status,'blocked')
  book.beginAttempt(task)
  await gate(task,'blocked')
  await capture(task)
  await gate(task,'pass')
  await capture(task,{signal:AbortSignal.abort()})
  await gate(task,'blocked')
  await capture(task)
  await gate(task,'pass')
  const read=book.store.read.bind(book.store)
  book.store.read=async key=>{edit('App.cs','during gate');return read(key)}
  await gate(task,'blocked')
  book.store.read=read
  git('update-index','--assume-unchanged','App.cs')
  assert.equal(fresh().available,false)
  await gate(task,'blocked')
  git('update-index','--no-assume-unchanged','App.cs')
  edit('.gitignore','Ignored.cs\n**/obj/\n')
  await capture(task)
  await gate(task,'pass')
  edit('Ignored.cs','untracked build input')
  assert.match(fresh().reason,/Git-ignored .NET input/)
  await gate(task,'blocked')
  edit('.gitignore','**/obj/\n')
  await capture(task)
  await gate(task,'pass')
  const shell={resolve:x=>x,async execute(){
    edit('App.cs','changed during build')
    return {result:async()=>({exitCode:0})}
  }}
  const result=await runCheck({shell},{session:{}},root,{kind:'build',target:'App.csproj'},fresh,s.compareFingerprints,undefined,new AbortController().signal)
  assert.equal(result.outcome,'unverified')
  assert.match(result.summary,/workspace changed/)
})
