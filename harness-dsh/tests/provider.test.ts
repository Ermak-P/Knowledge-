import assert from 'node:assert/strict'
import { once } from 'node:events'
import { createServer } from 'node:http'
import { test } from 'node:test'
import { Context } from '@deepseek-ai/cordis'
import { mountAgentLoopTestDependencies, mountAgentLoopTestHarness } from '@deepseek-ai/dsh-agent-loop-testkit'
import { createUserMessage } from '@deepseek-ai/dsh-llm'
import * as openai from '@deepseek-ai/dsh-llm-pi-ai'
import { defineTool } from '@deepseek-ai/dsh-tools'

test('DSH OpenAI-compatible HTTP transport handles tool calls with reasoning off', {timeout:20000}, async t=>{
  const requests=[]
  const server=createServer(async(req,res)=>{
    const body=[]
    for await(const chunk of req)body.push(chunk)
    requests.push({url:req.url,body:JSON.parse(Buffer.concat(body).toString())})
    const index=requests.length
    res.writeHead(200,{'content-type':'text/event-stream'})
    const send=(delta,reason)=>res.write('data: '+JSON.stringify({
      id:'chatcmpl-fixture',created:1,object:'chat.completion.chunk',model:'fixture',
      choices:[{index:0,delta,finish_reason:reason}]
    })+'\n\n')
    send({role:'assistant'},null)
    if(index<3){
      send({tool_calls:[{index:0,id:'call_'+index,type:'function',function:{
        name:'probe',arguments:index===1?'{"value":"wire"}':'{"value":4}'
      }}]},null)
      send({},'tool_calls')
    }else{
      send({content:'done'},null)
      send({},'stop')
    }
    res.end('data: [DONE]\n\n')
  }).listen(0,'127.0.0.1')
  t.after(()=>{server.closeAllConnections();return new Promise(resolve=>server.close(resolve))})
  await once(server,'listening')

  const ctx=new Context()
  const originalKey=process.env.DSH_FIXTURE_API_KEY
  process.env.DSH_FIXTURE_API_KEY='fixture-key'
  t.after(()=>{if(originalKey===undefined)delete process.env.DSH_FIXTURE_API_KEY;else process.env.DSH_FIXTURE_API_KEY=originalKey})
  t.after(()=>ctx.fiber.dispose())
  await mountAgentLoopTestDependencies(ctx)
  await ctx.plugin(openai,{providers:{fixture:{
    api:'openai-completions',baseURL:'http://127.0.0.1:'+server.address().port+'/v1',
    apiKeyEnv:'DSH_FIXTURE_API_KEY',timeoutMs:3000,
    models:[{id:'fixture',contextWindow:8192,maxTokens:512,reasoningEfforts:{off:'off',low:'low'}}],
  }}})
  let calls=0
  ctx.tools.register(defineTool({
    name:'probe',description:'Echo a string',parameters:{value:{type:'string',required:true}},
    output:{schema:{type:'string'},render:(_args,value)=>[{type:'text',text:value}]},
    async execute(args){calls++;assert.equal(args.value,'wire');return args.value},
  }))
  const outcomes=[]
  ctx.on('tools/result',(exec,result)=>{if(exec.name==='probe')outcomes.push(result.isError)})
  const harness=await mountAgentLoopTestHarness(ctx)
  const agent=await harness.create('provider-acceptance',{provider:'fixture',model:'fixture',reasoningEffort:'off'})
  agent.followup(createUserMessage({source:{kind:'user'},content:[{type:'text',text:'Exercise the tool'}]}))
  await agent.whenIdle()
  assert.equal(calls,1,JSON.stringify(agent.session.snapshotEvents().filter(e=>e.type==='turn/end'||e.type==='step/end')))
  assert.deepEqual(outcomes,[false,true])
  assert.equal(requests.length,3)
  assert.ok(requests.every(({url,body})=>url==='/v1/chat/completions'&&[undefined,'off'].includes(body.reasoning_effort)))
  assert.ok(requests[2].body.messages.some(message=>message.role==='tool'&&message.tool_call_id==='call_2'))
})
