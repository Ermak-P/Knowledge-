import assert from 'node:assert/strict'
import { test } from 'node:test'
import { Context } from '@deepseek-ai/cordis'
import { mountAgentLoopTestDependencies, mountAgentLoopTestHarness } from '@deepseek-ai/dsh-agent-loop-testkit'
import { createUserMessage, LlmAdapter, type StreamChunk, type ToolCallId } from '@deepseek-ai/dsh-llm'
import type { SessionId } from '@deepseek-ai/dsh-session'
import { defineTool } from '@deepseek-ai/dsh-tools'

import * as v from '@bpc-oss/dsh-verification'
import * as e from '@bpc-oss/dsh-evidence'
import * as s from 'stalegreen'
import { EvidenceBook } from '../src/lifecycle.ts'

class EvidenceAdapter extends LlmAdapter {
  requests=0
  turns=new Map()
  async resolveModel(provider,model){return {provider,id:model,name:model}}
  async *stream({sessionId}){
    this.requests++
    const step=(this.turns.get(sessionId)??0)+1
    this.turns.set(sessionId,step)
    if(step===1){
      yield {type:'block-start',index:0,blockType:'tool-call'}
      yield {type:'block-end',index:0,block:{type:'tool-call',id:('call-'+this.requests) as ToolCallId,name:'harness_run_check',arguments:'{"criterion_id":"ac"}'}}
      yield {type:'finish',reason:{kind:'tool-calls'}}
    }else{
      yield {type:'block-start',index:0,blockType:'text'}
      yield {type:'text-delta',index:0,text:'done'}
      yield {type:'block-end',index:0,block:{type:'text',text:'done'}}
      yield {type:'finish',reason:{kind:'stop'}}
    }
  }
}

for(const concurrent of [false,true])test(
  'real DSH tool dispatcher isolates '+(concurrent?'concurrent':'sequential')+' session evidence',
  {timeout:30000}, async t=>{
  const ctx=new Context();t.after(()=>ctx.fiber.dispose())
  await mountAgentLoopTestDependencies(ctx)
  const fp=()=>({available:true,tree:'fixture',head:null,ms:0})
  const book=new EvidenceBook({v,e,s},fp)
  const task=id=>({id,objective:'build '+id,codingFiles:[],testFiles:[],tdd:false,criteria:[{id:'ac',desc:'build succeeds',kind:'build',target:'App.csproj'}]})
  const a=book.add(task('a'),'run','root',[{kind:'user-message',eventRef:'root:1',seq:1,text:'build'}])
  const b=book.add(task('b'),'run','root',[{kind:'user-message',eventRef:'root:1',seq:1,text:'build'}])
  const bySession=new Map([['native-a','a'],['native-b','b']])
  ctx.on('tools/result',(exec,result)=>{
    if(exec.name!=='harness_run_check'||!exec.agent)return
    const sid=String(exec.agent.session.id),taskId=bySession.get(sid)
    if(!taskId)return
    void book.capture({taskId,role:'verification',agentId:String(exec.agent.id),sessionId:sid},{callId:String(exec.callId),name:exec.name,arguments:exec.arguments,isError:result.isError,value:result.isError?undefined:JSON.parse(result.value)})
  })
  const adapter=new EvidenceAdapter();ctx.llm.registerAdapter(['mock'],adapter)
  ctx.tools.register(defineTool({
    name:'harness_run_check',description:'Test-only controlled actual tool',
    parameters:{criterion_id:{type:'string',required:true}},
    output:{schema:{type:'string'},render:(_args,value)=>[{type:'text',text:value}]},
    async execute(_args,exec){
      const failed=concurrent&&exec.agent.session.id==='native-b'
      return JSON.stringify({kind:'build',outcome:failed?'fail':'pass',exitCode:failed?1:0,summary:'real tool dispatch; process mocked',fingerprint:fp()})
    }
  }))
  const harness=await mountAgentLoopTestHarness(ctx)
  async function run(sid){
    const agent=await harness.create(sid as SessionId,{provider:'mock',model:'mock'})
    agent.followup(createUserMessage({content:[{type:'text',text:'run check'}],source:{kind:'user'}}))
    await agent.whenIdle()
  }
  if(concurrent)await Promise.all([run('native-a'),run('native-b')])
  else{
    await run('native-a')
    assert.equal((await book.evaluate(b)).status,'blocked')
    await run('native-b')
  }
  assert.equal((await book.evaluate(a)).status,'pass')
  assert.equal((await book.evaluate(b)).status,concurrent?'fail':'pass')
  assert.equal(a.refs[0].producerSessionId,'native-a');assert.equal(b.refs[0].producerSessionId,'native-b')
  assert.equal(adapter.requests,4)
})
