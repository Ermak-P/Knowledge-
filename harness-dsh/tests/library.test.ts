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
